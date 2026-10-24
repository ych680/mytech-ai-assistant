"""Offline six-request GLM-4.7 A/B preparation; no reconstructed baseline fallback.

Without a reviewed credential-free actual working export, generate only a
blocked manifest, requested configuration, minimal plan and blank measurements.
Never imports an app, invokes a provider, reads .env, or executes model calls.
"""

import argparse
from copy import deepcopy
import csv
import difflib
import hashlib
import io
import json
from pathlib import Path
import re
import sys

try:
    from . import sync_catalogue as sync
    from .build_aiep_test import scan_credentials
except ImportError:
    import sync_catalogue as sync
    from build_aiep_test import scan_credentials


OUTPUT_SUBDIR = Path("generated/glm47_prompt_ab")
DEFAULT_BASELINE = sync.ROOT / "tools/templates/v21_working_actual_export_sanitized.json"
DEFAULT_REVIEW = sync.ROOT / "tools/templates/v21_glm47_actual_export_review.json"
CONTROL = "A-glm47-original.json"
CANDIDATE = "B-glm47-short.json"
REVIEW_FLAGS = ("credential_free", "original_export_prompts_verified", "non_prompt_configuration_reviewed",
                "validation_memory_and_four_field_contract_reviewed")
PARITY_ITEMS = ("20_nodes_18_edges", "node_and_output_ids", "kb_bindings_and_similarity_035",
                "model_parameters_and_output_limits", "conversation_histories", "extraction_and_routing",
                "budget_usage_product_validation", "memory_protection", "four_field_public_json")
RESULT_COLUMNS = ["run_id", "scenario_id", "variant", "execution_order", "session_label", "execution_status",
                  "state_extraction_ms", "recommendation_executed", "recommendation_ms", "total_workflow_ms",
                  "platform_credits", "credit_unit", "credit_scope", "raw_extraction_correct", "routing_correct",
                  "json_valid", "validation_status", "turn_pass", "evidence_ref", "notes"]


def digest(value):
    return hashlib.sha256(value).hexdigest()


def minimal_plan():
    cases = [
        {"id": "G01", "message": "I need a laptop under ¥6,000 for gaming.", "expected_route": "recommendation",
         "expected_state": [{"category": "Laptop", "budget": 6000, "main_usage": "Gaming"}],
         "checks": ["raw extraction is supported with numeric budget 6000", "correct recommendation route",
                    "one grounded Gaming Laptop <=6000; exact catalogue identity, price and source"]},
        {"id": "G02", "message": "I need a laptop for studying under RMB 6000 and a gaming mouse under RMB 300.",
         "expected_route": "recommendation",
         "expected_state": [{"category": "Laptop", "budget": 6000, "main_usage": "Study"},
                            {"category": "Mouse", "budget": 300, "main_usage": "Gaming"}],
         "checks": ["two independent requests; no usage or budget mixing", "correct recommendation route",
                    "two grounded eligible products; exact price/source; no unsafe partial batch"]},
        {"id": "G03", "message": "I need a gaming mouse.", "expected_route": "clarification",
         "expected_state": [{"category": "Mouse", "budget": None, "main_usage": "Gaming"}],
         "checks": ["only budget is missing; no invented budget", "route to clarification; Recommendation Assistant not executed",
                    "ask only for budget; recommendations=[]; clarification_needed=true"]},
    ]
    schedule = [{"run_id": f"{case['id']}-{variant}", "scenario_id": case["id"], "variant": variant,
                 "execution_order": index * 2 + offset + 1, "session_policy": "new distinct fresh conversation"}
                for index, case in enumerate(cases)
                for offset, variant in enumerate(("A", "B") if index % 2 == 0 else ("B", "A"))]
    return {"status": "PREPARATION_ONLY_NOT_RUN", "model_under_test": "glm-4.7",
            "baseline_requirement": "Actual reviewed exported published working TEST workflow; reconstruction forbidden",
            "scenarios": cases, "execution_schedule": schedule,
            "request_limit": {"pairs": 3, "requests_total": 6, "requests_per_variant": 3,
                              "repetitions": 1, "warmups": 0, "retries": 0, "continuation_turns": 0},
            "no_automatic_execution": True, "later_suite": "docs/v21-prompt-ab-broader-plan-deferred.md",
            "measurements": RESULT_COLUMNS,
            "limitations": "One observation per variant/scenario; exploratory only, no p95, significance or reliability-equivalence claim"}


def result_template(plan):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=RESULT_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for run in plan["execution_schedule"]:
        row = dict.fromkeys(RESULT_COLUMNS, "NA")
        row.update({key: run[key] for key in ("run_id", "scenario_id", "variant", "execution_order")})
        row.update(session_label=f"fresh-{run['run_id']}", execution_status="NOT_RUN")
        writer.writerow(row)
    return stream.getvalue()


def graph_checks(graph, nodes):
    if (len(graph.get("nodes", [])), len(graph.get("edges", []))) != (20, 18):
        raise ValueError("Actual baseline must have exactly 20 nodes and 18 edges; no reconstruction or overlays allowed")
    if len(set(nodes.values())) != 3:
        raise ValueError("Reviewed extraction, recommendation and retrieval node IDs must be distinct")
    if sync.check_workflow_inputs(graph):
        raise ValueError("Actual export contains an unresolved or invalid native input/output binding")
    if sync.node_input(graph, nodes["retrieval"], "similarity").get("value") != 0.35:
        raise ValueError("Actual export similarity must already be 0.35; do not modify it as part of A/B")
    datasets = sync.node_input(graph, nodes["retrieval"], "datasets").get("value")
    if not isinstance(datasets, list):
        raise ValueError("Actual knowledge-base selector shape needs review")
    for node in graph["nodes"]:
        for field in node.get("inputs", []):
            if field["key"] in ("model", "modelId") and not (isinstance(field.get("value"), str) and field["value"].strip()):
                raise ValueError("Actual model choices must be present; blank portable model selectors are not a baseline")


def verified_pair(source, review, source_sha):
    """A: source plus two GLM selectors; B: verified A plus two prompt strings."""
    if (review.get("provenance") != "actual_published_working_test_export"
            or review.get("source_sha256") != source_sha or not review.get("publish_state")
            or review.get("source_canonical_sha256") != digest(sync.json_text(source).encode())
            or any(review.get(key) is not True for key in REVIEW_FLAGS)):
        raise ValueError("Actual source provenance, exact hash, explicit publish-state evidence and configuration review required")
    nodes = review.get("nodes", {})
    if set(nodes) != {"state_extraction", "recommendation", "retrieval"}:
        raise ValueError("Review must identify the three actual node IDs")
    target = review.get("glm47", {})
    model_id = target.get("selector_value")
    if (target.get("display_name") != "glm-4.7" or target.get("selector_verified_from_export") is not True
            or not isinstance(model_id, str) or not model_id.strip()):
        raise ValueError("Verified account-specific GLM-4.7 selector required; display name alone is insufficient")
    graph_checks(source, nodes)
    if model_id not in [field.get("value") for node in source["nodes"] for field in node.get("inputs", []) if field.get("key") == "model"]:
        raise ValueError("GLM-4.7 selector evidence does not occur in this actual export")
    control = deepcopy(source)
    model_changes = []
    prompt_fields = (("state_extraction", "description"), ("recommendation", "systemPrompt"))
    for role, _ in prompt_fields:
        model = sync.node_input(control, nodes[role], "model")
        if model.get("valueDesc") not in (None, ""):
            raise ValueError("Model selector has additional metadata; obtain a reviewed native GLM selector before generation")
        before = model["value"]
        model["value"] = model_id
        model_changes.append({"node_id": nodes[role], "input_key": "model", "source_value_sha256": digest(before.encode()),
                              "target_display": "glm-4.7", "target_value_sha256": digest(model_id.encode())})
    # Proof of source -> A isolation: no settings/model parameters/KB/code overlays.
    restored = deepcopy(control)
    for role, _ in prompt_fields:
        sync.node_input(restored, nodes[role], "model")["value"] = sync.node_input(source, nodes[role], "model")["value"]
    if restored != source:
        raise ValueError("Unexpected actual-export to A change outside target model selectors")
    candidate = deepcopy(control)
    short = sync.optimized_prompt_values()
    changes = []
    refs = lambda text: re.findall(r"\{\{\$([^.$]+)\.([^$]+)\$\}\}", text)
    for role, key in prompt_fields:
        field = sync.node_input(candidate, nodes[role], key)
        old, new = field.get("value"), short[role]
        if not isinstance(old, str) or not old.strip() or old == new or refs(old) != refs(new):
            raise ValueError("Actual original prompts are missing/already shortened or their references differ; review required")
        field["value"] = new
        changes.append({"role": role, "node_id": nodes[role], "input_key": key,
                        "A_sha256": digest(old.encode()), "B_sha256": digest(new.encode()),
                        "A_characters": len(old), "B_characters": len(new)})
    restored_b = deepcopy(candidate)
    for role, key in prompt_fields:
        sync.node_input(restored_b, nodes[role], key)["value"] = sync.node_input(control, nodes[role], key)["value"]
    if restored_b != control:
        raise ValueError("B must differ from verified A only in two prompt values")
    graph_checks(control, nodes)
    graph_checks(candidate, nodes)
    return control, candidate, model_changes, changes


def render_outputs(source=None, review=None, source_sha=None):
    plan = minimal_plan()
    outputs = {"plan.json": sync.json_text(plan), "six-request-results-template.csv": result_template(plan)}
    configuration = {
        "intended_models": {"state_extraction": "glm-4.7", "recommendation": "glm-4.7",
                            "clarification_and_other_models": "identical to actual working export; no other model change"},
        "source_to_A_allowed_changes": "Only the two relevant model selector values; retain original actual prompts",
        "A_to_B_allowed_changes": "Only State Extraction description and Recommendation Assistant systemPrompt",
        "kb_policy": "Same actual existing 54-product KB, no content/reindex changes; similarity must already be 0.35",
        "protected_app": "Currently published DeepSeek-powered TEST and AIEP remain unchanged",
        "required_review_fields": list(REVIEW_FLAGS),
        "parity": dict.fromkeys(PARITY_ITEMS, "PENDING_ACTUAL_EXPORT_AND_CONFIGURATION_REVIEW"),
    }
    manifest = {"status": "BLOCKED_MISSING_AUTHORITATIVE_EXPORT", "workflow_files": [],
                "reason": "No actual verified published working export supplied; local reconstruction is not authoritative",
                "glm47_configuration": "REQUESTED_ONLY — selector availability and both configured models unverified",
                "requests_executed": 0, "credits_spent": 0, "initial_request_ceiling": 6,
                "not_a_live_runner": True, "protected_deployment_modified": False}
    if any(item is not None for item in (source, review, source_sha)):
        if any(item is None for item in (source, review, source_sha)):
            raise ValueError("Actual baseline, review and raw SHA-256 must be supplied together")
        a, b, models, prompts = verified_pair(source, review, source_sha)
        outputs[CONTROL], outputs[CANDIDATE] = sync.json_text(a), sync.json_text(b)
        diff = []
        for change in prompts:
            old = sync.node_input(a, change["node_id"], change["input_key"])["value"]
            new = sync.node_input(b, change["node_id"], change["input_key"])["value"]
            for line in difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                                            fromfile=f"A/{change['node_id']}/{change['input_key']}",
                                            tofile=f"B/{change['node_id']}/{change['input_key']}", n=0):
                diff.append(line if line.endswith("\n") else line + "\n\\ No newline at end of file\n")
        outputs["prompt-changes.diff"] = "".join(diff)
        manifest.update(status="IMPORT_CANDIDATES_PREPARED_KB_AND_PUBLISH_PARITY_PENDING", reason=None,
                        workflow_files=[CONTROL, CANDIDATE], source_sha256=source_sha,
                        review_sha256=digest(sync.json_text(review).encode()),
                        published_revision=review.get("published_revision"), publish_state=review["publish_state"],
                        original_download_sha256=review.get("original_download_sha256"),
                        model_changes=models, prompt_changes=prompts,
                        glm47_configuration="Both relevant selector values set to the verified GLM-4.7 identifier; native import/runtime still pending")
        configuration["parity"] = dict.fromkeys(PARITY_ITEMS, "PRESERVED_FROM_OPERATOR_REVIEWED_SOURCE; A/B JSON equality checked")
        configuration["parity"]["kb_bindings_and_similarity_035"] = (
            "A/B selectors identical and similarity 0.35; ACTUAL EXISTING KB ID UNVERIFIED because export omits selection"
            if not sync.node_input(source, review["nodes"]["retrieval"], "datasets")["value"]
            else "A/B KB selectors identical to actual export; imported binding still needs operator confirmation")
        configuration["publish_state"] = review["publish_state"]
        manifest["full_runtime_parity_confirmed"] = False
        manifest["invariants"] = {
            "nodes": len(a["nodes"]), "edges": len(a["edges"]),
            "node_ids": [node["nodeId"] for node in a["nodes"]],
            "output_ids": {node["nodeId"]: [item["id"] for item in node.get("outputs", [])] for node in a["nodes"]},
            "all_A_B_non_prompt_JSON_identical": True,
            "source_to_A_only_two_model_selector_values": True,
            "source_code_sha256": {node["nodeId"]: digest(field["value"].encode()) for node in source["nodes"]
                                   for field in node.get("inputs", []) if field["key"] == "code"},
            "retrieval_similarity": sync.node_input(a, review["nodes"]["retrieval"], "similarity")["value"],
            "exported_kb_selection_count": len(sync.node_input(source, review["nodes"]["retrieval"], "datasets")["value"]),
            "source_model_inventory": {node["nodeId"]: field["value"] for node in source["nodes"]
                                       for field in node.get("inputs", []) if field["key"] == "model"},
            "source_comparison": review.get("comparison_with_reconstructed_A"),
            "sanitization": review.get("sanitization"),
        }
    outputs["configuration-checklist.json"] = sync.json_text(configuration)
    manifest["builder_sha256"] = digest(Path(__file__).read_bytes())
    manifest["outputs"] = {name: digest(text.encode()) for name, text in outputs.items()}
    outputs["manifest.json"] = sync.json_text(manifest)
    for name, text in outputs.items():
        if scan_credentials(text):
            raise ValueError(f"Credential-pattern review rejected public artifact {name}; matched values withheld")
    return {name: text.encode() for name, text in outputs.items()}


def check_outputs(outputs, directory):
    errors = sync.check_outputs(outputs, directory)
    if directory.exists() and sorted(p.name for p in directory.iterdir()) != sorted(outputs):
        errors.append("Unexpected GLM A/B files: do not mix ready exports, blocked plans or actual results")
    if any(p.is_symlink() for p in (directory.parent, directory, *(directory / name for name in outputs))):
        errors.append("Symlink in GLM A/B output path")
    return errors


def write_outputs(outputs, directory):
    for p in (directory.parent, directory, *(directory / name for name in outputs)):
        if p.is_symlink():
            raise ValueError("Refusing symlink GLM A/B output")
    if directory.exists() and set(p.name for p in directory.iterdir()) - set(outputs):
        raise ValueError("Unexpected GLM A/B files; use a new output root, never overwrite results or delete exports automatically")
    directory.mkdir(parents=True, exist_ok=True)
    for name, data in outputs.items():
        path = directory / name
        if not path.exists() or path.read_bytes() != data:
            path.write_bytes(data)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--output-root", type=Path, default=sync.ROOT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        if bool(args.baseline) != bool(args.review):
            raise ValueError("--baseline and --review are required together")
        kwargs = {}
        if args.baseline:
            for path in (args.baseline, args.review):
                if path.name.startswith(".env") or path.suffix.lower() != ".json" or path.is_symlink():
                    raise ValueError("Only explicit reviewed credential-free JSON inputs accepted; environment files and symlinks forbidden")
            forbidden = [sync.WORKFLOW_TEMPLATE, sync.ROOT / "workflow/mytech-fastgpt-workflow.json",
                         sync.ROOT / sync.OUTPUT_SUBDIR / sync.WORKFLOW]
            if args.baseline.resolve() in [p.resolve() for p in forbidden] or "generated/prompt_ab_test" in args.baseline.as_posix():
                raise ValueError("Known local/portable reconstruction cannot be the actual working baseline")
            review = json.loads(args.review.read_text(encoding="utf-8"))
            if review.get("credential_free") is not True:
                raise ValueError("Credential-free source review required before reading the baseline")
            raw = args.baseline.read_bytes()
            if digest(raw) != review.get("source_sha256"):
                raise ValueError("Actual source SHA-256 differs from reviewed file")
            if scan_credentials(raw.decode("utf-8-sig")):
                raise ValueError("Baseline rejected by credential-pattern review; no values will be displayed")
            kwargs = {"source": json.loads(raw.decode("utf-8-sig")), "review": review, "source_sha": digest(raw)}
        outputs = render_outputs(**kwargs)
        directory = args.output_root.resolve() / OUTPUT_SUBDIR
        if args.check:
            errors = check_outputs(outputs, directory)
            if errors:
                raise ValueError("\n".join(errors))
        else:
            write_outputs(outputs, directory)
        status = json.loads(outputs["manifest.json"])["status"]
        print(f"GLM-4.7 preparation {'consistent' if args.check else 'written'}: {directory}; status={status}; six planned requests, zero executed.")
    except (OSError, UnicodeError, ValueError, KeyError, StopIteration, TypeError, RecursionError):
        # Avoid echoing a parse error, private model value or arbitrary export text.
        print("ERROR: GLM-4.7 source/configuration or artifact verification failed; no secret values displayed. Review the credential-free inputs and checklist.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
