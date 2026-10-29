"""Build a private, school-derived validator candidate; never import or publish it.

Only four reviewed JSON locations may differ. Existing outputs are never
overwritten. The raw school metadata stays in ignored private/exports/.
"""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

try:
    from . import sync_catalogue as sync
    from .check_workflow_registry import inspect_public_json
except ImportError:
    import sync_catalogue as sync
    from check_workflow_registry import inspect_public_json


ROOT = Path(__file__).resolve().parents[1]
BASE_COMMIT = "4745b7a792036785d54a2210b62a0b9100bb8779"
SCHOOL_SHA256 = "31a3d18d2fcb2ee3c9b1fb215b8b5ce96003cc1f76ca57022d3a40361b8fc738"
REFERENCE = "generated/v21_quick_prompt_demo/workflow-completion-repair.json"
CATALOGUE = "generated/v21_quick_prompt_demo/local/catalogue.json"
OUTPUT_DIRECTORY = ROOT / "private/exports/v21_school_validator_alignment"
CANDIDATE = "mytech-v21-school-validator-alignment.private-export.json"
SOURCE_HASHES = {
    REFERENCE: "108bd7340b37bbfdce5017547fd624b99ec771ee9c62a98304654fcaa02ec5e0",
    "generated/v21_quick_prompt_demo/local/mytech-fastgpt-workflow-v2_1-TEST.json": "108bd7340b37bbfdce5017547fd624b99ec771ee9c62a98304654fcaa02ec5e0",
    CATALOGUE: "0e99d7df0238b67d321f729a6ecbe87ed35f16aec1c6e923f2d00e3d69bf85ac",
    "generated/v21_quick_prompt_demo/local/MyTech_Product_Knowledge_v2_1_TEST.md": "96bca468f19799fca9a17adfce1a37e2fa6fe8e099835f47a3b12c59931af4f4",
    "tools/build_v21_completion_repair.py": "0d784114f0261f1aa7a98d3ca7268f3f685a8f48a9abaa62e795405f42d31094",
    "tools/templates/v21_usage_validation.js": "704d5101d6ae8a9881dbfebe94ad02a88da84f40867f991abac2dd01a380e4bd",
    "tools/templates/v21_completion_validation.js": "492979de42450649aa2b24f6fdd612d3ac6ccd56e121d9e48a1e946bc5e57cac",
    "tests/usage-repair.test.mjs": "16b6b6622a904738c660e0133a350059f477a8c698641fdbc0b0e3d457553279",
    "tests/completion-repair.test.mjs": "f06dc36052f115a3ea3c5118d4e3b84e810617f5bed2d5f4e83b99f9a7f13102",
    "tests/quick-prompt-demo.test.mjs": "f20a0f2820dceb114127a8ac9c27c61124140ca9f5f03c7c7c7894f7ec086389",
    "mytech_v2_1_test_adapter.mjs": "24fd37ee558070b0856a1daf1d5d0abade923b58982712754bd1f4dea2b6d71f",
    "mytech_v2_1_test_server.mjs": "b6ca1af6c82358f641bc49f9b0d00706725c1d6721ff17b606cc1645f30207b7",
    "tests/helpers/v21-repair-frontend.mjs": "70599dbdcd0a8c87596ee48434b0404c460d210056d8c6409256248e2324a7dc",
}
ALLOWED_PATHS = [
    "/nodes/11/inputs/2/value",
    "/nodes/11/inputs/7",
    "/nodes/11/outputs/11",
    "/nodes/14/inputs/0/value",
]
AI_PROMPTS = [("etNrwEXVwr5sySpK", "description"),
              ("ikIzMK483vihRths", "systemPrompt"),
              ("pskHz4kajjJnBWwG", "systemPrompt")]


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def semantic_diff(left, right, path=""):
    """Report replacements and appended array elements at their precise paths."""
    if type(left) is not type(right):
        return [{"op": "replace", "path": path}]
    if isinstance(left, dict):
        changes = []
        for key in sorted(set(left) | set(right)):
            child = path + "/" + key.replace("~", "~0").replace("/", "~1")
            if key not in left:
                changes.append({"op": "add", "path": child})
            elif key not in right:
                changes.append({"op": "remove", "path": child})
            else:
                changes.extend(semantic_diff(left[key], right[key], child))
        return changes
    if isinstance(left, list):
        changes = []
        for index in range(max(len(left), len(right))):
            child = path + "/" + str(index)
            if index >= len(left):
                changes.append({"op": "add", "path": child})
            elif index >= len(right):
                changes.append({"op": "remove", "path": child})
            else:
                changes.extend(semantic_diff(left[index], right[index], child))
        return changes
    return [] if left == right else [{"op": "replace", "path": path}]


def node(workflow, node_id):
    matches = [n for n in workflow["nodes"] if n["nodeId"] == node_id]
    if len(matches) != 1:
        raise ValueError("Missing or duplicate required node")
    return matches[0]


def field(workflow, node_id, key):
    matches = [i for i in node(workflow, node_id)["inputs"] if i["key"] == key]
    if len(matches) != 1:
        raise ValueError("Missing or duplicate required input")
    return matches[0]


def catalogue(workflow):
    code = field(workflow, sync.VALIDATOR_ID, "code")["value"]
    marker = "const PRODUCT_CATALOG = "
    if code.count(marker) != 1:
        raise ValueError("Unexpected embedded catalogue")
    return json.JSONDecoder().raw_decode(code.split(marker, 1)[1])[0]


def validate_candidate(school, candidate, reference):
    expected = [{"op": op, "path": path} for op, path in
                zip(["replace", "add", "add", "replace"], ALLOWED_PATHS)]
    changes = semantic_diff(school, candidate)
    if changes != expected:
        raise ValueError("Candidate exceeds the exact four-change boundary")
    if len(school["nodes"]) != 20 or len(school["edges"]) != 18:
        raise ValueError("Unexpected school graph size")
    restored = deepcopy(candidate)
    restored["nodes"][11]["inputs"][2]["value"] = school["nodes"][11]["inputs"][2]["value"]
    restored["nodes"][11]["inputs"].pop()
    restored["nodes"][11]["outputs"].pop()
    restored["nodes"][14]["inputs"][0]["value"] = school["nodes"][14]["inputs"][0]["value"]
    if restored != school:
        raise ValueError("Unapproved school configuration change")
    for node_id, key in AI_PROMPTS:
        if field(candidate, node_id, "model")["value"] != "deepseek/deepseek-v4.1-flash":
            raise ValueError("School DeepSeek model was not preserved")
        if field(candidate, node_id, key)["value"].encode() != field(school, node_id, key)["value"].encode():
            raise ValueError("School prompt changed")
    validator = node(candidate, sync.VALIDATOR_ID)
    reviewed = node(reference, sync.VALIDATOR_ID)
    if validator["inputs"][2] != reviewed["inputs"][2] or validator["inputs"][-1] != reviewed["inputs"][-1] or validator["outputs"][-1] != reviewed["outputs"][-1]:
        raise ValueError("Reviewed validator code or mapping differs")
    if field(candidate, "zh9L8VeY9vKm3WnU", "text") != field(reference, "zh9L8VeY9vKm3WnU", "text"):
        raise ValueError("Reviewed fallback differs")
    if catalogue(candidate) != catalogue(school) or sync.check_workflow_inputs(candidate):
        raise ValueError("Catalogue or native references differ")
    return changes


def align_workflow(school, reference):
    """Pure transformation; callers must verify source bytes before using it."""
    validator = node(school, sync.VALIDATOR_ID)
    fallback = node(school, "zh9L8VeY9vKm3WnU")
    if school["nodes"][11] is not validator or school["nodes"][14] is not fallback:
        raise ValueError("Approved node indexes do not match IDs")
    if len(validator["inputs"]) != 7 or len(validator["outputs"]) != 11 or validator["inputs"][2]["key"] != "code" or fallback["inputs"][0]["key"] != "text":
        raise ValueError("Unexpected indexes or occupied append slots")
    if any(i["key"] == "retrieved_evidence" for i in validator["inputs"]) or any(o["key"] == "completion_status" or o.get("id") == "phase3CompletionStatus" for o in validator["outputs"]):
        raise ValueError("Candidate mappings already exist")
    reviewed = node(reference, sync.VALIDATOR_ID)
    if len(reviewed["inputs"]) != 8 or reviewed["inputs"][7]["key"] != "retrieved_evidence" or len(reviewed["outputs"]) != 12 or reviewed["outputs"][11]["key"] != "completion_status":
        raise ValueError("Unexpected reviewed mappings")
    result = deepcopy(school)
    result["nodes"][11]["inputs"][2]["value"] = reviewed["inputs"][2]["value"]
    result["nodes"][11]["inputs"].append(deepcopy(reviewed["inputs"][7]))
    result["nodes"][11]["outputs"].append(deepcopy(reviewed["outputs"][11]))
    result["nodes"][14]["inputs"][0]["value"] = field(reference, "zh9L8VeY9vKm3WnU", "text")["value"]
    validate_candidate(school, result, reference)
    return result


def render_outputs(school_raw, root=ROOT):
    if digest(school_raw) != SCHOOL_SHA256:
        raise ValueError("School SHA-256 mismatch; no output generated")
    sources = {}
    for name, expected in SOURCE_HASHES.items():
        path = Path(root) / name
        reject_symlinks(path)
        raw = path.read_bytes()
        if digest(raw) != expected:
            raise ValueError("Pinned repository source mismatch: " + name)
        sources[name] = raw
    school = inspect_public_json(school_raw)
    reference = inspect_public_json(sources[REFERENCE])
    master = inspect_public_json(sources[CATALOGUE])
    if len(master["products"]) != 54 or len(master["supported_categories"]) != 9 or catalogue(school) != sync.catalogue_projection(master):
        raise ValueError("School catalogue differs from the reviewed Master")
    candidate = align_workflow(school, reference)
    raw = (json.dumps(candidate, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    # Inspection rejects credential patterns; school metadata is preserved privately.
    inspect_public_json(raw)
    prompts = {node_id: {"characters": len(field(school, node_id, key)["value"]),
                         "sha256": digest(field(school, node_id, key)["value"].encode("utf-8")),
                         "model": field(school, node_id, "model")["value"],
                         "history": field(school, node_id, "history")["value"],
                         "complete_ai_node_sha256": digest(canonical(node(school, node_id)))}
               for node_id, key in AI_PROMPTS}
    report = {
        "status": "OFFLINE_CANDIDATE_REQUIRES_INDEPENDENT_PRE_IMPORT_REVIEW",
        "base_commit": BASE_COMMIT, "candidate": CANDIDATE,
        "source_school_sha256": digest(school_raw), "candidate_sha256": digest(raw),
        "reference_sha256": digest(sources[REFERENCE]), "sources_sha256": SOURCE_HASHES,
        "generator_sha256": digest(Path(__file__).read_bytes()),
        "semantic_diff": validate_candidate(school, candidate, reference),
        "preserved": {"nodes": 20, "edges": 18, "products": 54, "categories": 9,
                      "school_semantic_sha256": digest(canonical(school)),
                      "edges_sha256": digest(canonical(school["edges"])),
                      "chat_config_including_private_metadata_sha256": digest(canonical(school["chatConfig"])),
                      "embedded_catalogue_sha256": digest(canonical(catalogue(school))),
                      "retrieval_node_sha256": digest(canonical(node(school, sync.RETRIEVAL_ID))),
                      "ai_nodes": prompts,
                      "all_other_json_values_identical": True},
        "privacy": "School export metadata retained. Ignored local artifact; do not upload without a separate metadata review.",
        "live_calls": 0, "imported": False, "published": False,
        "limitations": ["Published revision and runtime KB binding unverified.",
                        "Evidence diagnostics are not a strict grounding gate.",
                        "Validation failure preserves anchors, not every earlier request-state write.",
                        "Native FastGPT execution and remote cancellation semantics require separately authorized acceptance."]}
    lines = ["# School-derived validator alignment preservation report", "",
             "Status: offline candidate; independent pre-import review required.", "",
             "The downloaded school backup and every existing repository artifact remain unchanged.",
             "School export metadata is retained privately; do not upload this package without review.", "",
             "School SHA-256: `" + digest(school_raw) + "`",
             "Candidate SHA-256: `" + digest(raw) + "`", "",
             "Exactly four semantic changes:", ""]
    lines.extend("- " + c["op"] + " `" + c["path"] + "`" for c in report["semantic_diff"])
    lines.extend(["", "Preserved: 20 existing nodes, 18 edges, all three school DeepSeek models and prompts,",
                  "history/parameters, all other code, routing/state, school metadata, 54-product catalogue,",
                  "nine categories and retrieval settings. Detailed fingerprints are in preservation.json.", "",
                  "No frontend, launcher, adapter, AIEP or API-binding change is included.", "",
                  "Validation command (candidate-specific; existing suites replayed in memory):", "",
                  "```sh", "MYTECH_SCHOOL_CANDIDATE=private/exports/v21_school_validator_alignment/" + CANDIDATE
                  + " node --test tests/school-validator-candidate.test.mjs",
                  "```", "", "Deterministic check: python -B tools/build_v21_school_validator_candidate.py --check", "",
                  "Limitations:", ""])
    lines.extend("- " + item for item in report["limitations"])
    return {CANDIDATE: raw,
            "preservation.json": (json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode(),
            "preservation.md": ("\n".join(lines) + "\n").encode()}


def reject_symlinks(path):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("Symlink path refused")


def write_outputs(outputs, directory, check=False):
    directory = Path(directory)
    reject_symlinks(directory)
    # Preflight every target before any write; never replace existing bytes.
    for name, raw in outputs.items():
        path = directory / name
        reject_symlinks(path)
        if path.exists() and path.read_bytes() != raw:
            raise ValueError("Existing output differs; refusing overwrite")
        if check and not path.is_file():
            raise ValueError("Missing candidate output")
    if not check:
        directory.mkdir(parents=True, exist_ok=True)
        for name, raw in outputs.items():
            path = directory / name
            if not path.exists():
                with path.open("xb") as stream:
                    stream.write(raw)


def verify_git_baseline(root=ROOT):
    def git(*args):
        return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True).stdout
    if git("rev-parse", "HEAD").decode().strip() != BASE_COMMIT:
        raise ValueError("Unexpected Git HEAD")
    git("diff", "--exit-code")
    git("diff", "--cached", "--exit-code")
    for name in SOURCE_HASHES:
        if digest(git("show", BASE_COMMIT + ":" + name)) != SOURCE_HASHES[name]:
            raise ValueError("Pinned source does not match baseline commit")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--school", type=Path, default=Path.home() / "Downloads/MyTech v2.1 — TEST Knowledge.json")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.school.suffix.lower() != ".json" or any(p.startswith(".env") for p in args.school.parts):
            raise ValueError("Only the explicitly selected JSON backup may be read")
        reject_symlinks(args.school)
        verify_git_baseline()
        # Confirm ignored storage before writing any school metadata.
        subprocess.run(["git", "check-ignore", "--quiet", str(OUTPUT_DIRECTORY / CANDIDATE)], cwd=ROOT, check=True)
        school_raw = args.school.read_bytes()
        outputs = render_outputs(school_raw)
        if outputs != render_outputs(school_raw):
            raise ValueError("Nondeterministic generation")
        write_outputs(outputs, OUTPUT_DIRECTORY, check=args.check)
        if args.school.read_bytes() != school_raw:
            raise ValueError("School backup changed during preparation")
        print("School-derived candidate " + ("consistent" if args.check else "prepared privately") + "; four changes; no live calls")
        print("Candidate SHA-256: " + digest(outputs[CANDIDATE]))
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        print("School candidate failed: " + type(error).__name__ + "; review source hashes and contracts; values withheld", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
