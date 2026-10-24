"""Original-export repair isolation, frozen uploads and deterministic provenance."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path, PureWindowsPath
import tempfile
import unittest
from unittest.mock import patch

from tools import build_aiep_test as aiep
from tools import build_v21_usage_repair as repair
from tools import sync_catalogue as sync
from tools.check_workflow_registry import check_registry, json_differences


class UsageRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.outputs = repair.render_outputs()
        cls.original = sync.load_dataset(sync.FROZEN_USAGE_WORKFLOW)
        cls.candidate = json.loads(cls.outputs[repair.WORKFLOW])

    def test_actual_original_graph_changes_only_the_validator_code(self):
        manifest = json.loads(self.outputs["manifest.json"])
        differences = json_differences(self.original, self.candidate)
        self.assertEqual(differences, manifest["workflow_changed_paths"])
        self.assertEqual(len(differences), 1)
        self.assertTrue(differences[0].endswith("/value"))
        restored = deepcopy(self.candidate)
        sync.validation_code(restored)["value"] = sync.validation_code(self.original)["value"]
        self.assertEqual(restored, self.original)
        self.assertEqual((len(restored["nodes"]), len(restored["edges"])), (20, 18))
        self.assertEqual(sync.check_workflow_inputs(self.candidate), [])
        self.assertTrue(sync.validation_code(self.candidate)["value"].startswith(sync.USAGE_VALIDATOR.read_text(encoding="utf-8")))
        self.assertEqual(self.outputs[repair.WORKFLOW], self.outputs["local/" + sync.WORKFLOW])

    def test_frozen_uploads_and_actual_snapshots_remain_reproducible(self):
        registry, graphs, _ = check_registry()
        dataset = sync.load_dataset(sync.TEST_DATASET)
        self.assertEqual(sync.render_frontend(dataset).encode(), (sync.ROOT / sync.OUTPUT_SUBDIR / "index.html").read_bytes())
        self.assertEqual(aiep.render_aiep_frontend(dataset).encode(), (sync.ROOT / aiep.OUTPUT_SUBDIR / "site/index.html").read_bytes())
        self.assertEqual(graphs["original"], self.original)
        self.assertEqual(registry["default_variant"], "original")
        self.assertFalse(json.loads(self.outputs["manifest.json"])["default_deployment_changed"])

    def test_new_frontends_preserve_css_dataset_and_card_rendering(self):
        import re
        for candidate, baseline in [("local/index.html", sync.OUTPUT_SUBDIR / "index.html"), ("aiep/site/index.html", aiep.OUTPUT_SUBDIR / "site/index.html")]:
            repaired = self.outputs[candidate].decode("utf-8")
            accepted = (sync.ROOT / baseline).read_text(encoding="utf-8")
            for pattern in [r"<style>([\s\S]*?)</style>", r'<script type="application/json" id="mytech-dataset">([\s\S]*?)</script>', r"    function addStructuredResponse\([\s\S]*?(?=\n    function )"]:
                self.assertEqual(re.search(pattern, repaired)[0], re.search(pattern, accepted)[0])
            self.assertIn("function testUsageOwnershipIssue", repaired)

    def test_all_manifest_fingerprints_and_committed_outputs_match(self):
        self.assertEqual(repair.render_outputs(), self.outputs)
        self.assertEqual(repair.check_outputs(self.outputs, sync.ROOT / repair.OUTPUT_SUBDIR), [])
        manifest = json.loads(self.outputs["manifest.json"])
        for name, expected in manifest["outputs"].items():
            self.assertEqual(hashlib.sha256(self.outputs[name]).hexdigest(), expected)
        for name, expected in manifest["sources_sha256"].items():
            self.assertNotIn("\\", name)
            self.assertFalse(Path(name).is_absolute())
            self.assertEqual(hashlib.sha256((sync.ROOT / name).read_bytes()).hexdigest(), expected)

    def test_manifest_paths_are_posix_with_windows_path_formatting(self):
        original = Path.relative_to
        def windows_relative(path, *args, **kwargs):
            return PureWindowsPath(original(path, *args, **kwargs).as_posix())
        with patch.object(Path, "relative_to", windows_relative):
            self.assertEqual(repair.render_outputs(), self.outputs)

    def test_writer_is_deterministic_and_checks_never_repair_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary).resolve() / repair.OUTPUT_SUBDIR
            repair.write_outputs(self.outputs, directory)
            before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in directory.rglob("*") if p.is_file()}
            repair.write_outputs(self.outputs, directory)
            self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before})
            stale = directory / "aiep/site/index.html"
            stale.write_bytes(stale.read_bytes() + b"stale")
            changed = stale.read_bytes()
            self.assertTrue(repair.check_outputs(self.outputs, directory))
            self.assertEqual(stale.read_bytes(), changed)
            (directory / "unexpected.txt").write_text("offline fixture", encoding="utf-8")
            with self.assertRaises(ValueError): repair.write_outputs(self.outputs, directory)

    def test_changed_original_helper_fails_before_generation(self):
        altered = deepcopy(self.original)
        sync.validation_code(altered)["value"] = "changed source\n" + sync.validation_code(altered)["value"]
        with self.assertRaises(ValueError): repair.repair_workflow(altered)

    def test_symlink_candidate_is_rejected_without_overwriting_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary).resolve() / "candidate"
            repair.write_outputs(self.outputs, directory)
            target = Path(temporary).resolve() / "protected.html"
            target.write_bytes(self.outputs["aiep/site/index.html"])
            link = directory / "aiep/site/index.html"
            link.unlink()
            link.symlink_to(target)
            self.assertTrue(repair.check_outputs(self.outputs, directory))
            with self.assertRaises(ValueError): repair.write_outputs(self.outputs, directory)
            self.assertEqual(target.read_bytes(), self.outputs["aiep/site/index.html"])

    def test_live_evidence_does_not_claim_missing_response_or_validator_bytes(self):
        fixtures = sync.load_dataset(sync.ROOT / "tests/fixtures/v21_usage_repair.json")
        self.assertFalse(fixtures["live_evidence"]["exact_final_json_captured"])
        self.assertFalse(fixtures["live_evidence"]["code_run_2_output_captured"])
        self.assertFalse(fixtures["live_evidence"]["aiep_response_identical_to_fastgpt_run_verified"])
        pair = fixtures["paired_live_control"]
        self.assertNotEqual(pair["failed_input"], pair["successful_input"])
        self.assertEqual([c["message"] for c in fixtures["cases"] if c["id"] in ["shared-gaming-1000-paired-failure", "explicit-gaming-1000-paired-success"]], [pair["failed_input"], pair["successful_input"]])


if __name__ == "__main__":
    unittest.main()
