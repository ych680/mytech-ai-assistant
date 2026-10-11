"""Offline runner integration and fault injection; real tools, no real provider."""

from contextlib import contextmanager, redirect_stdout
from copy import deepcopy
from hashlib import sha256
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.request

from evaluations import fixtures
from evaluations import run_tool3 as runner
from evaluations.scenario_contract import load_manifest
from tools import tool3_executor as executor
from tools import tool3_tokenproxy as adapter


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.manifest = load_manifest()
        self.dataset_bytes = fixtures.DATASET_SOURCE.read_bytes()
        self.knowledge_bytes = fixtures.KNOWLEDGE_SOURCE.read_bytes()
        self.network_guards = []
        for target in ("socket.create_connection", "socket.socket.connect",
                       "urllib.request.urlopen", "urllib.request.OpenerDirector.open",
                       "tools.tool3_tokenproxy.http_transport", "tools.tool3_tokenproxy.getpass.getpass"):
            block = patch(target, side_effect=AssertionError("Real provider/credentials forbidden"))
            self.network_guards.append(block.start())
            self.addCleanup(block.stop)

    def tearDown(self):
        for guard in self.network_guards:
            guard.assert_not_called()
        self.assertEqual(fixtures.DATASET_SOURCE.read_bytes(), self.dataset_bytes)
        self.assertEqual(fixtures.KNOWLEDGE_SOURCE.read_bytes(), self.knowledge_bytes)

    @contextmanager
    def manifest_path(self, manifest):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scenarios.json"
            path.write_text(json.dumps(manifest, ensure_ascii=True), encoding="utf-8")
            yield path

    def request(self, *, method="POST", url=adapter.API_URL):
        return urllib.request.Request(url, data=b"{}", method=method,
                                      headers={"Authorization": "Bearer " + runner.OFFLINE_MARKER})

    def invoke(self, transport, request=None):
        return transport(self.request() if request is None else request,
                         timeout=adapter.HTTP_TIMEOUT_SECONDS,
                         max_response_bytes=adapter.MAX_RESPONSE_BYTES)

    @contextmanager
    def track_fixtures(self):
        roots = []
        real_prepare = runner.prepare_fixture

        @contextmanager
        def tracked(identifier):
            with real_prepare(identifier) as fixture:
                roots.append(fixture.bindings.dataset_path.parent)
                yield fixture

        with patch.object(runner, "prepare_fixture", tracked):
            yield roots
        self.assertTrue(all(not root.exists() for root in roots))

    def test_all_sixteen_real_execution_paths_match_the_authored_contract(self):
        with self.track_fixtures() as roots:
            cases = runner.run_all_scenarios()
        self.assertEqual(len(roots), 16)
        self.assertEqual(len(set(roots)), 16)
        self.assertEqual([case["scenario_id"] for case in cases],
                         [scenario["id"] for scenario in self.manifest["scenarios"]])
        for case, scenario in zip(cases, self.manifest["scenarios"]):
            with self.subTest(scenario=case["scenario_id"]):
                self.assertEqual(case["scenario_version"], scenario["version"])
                self.assertEqual(case["evaluation_mode"], "scripted_offline")
                self.assertEqual(case["runner_status"], "completed")
                self.assertEqual(case["infrastructure_failures"], [])
                self.assertEqual(case["contract_comparison"], {"status": "matched", "mismatches": []})
                self.assertEqual(case["actual"]["api_requests"], case["completion_attempts_observed"])
                self.assertEqual(case["transport_invocations"], len(scenario["script"]))
                self.assertEqual(case["script"]["steps_consumed"], len(scenario["script"]))
                self.assertEqual(case["script"]["steps_remaining"], 0)
                self.assertEqual(case["fixture"]["integrity"], "passed")
                self.assertEqual(case["fixture"]["cleanup"], "passed")
                self.assertEqual(case["fixture"]["source_dataset_sha256"], sha256(self.dataset_bytes).hexdigest())
                self.assertEqual(case["fixture"]["source_knowledge_sha256"], sha256(self.knowledge_bytes).hexdigest())

    def test_native_response_envelope_preserves_ids_names_and_json_arguments(self):
        steps = self.manifest["scenarios"][2]["script"]
        transport = runner.ScriptedTransport(steps)
        response = self.invoke(transport)
        choice = json.loads(response.body)["choices"][0]
        self.assertEqual(choice["finish_reason"], "tool_calls")
        self.assertEqual(choice["message"]["role"], "assistant")
        for actual, scripted in zip(choice["message"]["tool_calls"], steps[0]["calls"]):
            self.assertEqual(actual["id"], scripted["id"])
            self.assertEqual(actual["type"], "function")
            self.assertEqual(actual["function"]["name"], scripted["name"])
            self.assertEqual(json.loads(actual["function"]["arguments"]), scripted["arguments"])
        final = json.loads(self.invoke(transport).body)["choices"][0]
        self.assertEqual(final["finish_reason"], "stop")
        self.assertEqual(final["message"]["content"], steps[1]["text"])
        self.assertEqual([row["id"] for row in transport.tool_calls], ["v1", "k1"])
        self.assertEqual(transport.transport_invocations, 2)
        self.assertEqual(transport._responses, [])

    def test_multiple_calls_use_real_executor_and_resource_functions(self):
        with patch.object(executor, "execute_tool_calls", wraps=executor.execute_tool_calls) as execute, \
             patch.object(executor.validate_products, "load_dataset", wraps=executor.validate_products.load_dataset) as load, \
             patch.object(executor.build_knowledge, "check_knowledge", wraps=executor.build_knowledge.check_knowledge) as check:
            case = runner.run_scenario("AE-03")
        execute.assert_called_once()
        load.assert_called_once()
        # Baseline fixture verification plus the actual executor knowledge check.
        self.assertEqual(check.call_count, 2)
        rows = case["actual"]["tool_results"]
        self.assertEqual([row["tool_call_id"] for row in rows], ["v1", "k1"])
        self.assertEqual(rows[0]["data"], {"products": 27, "categories": 9, "strict_v1": True})
        self.assertEqual(rows[1]["data"], {"records": 27})

    def test_sequential_execution_has_two_real_batches_and_three_completions(self):
        with patch.object(executor, "execute_tool_calls", wraps=executor.execute_tool_calls) as execute:
            case = runner.run_scenario("AE-11")
        self.assertEqual(execute.call_count, 2)
        self.assertEqual(case["actual"]["tool_rounds"], 2)
        self.assertEqual(case["actual"]["api_requests"], 3)
        self.assertEqual(case["transport_invocations"], 3)
        self.assertEqual([(row["script_step"], row["id"]) for row in case["tool_calls"]],
                         [(1, "v1"), (2, "k1")])

    def test_failed_validation_and_skipped_inspection_are_preserved(self):
        with patch.object(executor, "_read_knowledge", wraps=executor._read_knowledge) as read:
            case = runner.run_scenario("AE-08")
        read.assert_not_called()
        rows = case["actual"]["tool_results"]
        self.assertEqual([(row["status"], row["code"]) for row in rows],
                         [("failed", "dataset_invalid"), ("skipped", "dataset_invalid")])
        self.assertTrue(all(row["data"] is None for row in rows))
        self.assertTrue(rows[0]["diagnostics"])
        self.assertEqual(case["actual"]["status"], "completed")
        self.assertEqual(case["actual"]["execution_status"], "failed")

    def test_knowledge_inconsistency_is_observed_from_the_real_checker(self):
        case = runner.run_scenario("AE-07")
        row = case["actual"]["tool_results"][0]
        self.assertEqual((row["status"], row["code"]), ("failed", "knowledge_inconsistent"))
        self.assertEqual(row["diagnostics"], ["records[0].Reference Price: missing or differs from dataset"])
        self.assertNotEqual(case["fixture"]["knowledge_sha256"], case["fixture"]["source_knowledge_sha256"])

    def test_invalid_batches_preserve_rejected_attempts_and_execute_nothing(self):
        for identifier, rejected in (("AE-09", "generate_knowledge"), ("AE-10", "check_knowledge")):
            with self.subTest(scenario=identifier), \
                 patch.object(executor.validate_products, "load_dataset", wraps=executor.validate_products.load_dataset) as load:
                case = runner.run_scenario(identifier)
            load.assert_not_called()
            self.assertEqual(case["actual"]["tool_results"], [])
            self.assertEqual(case["actual"]["code"], "invalid_tool_calls")
            self.assertEqual(case["actual"]["tool_rounds"], 0)
            self.assertEqual([row["name"] for row in case["tool_calls"]], ["validate_products", rejected])
            self.assertEqual(case["runner_status"], "completed")
            self.assertNotIn("arguments", case["tool_calls"][1])

    def test_http_502_after_partial_execution_preserves_actual_result(self):
        case = runner.run_scenario("AE-14")
        actual = case["actual"]
        self.assertEqual((actual["status"], actual["code"], actual["execution_status"]),
                         ("failed", "http_error_502", "success"))
        self.assertEqual(actual["tool_results"][0]["tool_call_id"], "v1")
        self.assertEqual(actual["tool_results"][0]["data"]["products"], 27)
        self.assertIsNone(actual["assistant_response"])
        self.assertEqual(case["transport_invocations"], 2)
        self.assertEqual(case["infrastructure_failures"], [])

    def test_execution_limit_records_third_attempt_without_third_execution(self):
        with patch.object(executor, "execute_tool_calls", wraps=executor.execute_tool_calls) as execute:
            case = runner.run_scenario("AE-16")
        self.assertEqual(execute.call_count, 2)
        self.assertEqual(case["actual"]["code"], "execution_limit_reached")
        self.assertEqual([row["id"] for row in case["tool_calls"]], ["v1", "k1", "v2"])
        self.assertEqual([row["tool_call_id"] for row in case["actual"]["tool_results"]], ["v1", "k1"])
        self.assertEqual(case["actual"]["tool_rounds"], 2)
        self.assertEqual(case["transport_invocations"], 3)

    def test_missing_operations_and_contradictory_explanations_are_not_scored(self):
        for identifier in ("AE-04", "AE-05", "AE-12", "AE-15"):
            with self.subTest(scenario=identifier):
                case = runner.run_scenario(identifier)
                self.assertEqual(case["contract_comparison"]["status"], "matched")
                self.assertNotIn("task_verdict", case)
                self.assertNotIn("human_review", case)
                self.assertNotIn("expected", case)
                self.assertNotIn("operation_handling", case)
        contradictory = runner.run_scenario("AE-15")["actual"]
        self.assertEqual(contradictory["tool_results"][0]["status"], "failed")
        self.assertEqual(contradictory["assistant_response"], "Validation passed; all 27 products are valid.")

    def test_actual_evidence_is_not_populated_from_authored_expectations(self):
        # A valid authored oracle can disagree with reality. Changing the fixture
        # leaves the oracle intact and must expose the real negative tool result.
        manifest = deepcopy(self.manifest)
        manifest["scenarios"][0]["fixture_id"] = "FD"
        before = deepcopy(manifest)
        with self.manifest_path(manifest) as path:
            case = runner.run_scenario("AE-01", manifest_path=path)
        self.assertEqual(manifest, before)
        self.assertEqual(case["actual"]["code"], "tool_execution_failed")
        self.assertEqual(case["actual"]["tool_results"][0]["code"], "dataset_invalid")
        self.assertEqual(case["contract_comparison"]["status"], "mismatched")
        self.assertIn("code", case["contract_comparison"]["mismatches"])
        self.assertIn("tool_results[0].status", case["contract_comparison"]["mismatches"])
        self.assertEqual(case["runner_status"], "completed")

    def test_contract_comparison_checks_order_identity_and_counts_without_mutation(self):
        case = runner.run_scenario("AE-03")
        actual = case["actual"]
        expected = deepcopy(self.manifest["scenarios"][2]["expected"])
        before = deepcopy(actual)
        expected["tool_results"].reverse()
        expected["orchestration"]["api_requests"] = 3
        comparison = runner.compare_orchestration(actual, expected)
        self.assertEqual(comparison["status"], "mismatched")
        self.assertIn("api_requests", comparison["mismatches"])
        self.assertIn("tool_results[0].tool_call_id", comparison["mismatches"])
        self.assertEqual(actual, before)
        no_tools = runner.run_scenario("AE-04")["actual"]
        no_tools["api_requests"] = True
        comparison = runner.compare_orchestration(no_tools, self.manifest["scenarios"][3]["expected"])
        self.assertIn("api_requests", comparison["mismatches"])

    def test_pretransport_failure_distinguishes_completion_attempts_and_transport_calls(self):
        with patch.object(adapter, "MAX_CONVERSATION_BYTES", 1):
            case = runner.run_scenario("AE-01")
        self.assertEqual(case["actual"]["api_requests"], 1)
        self.assertEqual(case["completion_attempts_observed"], 1)
        self.assertEqual(case["transport_invocations"], 0)
        self.assertEqual(case["actual"]["code"], "conversation_too_large")
        self.assertEqual(case["script"]["steps_remaining"], 2)
        self.assertIn("unconsumed_script_steps", case["infrastructure_failures"])
        self.assertEqual(case["runner_status"], "infrastructure_failure")

    def test_script_exhaustion_is_infrastructure_failure_with_partial_real_evidence(self):
        real_transport = runner.ScriptedTransport
        with patch.object(runner, "ScriptedTransport", side_effect=lambda steps: real_transport(steps[:-1])):
            case = runner.run_scenario("AE-01")
        self.assertEqual(case["runner_status"], "infrastructure_failure")
        self.assertIn("script_exhausted", case["infrastructure_failures"])
        self.assertEqual(case["actual"]["code"], "transport_error")
        self.assertEqual(case["actual"]["tool_results"][0]["status"], "success")
        self.assertEqual(case["transport_invocations"], 2)
        self.assertEqual(case["script"]["steps_consumed"], 1)
        self.assertEqual(case["fixture"]["cleanup"], "passed")

    def test_unexpected_transport_request_is_flagged_without_consuming_a_step(self):
        transport = runner.ScriptedTransport(self.manifest["scenarios"][0]["script"])
        with self.assertRaisesRegex(runner.EvaluationInfrastructureError, "unexpected_transport_request"):
            self.invoke(transport, self.request(method="GET"))
        self.assertEqual(transport.failure_codes, ["unexpected_transport_request"])
        self.assertEqual(transport.steps_consumed, 0)
        self.assertEqual(transport.transport_invocations, 1)
        self.assertEqual(transport.tool_calls, [])

    def test_malformed_script_data_is_never_executed_as_code(self):
        for steps in ([{"type": "python", "code": "forbidden()"}],
                      [{"type": "final", "text": None}],
                      [{"type": "tool_calls", "calls": [None]}]):
            with self.subTest(steps=steps), self.assertRaises(runner.EvaluationInfrastructureError):
                runner.ScriptedTransport(steps)
        manifest = deepcopy(self.manifest)
        manifest["scenarios"][0]["script"][-1]["text"] = "<thinking>unfinished"
        with self.manifest_path(manifest) as path:
            case = runner.run_scenario("AE-01", manifest_path=path)
        self.assertEqual(case["actual"]["code"], "invalid_thinking_markup")
        self.assertIn("invalid_script_response", case["infrastructure_failures"])

    def test_invalid_manifest_fixture_identifier_and_unknown_id_fail_before_execution(self):
        for invalid in ("FZ", "../F0"):
            manifest = deepcopy(self.manifest)
            manifest["scenarios"][0]["fixture_id"] = invalid
            with self.subTest(fixture=invalid), self.manifest_path(manifest) as path, \
                 patch.object(runner, "prepare_fixture") as prepare, \
                 self.assertRaisesRegex(runner.EvaluationInfrastructureError, "invalid_manifest"):
                runner.run_all_scenarios(manifest_path=path)
            prepare.assert_not_called()
        with patch.object(runner, "prepare_fixture") as prepare, \
             self.assertRaisesRegex(runner.EvaluationInfrastructureError, "unknown_scenario"):
            runner.run_scenario("AE-99")
        prepare.assert_not_called()

    def test_fixture_preparation_failure_is_sanitized_and_does_not_invent_actuals(self):
        with patch.object(runner, "prepare_fixture", side_effect=fixtures.FixtureError("private-test-sentinel")):
            case = runner.run_scenario("AE-01")
        self.assertEqual(case["infrastructure_failures"], ["fixture_failure"])
        self.assertIsNone(case["actual"])
        self.assertEqual(case["fixture"]["integrity"], "not_prepared")
        self.assertEqual(case["completion_attempts_observed"], 0)
        self.assertEqual(case["transport_invocations"], 0)
        self.assertNotIn("private-test-sentinel", json.dumps(case))

    def test_unexpected_exception_preserves_observed_tool_feedback_and_cleanup(self):
        real_complete = adapter.TokenProxyClient.complete

        def crash_after_feedback(client, messages, *, allow_tools=True):
            if any(message["role"] == "tool" for message in messages):
                raise RuntimeError("private-test-sentinel")
            return real_complete(client, messages, allow_tools=allow_tools)

        with self.track_fixtures() as roots, patch.object(adapter.TokenProxyClient, "complete", crash_after_feedback):
            case = runner.run_scenario("AE-01")
        self.assertEqual(len(roots), 1)
        self.assertEqual(case["runner_status"], "infrastructure_failure")
        self.assertIn("runner_exception", case["infrastructure_failures"])
        self.assertIsNone(case["actual"])
        self.assertEqual(case["partial_tool_results"][0]["tool_call_id"], "v1")
        self.assertEqual(case["partial_tool_results"][0]["data"]["products"], 27)
        self.assertEqual(case["completion_attempts_observed"], 2)
        self.assertEqual(case["transport_invocations"], 1)
        self.assertEqual(case["fixture"]["integrity"], "passed")
        self.assertNotIn("private-test-sentinel", json.dumps(case))

    def test_fixture_integrity_failure_preserves_returned_results_and_cleans_up(self):
        real_orchestrate = adapter.orchestrate

        def corrupt_temporary_fixture(request, *, client, bindings):
            result = real_orchestrate(request, client=client, bindings=bindings)
            bindings.dataset_path.write_bytes(b"fixture-only corruption")
            return result

        with self.track_fixtures(), patch.object(adapter, "orchestrate", corrupt_temporary_fixture):
            case = runner.run_scenario("AE-01")
        self.assertEqual(case["actual"]["tool_results"][0]["status"], "success")
        self.assertEqual(case["runner_status"], "infrastructure_failure")
        self.assertEqual(case["fixture"]["integrity"], "failed")
        self.assertEqual(case["fixture"]["cleanup"], "passed")
        self.assertIn("fixture_failure", case["infrastructure_failures"])

    def test_malformed_returned_result_is_sanitized_and_retains_observed_feedback(self):
        real_orchestrate = adapter.orchestrate

        def malformed_result(request, *, client, bindings):
            result = real_orchestrate(request, client=client, bindings=bindings)
            del result["api_requests"]
            result["unexpected_private"] = "private-test-sentinel"
            return result

        with patch.object(adapter, "orchestrate", malformed_result):
            case = runner.run_scenario("AE-01")
        self.assertEqual(case["runner_status"], "infrastructure_failure")
        self.assertIn("invalid_orchestration_result", case["infrastructure_failures"])
        self.assertIsNone(case["actual"])
        self.assertEqual(case["partial_tool_results"][0]["tool_call_id"], "v1")
        self.assertNotIn("private-test-sentinel", json.dumps(case))

    def test_repeated_runs_are_deterministic_without_paths_or_timestamps(self):
        self.assertEqual(runner.run_all_scenarios(), runner.run_all_scenarios())

    def test_evidence_excludes_authentication_requests_environment_files_and_hidden_text(self):
        manifest = deepcopy(self.manifest)
        manifest["scenarios"][0]["script"][-1]["text"] = (
            "<thinking>hidden-reasoning-test-sentinel</thinking>Dataset checked."
        )
        real_open = io.open

        def guarded_open(file, *args, **kwargs):
            if isinstance(file, (str, Path)) and Path(file).name.startswith(".env"):
                self.fail("Environment files must not be opened")
            return real_open(file, *args, **kwargs)

        with self.manifest_path(manifest) as path, patch("io.open", side_effect=guarded_open):
            case = runner.run_scenario("AE-01", manifest_path=path)
        self.assertEqual(case["actual"]["assistant_response"], "Dataset checked.")
        serialized = json.dumps(case)
        for forbidden in (runner.OFFLINE_MARKER, "Authorization", "Bearer ", "hidden-reasoning-test-sentinel",
                          str(fixtures.DATASET_SOURCE.parent), "headers", "request_object"):
            self.assertNotIn(forbidden, serialized)
        self.assertEqual(set(case["tool_calls"][0]), {"transport_invocation", "script_step", "id", "name"})

    def test_cli_verifies_contracts_without_task_scoring_or_report_files(self):
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(runner.main(["AE-14"]), 0)
        self.assertIn("failed/http_error_502", output.getvalue())
        self.assertIn("contract=matched", output.getvalue())
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(runner.main(["AE-99"]), 1)
        self.assertIn("unknown_scenario", output.getvalue())


if __name__ == "__main__":
    unittest.main()
