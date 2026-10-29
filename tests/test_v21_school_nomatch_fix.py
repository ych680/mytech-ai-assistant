"""Hotfix preservation checks use public synthetic metadata, never Downloads."""

import json
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import build_v21_school_nomatch_fix as fix


class SchoolNoMatchFixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = json.loads((fix.ROOT / fix.alignment.REFERENCE).read_bytes())
        for node_id, _ in fix.alignment.AI_PROMPTS:
            fix.alignment.field(cls.source, node_id, "model")["value"] = "deepseek/deepseek-v4.1-flash"
        cls.source["chatConfig"]["_id"] = "synthetic-school-metadata"
        cls.raw = b"\xef\xbb\xbf" + json.dumps(cls.source, ensure_ascii=False, indent=2).encode()
        cls.template = fix.TEMPLATE.read_text(encoding="utf-8")

    def test_only_helper_changes_and_raw_source_can_be_recovered_exactly(self):
        raw = fix.patch_candidate(self.raw, self.template)
        candidate = json.loads(raw)
        self.assertEqual(fix.alignment.semantic_diff(self.source, candidate), fix.ALLOWED_DIFF)
        old_code = fix.alignment.field(self.source, fix.alignment.sync.VALIDATOR_ID, "code")["value"]
        new_code = fix.alignment.field(candidate, fix.alignment.sync.VALIDATOR_ID, "code")["value"]
        a, _, b = fix.split_helper(old_code)
        c, _, d = fix.split_helper(new_code)
        self.assertEqual((a, b), (c, d))
        recovered = raw.replace(json.dumps(new_code, ensure_ascii=False).encode(),
                                json.dumps(old_code, ensure_ascii=False).encode(), 1)
        self.assertEqual(recovered, self.raw)
        self.assertEqual(candidate["chatConfig"], self.source["chatConfig"])

    def test_old_or_reordered_or_already_patched_sources_are_rejected(self):
        for kind in ("older", "reordered", "already patched"):
            source = deepcopy(self.source)
            if kind == "older":
                fix.alignment.field(source, fix.alignment.sync.VALIDATOR_ID, "code")["value"] = "function main() {}"
            elif kind == "reordered":
                source["nodes"][10], source["nodes"][11] = source["nodes"][11], source["nodes"][10]
            else:
                source = json.loads(fix.patch_candidate(self.raw, self.template))
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                fix.patch_candidate(json.dumps(source, ensure_ascii=False).encode(), self.template)

    def test_unverified_real_source_fails_before_template_or_repository_reads(self):
        with patch.object(Path, "read_bytes", side_effect=AssertionError("must not read")):
            with self.assertRaisesRegex(ValueError, "fingerprint"):
                fix.prepare_outputs(b"unverified", b"", b"", b"")

    def test_invalid_or_unchanged_helper_fails(self):
        old_code = fix.alignment.field(self.source, fix.alignment.sync.VALIDATOR_ID, "code")["value"]
        for template in ("", "function unrelated() {}", fix.split_helper(old_code)[1]):
            with self.subTest(template=template[:30]), self.assertRaises(ValueError):
                fix.patch_candidate(self.raw, template)

    def test_output_never_overwrites_and_check_preserves_bytes_and_mtime(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary).resolve()
            raw = fix.patch_candidate(self.raw, self.template)
            fix.alignment.write_outputs({fix.CANDIDATE: raw}, directory)
            path = directory / fix.CANDIDATE
            before = (path.read_bytes(), path.stat().st_mtime_ns)
            fix.alignment.write_outputs({fix.CANDIDATE: raw}, directory, check=True)
            self.assertEqual(before, (path.read_bytes(), path.stat().st_mtime_ns))
            with self.assertRaisesRegex(ValueError, "refusing overwrite"):
                fix.alignment.write_outputs({fix.CANDIDATE: b"different"}, directory)
            self.assertEqual(before, (path.read_bytes(), path.stat().st_mtime_ns))


if __name__ == "__main__":
    unittest.main()
