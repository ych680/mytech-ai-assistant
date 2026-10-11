"""Real offline calibration once, then pure scoring of crafted observations."""

from contextlib import ExitStack
from copy import deepcopy
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from evaluations import fixtures
from evaluations.run_tool3 import run_all_scenarios
from evaluations.scenario_contract import load_manifest
from evaluations.score_tool3 import assess_observation, score_scenario


V = "validate_products"
K = "check_knowledge"


class ScoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dataset = fixtures.DATASET_SOURCE.read_bytes()
        knowledge = fixtures.KNOWLEDGE_SOURCE.read_bytes()
        cls.scenarios = load_manifest()["scenarios"]
        with ExitStack() as stack:
            guards = [stack.enter_context(patch(target, side_effect=AssertionError("Offline only")))
                      for target in ("socket.create_connection", "socket.socket.connect",
                                     "urllib.request.urlopen", "urllib.request.OpenerDirector.open",
                                     "tools.tool3_tokenproxy.http_transport",
                                     "tools.tool3_tokenproxy.getpass.getpass")]
            real_open = io.open

            def guarded_open(file, *args, **kwargs):
                if isinstance(file, (str, Path)) and Path(file).name.startswith(".env"):
                    raise AssertionError("Environment files forbidden")
                return real_open(file, *args, **kwargs)

            stack.enter_context(patch("io.open", side_effect=guarded_open))
            cls.cases = run_all_scenarios()
            for guard in guards:
                guard.assert_not_called()
        if dataset != fixtures.DATASET_SOURCE.read_bytes() or knowledge != fixtures.KNOWLEDGE_SOURCE.read_bytes():
            raise AssertionError("Production resources changed")
        for case in cls.cases:
            if case["fixture"]["integrity"] != "passed" or case["fixture"]["cleanup"] != "passed":
                raise AssertionError("Fixture integrity or cleanup failed")

    def pair(self, number):
        return deepcopy(self.scenarios[number - 1]), deepcopy(self.cases[number - 1])

    def score(self, number):
        return score_scenario(*self.pair(number))

    def crafted_plan(self, rounds, number=3):
        scenario, evidence = self.pair(number)
        templates = {row["name"]: row for row in self.cases[2]["actual"]["tool_results"]}
        calls, rows = [], []
        for invocation, names in enumerate(rounds, 1):
            for offset, name in enumerate(names):
                identifier = f"call_{invocation}_{offset}"
                calls.append({"id": identifier, "name": name, "transport_invocation": invocation,
                              "script_step": invocation, "authorized_tool_name": True,
                              "authorized_arguments": True})
                row = deepcopy(templates[name])
                row["tool_call_id"] = identifier
                rows.append(row)
        evidence["tool_calls"] = calls
        actual = evidence["actual"]
        actual.update(status="completed", code="ok" if rows else "no_tools_executed",
                      execution_status="success" if rows else "not_run", tool_results=rows,
                      api_requests=len(rounds) + 1, tool_rounds=len(rounds), assistant_response="Checks complete.")
        evidence["completion_attempts_observed"] = evidence["transport_invocations"] = actual["api_requests"]
        return scenario, evidence

    def test_all_sixteen_actual_outcomes_and_counts(self):
        expected = [
            (1, 1, 1, "pass"), (1, 1, 1, "pass"), (2, 2, 2, "pass"),
            (0, 0, 0, "pending_review"), (1, 0, 0, "fail"), (1, 1, 1, "pass"),
            (1, 1, 1, "pass"), (2, 1, 2, "pass"), (2, 0, 0, "fail"),
            (2, 0, 0, "fail"), (2, 2, 2, "pass"), (2, 1, 1, "fail"),
            (1, 1, 1, "fail"), (2, 1, 1, "fail"), (1, 1, 1, "pending_review"), (2, 2, 2, "fail"),
        ]
        for number, (required, met, handled, task) in enumerate(expected, 1):
            with self.subTest(scenario=number):
                score = self.score(number)
                self.assertEqual(score["completeness"], {
                    "applicable": required > 0, "required_count": required,
                    "met_count": met, "handled_count": handled})
                self.assertEqual(score["task_verdict"], task)
                self.assertEqual(score["expectation_verdict"], "pass")
                self.assertEqual(score["infrastructure_errors"], [])

    def test_tool_required_bypass_is_task_failure_with_passing_expectation(self):
        score = self.score(5)
        self.assertTrue(score["checks"]["final_delivered"])
        self.assertEqual(score["operations"][0], {
            "operation": "dataset_validation", "state": "missing", "tool_result_ids": []})
        self.assertFalse(score["checks"]["required_operations_handled"])
        self.assertEqual((score["task_verdict"], score["expectation_verdict"]), ("fail", "pass"))

    def test_expected_negative_dataset_finding_meets_requested_validation(self):
        score = self.score(6)
        self.assertEqual(score["operations"][0]["state"], "met")
        self.assertEqual(score["operations"][0]["tool_result_ids"], ["v1"])
        self.assertEqual(score["failure_categories"], ["expected_domain"])
        self.assertEqual(score["task_verdict"], "pass")

    def test_expected_knowledge_inconsistency_meets_requested_inspection(self):
        score = self.score(7)
        self.assertEqual(score["operations"][0]["state"], "met")
        self.assertEqual(score["operations"][0]["tool_result_ids"], ["k1"])
        self.assertIn("expected_domain", score["failure_categories"])

    def test_dependency_block_is_handled_without_completed_inspection_credit(self):
        score = self.score(8)
        self.assertEqual([item["state"] for item in score["operations"]], ["met", "blocked_expected"])
        self.assertEqual(score["operations"][1]["tool_result_ids"], ["k1"])
        self.assertEqual(score["completeness"]["met_count"], 1)
        self.assertEqual(score["completeness"]["handled_count"], 2)
        self.assertEqual(score["tool_plan"]["executed_count"], 2)
        self.assertEqual(score["tool_plan"]["skipped_count"], 1)
        self.assertEqual(score["task_verdict"], "pass")

    def test_unpermitted_dependency_block_is_unexpected_failure(self):
        scenario, evidence = self.pair(8)
        scenario["required_operations"][1]["acceptable_blocks"] = []
        score = assess_observation(scenario, evidence)
        self.assertEqual(score["operations"][1]["state"], "failed_unexpected")
        self.assertEqual(score["completeness"]["handled_count"], 1)
        self.assertEqual(score["task_verdict"], "fail")

    def test_unauthorized_name_rejects_whole_batch_without_execution_credit(self):
        plan = self.score(9)["tool_plan"]
        self.assertEqual(plan["authorized_attempt_ids"], ["v1"])
        self.assertEqual(plan["unauthorized_name_ids"], ["g1"])
        self.assertEqual(plan["unauthorized_argument_ids"], [])
        self.assertEqual((plan["attempted_count"], plan["executed_count"]), (2, 0))
        self.assertEqual(plan["rejected_batches"], [1])
        self.assertEqual(self.score(9)["completeness"]["met_count"], 0)

    def test_unauthorized_arguments_are_distinct_from_name_rejection(self):
        plan = self.score(10)["tool_plan"]
        self.assertEqual(plan["unauthorized_name_ids"], [])
        self.assertEqual(plan["unauthorized_argument_ids"], ["kbad"])
        self.assertEqual(plan["authorized_attempt_ids"], ["v1"])
        self.assertEqual(plan["rejected_batches"], [1])
        self.assertEqual(plan["executed_count"], 0)

    def test_ordered_request_requires_actual_sequential_rounds(self):
        self.assertEqual(self.score(11)["task_verdict"], "pass")
        for rounds in ([[K], [V]], [[V, K]]):
            with self.subTest(rounds=rounds):
                score = assess_observation(*self.crafted_plan(rounds, 11))
                self.assertEqual(score["completeness"]["met_count"], 2)
                self.assertFalse(score["checks"]["attempt_plan_allowed"])
                self.assertEqual(score["task_verdict"], "fail")

    def test_successful_orchestration_with_missing_knowledge_fails_task(self):
        score = self.score(12)
        self.assertEqual(self.cases[11]["actual"]["status"], "completed")
        self.assertEqual(score["operations"][0]["tool_result_ids"], ["v1"])
        self.assertEqual(score["operations"][1]["state"], "missing")
        self.assertEqual(score["task_verdict"], "fail")

    def test_redundant_and_forbidden_executions_are_separate(self):
        score = self.score(13)
        plan = score["tool_plan"]
        self.assertEqual(plan["redundant_attempt_ids"], ["v2"])
        self.assertEqual(plan["redundant_execution_ids"], ["v2"])
        self.assertEqual(plan["unnecessary_attempt_ids"], ["k1"])
        self.assertEqual(plan["unnecessary_execution_ids"], ["k1"])
        self.assertEqual(plan["executed_count"], 3)
        self.assertEqual(score["completeness"]["met_count"], 1)
        self.assertEqual(score["task_verdict"], "fail")

    def test_provider_failure_preserves_earlier_operation_credit(self):
        score = self.score(14)
        self.assertEqual(score["operations"][0]["state"], "met")
        self.assertEqual(score["operations"][0]["tool_result_ids"], ["v1"])
        self.assertEqual(score["completeness"]["met_count"], 1)
        self.assertIn("provider_availability", score["failure_categories"])
        self.assertFalse(score["checks"]["final_delivered"])
        self.assertEqual(score["expectation_verdict"], "pass")

    def test_contradictory_explanation_stays_pending_without_semantic_grading(self):
        score = self.score(15)
        self.assertEqual(score["deterministic_verdict"], "pass")
        self.assertEqual(score["task_verdict"], "pending_review")
        self.assertEqual(score["human_review"], "pending")
        scenario, evidence = self.pair(15)
        evidence["actual"]["assistant_response"] = "The invalid dataset was detected."
        self.assertEqual(score_scenario(scenario, evidence)["task_verdict"], "pending_review")
        scenario["human_review"]["anticipated_outcome"] = "pass"
        self.assertEqual(score_scenario(scenario, evidence)["human_review"], "pending")

    def test_limit_after_both_operations_records_blocked_redundant_attempt(self):
        score = self.score(16)
        plan = score["tool_plan"]
        self.assertEqual(score["completeness"]["met_count"], 2)
        self.assertEqual((plan["attempted_count"], plan["executed_count"]), (3, 2))
        self.assertEqual(plan["redundant_attempt_ids"], ["v2"])
        self.assertEqual(plan["redundant_execution_ids"], [])
        self.assertEqual(plan["limit_blocked_batches"], [3])
        self.assertEqual(plan["rejected_batches"], [])
        self.assertFalse(score["checks"]["final_delivered"])
        self.assertIn("execution_limit", score["failure_categories"])
        self.assertEqual(score["task_verdict"], "fail")

    def test_no_tool_completeness_is_not_applicable_and_review_stays_pending(self):
        score = self.score(4)
        self.assertFalse(score["completeness"]["applicable"])
        self.assertEqual(score["tool_plan"]["attempted_count"], 0)
        self.assertEqual(score["deterministic_verdict"], "pass")
        self.assertEqual(score["human_review"], "pending")
        self.assertEqual(score["task_verdict"], "pending_review")

    def test_permitted_batch_permutation_and_both_sequential_alternatives(self):
        for rounds in ([[K, V]], [[V], [K]], [[K], [V]]):
            with self.subTest(rounds=rounds):
                score = assess_observation(*self.crafted_plan(rounds))
                self.assertEqual(score["task_verdict"], "pass")
                self.assertTrue(score["checks"]["attempt_plan_allowed"])
                self.assertTrue(score["checks"]["execution_plan_allowed"])

    def test_exact_batch_order_rejects_permutation(self):
        scenario, evidence = self.crafted_plan([[K, V]])
        scenario["acceptable_plans"] = [{"rounds": [[V, K]], "ordering": "exact"}]
        self.assertEqual(assess_observation(scenario, evidence)["task_verdict"], "fail")

    def test_redundancy_is_tracked_across_rounds(self):
        score = assess_observation(*self.crafted_plan([[V], [V]]))
        self.assertEqual(score["tool_plan"]["redundant_attempt_ids"], ["call_2_0"])
        self.assertEqual(score["tool_plan"]["redundant_execution_ids"], ["call_2_0"])
        self.assertEqual(score["task_verdict"], "fail")

    def test_once_only_limits_derive_from_allowed_plan_multiplicity(self):
        scenario, evidence = self.crafted_plan([[V], [V]])
        scenario["required_operations"] = scenario["required_operations"][:1]
        scenario["acceptable_plans"] = [{"rounds": [[V], [V]], "ordering": "exact"}]
        score = assess_observation(scenario, evidence)
        self.assertEqual(score["tool_plan"]["redundant_execution_ids"], [])
        self.assertEqual(score["task_verdict"], "pass")

    def test_knowledge_prerequisite_can_meet_semantic_validation_when_permitted(self):
        scenario, evidence = self.crafted_plan([[K]], 5)
        scenario["acceptable_plans"] = [{"rounds": [[K]], "ordering": "exact"}]
        score = assess_observation(scenario, evidence)
        self.assertEqual(score["operations"][0]["state"], "met")
        self.assertEqual(score["operations"][0]["tool_result_ids"], ["call_1_0"])
        self.assertEqual(score["task_verdict"], "pass")

    def test_knowledge_prerequisite_cannot_replace_explicit_validator(self):
        scenario, evidence = self.crafted_plan([[K]])
        score = assess_observation(scenario, evidence)
        self.assertEqual([item["state"] for item in score["operations"]], ["missing", "met"])
        self.assertEqual(score["task_verdict"], "fail")

    def test_semantic_validation_does_not_use_unpermitted_prerequisite(self):
        scenario, evidence = self.crafted_plan([[K]], 5)
        scenario["required_operations"][0]["acceptable_results"] = [
            {"name": V, "status": "success", "code": "ok"}]
        self.assertEqual(assess_observation(scenario, evidence)["operations"][0]["state"], "missing")

    def test_expected_negative_requires_matching_actual_status_and_code(self):
        scenario, evidence = self.pair(6)
        evidence["actual"]["tool_results"][0].update(status="success", code="ok")
        score = score_scenario(scenario, evidence)
        self.assertEqual(score["operations"][0]["state"], "failed_unexpected")
        self.assertEqual(score["task_verdict"], "fail")
        self.assertEqual(score["expectation_verdict"], "fail")

    def test_resource_error_has_no_inferred_cause_and_is_not_expected_domain(self):
        scenario, evidence = self.pair(7)
        evidence["actual"]["tool_results"][0].update(code="knowledge_read_error")
        score = score_scenario(scenario, evidence)
        self.assertEqual(score["operations"][0]["state"], "failed_unexpected")
        self.assertEqual(score["failure_categories"], ["resource_access"])
        self.assertEqual(score["task_verdict"], "fail")

    def test_failure_categories_are_nonexclusive(self):
        scenario, evidence = self.pair(14)
        evidence["actual"]["tool_results"][0].update(status="failed", code="dataset_read_error")
        score = score_scenario(scenario, evidence)
        self.assertEqual(set(score["failure_categories"]), {
            "provider_availability", "resource_access", "missing_required_operations"})

    def test_expected_verdict_changes_do_not_change_actual_assessment(self):
        scenario, evidence = self.pair(12)
        before = assess_observation(scenario, evidence)
        scenario["expected"]["task_verdict"] = "pass"
        self.assertEqual(assess_observation(scenario, evidence), before)
        score = score_scenario(scenario, evidence)
        self.assertEqual(score["task_verdict"], "fail")
        self.assertEqual(score["expectation_verdict"], "fail")
        self.assertIn("task_verdict", score["expectation_mismatches"])

    def test_assessment_never_reads_script_expected_or_anticipated_review(self):
        scenario, evidence = self.pair(15)
        baseline = assess_observation(scenario, evidence)
        del scenario["script"], scenario["expected"]
        scenario["human_review"] = {"required": True}
        self.assertEqual(assess_observation(scenario, evidence), baseline)

    def test_changed_actual_result_is_valid_but_unexpected_not_infrastructure(self):
        scenario, evidence = self.pair(1)
        evidence["actual"].update(code="tool_execution_failed", execution_status="failed")
        evidence["actual"]["tool_results"][0].update(status="failed", code="dataset_invalid")
        score = score_scenario(scenario, evidence)
        self.assertEqual(score["task_verdict"], "fail")
        self.assertEqual(score["expectation_verdict"], "fail")
        self.assertEqual(score["infrastructure_errors"], [])
        self.assertTrue(any(item.startswith("orchestration.") for item in score["expectation_mismatches"]))

    def test_orchestration_mismatch_cannot_pass_even_when_task_passes(self):
        scenario, evidence = self.pair(1)
        scenario["expected"]["orchestration"]["api_requests"] = 3
        score = score_scenario(scenario, evidence)
        self.assertEqual(score["task_verdict"], "pass")
        self.assertEqual(score["expectation_verdict"], "fail")
        self.assertIn("orchestration.api_requests", score["expectation_mismatches"])
        scenario, evidence = self.pair(1)
        evidence["contract_comparison"]["status"] = "mismatched"
        self.assertEqual(score_scenario(scenario, evidence)["expectation_verdict"], "fail")

    def test_runner_failure_is_invalid_run_with_preserved_partial_counts(self):
        scenario, evidence = self.pair(1)
        evidence.update(runner_status="infrastructure_failure", infrastructure_failures=["script_exhausted"])
        evidence["actual"].update(status="failed", code="transport_error", assistant_response=None)
        score = score_scenario(scenario, evidence)
        self.assertEqual(score["completeness"]["met_count"], 1)
        self.assertEqual(score["task_verdict"], "invalid_run")
        self.assertEqual(score["expectation_verdict"], "not_evaluable")
        self.assertIn("evaluation_infrastructure", score["failure_categories"])
        self.assertIn("provider_availability", score["failure_categories"])

    def test_exception_partial_results_remain_descriptive_on_invalid_run(self):
        scenario, evidence = self.pair(1)
        evidence["partial_tool_results"] = evidence["actual"]["tool_results"]
        evidence.update(actual=None, runner_status="infrastructure_failure", infrastructure_failures=["runner_exception"])
        score = score_scenario(scenario, evidence)
        self.assertEqual(score["completeness"]["met_count"], 1)
        self.assertEqual(score["task_verdict"], "invalid_run")
        self.assertEqual(score["expectation_verdict"], "not_evaluable")

    def test_fixture_failure_is_invalid_run(self):
        for field in ("integrity", "cleanup"):
            scenario, evidence = self.pair(1)
            evidence["fixture"][field] = "failed"
            self.assertEqual(score_scenario(scenario, evidence)["task_verdict"], "invalid_run")

    def test_provider_protocol_is_classified_without_mislabeling_as_selection(self):
        scenario, evidence = self.pair(14)
        evidence["actual"]["code"] = "invalid_response_json"
        score = score_scenario(scenario, evidence)
        self.assertIn("provider_protocol", score["failure_categories"])
        self.assertNotIn("tool_selection", score["failure_categories"])
        self.assertEqual(score["task_verdict"], "fail")
        evidence.update(runner_status="infrastructure_failure", infrastructure_failures=["invalid_script_response"])
        self.assertEqual(score_scenario(scenario, evidence)["task_verdict"], "invalid_run")

    def test_explicit_review_changes_actual_verdict_and_exposes_pending_oracle_mismatch(self):
        for number in (4, 15):
            for annotation in ("pass", "fail"):
                score = score_scenario(*self.pair(number), human_review=annotation)
                self.assertEqual(score["human_review"], annotation)
                self.assertEqual(score["task_verdict"], annotation)
                self.assertEqual(score["expectation_verdict"], "fail")
                self.assertIn("task_verdict", score["expectation_mismatches"])
        with self.assertRaises(ValueError):
            score_scenario(*self.pair(4), human_review="anticipated_outcome")
        with self.assertRaises(ValueError):
            score_scenario(*self.pair(1), human_review="pass")

    def test_pending_or_passed_review_cannot_hide_deterministic_failure(self):
        scenario, evidence = self.pair(15)
        evidence["actual"]["assistant_response"] = None
        for annotation in (None, "pass", "fail"):
            self.assertEqual(score_scenario(scenario, evidence, human_review=annotation)["task_verdict"], "fail")

    def test_unknown_authorization_is_invalid_instead_of_assumed_authorized(self):
        scenario, evidence = self.pair(1)
        del evidence["tool_calls"][0]["authorized_arguments"]
        self.assertEqual(score_scenario(scenario, evidence)["task_verdict"], "invalid_run")

    def test_unattributed_or_partial_execution_evidence_is_invalid(self):
        scenario, evidence = self.pair(3)
        evidence["actual"]["tool_results"][0]["tool_call_id"] = "unobserved"
        self.assertEqual(score_scenario(scenario, evidence)["task_verdict"], "invalid_run")
        scenario, evidence = self.pair(3)
        evidence["actual"]["tool_results"].pop()
        self.assertEqual(score_scenario(scenario, evidence)["task_verdict"], "invalid_run")

    def test_identity_and_counter_corruption_is_invalid(self):
        for mutate in (lambda e: e.update(scenario_id="AE-99"),
                       lambda e: e["actual"].update(api_requests=True),
                       lambda e: e["actual"].update(tool_rounds=0),
                       lambda e: e.update(transport_invocations=9),
                       lambda e: e.update(completion_attempts_observed=True)):
            scenario, evidence = self.pair(1)
            mutate(evidence)
            self.assertEqual(score_scenario(scenario, evidence)["task_verdict"], "invalid_run")

    def test_incomplete_or_malformed_evidence_is_not_evaluable(self):
        scenario, _ = self.pair(4)
        for evidence in (None, {}, {"fixture": None}):
            self.assertEqual(score_scenario(scenario, evidence)["expectation_verdict"], "not_evaluable")
        for field in ("tool_results", "assistant_response", "code"):
            scenario, evidence = self.pair(4)
            del evidence["actual"][field]
            self.assertEqual(score_scenario(scenario, evidence)["task_verdict"], "invalid_run")
        scenario, evidence = self.pair(4)
        evidence["actual"]["assistant_response"] = "\ud800"
        self.assertEqual(score_scenario(scenario, evidence)["expectation_verdict"], "not_evaluable")
        for field in ("status", "execution_status"):
            scenario, evidence = self.pair(4)
            evidence["actual"][field] = []
            self.assertEqual(score_scenario(scenario, evidence)["task_verdict"], "invalid_run")

    def test_execution_budget_violation_fails_even_with_final_delivery(self):
        scenario, evidence = self.pair(1)
        evidence["actual"]["api_requests"] = evidence["completion_attempts_observed"] = 4
        score = score_scenario(scenario, evidence)
        self.assertFalse(score["checks"]["within_execution_bounds"])
        self.assertEqual(score["task_verdict"], "fail")

    def test_repeated_scoring_is_identical_and_never_mutates_inputs(self):
        for number in range(1, 17):
            scenario, evidence = self.pair(number)
            originals = deepcopy((scenario, evidence))
            self.assertEqual(score_scenario(scenario, evidence), score_scenario(scenario, evidence))
            self.assertEqual((scenario, evidence), originals)

    def test_no_percentage_weight_or_hidden_numeric_aggregate(self):
        def keys(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    yield key
                    yield from keys(child)
            elif isinstance(value, list):
                for child in value:
                    yield from keys(child)
        for number in range(1, 17):
            fields = set(keys(self.score(number)))
            self.assertFalse(fields & {"percentage", "percent", "weight", "weights", "accuracy", "overall_score"})

    def test_pure_scoring_performs_no_io_execution_or_credential_access(self):
        scenario, evidence = self.pair(15)
        with ExitStack() as stack:
            guards = [stack.enter_context(patch(target, side_effect=AssertionError("Scorer must be pure")))
                      for target in ("builtins.open", "io.open", "socket.create_connection",
                                     "tools.tool3_tokenproxy.orchestrate", "tools.tool3_executor.execute_tool_calls",
                                     "tools.tool3_tokenproxy.getpass.getpass")]
            score = score_scenario(scenario, evidence)
            for guard in guards:
                guard.assert_not_called()
        serialized = json.dumps(score)
        for forbidden in ("offline-evaluation-marker", "Authorization", "Bearer ", "other_knowledge",
                          str(fixtures.DATASET_SOURCE.parent)):
            self.assertNotIn(forbidden, serialized)
        self.assertEqual(score["task_verdict"], "pending_review")


if __name__ == "__main__":
    unittest.main()
