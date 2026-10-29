"""Prepare a separate private no-match hotfix from the verified upgraded school export.

The historical PR18 template/packages stay frozen. Only completionNegativeClaim
is replaced, preserving every other source byte, including the export's BOM.
"""

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

try:
    from . import build_v21_school_validator_candidate as alignment
except ImportError:
    import build_v21_school_validator_candidate as alignment


ROOT = alignment.ROOT
SOURCE_SHA256 = "c7389bf0896b81216604b3c0dde7e79a8d8ed825ffc43e925cb1fe9605d54b84"
APPROVED_SHA256 = "d1899aa9026e0ab275e61fd1c4576842438d69d4d05a8fc52939aa2dd9ebc325"
APPROVED = alignment.OUTPUT_DIRECTORY / alignment.CANDIDATE
TEMPLATE = ROOT / "tools/templates/v21_completion_negative_claim.js"
LEGACY_TEMPLATE = ROOT / "tools/templates/v21_completion_validation.js"
CANDIDATE = "mytech-v21-school-validator-nomatch-fix.private-export.json"
REPORT = "nomatch-preservation.json"
ALLOWED_DIFF = [{"op": "replace", "path": "/nodes/11/inputs/2/value"}]
START = "function completionNegativeClaim(answer, category) {"
END = "\n\nfunction completionCanonicalNoMatch("


def split_helper(code):
    if code.count(START) != 1 or code.count(END) != 1:
        raise ValueError("Negative-claim helper boundary drift")
    start = code.index(START)
    end = code.index(END, start)
    return code[:start], code[start:end], code[end:]


def patch_candidate(source_raw, template):
    """Pure, narrowly bounded patch; source selection is verified by prepare_outputs."""
    source = alignment.inspect_public_json(source_raw)
    validator = alignment.node(source, alignment.sync.VALIDATOR_ID)
    if (len(source["nodes"]) != 20 or len(source["edges"]) != 18
            or source["nodes"][11] is not validator
            or validator["inputs"][2]["key"] != "code"):
        raise ValueError("Unexpected school validator position or graph")
    code = alignment.field(source, validator["nodeId"], "code")["value"]
    prefix, old_helper, suffix = split_helper(code)
    if old_helper != split_helper(LEGACY_TEMPLATE.read_text(encoding="utf-8"))[1]:
        raise ValueError("Source does not contain the reviewed pre-hotfix helper")
    helper = template.rstrip("\n")
    if not helper.startswith(START) or not helper.endswith("\n}") or helper == old_helper:
        raise ValueError("Invalid or unchanged hotfix helper")
    new_code = prefix + helper + suffix
    old_literal = json.dumps(code, ensure_ascii=False).encode("utf-8")
    new_literal = json.dumps(new_code, ensure_ascii=False).encode("utf-8")
    if source_raw.count(old_literal) != 1:
        raise ValueError("Cannot uniquely patch the original encoded validator")
    raw = source_raw.replace(old_literal, new_literal, 1)
    candidate = alignment.inspect_public_json(raw)
    if alignment.semantic_diff(source, candidate) != ALLOWED_DIFF:
        raise ValueError("Hotfix exceeds its one-field boundary")
    restored = deepcopy(candidate)
    alignment.field(restored, validator["nodeId"], "code")["value"] = code
    if restored != source or alignment.sync.check_workflow_inputs(candidate):
        raise ValueError("School architecture or references changed")
    return raw


def prepare_outputs(source_raw, original_raw, approved_raw, reference_raw):
    for raw, expected in [(source_raw, SOURCE_SHA256), (original_raw, alignment.SCHOOL_SHA256),
                          (approved_raw, APPROVED_SHA256),
                          (reference_raw, alignment.SOURCE_HASHES[alignment.REFERENCE])]:
        if alignment.digest(raw) != expected:
            raise ValueError("Unverified source fingerprint; no output generated")
    source, original, approved, reference = [alignment.inspect_public_json(raw)
                                            for raw in (source_raw, original_raw, approved_raw, reference_raw)]
    if source != approved:
        raise ValueError("Latest export differs from the approved school-derived candidate")
    changes = alignment.validate_candidate(original, source, reference)
    template = TEMPLATE.read_text(encoding="utf-8")
    raw = patch_candidate(source_raw, template)
    report = {
        "status": "OFFLINE_HOTFIX_REQUIRES_INDEPENDENT_REVIEW",
        "base_commit": alignment.BASE_COMMIT,
        "source_school_sha256": alignment.digest(source_raw),
        "source_description": "Latest explicitly selected upgraded school export; semantically identical to approved candidate",
        "original_school_sha256": alignment.digest(original_raw),
        "previous_candidate_sha256": alignment.digest(approved_raw),
        "source_alignment_diff_from_original": changes,
        "candidate": CANDIDATE, "candidate_sha256": alignment.digest(raw),
        "semantic_diff": ALLOWED_DIFF,
        "validator_change": "completionNegativeClaim only; optional single gaming adjective before Laptop",
        "sources_sha256": {p.relative_to(ROOT).as_posix(): alignment.digest(p.read_bytes()) for p in
                           [Path(__file__), TEMPLATE, LEGACY_TEMPLATE,
                            ROOT / "tests/school-validator-nomatch.test.mjs",
                            ROOT / "tests/test_v21_school_nomatch_fix.py",
                            ROOT / "tests/usage-repair.test.mjs", ROOT / "tests/completion-repair.test.mjs",
                            ROOT / "tests/quick-prompt-demo.test.mjs"]},
        "preservation": "All bytes outside the encoded validator unchanged; all code outside the helper unchanged",
        "nodes": 20, "edges": 18, "products": 54, "categories": 9,
        "live_calls": 0, "imported": False, "published": False,
        "privacy": "School metadata retained privately; no metadata values included in this report",
        "limitations": ["Native import and runtime compatibility unverified",
                        "KB selections and published revision unverified",
                        "Existing diagnostic-only grounding and free-text validation limits unchanged",
                        "Existing q-field evidence-recognition issue deliberately unchanged",
                        "Earlier request-state writes are not transactionally rolled back"]}
    return {CANDIDATE: raw, REPORT: (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="Explicit latest upgraded school JSON")
    parser.add_argument("--original", required=True, type=Path, help="Original school JSON for alignment verification")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        paths = [args.source, args.original, APPROVED, ROOT / alignment.REFERENCE]
        for path in paths:
            if path.suffix.lower() != ".json" or any(p.startswith(".env") for p in path.parts):
                raise ValueError("Only explicitly selected JSON sources are allowed")
            alignment.reject_symlinks(path)
        outputs = prepare_outputs(*(path.read_bytes() for path in paths))
        alignment.write_outputs(outputs, alignment.OUTPUT_DIRECTORY, check=args.check)
        print("No-match hotfix " + ("consistent" if args.check else "prepared privately") + "; one helper/one field; no live calls")
        print("Source SHA-256: " + SOURCE_SHA256)
        print("Candidate SHA-256: " + alignment.digest(outputs[CANDIDATE]))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print("No-match hotfix failed: " + type(error).__name__ + "; source/contract check failed; values withheld", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
