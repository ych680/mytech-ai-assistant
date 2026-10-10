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


def validate_dataset(dataset, strict_v1=False):
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
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET, help="UTF-8 JSON path (default: repository catalogue)")
    parser.add_argument("--strict-v1", action="store_true", help="enforce current v1 catalogue compatibility")
    args = parser.parse_args(argv)
    try:
        dataset = load_dataset(args.dataset)
    except json.JSONDecodeError as error:
        print(f"ERROR: JSON line {error.lineno}, column {error.colno}: {error.msg}", file=sys.stderr)
        return 1
    except (OSError, UnicodeError, ValueError, RecursionError) as error:
        print(f"ERROR: {args.dataset}: {error}", file=sys.stderr)
        return 1
    errors = validate_dataset(dataset, strict_v1=args.strict_v1)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    mode = " (strict-v1)" if args.strict_v1 else ""
    print(f"Valid: {len(dataset['products'])} products, {len(dataset['supported_categories'])} categories{mode}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
