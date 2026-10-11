"""Versioned evidence reporting for the sixteen scripted offline scenarios.

generate_report() runs the existing runner inside a verified offline boundary and
uses the existing scorer. build_report(manifest, evidence, *, repository=None,
offline_transport_verified=False) projects approved fields only. render_markdown
and write_report consume that same JSON-compatible report, never rescore it.

Schema 1.0.0 and scoring_rules_version 1.0.0 identify the approved Phase 2C
contract. Bump these declarations when adopting incompatible reporting or scoring
rules. Metadata deliberately omits timestamps, hostnames, paths and random IDs;
identical evidence, source revision/state and runtime produce identical bytes.

No final explanation text, diagnostics, result data, raw arguments, scripts,
requests or headers are included. Their omission also avoids persisting hidden
reasoning or arbitrary exception details. Task pass establishes deterministic
handling only, not full semantic explanation correctness. Required human reviews
remain pending. Future explicit annotations can disagree with the pending oracle;
such expectation mismatches do not by themselves indicate broken infrastructure.

Writes require an explicit directory and use exclusive creation for both files.
On ordinary write failures, only files created by this call are rolled back.
The pair is not a crash-atomic transaction. Offline guards are process-wide and
intended for this serial CLI, not concurrent live-provider work in the same process.
"""

import argparse
from collections import Counter
from contextlib import ExitStack
import json
from pathlib import Path
import platform
import re
import subprocess
from unittest.mock import patch

from tools import tool3_tokenproxy as adapter
from . import run_tool3 as runner
from .scenario_contract import load_manifest, validate_manifest
from .score_tool3 import score_scenario


SCHEMA_VERSION = "1.0.0"
SCORING_RULES_VERSION = "1.0.0"
REPORT_KIND = "mytech_tool3_evaluation_evidence"
JSON_FILENAME = "tool3-evaluation.json"
MARKDOWN_FILENAME = "tool3-evaluation.md"
NOTICE = ("Scripted offline results validate evaluation behavior under controlled responses. "
          "They do not measure empirical LLM accuracy.")
REVIEW_BOUNDARY = (
    "Deterministic task pass does not establish full semantic correctness of final explanations. "
    "Required human reviews remain pending; anticipated outcomes are not judgments. "
    "Future explicit review annotations may disagree with a pending baseline oracle without "
    "indicating an evaluation infrastructure failure."
)
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TASK_VERDICTS = ("pass", "fail", "pending_review", "invalid_run")
EXPECTATION_VERDICTS = ("pass", "fail", "not_evaluable")
CHECK_FIELDS = (
    "required_operations_handled", "tool_selection_authorized", "attempt_plan_allowed",
    "execution_plan_allowed", "no_redundant_or_unnecessary_calls", "within_execution_bounds",
    "final_delivered", "no_unexpected_execution_failures",
)
PLAN_ID_FIELDS = (
    "authorized_attempt_ids", "unauthorized_name_ids", "unauthorized_argument_ids",
    "redundant_attempt_ids", "redundant_execution_ids", "unnecessary_attempt_ids",
    "unnecessary_execution_ids", "unexecuted_attempt_ids",
)


class ReportError(RuntimeError):
    """A bounded error code, never an underlying exception message or path."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _token(value):
    if value is None:
        return None
    return value if type(value) is str and re.fullmatch(r"[A-Za-z0-9_.\[\]-]{1,160}", value) else "redacted"


def _number(value):
    return value if type(value) is int and value >= 0 else None


def _boolean(value):
    return value if type(value) is bool else None


def _hash(value):
    return value if type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) else None


def _tokens(values):
    return [_token(value) for value in values]


def collect_repository_state():
    """Read fixed Git metadata locally; unavailable facts are null, never guessed."""
    def git(*args):
        try:
            result = subprocess.run(["git", *args], cwd=REPOSITORY_ROOT, capture_output=True,
                                    text=True, timeout=5, check=False)
            return result.stdout.strip() if result.returncode == 0 else None
        except (OSError, subprocess.SubprocessError, UnicodeError):
            return None

    revision = git("rev-parse", "--verify", "HEAD")
    if revision is not None and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", revision) is None:
        revision = None
    status = git("status", "--porcelain=v1", "--untracked-files=normal")
    return {"revision": revision, "dirty": bool(status) if status is not None else None}


class _OfflineBoundary:
    """Verify actual transport injection and invocations, with no network fallback."""

    def __init__(self):
        self.scripted_invocations = 0
        self.verified_clients = 0
        self.unverified_clients = 0
        self.blocked_attempts = 0

    def deny(self, *args, **kwargs):
        self.blocked_attempts += 1
        raise ReportError("offline_boundary_violation")

    def install(self, stack):
        real_transport = runner.ScriptedTransport.__call__
        real_init = adapter.TokenProxyClient.__init__

        def observe_transport(transport, *args, **kwargs):
            self.scripted_invocations += 1
            return real_transport(transport, *args, **kwargs)

        def observe_client(client, api_key, *, transport=None):
            if type(transport) is runner.ScriptedTransport:
                self.verified_clients += 1
            else:
                self.unverified_clients += 1
            real_init(client, api_key, transport=transport)

        for target in ("socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex",
                       "urllib.request.urlopen", "urllib.request.OpenerDirector.open",
                       "tools.tool3_tokenproxy.http_transport", "tools.tool3_tokenproxy.getpass.getpass"):
            stack.enter_context(patch(target, side_effect=self.deny))
        stack.enter_context(patch.object(runner.ScriptedTransport, "__call__", observe_transport))
        stack.enter_context(patch.object(adapter.TokenProxyClient, "__init__", observe_client))

    def verified(self, evidence):
        return (self.blocked_attempts == 0 and self.unverified_clients == 0
                and self.verified_clients == len(evidence)
                and all(type(case.get("transport_invocations")) is int for case in evidence)
                and self.scripted_invocations == sum(case["transport_invocations"] for case in evidence))


def _project_scenario(scenario, evidence, verified):
    score = score_scenario(scenario, evidence)
    actual = evidence["actual"]
    returned = type(actual) is dict
    rows = actual["tool_results"] if returned else evidence["partial_tool_results"]
    actual = actual if returned else {}
    fixture = evidence["fixture"]
    plan = score["tool_plan"]
    plan_projection = {
        key: [[_token(name) for name in batch] for batch in plan[key]]
        for key in ("attempted_rounds", "executed_rounds")
    }
    plan_projection.update({key: _number(plan[key]) for key in (
        "attempt_plan_index", "execution_plan_index", "attempted_count", "executed_count", "skipped_count")})
    plan_projection.update({key: _tokens(plan[key]) for key in PLAN_ID_FIELDS})
    plan_projection.update({key: [_number(value) for value in plan[key]] for key in (
        "rejected_batches", "limit_blocked_batches", "unresolved_batches")})
    return {
        "scenario_id": _token(scenario["id"]), "scenario_version": _token(scenario["version"]),
        "fixture": {
            "id": _token(fixture["id"]),
            **{key: _hash(fixture[key]) for key in ("dataset_sha256", "knowledge_sha256",
                 "source_dataset_sha256", "source_knowledge_sha256")},
            "integrity": _token(fixture["integrity"]), "cleanup": _token(fixture["cleanup"]),
        },
        "provenance": {
            "attempted_tool_calls": "scripted_transport_native_response",
            "tool_results": "orchestration_return" if returned else "observed_tool_feedback",
            "assessment": "score_tool3.score_scenario",
        },
        "attempted_tool_calls": [{
            "id": _token(call["id"]), "name": _token(call["name"]),
            "transport_invocation": _number(call["transport_invocation"]),
            "script_step": _number(call["script_step"]),
            "authorized_tool_name": _boolean(call["authorized_tool_name"]),
            "authorized_arguments": _boolean(call["authorized_arguments"]),
        } for call in evidence["tool_calls"]],
        "tool_results": [{key: _token(row[key]) for key in runner.RESULT_FIELDS} for row in rows],
        "orchestration": {
            "status": _token(actual.get("status")), "code": _token(actual.get("code")),
            "execution_status": _token(actual.get("execution_status")),
            "api_requests": _number(actual.get("api_requests")),
            "tool_rounds": _number(actual.get("tool_rounds")),
        },
        "completion_attempts": _number(evidence["completion_attempts_observed"]),
        "transport_invocations": _number(evidence["transport_invocations"]),
        "actual_network_requests": 0 if verified else None,
        "runner_status": _token(evidence["runner_status"]),
        "operations": [{"operation": _token(item["operation"]), "state": _token(item["state"]),
                        "tool_result_ids": _tokens(item["tool_result_ids"])} for item in score["operations"]],
        "completeness": {"applicable": _boolean(score["completeness"]["applicable"]),
                         **{key: _number(score["completeness"][key]) for key in (
                             "required_count", "met_count", "handled_count")}},
        "execution_plan": plan_projection,
        "checks": {key: _boolean(score["checks"][key]) for key in CHECK_FIELDS},
        "failure_categories": _tokens(score["failure_categories"]),
        "deterministic_verdict": _token(score["deterministic_verdict"]),
        "task_verdict": _token(score["task_verdict"]),
        "expectation_verdict": _token(score["expectation_verdict"]),
        "expectation_mismatches": _tokens(score["expectation_mismatches"]),
        "human_review": _token(score["human_review"]),
        "infrastructure_errors": {
            "runner": _tokens(evidence["infrastructure_failures"]),
            "scorer": _tokens(score["infrastructure_errors"]),
        },
    }


def build_report(manifest, evidence, *, repository=None, offline_transport_verified=False):
    """Build only in memory, in manifest order. No implicit claim of zero network.

    The verification flag is supplied only by a caller that observed the offline
    boundary; evaluation_mode alone is insufficient. Imported observations default
    to unknown network counts. No human annotations are accepted in this phase.
    """
    try:
        validate_manifest(manifest)
        by_id = {case["scenario_id"]: case for case in evidence}
        if (len(evidence) != len(by_id) or set(by_id) != {s["id"] for s in manifest["scenarios"]}
                or type(offline_transport_verified) is not bool):
            raise ReportError("invalid_report_evidence")
        records = [_project_scenario(s, by_id[s["id"]], offline_transport_verified)
                   for s in manifest["scenarios"]]
        tasks = Counter(record["task_verdict"] for record in records)
        expectations = Counter(record["expectation_verdict"] for record in records)
        repository = repository or {}
        revision = repository.get("revision")
        if type(revision) is not str or re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", revision) is None:
            revision = None
        return {
            "schema_version": SCHEMA_VERSION, "report_kind": REPORT_KIND,
            "evaluation_mode": "scripted_offline", "notice": NOTICE, "human_review_boundary": REVIEW_BOUNDARY,
            "manifest_version": manifest["manifest_version"], "manifest_schema_version": manifest["schema_version"],
            "scoring_rules_version": SCORING_RULES_VERSION,
            "repository": {"revision": revision, "dirty": _boolean(repository.get("dirty"))},
            "runtime": {"python_version": platform.python_version(), "platform": {
                "system": platform.system(), "release": platform.release(), "machine": platform.machine()}},
            "execution_limits": {"completion_attempts": adapter.MAX_API_REQUESTS,
                "tool_rounds": adapter.MAX_TOOL_ROUNDS, "total_tool_calls": adapter.MAX_TOTAL_CALLS,
                "assistant_bytes": adapter.MAX_ASSISTANT_BYTES, "response_bytes": adapter.MAX_RESPONSE_BYTES,
                "conversation_bytes": adapter.MAX_CONVERSATION_BYTES},
            "offline_transport_verified": offline_transport_verified,
            "actual_network_requests": 0 if offline_transport_verified else None,
            "scenario_count": len(records),
            "totals": {"task_verdicts": {key: tasks[key] for key in TASK_VERDICTS},
                       "expectation_verdicts": {key: expectations[key] for key in EXPECTATION_VERDICTS}},
            "scenarios": records,
        }
    except ReportError:
        raise
    except Exception:
        raise ReportError("report_generation_failed") from None


def generate_report():
    """Execute all scenarios once, score, and project. No output files are written."""
    try:
        manifest = load_manifest()
        boundary = _OfflineBoundary()
        with ExitStack() as stack:
            boundary.install(stack)
            evidence = runner.run_all_scenarios()
        return build_report(manifest, evidence, repository=collect_repository_state(),
                            offline_transport_verified=boundary.verified(evidence))
    except ReportError:
        raise
    except Exception:
        raise ReportError("report_generation_failed") from None


def serialize_report(report):
    """Stable UTF-8-compatible JSON text, with sorted keys and one trailing LF."""
    try:
        return json.dumps(report, ensure_ascii=True, allow_nan=False, sort_keys=True, indent=2) + "\n"
    except (TypeError, ValueError, RecursionError):
        raise ReportError("report_serialization_failed") from None


def _cell(value):
    if value is None:
        return "unknown"
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(
        ">", "&gt;").replace("|", "&#124;").replace("`", "&#96;").replace("\n", " ").replace("\r", " ")[:512]


def render_markdown(report):
    """Render the supplied report only; no execution, scoring or oracle reads."""
    try:
        lines = ["# MyTech Tool 3 Evaluation Evidence", "", "> " + _cell(report["notice"]), "",
                 _cell(report["human_review_boundary"]), "",
                 f"Schema: {_cell(report['schema_version'])}; manifest: {_cell(report['manifest_version'])}; "
                 f"scoring rules: {_cell(report['scoring_rules_version'])}.",
                 f"Revision: {_cell(report['repository']['revision'])}; dirty tree: {_cell(report['repository']['dirty'])}.",
                 f"Offline transport verified: {_cell(report['offline_transport_verified'])}; "
                 f"actual network requests: {_cell(report['actual_network_requests'])}.", "",
                 "| Scenario | Required / Met / Handled | Orchestration / Code | Completion Attempts / Transport Invocations | Tool Rounds | Task Verdict | Expectation Verdict | Human Review |",
                 "|---|---|---|---|---|---|---|---|"]
        for record in report["scenarios"]:
            counts = record["completeness"]
            completeness = " / ".join(str(counts[key]) for key in ("required_count", "met_count", "handled_count"))
            if not counts["applicable"]:
                completeness += " (not applicable)"
            actual = record["orchestration"]
            cells = [record["scenario_id"], completeness,
                     f"{_cell(actual['status'])} / {_cell(actual['code'])}",
                     f"{_cell(record['completion_attempts'])} / {_cell(record['transport_invocations'])}",
                     actual["tool_rounds"], record["task_verdict"], record["expectation_verdict"], record["human_review"]]
            lines.append("| " + " | ".join(_cell(value) for value in cells) + " |")
        lines.extend(["", "## Totals", ""])
        for section, labels in (
            ("task_verdicts", (("pass", "Task Pass"), ("fail", "Task Fail"),
                              ("pending_review", "Pending Review"), ("invalid_run", "Invalid Runs"))),
            ("expectation_verdicts", (("pass", "Evaluation Expectations Passed"),
                                     ("fail", "Evaluation Expectations Failed"), ("not_evaluable", "Not Evaluable"))),
        ):
            lines.extend(f"- {label}: {report['totals'][section][key]}" for key, label in labels)
        lines.extend(["", "## Findings and task-handling checks", "",
                      "Expected domain findings and acceptable dependency blocks can satisfy requirements. "
                      "An expected agent task failure can have a passing evaluation expectation. "
                      "Counts of executed calls include skipped dispatches, separately identified in JSON.", ""])
        for record in report["scenarios"]:
            findings = list(record["failure_categories"])
            findings.extend("operation " + item["operation"] + ": " + item["state"]
                            for item in record["operations"] if item["state"] != "met")
            findings.extend("check unmet: " + key for key in CHECK_FIELDS if record["checks"][key] is False)
            findings.extend("expectation mismatch: " + field for field in record["expectation_mismatches"])
            findings.extend("infrastructure " + source + ": " + code
                            for source, codes in record["infrastructure_errors"].items() for code in codes)
            if findings:
                lines.append("- " + _cell(record["scenario_id"]) + ": " + "; ".join(_cell(item) for item in findings))
        return "\n".join(lines) + "\n"
    except Exception:
        raise ReportError("markdown_render_failed") from None


def write_report(report, *, output_dir):
    """Exclusively create JSON and Markdown; roll back owned files on failure."""
    if output_dir is None or not str(output_dir).strip():
        raise ReportError("explicit_output_directory_required")
    try:
        payloads = (serialize_report(report).encode("utf-8"), render_markdown(report).encode("utf-8"))
        if len(payloads[0]) > 1024 * 1024 or len(payloads[1]) > 256 * 1024:
            raise ReportError("report_size_limit")
        directory = Path(output_dir).resolve()
        paths = (directory / JSON_FILENAME, directory / MARKDOWN_FILENAME)
    except ReportError:
        raise
    except Exception:
        raise ReportError("invalid_output_directory") from None
    created = []
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with ExitStack() as stack:
            streams = []
            for path in paths:
                streams.append(stack.enter_context(path.open("xb")))
                created.append(path)
            for stream, payload in zip(streams, payloads):
                if stream.write(payload) != len(payload):
                    raise ReportError("short_report_write")
        return paths
    except Exception as error:
        cleanup_failed = False
        for path in reversed(created):
            try:
                path.unlink()
            except OSError:
                cleanup_failed = True
        code = "report_cleanup_failed" if cleanup_failed else (
            "report_exists" if isinstance(error, FileExistsError) else "report_write_failed")
        raise ReportError(code) from None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate deterministic offline JSON and Markdown evidence.")
    parser.add_argument("--output-dir", required=True, help="Explicit directory; existing report files are preserved")
    args = parser.parse_args(argv)
    try:
        report = generate_report()
        write_report(report, output_dir=args.output_dir)
    except ReportError as error:
        print("Evidence reporting failed: " + error.code)
        return 1
    print(NOTICE)
    print(f"Wrote {JSON_FILENAME} and {MARKDOWN_FILENAME}; scenarios={report['scenario_count']}")
    print(json.dumps(report["totals"], sort_keys=True))
    return 0 if all(record["expectation_verdict"] == "pass" for record in report["scenarios"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
