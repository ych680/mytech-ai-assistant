"""Bounded TokenProxy native-tool orchestration, separate from MyTech production.

orchestrate(request, *, client, bindings=None) returns the generated explanation
separately from truthful, bounded Phase 1 tool results. Inject a transport into
TokenProxyClient for offline use. Nothing sends HTTP at import time.

An explicitly authorized future live smoke test can use:
    uv run python -m tools.tool3_tokenproxy --live
Without --live the CLI only displays help. Credentials are requested with hidden
getpass input, never loaded from files/environment or accepted as CLI arguments.
The endpoint/model below come from the supplied classroom smoke-test contract.
"""

import argparse
from copy import deepcopy
from dataclasses import dataclass
import getpass
import json
import math
import re
import ssl
import urllib.error
import urllib.request
import warnings

from . import tool3_executor


API_URL = "https://api.aidcec-ai-agent.com/v1/chat/completions"
MODEL = "tokenproxy/vision"
MAX_API_REQUESTS = 3
MAX_TOOL_ROUNDS = 2
MAX_TOTAL_CALLS = 8
HTTP_TIMEOUT_SECONDS = 60
MAX_RESPONSE_BYTES = 128 * 1024
MAX_USER_BYTES = 8 * 1024
MAX_ASSISTANT_BYTES = 16 * 1024
MAX_DIAGNOSTIC_CHARS = 512  # Includes the individual-message truncation notice.
MAX_TOOL_RESULT_BYTES = 16 * 1024  # Per role:tool JSON content, UTF-8 encoded.
MAX_CONVERSATION_BYTES = 128 * 1024  # Entire serialized HTTP request, including tools.
MAX_OUTPUT_TOKENS = 2048
EXAMPLE_REQUEST = "Validate my product dataset and check whether the knowledge base is consistent."
_SYSTEM_MESSAGE = (
    "You coordinate two read-only local tools. Use only the advertised resource identifiers. "
    "Use tools for validation/consistency claims. Report which operations were actually "
    "requested and their returned statuses; never claim a skipped or failed check succeeded. "
    "Do not request paths, commands, network access, generation, or policy changes. "
    "After tool results, give a concise explanation without thinking markup."
)


def tool_definitions():
    """Return fresh schemas matching the Phase 1 executor's exact arguments."""
    definitions = []
    for name, description, properties in (
        ("validate_products", "Validate the selected local product dataset.",
         {"dataset": {"type": "string", "enum": ["selected_dataset"]}}),
        ("check_knowledge", "Check selected local knowledge after mandatory dataset validation.",
         {"dataset": {"type": "string", "enum": ["selected_dataset"]},
          "knowledge": {"type": "string", "enum": ["selected_knowledge"]}}),
    ):
        definitions.append({"type": "function", "function": {
            "name": name, "description": description,
            "parameters": {"type": "object", "properties": properties,
                           "required": list(properties), "additionalProperties": False},
        }})
    return definitions


class ProviderError(Exception):
    """Sanitized failure code; provider bodies, exception details, and keys are omitted."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class HTTPResponse:
    """Transport result. body must be raw bytes; status must be an integer."""

    status: int
    body: bytes


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http_transport(request, *, timeout, max_response_bytes):
    """One HTTPS POST, no redirects/proxy discovery/retries; bounded body read.

    urllib's timeout bounds blocking network operations, not a hard wall-clock
    deadline for DNS resolution or a peer trickling bytes. No background workers.
    """
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), _NoRedirect(),
        urllib.request.HTTPSHandler(context=ssl.create_default_context()),
    )
    with opener.open(request, timeout=timeout) as response:
        if response.status != 200:
            return HTTPResponse(response.status, b"")
        body = response.read(max_response_bytes + 1)
        if len(body) > max_response_bytes:
            raise ProviderError("response_too_large")
        return HTTPResponse(response.status, body)


def _json_bytes(value):
    return json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":")).encode("utf-8")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("nonstandard JSON constant")


def _finite_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("nonfinite JSON number")
    return number


def _bounded_text(value, limit):
    return type(value) is str and len(value) <= limit and len(value.encode("utf-8")) <= limit


def _assistant_message(body):
    try:
        response = json.loads(
            body.decode("utf-8"), object_pairs_hook=_unique_object,
            parse_constant=_reject_constant, parse_float=_finite_float,
        )
    except (UnicodeError, ValueError, RecursionError):
        raise ProviderError("invalid_response_json") from None
    try:
        choices = response["choices"]
        if type(choices) is not list or len(choices) != 1 or type(choices[0]) is not dict:
            raise ValueError
        message = choices[0]["message"]
        if type(message) is not dict or message.get("role") != "assistant" or "function_call" in message:
            raise ValueError
        content = message.get("content")
        if content is not None and not _bounded_text(content, MAX_ASSISTANT_BYTES):
            raise ValueError
        calls = message.get("tool_calls", [])
        if type(calls) is not list:
            raise ValueError
        for call in calls:
            if (type(call) is not dict or type(call.get("id")) is not str
                    or call.get("type") != "function" or type(call.get("function")) is not dict
                    or type(call["function"].get("name")) is not str
                    or type(call["function"].get("arguments")) is not str):
                raise ValueError
        expected_finish = "tool_calls" if calls else "stop"
        if choices[0].get("finish_reason") not in (None, expected_finish):
            raise ValueError
    except (KeyError, TypeError, ValueError, UnicodeError, RecursionError):
        raise ProviderError("invalid_assistant_message") from None
    # Preserve original call envelopes and argument strings; Phase 1 validates
    # exact keys/IDs/arguments before any resource access. Drop unrelated metadata.
    result = {"role": "assistant", "content": content}
    if calls:
        result["tool_calls"] = calls
    return result


class TokenProxyClient:
    """Runtime-authenticated client; transport(request, *, timeout, max_response_bytes).

    transport returns HTTPResponse and is a trusted local dependency, never
    selected by the LLM. This object has no credential-bearing repr or logging.
    """

    def __init__(self, api_key, *, transport=None):
        if (type(api_key) is not str or not 1 <= len(api_key) <= 4096
                or any(not 33 <= ord(char) <= 126 for char in api_key)):
            raise ValueError("Invalid runtime authentication value")
        self._api_key = api_key
        self._transport = http_transport if transport is None else transport

    def complete(self, messages, *, allow_tools=True):
        payload = {
            "model": MODEL, "messages": messages, "tools": tool_definitions(),
            "tool_choice": "auto" if allow_tools else "none",
            "stream": False, "max_tokens": MAX_OUTPUT_TOKENS,
        }
        try:
            body = _json_bytes(payload)
        except (ValueError, TypeError, RecursionError):
            raise ProviderError("invalid_conversation") from None
        if len(body) > MAX_CONVERSATION_BYTES:
            raise ProviderError("conversation_too_large")
        request = urllib.request.Request(API_URL, data=body, method="POST", headers={
            "Authorization": "Bearer " + self._api_key,
            "Content-Type": "application/json", "Accept": "application/json",
        })
        try:
            response = self._transport(
                request, timeout=HTTP_TIMEOUT_SECONDS, max_response_bytes=MAX_RESPONSE_BYTES,
            )
        except ProviderError:
            raise
        except urllib.error.HTTPError as error:
            # Do not read the error body or expose its URL/headers/reason.
            code = "http_error_" + str(error.code) if type(error.code) is int else "http_error"
            error.close()
            raise ProviderError(code) from None
        except TimeoutError:
            raise ProviderError("request_timeout") from None
        except urllib.error.URLError as error:
            code = "request_timeout" if isinstance(error.reason, TimeoutError) else "network_error"
            raise ProviderError(code) from None
        except Exception:
            raise ProviderError("transport_error") from None
        if type(response) is not HTTPResponse or type(response.status) is not int:
            raise ProviderError("invalid_http_response")
        if response.status != 200:
            raise ProviderError("http_error_" + str(response.status))
        if type(response.body) is not bytes:
            raise ProviderError("invalid_http_response")
        if len(response.body) > MAX_RESPONSE_BYTES:
            raise ProviderError("response_too_large")
        return _assistant_message(response.body)


def _clean_final_text(text):
    if type(text) is not str:
        raise ProviderError("empty_assistant_response")
    output, position, depth = [], 0, 0
    for marker in re.finditer(r"</?thinking\b", text, re.IGNORECASE):
        tag = re.match(r"</?thinking(?:\s[^<>]*?)?\s*>", text[marker.start():], re.IGNORECASE)
        if tag is None:
            raise ProviderError("invalid_thinking_markup")
        if depth == 0:
            output.append(text[position:marker.start()])
        if text[marker.start() + 1] == "/":
            if depth == 0:
                raise ProviderError("invalid_thinking_markup")
            depth -= 1
        else:
            depth += 1
        position = marker.start() + tag.end()
    if depth:
        raise ProviderError("invalid_thinking_markup")
    output.append(text[position:])
    cleaned = "".join(output).strip()
    if not cleaned:
        raise ProviderError("empty_assistant_response")
    return cleaned


def _short_diagnostic(text):
    notice = " [message truncated]"
    return text if len(text) <= MAX_DIAGNOSTIC_CHARS else text[:MAX_DIAGNOSTIC_CHARS - len(notice)] + notice


def _serialize_tool_result(row):
    bounded = dict(row)
    diagnostics = [_short_diagnostic(text) for text in row["diagnostics"]]
    # Preserve Phase 1's upstream truncation notice even if this layer must omit
    # more entries to fit the byte budget (particularly for escaped Unicode).
    tail = diagnostics[-1:] if diagnostics and diagnostics[-1].startswith("Diagnostics truncated:") else []
    head = diagnostics[:-1] if tail else diagnostics
    retained = len(head)
    while True:
        omitted = len(head) - retained
        notice = [f"Additional executor diagnostic entries omitted: {omitted}."] if omitted else []
        bounded["diagnostics"] = head[:retained] + notice + tail
        content = _json_bytes(bounded)
        if len(content) <= MAX_TOOL_RESULT_BYTES:
            return bounded, content.decode("utf-8")
        if retained == 0:
            raise ProviderError("tool_result_too_large")
        retained -= 1


def orchestrate(request, *, client, bindings=None):
    """Run at most three completion attempts and two validated execution rounds.

    status/code describe orchestration; execution_status is not_run/success/failed
    based only on actual Phase 1 results. Explanation is never execution evidence.
    Earlier results remain visible on later provider/limit/batch failures. Tool
    results are returned with the same bounds used for role:tool messages.
    """
    records, seen_ids = [], set()
    attempts = rounds = 0

    def finish(code, assistant_response=None, *, completed=False):
        execution = "not_run" if not records else (
            "success" if all(row["status"] == "success" for row in records) else "failed"
        )
        return {
            "status": "completed" if completed else "failed", "code": code,
            "assistant_response": assistant_response, "execution_status": execution,
            "tool_results": records, "api_requests": attempts, "tool_rounds": rounds,
        }

    try:
        if not _bounded_text(request, MAX_USER_BYTES) or not request.strip():
            return finish("invalid_user_request")
    except UnicodeError:
        return finish("invalid_user_request")
    if bindings is not None and type(bindings) is not tool3_executor.ResourceBindings:
        return finish("invalid_resource_bindings")
    messages = [{"role": "system", "content": _SYSTEM_MESSAGE}, {"role": "user", "content": request}]
    for _ in range(MAX_API_REQUESTS):
        attempts += 1
        try:
            message = client.complete(
                deepcopy(messages), allow_tools=rounds < MAX_TOOL_ROUNDS and len(records) < MAX_TOTAL_CALLS,
            )
            calls = message.get("tool_calls", [])
            if not calls:
                text = _clean_final_text(message["content"])
                code = "no_tools_executed" if not records else (
                    "ok" if all(row["status"] == "success" for row in records) else "tool_execution_failed"
                )
                return finish(code, text, completed=True)
            # Reserve one remaining request for the final explanation. A provider
            # ignoring tool_choice=none never causes another tool execution.
            if (rounds >= MAX_TOOL_ROUNDS or attempts >= MAX_API_REQUESTS
                    or len(records) + len(calls) > MAX_TOTAL_CALLS):
                return finish("execution_limit_reached")
            if any(call["id"] in seen_ids for call in calls):
                return finish("invalid_tool_calls")
            batch = tool3_executor.execute_tool_calls(calls, bindings=bindings)
            rounds += 1
            seen_ids.update(call["id"] for call in calls)
            messages.append(message)
            # Preserve every executed call, even if serializing an earlier result
            # fails. Empty diagnostic summaries never alter status/code/data.
            offset = len(records)
            records.extend(dict(row, diagnostics=[]) for row in batch["results"])
            for index, row in enumerate(batch["results"]):
                bounded, content = _serialize_tool_result(row)
                records[offset + index] = bounded
                messages.append({"role": "tool", "tool_call_id": row["tool_call_id"], "content": content})
        except tool3_executor.ToolCallError:
            return finish("invalid_tool_calls")
        except ProviderError as error:
            return finish(error.code)
    return finish("execution_limit_reached")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Explicitly authorize the documented live smoke test")
    args = parser.parse_args(argv)
    if not args.live:
        parser.print_help()
        return 0
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            key = getpass.getpass("TokenProxy API key (hidden): ")
        client = TokenProxyClient(key)
    except (ValueError, EOFError, KeyboardInterrupt, getpass.GetPassWarning):
        print("Secure runtime authentication unavailable.")
        return 1
    result = orchestrate(EXAMPLE_REQUEST, client=client)
    print(json.dumps(result, ensure_ascii=True))
    # This fixed demonstration requires two actual successful tool-call records.
    successful_tools = {row["name"] for row in result["tool_results"] if row["status"] == "success"}
    passed = (result["status"] == "completed" and result["execution_status"] == "success"
              and {"validate_products", "check_knowledge"} <= successful_tools)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
