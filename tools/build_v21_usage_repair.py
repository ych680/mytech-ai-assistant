"""Build isolated usage-repair candidates from the frozen actual Original export.

Offline only. Existing uploads, archived workflows, prompts and KBs are not
written. The accepted catalogue/A/B generators remain reproducible baselines.
"""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

try:
    from . import sync_catalogue as sync
    from . import build_aiep_test as aiep
    from .check_workflow_registry import check_registry, json_differences, sensitive_paths
except ImportError:
    import sync_catalogue as sync
    import build_aiep_test as aiep
    from check_workflow_registry import check_registry, json_differences, sensitive_paths


OUTPUT_SUBDIR = Path("generated/v21_multiproduct_usage_fix")
WORKFLOW = "workflow-original-repair.json"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def repair_workflow(original):
    candidate = deepcopy(original)
    field = sync.validation_code(candidate)
    baseline = sync.usage_validator_text()
    if not field["value"].startswith(baseline + "\nfunction main("):
        raise ValueError("Original validator does not match the reviewed frozen helper")
    code = sync.usage_validator_text(repair=True) + field["value"][len(baseline):]
    # Strict complete JSON, preserving support for a whole JSON code fence.
    start, end = code.index('  let text ='), code.index("  if (!data ||")
    code = code[:start] + r'''  let text = String(raw_json || "").trim();
  const fence = /^```json\r?\n([\s\S]*?)\r?\n```$/i.exec(text);
  if (fence) text = fence[1];
  let data;
  try { data = JSON.parse(text); }
  catch { return invalidResult("Invalid JSON returned by the recommendation model."); }

''' + code[end:]
    marker = '  const categoryKey = value =>'
    code = sync.replace_once(code, marker, '''  if (!checkUsageRepairResponseContract(data, PRODUCT_CATALOG)) {
    return invalidResult("Invalid exact response contract or catalogue facts.");
  }
  if (requests.some(request => !request || !Number.isFinite(request.budget) || request.budget <= 0
    || typeof request.main_usage !== "string" || !request.main_usage.trim())) {
    return invalidResult("Each request requires its own positive hard budget and usage.");
  }

''' + marker)
    marker = '  if (!validation_ok) return invalidResult(validation_error);'
    code = sync.replace_once(code, marker, marker + '''
  const partial = checkPartialCatalogueRecommendations(data, requests, PRODUCT_CATALOG, USAGE_COMPATIBILITY);
  if (!partial.valid) return invalidResult(partial.error);
''')
    field["value"] = code
    differences = json_differences(original, candidate)
    index = next(i for i, node in enumerate(original["nodes"]) if node["nodeId"] == sync.VALIDATOR_ID)
    field_index = next(i for i, item in enumerate(original["nodes"][index]["inputs"]) if item["key"] == "code")
    if differences != [f"/nodes/{index}/inputs/{field_index}/value"] or sync.check_workflow_inputs(candidate):
        raise ValueError("Unexpected graph or binding change outside the validator code field")
    return candidate, differences


def render_outputs():
    registry, graphs, _ = check_registry()
    dataset = sync.load_dataset(sync.TEST_DATASET)
    original = graphs["original"]
    candidate, differences = repair_workflow(original)
    original_raw = (sync.ROOT / registry["variants"]["original"]["snapshot"]).read_bytes()
    outputs = {
        WORKFLOW: sync.json_text(candidate).encode("utf-8"),
        "local/index.html": sync.render_frontend(dataset, repair_usage=True).encode("utf-8"),
        "local/catalogue.json": sync.TEST_DATASET.read_bytes(),
        "local/" + sync.WORKFLOW: sync.json_text(candidate).encode("utf-8"),
        "local/" + sync.KNOWLEDGE: (sync.ROOT / sync.OUTPUT_SUBDIR / sync.KNOWLEDGE).read_bytes(),
        "aiep/site/index.html": aiep.render_aiep_frontend(dataset, repair_usage=True).encode("utf-8"),
    }
    local_manifest = {"product_count": len(dataset["products"]), "release_scope": "OFFLINE USAGE REPAIR CANDIDATE — not deployed",
                      "outputs": {name.removeprefix("local/"): digest(raw) for name, raw in outputs.items() if name.startswith("local/")}}
    outputs["local/manifest.json"] = sync.json_text(local_manifest).encode("utf-8")
    sources = [Path(__file__), sync.ROOT / "tools/sync_catalogue.py", sync.ROOT / "tools/build_aiep_test.py",
               sync.USAGE_VALIDATOR, sync.FRONTEND_USAGE, sync.USAGE_COMPATIBILITY, sync.FROZEN_USAGE_WORKFLOW,
               sync.FRONTEND, sync.FRONTEND_VALIDATOR, sync.FRONTEND_RUNTIME, sync.TEST_SETTINGS,
               sync.CITATION_HELPERS, aiep.RUNTIME, aiep.TRANSPORT,
               sync.ROOT / "mytech_v2_1_test_adapter.mjs", sync.ROOT / "mytech_v2_1_test_server.mjs"]
    manifest = {
        "status": "OFFLINE_ONLY_REVIEW_REQUIRED", "default_deployment_changed": False,
        "source_original": registry["variants"]["original"]["snapshot"], "source_sha256": digest(original_raw),
        "workflow_changed_paths": differences, "nodes": len(candidate["nodes"]), "edges": len(candidate["edges"]),
        "prompts_models_history_rag_routing_and_memory_bindings": "Identical to the actual Original export",
        "kb_binding": "Unverified: Original export omits dataset selection; bind and verify manually before any future use",
        "published_revision": None, "requests_executed_by_builder": 0,
        "partial_response_policy": "Only catalogue-ineligible omitted categories, with explicit same-clause no-match explanations; never discard invalid returned products",
        "upload_directory": (OUTPUT_SUBDIR / "aiep/site").as_posix(),
        "sources_sha256": {path.relative_to(sync.ROOT).as_posix(): digest(path.read_bytes()) for path in sources},
        "outputs": {name: digest(raw) for name, raw in outputs.items()},
    }
    outputs["manifest.json"] = sync.json_text(manifest).encode("utf-8")
    for name, raw in outputs.items():
        text = raw.decode("utf-8")
        if aiep.scan_credentials(text) or (name.endswith(".json") and sensitive_paths(json.loads(text))):
            raise ValueError("Candidate credential review failed; matched values withheld")
    return outputs


def check_outputs(outputs, directory):
    paths = [directory.parent, directory, *(directory / name for name in outputs)]
    if any(path.is_symlink() for path in paths) or (directory.exists() and any(p.is_symlink() for p in directory.rglob("*"))):
        return ["Symlink in usage-repair candidate; no linked content inspected"]
    errors = sync.check_outputs(outputs, directory)
    if directory.exists():
        actual = {path.relative_to(directory).as_posix() for path in directory.rglob("*") if path.is_file()}
        if actual != set(outputs):
            errors.append("Unexpected or missing usage-repair candidate files")
    return errors


def write_outputs(outputs, directory):
    for name in outputs:
        path = directory / name
        if any(parent.is_symlink() for parent in [path, *path.parents]):
            raise ValueError("Refusing symlink candidate output")
    if directory.exists() and {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()} - set(outputs):
        raise ValueError("Unexpected candidate files; review without overwriting")
    for name, raw in outputs.items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() or path.read_bytes() != raw:
            path.write_bytes(raw)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-root", type=Path, default=sync.ROOT)
    args = parser.parse_args(argv)
    try:
        outputs = render_outputs()
        directory = args.output_root.resolve() / OUTPUT_SUBDIR
        if args.check:
            errors = check_outputs(outputs, directory)
            if errors:
                raise ValueError("\n".join(errors))
        else:
            write_outputs(outputs, directory)
        print(f"Usage-repair candidate {'consistent' if args.check else 'prepared'}: {directory}; no deployment or live calls")
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Usage-repair preparation failed: {type(error).__name__}; review public sources and manifests", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
