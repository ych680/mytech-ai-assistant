"""Retain DEFERRED reconstructed A/B offline fixtures, never an authoritative export.

The active six-request GLM-4.7 experiment uses build_glm47_prompt_ab.py.
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


OUTPUT_SUBDIR = Path("generated/prompt_ab_test")
CONTROL = "mytech-v21-prompt-A-control.json"
CANDIDATE = "mytech-v21-prompt-B-short.json"
PROMPTS = (("state_extraction", sync.EXTRACTOR_ID, "description"),
           ("recommendation", sync.RECOMMENDATION_ID, "systemPrompt"))
TURN_COLUMNS = ["campaign_id", "pair_id", "run_id", "scenario_id", "repetition", "variant", "order",
                "turn_index", "session_label", "entrypoint", "started_at", "expected_kind", "outcome",
                "scope_ok", "state_ok", "json_contract_ok", "turn_pass", "eligible_requests", "returned_recommendations", "valid_recommendations",
                "validation_fallback", "safety_violations", "total_workflow_ms", "wall_ms",
                "input_tokens", "output_tokens", "credit_delta", "credit_unit", "credit_scope",
                "cache_status", "evidence_ref", "notes"]
NODE_COLUMNS = ["run_id", "node_id", "node_name", "executed", "duration_ms", "input_tokens",
                "output_tokens", "credits", "credit_unit", "evidence_ref"]


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


def csv_header(columns):
    stream = io.StringIO(newline="")
    csv.writer(stream, lineterminator="\n").writerow(columns)
    return stream.getvalue()


def assert_prompt_pair(control, candidate):
    """Fail closed unless the complete graphs differ in exactly two string values."""
    for graph in (control, candidate):
        if (len(graph["nodes"]), len(graph["edges"])) != (20, 18):
            raise ValueError("Prompt A/B requires the reviewed 20-node/18-edge graph")
        sync.assert_portable(graph)
        errors = sync.check_workflow_inputs(graph)
        if errors:
            raise ValueError("Invalid native A/B input contract")
    restored = deepcopy(candidate)
    changes = []
    reference_pattern = r"\{\{\$([^.$]+)\.([^$]+)\$\}\}"
    for label, identifier, key in PROMPTS:
        old = sync.node_input(control, identifier, key)["value"]
        new = sync.node_input(candidate, identifier, key)["value"]
        if not all(isinstance(value, str) and value.strip() for value in (old, new)) or old == new:
            raise ValueError("Both A/B prompts must be nonempty and different")
        if re.findall(reference_pattern, old) != re.findall(reference_pattern, new):
            raise ValueError("A/B prompt interpolation changed")
        sync.node_input(restored, identifier, key)["value"] = old
        changes.append({"label": label, "node_id": identifier, "input_key": key,
                        "A_characters": len(old), "B_characters": len(new),
                        "reduction_percent": round(100 * (1 - len(new) / len(old)), 2),
                        "A_sha256": digest(old.encode()), "B_sha256": digest(new.encode())})
    if restored != control:
        raise ValueError("A/B difference outside the two allowed prompt values")
    appendix = sync.EXTRACTION_RULES.read_text(encoding="utf-8")
    if not all(sync.node_input(graph, sync.EXTRACTOR_ID, "description")["value"].endswith(appendix)
               for graph in (control, candidate)):
        raise ValueError("A/B extraction reliability appendix changed")
    return changes


def plan():
    """Small matched user trajectories, not fixed model answers or live results."""
    scenarios = []
    for index, amount in enumerate(("RMB 6000", "RMB 6,000", "¥6000", "¥6,000"), 1):
        scenarios.append({"id": f"C0{index}", "group": "currency", "turns": [
            {"message": f"I need a laptop under {amount} for gaming.", "expected_kind": "recommendation",
             "assertions": ["supported; Laptop budget exactly 6000 and Gaming usage", "one eligible grounded Laptop; exact catalogue price/source; price <= 6000"]}]})
    scenarios += [
        {"id": "S01", "group": "single", "turns": [
            {"message": "I need a laptop for studying under RMB 6000.", "expected_kind": "recommendation",
             "assertions": ["Laptop / 6000 / Study", "one eligible grounded Laptop; no unrelated category"]}]},
        {"id": "M01", "group": "multi", "turns": [
            {"message": "I need a laptop for studying under RMB 6000 and a gaming mouse under RMB 300.", "expected_kind": "recommendation",
             "assertions": ["Laptop / 6000 / Study AND Mouse / 300 / Gaming; independent fields",
                            "two eligible recommendations; no Office-only mouse for Gaming; no partial invalid batch"]}]},
        {"id": "T01", "group": "follow_up", "turns": [
            {"message": "I need a laptop for studying under RMB 6000 and a gaming mouse under RMB 500.", "expected_kind": "recommendation",
             "assertions": ["two eligible recommendations; save separate validated anchors and requests"]},
            {"message": "Cheaper mouse.", "expected_kind": "comparison_or_no_match",
             "assertions": ["only Mouse is targeted; Gaming and budget 500 retained", "strictly cheaper than its prior validated Mouse or truthful no-match; Laptop anchor unchanged"]},
            {"message": "Another laptop.", "expected_kind": "comparison_or_no_match",
             "assertions": ["only Laptop is targeted; Study and budget 6000 retained", "different eligible Laptop or truthful no-match; Mouse anchor unchanged"]},
            {"message": "More expensive mouse.", "expected_kind": "comparison_or_no_match",
             "assertions": ["only Mouse; strictly above latest validated Mouse but <=500; Gaming retained", "truthful no-match allowed; invalid/no-match reply must not replace anchors"]}]},
        {"id": "N01", "group": "no_match", "turns": [
            {"message": "I need a gaming mouse under RMB 50.", "expected_kind": "no_match",
             "assertions": ["complete Mouse / 50 / Gaming; no eligible product in this Master", "recommendations=[]; clarification_needed=false; no budget widening"]}]},
        {"id": "Q01", "group": "clarification", "turns": [
            {"message": "I need a gaming mouse.", "expected_kind": "clarification",
             "assertions": ["ask only for missing budget; no recommendations; preserve Mouse/Gaming"]},
            {"message": "RMB 300.", "expected_kind": "recommendation",
             "assertions": ["Mouse / 300 / Gaming recovered from same chat; one eligible recommendation"]}]},
    ]
    turns = sum(len(case["turns"]) for case in scenarios)
    return {"scope": "DEFERRED broader offline fixture plan; superseded, not authorized for live execution",
            "phase_status": "DEFERRED_NOT_AUTHORIZED",
            "active_plan": "generated/glm47_prompt_ab/plan.json",
            "live_parity_gate": "PENDING: compare A against the currently published working TEST prompts/configuration",
            "variants": {"A": CONTROL, "B": CANDIDATE}, "scenarios": scenarios,
            "schedule": {"repetitions": 3, "turns_per_variant_per_repetition": turns,
                         "measured_request_ceiling": turns * 2 * 3, "warmup_requests": 2,
                         "all_request_ceiling_without_retries": turns * 2 * 3 + 2,
                         "smoke_requests_including_warmup": turns * 2 + 2,
                         "pair_order": "For zero-based scenario_index and repetition_index: AB if their sum is even, otherwise BA; run the whole session before its pair",
                         "session_policy": "Fresh distinct chat per variant/scenario/repetition; keep chat only within that scenario's turns; no automatic retries"},
            "offline_fault_cases": ["wrong exact price", "wrong source", "wrong category", "over budget",
                                    "wrong usage", "malformed JSON", "duplicate category batch"],
            "result_columns": TURN_COLUMNS, "node_metric_columns": NODE_COLUMNS,
            "no_live_results": True}


def render_outputs():
    dataset = sync.load_dataset(sync.TEST_DATASET)
    expected = sync.render_outputs(dataset)
    errors = sync.check_outputs(expected, sync.ROOT / sync.OUTPUT_SUBDIR)
    if errors:
        raise ValueError("Local TEST artifacts are stale; review consistency before A/B preparation")
    candidate = json.loads(expected[sync.WORKFLOW])
    template = sync.load_dataset(sync.WORKFLOW_TEMPLATE)
    sync.assert_workflow_contract(template, candidate)
    control = deepcopy(candidate)
    originals = sync.original_prompt_values(template)
    for label, identifier, key in PROMPTS:
        sync.node_input(control, identifier, key)["value"] = originals[label]
    changes = assert_prompt_pair(control, candidate)
    fingerprint = deepcopy(control)
    prompt_diff = []
    for label, identifier, key in PROMPTS:
        old = sync.node_input(control, identifier, key)["value"]
        new = sync.node_input(candidate, identifier, key)["value"]
        for line in difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True),
                                        fromfile=f"A/{identifier}/{key}", tofile=f"B/{identifier}/{key}", n=0):
            prompt_diff.append(line if line.endswith("\n") else line + "\n\\ No newline at end of file\n")
        sync.node_input(fingerprint, identifier, key)["value"] = "<PROMPT_UNDER_TEST>"
    outputs = {CONTROL: sync.json_text(control), CANDIDATE: sync.json_text(candidate),
               "prompt-changes.diff": "".join(prompt_diff), "plan.json": sync.json_text(plan()),
               "turn-results-template.csv": csv_header(TURN_COLUMNS),
               "node-metrics-template.csv": csv_header(NODE_COLUMNS)}
    code_hashes = {node["nodeId"]: digest(field["value"].encode()) for node in control["nodes"]
                   for field in node.get("inputs", []) if field["key"] == "code"}
    manifest = {
        "scope": "DEFERRED RECONSTRUCTED OFFLINE FIXTURES ONLY — DO NOT IMPORT OR USE AS THE WORKING EXPORT",
        "import_status": "DO_NOT_IMPORT — active GLM-4.7 experiment requires the actual reviewed working export",
        "superseded_by": "generated/glm47_prompt_ab/manifest.json",
        "control_provenance": "Reconstructed pre-shortening v2.1 TEST: existing 54-product generated graph with original two prompts restored; NOT a fresh live export",
        "live_control_parity": "UNVERIFIED — operator must compare actual published A prompts and model/KB/settings before running",
        "user_report": "AIEP now connected to published working TEST; no live inspection performed in preparation",
        "changed_prompt_values": changes,
        "invariants": {"nodes": len(control["nodes"]), "edges": len(control["edges"]),
                       "node_ids": [node["nodeId"] for node in control["nodes"]],
                       "global_variables": len(control["chatConfig"]["variables"]),
                       "non_prompt_graph_sha256": digest(sync.json_text(fingerprint).encode()),
                       "deterministic_code_sha256": code_hashes, "product_count": len(dataset["products"]),
                       "retrieval_similarity": sync.node_input(control, sync.RETRIEVAL_ID, "similarity")["value"],
                       "extraction_history": sync.node_input(control, sync.EXTRACTOR_ID, "history")["value"],
                       "recommendation_history": sync.node_input(control, sync.RECOMMENDATION_ID, "history")["value"],
                       "recommendation_max_tokens": sync.node_input(control, sync.RECOMMENDATION_ID, "maxToken")["value"],
                       "all_other_json_values_identical": True},
        "binding_policy": "Both exports preserve blank portable model/dataset bindings. Operator must bind BOTH isolated apps to exactly the working models/settings and existing unchanged 54-product KB; actual live parity is not proven offline.",
        "sources_sha256": {path.relative_to(sync.ROOT).as_posix(): digest(path.read_bytes()) for path in
                           (Path(__file__), sync.ROOT / "tools/sync_catalogue.py", sync.WORKFLOW_TEMPLATE, sync.TEST_DATASET, sync.STATE_EXTRACTION_PROMPT,
                            sync.RECOMMENDATION_PROMPT, sync.EXTRACTION_RULES,
                            sync.ROOT / sync.OUTPUT_SUBDIR / sync.WORKFLOW)},
        "outputs": {name: digest(text.encode()) for name, text in outputs.items()},
        "live_measurements": "NONE — blank CSV headers only; no model credits used",
    }
    outputs["manifest.json"] = sync.json_text(manifest)
    for name, text in outputs.items():
        findings = scan_credentials(text)
        if findings:
            raise ValueError(f"Credential pattern review failed in {name}: {findings}")
    return {name: text.encode("utf-8") for name, text in outputs.items()}


def check_outputs(outputs, directory):
    errors = sync.check_outputs(outputs, directory)
    if directory.exists() and sorted(path.name for path in directory.iterdir()) != sorted(outputs):
        errors.append("A/B artifact directory must contain exactly the generated preparation files; keep actual results elsewhere")
    if any(path.is_symlink() for path in (directory.parent, directory, *(directory / name for name in outputs))):
        errors.append("Symlink in A/B output path")
    return errors


def write_outputs(outputs, directory):
    for path in (directory.parent, directory, *(directory / name for name in outputs)):
        if path.is_symlink():
            raise ValueError("Refusing symlink A/B output path")
    if directory.exists() and set(path.name for path in directory.iterdir()) - set(outputs):
        raise ValueError("Unexpected A/B artifacts; review manually instead of overwriting results")
    directory.mkdir(parents=True, exist_ok=True)
    for name, payload in outputs.items():
        path = directory / name
        if not path.exists() or path.read_bytes() != payload:
            path.write_bytes(payload)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=sync.ROOT)
    parser.add_argument("--check", action="store_true")
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
        print(f"Deferred reconstructed offline fixtures {'consistent' if args.check else 'prepared'}: {directory}; DO NOT IMPORT. Active experiment: build_glm47_prompt_ab.py.")
    except (OSError, UnicodeError, ValueError, RecursionError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
