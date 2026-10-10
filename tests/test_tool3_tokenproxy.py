"""Mocked TokenProxy protocol tests; no real network or authentication is used."""

from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import ssl
import tempfile
import unittest
from unittest.mock import Mock, patch
import urllib.error

from tools import tool3_executor as executor
from tools import tool3_tokenproxy as adapter


def call(name="validate_products", call_id="call_1", arguments=None):
    if arguments is None:
        arguments = {"dataset": "selected_dataset"}
        if name == "check_knowledge":
            arguments["knowledge"] = "selected_knowledge"
    return {"id": call_id, "type": "function", "function": {
        "name": name, "arguments": json.dumps(arguments),
    }}


def completion(content="Finished.", calls=None, **extra):
    message = {"role": "assistant", "content": content}
    if calls is not None:
        message["tool_calls"] = calls
    return {"choices": [{"message": message, **extra}]}


class ScriptedTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request, *, timeout, max_response_bytes):
        self.requests.append({
            "url": request.full_url, "method": request.get_method(),
            "payload": json.loads(request.data), "timeout": timeout,
            "max_response_bytes": max_response_bytes,
        })
        if not self.responses:
            raise AssertionError("Unexpected additional provider request")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        if callable(response):
            response = response(request)
        if type(response) is adapter.HTTPResponse:
            return response
        body = response if type(response) is bytes else json.dumps(response).encode("utf-8")
        return adapter.HTTPResponse(200, body)


class TokenProxyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset_bytes = executor.validate_products.DEFAULT_DATASET.read_bytes()
        cls.knowledge_bytes = executor.DEFAULT_KNOWLEDGE.read_bytes()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.dataset = self.root / "products.json"
        self.knowledge = self.root / "knowledge.md"
        self.dataset.write_bytes(self.dataset_bytes)
        self.knowledge.write_bytes(self.knowledge_bytes)
        self.bindings = executor.ResourceBindings(self.dataset, self.knowledge)
        self.network_mocks = []
        for target in ("socket.create_connection", "socket.socket.connect", "urllib.request.urlopen"):
            block = patch(target, side_effect=AssertionError("Real network forbidden"))
            self.network_mocks.append(block.start())
            self.addCleanup(block.stop)

    def tearDown(self):
        for network in self.network_mocks:
            network.assert_not_called()
        self.assertEqual(self.dataset_bytes, executor.validate_products.DEFAULT_DATASET.read_bytes())
        self.assertEqual(self.knowledge_bytes, executor.DEFAULT_KNOWLEDGE.read_bytes())

    def run_script(self, responses, request="Check the selected resources."):
        transport = ScriptedTransport(responses)
        client = adapter.TokenProxyClient("offline-test-key", transport=transport)
        before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.iterdir()}
        result = adapter.orchestrate(request, client=client, bindings=self.bindings)
        after = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.iterdir()}
        self.assertEqual(before, after)
        self.assertNotIn("offline-test-key", json.dumps(result))
        self.assertNotIn(str(self.root), json.dumps(result))
        return result, transport

    def test_single_call_uses_real_executor(self):
        result, transport = self.run_script([
            completion(None, [call()]), completion("Dataset validated."),
        ])
        self.assertEqual((result["status"], result["code"], result["execution_status"]),
                         ("completed", "ok", "success"))
        self.assertEqual(result["tool_results"][0]["data"]["products"], 27)
        self.assertEqual([row["name"] for row in result["tool_results"]], ["validate_products"])
        self.assertEqual((result["api_requests"], result["tool_rounds"]), (2, 1))
        first = transport.requests[0]
        self.assertEqual((first["url"], first["method"]), (adapter.API_URL, "POST"))
        self.assertEqual(first["timeout"], 60)
        self.assertEqual(first["max_response_bytes"], 128 * 1024)
        self.assertEqual(first["payload"]["model"], "tokenproxy/vision")
        self.assertFalse(first["payload"]["stream"])
        self.assertEqual(first["payload"]["max_tokens"], adapter.MAX_OUTPUT_TOKENS)

    def test_multiple_calls_exact_message_order_and_id_association(self):
        calls = [call(), call("check_knowledge", "call_2")]
        result, transport = self.run_script([completion("Checking.", calls), completion()])
        self.assertEqual(result["execution_status"], "success")
        messages = transport.requests[1]["payload"]["messages"]
        self.assertEqual([m["role"] for m in messages], ["system", "user", "assistant", "tool", "tool"])
        self.assertEqual(messages[2], {"role": "assistant", "content": "Checking.", "tool_calls": calls})
        for index, tool_id in enumerate(("call_1", "call_2")):
            message = messages[3 + index]
            self.assertEqual(message["tool_call_id"], tool_id)
            self.assertEqual(json.loads(message["content"]), result["tool_results"][index])
        self.assertEqual(transport.requests[0]["payload"]["tools"], transport.requests[1]["payload"]["tools"])

    def test_two_rounds_keep_tools_and_disable_further_selection(self):
        result, transport = self.run_script([
            completion(None, [call()]),
            completion(None, [call("check_knowledge", "call_2")]), completion(),
        ])
        self.assertEqual((result["api_requests"], result["tool_rounds"]), (3, 2))
        self.assertEqual(result["execution_status"], "success")
        self.assertEqual([m["role"] for m in transport.requests[2]["payload"]["messages"]],
                         ["system", "user", "assistant", "tool", "assistant", "tool"])
        self.assertEqual([r["payload"]["tool_choice"] for r in transport.requests], ["auto", "auto", "none"])
        for request in transport.requests:
            self.assertEqual(request["payload"]["tools"], adapter.tool_definitions())

    def test_schemas_match_executor_arguments_and_are_fresh(self):
        schemas = adapter.tool_definitions()
        self.assertEqual([s["function"]["name"] for s in schemas], ["validate_products", "check_knowledge"])
        for tool in schemas:
            schema = tool["function"]["parameters"]
            self.assertFalse(schema["additionalProperties"])
            self.assertEqual(set(schema["required"]), set(schema["properties"]))
            for name, prop in schema["properties"].items():
                self.assertEqual(prop, {"type": "string", "enum": ["selected_" + name]})
        schemas[0]["function"]["parameters"]["properties"]["dataset"]["enum"].append("bad")
        self.assertNotEqual(schemas, adapter.tool_definitions())

    def test_validation_failure_and_skipped_check_remain_truthful(self):
        self.dataset.write_text("{}", encoding="utf-8")
        with patch.object(executor, "_read_knowledge") as read:
            result, transport = self.run_script([
                completion(None, [call(), call("check_knowledge", "call_2")]),
                completion("Everything succeeded."),
            ])
        read.assert_not_called()
        self.assertEqual(result["code"], "tool_execution_failed")
        self.assertEqual(result["execution_status"], "failed")
        self.assertEqual([r["status"] for r in result["tool_results"]], ["failed", "skipped"])
        for index, message in enumerate(transport.requests[1]["payload"]["messages"][-2:]):
            self.assertEqual(json.loads(message["content"])["code"], "dataset_invalid")
            self.assertEqual(json.loads(message["content"])["status"], result["tool_results"][index]["status"])

    def test_standalone_check_and_knowledge_mismatch(self):
        self.knowledge.write_text("# Changed\n", encoding="utf-8")
        result, _ = self.run_script([completion(None, [call("check_knowledge")]), completion()])
        self.assertEqual(result["execution_status"], "failed")
        self.assertEqual(len(result["tool_results"]), 1)
        self.assertEqual(result["tool_results"][0]["code"], "knowledge_inconsistent")

    def test_invalid_batch_executes_nothing_and_is_not_repaired(self):
        invalid = [call("generate_knowledge", "bad"), call(arguments={"dataset": "../data.json"})]
        malformed = call()
        malformed["function"]["arguments"] = "{"
        invalid.append(malformed)
        duplicate = call()
        duplicate["function"]["arguments"] = '{"dataset":"selected_dataset","dataset":"selected_dataset"}'
        invalid.append(duplicate)
        extra = call()
        extra["function"]["extra"] = True
        invalid.append(extra)
        for bad in invalid:
            with self.subTest(bad=bad), patch.object(executor.validate_products, "load_dataset") as load:
                result, transport = self.run_script([completion(None, [call(call_id="valid"), bad])])
            self.assertEqual(result["code"], "invalid_tool_calls")
            self.assertEqual(result["execution_status"], "not_run")
            self.assertEqual(result["tool_results"], [])
            self.assertEqual(len(transport.requests), 1)
            load.assert_not_called()

    def test_call_ids_missing_duplicate_and_reused_across_rounds(self):
        missing = call()
        del missing["id"]
        for calls in ([missing], [call(), call()]):
            with patch.object(executor.validate_products, "load_dataset") as load:
                result, _ = self.run_script([completion(None, calls)])
            self.assertIn(result["code"], ("invalid_assistant_message", "invalid_tool_calls"))
            load.assert_not_called()
        with patch.object(executor, "execute_tool_calls", wraps=executor.execute_tool_calls) as execute:
            result, _ = self.run_script([completion(None, [call()]), completion(None, [call()])])
        execute.assert_called_once()
        self.assertEqual(result["code"], "invalid_tool_calls")
        self.assertEqual(len(result["tool_results"]), 1)

    def test_direct_answer_explicitly_reports_no_tools(self):
        with patch.object(executor, "execute_tool_calls") as execute:
            result, _ = self.run_script([completion("Your data is valid.")])
        execute.assert_not_called()
        self.assertEqual((result["code"], result["execution_status"], result["tool_results"]),
                         ("no_tools_executed", "not_run", []))

    def test_round_limit_rejects_unexpected_third_batch(self):
        with patch.object(executor, "execute_tool_calls", wraps=executor.execute_tool_calls) as execute:
            result, transport = self.run_script([
                completion(None, [call()]), completion(None, [call(call_id="call_2")]),
                completion(None, [call(call_id="call_3")]),
            ])
        self.assertEqual(execute.call_count, 2)
        self.assertEqual(len(transport.requests), 3)
        self.assertEqual(result["code"], "execution_limit_reached")
        self.assertEqual(len(result["tool_results"]), 2)

    def test_cumulative_call_limit_rejects_whole_next_batch(self):
        first = [call(call_id=f"call_{i}") for i in range(7)]
        second = [call(call_id="next_1"), call(call_id="next_2")]
        with patch.object(executor, "execute_tool_calls", wraps=executor.execute_tool_calls) as execute:
            result, _ = self.run_script([completion(None, first), completion(None, second)])
        self.assertEqual(result["code"], "execution_limit_reached")
        execute.assert_called_once()
        self.assertEqual(len(result["tool_results"]), 7)

    def test_eight_calls_allow_final_answer_but_no_more_execution(self):
        calls = [call(call_id=f"call_{i}") for i in range(8)]
        result, transport = self.run_script([completion(None, calls), completion()])
        self.assertEqual(result["code"], "ok")
        self.assertEqual(len(result["tool_results"]), 8)
        self.assertEqual(transport.requests[1]["payload"]["tool_choice"], "none")
        result, _ = self.run_script([completion(None, calls), completion(None, [call(call_id="extra")])])
        self.assertEqual(result["code"], "execution_limit_reached")
        with patch.object(executor, "execute_tool_calls") as execute:
            result, _ = self.run_script([completion(None, calls + [call(call_id="ninth")])])
        self.assertEqual(result["code"], "execution_limit_reached")
        execute.assert_not_called()

    def test_provider_http_failures_are_sanitized(self):
        for status in (301, 401, 403, 429, 500, 502):
            with self.subTest(status=status):
                response = adapter.HTTPResponse(status, b'offline-test-key C:\\private\\credential')
                result, transport = self.run_script([response])
                self.assertEqual(result["code"], f"http_error_{status}")
                self.assertEqual(len(transport.requests), 1)
        error = urllib.error.HTTPError("https://private.invalid/offline-test-key", 502,
                                       "offline-test-key", {}, io.BytesIO(b"private error"))
        result, _ = self.run_script([error])
        self.assertEqual(result["code"], "http_error_502")
        self.assertTrue(error.fp.closed)

    def test_timeout_tls_network_and_other_transport_errors(self):
        for error, code in (
            (TimeoutError("offline-test-key"), "request_timeout"),
            (urllib.error.URLError(TimeoutError("private")), "request_timeout"),
            (urllib.error.URLError("offline-test-key"), "network_error"),
            (ssl.SSLError("offline-test-key"), "transport_error"),
            (OSError("C:\\private\\credential"), "transport_error"),
            (RuntimeError("offline-test-key"), "transport_error"),
        ):
            with self.subTest(code=code):
                result, transport = self.run_script([error])
                self.assertEqual(result["code"], code)
                self.assertEqual(len(transport.requests), 1)

    def test_provider_failure_preserves_prior_real_results(self):
        result, _ = self.run_script([completion(None, [call()]), adapter.HTTPResponse(502, b"private")])
        self.assertEqual((result["status"], result["code"]), ("failed", "http_error_502"))
        self.assertEqual(result["execution_status"], "success")
        self.assertEqual(result["tool_results"][0]["status"], "success")

    def test_invalid_utf8_json_duplicate_keys_and_nonfinite_values(self):
        for body in (b"\xff", b"{", b"{} trailing", b'{"choices":[],"choices":[]}',
                     b'{"value":NaN}', b'{"value":Infinity}', b'{"value":1e400}',
                     b"[" * 1500 + b"]" * 1500 + b" trailing"):
            with self.subTest(body=body[:30]):
                result, _ = self.run_script([body])
                self.assertEqual(result["code"], "invalid_response_json")

    def test_malformed_response_structures_never_execute(self):
        responses = [None, [], {}, {"choices": []}, {"choices": [{}, {}]},
                     {"choices": [None]}, {"choices": [{"message": None}]}]
        for content in (17, [], {}):
            responses.append(completion(content))
        for role in (None, "user", "tool"):
            response = completion()
            response["choices"][0]["message"]["role"] = role
            responses.append(response)
        for calls in (None, {}, "calls", [None], [{"id": [], "type": "function", "function": {}}]):
            response = completion()
            response["choices"][0]["message"]["tool_calls"] = calls
            responses.append(response)
        responses.append(completion("Partial", finish_reason="length"))
        responses.append(completion(None, [call()], finish_reason="stop"))
        for response in responses:
            with self.subTest(response=response), patch.object(executor, "execute_tool_calls") as execute:
                result, _ = self.run_script([response])
            self.assertEqual(result["code"], "invalid_assistant_message")
            execute.assert_not_called()

    def test_empty_assistant_answers(self):
        for text in (None, "", " \n\t", "<thinking>private reasoning</thinking>"):
            result, _ = self.run_script([completion(text)])
            self.assertEqual(result["code"], "empty_assistant_response")
            self.assertIsNone(result["assistant_response"])

    def test_thinking_blocks_nested_multiple_and_case_insensitive(self):
        for text, expected in (
            ("<thinking>hidden</thinking>Visible.", "Visible."),
            ("Before <thinking>one<thinking>two</thinking>three</thinking> after", "Before  after"),
            ("<THINKING>one\ntwo</THINKING>OK<thinking mode='x'>three</thinking>", "OK"),
        ):
            result, _ = self.run_script([completion(text)])
            self.assertEqual(result["assistant_response"], expected)
        for text in ("<thinking>unfinished", "</thinking>orphan", "<thinking truncated", "<thinking/>text"):
            result, _ = self.run_script([completion(text)])
            self.assertEqual(result["code"], "invalid_thinking_markup")
            self.assertIsNone(result["assistant_response"])

    def test_oversized_raw_and_assistant_responses(self):
        result, _ = self.run_script([b" " * (adapter.MAX_RESPONSE_BYTES + 1)])
        self.assertEqual(result["code"], "response_too_large")
        for text in ("x" * (adapter.MAX_ASSISTANT_BYTES + 1), "中" * 6000, "\ud800"):
            result, _ = self.run_script([completion(text)])
            self.assertEqual(result["code"], "invalid_assistant_message")

    def test_invalid_user_requests_make_no_provider_attempts(self):
        for request in (None, "", "  ", [], "\ud800", "x" * (adapter.MAX_USER_BYTES + 1), "中" * 3000):
            result, transport = self.run_script([], request=request)
            self.assertEqual(result["code"], "invalid_user_request")
            self.assertEqual(result["api_requests"], 0)
            self.assertEqual(transport.requests, [])

    def test_individual_and_serialized_diagnostic_bounds_preserve_failures(self):
        diagnostics = ["中" * 1000 for _ in range(49)] + ["Diagnostics truncated: 99 additional messages omitted."]
        row = {"tool_call_id": "call_1", "name": "validate_products", "status": "failed",
               "code": "dataset_invalid", "diagnostics": diagnostics, "data": None}
        original = deepcopy(row)
        with patch.object(executor, "execute_tool_calls", return_value={"ok": False, "results": [row]}):
            result, transport = self.run_script([completion(None, [call()]), completion()])
        self.assertEqual(row, original)
        bounded = result["tool_results"][0]
        self.assertEqual((bounded["status"], bounded["code"]), ("failed", "dataset_invalid"))
        self.assertEqual(result["execution_status"], "failed")
        self.assertTrue(all(len(d) <= adapter.MAX_DIAGNOSTIC_CHARS for d in bounded["diagnostics"]))
        self.assertTrue(bounded["diagnostics"][0].endswith(" [message truncated]"))
        self.assertEqual(bounded["diagnostics"][-1], diagnostics[-1])
        self.assertTrue(any(d.startswith("Additional executor diagnostic entries omitted:") for d in bounded["diagnostics"]))
        content = transport.requests[1]["payload"]["messages"][-1]["content"]
        self.assertLessEqual(len(content.encode("utf-8")), adapter.MAX_TOOL_RESULT_BYTES)
        self.assertEqual(json.loads(content), bounded)

    def test_untransmittable_results_preserve_all_executed_statuses(self):
        with patch.object(adapter, "MAX_TOOL_RESULT_BYTES", 1):
            result, transport = self.run_script([completion(None, [call(), call("check_knowledge", "call_2")])])
        self.assertEqual(result["code"], "tool_result_too_large")
        self.assertEqual([r["tool_call_id"] for r in result["tool_results"]], ["call_1", "call_2"])
        self.assertEqual([r["status"] for r in result["tool_results"]], ["success", "success"])
        self.assertEqual(len(transport.requests), 1)

    def test_conversation_budget_checked_before_every_transport(self):
        with patch.object(adapter, "MAX_CONVERSATION_BYTES", 1):
            result, transport = self.run_script([])
        self.assertEqual(result["code"], "conversation_too_large")
        self.assertEqual(transport.requests, [])

        def lower_budget_after_first_request(request):
            adapter.MAX_CONVERSATION_BYTES = len(request.data) + 1
            return completion(None, [call()])

        with patch.object(adapter, "MAX_CONVERSATION_BYTES", adapter.MAX_CONVERSATION_BYTES):
            result, transport = self.run_script([lower_budget_after_first_request])
        self.assertEqual(result["code"], "conversation_too_large")
        self.assertEqual(len(transport.requests), 1)
        self.assertEqual(result["tool_results"][0]["status"], "success")

    def test_http_transport_bounds_body_disables_redirects_and_verifies_tls(self):
        response = Mock(status=200)
        response.read.return_value = b"{}"
        opener = Mock()
        opener.open.return_value.__enter__ = Mock(return_value=response)
        opener.open.return_value.__exit__ = Mock(return_value=False)
        request = adapter.urllib.request.Request(adapter.API_URL, data=b"{}", method="POST")
        with patch.object(adapter.urllib.request, "build_opener", return_value=opener) as build:
            actual = adapter.http_transport(request, timeout=60, max_response_bytes=128)
        self.assertEqual(actual, adapter.HTTPResponse(200, b"{}"))
        response.read.assert_called_once_with(129)
        opener.open.assert_called_once_with(request, timeout=60)
        proxy, redirect, https = build.call_args.args
        self.assertEqual(proxy.proxies, {})
        self.assertIsNone(redirect.redirect_request(None, None, 302, "", {}, "https://other.invalid"))
        self.assertEqual(https._context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(https._context.check_hostname)
        response.read.return_value = b"x" * 129
        with patch.object(adapter.urllib.request, "build_opener", return_value=opener), \
             self.assertRaisesRegex(adapter.ProviderError, "response_too_large"):
            adapter.http_transport(request, timeout=60, max_response_bytes=128)

    def test_http_transport_does_not_read_non_success_body(self):
        response = Mock(status=502)
        opener = Mock()
        opener.open.return_value.__enter__ = Mock(return_value=response)
        opener.open.return_value.__exit__ = Mock(return_value=False)
        with patch.object(adapter.urllib.request, "build_opener", return_value=opener):
            result = adapter.http_transport(Mock(), timeout=60, max_response_bytes=128)
        self.assertEqual(result, adapter.HTTPResponse(502, b""))
        response.read.assert_not_called()

    def test_runtime_key_validation_and_no_key_in_request_payload(self):
        for key in (None, "", "x\r\nInjected: header", "x y", "中", "x" * 4097):
            with self.assertRaisesRegex(ValueError, "Invalid runtime authentication value"):
                adapter.TokenProxyClient(key)
        captured = []

        def transport(request, **kwargs):
            self.assertEqual(request.get_header("Authorization"), "Bearer offline-test-key")
            self.assertNotIn(b"offline-test-key", request.data)
            captured.append(request)
            return adapter.HTTPResponse(200, json.dumps(completion()).encode())

        client = adapter.TokenProxyClient("offline-test-key", transport=transport)
        self.assertNotIn("offline-test-key", repr(client))
        client.complete([{"role": "user", "content": "hello"}])
        self.assertEqual(len(captured), 1)

    def test_default_cli_is_help_only_without_credentials_or_http(self):
        with patch.object(adapter.getpass, "getpass") as prompt, \
             patch.object(adapter, "http_transport") as transport, redirect_stdout(io.StringIO()) as output:
            self.assertEqual(adapter.main([]), 0)
        self.assertIn("--live", output.getvalue())
        prompt.assert_not_called()
        transport.assert_not_called()

    def assert_live_cli_exit(self, tool_statuses, expected_exit, *, status="completed",
                             execution_status="success", code="ok"):
        result = {
            "status": status, "code": code,
            "assistant_response": "Both checks succeeded.",
            "execution_status": execution_status,
            "tool_results": [
                {"tool_call_id": f"call_{index}", "name": name, "status": tool_status,
                 "code": "ok" if tool_status == "success" else "dataset_invalid",
                 "diagnostics": [], "data": None}
                for index, (name, tool_status) in enumerate(tool_statuses, start=1)
            ],
            "api_requests": 2, "tool_rounds": 1 if tool_statuses else 0,
        }
        with patch.object(adapter.getpass, "getpass", return_value="offline-test-key") as prompt, \
             patch.object(adapter, "TokenProxyClient") as client, \
             patch.object(adapter, "orchestrate", return_value=result) as orchestrate, \
             patch.object(adapter, "http_transport") as transport, redirect_stdout(io.StringIO()) as output:
            self.assertEqual(adapter.main(["--live"]), expected_exit)
        prompt.assert_called_once_with("TokenProxy API key (hidden): ")
        client.assert_called_once_with("offline-test-key")
        orchestrate.assert_called_once_with(adapter.EXAMPLE_REQUEST, client=client.return_value)
        transport.assert_not_called()
        self.assertEqual(json.loads(output.getvalue()), result)
        self.assertNotIn("offline-test-key", output.getvalue())

    def test_live_cli_accepts_both_successful_tool_records(self):
        self.assert_live_cli_exit([("validate_products", "success"), ("check_knowledge", "success")], 0)

    def test_live_cli_rejects_validation_only(self):
        self.assert_live_cli_exit([("validate_products", "success")], 1)

    def test_live_cli_rejects_knowledge_check_only(self):
        self.assert_live_cli_exit([("check_knowledge", "success")], 1)

    def test_live_cli_rejects_no_tools(self):
        self.assert_live_cli_exit([], 1, execution_status="not_run", code="no_tools_executed")

    def test_live_cli_rejects_failed_or_skipped_tools(self):
        for tool_status in ("failed", "skipped"):
            with self.subTest(tool_status=tool_status):
                self.assert_live_cli_exit(
                    [("validate_products", "success"), ("check_knowledge", tool_status)], 1,
                    execution_status="failed", code="tool_execution_failed",
                )

    def test_live_cli_rejects_provider_failure_after_successful_tools(self):
        self.assert_live_cli_exit(
            [("validate_products", "success"), ("check_knowledge", "success")], 1,
            status="failed", code="http_error_502",
        )


if __name__ == "__main__":
    unittest.main()
