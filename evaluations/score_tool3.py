"""Pure, deterministic scoring of in-memory offline runner evidence.

assess_observation(scenario, evidence, *, human_review=None) uses requirements,
plans and actual evidence only; it never reads scripts or expected assessments.
score_scenario(...) additionally compares that independent assessment with the
authored oracle. Pass a scenario from the validated manifest. Neither function
executes tools, reads files, judges natural language, or persists reports.

human_review is an optional explicit in-memory annotation ('pass' or 'fail').
Absent an annotation, a required review stays pending, regardless of anticipated
outcome. An annotation changes the actual task verdict. Expectation comparison
still uses the authored oracle, so a reviewed verdict differs from a pending oracle.

Executed-call counts include accepted dispatches returning skipped results;
skipped_count identifies these separately. Redundancy means exceeding the largest
per-tool multiplicity in any permitted plan for the selected fixed resources.
Forbidden tools are names absent from every permitted plan. Unknown causes behind
coarse resource errors are deliberately not inferred. There are no percentages,
weights, aggregate accuracy claims or semantic explanation scores.
"""

from collections import Counter

from tools import tool3_tokenproxy as adapter
from .run_tool3 import compare_orchestration


PROTOCOL_CODES = frozenset({
    "invalid_response_json", "invalid_assistant_message", "empty_assistant_response",
    "invalid_thinking_markup", "invalid_http_response", "response_too_large",
})
AVAILABILITY_CODES = frozenset({"network_error", "request_timeout", "transport_error"})
RESOURCE_CODES = frozenset({"dataset_read_error", "knowledge_read_error"})
OPERATION_TOOLS = {
    "explicit_validate_products": {"validate_products"},
    "dataset_validation": {"validate_products", "check_knowledge"},
    "knowledge_inspection": {"check_knowledge"},
}


def _matches(row, specification):
    return all(row[key] == specification[key] for key in ("name", "status", "code"))


def _operations(requirements, rows):
    outcomes = []
    for requirement in requirements:
        # Only tools explicitly permitted as evidence for this requirement may
        # provide semantic credit. In particular K cannot replace explicit V.
        permitted = {item["name"] for item in
                     requirement["acceptable_results"] + requirement["acceptable_blocks"]}
        candidates = [row for row in rows if row["name"] in
                      (permitted & OPERATION_TOOLS[requirement["operation"]])]
        met = [row for row in candidates if any(_matches(row, item)
               for item in requirement["acceptable_results"])]
        blocked = [row for row in candidates if any(_matches(row, item)
                   for item in requirement["acceptable_blocks"])]
        state, supporting = ("met", met) if met else (
            ("blocked_expected", blocked) if blocked else (
                ("failed_unexpected", candidates) if candidates else ("missing", [])))
        outcomes.append({"operation": requirement["operation"], "state": state,
                         "tool_result_ids": [row["tool_call_id"] for row in supporting]})
    return outcomes


def _read_evidence(scenario, evidence):
    """Reject incomplete/incoherent evidence without guessing authorization.

    Partial, well-formed results remain descriptive evidence on infrastructure
    failures. They never turn an invalid run into an agent pass or failure.
    """
    errors = []
    if type(evidence) is not dict:
        evidence = {}
        errors.append("malformed_evidence")
    actual = evidence.get("actual")
    fixture = evidence.get("fixture")
    if type(fixture) is not dict:
        fixture = {}
    if (evidence.get("evaluation_mode") != "scripted_offline"
            or evidence.get("scenario_id") != scenario["id"]
            or evidence.get("scenario_version") != scenario["version"]
            or fixture.get("id") != scenario["fixture_id"]):
        errors.append("evidence_identity_mismatch")
    if (evidence.get("runner_status") != "completed"
            or evidence.get("infrastructure_failures")
            or fixture.get("integrity") != "passed"
            or fixture.get("cleanup") != "passed"):
        errors.append("runner_or_fixture_failure")
    calls = evidence.get("tool_calls", [])
    rows = actual.get("tool_results", []) if type(actual) is dict else evidence.get("partial_tool_results", [])
    try:
        if type(calls) is not list or type(rows) is not list:
            raise ValueError
        last_invocation = 0
        for call in calls:
            if (type(call) is not dict or type(call["id"]) is not str
                    or type(call["name"]) is not str
                    or type(call["transport_invocation"]) is not int
                    or call["transport_invocation"] < max(1, last_invocation)
                    or type(call["authorized_tool_name"]) is not bool
                    or type(call["authorized_arguments"]) is not bool):
                raise ValueError
            last_invocation = call["transport_invocation"]
        seen = set()
        for row in rows:
            if (type(row) is not dict or any(type(row[key]) is not str
                    for key in ("tool_call_id", "name", "status", "code"))
                    or row["status"] not in {"success", "failed", "skipped"}
                    or row["tool_call_id"] in seen):
                raise ValueError
            seen.add(row["tool_call_id"])
    except (KeyError, TypeError, ValueError):
        calls, rows = [], []
        errors.append("malformed_call_evidence")
    if type(actual) is not dict:
        actual = {}
        errors.append("missing_orchestration_result")
    elif (not {"status", "code", "execution_status", "api_requests", "tool_rounds",
               "assistant_response", "tool_results"} <= actual.keys()
          or type(actual.get("status")) is not str
          or actual.get("status") not in {"completed", "failed"}
          or type(actual.get("code")) is not str
          or type(actual.get("execution_status")) is not str
          or actual.get("execution_status") not in {"success", "failed", "not_run"}
          or any(type(actual.get(key)) is not int or actual[key] < 0
                 for key in ("api_requests", "tool_rounds"))
          or (actual.get("assistant_response") is not None
              and type(actual["assistant_response"]) is not str)):
        errors.append("malformed_orchestration_evidence")
        actual = {}
    if actual:
        if (type(evidence.get("completion_attempts_observed")) is not int
                or actual["api_requests"] != evidence.get("completion_attempts_observed")
                or type(evidence.get("transport_invocations")) is not int
                or not 0 <= evidence["transport_invocations"] <= actual["api_requests"]
                or any(call["transport_invocation"] > evidence["transport_invocations"] for call in calls)):
            errors.append("incoherent_completion_counts")
        try:
            if actual["assistant_response"] is not None:
                actual["assistant_response"].encode("utf-8")
        except UnicodeError:
            errors.append("malformed_final_encoding")
            actual = {}
    return actual, calls, rows, errors


def _plan_index(rounds, plans):
    for index, plan in enumerate(plans):
        if len(rounds) != len(plan["rounds"]):
            continue
        if all((Counter(observed) == Counter(allowed) if plan["ordering"] == "any_within_round"
                else observed == allowed) for observed, allowed in zip(rounds, plan["rounds"])):
            return index
    return None


def _redundant(items, limits, id_key):
    counts, redundant = Counter(), []
    for item in items:
        counts[item["name"]] += 1
        # A forbidden first call is unnecessary, not a repetition.
        if counts[item["name"]] > max(1, limits.get(item["name"], 0)):
            redundant.append(item[id_key])
    return redundant


def _plan(calls, rows, plans, code, errors):
    batches = {}
    for call in calls:
        batches.setdefault(call["transport_invocation"], []).append(call)
    assigned = {}
    previous = -1
    for row in rows:
        index = next((i for i, call in enumerate(calls) if i not in assigned
                      and call["id"] == row["tool_call_id"] and call["name"] == row["name"]), None)
        if (index is None or index <= previous or not calls[index]["authorized_tool_name"]
                or not calls[index]["authorized_arguments"]):
            errors.append("unattributed_execution_result")
            continue
        previous = index
        assigned[index] = row
    executed_batches = {}
    for index in assigned:
        call = calls[index]
        executed_batches.setdefault(call["transport_invocation"], []).append(call["name"])
    rejected, limited, unresolved = [], [], []
    for invocation, batch in batches.items():
        executed = len(executed_batches.get(invocation, []))
        if 0 < executed < len(batch):
            errors.append("partial_batch_evidence")
        if not executed:
            # A terminal code explains only the last attempted batch.
            terminal = invocation == max(batches)
            if terminal and code == "invalid_tool_calls":
                rejected.append(invocation)
            elif terminal and code == "execution_limit_reached":
                limited.append(invocation)
            else:
                unresolved.append(invocation)
                errors.append("unexplained_unexecuted_batch")
    limits = Counter()
    for plan in plans:
        counts = Counter(name for batch in plan["rounds"] for name in batch)
        limits |= counts
    attempted_rounds = [[call["name"] for call in batch] for batch in batches.values()]
    executed_rounds = list(executed_batches.values())
    return {
        "attempted_rounds": attempted_rounds, "executed_rounds": executed_rounds,
        "attempt_plan_index": _plan_index(attempted_rounds, plans),
        "execution_plan_index": _plan_index(executed_rounds, plans),
        "attempted_count": len(calls), "executed_count": len(rows),
        "skipped_count": sum(row["status"] == "skipped" for row in rows),
        "authorized_attempt_ids": [call["id"] for call in calls
                                   if call["authorized_tool_name"] and call["authorized_arguments"]],
        "unauthorized_name_ids": [call["id"] for call in calls if not call["authorized_tool_name"]],
        "unauthorized_argument_ids": [call["id"] for call in calls
                                     if call["authorized_tool_name"] and not call["authorized_arguments"]],
        "redundant_attempt_ids": _redundant(calls, limits, "id"),
        "redundant_execution_ids": _redundant(rows, limits, "tool_call_id"),
        "unnecessary_attempt_ids": [call["id"] for call in calls if call["name"] not in limits],
        "unnecessary_execution_ids": [row["tool_call_id"] for row in rows if row["name"] not in limits],
        "unexecuted_attempt_ids": [call["id"] for i, call in enumerate(calls) if i not in assigned],
        "rejected_batches": rejected, "limit_blocked_batches": limited,
        "unresolved_batches": unresolved,
    }


def assess_observation(scenario, evidence, *, human_review=None):
    """Derive actual task handling; inputs are never mutated or executed.

    Well-formed unexpected observations are valid agent failures. Broken runner,
    fixture or evidence accounting yields invalid_run, retaining partial credit
    as descriptive counts. Bad review annotations raise ValueError.
    """
    if human_review not in (None, "pass", "fail"):
        raise ValueError("human_review must be None, pass or fail")
    review_required = scenario["human_review"]["required"]
    if human_review is not None and not review_required:
        raise ValueError("scenario does not require human review")
    review = (human_review or "pending") if review_required else "not_applicable"
    actual, calls, rows, errors = _read_evidence(scenario, evidence)
    operations = _operations(scenario["required_operations"], rows)
    plan = _plan(calls, rows, scenario["acceptable_plans"], actual.get("code"), errors)
    if actual and len(plan["executed_rounds"]) != actual["tool_rounds"]:
        errors.append("incoherent_execution_rounds")
    acceptable = [item for requirement in scenario["required_operations"]
                  for item in requirement["acceptable_results"] + requirement["acceptable_blocks"]]
    unexpected_rows = [row for row in rows if row["status"] != "success"
                       and not any(_matches(row, item) for item in acceptable)]
    completeness = {
        "applicable": bool(operations), "required_count": len(operations),
        "met_count": sum(item["state"] == "met" for item in operations),
        "handled_count": sum(item["state"] in {"met", "blocked_expected"} for item in operations),
    }
    code = actual.get("code", "")
    limits = (actual.get("api_requests", 0) <= adapter.MAX_API_REQUESTS
              and actual.get("tool_rounds", 0) <= adapter.MAX_TOOL_ROUNDS
              and len(rows) <= adapter.MAX_TOTAL_CALLS and code != "execution_limit_reached"
              and all(len(batch) <= adapter.MAX_TOTAL_CALLS for batch in plan["attempted_rounds"]))
    final = actual.get("assistant_response")
    final_delivered = (actual.get("status") == "completed" and type(final) is str and bool(final.strip())
                       and len(final.encode("utf-8")) <= adapter.MAX_ASSISTANT_BYTES)
    checks = {
        "required_operations_handled": completeness["handled_count"] == completeness["required_count"],
        "tool_selection_authorized": not (plan["unauthorized_name_ids"] or plan["unauthorized_argument_ids"]),
        "attempt_plan_allowed": plan["attempt_plan_index"] is not None,
        "execution_plan_allowed": plan["execution_plan_index"] is not None,
        "no_redundant_or_unnecessary_calls": not any(plan[key] for key in (
            "redundant_attempt_ids", "redundant_execution_ids", "unnecessary_attempt_ids", "unnecessary_execution_ids")),
        "within_execution_bounds": limits, "final_delivered": final_delivered,
        "no_unexpected_execution_failures": not unexpected_rows,
    }
    categories = set()
    if any(row["code"] in {"dataset_invalid", "knowledge_inconsistent"}
           and any(_matches(row, item) for item in acceptable) for row in rows):
        categories.add("expected_domain")
    if any(row["code"] in RESOURCE_CODES for row in rows):
        categories.add("resource_access")
    if code in AVAILABILITY_CODES or code.startswith("http_error_"):
        categories.add("provider_availability")
    if code in PROTOCOL_CODES:
        categories.add("provider_protocol")
    if not limits:
        categories.add("execution_limit")
    if not checks["tool_selection_authorized"] or code == "invalid_tool_calls":
        categories.add("tool_selection")
    if any(item["state"] == "missing" for item in operations):
        categories.add("missing_required_operations")
    if not checks["no_redundant_or_unnecessary_calls"]:
        categories.add("unnecessary_or_redundant_calls")
    if review_required:
        categories.add("explanation_review")
    if errors:
        categories.add("evaluation_infrastructure")
    deterministic = "invalid_run" if errors else ("pass" if all(checks.values()) else "fail")
    task = ("pending_review" if review == "pending" else review) if deterministic == "pass" and review_required else deterministic
    return {
        "evaluation_mode": "scripted_offline", "scenario_id": scenario["id"],
        "operations": operations, "completeness": completeness, "tool_plan": plan,
        "checks": checks, "deterministic_verdict": deterministic, "task_verdict": task,
        "human_review": review,
        "failure_categories": sorted(categories), "infrastructure_errors": sorted(set(errors)),
    }


def score_scenario(scenario, evidence, *, human_review=None):
    """Assess independently, then compare with the authored oracle.

    Recompute orchestration comparison; a stale runner comparison cannot conceal
    changed evidence. A runner-reported mismatch also remains visible. Intentionally
    failed tasks can pass expectations; infrastructure failures are not_evaluable.
    """
    score = assess_observation(scenario, evidence, human_review=human_review)
    if score["task_verdict"] == "invalid_run":
        score["expectation_verdict"] = "not_evaluable"
        score["expectation_mismatches"] = []
        return score
    expected = scenario["expected"]
    comparison = compare_orchestration(evidence["actual"], expected)
    mismatches = ["orchestration." + field for field in comparison["mismatches"]]
    runner_comparison = evidence.get("contract_comparison")
    if type(runner_comparison) is dict and runner_comparison.get("status") == "mismatched":
        mismatches.append("runner_contract_comparison")
    if score["task_verdict"] != expected["task_verdict"]:
        mismatches.append("task_verdict")
    handling = [{"operation": item["operation"], "state": item["state"]} for item in score["operations"]]
    if handling != expected["operation_handling"]:
        mismatches.append("operation_handling")
    score["expectation_verdict"] = "fail" if mismatches else "pass"
    score["expectation_mismatches"] = mismatches
    return score
