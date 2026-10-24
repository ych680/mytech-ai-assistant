"""Offline A/B artifact isolation, provenance and whole-graph equality regressions."""

from copy import deepcopy
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest

from tools import build_prompt_ab_test as ab
from tools import sync_catalogue as sync


class PromptAbPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.outputs = ab.render_outputs()
        cls.control = json.loads(cls.outputs[ab.CONTROL])
        cls.candidate = json.loads(cls.outputs[ab.CANDIDATE])

    def test_prepared_artifacts_are_exact_and_only_two_fields_differ(self):
        self.assertEqual(ab.check_outputs(self.outputs, sync.ROOT / ab.OUTPUT_SUBDIR), [])
        changes = ab.assert_prompt_pair(self.control, self.candidate)
        self.assertEqual([(item["node_id"], item["input_key"]) for item in changes],
                         [(sync.EXTRACTOR_ID, "description"), (sync.RECOMMENDATION_ID, "systemPrompt")])
        self.assertEqual([item["A_characters"] for item in changes], [11634, 11087])
        self.assertEqual([item["B_characters"] for item in changes], [5615, 5164])
        restored = deepcopy(self.candidate)
        for _, node_id, key in ab.PROMPTS:
            sync.node_input(restored, node_id, key)["value"] = sync.node_input(self.control, node_id, key)["value"]
        self.assertEqual(restored, self.control)
        promoted = deepcopy(self.control)
        sync.apply_prompt_optimization(promoted)
        self.assertEqual(promoted, self.candidate)

    def test_candidate_is_byte_exact_copy_of_existing_generated_workflow(self):
        self.assertEqual(self.outputs[ab.CANDIDATE], (sync.ROOT / sync.OUTPUT_SUBDIR / sync.WORKFLOW).read_bytes())
        sync.assert_workflow_contract(sync.load_dataset(sync.WORKFLOW_TEMPLATE), self.candidate)

    def test_structure_bindings_models_histories_rag_globals_and_code_are_identical(self):
        for graph in (self.control, self.candidate):
            self.assertEqual((len(graph["nodes"]), len(graph["edges"])), (20, 18))
            self.assertEqual(len(graph["chatConfig"]["variables"]), 5)
            sync.assert_portable(graph)
            self.assertEqual(sync.check_workflow_inputs(graph), [])
        for node_a, node_b in zip(self.control["nodes"], self.candidate["nodes"]):
            self.assertEqual(node_a["nodeId"], node_b["nodeId"])
            self.assertEqual(node_a["outputs"], node_b["outputs"])
            for field_a, field_b in zip(node_a["inputs"], node_b["inputs"]):
                if (node_a["nodeId"], field_a["key"]) not in [(n, k) for _, n, k in ab.PROMPTS]:
                    self.assertEqual(field_a, field_b)
        self.assertEqual(self.control["edges"], self.candidate["edges"])
        self.assertEqual(self.control["chatConfig"], self.candidate["chatConfig"])

    def test_configuration_or_deterministic_code_drift_is_rejected(self):
        for node_id, key, value in [(sync.RETRIEVAL_ID, "similarity", 0.4),
                                    (sync.EXTRACTOR_ID, "history", 3),
                                    (sync.RECOMMENDATION_ID, "maxToken", 800),
                                    (sync.VALIDATOR_ID, "code", "changed"),
                                    (sync.GUARD_ID, "code", "changed")]:
            altered = deepcopy(self.candidate)
            sync.node_input(altered, node_id, key)["value"] = value
            with self.assertRaises(ValueError): ab.assert_prompt_pair(self.control, altered)
        altered = deepcopy(self.candidate)
        altered["edges"].reverse()
        with self.assertRaises(ValueError): ab.assert_prompt_pair(self.control, altered)

    def test_reference_drift_or_identical_prompts_are_rejected(self):
        for value in ("", "changed {{$unknown.output$}}", sync.node_input(self.control, sync.RECOMMENDATION_ID, "systemPrompt")["value"]):
            altered = deepcopy(self.candidate)
            sync.node_input(altered, sync.RECOMMENDATION_ID, "systemPrompt")["value"] = value
            with self.assertRaises(ValueError): ab.assert_prompt_pair(self.control, altered)

    def test_bound_portable_exports_are_rejected(self):
        for node_id, key, value in [(sync.EXTRACTOR_ID, "model", "private-model-binding"),
                                    (sync.RETRIEVAL_ID, "datasets", [{"datasetId": "private-kb-binding"}])]:
            altered = deepcopy(self.candidate)
            sync.node_input(altered, node_id, key)["value"] = value
            with self.assertRaises(ValueError): ab.assert_prompt_pair(self.control, altered)

    def test_manifest_does_not_claim_live_verification_or_measurements(self):
        manifest = json.loads(self.outputs["manifest.json"])
        self.assertIn("UNVERIFIED", manifest["live_control_parity"])
        self.assertIn("NOT a fresh live export", manifest["control_provenance"])
        self.assertIn("NONE", manifest["live_measurements"])
        self.assertEqual(manifest["invariants"]["product_count"], 54)
        self.assertEqual(manifest["invariants"]["retrieval_similarity"], 0.35)
        for name, expected in manifest["outputs"].items():
            self.assertEqual(ab.digest(self.outputs[name]), expected)

    def test_plan_is_small_bounded_and_csvs_have_no_fabricated_results(self):
        plan = json.loads(self.outputs["plan.json"])
        self.assertEqual(len(plan["scenarios"]), 9)
        self.assertEqual(sum(len(item["turns"]) for item in plan["scenarios"]), 13)
        self.assertEqual(plan["schedule"]["all_request_ceiling_without_retries"], 80)
        self.assertEqual(plan["schedule"]["smoke_requests_including_warmup"], 28)
        self.assertTrue(plan["no_live_results"])
        self.assertEqual(set(item["group"] for item in plan["scenarios"]),
                         {"currency", "single", "multi", "follow_up", "no_match", "clarification"})
        for name, columns in [("turn-results-template.csv", ab.TURN_COLUMNS), ("node-metrics-template.csv", ab.NODE_COLUMNS)]:
            self.assertEqual(list(csv.reader(io.StringIO(self.outputs[name].decode()))), [columns])

    def test_writer_is_idempotent_stale_checks_are_read_only_and_extra_results_protected(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / ab.OUTPUT_SUBDIR
            ab.write_outputs(self.outputs, directory)
            before = {p.name: p.stat().st_mtime_ns for p in directory.iterdir()}
            ab.write_outputs(self.outputs, directory)
            self.assertEqual(before, {p.name: p.stat().st_mtime_ns for p in directory.iterdir()})
            target = directory / ab.CANDIDATE
            target.write_bytes(target.read_bytes() + b"stale")
            self.assertTrue(ab.check_outputs(self.outputs, directory))
            self.assertTrue(target.read_bytes().endswith(b"stale"))
            (directory / "actual-results.csv").write_text("preserve results")
            with self.assertRaisesRegex(ValueError, "Unexpected A/B artifacts"):
                ab.write_outputs(self.outputs, directory)

    def test_symlink_cannot_overwrite_unrelated_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / ab.OUTPUT_SUBDIR
            directory.mkdir(parents=True)
            protected = Path(temporary) / "original.json"
            protected.write_text("original")
            (directory / ab.CANDIDATE).symlink_to(protected)
            with self.assertRaisesRegex(ValueError, "symlink"):
                ab.write_outputs(self.outputs, directory)
            self.assertEqual(protected.read_text(), "original")


if __name__ == "__main__":
    unittest.main()
