"""Read-only MyTech catalogue validation using only the Python standard library.

Run with --strict-v1 to check compatibility with the current classroom catalogue.
Additional JSON fields are allowed; the documented fields remain required.
"""

import argparse
from datetime import date
import json
import math
from pathlib import Path
import re
import sys


DEFAULT_DATASET = Path(__file__).resolve().parents[1] / "mytech_v1_product_dataset.json"
V1_CATEGORIES = (
    "Laptop", "Desktop", "Smartphone", "Tablet", "Headphones",
    "Monitor", "Smartwatch", "Mouse", "Keyboard",
)
TIERS = ("Entry", "Mid-range", "Premium")
ROOT_STRINGS = ("dataset_name", "version", "snapshot_date", "currency", "price_note")
PRODUCT_STRINGS = ("id", "category", "product", "tier", "source")
TEST_DATASET = DEFAULT_DATASET.parent / "catalogue" / "mytech_products_v2_1_test.json"
ID_PREFIXES = dict(zip(V1_CATEGORIES, ("LAP", "DES", "PHO", "TAB", "AUD", "MON", "WAT", "MOU", "KEY")))
TEST_REVIEW_STATUSES = (
    "EXISTING BASELINE", "NEW CANDIDATE — provisional", "NEW CANDIDATE — unverified",
)


class _ObjectPairs(list):
    """Keep object pairs until paths are available for duplicate-key errors."""


def _reject_constant(value):
    raise ValueError(f"JSON: non-standard numeric constant {value} is not allowed")


def _unpack(value, path="$"):
    if isinstance(value, _ObjectPairs):
        result = {}
        for key, item in value:
            field = f"{path}[{json.dumps(key, ensure_ascii=True)}]"
            if key in result:
                raise ValueError(f"{field}: duplicate JSON key")
            result[key] = _unpack(item, field)
        return result
    if isinstance(value, list):
        return [_unpack(item, f"{path}[{index}]") for index, item in enumerate(value)]
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{path}: non-finite JSON number is not allowed")
    return value


def load_dataset(path):
    """Read UTF-8 JSON, rejecting duplicate keys and all non-finite numbers."""
    text = Path(path).read_text(encoding="utf-8")
    return _unpack(json.loads(
        text, object_pairs_hook=_ObjectPairs, parse_constant=_reject_constant,
    ))


def validate_dataset(dataset, strict_v1=False, test_v21=False):
    """Return field-specific errors without mutating the supplied object."""
    errors = []

    def nonempty_string(value, path):
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{path}: must be a non-empty string")
            return False
        return True

    def string_array(value, path):
        if not isinstance(value, list) or not value:
            errors.append(f"{path}: must be a non-empty array of strings")
            return False
        valid = True
        for index, item in enumerate(value):
            if not nonempty_string(item, f"{path}[{index}]"):
                valid = False
        return valid

    if not isinstance(dataset, dict):
        return ["$: must be an object"]
    for field in ROOT_STRINGS:
        nonempty_string(dataset.get(field), field)

    snapshot = dataset.get("snapshot_date")
    if isinstance(snapshot, str) and snapshot.strip():
        try:
            if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", snapshot):
                raise ValueError
            date.fromisoformat(snapshot)
        except ValueError:
            errors.append("snapshot_date: must be a real ISO calendar date (YYYY-MM-DD)")
    if dataset.get("currency") != "RMB":
        errors.append("currency: must be RMB because prices use price_rmb")

    categories = dataset.get("supported_categories")
    categories_valid = string_array(categories, "supported_categories")
    if categories_valid and len(set(categories)) != len(categories):
        errors.append("supported_categories: categories must be unique")

    products = dataset.get("products")
    if not isinstance(products, list) or not products:
        errors.append("products: must be a non-empty array of product objects")
    ids, names = {}, {}
    for index, product in enumerate(products if isinstance(products, list) else []):
        path = f"products[{index}]"
        if not isinstance(product, dict):
            errors.append(f"{path}: must be an object")
            continue
        for field in PRODUCT_STRINGS:
            nonempty_string(product.get(field), f"{path}.{field}")
        for field in ("review_status", "evidence_url", "price_evidence"):
            if field in product:
                nonempty_string(product[field], f"{path}.{field}")
        for field in ("main_usage", "key_features"):
            string_array(product.get(field), f"{path}.{field}")
        price = product.get("price_rmb")
        if type(price) is not int or price <= 0:
            errors.append(f"{path}.price_rmb: must be a positive integer (no booleans or floats)")
        category = product.get("category")
        if categories_valid and category not in categories:
            errors.append(f"{path}.category: must belong to supported_categories")
        if product.get("tier") not in TIERS:
            errors.append(f"{path}.tier: must be one of {', '.join(TIERS)}")
        for field, seen in (("id", ids), ("product", names)):
            value = product.get(field)
            if isinstance(value, str) and value.strip():
                if value in seen:
                    errors.append(f"{path}.{field}: duplicates products[{seen[value]}].{field}")
                else:
                    seen[value] = index

    if strict_v1:
        for field, expected in (("dataset_name", "MyTech v1 Product Dataset"), ("version", "1.0")):
            if dataset.get(field) != expected:
                errors.append(f"{field}: strict-v1 requires {expected!r}")
        if categories != list(V1_CATEGORIES):
            errors.append("supported_categories: strict-v1 requires the original nine categories in order")
        if not isinstance(products, list) or len(products) != 27:
            errors.append("products: strict-v1 requires exactly 27 products")
        for category in V1_CATEGORIES:
            members = [p for p in products if isinstance(p, dict) and p.get("category") == category] if isinstance(products, list) else []
            if len(members) != 3:
                errors.append(f"products[{category}]: strict-v1 requires exactly three products")
            if any(sum(p.get("tier") == tier for p in members) != 1 for tier in TIERS):
                errors.append(f"products[{category}].tier: strict-v1 requires one each of Entry, Mid-range, Premium")
    if test_v21:
        errors.extend(_validate_test_v21(dataset))
    return errors


def _validate_test_v21(dataset):
    """Opt-in TEST policy; no count limit and no changes to strict-v1 behavior."""
    errors = []
    if dataset.get("version") != "2.1-TEST":
        errors.append("version: test-v21 requires 2.1-TEST")
    if "TEST" not in str(dataset.get("dataset_name", "")):
        errors.append("dataset_name: test-v21 requires a TEST-only identity")
    if "TEST" not in str(dataset.get("price_note", "")):
        errors.append("price_note: test-v21 requires an explicit TEST disclosure")
    if dataset.get("supported_categories") != list(V1_CATEGORIES):
        errors.append("supported_categories: test-v21 requires the supported nine categories in order")
    products = dataset.get("products")
    if not isinstance(products, list):
        return errors
    baseline = {p["id"]: p for p in load_dataset(DEFAULT_DATASET)["products"]}
    found, names = set(), set()
    for index, product in enumerate(products):
        if not isinstance(product, dict):
            continue
        path = f"products[{index}]"
        identifier = product.get("id")
        prefix = ID_PREFIXES.get(str(product.get("category")))
        if not isinstance(identifier, str) or not re.fullmatch(rf"{prefix}-(?=[0-9]*[1-9])[0-9]{{3,9}}", identifier):
            errors.append(f"{path}.id: must use its category prefix and a positive numeric suffix")
        else:
            found.add(identifier)
        for field in PRODUCT_STRINGS:
            value = product.get(field)
            if isinstance(value, str) and value != value.strip():
                errors.append(f"{path}.{field}: test-v21 disallows surrounding whitespace")
        name = str(product.get("product", "")).strip().casefold()
        if name in names or name in ("__proto__", "constructor", "prototype", "tostring", "hasownproperty"):
            errors.append(f"{path}.product: ambiguous or reserved catalogue name")
        names.add(name)
        price = product.get("price_rmb")
        if type(price) is int and price > 2 ** 53 - 1:
            errors.append(f"{path}.price_rmb: must be exactly representable in JavaScript")
        for field in ("review_status", "evidence_url", "price_evidence"):
            if not isinstance(product.get(field), str) or not product[field].strip() or product[field] != product[field].strip():
                errors.append(f"{path}.{field}: test-v21 requires non-empty review evidence")
        status = product.get("review_status")
        if status not in TEST_REVIEW_STATUSES:
            errors.append(f"{path}.review_status: only baseline or provisional/unverified TEST candidates are allowed")
        original = baseline.get(identifier) if isinstance(identifier, str) else None
        if original is not None:
            for field, value in original.items():
                if product.get(field) != value:
                    errors.append(f"{path}.{field}: existing baseline facts must remain unchanged")
            if status != "EXISTING BASELINE":
                errors.append(f"{path}.review_status: original product must retain EXISTING BASELINE")
        elif status == "EXISTING BASELINE":
            errors.append(f"{path}.review_status: a new product cannot claim baseline approval")
    for identifier in sorted(baseline.keys() - found):
        errors.append(f"products: missing baseline product {identifier}")
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET, help="UTF-8 JSON path (default: repository catalogue)")
    parser.add_argument("--strict-v1", action="store_true", help="enforce current v1 catalogue compatibility")
    parser.add_argument("--test-v21", action="store_true", help="enforce TEST-only v2.1 identities, review evidence and baseline preservation")
    args = parser.parse_args(argv)
    try:
        dataset = load_dataset(args.dataset)
    except json.JSONDecodeError as error:
        print(f"ERROR: JSON line {error.lineno}, column {error.colno}: {error.msg}", file=sys.stderr)
        return 1
    except (OSError, UnicodeError, ValueError, RecursionError) as error:
        print(f"ERROR: {args.dataset}: {error}", file=sys.stderr)
        return 1
    errors = validate_dataset(dataset, strict_v1=args.strict_v1, test_v21=args.test_v21)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    mode = " (strict-v1)" if args.strict_v1 else ""
    print(f"Valid: {len(dataset['products'])} products, {len(dataset['supported_categories'])} categories{mode}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
