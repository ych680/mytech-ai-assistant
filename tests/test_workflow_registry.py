"""Actual version snapshots, catalogue consistency, evidence and secret-boundary tests."""

from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from tools import check_workflow_registry as check
from tools import sync_catalogue as sync


class WorkflowRegistryTests(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        registry = json.loads((check.ROOT / check.REGISTRY).read_text())
        files = {str(check.REGISTRY), registry["comparison"], registry["catalogue"]["master"],
                 *registry["sources_and_generated_outputs"]}
        for entry in registry["variants"].values():
            files.update([entry["snapshot"], entry["provenance"]])
        for name in files:
            path = root / name; path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(check.ROOT / name, path)
        return root, registry

    def save(self, root, name, value):
        (root / name).write_text(sync.json_text(value))

    def test_registry_preserves_both_actual_versions_and_original_default(self):
        registry, graphs, differences = check.check_registry()
        self.assertEqual(registry["default_variant"], "original")
        self.assertFalse(registry["automatic_promotion"])
        self.assertEqual(set(graphs), {"original", "optimized"})
        self.assertEqual(differences["difference_count"], 6)
        self.assertEqual(len(differences["model_change_paths"]), 2)
        self.assertEqual(len(differences["prompt_change_paths"]), 2)
        self.assertEqual(len(differences["layout_change_paths"]), 2)
        self.assertEqual(differences["other_change_paths"], [])

    def test_registry_check_is_read_only(self):
        root, _ = self.fixture()
        before = {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in root.rglob('*') if p.is_file()}
        check.check_registry(root)
        self.assertEqual(before, {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in root.rglob('*') if p.is_file()})

    def test_original_cannot_be_implicitly_replaced_by_optimized(self):
        root, registry = self.fixture()
        registry["default_variant"] = "optimized"
        self.save(root, check.REGISTRY, registry)
        with self.assertRaises(ValueError): check.check_registry(root)

    def test_snapshot_tamper_fails_checksum(self):
        root, registry = self.fixture()
        path = root / registry["variants"]["optimized"]["snapshot"]
        path.write_bytes(path.read_bytes() + b"modified")
        with self.assertRaises(ValueError): check.check_registry(root)

    def test_master_drift_is_detected_without_regenerating_actual_exports(self):
        root, registry = self.fixture()
        path = registry["catalogue"]["master"]
        data = json.loads((root / path).read_text()); data["products"][-1]["price_rmb"] += 1
        self.save(root, path, data)
        # Even when the Master hash is deliberately updated, snapshots still must match.
        registry["catalogue"]["sha256"] = check.sha256((root / path).read_bytes())
        registry["sources_and_generated_outputs"][path] = registry["catalogue"]["sha256"]
        self.save(root, check.REGISTRY, registry)
        with self.assertRaisesRegex(ValueError, "catalogue differs"): check.check_registry(root)

    def test_extra_logic_change_is_not_classified_as_a_prompt_optimization(self):
        _, graphs, _ = check.check_registry()
        altered = deepcopy(graphs["optimized"])
        sync.node_input(altered, sync.RECOMMENDATION_ID, "history")["value"] = 3
        report = check.comparison(graphs["original"], altered)
        self.assertTrue(report["other_change_paths"])
        self.assertFalse(report["routing_validation_memory_output_and_other_configuration_identical"])

    def test_missing_KB_and_publish_revision_remain_explicit(self):
        registry, graphs, _ = check.check_registry()
        for role, graph in graphs.items():
            self.assertEqual(sync.node_input(graph, sync.RETRIEVAL_ID, "datasets")["value"], [])
            entry = registry["variants"][role]
            self.assertFalse(entry["kb_binding"]["exported_selection_present"])
            provenance = json.loads((check.ROOT / entry["provenance"]).read_text())
            self.assertIsNone(provenance["published_revision"])

    def test_sensitive_fields_are_rejected_without_disclosing_values(self):
        synthetic = "synthetic-not-a-real-credential"
        for value in ({"api_key": synthetic}, {"inputs": [{"key": "apiKey", "value": synthetic}]}):
            self.assertTrue(check.sensitive_paths(value))
            with self.assertRaises(ValueError) as raised:
                check.inspect_public_json(json.dumps(value).encode())
            self.assertNotIn(synthetic, str(raised.exception))

    def test_private_environment_and_outside_paths_are_rejected_before_read(self):
        for path in (".env", "../private.json", "/tmp/private.json", "folder/.env.v21.test"):
            with self.assertRaises(ValueError): check.safe_path(check.ROOT, path)

    def test_symlink_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); target = root / "public.json"; target.write_text('{}')
            try: (root / "alias.json").symlink_to(target)
            except OSError: self.skipTest("Symlink privileges unavailable")
            with self.assertRaises(ValueError): check.safe_path(root, "alias.json")

    def test_smoke_observation_is_not_a_completed_AB_or_verified_platform_bill(self):
        registry, _, _ = check.check_registry()
        smoke = json.loads((check.ROOT / registry["performance"]["record"]).read_text())
        self.assertEqual(smoke["overall"]["workflow_latency_seconds"], 34.45)
        self.assertEqual(smoke["overall"]["combined_AI_node_credits"], 0.9531)
        self.assertFalse(smoke["overall"]["platform_wide_billed_credits_independently_verified"])
        self.assertFalse(smoke["interpretation"]["completed_six_request_AB_evaluation"])
        self.assertFalse(smoke["interpretation"]["prompt_shortening_demonstrated_meaningful_latency_improvement"])
        self.assertFalse(registry["variants"]["optimized"]["default_deployed"])

    def test_generated_AB_rows_remain_unexecuted(self):
        import csv
        path = check.ROOT / "generated/glm47_prompt_ab/six-request-results-template.csv"
        with path.open(newline='') as stream: rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 6)
        self.assertTrue(all(row["execution_status"] == "NOT_RUN" for row in rows))
