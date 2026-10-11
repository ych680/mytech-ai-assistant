"""Bounded scripted offline execution and in-memory evidence, without scoring.

run_scenario(id, *, manifest_path=...) and run_all_scenarios(*, manifest_path=...)
load the complete validated manifest. Invalid configuration raises a sanitized
EvaluationInfrastructureError before any execution. Per-case infrastructure
failures return evidence with runner_status=infrastructure_failure.

Only the actual orchestration contract is compared with its authored oracle;
task satisfaction and explanation consistency are deliberately not assessed.
The optional CLI prints a brief execution check and writes no report files.
"""

import argparse
from copy import deepcopy
import json
import urllib.request

from tools import tool3_tokenproxy as adapter
from .fixtures import FixtureError, prepare_fixture
from .scenario_contract import DEFAULT_MANIFEST, ManifestError, load_manifest


OFFLINE_MARKER = "offline-evaluation-marker"
OUTCOME_FIELDS = ("status", "code", "execution_status", "api_requests", "tool_rounds")
RESULT_FIELDS = ("tool_call_id", "name", "status", "code")


class EvaluationInfrastructureError(RuntimeError):
    """Sanitized evaluation failure; never include exception text or requests."""

    failure_category = "evaluation_infrastructure"

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _response(step):
    """Translate response DATA only; never evaluate expressions or import names."""
    if type(step) is not dict:
        raise EvaluationInfrastructureError("invalid_script")
    kind = step.get("type")
    if kind == "http_error" and set(step) == {"type", "status"}:
        if type(step["status"]) is int and step["status"] == 502:
            return adapter.HTTPResponse(502, b"")
        raise EvaluationInfrastructureError("invalid_script")
    elif kind == "final" and set(step) == {"type", "text"}:
        text = step["text"]
        if type(text) is str and text.strip() and len(text.encode("utf-8")) <= adapter.MAX_ASSISTANT_BYTES:
            message = {"role": "assistant", "content": text}
            finish_reason = "stop"
        else:
            raise EvaluationInfrastructureError("invalid_script")
    elif kind == "tool_calls" and set(step) == {"type", "calls"}:
        if type(step["calls"]) is not list or not 1 <= len(step["calls"]) <= 8:
            raise EvaluationInfrastructureError("invalid_script")
        calls = []
        for call in step["calls"]:
            if (type(call) is not dict or set(call) != {"id", "name", "arguments"}
                    or type(call["id"]) is not str or type(call["name"]) is not str
                    or type(call["arguments"]) is not dict
                    or any(type(key) is not str or type(value) is not str
                           for key, value in call["arguments"].items())):
                raise EvaluationInfrastructureError("invalid_script")
            calls.append({"id": call["id"], "type": "function", "function": {
                "name": call["name"],
                "arguments": json.dumps(call["arguments"], ensure_ascii=True,
                                        allow_nan=False, separators=(",", ":")),
            }})
        message = {"role": "assistant", "content": None, "tool_calls": calls}
        finish_reason = "tool_calls"
    else:
        raise EvaluationInfrastructureError("invalid_script")
    body = json.dumps({"choices": [{"message": message, "finish_reason": finish_reason}]},
                      ensure_ascii=True, allow_nan=False, separators=(",", ":")).encode("utf-8")
    if len(body) > adapter.MAX_RESPONSE_BYTES:
        raise EvaluationInfrastructureError("invalid_script")
    return adapter.HTTPResponse(200, body)


class ScriptedTransport:
    """Injected local transport, not an HTTP client.

    Observations contain only response-emitted tool names/IDs and step numbers.
    Incoming headers, request bodies, request objects and intermediate assistant
    content are never retained. Consumed raw response bodies are discarded.
    Empty/truncated scripts are permitted here so exhaustion is observable;
    the public runner always validates its entire manifest first.
    """

    def __init__(self, steps):
        if type(steps) is not list or len(steps) > adapter.MAX_API_REQUESTS:
            raise EvaluationInfrastructureError("invalid_script")
        try:
            self._responses = [_response(step) for step in steps]
        except EvaluationInfrastructureError:
            raise
        except Exception:
            raise EvaluationInfrastructureError("invalid_script") from None
        self.steps_total = len(steps)
        self.steps_consumed = 0
        self.transport_invocations = 0
        self.tool_calls = []
        self.failure_codes = []

    def _fail(self, code):
        if code not in self.failure_codes:
            self.failure_codes.append(code)
        # TokenProxyClient sanitizes this exception into transport_error. The
        # independent flag is authoritative for evaluation-infrastructure failure.
        raise EvaluationInfrastructureError(code)

    def __call__(self, request, *, timeout, max_response_bytes):
        self.transport_invocations += 1
        if (type(request) is not urllib.request.Request
                or request.full_url != adapter.API_URL or request.get_method() != "POST"
                or timeout != adapter.HTTP_TIMEOUT_SECONDS
                or max_response_bytes != adapter.MAX_RESPONSE_BYTES):
            self._fail("unexpected_transport_request")
        if not self._responses:
            self._fail("script_exhausted")
        response = self._responses.pop(0)
        self.steps_consumed += 1
        if response.status == 200:
            message = json.loads(response.body)["choices"][0]["message"]
            for call in message.get("tool_calls", []):
                self.tool_calls.append({
                    "transport_invocation": self.transport_invocations,
                    "script_step": self.steps_consumed,
                    "id": call["id"], "name": call["function"]["name"],
                })
        return response


class _ObservedClient:
    """Count real complete() invocations and retain only actual tool feedback.

    If orchestration unexpectedly raises without returning, prior role:tool
    feedback is still observable here. It cannot expose a batch that failed
    before the orchestrator supplied its results to a subsequent completion.
    """

    def __init__(self, client):
        self.client = client
        self.completion_attempts = 0
        self.tool_feedback = []

    def complete(self, messages, *, allow_tools=True):
        self.completion_attempts += 1
        self.tool_feedback = [
            json.loads(message["content"]) for message in messages if message["role"] == "tool"
        ]
        return self.client.complete(messages, allow_tools=allow_tools)


def compare_orchestration(actual, expected):
    """Compare only outcome fields and ordered result identities/statuses/codes.

    Returns mismatch field paths, never a task verdict or human-review decision.
    Diagnostics, result data and the cleaned explanation remain actual evidence;
    the manifest does not define exact-text expectations for those fields.
    """
    mismatches = [
        key for key in OUTCOME_FIELDS
        if type(actual[key]) is not type(expected["orchestration"][key])
        or actual[key] != expected["orchestration"][key]
    ]
    rows, reference = actual["tool_results"], expected["tool_results"]
    if len(rows) != len(reference):
        mismatches.append("tool_results.length")
    for index, (row, authored) in enumerate(zip(rows, reference)):
        mismatches.extend(f"tool_results[{index}].{key}" for key in RESULT_FIELDS
                          if row[key] != authored[key])
    return {"status": "mismatched" if mismatches else "matched", "mismatches": mismatches}


def _execute(scenario):
    evidence = {
        "evaluation_mode": "scripted_offline",
        "scenario_id": scenario["id"], "scenario_version": scenario["version"],
        "fixture": {
            "id": scenario["fixture_id"], "dataset_sha256": None, "knowledge_sha256": None,
            "source_dataset_sha256": None, "source_knowledge_sha256": None,
            "integrity": "not_prepared", "cleanup": "not_prepared",
        },
        "actual": None, "completion_attempts_observed": 0,
        "transport_invocations": 0, "tool_calls": [], "partial_tool_results": [],
        "script": {"steps_total": len(scenario["script"]), "steps_consumed": 0, "steps_remaining": len(scenario["script"])},
        "runner_status": "infrastructure_failure", "infrastructure_failures": [],
        "contract_comparison": {"status": "not_checked", "mismatches": []},
    }
    transport = client = root = None

    def failure(code):
        if code not in evidence["infrastructure_failures"]:
            evidence["infrastructure_failures"].append(code)

    try:
        transport = ScriptedTransport(scenario["script"])
        client = _ObservedClient(adapter.TokenProxyClient(OFFLINE_MARKER, transport=transport))
        with prepare_fixture(scenario["fixture_id"]) as fixture:
            root = fixture.bindings.dataset_path.parent
            evidence["fixture"]["integrity"] = "not_checked"
            for key in ("dataset_sha256", "knowledge_sha256", "source_dataset_sha256", "source_knowledge_sha256"):
                evidence["fixture"][key] = getattr(fixture, key)
            try:
                evidence["actual"] = adapter.orchestrate(
                    scenario["request"], client=client, bindings=fixture.bindings,
                )
            except Exception:
                failure("runner_exception")
        # The fixture context verifies both prepared resources and original
        # source bytes before cleaning its directory, including on exceptions.
        evidence["fixture"]["integrity"] = "passed"
    except EvaluationInfrastructureError as error:
        failure(error.code)
    except FixtureError:
        if root is not None:
            evidence["fixture"]["integrity"] = "failed"
        failure("fixture_failure")
    except Exception:
        failure("runner_exception")

    if root is not None:
        try:
            evidence["fixture"]["cleanup"] = "failed" if root.exists() else "passed"
        except OSError:
            evidence["fixture"]["cleanup"] = "failed"
        if evidence["fixture"]["cleanup"] == "failed":
            failure("fixture_cleanup_failed")
    if client is not None:
        evidence["completion_attempts_observed"] = client.completion_attempts
        if evidence["actual"] is None:
            evidence["partial_tool_results"] = deepcopy(client.tool_feedback)
    if transport is not None:
        evidence["transport_invocations"] = transport.transport_invocations
        evidence["tool_calls"] = deepcopy(transport.tool_calls)
        evidence["script"] = {
            "steps_total": transport.steps_total, "steps_consumed": transport.steps_consumed,
            "steps_remaining": transport.steps_total - transport.steps_consumed,
        }
        for code in transport.failure_codes:
            failure(code)
        if evidence["script"]["steps_remaining"] and evidence["completion_attempts_observed"]:
            failure("unconsumed_script_steps")
    if evidence["actual"] is not None:
        try:
            if evidence["actual"]["code"] in {
                "invalid_response_json", "invalid_assistant_message", "empty_assistant_response",
                "invalid_thinking_markup", "invalid_http_response", "response_too_large",
                "transport_error", "network_error", "request_timeout",
            }:
                failure("invalid_script_response")
            if evidence["actual"]["api_requests"] != evidence["completion_attempts_observed"]:
                failure("completion_accounting_mismatch")
            evidence["contract_comparison"] = compare_orchestration(evidence["actual"], scenario["expected"])
        except Exception:
            failure("invalid_orchestration_result")
            evidence["actual"] = None
            if client is not None:
                evidence["partial_tool_results"] = deepcopy(client.tool_feedback)
    elif not evidence["infrastructure_failures"]:
        failure("missing_orchestration_result")
    if evidence["actual"] is not None and not evidence["infrastructure_failures"]:
        evidence["runner_status"] = "completed"
    return evidence


def _manifest(path):
    try:
        return load_manifest(path)
    except ManifestError:
        raise EvaluationInfrastructureError("invalid_manifest") from None
    except Exception:
        raise EvaluationInfrastructureError("manifest_load_failure") from None


def run_scenario(scenario_id, *, manifest_path=DEFAULT_MANIFEST):
    """Execute one validated scenario; no expected task/review fields are copied."""
    manifest = _manifest(manifest_path)
    for scenario in manifest["scenarios"]:
        if scenario["id"] == scenario_id:
            return _execute(scenario)
    raise EvaluationInfrastructureError("unknown_scenario")


def run_all_scenarios(*, manifest_path=DEFAULT_MANIFEST):
    """Execute all sixteen in manifest order, each with its own isolated fixture."""
    return [_execute(scenario) for scenario in _manifest(manifest_path)["scenarios"]]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario_id", nargs="?", help="Run one scenario; default: all sixteen")
    args = parser.parse_args(argv)
    try:
        cases = [run_scenario(args.scenario_id)] if args.scenario_id else run_all_scenarios()
    except EvaluationInfrastructureError as error:
        print("Evaluation infrastructure failure: " + error.code)
        return 1
    print("scripted_offline: execution contract verification; no task or explanation scoring")
    for case in cases:
        actual = case["actual"]
        outcome = (f"{actual['status']}/{actual['code']}; execution={actual['execution_status']}; "
                   f"attempts={actual['api_requests']}; rounds={actual['tool_rounds']}") if actual else "no orchestration result"
        print(f"{case['scenario_id']}: {outcome}; transport={case['transport_invocations']}; "
              f"runner={case['runner_status']}; contract={case['contract_comparison']['status']}")
    return 0 if all(case["runner_status"] == "completed" and case["contract_comparison"]["status"] == "matched"
                    for case in cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
