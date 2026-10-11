"""Reporting integration, provenance, projection safety and exclusive output."""

from collections import Counter
from contextlib import ExitStack, redirect_stdout, redirect_stderr
from copy import deepcopy
import importlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from evaluations import fixtures
from evaluations import report_tool3 as reporter
from evaluations import run_tool3 as runner
from evaluations.scenario_contract import load_manifest
from evaluations.score_tool3 import score_scenario


class ReportingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = load_manifest()
        with ExitStack() as stack:
            guards = [stack.enter_context(patch(target, side_effect=AssertionError("Live access forbidden")))
                      for target in ("socket.create_connection", "socket.socket.connect",
                                     "urllib.request.urlopen", "urllib.request.OpenerDirector.open",
                                     "tools.tool3_tokenproxy.http_transport", "tools.tool3_tokenproxy.getpass.getpass")]
            cls.evidence = runner.run_all_scenarios()
            for guard in guards:
                guard.assert_not_called()
        cls.report = reporter.build_report(cls.manifest, cls.evidence,
                                           repository={"revision": "a" * 40, "dirty": True})

    def setUp(self):
        self.dataset = fixtures.DATASET_SOURCE.read_bytes()
        self.knowledge = fixtures.KNOWLEDGE_SOURCE.read_bytes()
        self.guards = []
        for target in ("socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex",
                       "urllib.request.urlopen", "urllib.request.OpenerDirector.open",
                       "tools.tool3_tokenproxy.http_transport", "tools.tool3_tokenproxy.getpass.getpass"):
            block = patch(target, side_effect=AssertionError("Live access forbidden"))
            self.guards.append(block.start())
            self.addCleanup(block.stop)
        real_open = io.open

        def guarded_open(file, *args, **kwargs):
            if isinstance(file, (str, Path)) and Path(file).name.startswith(".env"):
                raise AssertionError("Environment files forbidden")
            return real_open(file, *args, **kwargs)

        block = patch("io.open", side_effect=guarded_open)
        block.start()
        self.addCleanup(block.stop)

    def tearDown(self):
        for guard in self.guards:
            guard.assert_not_called()
        self.assertEqual(fixtures.DATASET_SOURCE.read_bytes(), self.dataset)
        self.assertEqual(fixtures.KNOWLEDGE_SOURCE.read_bytes(), self.knowledge)

    def record(self, number, report=None):
        return (report or self.report)["scenarios"][number - 1]

    def test_full_report_runs_existing_runner_and_scorer_once_per_case(self):
        with patch.object(runner, "run_all_scenarios", wraps=runner.run_all_scenarios) as run, \
             patch.object(reporter, "score_scenario", wraps=score_scenario) as score:
            report = reporter.generate_report()
        run.assert_called_once_with()
        self.assertEqual(score.call_count, 16)
        self.assertEqual(report["scenario_count"], 16)
        self.assertEqual([row["scenario_id"] for row in report["scenarios"]],
                         [scenario["id"] for scenario in self.manifest["scenarios"]])
        self.assertTrue(report["offline_transport_verified"])
        self.assertEqual(report["actual_network_requests"], 0)
        for row in report["scenarios"]:
            self.assertEqual(row["actual_network_requests"], 0)
            self.assertEqual(row["fixture"]["integrity"], "passed")
            self.assertEqual(row["fixture"]["cleanup"], "passed")

    def test_schema_versions_runtime_and_effective_limits(self):
        report = self.report
        self.assertEqual(report["schema_version"], "1.0.0")
        self.assertEqual(report["scoring_rules_version"], "1.0.0")
        self.assertEqual(report["manifest_version"], self.manifest["manifest_version"])
        self.assertEqual(report["report_kind"], "mytech_tool3_evaluation_evidence")
        self.assertEqual(report["evaluation_mode"], "scripted_offline")
        self.assertRegex(report["runtime"]["python_version"], r"^\d+\.\d+\.\d+")
        self.assertEqual(set(report["runtime"]["platform"]), {"system", "release", "machine"})
        self.assertEqual(report["execution_limits"]["completion_attempts"], 3)
        self.assertEqual(report["execution_limits"]["tool_rounds"], 2)
        self.assertEqual(report["execution_limits"]["total_tool_calls"], 8)
        self.assertEqual(report["repository"], {"revision": "a" * 40, "dirty": True})

    def test_json_round_trip_and_markdown_use_identical_assessment_data(self):
        text = reporter.serialize_report(self.report)
        decoded = json.loads(text)
        self.assertEqual(decoded, self.report)
        markdown = reporter.render_markdown(self.report)
        self.assertEqual(reporter.render_markdown(decoded), markdown)
        for row in decoded["scenarios"]:
            line = next(line for line in markdown.splitlines() if line.startswith("| " + row["scenario_id"] + " |"))
            counts = row["completeness"]
            self.assertIn(f"{counts['required_count']} / {counts['met_count']} / {counts['handled_count']}", line)
            self.assertIn(f"{row['completion_attempts']} / {row['transport_invocations']}", line)
            self.assertIn(f"| {row['task_verdict']} | {row['expectation_verdict']} | {row['human_review']} |", line)
        self.assertTrue(text.endswith("\n"))
        self.assertNotIn("\r", text)

    def test_totals_match_independent_scorer_results(self):
        scores = [score_scenario(s, e) for s, e in zip(self.manifest["scenarios"], self.evidence)]
        for field, section in (("task_verdict", "task_verdicts"), ("expectation_verdict", "expectation_verdicts")):
            counts = Counter(score[field] for score in scores)
            self.assertEqual(self.report["totals"][section], {key: counts[key] for key in self.report["totals"][section]})
        self.assertEqual(self.report["totals"]["task_verdicts"], {"pass": 7, "fail": 7, "pending_review": 2, "invalid_run": 0})
        self.assertEqual(self.report["totals"]["expectation_verdicts"], {"pass": 16, "fail": 0, "not_evaluable": 0})
        markdown = reporter.render_markdown(self.report)
        for label, count in (("Task Pass", 7), ("Task Fail", 7), ("Pending Review", 2),
                             ("Invalid Runs", 0), ("Evaluation Expectations Passed", 16),
                             ("Evaluation Expectations Failed", 0), ("Not Evaluable", 0)):
            self.assertIn(f"- {label}: {count}\n", markdown)

    def test_changed_actual_assessment_changes_totals_without_hardcoded_distribution(self):
        evidence = deepcopy(self.evidence)
        evidence[11] = deepcopy(evidence[2])
        evidence[11]["scenario_id"] = "AE-12"
        report = reporter.build_report(self.manifest, evidence)
        self.assertEqual(self.record(12, report)["task_verdict"], "pass")
        self.assertEqual(self.record(12, report)["expectation_verdict"], "fail")
        self.assertEqual(report["totals"]["task_verdicts"]["pass"], 8)
        self.assertEqual(report["totals"]["task_verdicts"]["fail"], 6)
        self.assertEqual(report["totals"]["expectation_verdicts"]["pass"], 15)
        self.assertEqual(report["totals"]["expectation_verdicts"]["fail"], 1)
        self.assertIn("- Task Pass: 8", reporter.render_markdown(report))

    def test_dependency_block_evidence_and_associated_id_are_preserved(self):
        row = self.record(8)
        self.assertEqual(row["completeness"], {"applicable": True, "required_count": 2, "met_count": 1, "handled_count": 2})
        self.assertEqual(row["operations"][1], {"operation": "knowledge_inspection", "state": "blocked_expected", "tool_result_ids": ["k1"]})
        self.assertEqual(row["tool_results"][1], {"tool_call_id": "k1", "name": "check_knowledge", "status": "skipped", "code": "dataset_invalid"})
        self.assertEqual(row["task_verdict"], "pass")
        self.assertIn("blocked_expected", reporter.render_markdown(self.report))

    def test_completed_orchestration_does_not_hide_missing_operation(self):
        row = self.record(12)
        self.assertEqual(row["orchestration"]["status"], "completed")
        self.assertEqual(row["orchestration"]["code"], "ok")
        self.assertEqual(row["completeness"]["met_count"], 1)
        self.assertEqual(row["task_verdict"], "fail")
        self.assertEqual(row["expectation_verdict"], "pass")

    def test_redundant_and_unnecessary_attempts_and_executions_remain_distinct(self):
        plan = self.record(13)["execution_plan"]
        self.assertEqual(plan["redundant_attempt_ids"], ["v2"])
        self.assertEqual(plan["redundant_execution_ids"], ["v2"])
        self.assertEqual(plan["unnecessary_attempt_ids"], ["k1"])
        self.assertEqual(plan["unnecessary_execution_ids"], ["k1"])

    def test_provider_failure_retains_partial_operations_and_result_provenance(self):
        row = self.record(14)
        self.assertEqual(row["orchestration"]["code"], "http_error_502")
        self.assertEqual(row["tool_results"][0]["tool_call_id"], "v1")
        self.assertEqual(row["operations"][0]["state"], "met")
        self.assertEqual(row["completeness"]["met_count"], 1)
        self.assertEqual(row["provenance"]["tool_results"], "orchestration_return")
        self.assertIn("provider_availability", row["failure_categories"])
        self.assertFalse(row["checks"]["final_delivered"])

    def test_pending_reviews_remain_pending_and_notice_explains_semantic_boundary(self):
        for number in (4, 15):
            row = self.record(number)
            self.assertEqual(row["human_review"], "pending")
            self.assertEqual(row["task_verdict"], "pending_review")
            self.assertEqual(row["deterministic_verdict"], "pass")
        self.assertFalse(self.record(4)["completeness"]["applicable"])
        markdown = reporter.render_markdown(self.report)
        self.assertIn(reporter.NOTICE, markdown)
        self.assertIn("anticipated outcomes are not judgments", markdown)
        self.assertIn("without indicating an evaluation infrastructure failure", markdown)
        self.assertIn("not applicable", markdown)

    def test_report_does_not_accept_untrusted_review_fields_as_annotations(self):
        evidence = deepcopy(self.evidence)
        for number in (4, 15):
            evidence[number - 1]["human_review"] = "pass"
            evidence[number - 1]["task_verdict"] = "pass"
        report = reporter.build_report(self.manifest, evidence)
        for number in (4, 15):
            self.assertEqual(self.record(number, report)["human_review"], "pending")
            self.assertEqual(self.record(number, report)["task_verdict"], "pending_review")

    def test_execution_limit_has_complete_operations_but_missing_delivery(self):
        row = self.record(16)
        self.assertEqual(row["completeness"]["met_count"], 2)
        self.assertEqual(row["execution_plan"]["attempted_count"], 3)
        self.assertEqual(row["execution_plan"]["executed_count"], 2)
        self.assertEqual(row["execution_plan"]["limit_blocked_batches"], [3])
        self.assertEqual(row["orchestration"]["code"], "execution_limit_reached")
        self.assertFalse(row["checks"]["final_delivered"])
        self.assertEqual(row["task_verdict"], "fail")

    def test_exact_fixture_hashes_and_integrity_statuses_are_preserved(self):
        for record, evidence in zip(self.report["scenarios"], self.evidence):
            self.assertEqual(record["fixture"], evidence["fixture"])
        self.assertNotEqual(self.record(6)["fixture"]["dataset_sha256"], self.record(6)["fixture"]["source_dataset_sha256"])
        self.assertNotEqual(self.record(7)["fixture"]["knowledge_sha256"], self.record(7)["fixture"]["source_knowledge_sha256"])

    def test_attempted_names_arguments_authorization_and_rejected_batches_are_preserved(self):
        nine, ten = self.record(9), self.record(10)
        self.assertFalse(nine["attempted_tool_calls"][1]["authorized_tool_name"])
        self.assertTrue(ten["attempted_tool_calls"][1]["authorized_tool_name"])
        self.assertFalse(ten["attempted_tool_calls"][1]["authorized_arguments"])
        for row in (nine, ten):
            self.assertEqual(row["tool_results"], [])
            self.assertEqual(row["execution_plan"]["rejected_batches"], [1])
            self.assertEqual(row["completeness"]["met_count"], 0)

    def test_projection_excludes_raw_arguments_headers_explanations_diagnostics_and_extras(self):
        evidence = deepcopy(self.evidence)
        sentinel = "SECRET-SENTINEL /private/path <thinking>hidden</thinking> Bearer token"
        for case in evidence:
            case["raw_request"] = {"Authorization": sentinel}
            case["headers"] = {"Authorization": sentinel}
            if case["actual"] is not None:
                case["actual"]["assistant_response"] = sentinel
                case["actual"]["extra"] = sentinel
                for result in case["actual"]["tool_results"]:
                    result["diagnostics"] = [sentinel]
                    result["data"] = {"secret": sentinel}
            for call in case["tool_calls"]:
                call["arguments"] = {"knowledge": sentinel}
                call["extra"] = sentinel
        report = reporter.build_report(self.manifest, evidence)
        serialized = reporter.serialize_report(report)
        markdown = reporter.render_markdown(report)
        for forbidden in (sentinel, "SECRET-SENTINEL", "Authorization", "<thinking>", "other_knowledge",
                          "offline-evaluation-marker", "raw_request", "diagnostics", "assistant_response"):
            self.assertNotIn(forbidden, serialized + markdown)
        self.assertEqual(set(self.record(1, report)["tool_results"][0]), {"tool_call_id", "name", "status", "code"})

    def test_untrusted_error_details_are_bounded_and_redacted(self):
        evidence = deepcopy(self.evidence)
        evidence[0]["infrastructure_failures"] = ["C:\\private\\SECRET-SENTINEL\nBearer credential", "x" * 1000]
        report = reporter.build_report(self.manifest, evidence)
        self.assertEqual(self.record(1, report)["infrastructure_errors"]["runner"], ["redacted", "redacted"])
        self.assertNotIn("SECRET-SENTINEL", reporter.serialize_report(report))

    def test_repeated_generation_is_deterministic_without_timestamps_or_paths(self):
        with patch.object(reporter, "collect_repository_state", return_value={"revision": "b" * 40, "dirty": True}):
            first, second = reporter.generate_report(), reporter.generate_report()
        self.assertEqual(first, second)
        self.assertEqual(reporter.serialize_report(first), reporter.serialize_report(second))
        self.assertEqual(reporter.render_markdown(first), reporter.render_markdown(second))
        self.assertNotIn("timestamp", first)
        self.assertNotIn(str(fixtures.DATASET_SOURCE.parent), reporter.serialize_report(first))

    def test_manifest_order_is_preserved_even_when_input_evidence_is_reversed(self):
        report = reporter.build_report(self.manifest, list(reversed(self.evidence)))
        self.assertEqual([r["scenario_id"] for r in report["scenarios"]], [s["id"] for s in self.manifest["scenarios"]])

    def test_build_and_render_do_not_execute_or_write(self):
        with patch.object(runner, "run_all_scenarios", side_effect=AssertionError("Pure builder")), \
             patch.object(Path, "open", side_effect=AssertionError("No file access")), \
             patch.object(Path, "mkdir", side_effect=AssertionError("No directory creation")), \
             patch.object(reporter.subprocess, "run", side_effect=AssertionError("No implicit Git access")):
            report = reporter.build_report(self.manifest, self.evidence)
            reporter.serialize_report(report)
            reporter.render_markdown(report)

    def test_import_writes_no_report_files(self):
        with patch.object(Path, "open", side_effect=AssertionError("No output at import")), \
             patch.object(Path, "mkdir", side_effect=AssertionError("No output at import")):
            importlib.reload(reporter)

    def test_output_directory_is_required_before_cli_execution(self):
        with patch.object(reporter, "generate_report") as generate, redirect_stderr(io.StringIO()), \
             self.assertRaises(SystemExit) as error:
            reporter.main([])
        self.assertEqual(error.exception.code, 2)
        generate.assert_not_called()
        for directory in (None, "", "   "):
            with self.assertRaisesRegex(reporter.ReportError, "explicit_output_directory_required"):
                reporter.write_report(self.report, output_dir=directory)

    def test_writes_exactly_two_consistent_files_only_in_explicit_directory(self):
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "selected" / "reports"
            paths = reporter.write_report(self.report, output_dir=output)
            self.assertEqual(
                {p.resolve() for p in output.iterdir()},
                {p.resolve() for p in paths},
            )
            self.assertEqual(paths[0].name, reporter.JSON_FILENAME)
            self.assertEqual(paths[1].name, reporter.MARKDOWN_FILENAME)
            decoded = json.loads(paths[0].read_text(encoding="utf-8"))
            self.assertEqual(decoded, self.report)
            self.assertEqual(paths[1].read_text(encoding="utf-8"), reporter.render_markdown(decoded))
            self.assertNotIn(b"\r", paths[0].read_bytes() + paths[1].read_bytes())

    def test_existing_json_is_preserved_without_creating_markdown(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / reporter.JSON_FILENAME
            path.write_bytes(b"existing-json")
            with self.assertRaisesRegex(reporter.ReportError, "report_exists"):
                reporter.write_report(self.report, output_dir=root)
            self.assertEqual(path.read_bytes(), b"existing-json")
            self.assertEqual(list(Path(root).iterdir()), [path])

    def test_existing_markdown_is_preserved_and_new_json_is_rolled_back(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / reporter.MARKDOWN_FILENAME
            path.write_bytes(b"existing-markdown")
            with self.assertRaisesRegex(reporter.ReportError, "report_exists"):
                reporter.write_report(self.report, output_dir=root)
            self.assertEqual(path.read_bytes(), b"existing-markdown")
            self.assertEqual(list(Path(root).iterdir()), [path])

    def test_directory_creation_failure_is_sanitized(self):
        with patch.object(Path, "mkdir", side_effect=OSError("SECRET-SENTINEL private path")), \
             self.assertRaisesRegex(reporter.ReportError, "^report_write_failed$"):
            reporter.write_report(self.report, output_dir="unused-explicit-output")

    def test_partial_write_failure_removes_both_owned_outputs(self):
        real_open = Path.open

        class FailingStream:
            def __init__(self, stream):
                self.stream = stream

            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.stream.close()

            def write(self, payload):
                self.stream.write(payload[:10])
                raise OSError("SECRET-SENTINEL private path")

        def fault(path, *args, **kwargs):
            stream = real_open(path, *args, **kwargs)
            return FailingStream(stream) if path.name == reporter.MARKDOWN_FILENAME else stream

        with tempfile.TemporaryDirectory() as root, patch.object(Path, "open", fault):
            with self.assertRaisesRegex(reporter.ReportError, "^report_write_failed$"):
                reporter.write_report(self.report, output_dir=root)
            self.assertEqual(list(Path(root).iterdir()), [])

    def test_short_write_is_detected_and_both_owned_files_are_removed(self):
        real_open = Path.open

        class ShortStream:
            def __init__(self, stream):
                self.stream = stream

            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.stream.close()

            def write(self, payload):
                return self.stream.write(payload[:10])

        def fault(path, *args, **kwargs):
            stream = real_open(path, *args, **kwargs)
            return ShortStream(stream) if path.name == reporter.MARKDOWN_FILENAME else stream

        with tempfile.TemporaryDirectory() as root, patch.object(Path, "open", fault):
            with self.assertRaisesRegex(reporter.ReportError, "^report_write_failed$"):
                reporter.write_report(self.report, output_dir=root)
            self.assertEqual(list(Path(root).iterdir()), [])

    def test_serialization_failure_creates_no_output(self):
        report = deepcopy(self.report)
        report["bad"] = float("nan")
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "uncreated"
            with self.assertRaisesRegex(reporter.ReportError, "report_serialization_failed"):
                reporter.write_report(report, output_dir=output)
            self.assertFalse(output.exists())

    def test_infrastructure_failure_is_distinct_and_preserves_feedback_provenance(self):
        evidence = deepcopy(self.evidence)
        case = evidence[13]
        case["partial_tool_results"] = case["actual"]["tool_results"]
        case.update(actual=None, runner_status="infrastructure_failure", infrastructure_failures=["runner_exception"])
        report = reporter.build_report(self.manifest, evidence)
        row = self.record(14, report)
        self.assertEqual(row["task_verdict"], "invalid_run")
        self.assertEqual(row["expectation_verdict"], "not_evaluable")
        self.assertEqual(row["completeness"]["met_count"], 1)
        self.assertEqual(row["provenance"]["tool_results"], "observed_tool_feedback")
        self.assertEqual(row["orchestration"]["status"], None)
        self.assertEqual(row["completion_attempts"], 2)
        self.assertEqual(report["totals"]["task_verdicts"]["invalid_run"], 1)
        self.assertEqual(report["totals"]["task_verdicts"]["fail"], 6)
        self.assertEqual(report["totals"]["expectation_verdicts"]["not_evaluable"], 1)

    def test_zero_network_requires_verified_observed_transport_not_mode_label(self):
        self.assertFalse(self.report["offline_transport_verified"])
        self.assertIsNone(self.report["actual_network_requests"])
        self.assertTrue(all(row["actual_network_requests"] is None for row in self.report["scenarios"]))
        with patch.object(runner, "run_all_scenarios", return_value=deepcopy(self.evidence)):
            unverified = reporter.generate_report()
        self.assertFalse(unverified["offline_transport_verified"])
        self.assertIsNone(unverified["actual_network_requests"])

    def test_network_and_credential_attempts_are_blocked_and_never_claim_verified_zero(self):
        import getpass
        import urllib.request

        def network_attempt(*args, **kwargs):
            return urllib.request.urlopen("https://example.invalid/forbidden")

        def credential_attempt(*args, **kwargs):
            return getpass.getpass("Forbidden credential entry")

        for attempt in (network_attempt, credential_attempt):
            with patch.object(reporter.adapter.TokenProxyClient, "complete", attempt):
                report = reporter.generate_report()
            self.assertFalse(report["offline_transport_verified"])
            self.assertIsNone(report["actual_network_requests"])
            self.assertEqual(report["totals"]["task_verdicts"]["invalid_run"], 16)
            self.assertEqual(report["totals"]["expectation_verdicts"]["not_evaluable"], 16)

    def test_unavailable_git_metadata_remains_null(self):
        with patch.object(reporter.subprocess, "run", side_effect=FileNotFoundError("SECRET-SENTINEL")):
            self.assertEqual(reporter.collect_repository_state(), {"revision": None, "dirty": None})
        with patch.object(reporter.subprocess, "run", side_effect=subprocess.TimeoutExpired("git", 5)):
            self.assertEqual(reporter.collect_repository_state(), {"revision": None, "dirty": None})

    def test_git_metadata_uses_fixed_read_only_commands_and_discards_paths(self):
        outputs = [subprocess.CompletedProcess([], 0, "c" * 40 + "\n", ""),
                   subprocess.CompletedProcess([], 0, "?? SECRET-SENTINEL/path\n", "")]
        with patch.object(reporter.subprocess, "run", side_effect=outputs) as run:
            state = reporter.collect_repository_state()
        self.assertEqual(state, {"revision": "c" * 40, "dirty": True})
        self.assertEqual(run.call_args_list[0].args[0], ["git", "rev-parse", "--verify", "HEAD"])
        self.assertEqual(run.call_args_list[1].args[0], ["git", "status", "--porcelain=v1", "--untracked-files=normal"])
        self.assertNotIn("SECRET-SENTINEL", json.dumps(state))

    def test_invalid_or_missing_evidence_fails_before_output(self):
        for evidence in (self.evidence[:-1], self.evidence + self.evidence[:1]):
            with self.assertRaisesRegex(reporter.ReportError, "invalid_report_evidence"):
                reporter.build_report(self.manifest, evidence)
        with patch.object(runner, "run_all_scenarios", side_effect=RuntimeError("SECRET-SENTINEL")), \
             self.assertRaisesRegex(reporter.ReportError, "^report_generation_failed$"):
            reporter.generate_report()

    def test_cli_generates_full_report_in_temporary_directory(self):
        with tempfile.TemporaryDirectory() as root, redirect_stdout(io.StringIO()) as output:
            self.assertEqual(reporter.main(["--output-dir", root]), 0)
            report = json.loads((Path(root) / reporter.JSON_FILENAME).read_text(encoding="utf-8"))
            markdown = (Path(root) / reporter.MARKDOWN_FILENAME).read_text(encoding="utf-8")
        self.assertEqual(report["scenario_count"], 16)
        self.assertTrue(report["offline_transport_verified"])
        self.assertEqual(markdown, reporter.render_markdown(report))
        self.assertIn(reporter.NOTICE, output.getvalue())

    def test_cli_preserves_existing_files_and_reports_sanitized_error(self):
        with tempfile.TemporaryDirectory() as root, redirect_stdout(io.StringIO()) as output:
            existing = Path(root) / reporter.JSON_FILENAME
            existing.write_bytes(b"preserve")
            self.assertEqual(reporter.main(["--output-dir", root]), 1)
            self.assertEqual(existing.read_bytes(), b"preserve")
        self.assertIn("report_exists", output.getvalue())

    def test_cli_returns_failure_for_unexpected_assessment_but_writes_useful_evidence(self):
        evidence = deepcopy(self.evidence)
        evidence[11] = deepcopy(evidence[2])
        evidence[11]["scenario_id"] = "AE-12"
        report = reporter.build_report(self.manifest, evidence)
        with tempfile.TemporaryDirectory() as root, redirect_stdout(io.StringIO()), \
             patch.object(reporter, "generate_report", return_value=report):
            self.assertEqual(reporter.main(["--output-dir", root]), 1)
            saved = json.loads((Path(root) / reporter.JSON_FILENAME).read_text(encoding="utf-8"))
            self.assertEqual(saved["scenarios"][11]["expectation_verdict"], "fail")
            self.assertEqual(saved["scenarios"][11]["task_verdict"], "pass")

    def test_cli_failure_does_not_write_report_and_hides_exception_details(self):
        with tempfile.TemporaryDirectory() as root, redirect_stdout(io.StringIO()) as output, \
             patch.object(runner, "run_all_scenarios", side_effect=RuntimeError("SECRET-SENTINEL")):
            self.assertEqual(reporter.main(["--output-dir", root]), 1)
            self.assertEqual(list(Path(root).iterdir()), [])
        self.assertNotIn("SECRET-SENTINEL", output.getvalue())
        self.assertIn("report_generation_failed", output.getvalue())


if __name__ == "__main__":
    unittest.main()
