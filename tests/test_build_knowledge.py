"""Knowledge builder regression tests using isolated temporary files."""

from copy import deepcopy
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

from tools import build_knowledge as builder


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "build_knowledge.py"
KNOWLEDGE = ROOT / "knowledge" / "MyTech_Product_Knowledge_v1.md"


class KnowledgeBuilderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source_bytes = builder.DEFAULT_DATASET.read_bytes()
        cls.knowledge_bytes = KNOWLEDGE.read_bytes()
        cls.catalogue = json.loads(cls.source_bytes)
        cls.legacy = cls.knowledge_bytes.decode("utf-8")

    def setUp(self):
        self.dataset = deepcopy(self.catalogue)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.input = self.directory / "dataset.json"
        self.output = self.directory / "knowledge.md"
        self.input.write_text(json.dumps(self.dataset, ensure_ascii=False), encoding="utf-8")

    def run_cli(self, *args, default=False):
        command = [sys.executable, "-B", str(SCRIPT)]
        if not default:
            command.extend(["--dataset", str(self.input)])
        before = self.input.read_bytes()
        result = subprocess.run(command + list(args), cwd=self.directory,
                                capture_output=True, text=True, check=False)
        self.assertEqual(before, self.input.read_bytes())
        self.assertEqual(self.source_bytes, builder.DEFAULT_DATASET.read_bytes())
        self.assertEqual(self.knowledge_bytes, KNOWLEDGE.read_bytes())
        return result

    def test_current_knowledge_consistent_and_default_path_independent_of_cwd(self):
        self.assertEqual(builder.check_knowledge(self.dataset, self.legacy), [])
        result = self.run_cli("--check", str(KNOWLEDGE), default=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("27 product records", result.stdout)

    def test_deterministic_generation_preserves_all_records(self):
        before = deepcopy(self.dataset)
        first = builder.render_knowledge(self.dataset)
        self.assertEqual(first, builder.render_knowledge(self.dataset))
        self.assertEqual(before, self.dataset)
        self.assertEqual(first.count("## Product Record:"), 27)
        self.assertEqual(builder.check_knowledge(self.dataset, first), [])
        _, _, records = builder._parse_markdown(first)
        self.assertEqual(len(records), 27)
        for product, (heading, fields) in zip(self.dataset["products"], records):
            self.assertEqual(heading, f"{product['id']} — {product['product']}")
            self.assertEqual(fields, builder._record(product, "RMB"))
        result = self.run_cli("--output", str(self.output))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output.read_bytes(), first.encode("utf-8"))
        self.assertNotIn(b"\r\n", self.output.read_bytes())

    def test_unicode_punctuation_and_list_boundaries_round_trip(self):
        unusual = "  中文 × & <tag> &copy; \\ `code` **bold** [link](url) # | ~ ; ,\nSource: fake\r\t\u2028end  "
        product = self.dataset["products"][0]
        for field in ("id", "product", "source"):
            product[field] = unusual + field
        product["main_usage"] = ["Study, Office", unusual]
        product["key_features"] = ["8,000 DPI sensor; quiet clicks", unusual]
        self.dataset["price_note"] += unusual
        rendered = builder.render_knowledge(self.dataset)
        self.assertEqual(builder.check_knowledge(self.dataset, rendered), [])
        _, metadata, records = builder._parse_markdown(rendered)
        self.assertEqual(metadata["Price note"], self.dataset["price_note"])
        self.assertEqual(records[0][1], builder._record(product, "RMB"))
        # Changing array boundaries must be detected in the generated format.
        changed = deepcopy(self.dataset)
        changed["products"][0]["main_usage"] = ["Study", "Office", unusual]
        self.assertTrue(builder.check_knowledge(changed, rendered))

    def test_generated_lists_cannot_be_replaced_with_inline_strings(self):
        generated = builder.render_knowledge(self.dataset)
        product = self.dataset["products"][0]
        cases = (
            ("Supported categories", self.dataset["supported_categories"], ", ", "."),
            ("Main Usage", product["main_usage"], ", ", ""),
            ("Key Features", product["key_features"], "; ", ""),
        )
        for label, values, delimiter, suffix in cases:
            with self.subTest(label=label):
                bullet_lines = "\n".join(builder._field_lines({label: values}))
                inline = f"{label}: {builder._escape(delimiter.join(values) + suffix)}"
                changed = generated.replace(bullet_lines, inline, 1)
                self.assertNotEqual(changed, generated)
                errors = builder.check_knowledge(self.dataset, changed)
                self.assertTrue(any(label in error for error in errors), errors)
                self.output.write_text(changed, encoding="utf-8")
                before = self.output.read_bytes()
                result = self.run_cli("--check", str(self.output))
                self.assertEqual(result.returncode, 1)
                self.assertEqual(self.output.read_bytes(), before)
        self.assertEqual(builder.check_knowledge(self.dataset, generated), [])
        self.assertEqual(builder.check_knowledge(self.dataset, self.legacy), [])

    def test_changed_product_fields_detected_in_both_formats(self):
        generated = builder.render_knowledge(self.dataset)
        changes = {
            "Product ID": ("LAP-001", "LAP-999"),
            "Product": (self.dataset["products"][0]["product"], "Changed model"),
            "Category": ("Laptop", "Desktop"),
            "Reference Price": ("RMB 5799", "RMB 5800"),
            "Tier": ("Entry", "Premium"),
            "Source": ("Lenovo Official Store", "Changed source"),
        }
        for text in (self.legacy, generated):
            for label, (old, new) in changes.items():
                with self.subTest(label=label, generated=text == generated):
                    encoded_old = builder._escape(old) if text == generated else old
                    changed = text.replace(f"{label}: {encoded_old}", f"{label}: {new}", 1)
                    self.assertNotEqual(changed, text)
                    errors = builder.check_knowledge(self.dataset, changed)
                    self.assertTrue(any(label in error for error in errors), errors)
            for old in ("Study", "14-inch display", "8,000 DPI sensor"):
                encoded = builder._escape(old) if text == generated else old
                changed = text.replace(encoded, "Changed description", 1)
                self.assertTrue(builder.check_knowledge(self.dataset, changed))

    def test_missing_extra_and_reordered_records(self):
        header, *records = self.legacy.split("## Product Record: ")
        variants = (
            records[:-1], records + [records[-1]],
            [records[1], records[0]] + records[2:],
        )
        for variant in variants:
            text = header + "".join("## Product Record: " + record for record in variant)
            self.assertTrue(builder.check_knowledge(self.dataset, text))

    def test_metadata_differences_and_known_disclaimer(self):
        generated = builder.render_knowledge(self.dataset)
        for old, new in (
            ("2026-09-12", "2026-09-13"), ("Currency: RMB", "Currency: USD"),
            (builder.DISCLAIMER, "Live prices available now."),
            ("# MyTech Product Knowledge v1", "# MyTech Product Knowledge v2"),
            ("Laptop, Desktop", "Desktop, Laptop"),
        ):
            self.assertTrue(builder.check_knowledge(self.dataset, self.legacy.replace(old, new, 1)))
        for old, new in (("Version: 1.0", "Version: 2.0"),
                         ("Dataset name: MyTech v1 Product Dataset", "Dataset name: Other")):
            self.assertTrue(builder.check_knowledge(self.dataset, generated.replace(old, new, 1)))
        changed = deepcopy(self.dataset)
        changed["price_note"] = "A different price policy"
        self.assertTrue(builder.check_knowledge(changed, self.legacy))
        self.assertEqual(builder.check_knowledge(self.dataset, self.legacy), [])

    def test_malformed_unexpected_and_duplicate_record_content(self):
        for replacement in (
            "## Product Record LAP-001", "### Unexpected record", "Unexpected prose",
            "Unknown Field: surprise", "Source: Lenovo Official Store\nSource: duplicate",
        ):
            text = self.legacy.replace("Source: Lenovo Official Store", replacement, 1)
            self.assertTrue(builder.check_knowledge(self.dataset, text))
        self.assertTrue(builder.check_knowledge(self.dataset, self.legacy.replace("Tier: Entry\n", "", 1)))
        self.assertTrue(builder.check_knowledge(self.dataset, ""))

    def test_invalid_dataset_never_creates_output(self):
        invalid = deepcopy(self.dataset)
        invalid["products"][0]["price_rmb"] = False
        invalid_unicode = deepcopy(self.dataset)
        invalid_unicode["products"][0]["source"] = "\ud800"
        for text in (json.dumps(invalid), json.dumps(invalid_unicode),
                     '{"x":1,"x":2}', '{"x":1e400}', '{'):
            self.input.write_text(text, encoding="utf-8")
            result = self.run_cli("--output", str(self.output))
            self.assertEqual(result.returncode, 1)
            self.assertFalse(self.output.exists())
        with self.assertRaises(ValueError):
            builder.render_knowledge(invalid)
        with self.assertRaises(ValueError):
            builder.check_knowledge(invalid, self.legacy)

    def test_check_is_read_only_for_success_and_failure(self):
        for text in (self.legacy, self.legacy.replace("RMB 5799", "RMB 1", 1)):
            self.output.write_text(text, encoding="utf-8")
            before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.directory.iterdir()}
            result = self.run_cli("--check", str(self.output))
            self.assertEqual(result.returncode, 0 if text == self.legacy else 1)
            after = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.directory.iterdir()}
            self.assertEqual(before, after)

    def test_existing_output_and_source_files_cannot_be_overwritten(self):
        self.output.write_bytes(b"keep existing file")
        for path in (self.output, self.input, KNOWLEDGE, builder.DEFAULT_DATASET):
            before = path.read_bytes()
            result = self.run_cli("--output", str(path))
            self.assertEqual(result.returncode, 1)
            self.assertEqual(before, path.read_bytes())

    def test_cli_requires_exactly_one_mode_and_handles_missing_check(self):
        for args in ((), ("--check", str(KNOWLEDGE), "--output", str(self.output))):
            self.assertEqual(self.run_cli(*args).returncode, 2)
            self.assertFalse(self.output.exists())
        result = self.run_cli("--check", str(self.output))
        self.assertEqual(result.returncode, 1)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
