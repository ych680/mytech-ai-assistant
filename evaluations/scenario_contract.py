"""Strict version-1 contract for the sixteen offline evaluation scenarios.

This module validates definitions only. It never runs provider scripts, executes
tools, scores observations, or resolves human review. Expected outcomes are
authored oracles, never observations of an evaluated run. Scripts are JSON data.
"""

import json
from pathlib import Path
import re

from .fixtures import FIXTURE_IDS


DEFAULT_MANIFEST = Path(__file__).with_name("scenarios.json")
SCHEMA_VERSION = "1.0.0"
SCENARIO_IDS = frozenset(f"AE-{number:02d}" for number in range(1, 17))
TOOLS = frozenset({"validate_products", "check_knowledge"})
OPERATIONS = frozenset({"explicit_validate_products", "dataset_validation", "knowledge_inspection"})
RESULT_PAIRS = {
    "validate_products": {("success", "ok"), ("failed", "dataset_invalid")},
    "check_knowledge": {("success", "ok"), ("failed", "knowledge_inconsistent"),
                        ("skipped", "dataset_invalid")},
}
ORCHESTRATION_CODES = frozenset({
    "ok", "no_tools_executed", "tool_execution_failed", "invalid_tool_calls",
    "http_error_502", "execution_limit_reached",
})
REASONS = frozenset({
    "requirements_met", "no_tools_needed", "tools_required_bypass", "expected_dataset_invalid",
    "expected_knowledge_inconsistent", "expected_dependency_block", "unsupported_tool",
    "unauthorized_arguments", "missing_required_operation", "redundant_calls", "unnecessary_calls",
    "provider_failure", "final_delivery_missing", "human_review_required", "execution_limit",
})


class ManifestError(ValueError):
    """A definition has unknown fields, invalid values, or conflicting oracles."""


def _error(path, message):
    raise ManifestError(f"{path}: {message}")


def _fields(value, names, path):
    if type(value) is not dict or set(value) != set(names):
        _error(path, "expected exactly " + ", ".join(sorted(names)))


def _text(value, path, limit=8192):
    if type(value) is not str or not value.strip():
        _error(path, "expected a non-empty string")
    try:
        if len(value.encode("utf-8")) > limit:
            _error(path, "text exceeds byte limit")
    except UnicodeError:
        _error(path, "expected valid UTF-8 text")


def _choice(value, choices, path):
    if type(value) is not str or value not in choices:
        _error(path, "unsupported value")


def _version(value, path):
    if type(value) is not str or re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", value) is None:
        _error(path, "expected a major.minor.patch version without leading zeroes")


def _integer(value, minimum, maximum, path):
    if type(value) is not int or not minimum <= value <= maximum:
        _error(path, f"expected integer from {minimum} to {maximum}")


def _array(value, path, *, nonempty=True):
    if type(value) is not list or (nonempty and not value):
        _error(path, "expected " + ("non-empty " if nonempty else "") + "array")


def _evidence(value, path):
    _fields(value, {"name", "status", "code"}, path)
    _choice(value["name"], TOOLS, path + ".name")
    _choice(value["status"], {"success", "failed", "skipped"}, path + ".status")
    _text(value["code"], path + ".code", limit=64)
    if (value["status"], value["code"]) not in RESULT_PAIRS[value["name"]]:
        _error(path, "unsupported tool status/code pair")


def _script(script, path):
    _array(script, path)
    if len(script) > 3:
        _error(path, "at most three provider responses are supported")
    calls_by_id = {}
    unauthorized_steps = set()
    for index, step in enumerate(script):
        where = f"{path}[{index}]"
        if type(step) is not dict:
            _error(where, "expected a response specification object")
        _choice(step.get("type"), {"tool_calls", "final", "http_error"}, where + ".type")
        kind = step["type"]
        if kind == "tool_calls":
            _fields(step, {"type", "calls"}, where)
            _array(step["calls"], where + ".calls")
            if len(step["calls"]) > 8:
                _error(where, "a script batch supports at most eight calls")
            for offset, call in enumerate(step["calls"]):
                call_path = f"{where}.calls[{offset}]"
                _fields(call, {"id", "name", "arguments"}, call_path)
                call_id = call["id"]
                if type(call_id) is not str or re.fullmatch(r"[A-Za-z0-9_-]{1,128}", call_id) is None:
                    _error(call_path, "invalid call ID")
                if call_id in calls_by_id:
                    _error(call_path, "duplicate call ID")
                name = call["name"]
                if type(name) is not str or re.fullmatch(r"[a-z_]{1,64}", name) is None:
                    _error(call_path, "invalid scripted tool name")
                # Unsupported names/resource identifiers are intentional negative
                # data, permitted only with the rejected-batch outcome below.
                arguments = call["arguments"]
                keys = {"dataset", "knowledge"} if name == "check_knowledge" else {"dataset"}
                _fields(arguments, keys, call_path + ".arguments")
                for key, value in arguments.items():
                    _text(value, call_path + ".arguments." + key, limit=128)
                authorized = (name in TOOLS and arguments["dataset"] == "selected_dataset"
                              and (name != "check_knowledge" or arguments["knowledge"] == "selected_knowledge"))
                if not authorized:
                    unauthorized_steps.add(index)
                calls_by_id[call_id] = call
        else:
            if index != len(script) - 1:
                _error(where, "a final or HTTP error response must end the script")
            if kind == "final":
                _fields(step, {"type", "text"}, where)
                _text(step["text"], where + ".text", limit=16384)
            else:
                _fields(step, {"type", "status"}, where)
                if type(step["status"]) is not int or step["status"] != 502:
                    _error(where, "version 1 supports only the HTTP 502 scenario")
    return calls_by_id, unauthorized_steps


def _scenario(scenario, path):
    _fields(scenario, {"id", "version", "scenario_type", "request", "fixture_id", "script",
                       "required_operations", "acceptable_plans", "expected", "human_review"}, path)
    _choice(scenario["id"], SCENARIO_IDS, path + ".id")
    _version(scenario["version"], path + ".version")
    _choice(scenario["scenario_type"], {"tool_task", "no_tool_question"}, path + ".scenario_type")
    _text(scenario["request"], path + ".request")
    _choice(scenario["fixture_id"], FIXTURE_IDS, path + ".fixture_id")
    calls, unauthorized_steps = _script(scenario["script"], path + ".script")

    operations = scenario["required_operations"]
    _array(operations, path + ".required_operations", nonempty=False)
    seen_operations = set()
    for index, operation in enumerate(operations):
        where = f"{path}.required_operations[{index}]"
        _fields(operation, {"operation", "acceptable_results", "acceptable_blocks"}, where)
        name = operation["operation"]
        _choice(name, OPERATIONS, where + ".operation")
        if name in seen_operations:
            _error(where, "duplicate required operation")
        seen_operations.add(name)
        _array(operation["acceptable_results"], where + ".acceptable_results")
        _array(operation["acceptable_blocks"], where + ".acceptable_blocks", nonempty=False)
        for key in ("acceptable_results", "acceptable_blocks"):
            rows = operation[key]
            for row in rows:
                _evidence(row, where + "." + key)
                if key == "acceptable_blocks":
                    if name != "knowledge_inspection" or row != {
                        "name": "check_knowledge", "status": "skipped", "code": "dataset_invalid",
                    }:
                        _error(where, "only dependency-blocked knowledge inspection is an acceptable block")
                elif row["status"] == "skipped":
                    _error(where, "skipped results cannot satisfy a completed operation")
                if name == "explicit_validate_products" and row["name"] != "validate_products":
                    _error(where, "internal validation cannot replace an explicit validator call")
                if name == "knowledge_inspection" and row["name"] != "check_knowledge":
                    _error(where, "knowledge inspection requires check_knowledge")
                if name == "dataset_validation" and row["name"] == "check_knowledge" and row["code"] not in {"ok", "knowledge_inconsistent"}:
                    _error(where, "knowledge evidence must establish successful prerequisite validation")
            if len({json.dumps(row, sort_keys=True) for row in rows}) != len(rows):
                _error(where, "duplicate evidence predicate")
    if (scenario["scenario_type"] == "no_tool_question") != (not operations):
        _error(path, "only no-tool questions may have no required operations")

    plans = scenario["acceptable_plans"]
    _array(plans, path + ".acceptable_plans")
    seen_plans = set()
    for plan in plans:
        _fields(plan, {"rounds", "ordering"}, path + ".acceptable_plans")
        _choice(plan["ordering"], {"exact", "any_within_round"}, path + ".acceptable_plans.ordering")
        _array(plan["rounds"], path + ".acceptable_plans.rounds", nonempty=False)
        if len(plan["rounds"]) > 2:
            _error(path, "an acceptable plan cannot exceed two tool rounds")
        flattened = []
        for batch in plan["rounds"]:
            _array(batch, path + ".acceptable_plans.rounds[]")
            for name in batch:
                _choice(name, TOOLS, path + ".acceptable_plans.tool")
            flattened.extend(batch)
        if len(flattened) > 8 or len(flattened) != len(set(flattened)):
            _error(path, "acceptable plans cannot contain redundant or excess calls")
        if (not operations) != (not flattened):
            _error(path, "acceptable plan must agree with whether tools are required")
        for operation in operations:
            if not any(row["name"] in flattened for row in operation["acceptable_results"]):
                _error(path, "acceptable plan omits a required operation")
        canonical_rounds = [sorted(batch) if plan["ordering"] == "any_within_round" else batch for batch in plan["rounds"]]
        signature = json.dumps(canonical_rounds)
        if signature in seen_plans:
            _error(path, "duplicate acceptable plan")
        seen_plans.add(signature)

    expected = scenario["expected"]
    _fields(expected, {"orchestration", "tool_results", "operation_handling", "task_verdict",
                       "evaluation_expectation_verdict", "reason_codes"}, path + ".expected")
    outcome = expected["orchestration"]
    _fields(outcome, {"status", "code", "execution_status", "api_requests", "tool_rounds"}, path + ".expected.orchestration")
    _choice(outcome["status"], {"completed", "failed"}, path + ".expected.status")
    _choice(outcome["code"], ORCHESTRATION_CODES, path + ".expected.code")
    _choice(outcome["execution_status"], {"not_run", "success", "failed"}, path + ".expected.execution_status")
    _integer(outcome["api_requests"], 1, 3, path + ".expected.api_requests")
    _integer(outcome["tool_rounds"], 0, 2, path + ".expected.tool_rounds")
    if outcome["api_requests"] != len(scenario["script"]):
        _error(path, "expected attempts must match this script's response count")
    terminal = scenario["script"][-1]["type"]
    if (outcome["status"] == "completed") != (terminal == "final"):
        _error(path, "orchestration status conflicts with the terminal script step")
    if terminal == "http_error" and outcome["code"] != "http_error_502":
        _error(path, "HTTP 502 script requires its matching outcome code")
    if unauthorized_steps and unauthorized_steps != {len(scenario["script"]) - 1}:
        _error(path, "unauthorized calls must occur in the terminal rejected batch")
    if bool(unauthorized_steps) != (outcome["code"] == "invalid_tool_calls"):
        _error(path, "unauthorized scripted calls require a matching rejected-batch oracle")
    if terminal == "tool_calls" and outcome["code"] not in {"invalid_tool_calls", "execution_limit_reached"}:
        _error(path, "terminal tool calls require a rejection or limit oracle")
    if outcome["code"] == "execution_limit_reached" and (
        terminal != "tool_calls" or (len(scenario["script"]) < 3 and len(calls) <= 8)
    ):
        _error(path, "limit oracle must request calls beyond the round/request/call bounds")

    rows = expected["tool_results"]
    _array(rows, path + ".expected.tool_results", nonempty=False)
    seen_results = set()
    for row in rows:
        _fields(row, {"tool_call_id", "name", "status", "code"}, path + ".expected.tool_results[]")
        _evidence({key: row[key] for key in ("name", "status", "code")}, path + ".expected.tool_results[]")
        call_id = row["tool_call_id"]
        if type(call_id) is not str or call_id not in calls or call_id in seen_results or calls[call_id]["name"] != row["name"]:
            _error(path, "result must reference a unique matching scripted call")
        seen_results.add(call_id)
    aggregate = "not_run" if not rows else ("success" if all(row["status"] == "success" for row in rows) else "failed")
    if outcome["execution_status"] != aggregate:
        _error(path, "aggregate execution status conflicts with expected tool results")
    # Every earlier script step is an accepted tool batch; the terminal step is
    # a final answer, provider error, or rejected batch. Check authored evidence
    # references without running a tool or assessing any actual agent behavior.
    accepted_steps = scenario["script"][:-1]
    accepted_ids = [call["id"] for step in accepted_steps for call in step["calls"]]
    if [row["tool_call_id"] for row in rows] != accepted_ids:
        _error(path, "expected results must preserve all accepted calls and exclude rejected calls")
    if outcome["tool_rounds"] != len(accepted_steps):
        _error(path, "tool rounds conflict with the accepted script batches")
    if outcome["status"] == "completed":
        code = "no_tools_executed" if not rows else ("ok" if aggregate == "success" else "tool_execution_failed")
        if outcome["code"] != code:
            _error(path, "completed orchestration code conflicts with expected results")

    handling = expected["operation_handling"]
    _array(handling, path + ".expected.operation_handling", nonempty=False)
    handled = set()
    for row in handling:
        _fields(row, {"operation", "state"}, path + ".expected.operation_handling[]")
        _choice(row["operation"], seen_operations, path + ".expected.operation_handling.operation")
        _choice(row["state"], {"met", "blocked_expected", "missing"}, path + ".expected.operation_handling.state")
        if row["operation"] in handled:
            _error(path, "duplicate expected operation handling")
        handled.add(row["operation"])
        requirement = next(op for op in operations if op["operation"] == row["operation"])
        if row["state"] != "missing":
            predicates = requirement["acceptable_blocks" if row["state"] == "blocked_expected" else "acceptable_results"]
            if not any(all(actual[key] == predicate[key] for key in predicate) for predicate in predicates for actual in rows):
                _error(path, "expected operation state lacks supporting result evidence")
        elif any(
            all(actual[key] == predicate[key] for key in predicate)
            for predicate in requirement["acceptable_results"] + requirement["acceptable_blocks"]
            for actual in rows
        ):
            _error(path, "an operation with acceptable evidence cannot be marked missing")
    if handled != seen_operations:
        _error(path, "expected handling must cover every required operation")
    _choice(expected["task_verdict"], {"pass", "fail", "pending_review"}, path + ".expected.task_verdict")
    if expected["evaluation_expectation_verdict"] != "pass":
        _error(path, "authored scenarios must expect a passing evaluation-expectation check")
    _array(expected["reason_codes"], path + ".expected.reason_codes")
    for reason in expected["reason_codes"]:
        _choice(reason, REASONS, path + ".expected.reason_codes[]")
    if len(set(expected["reason_codes"])) != len(expected["reason_codes"]):
        _error(path, "duplicate reason code")
    if expected["task_verdict"] != "fail" and (outcome["status"] != "completed" or any(row["state"] == "missing" for row in handling)):
        _error(path, "missing operations or failed delivery cannot pass task satisfaction")

    review = scenario["human_review"]
    _fields(review, {"required", "scope", "state", "anticipated_outcome"}, path + ".human_review")
    if type(review["required"]) is not bool:
        _error(path, "human_review.required must be boolean")
    if review["required"]:
        _choice(review["scope"], {"answer_correctness", "explanation_consistency"}, path + ".human_review.scope")
        if review["state"] != "pending":
            _error(path, "semantic review remains pending without an explicit review annotation")
        _choice(review["anticipated_outcome"], {"pass", "fail"}, path + ".human_review.anticipated_outcome")
        if expected["task_verdict"] == "pass":
            _error(path, "required pending review cannot produce a final task pass")
    elif review != {"required": False, "scope": "none", "state": "not_required", "anticipated_outcome": None}:
        _error(path, "non-required review must have no outcome annotation")
    elif expected["task_verdict"] == "pending_review":
        _error(path, "pending task verdict requires human review")


def validate_manifest(manifest):
    """Validate without changing input; return the manifest for convenient loading."""
    _fields(manifest, {"schema_version", "manifest_version", "scenarios"}, "manifest")
    if manifest["schema_version"] != SCHEMA_VERSION:
        _error("manifest.schema_version", "unsupported schema version")
    _version(manifest["manifest_version"], "manifest.manifest_version")
    _array(manifest["scenarios"], "manifest.scenarios")
    seen = set()
    for index, scenario in enumerate(manifest["scenarios"]):
        _scenario(scenario, f"manifest.scenarios[{index}]")
        if scenario["id"] in seen:
            _error("manifest.scenarios", "duplicate scenario ID")
        seen.add(scenario["id"])
    if seen != SCENARIO_IDS:
        _error("manifest.scenarios", "version 1 requires exactly AE-01 through AE-16")
    return manifest


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ManifestError("Duplicate JSON field")
        result[key] = value
    return result


def _reject_constant(value):
    raise ManifestError("Non-standard JSON constants are forbidden")


def load_manifest(path=DEFAULT_MANIFEST):
    """Read a trusted local UTF-8 manifest; no scripts or fixtures are executed."""
    try:
        manifest = json.loads(Path(path).read_text(encoding="utf-8"),
                              object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except (OSError, UnicodeError, ValueError, RecursionError) as error:
        raise ManifestError("Could not load a valid JSON scenario manifest") from error
    return validate_manifest(manifest)
