"""Phase 3 provenance, determinism, preservation and credential exclusion."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path, PureWindowsPath
import tempfile
import unittest
from unittest.mock import patch

from tools import build_v21_completion_repair as repair


class CompletionRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.outputs = repair.render_outputs()
        cls.source = json.loads((repair.SOURCE / repair.parent.WORKFLOW).read_text(encoding="utf-8"))
        cls.candidate = json.loads(cls.outputs[repair.WORKFLOW])

    def test_parent_is_exact_reviewed_pr17_workflow(self):
        raw = (repair.SOURCE / repair.parent.WORKFLOW).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), repair.PARENT_WORKFLOW_SHA256)
        self.assertNotEqual(repair.SOURCE, repair.sync.ROOT / repair.OUTPUT_SUBDIR)
        self.assertEqual(repair.parent.check_outputs(repair.parent.render_outputs(), repair.SOURCE), [])

    def test_authorized_native_fields_only_and_all_reference_types_resolve(self):
        a, b = self.source, self.candidate
        self.assertEqual(len(b["nodes"]), 20)
        self.assertEqual(len(b["edges"]), 18)
        self.assertEqual(a["edges"], b["edges"])
        self.assertEqual(a["chatConfig"], b["chatConfig"])
        self.assertEqual(repair.sync.check_workflow_inputs(b), [])
        for old, new in zip(a["nodes"], b["nodes"]):
            restored = deepcopy(new)
            if old["nodeId"] == repair.sync.VALIDATOR_ID:
                self.assertEqual(new["inputs"][-1]["value"], ["zWAw4oYVL1QMe8YX", "quoteQA"])
                self.assertEqual(new["inputs"][-1]["valueType"], "datasetQuote")
                self.assertEqual(new["outputs"][-1]["key"], "completion_status")
                restored["inputs"].pop()
                restored["outputs"].pop()
                for field, previous in zip(restored["inputs"], old["inputs"]):
                    if field["key"] == "code":
                        field["value"] = previous["value"]
            elif old["nodeId"] == "zh9L8VeY9vKm3WnU":
                self.assertEqual(json.loads(new["inputs"][0]["value"]), repair.SAFE)
                restored["inputs"][0]["value"] = old["inputs"][0]["value"]
            self.assertEqual(restored, old)

    def test_protected_baseline_fingerprints_are_unchanged(self):
        evidence = json.loads((repair.sync.ROOT / "tests/fixtures/v21_completion_preservation.json").read_text(encoding="utf-8"))
        for name, expected in evidence["sha256"].items():
            with self.subTest(path=name):
                self.assertEqual(hashlib.sha256((repair.sync.ROOT / name).read_bytes()).hexdigest(), expected)

    def test_identical_master_knowledge_workflow_copies_and_css_cards(self):
        self.assertEqual(self.outputs["local/catalogue.json"], repair.sync.TEST_DATASET.read_bytes())
        self.assertEqual(self.outputs["local/" + repair.sync.KNOWLEDGE], (repair.SOURCE / "local" / repair.sync.KNOWLEDGE).read_bytes())
        self.assertEqual(self.outputs[repair.WORKFLOW], self.outputs["local/" + repair.sync.WORKFLOW])
        import re
        for name in ("local/index.html", "aiep/site/index.html"):
            before = (repair.SOURCE / name).read_text(encoding="utf-8")
            after = self.outputs[name].decode("utf-8")
            for pattern in [r"<style>([\s\S]*?)</style>", r'<script type="application/json" id="mytech-dataset">([\s\S]*?)</script>', r"    function addStructuredResponse\([\s\S]*?(?=\n    function )"]:
                self.assertEqual(re.search(pattern, before)[0], re.search(pattern, after)[0])

    def test_generated_artifacts_and_provenance_are_current(self):
        self.assertEqual(repair.render_outputs(), self.outputs)
        self.assertEqual(repair.parent.check_outputs(self.outputs, repair.sync.ROOT / repair.OUTPUT_SUBDIR), [])
        manifest = json.loads(self.outputs["manifest.json"])
        self.assertFalse(manifest["default_deployment_changed"])
        self.assertEqual(manifest["requests_executed_by_builder"], 0)
        for name, expected in manifest["sources_sha256"].items():
            self.assertNotIn("\\", name)
            self.assertEqual(hashlib.sha256((repair.sync.ROOT / name).read_bytes()).hexdigest(), expected)
        for name, expected in manifest["outputs"].items():
            self.assertEqual(hashlib.sha256(self.outputs[name]).hexdigest(), expected)

    def test_windows_path_formatting_is_portable(self):
        original = Path.relative_to
        def windows_relative(path, *args, **kwargs):
            return PureWindowsPath(original(path, *args, **kwargs).as_posix())
        with patch.object(Path, "relative_to", windows_relative):
            self.assertEqual(repair.render_outputs(), self.outputs)

    def test_repeat_generation_does_not_rewrite_and_check_does_not_repair(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            directory = root / repair.OUTPUT_SUBDIR
            repair.parent.write_outputs(self.outputs, directory)
            before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in directory.rglob("*") if p.is_file()}
            repair.parent.write_outputs(repair.render_outputs(), directory)
            self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before})
            stale = directory / repair.WORKFLOW
            stale.write_bytes(stale.read_bytes() + b"stale")
            expected = stale.read_bytes()
            self.assertEqual(repair.main(["--check", "--output-root", str(root)]), 1)
            self.assertEqual(stale.read_bytes(), expected)

    def test_public_package_has_no_credentials_or_runtime_selections(self):
        for name, raw in self.outputs.items():
            text = raw.decode("utf-8")
            self.assertEqual(repair.aiep.scan_credentials(text), [], name)
            if name.endswith(".json"):
                self.assertEqual(repair.parent.sensitive_paths(json.loads(text)), [], name)
        hosted = self.outputs["aiep/site/index.html"].decode("utf-8")
        for forbidden in ("LOCAL_TEST", "apiKey", "localStorage", "/api/test/", "localhost", "authorization", "Bearer "):
            self.assertNotIn(forbidden, hosted)
        self.assertEqual(next(i["value"] for n in self.candidate["nodes"] if n["nodeId"] == "zWAw4oYVL1QMe8YX" for i in n["inputs"] if i["key"] == "datasets"), [])

    def test_tampered_parent_workflow_is_rejected(self):
        original = Path.read_bytes
        def changed(path):
            raw = original(path)
            return raw + b" " if path == repair.SOURCE / repair.parent.WORKFLOW else raw
        with patch.object(Path, "read_bytes", changed), self.assertRaisesRegex(ValueError, "fingerprint"):
            repair.render_outputs()

    def test_symlink_parent_is_rejected_before_any_source_read(self):
        original = Path.is_symlink
        with patch.object(Path, "is_symlink", lambda path: path == repair.SOURCE or original(path)), \
             patch.object(Path, "read_bytes", side_effect=AssertionError("Source must not be read")), \
             self.assertRaisesRegex(ValueError, "Symlink"):
            repair.render_outputs()


if __name__ == "__main__":
    unittest.main()
