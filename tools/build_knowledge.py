"""Build new RAG Markdown or check existing MyTech knowledge without changing it.

Usage: python3 tools/build_knowledge.py --output new-knowledge.md
       python3 tools/build_knowledge.py --check knowledge/MyTech_Product_Knowledge_v1.md
Output creation is exclusive: existing files are never overwritten.
"""

import argparse
import html
from pathlib import Path
import sys

try:
    from .validate_products import DEFAULT_DATASET, load_dataset, validate_dataset
except ImportError:  # Direct script execution.
    from validate_products import DEFAULT_DATASET, load_dataset, validate_dataset


TITLE = "# MyTech Product Knowledge"
DISCLAIMER = "All prices are fixed classroom reference prices, not live retailer quotes."
V1_NOTE = (
    "Fixed reference prices for the classroom prototype. They are not live retailer quotes. "
    "MyTech should describe them as reference prices."
)
INTRO = (
    "Each product record below is self-contained so that product name, category, "
    "reference price, usage, features, and source remain together during retrieval."
)


def _validated(dataset):
    errors = validate_dataset(dataset)
    if errors:
        raise ValueError("\n".join(errors))


def _escape(value):
    """Encode Markdown syntax and line controls, preserving exact decoded text."""
    special = "\\`*_[]#|~\n\r\t\v\f\x1c\x1d\x1e\x85\u2028\u2029"
    return "".join(
        f"&#{ord(char)};" if char in special else html.escape(char, quote=False)
        for char in value
    )


def _metadata(dataset):
    return {
        "Dataset name": dataset["dataset_name"],
        "Version": dataset["version"],
        "Dataset snapshot": dataset["snapshot_date"],
        "Currency": dataset["currency"],
        "Price note": dataset["price_note"],
        "Price disclaimer": DISCLAIMER,
        "Supported categories": dataset["supported_categories"],
    }


def _record(product, currency):
    return {
        "Product ID": product["id"],
        "Category": product["category"],
        "Product": product["product"],
        "Reference Price": f"{currency} {product['price_rmb']}",
        "Tier": product["tier"],
        "Main Usage": product["main_usage"],
        "Key Features": product["key_features"],
        "Source": product["source"],
    }


def _field_lines(fields):
    lines = []
    for label, value in fields.items():
        if isinstance(value, list):
            lines.append(f"{label}:")
            lines.extend(f"  - {_escape(item)}" for item in value)
        else:
            lines.append(f"{label}: {_escape(value)}")
    return lines


def render_knowledge(dataset):
    """Validate then render deterministic Markdown, with LF line endings."""
    _validated(dataset)
    lines = [TITLE, "", *_field_lines(_metadata(dataset)), "", INTRO, ""]
    for product in dataset["products"]:
        heading = f"{product['id']} — {product['product']}"
        lines.extend([
            f"## Product Record: {_escape(heading)}",
            *_field_lines(_record(product, dataset["currency"])), "", "---", "",
        ])
    return "\n".join(lines)


def _parse_markdown(text):
    """Parse the supported labelled-record formats; fail on unrecognized content."""
    metadata, records = {}, []
    target = metadata
    title = None
    list_field = None
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        if title is None:
            if not line.startswith("# "):
                raise ValueError(f"Markdown line {number}: expected document title")
            title = line
            continue
        if line.startswith("## Product Record: "):
            heading = html.unescape(line[len("## Product Record: "):])
            target = {}
            records.append((heading, target))
            list_field = None
            continue
        if line == "---" and records:
            list_field = None
            continue
        if line == INTRO and not records:
            list_field = None
            continue
        if line.startswith("  - ") and list_field is not None:
            target[list_field].append(html.unescape(line[4:]))
            continue
        label, separator, value = line.partition(":")
        allowed = _METADATA_LABELS if not records else _RECORD_LABELS
        if not separator or label not in allowed or (value and not value.startswith(" ")):
            raise ValueError(f"Markdown line {number}: malformed or unexpected content")
        if label in target:
            raise ValueError(f"Markdown line {number}: duplicate field {label}")
        list_field = None
        if value == "" and label in _LIST_LABELS:
            target[label] = []
            list_field = label
        else:
            target[label] = html.unescape(value[1:])
    if title is None:
        raise ValueError("Markdown: missing document title")
    return title, metadata, records


_METADATA_LABELS = {
    "Dataset name", "Version", "Dataset snapshot", "Currency", "Price note",
    "Price disclaimer", "Supported categories",
}
_RECORD_LABELS = {
    "Product ID", "Category", "Product", "Reference Price", "Tier", "Main Usage",
    "Key Features", "Source",
}
_LIST_LABELS = {"Supported categories", "Main Usage", "Key Features"}


def check_knowledge(dataset, text):
    """Check every field, heading and record position, allowing known legacy prose."""
    _validated(dataset)
    try:
        title, metadata, records = _parse_markdown(text)
    except ValueError as error:
        return [str(error)]
    errors = []
    legacy = (
        title == "# MyTech Product Knowledge v1"
        and dataset["dataset_name"] == "MyTech v1 Product Dataset"
        and dataset["version"] == "1.0"
    )
    if title != TITLE and not legacy:
        errors.append("title: does not match the supported document identity/version")
    expected_meta = _metadata(dataset)
    if legacy:
        for label in ("Dataset name", "Version", "Price disclaimer"):
            if label not in metadata:
                expected_meta.pop(label)
        if dataset["price_note"] == V1_NOTE and metadata.get("Price note") == DISCLAIMER:
            expected_meta["Price note"] = DISCLAIMER

    def compare(expected, actual, path):
        for label, value in expected.items():
            found = actual.get(label)
            if legacy and isinstance(value, list) and isinstance(found, str):
                # Legacy inline lists: compare the full serialization, never split
                # descriptions on punctuation (e.g. "8,000 DPI sensor").
                delimiter = "; " if label == "Key Features" else ", "
                value = delimiter.join(value)
                if label == "Supported categories":
                    value += "."
            if found != value:
                errors.append(f"{path}.{label}: missing or differs from dataset")

    compare(expected_meta, metadata, "metadata")
    if len(records) != len(dataset["products"]):
        errors.append(f"records: expected {len(dataset['products'])}, found {len(records)}")
    for index, (product, (heading, fields)) in enumerate(zip(dataset["products"], records)):
        path = f"records[{index}]"
        if heading != f"{product['id']} — {product['product']}":
            errors.append(f"{path}.heading: identity or order differs from dataset")
        compare(_record(product, dataset["currency"]), fields, path)
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--output", type=Path, help="create a new UTF-8 Markdown file exclusively")
    mode.add_argument("--check", type=Path, help="check existing Markdown without writing")
    args = parser.parse_args(argv)
    try:
        dataset = load_dataset(args.dataset)
        _validated(dataset)
        if args.check is not None:
            errors = check_knowledge(dataset, args.check.read_text(encoding="utf-8"))
            if errors:
                raise ValueError("\n".join(errors))
            print(f"Consistent: {len(dataset['products'])} product records.")
        else:
            payload = render_knowledge(dataset).encode("utf-8")
            with args.output.open("xb") as output:
                output.write(payload)
            print(f"Created {args.output}: {len(dataset['products'])} product records.")
    except (OSError, UnicodeError, ValueError, RecursionError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
