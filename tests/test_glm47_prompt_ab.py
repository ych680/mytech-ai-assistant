"""Actual-export provenance and six-request GLM A/B preparation, entirely offline."""

from copy import deepcopy
import csv
import io
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from tools import build_glm47_prompt_ab as glm
from tools import sync_catalogue as sync


class Glm47PromptAbTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = glm.DEFAULT_BASELINE.read_bytes()
        cls.source, cls.review, cls.sha = json.loads(raw), json.loads(glm.DEFAULT_REVIEW.read_text(encoding="utf-8")), glm.digest(raw)
        cls.outputs = glm.render_outputs(cls.source, cls.review, cls.sha)
        cls.a, cls.b = json.loads(cls.outputs[glm.CONTROL]), json.loads(cls.outputs[glm.CANDIDATE])

    def test_review_loading_preserves_unicode_with_a_cp1252_default(self):
        read_text = Path.read_text

        def cp1252_default(path, *args, **kwargs):
            if path == glm.DEFAULT_REVIEW and not args and kwargs.get("encoding") is None:
                return path.read_bytes().decode("cp1252")
            return read_text(path, *args, **kwargs)

        class LocaleProbe(Glm47PromptAbTests):
            pass

        with patch.object(Path, "read_text", cp1252_default):
            LocaleProbe.setUpClass()
        expected = json.loads(glm.DEFAULT_REVIEW.read_bytes())
        self.assertIn("\u2014", expected["source_filename"])
        self.assertEqual(LocaleProbe.review, expected)
        self.assertEqual(LocaleProbe.outputs, self.outputs)

    def test_generated_package_matches_actual_source_review(self):
        self.assertEqual(glm.check_outputs(self.outputs, sync.ROOT / glm.OUTPUT_SUBDIR), [])
        self.assertEqual(self.sha, self.review["source_sha256"])
        self.assertEqual(self.review["original_download_sha256"], "3e6087b7572ea4c7cfa702c895f5b6a369e6a31c032cfd4264d5d2e72b736f60")
        self.assertNotIn("_id", self.source["chatConfig"])
        self.assertEqual(self.review["comparison_with_reconstructed_A"]["difference_count"], 7)
        self.assertTrue(self.review["comparison_with_reconstructed_A"]["long_prompts_exact_match"])

    def test_source_to_A_changes_only_two_glm_selectors(self):
        restored = deepcopy(self.a)
        for node in (sync.EXTRACTOR_ID, sync.RECOMMENDATION_ID):
            self.assertEqual(sync.node_input(self.source, node, "model")["value"], "deepseek/deepseek-v4.1-flash")
            self.assertEqual(sync.node_input(self.a, node, "model")["value"], "glm-4.7")
            self.assertEqual(sync.node_input(self.b, node, "model")["value"], "glm-4.7")
            sync.node_input(restored, node, "model")["value"] = sync.node_input(self.source, node, "model")["value"]
        self.assertEqual(restored, self.source)
        self.assertEqual(sync.node_input(self.a, "ikIzMK483vihRths", "model"), sync.node_input(self.source, "ikIzMK483vihRths", "model"))

    def test_B_is_derived_from_A_with_only_two_prompt_changes(self):
        restored = deepcopy(self.b)
        for role, node, key in (("state_extraction", sync.EXTRACTOR_ID, "description"),
                                ("recommendation", sync.RECOMMENDATION_ID, "systemPrompt")):
            self.assertEqual(sync.node_input(self.a, node, key), sync.node_input(self.source, node, key))
            self.assertEqual(sync.node_input(self.b, node, key)["value"], sync.optimized_prompt_values()[role])
            sync.node_input(restored, node, key)["value"] = sync.node_input(self.a, node, key)["value"]
        self.assertEqual(restored, self.a)

    def test_zero_context_reports_reconstruct_exact_prompts_and_final_newlines(self):
        from tools import build_prompt_ab_test as deferred

        portable = deferred.render_outputs()
        packages = [(self.outputs, self.a, self.b),
                    (portable, json.loads(portable[deferred.CONTROL]), json.loads(portable[deferred.CANDIDATE]))]
        for outputs, control, candidate in packages:
            report = outputs["prompt-changes.diff"].decode()
            self.assertTrue(all(line == line.rstrip(" \t") for line in report.splitlines()))
            lines = report.splitlines(keepends=True)
            index = 0
            for node, key in ((sync.EXTRACTOR_ID, "description"), (sync.RECOMMENDATION_ID, "systemPrompt")):
                self.assertEqual(lines[index:index + 2], [f"--- A/{node}/{key}\n", f"+++ B/{node}/{key}\n"])
                index += 2
                original = sync.node_input(control, node, key)["value"].splitlines(keepends=True)
                result, consumed, hunks = [], 0, 0
                while index < len(lines) and lines[index].startswith("@@ "):
                    header = re.fullmatch(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@\n", lines[index])
                    self.assertIsNotNone(header)
                    old_start, old_count, new_start, new_count = [int(value) if value is not None else 1 for value in header.groups()]
                    index += 1
                    changes = []
                    while index < len(lines) and not lines[index].startswith(("@@ ", "--- A/")):
                        line = lines[index]
                        if line == "\\ No newline at end of file\n":
                            self.assertTrue(changes and changes[-1][1].endswith("\n"))
                            changes[-1] = (changes[-1][0], changes[-1][1][:-1])
                        else:
                            self.assertIn(line[0], "-+")
                            changes.append((line[0], line[1:]))
                        index += 1
                    removed = [text for prefix, text in changes if prefix == "-"]
                    added = [text for prefix, text in changes if prefix == "+"]
                    self.assertEqual((len(removed), len(added)), (old_count, new_count))
                    position = old_start - 1 if old_count else old_start
                    self.assertGreaterEqual(position, consumed)
                    self.assertEqual(original[position:position + old_count], removed)
                    result.extend(original[consumed:position])
                    self.assertEqual(len(result), new_start - 1 if new_count else new_start)
                    result.extend(added)
                    consumed = position + old_count
                    hunks += 1
                self.assertGreater(hunks, 0)
                result.extend(original[consumed:])
                self.assertEqual("".join(result), sync.node_input(candidate, node, key)["value"])
            self.assertEqual(index, len(lines))

    def test_actual_structure_output_ids_state_code_and_settings_are_preserved(self):
        for graph in (self.source, self.a, self.b):
            self.assertEqual((len(graph["nodes"]), len(graph["edges"])), (20, 18))
            self.assertEqual(sync.check_workflow_inputs(graph), [])
            self.assertEqual(graph["edges"], self.source["edges"])
            self.assertEqual(graph["chatConfig"], self.source["chatConfig"])
            self.assertEqual([n["nodeId"] for n in graph["nodes"]], [n["nodeId"] for n in self.source["nodes"]])
            for node, original in zip(graph["nodes"], self.source["nodes"]):
                self.assertEqual(node["outputs"], original["outputs"])
                self.assertEqual(node.get("position"), original.get("position"))
                for field in original["inputs"]:
                    if field["key"] == "code":
                        self.assertEqual(sync.node_input(graph, node["nodeId"], "code"), field)

    def test_missing_KB_and_publish_revision_are_explicit_not_claimed_verified(self):
        manifest = json.loads(self.outputs["manifest.json"])
        config = json.loads(self.outputs["configuration-checklist.json"])
        self.assertFalse(manifest["full_runtime_parity_confirmed"])
        self.assertIn("PENDING", manifest["status"])
        self.assertIsNone(manifest["published_revision"])
        self.assertIn("UNVERIFIED", manifest["publish_state"])
        self.assertIn("UNVERIFIED", config["parity"]["kb_bindings_and_similarity_035"])
        for graph in (self.a, self.b):
            self.assertEqual(sync.node_input(graph, sync.RETRIEVAL_ID, "datasets")["value"], [])
            self.assertEqual(sync.node_input(graph, sync.RETRIEVAL_ID, "similarity")["value"], 0.35)

    def test_no_source_generates_no_fake_workflows(self):
        outputs = glm.render_outputs()
        self.assertNotIn(glm.CONTROL, outputs)
        self.assertNotIn(glm.CANDIDATE, outputs)
        self.assertEqual(json.loads(outputs["manifest.json"])["status"], "BLOCKED_MISSING_AUTHORITATIVE_EXPORT")

    def test_plan_is_exactly_three_pairs_six_fresh_requests_no_warmup_or_followup(self):
        plan = glm.minimal_plan()
        self.assertEqual(len(plan["scenarios"]), 3)
        self.assertEqual(len(plan["execution_schedule"]), 6)
        self.assertEqual(plan["request_limit"], {"pairs": 3, "requests_total": 6, "requests_per_variant": 3,
                                              "repetitions": 1, "warmups": 0, "retries": 0, "continuation_turns": 0})
        self.assertTrue(plan["no_automatic_execution"])
        self.assertEqual([item["variant"] for item in plan["execution_schedule"]], ["A", "B", "B", "A", "A", "B"])
        self.assertEqual(plan["scenarios"][2]["expected_route"], "clarification")
        self.assertEqual(plan["scenarios"][2]["expected_state"][0]["budget"], None)

    def test_six_result_rows_are_not_run_and_have_no_fabricated_measurements(self):
        rows = list(csv.DictReader(io.StringIO(self.outputs["six-request-results-template.csv"].decode())))
        self.assertEqual(len(rows), 6)
        for row in rows:
            self.assertEqual(row["execution_status"], "NOT_RUN")
            for key in ("state_extraction_ms", "recommendation_ms", "total_workflow_ms", "platform_credits", "json_valid", "turn_pass"):
                self.assertEqual(row[key], "NA")

    def test_unverified_provenance_hash_or_mutated_source_is_rejected(self):
        for key, value in (("provenance", "local_reconstruction"), ("source_sha256", "wrong"), ("credential_free", False)):
            review = deepcopy(self.review); review[key] = value
            with self.assertRaises(ValueError): glm.verified_pair(self.source, review, self.sha)
        mutated = deepcopy(self.source)
        sync.node_input(mutated, sync.RECOMMENDATION_ID, "maxToken")["value"] = 800
        with self.assertRaises(ValueError): glm.verified_pair(mutated, self.review, self.sha)

    def test_glm_selector_must_have_evidence_in_actual_export(self):
        review = deepcopy(self.review)
        review["glm47"]["selector_value"] = "guessed-account-selector"
        with self.assertRaises(ValueError): glm.verified_pair(self.source, review, self.sha)

    def test_native_contract_reference_drift_in_short_prompt_is_rejected(self):
        optimized = sync.optimized_prompt_values()
        optimized["recommendation"] += " {{$missing.node$}}"
        with patch.object(sync, "optimized_prompt_values", return_value=optimized):
            with self.assertRaises(ValueError): glm.verified_pair(self.source, self.review, self.sha)

    def test_environment_path_and_reconstructed_file_are_rejected_without_reading(self):
        with patch.object(Path, "read_bytes", side_effect=AssertionError("source must not be read")):
            self.assertEqual(glm.main(["--baseline", ".env", "--review", str(glm.DEFAULT_REVIEW)]), 1)
            self.assertEqual(glm.main(["--baseline", str(sync.WORKFLOW_TEMPLATE), "--review", str(glm.DEFAULT_REVIEW)]), 1)

    def test_writer_idempotence_read_only_checks_and_extra_result_protection(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / glm.OUTPUT_SUBDIR
            glm.write_outputs(self.outputs, directory)
            before = {p.name: p.stat().st_mtime_ns for p in directory.iterdir()}
            glm.write_outputs(self.outputs, directory)
            self.assertEqual(before, {p.name: p.stat().st_mtime_ns for p in directory.iterdir()})
            path = directory / glm.CANDIDATE
            path.write_bytes(path.read_bytes() + b"stale")
            self.assertTrue(glm.check_outputs(self.outputs, directory))
            self.assertTrue(path.read_bytes().endswith(b"stale"))
            (directory / "actual-results.csv").write_text("keep")
            with self.assertRaises(ValueError): glm.write_outputs(self.outputs, directory)
