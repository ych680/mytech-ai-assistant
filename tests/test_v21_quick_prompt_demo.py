"""Offline generation, source mapping, frozen releases and public asset checks."""
import hashlib
import json
from pathlib import Path, PureWindowsPath
import re
import tempfile
import unittest
from unittest.mock import patch

from tools import build_v21_quick_prompt_demo as demo


class QuickPromptDemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.outputs = demo.render_outputs()

    def test_parent_and_candidate_are_reproducible_and_current(self):
        self.assertEqual(demo.completion.render_outputs(), {name: (demo.SOURCE / name).read_bytes()
                         for name in demo.completion.render_outputs()})
        self.assertEqual(demo.render_outputs(), self.outputs)
        self.assertEqual(demo.parent.check_outputs(self.outputs, demo.ROOT / demo.OUTPUT_SUBDIR), [])

    def test_protected_baselines_match_pre_phase4_fingerprints(self):
        frozen = json.loads(demo.PRESERVATION.read_text(encoding="utf-8"))
        self.assertEqual(frozen["base_commit"], "e50dbfe025f102644355ec7d0d1ff38370af19e7")
        self.assertGreaterEqual(len(frozen["sha256"]), 67)
        for name, digest in frozen["sha256"].items():
            self.assertEqual(hashlib.sha256((demo.ROOT / name).read_bytes()).hexdigest(), digest, name)

    def test_workflow_catalogue_and_knowledge_copies_are_exact_pr18_bytes(self):
        for name in (demo.completion.WORKFLOW, "local/" + demo.sync.WORKFLOW,
                     "local/catalogue.json", "local/" + demo.sync.KNOWLEDGE):
            self.assertEqual(self.outputs[name], (demo.SOURCE / name).read_bytes(), name)
        self.assertEqual(self.outputs["local/catalogue.json"], demo.sync.TEST_DATASET.read_bytes())
        self.assertEqual(len(json.loads(self.outputs["local/catalogue.json"])["products"]), 54)
        self.assertTrue(json.loads(self.outputs["local/manifest.json"])["completion_validation"])

    def test_base_styles_cards_validation_transport_and_keyboard_handlers_are_preserved(self):
        functions = ["addStructuredResponse", "callModel", "serializableContext", "updateContextAfterResponse",
                     "validateStructuredOutput", "checkRecommendationCompletion", "checkClientRecommendationCompletion",
                     "safeErrorResponse", "createRecoveryAction"]
        for name in ("local/index.html", "aiep/site/index.html"):
            before = (demo.SOURCE / name).read_text(encoding="utf-8")
            after = self.outputs[name].decode("utf-8")
            self.assertEqual(re.findall(r"<style>([\s\S]*?)</style>", before), re.findall(r"<style>([\s\S]*?)</style>", after))
            for function in functions:
                pattern = r"(?:async )?function " + function + r"\([\s\S]*?(?=\n(?:    )?(?:async )?function |\n    const |\n    let )"
                self.assertEqual(re.search(pattern, before)[0], re.search(pattern, after)[0], (name, function))
            pattern = r'    inputElement.addEventListener\("keydown",[\s\S]*?\n    \}\);'
            self.assertEqual(re.search(pattern, before)[0], re.search(pattern, after)[0])
            for script in ("mytech-dataset", "mytech-reference-prompt"):
                pattern = r'<script type="application/json" id="' + script + r'">([\s\S]*?)</script>'
                self.assertEqual(re.search(pattern, before)[0], re.search(pattern, after)[0])

    def test_sources_and_generated_hashes_have_portable_complete_provenance(self):
        manifest = json.loads(self.outputs["manifest.json"])
        self.assertTrue(manifest["frontend_only"])
        self.assertFalse(manifest["default_deployment_changed"])
        self.assertEqual(manifest["requests_executed_by_builder"], 0)
        for name, digest in manifest["sources_sha256"].items():
            self.assertNotIn("\\", name)
            self.assertEqual(hashlib.sha256((demo.ROOT / name).read_bytes()).hexdigest(), digest)
        self.assertEqual(set(manifest["outputs"]), set(self.outputs) - {"manifest.json"})
        for name, digest in manifest["outputs"].items():
            self.assertEqual(hashlib.sha256(self.outputs[name]).hexdigest(), digest)
        local = json.loads(self.outputs["local/manifest.json"])
        for name, digest in local["outputs"].items():
            self.assertEqual(hashlib.sha256(self.outputs["local/" + name]).hexdigest(), digest)

    def test_public_assets_exclude_credentials_and_aiep_has_no_local_runtime(self):
        for name, raw in self.outputs.items():
            text = raw.decode("utf-8")
            self.assertEqual(demo.aiep.scan_credentials(text), [], name)
            if name.endswith(".json"):
                self.assertEqual(demo.parent.sensitive_paths(json.loads(text)), [], name)
        hosted = self.outputs["aiep/site/index.html"].decode("utf-8")
        for forbidden in ("LOCAL_TEST", "localStorage", "apiKey", "authorization", "Bearer ", "/api/test/", "localhost"):
            self.assertNotIn(forbidden, hosted)

    def test_exact_primary_count_and_native_accessible_additions(self):
        for name in ("local/index.html", "aiep/site/index.html"):
            html = self.outputs[name].decode("utf-8")
            self.assertEqual(len(re.findall('class="prompt-button"', html)), 4)
            self.assertIn("Gaming Setup ×2", html)
            self.assertIn('document.createElement("details")', html)
            self.assertIn('document.createElement("summary")', html)
            self.assertIn('select.value = ""', html)
            self.assertIn('button.type = "button"', html)
            self.assertIn('"aria-label", "Category to compare"', html)
            self.assertIn('"aria-live", "polite"', html)

    def test_additions_wrap_and_do_not_change_fixed_composer_geometry(self):
        css = demo.STYLE.read_text(encoding="utf-8")
        self.assertNotIn("--composer-height:", css)
        self.assertNotIn("position: fixed", css)
        self.assertIn("flex-wrap: wrap", css)
        self.assertIn("overflow-wrap: anywhere", css)
        self.assertIn("max-width: 100%", css)
        self.assertIn(":focus-visible", css)
        self.assertNotIn("animation:", css)

    def test_windows_provenance_matches_posix_outputs(self):
        original = Path.relative_to
        with patch.object(Path, "relative_to", lambda path, *args, **kwargs: PureWindowsPath(original(path, *args, **kwargs).as_posix())):
            self.assertEqual(demo.render_outputs(), self.outputs)

    def test_generation_is_idempotent_and_check_cannot_repair(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            directory = root / demo.OUTPUT_SUBDIR
            self.assertEqual(demo.main(["--output-root", str(root)]), 0)
            before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in directory.rglob("*") if p.is_file()}
            self.assertEqual(demo.main(["--output-root", str(root)]), 0)
            self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before})
            stale = directory / "local/index.html"
            stale.write_bytes(stale.read_bytes() + b"stale")
            expected = stale.read_bytes()
            self.assertEqual(demo.main(["--check", "--output-root", str(root)]), 1)
            self.assertEqual(stale.read_bytes(), expected)

    def test_modified_parent_is_rejected_before_rendering(self):
        original = Path.read_bytes
        with patch.object(Path, "read_bytes", lambda path: original(path) + (b"changed" if path == demo.SOURCE / "local/index.html" else b"")):
            with self.assertRaisesRegex(ValueError, "Protected baseline differs"):
                demo.render_outputs()

    def test_symlink_parent_is_rejected_before_reading_it(self):
        original = Path.is_symlink
        with patch.object(Path, "is_symlink", lambda path: path == demo.SOURCE or original(path)):
            with self.assertRaisesRegex(ValueError, "Symlink"):
                demo.render_outputs()


if __name__ == "__main__":
    unittest.main()
