"""Offline, read-only executor for a bounded batch of native function calls.

Public API: execute_tool_calls(calls, *, bindings=None) returns a JSON-compatible
batch result. ResourceBindings supplies trusted local paths and validation policy;
model arguments can only reference selected_dataset and selected_knowledge.

Each call must have this exact shape (arguments is a JSON-encoded string):
    {"id": "call_1", "type": "function", "function": {
        "name": "validate_products",
        "arguments": '{"dataset":"selected_dataset"}'}}

check_knowledge additionally requires "knowledge": "selected_knowledge".
ToolCallError rejects the entire batch before resource access. Operational failures
are returned as failed/skipped results, with no dependent knowledge check after
invalid data. Validation and dataset loading happen once per batch, including for
a standalone knowledge check. No state or validation is cached across batches.

This module has no API client, CLI, subprocess dispatch, or writing operations.
Trusted bindings are not a sandbox against a hostile local caller/filesystem.
"""

from dataclasses import dataclass
import json
from pathlib import Path
import re
import stat

from . import build_knowledge, validate_products


MAX_CALLS = 8
MAX_ARGUMENT_BYTES = 4096
MAX_RESOURCE_BYTES = 2 * 1024 * 1024
MAX_DIAGNOSTICS = 50  # Per result, including the truncation notice when needed.
DEFAULT_KNOWLEDGE = (
    Path(__file__).resolve().parents[1] / "knowledge" / "MyTech_Product_Knowledge_v1.md"
)
_ARGUMENTS = {
    "validate_products": {"dataset": "selected_dataset"},
    "check_knowledge": {
        "dataset": "selected_dataset", "knowledge": "selected_knowledge",
    },
}


@dataclass(frozen=True)
class ResourceBindings:
    """Local-only configuration; use strict_v1=False explicitly for other catalogues.

    Relative paths resolve against the local caller's current directory. Defaults
    are repository-anchored and always select strict-v1 unless locally overridden.
    """

    dataset_path: Path = validate_products.DEFAULT_DATASET
    knowledge_path: Path = DEFAULT_KNOWLEDGE
    strict_v1: bool = True

    def __post_init__(self):
        if type(self.strict_v1) is not bool:
            raise ValueError("strict_v1 must be a boolean")
        for field, suffix in (("dataset_path", ".json"), ("knowledge_path", ".md")):
            path = Path(getattr(self, field)).resolve()
            if path.suffix.lower() != suffix:
                raise ValueError(f"{field} must reference a {suffix} file")
            object.__setattr__(self, field, path)


class ToolCallError(ValueError):
    """Invalid batch/envelope/arguments: no resource was opened or tool executed."""


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("non-standard JSON constant")


def _parse_calls(calls):
    if type(calls) is not list or not 1 <= len(calls) <= MAX_CALLS:
        raise ToolCallError(f"calls must be a list containing 1 to {MAX_CALLS} calls")
    parsed, seen = [], set()
    for index, call in enumerate(calls):
        prefix = f"call[{index}]"
        if type(call) is not dict or set(call) != {"id", "type", "function"}:
            raise ToolCallError(f"{prefix}: expected id, type, and function only")
        call_id = call["id"]
        if type(call_id) is not str or re.fullmatch(r"[A-Za-z0-9_-]{1,128}", call_id) is None:
            raise ToolCallError(f"{prefix}: id must contain 1-128 ASCII letters, digits, _ or -")
        if call_id in seen:
            raise ToolCallError(f"{prefix}: duplicate call id")
        seen.add(call_id)
        function = call["function"]
        if call["type"] != "function" or type(function) is not dict or set(function) != {"name", "arguments"}:
            raise ToolCallError(f"{prefix}: expected a function with name and arguments only")
        name = function["name"]
        if type(name) is not str or name not in _ARGUMENTS:
            raise ToolCallError(f"{prefix}: unsupported tool name")
        arguments = function["arguments"]
        try:
            if (type(arguments) is not str or len(arguments) > MAX_ARGUMENT_BYTES
                    or len(arguments.encode("utf-8")) > MAX_ARGUMENT_BYTES):
                raise ValueError("arguments must be a bounded UTF-8 JSON string")
            arguments = json.loads(
                arguments, object_pairs_hook=_unique_object, parse_constant=_reject_constant,
            )
        except (ValueError, UnicodeError, RecursionError) as error:
            raise ToolCallError(f"{prefix}: invalid JSON arguments") from error
        expected = _ARGUMENTS[name]
        if type(arguments) is not dict or set(arguments) != set(expected):
            raise ToolCallError(f"{prefix}: unexpected argument keys")
        if any(type(arguments[key]) is not str or arguments[key] != value
               for key, value in expected.items()):
            raise ToolCallError(f"{prefix}: expected authorized resource identifiers")
        parsed.append((call_id, name))
    return parsed


def _check_resource(path):
    info = path.stat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("bound resource must be a regular file")
    if info.st_size > MAX_RESOURCE_BYTES:
        raise ValueError("bound resource exceeds size limit")


def _read_knowledge(path):
    _check_resource(path)
    with path.open("rb") as source:
        payload = source.read(MAX_RESOURCE_BYTES + 1)
    if len(payload) > MAX_RESOURCE_BYTES:
        raise ValueError("bound resource exceeds size limit")
    return payload.decode("utf-8")


def _result(call_id, name, status, code, diagnostics, data=None):
    if len(diagnostics) > MAX_DIAGNOSTICS:
        omitted = len(diagnostics) - (MAX_DIAGNOSTICS - 1)
        diagnostics = diagnostics[:MAX_DIAGNOSTICS - 1] + [
            f"Diagnostics truncated: {omitted} additional messages omitted.",
        ]
    return {
        "tool_call_id": call_id, "name": name, "status": status, "code": code,
        "diagnostics": list(diagnostics), "data": data,
    }


def execute_tool_calls(calls, *, bindings=None):
    """Execute only validated calls; return {ok: bool, results: [per-call results]}.

    Results preserve input order and call IDs. status is success, failed, or
    skipped; code distinguishes data/IO failures from knowledge mismatches.
    Each result contains at most MAX_DIAGNOSTICS messages; if truncated, the last
    message reports how many were omitted. Status and code are unchanged.
    Invalid calls raise ToolCallError, including an invalid later call in a batch.
    Invalid local configuration raises TypeError/ValueError rather than tool errors.
    """
    parsed = _parse_calls(calls)
    if bindings is None:
        bindings = ResourceBindings()
    if type(bindings) is not ResourceBindings:
        raise TypeError("bindings must be ResourceBindings")

    dataset = None
    try:
        _check_resource(bindings.dataset_path)
        dataset = validate_products.load_dataset(bindings.dataset_path)
        errors = validate_products.validate_dataset(dataset, strict_v1=bindings.strict_v1)
        validation_code = "dataset_invalid" if errors else "ok"
    except (OSError, UnicodeError, ValueError, RecursionError) as error:
        errors = [f"Could not load/validate bound dataset ({type(error).__name__})."]
        validation_code = "dataset_read_error"

    results = []
    knowledge_result = None
    for call_id, name in parsed:
        # Dispatch is fixed, never getattr/import/eval or a model-supplied command.
        if name == "validate_products":
            counts = None if errors else {
                "products": len(dataset["products"]),
                "categories": len(dataset["supported_categories"]),
                "strict_v1": bindings.strict_v1,
            }
            results.append(_result(
                call_id, name, "failed" if errors else "success", validation_code, errors, counts,
            ))
        elif errors:
            results.append(_result(call_id, name, "skipped", validation_code, errors))
        else:
            if knowledge_result is None:
                try:
                    text = _read_knowledge(bindings.knowledge_path)
                    diagnostics = build_knowledge.check_knowledge(dataset, text)
                    knowledge_result = (
                        "failed" if diagnostics else "success",
                        "knowledge_inconsistent" if diagnostics else "ok", diagnostics,
                    )
                except (OSError, UnicodeError, ValueError, RecursionError) as error:
                    knowledge_result = (
                        "failed", "knowledge_read_error",
                        [f"Could not read/check bound knowledge ({type(error).__name__})."],
                    )
            status, code, diagnostics = knowledge_result
            data = {"records": len(dataset["products"])} if status == "success" else None
            results.append(_result(call_id, name, status, code, diagnostics, data))
    return {"ok": all(result["status"] == "success" for result in results), "results": results}
