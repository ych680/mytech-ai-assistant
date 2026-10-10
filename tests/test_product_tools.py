"""Offline validator tests; all writable fixtures live in temporary directories."""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "validate_products.py"
SPEC = importlib.util.spec_from_file_location("validate_products", SCRIPT)
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class ProductValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = validator.DEFAULT_DATASET.read_bytes()
        cls.catalogue = json.loads(cls.original)

    def setUp(self):
        self.dataset = deepcopy(self.catalogue)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.fixture = Path(self.temp.name) / "products.json"

    def run_cli(self, text=None, strict=False, default=False):
        args = [sys.executable, "-B", str(SCRIPT)]
        if not default:
            self.fixture.write_text(text if text is not None else json.dumps(self.dataset), encoding="utf-8")
            before = self.fixture.read_bytes()
            args.extend(["--dataset", str(self.fixture)])
        if strict:
            args.append("--strict-v1")
        result = subprocess.run(args, cwd=self.temp.name, capture_output=True, text=True, check=False)
        if not default:
            self.assertEqual(before, self.fixture.read_bytes())
            self.assertEqual(list(Path(self.temp.name).iterdir()), [self.fixture])
        self.assertEqual(self.original, validator.DEFAULT_DATASET.read_bytes())
        return result

    def assert_invalid(self, dataset, field, strict=False):
        errors = validator.validate_dataset(dataset, strict_v1=strict)
        self.assertTrue(any(field in error for error in errors), errors)

    def test_current_catalogue_and_default_path_from_other_directory(self):
        for strict in (False, True):
            with self.subTest(strict=strict):
                self.assertEqual(validator.validate_dataset(self.dataset, strict), [])
                result = self.run_cli(strict=strict, default=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("27 products, 9 categories", result.stdout)

    def test_missing_and_wrongly_typed_root_fields(self):
        for field in self.catalogue:
            for value in (None, 42, {}):
                with self.subTest(field=field, value=value):
                    data = deepcopy(self.catalogue)
                    data[field] = value
                    self.assert_invalid(data, field)
            data = deepcopy(self.catalogue)
            del data[field]
            self.assert_invalid(data, field)
        for value in (None, [], "dataset", 1):
            self.assert_invalid(value, "$")

    def test_missing_and_wrongly_typed_product_fields(self):
        for field in self.catalogue["products"][0]:
            data = deepcopy(self.catalogue)
            del data["products"][0][field]
            self.assert_invalid(data, f"products[0].{field}")
            for value in (None, {}):
                data = deepcopy(self.catalogue)
                data["products"][0][field] = value
                self.assert_invalid(data, f"products[0].{field}")
        self.dataset["products"][0] = []
        self.assert_invalid(self.dataset, "products[0]")

    def test_empty_strings_and_arrays(self):
        for field in validator.ROOT_STRINGS:
            for value in ("", " \n\t"):
                data = deepcopy(self.catalogue)
                data[field] = value
                self.assert_invalid(data, field)
        for field in validator.PRODUCT_STRINGS:
            data = deepcopy(self.catalogue)
            data["products"][0][field] = " \n"
            self.assert_invalid(data, f"products[0].{field}")
        for field in ("supported_categories", "products"):
            data = deepcopy(self.catalogue)
            data[field] = []
            self.assert_invalid(data, field)
        for field in ("main_usage", "key_features"):
            for value in ([], [""], [" \t"], [42], [None], "Study"):
                data = deepcopy(self.catalogue)
                data["products"][0][field] = value
                self.assert_invalid(data, f"products[0].{field}")
        for value in ([""], [42], ["Laptop", "Laptop"]):
            self.dataset["supported_categories"] = value
            self.assert_invalid(self.dataset, "supported_categories")

    def test_duplicate_ids_and_names(self):
        for field in ("id", "product"):
            data = deepcopy(self.catalogue)
            data["products"][1][field] = data["products"][0][field]
            self.assert_invalid(data, f"products[1].{field}")

    def test_duplicate_json_keys_at_every_depth(self):
        cases = (
            ('{"version":"1.0","version":"2.0"}', '$["version"]'),
            ('{"products":[{"id":"a","id":"b"}]}', '$["products"][0]["id"]'),
            ('{"extra":{"nested":{"x":1,"x":2}}}', '$["extra"]["nested"]["x"]'),
            ('{"id":1,"\\u0069d":2}', '$["id"]'),
        )
        for text, path in cases:
            with self.subTest(text=text):
                result = self.run_cli(text)
                self.assertEqual(result.returncode, 1)
                self.assertIn(path, result.stderr)
                self.assertIn("duplicate JSON key", result.stderr)

    def test_invalid_categories_and_tiers(self):
        for field, value in (("category", "Camera"), ("category", "laptop"), ("tier", "Luxury"), ("tier", "entry")):
            data = deepcopy(self.catalogue)
            data["products"][0][field] = value
            self.assert_invalid(data, f"products[0].{field}")
        self.dataset["currency"] = "USD"
        self.assert_invalid(self.dataset, "currency")

    def test_real_iso_calendar_dates(self):
        for value in ("2026-02-29", "2026-04-31", "2026-13-01", "0000-01-01", "20260912", "2026-9-12", "2026-09-12T00:00:00", " 2026-09-12"):
            self.dataset["snapshot_date"] = value
            self.assert_invalid(self.dataset, "snapshot_date")
        self.dataset["snapshot_date"] = "2024-02-29"
        self.assertEqual(validator.validate_dataset(self.dataset), [])

    def test_invalid_prices(self):
        for value in (0, -1, "5799", True, False, 5799.0, 1.5, float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                self.dataset["products"][0]["price_rmb"] = value
                self.assert_invalid(self.dataset, "products[0].price_rmb")
                result = self.run_cli()
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
        self.dataset["products"][0]["price_rmb"] = 1
        self.assertEqual(validator.validate_dataset(self.dataset), [])

    def test_nonstandard_constants_rejected_even_in_extra_fields(self):
        for token in ("NaN", "Infinity", "-Infinity"):
            result = self.run_cli('{"extra":' + token + '}')
            self.assertEqual(result.returncode, 1)
            self.assertIn(f"non-standard numeric constant {token}", result.stderr)

    def test_overflowing_exponents_rejected_at_every_depth(self):
        for token in ("1e400", "-1e400"):
            cases = (
                (token, "$"),
                ('{"extra":' + token + '}', '$["extra"]'),
                ('{"extra":{"values":[0,' + token + ']}}', '$["extra"]["values"][1]'),
                ('{"products":[{"price_rmb":' + token + '}]}', '$["products"][0]["price_rmb"]'),
            )
            for text, path in cases:
                with self.subTest(token=token, path=path):
                    result = self.run_cli(text)
                    self.assertEqual(result.returncode, 1)
                    self.assertEqual(result.stdout, "")
                    self.assertIn(f"{path}: non-finite JSON number", result.stderr)
                    with self.assertRaisesRegex(ValueError, "non-finite JSON number"):
                        validator.load_dataset(self.fixture)

    def test_finite_json_numbers_preserve_existing_behavior(self):
        # Arbitrarily large integers must not be converted to floats for this check.
        self.dataset["extra"] = {"values": [1e308, -1e308, 1.5, 0, 10 ** 400]}
        for strict in (False, True):
            result = self.run_cli(strict=strict)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(validator.load_dataset(self.fixture), self.dataset)
        self.dataset["products"][0]["price_rmb"] = 5799.0
        result = self.run_cli()
        self.assertEqual(result.returncode, 1)
        self.assertIn("products[0].price_rmb: must be a positive integer", result.stderr)

    def test_strict_v1_compatibility_failures(self):
        cases = []
        for field, value in (("dataset_name", "Other"), ("version", "2.0"), ("supported_categories", list(reversed(validator.V1_CATEGORIES)))):
            data = deepcopy(self.catalogue)
            data[field] = value
            cases.append((data, field))
        data = deepcopy(self.catalogue)
        data["products"].pop()
        cases.append((data, "exactly 27"))
        data = deepcopy(self.catalogue)
        data["products"][0]["category"] = "Desktop"
        cases.append((data, "exactly three"))
        data = deepcopy(self.catalogue)
        data["products"][0]["tier"] = "Premium"
        cases.append((data, "one each"))
        for data, field in cases:
            with self.subTest(field=field):
                self.assertEqual(validator.validate_dataset(data), [])
                self.assert_invalid(data, field, strict=True)
                self.dataset = data
                result = self.run_cli(strict=True)
                self.assertEqual(result.returncode, 1)
                self.assertIn("strict-v1", result.stderr)

    def test_validation_does_not_mutate_input(self):
        for strict in (False, True):
            before = deepcopy(self.dataset)
            validator.validate_dataset(self.dataset, strict)
            self.assertEqual(self.dataset, before)
            result = self.run_cli(strict=strict)
            self.assertEqual(result.returncode, 0, result.stderr)
        self.dataset["products"][0]["source"] = ""
        before = deepcopy(self.dataset)
        validator.validate_dataset(self.dataset, True)
        self.assertEqual(self.dataset, before)
        self.assertEqual(self.run_cli().returncode, 1)

    def test_malformed_json_encoding_and_missing_file(self):
        result = self.run_cli('{"products":')
        self.assertEqual(result.returncode, 1)
        self.assertIn("JSON line 1, column", result.stderr)
        self.fixture.write_bytes(b"\xff")
        before = self.fixture.read_bytes()
        for path in (self.fixture, Path(self.temp.name) / "missing.json"):
            result = subprocess.run([sys.executable, "-B", str(SCRIPT), "--dataset", str(path)], capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 1)
            self.assertIn("ERROR:", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(self.fixture.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
