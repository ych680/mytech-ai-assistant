"""Offline v2.1 generation, portability and consistency regression tests."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import build_knowledge as knowledge
from tools import sync_catalogue as sync
from tools.validate_products import load_dataset, validate_dataset, TEST_DATASET


class CatalogueSyncTests(unittest.TestCase):
    def setUp(self):
        self.dataset = load_dataset(TEST_DATASET)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.directory = self.root / sync.OUTPUT_SUBDIR
        self.master = self.root / "master.json"
        self.save_master()

    def save_master(self):
        self.master.write_text(sync.json_text(self.dataset), encoding="utf-8")

    def cli(self, check=False):
        script = "check_catalogue_consistency.py" if check else "sync_catalogue.py"
        return subprocess.run([sys.executable, "-B", str(sync.ROOT / "tools" / script),
                               "--dataset", str(self.master), "--output-root", str(self.root)],
                              cwd=self.root, capture_output=True, text=True)

    def generate(self):
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)

    def assert_all_catalogues(self, dataset, directory):
        node_dataset = json.loads((directory / "catalogue.json").read_text(encoding="utf-8"))
        self.assertEqual(node_dataset, dataset)
        html = (directory / "index.html").read_text(encoding="utf-8")
        embedded = re.search(r'id="mytech-dataset">([\s\S]*?)</script>', html)[1]
        self.assertEqual(json.loads(embedded), dataset)
        workflow = json.loads((directory / sync.WORKFLOW).read_text(encoding="utf-8"))
        code = sync.validation_code(workflow)["value"]
        start, end = sync.catalogue_span(code)
        self.assertEqual(json.loads(code[start:end]), sync.catalogue_projection(dataset))
        rag = (directory / sync.KNOWLEDGE).read_text(encoding="utf-8")
        self.assertEqual(knowledge.check_knowledge(dataset, rag), [])
        _, _, records = knowledge._parse_markdown(rag)
        self.assertEqual(len(records), len(dataset["products"]))
        for product, (_, record) in zip(dataset["products"], records):
            self.assertEqual(record["Review Status"], product["review_status"])
            self.assertIn("TEST ONLY", record["Release Scope"])
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["product_count"], len(dataset["products"]))
        for name, checksum in manifest["outputs"].items():
            self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(), checksum)

    def test_checked_in_outputs_match_all_master_fields(self):
        self.assertEqual(validate_dataset(self.dataset, test_v21=True), [])
        self.assertEqual(len(self.dataset["products"]), 54)
        self.assert_all_catalogues(self.dataset, sync.ROOT / sync.OUTPUT_SUBDIR)
        self.assertEqual(sync.check_outputs(sync.render_outputs(self.dataset), sync.ROOT / sync.OUTPUT_SUBDIR), [])

    def test_55th_product_updates_every_catalogue_after_regeneration(self):
        self.generate()
        product = deepcopy(self.dataset["products"][3])
        product.update(id="LAP-007", product="Expansion Test Laptop", price_rmb=3123,
                       review_status="NEW CANDIDATE — unverified")
        self.dataset["products"].append(product)
        self.save_master()
        stale = self.cli(check=True)
        self.assertEqual(stale.returncode, 1)
        self.assertIn("stale", stale.stderr)
        self.generate()
        self.assert_all_catalogues(self.dataset, self.directory)
        self.assertEqual(self.cli(check=True).returncode, 0)

    def test_generation_is_deterministic_and_preserves_stable_inputs(self):
        stable = [sync.WORKFLOW_TEMPLATE, sync.FRONTEND, TEST_DATASET,
                  sync.ROOT / "mytech_v1_product_dataset.json", sync.ROOT / "mytech_v2_server.mjs",
                  sync.ROOT / "mytech_response.mjs", sync.ROOT / "knowledge/MyTech_Product_Knowledge_v1.md"]
        before = {p: p.read_bytes() for p in stable}
        master_before = self.master.read_bytes()
        original = deepcopy(self.dataset)
        self.generate()
        first = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.directory.iterdir()}
        self.generate()
        self.assertEqual(first, {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.directory.iterdir()})
        self.assertEqual(before, {p: p.read_bytes() for p in stable})
        self.assertEqual(master_before, self.master.read_bytes())
        self.assertEqual(self.dataset, original)
        self.assertEqual(sync.render_outputs(original), sync.render_outputs(original))

    def test_workflow_reviewed_overlays_preserve_graph_state_contract(self):
        original = json.loads(sync.WORKFLOW_TEMPLATE.read_text(encoding="utf-8-sig"))
        generated = json.loads(sync.render_outputs(self.dataset)[sync.WORKFLOW])
        original_code = sync.validation_code(original)["value"]
        old_start, old_end = sync.catalogue_span(original_code)
        expected = original_code[:old_start] + sync.script_json(sync.catalogue_projection(self.dataset)) + original_code[old_end:]
        self.assertEqual(sync.validation_code(generated)["value"], sync.harden_validation_code(expected))
        sync.validation_code(generated)["value"] = original_code
        sync.apply_test_settings(original)
        sync.apply_extraction_reliability(original)
        sync.apply_prompt_optimization(original)
        self.assertEqual(generated, original)
        sync.assert_portable(generated)

    def test_check_is_read_only_for_modified_missing_and_stale_outputs(self):
        self.generate()
        for name in sync.render_outputs(self.dataset):
            with self.subTest(name=name):
                path = self.directory / name
                original = path.read_bytes()
                path.write_bytes(original + b"\nmodified")
                before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.directory.iterdir()}
                result = self.cli(check=True)
                self.assertEqual(result.returncode, 1)
                self.assertIn(name, result.stderr)
                self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.directory.iterdir()})
                path.unlink()
                self.assertEqual(self.cli(check=True).returncode, 1)
                self.assertFalse(path.exists())
                path.write_bytes(original)
        self.assertEqual(self.cli(check=True).returncode, 0)

    def test_check_missing_directory_does_not_create_it(self):
        self.assertEqual(self.cli(check=True).returncode, 1)
        self.assertFalse(self.directory.exists())

    def test_invalid_product_ids_names_prices_categories_and_missing_fields(self):
        candidate = self.dataset["products"][3]
        cases = [(field, None) for field in candidate]
        cases += [("id", value) for value in ("BAD", "MOU-004", "LAP-000", "LAP-0000", " LAP-007", "LAP-001")]
        cases += [("product", value) for value in ("", "  ", "constructor", "__proto__", self.dataset["products"][0]["product"], self.dataset["products"][0]["product"].lower())]
        cases += [("price_rmb", value) for value in (0, -1, True, 1.5, "3299", 2 ** 53, float("nan"))]
        cases += [("category", "Camera"), ("review_status", "CURRENT"), ("review_status", "EXISTING BASELINE")]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                data = deepcopy(self.dataset)
                if value is None:
                    del data["products"][3][field]
                else:
                    data["products"][3][field] = value
                with self.assertRaises(ValueError):
                    sync.render_outputs(data)

    def test_baseline_cannot_be_removed_changed_or_promoted(self):
        for field, value in (("price_rmb", 1), ("source", "Changed"), ("category", "Mouse"), ("main_usage", ["Gaming"])):
            data = deepcopy(self.dataset)
            data["products"][0][field] = value
            self.assertTrue(any("baseline" in error for error in validate_dataset(data, test_v21=True)))
        self.dataset["products"].pop(0)
        self.assertTrue(any("missing baseline" in error for error in validate_dataset(self.dataset, test_v21=True)))

    def test_invalid_master_never_rewrites_outputs(self):
        self.generate()
        before = {p: p.read_bytes() for p in self.directory.iterdir()}
        self.dataset["products"][3]["price_rmb"] = 0
        self.save_master()
        self.assertEqual(self.cli().returncode, 1)
        self.assertEqual(before, {p: p.read_bytes() for p in self.directory.iterdir()})

    def test_portable_template_binding_changes_fail_closed(self):
        workflow = json.loads(sync.WORKFLOW_TEMPLATE.read_text(encoding="utf-8-sig"))
        workflow["chatConfig"]["datasetId"] = "account-specific"
        with self.assertRaises(ValueError):
            sync.assert_portable(workflow)
        del workflow["chatConfig"]["datasetId"]
        for node in workflow["nodes"]:
            for field in node["inputs"]:
                if field["key"] in ("datasets", "model", "modelId"):
                    original = deepcopy(field)
                    field["value"] = [{"datasetId": "account-specific"}] if field["key"] == "datasets" else "account-model"
                    with self.assertRaises(ValueError):
                        sync.assert_portable(workflow)
                    field.clear()
                    field.update(original)
                    if field["key"] == "datasets":
                        field["valueDesc"] = '[{"datasetId":"account-specific"}]'
                        with self.assertRaises(ValueError):
                            sync.assert_portable(workflow)
                        field.update(original)

    def test_changed_template_markers_require_review(self):
        with self.assertRaises(ValueError):
            sync.catalogue_span("const RENAMED = {};")
        with self.assertRaises(ValueError):
            sync.replace_once("missing", "expected", "new")
        with patch.object(sync, "FRONTEND_VALIDATOR", self.root / "missing.js"):
            with self.assertRaises(OSError):
                sync.render_outputs(self.dataset)
        for missing in ("USAGE_VALIDATOR", "VALIDATION_FAILURE", "USAGE_COMPATIBILITY", "WORKFLOW_TEMPLATE"):
            with patch.object(sync, missing, self.root / "missing-template"):
                with self.assertRaises(OSError):
                    sync.render_outputs(self.dataset)
        with self.assertRaises(ValueError):
            sync.harden_validation_code("unexpected validation template")

    def test_invalid_usage_policy_cannot_generate_outputs(self):
        policy = self.root / "policy.json"
        for invalid in ([], {}, {"Gaming": []}, {"Gaming": [42]}):
            policy.write_text(json.dumps(invalid), encoding="utf-8")
            with patch.object(sync, "USAGE_COMPATIBILITY", policy):
                with self.assertRaisesRegex(ValueError, "usage policy"):
                    sync.render_outputs(self.dataset)

    def test_script_embedding_escapes_html_without_changing_product_identity(self):
        self.dataset["products"][3]["product"] = 'Test </script><script>alert("x")</script> & 中文'
        outputs = sync.render_outputs(self.dataset)
        html = outputs["index.html"].decode("utf-8")
        embedded = re.search(r'id="mytech-dataset">([\s\S]*?)</script>', html)[1]
        self.assertNotIn("<", embedded)
        self.assertEqual(json.loads(embedded), self.dataset)
        code = sync.validation_code(json.loads(outputs[sync.WORKFLOW]))["value"]
        start, end = sync.catalogue_span(code)
        self.assertIn(self.dataset["products"][3]["product"], json.loads(code[start:end]))

    def test_output_symlinks_cannot_overwrite_stable_files(self):
        self.directory.mkdir(parents=True)
        target = self.root / "protected.json"
        target.write_text("protected", encoding="utf-8")
        try:
            (self.directory / "catalogue.json").symlink_to(target)
        except OSError:
            self.skipTest("Symlink creation is unavailable on this platform")
        self.assertEqual(self.cli().returncode, 1)
        self.assertEqual(target.read_text(encoding="utf-8"), "protected")


if __name__ == "__main__":
    unittest.main()
