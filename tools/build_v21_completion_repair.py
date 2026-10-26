"""Separate offline completion candidate derived from the preserved PR #17 package."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

try:
    from . import build_v21_usage_repair as parent
except ImportError:
    import build_v21_usage_repair as parent

sync, aiep = parent.sync, parent.aiep
OUTPUT_SUBDIR = Path("generated/v21_completion_fix")
SOURCE = sync.ROOT / parent.OUTPUT_SUBDIR
POLICY = sync.ROOT / "tools/templates/v21_completion_validation.js"
WORKFLOW = "workflow-completion-repair.json"
PARENT_WORKFLOW_SHA256 = "e41498899c13434c68ee3de9691cfd9d705ecc81ba4629ba5c241d622bae551c"
SAFE = {"answer": "I couldn't complete a verified recommendation for this request. No product was accepted.",
        "recommendations": [], "next_step": "Please try again; your current requirements have not been changed.",
        "clarification_needed": False}


def replace_policy(text):
    start = text.index("function checkPartialCatalogueRecommendations(")
    end = text.index("function checkUsageRepairResponseContract(", start)
    return text[:start] + POLICY.read_text(encoding="utf-8") + "\n\n" + text[end:]


def repair_workflow(source):
    candidate = deepcopy(source)
    validator = next(n for n in candidate["nodes"] if n["nodeId"] == sync.VALIDATOR_ID)
    field = sync.validation_code(candidate)
    code = replace_policy(field["value"])
    code = sync.replace_once(code, "  follow_up_intent\n}) {", "  follow_up_intent,\n  retrieved_evidence\n}) {\n  let completion_status = 'not_evaluated';")
    code = sync.replace_once(code,
        "  const partial = checkPartialCatalogueRecommendations(data, requests, PRODUCT_CATALOG, USAGE_COMPATIBILITY);\n  if (!partial.valid) return invalidResult(partial.error);",
        "  const completion = checkRecommendationCompletion(data, requests, PRODUCT_CATALOG, USAGE_COMPATIBILITY,\n"
        "    { intent, previous, evidence: retrieved_evidence });\n"
        "  completion_status = completion.status;\n"
        "  if (!completion.valid) return invalidResult(completion.status + ': ' + completion.error);\n"
        "  if (completion.output) { answer = completion.output.answer; next_step = completion.output.next_step; }")
    # PR17's comparison-empty text said 'retrieved' without proving retrieval.
    # The verified current-request canonical text now owns all no-match wording.
    start = code.index("    if (validation_ok && isComparison) {", code.index("// Empty public recommendations"))
    end = code.index("\n  } else if", start)
    code = code[:start] + code[end:]
    code = sync.replace_once(code, "    validation_ok,\n    validation_error,", "    validation_ok,\n    completion_status,\n    validation_error,")
    start = code.index("    const safe = {", code.index("  function invalidResult("))
    end = code.index("    return {", start)
    code = code[:start] + "    const safe = " + json.dumps(SAFE, ensure_ascii=False) + ";\n" + code[end:]
    code = sync.replace_once(code, "      validation_ok: false,", "      validation_ok: false,\n      completion_status,")
    field["value"] = code
    evidence = deepcopy(next(i for i in validator["inputs"] if i["key"] == "active_requests"))
    evidence.update(key="retrieved_evidence", label="retrieved_evidence", valueType="datasetQuote", required=False,
                    value=["zWAw4oYVL1QMe8YX", "quoteQA"])
    validator["inputs"].append(evidence)
    status = deepcopy(next(i for i in validator["outputs"] if i.get("key") == "validation_error"))
    status.update(id="phase3CompletionStatus", key="completion_status", label="completion_status")
    validator["outputs"].append(status)
    fallback = next(n for n in candidate["nodes"] if n["nodeId"] == "zh9L8VeY9vKm3WnU")
    next(i for i in fallback["inputs"] if i["key"] == "text")["value"] = json.dumps(SAFE, ensure_ascii=False, indent=2)
    # Restoring precisely these authorized fields must restore the entire PR17
    # workflow, including every prompt/model/edge/state/retrieval setting.
    restored = deepcopy(candidate)
    for index, n in enumerate(restored["nodes"]):
        if n["nodeId"] in (sync.VALIDATOR_ID, "zh9L8VeY9vKm3WnU"):
            restored["nodes"][index] = deepcopy(source["nodes"][index])
    if restored != source:
        raise ValueError("Unexpected change outside completion validator/fallback")
    if source["edges"] != candidate["edges"] or source["chatConfig"] != candidate["chatConfig"] or sync.check_workflow_inputs(candidate):
        raise ValueError("Completion candidate graph/binding mismatch")
    return candidate


def repair_frontend(text):
    text = replace_policy(text)
    start = text.index("      const partial = checkPartialCatalogueRecommendations(")
    end = text.index("      const visibleText = [", start)
    text = text[:start] + ("      const completion = checkClientRecommendationCompletion(output, guard, testUsageCatalogue, TEST_USAGE_POLICY);\n"
                          "      if (!completion.valid) errors.push(completion.error);\n\n") + text[end:]
    text = sync.replace_once(text, "      return { valid: errors.length === 0, errors };",
                             "      return { valid: errors.length === 0, errors, output: completion.output || output };")
    text = sync.replace_once(text, "      if (validation.valid && validateStructuredOutput(display, guard).valid) return output;",
                             "      if (validation.valid && validateStructuredOutput(display, guard).valid) return validation.output;")
    return sync.replace_once(text, "        usageClarificationNeeded: usageIssue,", "        completionControl: completionControlMessage(text),\n        usageClarificationNeeded: usageIssue,")


def render_outputs():
    if any(p.is_symlink() for p in (SOURCE.parent, SOURCE)) or any(p.is_symlink() for p in SOURCE.rglob("*")):
        raise ValueError("Symlink in PR17 source package; no linked content read")
    raw = (SOURCE / parent.WORKFLOW).read_bytes()
    if parent.digest(raw) != PARENT_WORKFLOW_SHA256:
        raise ValueError("PR17 workflow base differs from reviewed fingerprint")
    # Check parent reproducibility without modifying its workflow or HTML.
    previous = parent.render_outputs()
    if parent.check_outputs(previous, SOURCE):
        raise ValueError("PR17 package is stale; review before deriving completion candidate")
    source = json.loads(raw)
    workflow = repair_workflow(source)
    outputs = {WORKFLOW: sync.json_text(workflow).encode("utf-8"),
               "local/" + sync.WORKFLOW: sync.json_text(workflow).encode("utf-8"),
               "local/catalogue.json": (SOURCE / "local/catalogue.json").read_bytes(),
               "local/" + sync.KNOWLEDGE: (SOURCE / "local" / sync.KNOWLEDGE).read_bytes()}
    for name in ("local/index.html", "aiep/site/index.html"):
        outputs[name] = repair_frontend(previous[name].decode("utf-8")).encode("utf-8")
    local = {"product_count": 54, "completion_validation": True, "release_scope": "OFFLINE COMPLETION CANDIDATE — not deployed",
             "outputs": {name.removeprefix("local/"): parent.digest(data) for name, data in outputs.items() if name.startswith("local/")}}
    outputs["local/manifest.json"] = sync.json_text(local).encode("utf-8")
    sources = [Path(__file__), POLICY, sync.ROOT / "mytech_v2_1_test_adapter.mjs", sync.ROOT / "mytech_v2_1_test_server.mjs",
               SOURCE / "manifest.json", SOURCE / parent.WORKFLOW, sync.TEST_DATASET]
    manifest = {"status": "OFFLINE_ONLY_REVIEW_REQUIRED", "base_commit": "860b744a9d9f956a7dfa296dea5843fdb3385c38",
                "source_pr17": (parent.OUTPUT_SUBDIR / parent.WORKFLOW).as_posix(), "source_sha256": parent.digest(raw),
                "workflow_changed_paths": parent.json_differences(source, workflow), "nodes": len(workflow["nodes"]), "edges": len(workflow["edges"]),
                "workflow_changed_fields": ["/nodes/11/inputs/2/value", "/nodes/11/inputs/7", "/nodes/11/outputs/11", "/nodes/14/inputs/0/value"],
                "prompts_models_history_rag_edges_and_memory_bindings": "Unchanged from PR17",
                "retrieval_diagnostics": "quoteQA is diagnostic only; empty evidence does not distinguish no hits from configuration/binding failure. Successful products retain unverified grounding unless complete records are recognized; recognition is not proof of model use. No synthesis or retry.",
                "published_revision": None, "kb_binding": "Unverified; no KB selection or publication changed",
                "default_deployment_changed": False, "requests_executed_by_builder": 0,
                "sources_sha256": {p.relative_to(sync.ROOT).as_posix(): parent.digest(p.read_bytes()) for p in sources},
                "outputs": {name: parent.digest(data) for name, data in outputs.items()}}
    outputs["manifest.json"] = sync.json_text(manifest).encode("utf-8")
    for name, data in outputs.items():
        text = data.decode("utf-8")
        if aiep.scan_credentials(text) or (name.endswith(".json") and parent.sensitive_paths(json.loads(text))):
            raise ValueError("Public completion candidate credential check failed; values withheld")
    return outputs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-root", type=Path, default=sync.ROOT)
    args = parser.parse_args(argv)
    try:
        outputs = render_outputs()
        directory = args.output_root.resolve() / OUTPUT_SUBDIR
        if args.check:
            if parent.check_outputs(outputs, directory):
                raise ValueError("Stale completion candidate")
        else:
            parent.write_outputs(outputs, directory)
        print("Completion candidate consistent" if args.check else "Offline completion candidate prepared; no live calls")
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Completion preparation failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
