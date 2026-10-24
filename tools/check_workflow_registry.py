"""Read-only checks for actual v2.1 workflow snapshots and release provenance.

Never reads Downloads or environment files, imports apps, or calls providers.
"""

import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import sys

try:
    from . import sync_catalogue as sync
    from .build_aiep_test import scan_credentials
except ImportError:
    import sync_catalogue as sync
    from build_aiep_test import scan_credentials


ROOT = sync.ROOT
REGISTRY = Path("workflow/v2.1/registry.json")
SENSITIVE_FIELDS = {"apikey", "accesstoken", "refreshtoken", "apitoken", "authorization", "proxyauthorization",
                    "password", "secret", "secretkey", "clientsecret", "privatekey", "token", "credential", "credentials"}
PROMPTS = ((sync.EXTRACTOR_ID, "description"), (sync.RECOMMENDATION_ID, "systemPrompt"))


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def sensitive_paths(value, path=""):
    """Only paths are returned; never include matched values in diagnostics."""
    hits = []
    normalize = lambda key: str(key).replace("_", "").replace("-", "").lower()
    populated = lambda item: item not in (None, "", [], {})
    if isinstance(value, dict):
        for key, item in value.items():
            if normalize(key) in SENSITIVE_FIELDS and populated(item):
                hits.append(path + "/" + key)
            hits.extend(sensitive_paths(item, path + "/" + key))
        if normalize(value.get("key", "")) in SENSITIVE_FIELDS and populated(value.get("value")):
            hits.append(path + "/value")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            hits.extend(sensitive_paths(item, path + "/" + str(index)))
    return hits


def inspect_public_json(raw):
    text = raw.decode("utf-8-sig")
    value = json.loads(text)
    if scan_credentials(text) or sensitive_paths(value):
        raise ValueError("Sensitive content rejected; matched values withheld")
    return value


def safe_path(root, relative):
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or any(part.startswith(".env") for part in path.parts):
        raise ValueError("Unsafe public registry path")
    result = root / path
    owned_paths = [root, *(root / Path(*path.parts[:index]) for index in range(1, len(path.parts) + 1))]
    if any(p.is_symlink() for p in owned_paths) or not result.resolve().is_relative_to(root.resolve()):
        raise ValueError("Symlink or outside-root registry path")
    return result


def json_differences(left, right, path=""):
    if type(left) is not type(right):
        return [path]
    if isinstance(left, dict):
        return sorted([path + "/" + key for key in left.keys() ^ right.keys()]
                      + [p for key in left.keys() & right.keys() for p in json_differences(left[key], right[key], path + "/" + key)])
    if isinstance(left, list):
        if len(left) != len(right):
            return [path]
        return [p for index, (a, b) in enumerate(zip(left, right)) for p in json_differences(a, b, path + "/" + str(index))]
    return [] if left == right else [path]


def comparison(original, optimized):
    paths = json_differences(original, optimized)
    prompt_paths, model_paths = [], []
    for identifier, key in PROMPTS:
        index = next(i for i, node in enumerate(original["nodes"]) if node["nodeId"] == identifier)
        fields = original["nodes"][index]["inputs"]
        prompt_paths.append(f"/nodes/{index}/inputs/{next(i for i,f in enumerate(fields) if f['key']==key)}/value")
        model_paths.append(f"/nodes/{index}/inputs/{next(i for i,f in enumerate(fields) if f['key']=='model')}/value")
    layout_paths = [p for p in paths if p.endswith(("/position/x", "/position/y"))]
    other = [p for p in paths if p not in prompt_paths + model_paths + layout_paths]
    return {"difference_count": len(paths), "changed_paths": paths,
            "prompt_change_paths": sorted(p for p in paths if p in prompt_paths),
            "model_change_paths": sorted(p for p in paths if p in model_paths),
            "layout_change_paths": sorted(layout_paths), "other_change_paths": sorted(other),
            "routing_validation_memory_output_and_other_configuration_identical": not other}


def check_registry(root=ROOT):
    root = Path(root)
    registry = inspect_public_json(safe_path(root, REGISTRY).read_bytes())
    if registry["default_variant"] != "original" or registry["automatic_promotion"] is not False:
        raise ValueError("Original must remain the default; automatic promotion forbidden")
    master_bytes = safe_path(root, registry["catalogue"]["master"]).read_bytes()
    master = inspect_public_json(master_bytes)
    if sha256(master_bytes) != registry["catalogue"]["sha256"] or len(master["products"]) != 54:
        raise ValueError("Registry Master checksum/count mismatch")
    graphs = {}
    for role in ("original", "optimized"):
        entry = registry["variants"][role]
        raw = safe_path(root, entry["snapshot"]).read_bytes()
        graph = inspect_public_json(raw)
        provenance_raw = safe_path(root, entry["provenance"]).read_bytes()
        provenance = inspect_public_json(provenance_raw)
        if sha256(provenance_raw) != entry["provenance_sha256"]:
            raise ValueError("Versioned provenance checksum mismatch")
        if sha256(raw) != entry["snapshot_sha256"] or sha256(raw) != provenance["sanitized_sha256"]:
            raise ValueError("Versioned snapshot checksum mismatch")
        if entry["application_name"] != provenance["application_name"] or entry["default_deployed"] != (role == "original"):
            raise ValueError("Application identity/default mismatch")
        if provenance["snapshot_kind"] != "actual_export" or provenance["published_revision"] is not None:
            raise ValueError("Actual-export provenance/publication evidence mismatch")
        if provenance["sanitization"]["removed_paths"] != ["/chatConfig/_id"] or "_id" in graph["chatConfig"]:
            raise ValueError("Account metadata redaction mismatch")
        if (len(graph["nodes"]), len(graph["edges"])) != (20, 18) or sync.check_workflow_inputs(graph):
            raise ValueError("Versioned native workflow contract mismatch")
        code = sync.validation_code(graph)["value"]
        start, end = sync.catalogue_span(code)
        if json.loads(code[start:end]) != sync.catalogue_projection(master):
            raise ValueError("Actual workflow catalogue differs from Master")
        if sync.node_input(graph, sync.RETRIEVAL_ID, "similarity")["value"] != 0.35:
            raise ValueError("Actual workflow retrieval threshold drift")
        if sync.node_input(graph, sync.RETRIEVAL_ID, "datasets")["value"] != [] or entry["kb_binding"]["exported_selection_present"] is not False:
            raise ValueError("KB binding must remain explicitly unverified in these snapshots")
        models = {node["nodeId"]: field["value"] for node in graph["nodes"] for field in node.get("inputs", []) if field["key"] == "model"}
        if models != entry["models"]:
            raise ValueError("Registered model configuration differs from actual snapshot")
        for node, key in PROMPTS:
            prompt = sync.node_input(graph, node, key)["value"]
            if sha256(prompt.encode()) != entry["prompts"][node]["sha256"]:
                raise ValueError("Registered original/short prompt fingerprint drift")
        graphs[role] = graph
    expected_models = {
        "original": {sync.EXTRACTOR_ID: "deepseek/deepseek-v4.1-flash", "ikIzMK483vihRths": "glm-4.7", sync.RECOMMENDATION_ID: "deepseek/deepseek-v4.1-flash"},
        "optimized": {sync.EXTRACTOR_ID: "glm-4.7", "ikIzMK483vihRths": "glm-4.7", sync.RECOMMENDATION_ID: "glm-4.7"},
    }
    if any(registry["variants"][role]["models"] != expected_models[role] for role in graphs):
        raise ValueError("Version roles/model configuration changed")
    actual_comparison = comparison(graphs["original"], graphs["optimized"])
    recorded = inspect_public_json(safe_path(root, registry["comparison"]).read_bytes())
    if actual_comparison != recorded or recorded["other_change_paths"]:
        raise ValueError("Unreviewed workflow difference beyond models, prompts and editor layout")
    if len(recorded["prompt_change_paths"]) != 2 or len(recorded["model_change_paths"]) != 2 or len(recorded["layout_change_paths"]) != 2:
        raise ValueError("Actual workflow change inventory drift")
    for name in ("sources_and_generated_outputs",):
        for reference, expected in registry[name].items():
            if sha256(safe_path(root, reference).read_bytes()) != expected:
                raise ValueError("Registered reproduction/deployment artifact checksum mismatch")
    known_original = inspect_public_json(safe_path(root, "tools/templates/v21_working_actual_export_sanitized.json").read_bytes())
    if graphs["original"] != known_original:
        raise ValueError("Versioned Original differs from preserved reviewed source")
    expected_default = registry["variants"]["original"]["application_name"]
    if registry["deployment"]["default_application"] != expected_default:
        raise ValueError("AIEP default application mapping drift")
    smoke = inspect_public_json(safe_path(root, registry["performance"]["record"]).read_bytes())
    if (smoke["application_name"] != registry["variants"]["optimized"]["application_name"]
            or registry["performance"]["observed_smoke_count"] != 1
            or registry["performance"]["completed_controlled_AB"] is not False
            or registry["performance"]["meaningful_prompt_latency_improvement_demonstrated"] is not False
            or smoke["interpretation"]["completed_six_request_AB_evaluation"] is not False
            or smoke["interpretation"]["prompt_shortening_demonstrated_meaningful_latency_improvement"] is not False
            or smoke["overall"]["platform_wide_billed_credits_independently_verified"] is not False):
        raise ValueError("Smoke-test evidence must not claim a controlled A/B result or verified platform bill")
    if not math.isclose(sum(node["AI_credits"] for node in smoke["nodes"].values()), smoke["overall"]["combined_AI_node_credits"], abs_tol=1e-9):
        raise ValueError("Reported node credit arithmetic mismatch")
    if not math.isclose(sum(node["latency_seconds"] for node in smoke["nodes"].values()) + smoke["overall"]["other_nodes_approx_seconds"], smoke["overall"]["workflow_latency_seconds"], abs_tol=0.01):
        raise ValueError("Reported smoke latency arithmetic mismatch")
    return registry, graphs, actual_comparison


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        check_registry(args.root)
        print("Consistent: actual Original/Optimized v2.1 snapshots; 54 products; 20 nodes/18 edges; 2 model + 2 prompt + 2 layout differences. Original remains default; KB/publication evidence limited.")
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, StopIteration):
        print("ERROR: workflow registry/security/consistency verification failed; private values withheld.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
