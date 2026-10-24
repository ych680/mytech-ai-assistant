"""Offline AIEP generation, upload boundary and accidental credential regression checks."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest

from tools import build_aiep_test as aiep
from tools import sync_catalogue as sync


class AiepBuildTests(unittest.TestCase):
    def setUp(self):
        self.dataset = sync.load_dataset(sync.TEST_DATASET)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / aiep.OUTPUT_SUBDIR

    def test_committed_candidate_matches_master_and_generator(self):
        outputs = aiep.render_outputs(self.dataset)
        self.assertEqual(aiep.check_outputs(outputs, sync.ROOT / aiep.OUTPUT_SUBDIR), [])
        self.assertEqual(set(outputs), {"site/index.html", "manifest.json"})
        manifest = json.loads(outputs["manifest.json"])
        self.assertEqual(manifest["product_count"], 54)
        self.assertIn("UNVERIFIED", manifest["transport"]["binding_status"])
        self.assertEqual(manifest["outputs"]["site/index.html"], hashlib.sha256(outputs["site/index.html"]).hexdigest())

    def test_added_product_changes_embedded_catalogue_contract_and_checksum(self):
        before = aiep.render_outputs(self.dataset)
        product = deepcopy(self.dataset["products"][3])
        product.update(id="LAP-007", product="AIEP expansion laptop", review_status="NEW CANDIDATE — unverified")
        self.dataset["products"].append(product)
        outputs = aiep.render_outputs(self.dataset)
        page = outputs["site/index.html"].decode()
        self.assertEqual(json.loads(re.search(r'id="mytech-dataset">([\s\S]*?)</script>', page)[1]), self.dataset)
        self.assertIn('"count":55', page)
        self.assertEqual(json.loads(outputs["manifest.json"])["product_count"], 55)
        self.assertNotEqual(before["site/index.html"], outputs["site/index.html"])

    def test_script_embedding_cannot_terminate_data_block(self):
        self.dataset["products"][3]["product"] = 'AIEP </script><script>alert("x")</script> & 中文'
        html = aiep.render_aiep_frontend(self.dataset)
        embedded = re.search(r'id="mytech-dataset">([\s\S]*?)</script>', html)[1]
        self.assertNotIn("<", embedded)
        self.assertEqual(json.loads(embedded), self.dataset)

    def test_deterministic_writer_and_read_only_stale_check(self):
        outputs = aiep.render_outputs(self.dataset)
        aiep.write_outputs(outputs, self.directory)
        paths = [self.directory / name for name in outputs]
        before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths}
        aiep.write_outputs(outputs, self.directory)
        self.assertEqual(before, {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths})
        page = self.directory / "site/index.html"
        page.write_bytes(page.read_bytes() + b"stale")
        mutated = page.read_bytes()
        self.assertTrue(aiep.check_outputs(outputs, self.directory))
        self.assertEqual(page.read_bytes(), mutated)

    def test_extra_upload_files_fail_closed(self):
        outputs = aiep.render_outputs(self.dataset)
        aiep.write_outputs(outputs, self.directory)
        (self.directory / "site/unexpected.txt").write_text("unexpected")
        self.assertTrue(aiep.check_outputs(outputs, self.directory))
        with self.assertRaisesRegex(ValueError, "Unexpected AIEP upload"):
            aiep.write_outputs(outputs, self.directory)

    def test_output_symlink_cannot_overwrite_original(self):
        outputs = aiep.render_outputs(self.dataset)
        (self.directory / "site").mkdir(parents=True)
        protected = Path(self.temp.name) / "protected.html"
        protected.write_text("original")
        (self.directory / "site/index.html").symlink_to(protected)
        with self.assertRaisesRegex(ValueError, "symlink"):
            aiep.write_outputs(outputs, self.directory)
        self.assertEqual(protected.read_text(), "original")

    def test_secret_scanner_returns_only_rules_and_lines_and_generation_rejects_embedding(self):
        # Synthetic patterns only, never environment files or real credentials.
        token = "openapi-" + "a" * 28
        for text in (token, 'api_key = "' + "x" * 28 + '"', '"authorization": "Bearer ' + "x" * 28 + '"',
                     "-----BEGIN PRIVATE KEY-----", "https://user:password@example.invalid", "AKIA" + "A" * 16):
            findings = aiep.scan_credentials(text)
            self.assertTrue(findings)
            self.assertNotIn(token, str(findings))
            self.assertTrue(all(isinstance(line, int) for _, line in findings))
        self.dataset["products"][3]["key_features"].append(token)
        with self.assertRaisesRegex(ValueError, "Credential review failed") as raised:
            aiep.render_outputs(self.dataset)
        self.assertNotIn(token, str(raised.exception))

    def test_candidate_generation_never_renders_or_copies_workflow(self):
        from unittest.mock import patch
        with patch.object(sync, "render_outputs", side_effect=AssertionError("workflow rendering forbidden")):
            outputs = aiep.render_outputs(self.dataset)
        self.assertNotIn(sync.WORKFLOW, outputs)
        html = outputs["site/index.html"].decode()
        self.assertNotIn(sync.STATE_EXTRACTION_PROMPT.read_text(encoding="utf-8"), html)
        self.assertNotIn(sync.RECOMMENDATION_PROMPT.read_text(encoding="utf-8"), html)

    def test_unified_catalogue_checker_detects_stale_aiep_upload(self):
        import contextlib
        import io
        args = ["--output-root", self.temp.name]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(sync.main(args), 0)
            self.assertEqual(sync.main([*args, "--check"]), 0)
            page = self.directory / "site/index.html"
            page.write_bytes(page.read_bytes() + b"modified")
            self.assertEqual(sync.main([*args, "--check"]), 1)
        self.assertTrue(page.read_bytes().endswith(b"modified"))


if __name__ == "__main__":
    unittest.main()
