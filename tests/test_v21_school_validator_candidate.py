"""School alignment contract tests use synthetic metadata, never Downloads."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import build_v21_school_validator_candidate as build


class SchoolValidatorCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.school = json.loads((build.ROOT / "workflow/v2.1/original/2026-10-24/workflow.sanitized.json").read_bytes())
        build.field(cls.school, "ikIzMK483vihRths", "model")["value"] = "deepseek/deepseek-v4.1-flash"
        cls.school["chatConfig"]["_id"] = "synthetic-private-school-metadata"
        cls.reference = json.loads((build.ROOT / build.REFERENCE).read_bytes())

    def test_exact_four_changes_and_reversible_preservation(self):
        before = deepcopy(self.school)
        candidate = build.align_workflow(self.school, self.reference)
        self.assertEqual(self.school, before, "generation must not mutate the source")
        self.assertEqual(build.validate_candidate(self.school, candidate, self.reference), [
            {"op": op, "path": path} for op, path in
            zip(["replace", "add", "add", "replace"], build.ALLOWED_PATHS)])
        self.assertEqual(candidate["chatConfig"], self.school["chatConfig"])
        for node_id, _ in build.AI_PROMPTS:
            self.assertEqual(build.node(candidate, node_id), build.node(self.school, node_id))

    def test_existing_inputs_outputs_and_metadata_are_not_overwritten(self):
        candidate = build.align_workflow(self.school, self.reference)
        old = build.node(self.school, build.sync.VALIDATOR_ID)
        new = build.node(candidate, build.sync.VALIDATOR_ID)
        for index, item in enumerate(old["inputs"]):
            if index != 2:
                self.assertEqual(item, new["inputs"][index])
        self.assertEqual(old["outputs"], new["outputs"][:-1])
        self.assertEqual(new["inputs"][7], build.node(self.reference, build.sync.VALIDATOR_ID)["inputs"][7])
        self.assertEqual(new["outputs"][11], build.node(self.reference, build.sync.VALIDATOR_ID)["outputs"][11])

    def test_out_of_boundary_prompt_model_metadata_edge_and_code_changes_fail(self):
        changes = [
            lambda c: build.field(c, "ikIzMK483vihRths", "model").update(value="glm-4.7"),
            lambda c: build.field(c, "etNrwEXVwr5sySpK", "description").update(value="changed"),
            lambda c: c["chatConfig"].update(_id="changed"),
            lambda c: c["edges"].pop(),
            lambda c: build.field(c, "v21RmbInputNormalize", "code").update(value="changed"),
            lambda c: build.node(c, build.sync.VALIDATOR_ID)["inputs"][7].update(required=True),
        ]
        for change in changes:
            with self.subTest(change=changes.index(change)):
                candidate = build.align_workflow(self.school, self.reference)
                change(candidate)
                with self.assertRaises(ValueError):
                    build.validate_candidate(self.school, candidate, self.reference)

    def test_reordered_nodes_and_occupied_append_slots_fail_without_mutation(self):
        for scenario in ("reorder", "input", "output"):
            school = deepcopy(self.school)
            if scenario == "reorder":
                school["nodes"][10], school["nodes"][11] = school["nodes"][11], school["nodes"][10]
            elif scenario == "input":
                school["nodes"][11]["inputs"].append({"key": "existing"})
            else:
                school["nodes"][11]["outputs"].append({"key": "existing", "id": "existing"})
            before = deepcopy(school)
            with self.assertRaises(ValueError):
                build.align_workflow(school, self.reference)
            self.assertEqual(school, before)

    def test_generation_is_deterministic_and_report_excludes_metadata_value(self):
        raw = b"\xef\xbb\xbf" + json.dumps(self.school, ensure_ascii=False).encode()
        with patch.object(build, "SCHOOL_SHA256", build.digest(raw)):
            first = build.render_outputs(raw)
            self.assertEqual(first, build.render_outputs(raw))
        candidate = json.loads(first[build.CANDIDATE])
        report = json.loads(first["preservation.json"])
        self.assertEqual(report["candidate_sha256"], build.digest(first[build.CANDIDATE]))
        self.assertEqual(candidate["chatConfig"], self.school["chatConfig"])
        self.assertNotIn("synthetic-private-school-metadata", first["preservation.json"].decode())
        self.assertEqual(report["preserved"]["chat_config_including_private_metadata_sha256"], build.digest(build.canonical(self.school["chatConfig"])))

    def test_school_hash_mismatch_fails_before_repository_reads(self):
        with patch.object(Path, "read_bytes", side_effect=AssertionError("must not read repository")):
            with self.assertRaisesRegex(ValueError, "School SHA-256"):
                build.render_outputs(b"changed source")

    def test_idempotence_read_only_check_and_preflight_overwrite_refusal(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary).resolve() / "candidate"
            outputs = {"one": b"one", "two": b"two"}
            build.write_outputs(outputs, directory)
            before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in directory.iterdir()}
            build.write_outputs(outputs, directory)
            build.write_outputs(outputs, directory, check=True)
            self.assertEqual(before, {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in directory.iterdir()})
            with self.assertRaises(ValueError):
                build.write_outputs({"new": b"new", "two": b"tampered"}, directory)
            self.assertFalse((directory / "new").exists())
            with self.assertRaises(ValueError):
                build.write_outputs({"missing": b"data"}, directory, check=True)
            self.assertFalse((directory / "missing").exists())

    def test_symlink_outputs_are_refused_before_read_or_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / "target").mkdir()
            try:
                (root / "link").symlink_to(root / "target", target_is_directory=True)
            except OSError:
                self.skipTest("Directory symlinks unavailable")
            with self.assertRaises(ValueError):
                build.write_outputs({"candidate": b"data"}, root / "link")
            self.assertEqual(list((root / "target").iterdir()), [])


if __name__ == "__main__":
    unittest.main()
