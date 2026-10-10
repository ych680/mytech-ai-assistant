"""Offline executor tests; only temporary fixtures may be written."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import tool3_executor as executor


def tool_call(name="validate_products", call_id="call_1", arguments=None):
    if arguments is None:
        arguments = {"dataset": "selected_dataset"}
        if name == "check_knowledge":
            arguments["knowledge"] = "selected_knowledge"
    return {
        "id": call_id, "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }


class Tool3ExecutorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset_bytes = executor.validate_products.DEFAULT_DATASET.read_bytes()
        cls.knowledge_bytes = executor.DEFAULT_KNOWLEDGE.read_bytes()
        cls.catalogue = json.loads(cls.dataset_bytes)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.dataset_path = self.directory / "products.json"
        self.knowledge_path = self.directory / "knowledge.md"
        self.dataset_path.write_bytes(self.dataset_bytes)
        self.knowledge_path.write_bytes(self.knowledge_bytes)
        self.bindings = executor.ResourceBindings(self.dataset_path, self.knowledge_path)

    def tearDown(self):
        self.assertEqual(self.dataset_bytes, executor.validate_products.DEFAULT_DATASET.read_bytes())
        self.assertEqual(self.knowledge_bytes, executor.DEFAULT_KNOWLEDGE.read_bytes())

    def snapshot(self):
        return {
            str(path.relative_to(self.directory)): (
                path.read_bytes() if path.is_file() else None, path.stat().st_mtime_ns,
            )
            for path in self.directory.rglob("*")
        }

    def execute(self, calls, bindings=None):
        before = self.snapshot()
        with patch("socket.create_connection", side_effect=AssertionError("Network forbidden")), \
             patch("socket.socket.connect", side_effect=AssertionError("Network forbidden")), \
             patch("subprocess.Popen", side_effect=AssertionError("Subprocess forbidden")):
            result = executor.execute_tool_calls(
                calls, bindings=self.bindings if bindings is None else bindings,
            )
        self.assertEqual(before, self.snapshot())
        json.dumps(result, allow_nan=False)
        return result

    def reject(self, calls):
        before = self.snapshot()
        with patch.object(executor, "_check_resource") as resource_check, \
             patch.object(executor.validate_products, "load_dataset") as load, \
             patch.object(executor.build_knowledge, "check_knowledge") as check:
            with self.assertRaises(executor.ToolCallError):
                executor.execute_tool_calls(calls, bindings=self.bindings)
            resource_check.assert_not_called()
            load.assert_not_called()
            check.assert_not_called()
        self.assertEqual(before, self.snapshot())

    def write_dataset(self, dataset):
        self.dataset_path.write_text(json.dumps(dataset), encoding="utf-8")

    def test_valid_dataset_validation(self):
        result = self.execute([tool_call()])
        self.assertTrue(result["ok"])
        self.assertEqual(result["results"], [{
            "tool_call_id": "call_1", "name": "validate_products", "status": "success",
            "code": "ok", "diagnostics": [],
            "data": {"products": 27, "categories": 9, "strict_v1": True},
        }])

    def test_standalone_knowledge_check_validates_first(self):
        events = []
        validate = executor.validate_products.validate_dataset
        check = executor.build_knowledge.check_knowledge

        def validation(*args, **kwargs):
            events.append("validate")
            return validate(*args, **kwargs)

        def knowledge(*args):
            events.append("check")
            return check(*args)

        with patch.object(executor.validate_products, "validate_dataset", side_effect=validation), \
             patch.object(executor.build_knowledge, "check_knowledge", side_effect=knowledge):
            result = self.execute([tool_call("check_knowledge")])
        self.assertEqual(events, ["validate", "check"])
        self.assertTrue(result["ok"])
        self.assertEqual(result["results"][0]["data"], {"records": 27})

    def test_sequential_calls_share_validated_snapshot(self):
        with patch.object(executor.validate_products, "load_dataset", wraps=executor.validate_products.load_dataset) as load, \
             patch.object(executor.validate_products, "validate_dataset", wraps=executor.validate_products.validate_dataset) as validate:
            result = self.execute([tool_call(), tool_call("check_knowledge", "call_2")])
        self.assertTrue(result["ok"])
        self.assertEqual([r["tool_call_id"] for r in result["results"]], ["call_1", "call_2"])
        load.assert_called_once_with(self.dataset_path.resolve())
        validate.assert_called_once()
        self.assertTrue(validate.call_args.kwargs["strict_v1"])

    def test_invalid_dataset_returns_diagnostics(self):
        dataset = deepcopy(self.catalogue)
        dataset["products"][0]["price_rmb"] = False
        self.write_dataset(dataset)
        result = self.execute([tool_call()])
        self.assertFalse(result["ok"])
        row = result["results"][0]
        self.assertEqual((row["status"], row["code"]), ("failed", "dataset_invalid"))
        self.assertIsNone(row["data"])
        self.assertTrue(any("price_rmb" in error for error in row["diagnostics"]))

    def test_failed_validation_skips_all_knowledge_access(self):
        self.write_dataset({})
        for calls in ([tool_call("check_knowledge")],
                      [tool_call(), tool_call("check_knowledge", "call_2")]):
            with self.subTest(calls=len(calls)), \
                 patch.object(executor, "_read_knowledge") as read, \
                 patch.object(executor.build_knowledge, "check_knowledge") as check:
                result = self.execute(calls)
                self.assertFalse(result["ok"])
                self.assertEqual(result["results"][-1]["status"], "skipped")
                self.assertEqual(result["results"][-1]["code"], "dataset_invalid")
                read.assert_not_called()
                check.assert_not_called()

    def test_default_bindings_are_repository_anchored_and_strict(self):
        with patch("os.getcwd", return_value=str(self.directory)):
            result = executor.execute_tool_calls([tool_call(), tool_call("check_knowledge", "call_2")])
        self.assertTrue(result["ok"])
        self.assertTrue(result["results"][0]["data"]["strict_v1"])

    def test_validation_policy_is_controlled_locally(self):
        dataset = deepcopy(self.catalogue)
        dataset["dataset_name"] = "Another catalogue"
        self.write_dataset(dataset)
        self.assertFalse(self.execute([tool_call()])["ok"])
        general = executor.ResourceBindings(self.dataset_path, self.knowledge_path, strict_v1=False)
        result = self.execute([tool_call()], bindings=general)
        self.assertTrue(result["ok"])
        self.assertFalse(result["results"][0]["data"]["strict_v1"])
        self.reject([tool_call(arguments={"dataset": "selected_dataset", "strict_v1": False})])

    def test_knowledge_mismatch_is_an_operational_failure(self):
        self.knowledge_path.write_text("# Wrong knowledge\n", encoding="utf-8")
        result = self.execute([tool_call("check_knowledge")])
        row = result["results"][0]
        self.assertFalse(result["ok"])
        self.assertEqual((row["status"], row["code"]), ("failed", "knowledge_inconsistent"))
        self.assertTrue(row["diagnostics"])

    def test_many_validation_errors_are_truncated_and_dependents_skipped(self):
        dataset = deepcopy(self.catalogue)
        for product in dataset["products"]:
            product["price_rmb"] = 0
            product["source"] = ""
            product["tier"] = "invalid"
        self.write_dataset(dataset)
        diagnostics = executor.validate_products.validate_dataset(dataset, strict_v1=True)
        self.assertGreater(len(diagnostics), executor.MAX_DIAGNOSTICS)
        with patch.object(executor, "_read_knowledge") as read:
            result = self.execute([tool_call(), tool_call("check_knowledge", "call_2")])
        read.assert_not_called()
        self.assertFalse(result["ok"])
        self.assertEqual([row["status"] for row in result["results"]], ["failed", "skipped"])
        for row in result["results"]:
            self.assertEqual(row["code"], "dataset_invalid")
            self.assertIsNone(row["data"])
            self.assertEqual(len(row["diagnostics"]), executor.MAX_DIAGNOSTICS)
            self.assertEqual(row["diagnostics"][:-1], diagnostics[:executor.MAX_DIAGNOSTICS - 1])
            omitted = len(diagnostics) - (executor.MAX_DIAGNOSTICS - 1)
            self.assertEqual(row["diagnostics"][-1],
                             f"Diagnostics truncated: {omitted} additional messages omitted.")

    def test_many_knowledge_mismatches_are_truncated(self):
        text = "\n".join(
            line.partition(":")[0] + ": changed"
            if line.startswith(("Reference Price:", "Tier:", "Source:")) else line
            for line in self.knowledge_bytes.decode("utf-8").splitlines()
        )
        self.knowledge_path.write_text(text, encoding="utf-8")
        diagnostics = executor.build_knowledge.check_knowledge(self.catalogue, text)
        self.assertGreater(len(diagnostics), executor.MAX_DIAGNOSTICS)
        result = self.execute([
            tool_call("check_knowledge"), tool_call("check_knowledge", "call_2"),
        ])
        self.assertFalse(result["ok"])
        for row in result["results"]:
            self.assertEqual((row["status"], row["code"]), ("failed", "knowledge_inconsistent"))
            self.assertIsNone(row["data"])
            self.assertEqual(len(row["diagnostics"]), executor.MAX_DIAGNOSTICS)
            self.assertEqual(row["diagnostics"][:-1], diagnostics[:executor.MAX_DIAGNOSTICS - 1])
            omitted = len(diagnostics) - (executor.MAX_DIAGNOSTICS - 1)
            self.assertEqual(row["diagnostics"][-1],
                             f"Diagnostics truncated: {omitted} additional messages omitted.")

    def test_diagnostics_limit_boundary_for_both_operations(self):
        for name, module, function, code in (
            ("validate_products", executor.validate_products, "validate_dataset", "dataset_invalid"),
            ("check_knowledge", executor.build_knowledge, "check_knowledge", "knowledge_inconsistent"),
        ):
            for count in (executor.MAX_DIAGNOSTICS - 1, executor.MAX_DIAGNOSTICS,
                          executor.MAX_DIAGNOSTICS + 1):
                with self.subTest(tool=name, count=count):
                    diagnostics = [f"Error {index}" for index in range(count)]
                    original = diagnostics.copy()
                    with patch.object(module, function, return_value=diagnostics):
                        result = self.execute([tool_call(name)])
                    self.assertFalse(result["ok"])
                    row = result["results"][0]
                    self.assertEqual((row["status"], row["code"]), ("failed", code))
                    if count <= executor.MAX_DIAGNOSTICS:
                        self.assertEqual(row["diagnostics"], original)
                    else:
                        self.assertEqual(row["diagnostics"], original[:executor.MAX_DIAGNOSTICS - 1] + [
                            "Diagnostics truncated: 2 additional messages omitted.",
                        ])
                    self.assertEqual(diagnostics, original)

    def test_successful_results_are_unchanged(self):
        result = self.execute([tool_call(), tool_call("check_knowledge", "call_2")])
        self.assertEqual(result, {"ok": True, "results": [
            {"tool_call_id": "call_1", "name": "validate_products", "status": "success",
             "code": "ok", "diagnostics": [],
             "data": {"products": 27, "categories": 9, "strict_v1": True}},
            {"tool_call_id": "call_2", "name": "check_knowledge", "status": "success",
             "code": "ok", "diagnostics": [], "data": {"records": 27}},
        ]})

    def test_unknown_tools_and_writing_operations_are_rejected(self):
        for name in ("generate_knowledge", "render_knowledge", "main", "__import__", "os.system", "", [], None):
            with self.subTest(name=name):
                self.reject([tool_call(name=name)])

    def test_malformed_and_non_object_json(self):
        for raw in ("", "{", "{} trailing", "[]", "null", "true", '"text"', "12",
                    '{"dataset":"selected_dataset",}', "[" * 1500 + "]" * 1500):
            with self.subTest(raw=raw[:30]):
                call = tool_call()
                call["function"]["arguments"] = raw
                self.reject([call])

    def test_duplicate_json_keys_including_nested_and_escaped(self):
        for raw in (
            '{"dataset":"selected_dataset","dataset":"selected_dataset"}',
            '{"dataset":"selected_dataset","\\u0064ataset":"selected_dataset"}',
            '{"dataset":{"x":1,"x":2}}',
        ):
            call = tool_call()
            call["function"]["arguments"] = raw
            self.reject([call])

    def test_nonstandard_constants_and_unsupported_values(self):
        for value in ("NaN", "Infinity", "-Infinity", "1e400", "null", "false", "1", "[]", "{}"):
            with self.subTest(value=value):
                call = tool_call()
                call["function"]["arguments"] = '{"dataset":' + value + '}'
                self.reject([call])

    def test_paths_urls_and_unknown_identifiers_are_rejected(self):
        for value in ("other_dataset", "../products.json", "C:\\private\\products.json",
                      "/tmp/products.json", "https://example.invalid/products.json", ".env", ".env2"):
            with self.subTest(value=value):
                self.reject([tool_call(arguments={"dataset": value})])
        self.reject([tool_call("check_knowledge", arguments={
            "dataset": "selected_dataset", "knowledge": "other_knowledge",
        })])

    def test_extra_missing_and_wrongly_typed_arguments(self):
        for arguments in ({}, {"dataset": "selected_dataset", "output": "new.md"},
                          {"dataset": "selected_dataset", "command": "anything"},
                          {"dataset": True}, {"dataset": 1}, {"dataset": ["selected_dataset"]},
                          {"dataset": "selected_dataset", "knowledge": "selected_knowledge"}):
            with self.subTest(arguments=arguments):
                self.reject([tool_call(arguments=arguments)])
        self.reject([tool_call("check_knowledge", arguments={"dataset": "selected_dataset"})])
        for raw in ({}, None, b"{}", 123):
            call = tool_call()
            call["function"]["arguments"] = raw
            self.reject([call])

    def test_call_id_validation(self):
        for call_id in ("", "with space", "line\nbreak", "中文", "x" * 129, None, 1, []):
            with self.subTest(call_id=call_id):
                self.reject([tool_call(call_id=call_id)])
        call = tool_call()
        del call["id"]
        self.reject([call])
        self.reject([tool_call(), tool_call("check_knowledge")])
        result = self.execute([tool_call(call_id="A" * 128)])
        self.assertTrue(result["ok"])

    def test_envelope_and_function_shape_are_exact(self):
        self.reject([None])
        self.reject([[]])
        for change in ("extra", "missing_type", "wrong_type", "extra_function_key", "missing_name", "not_function"):
            with self.subTest(change=change):
                call = tool_call()
                if change == "extra":
                    call["extra"] = "ignored?"
                elif change == "missing_type":
                    del call["type"]
                elif change == "wrong_type":
                    call["type"] = "other"
                elif change == "extra_function_key":
                    call["function"]["extra"] = True
                elif change == "missing_name":
                    del call["function"]["name"]
                else:
                    call["function"] = "validate_products"
                self.reject([call])

    def test_invalid_later_call_rejects_entire_batch(self):
        self.reject([tool_call(), tool_call("generate_knowledge", "call_2")])

    def test_batch_limits(self):
        for calls in ([], None, {}, (), iter([tool_call()]),
                      [tool_call(call_id=f"call_{i}") for i in range(executor.MAX_CALLS + 1)]):
            self.reject(calls)
        result = self.execute([tool_call(call_id=f"call_{i}") for i in range(executor.MAX_CALLS)])
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["results"]), executor.MAX_CALLS)

    def test_argument_size_and_unicode_limits(self):
        call = tool_call()
        raw = call["function"]["arguments"]
        call["function"]["arguments"] = raw + " " * (executor.MAX_ARGUMENT_BYTES - len(raw))
        self.assertTrue(self.execute([call])["ok"])
        call["function"]["arguments"] += " "
        self.reject([call])
        for raw in ('{"dataset":"' + "中" * 1500 + '"}', "\ud800"):
            call["function"]["arguments"] = raw
            self.reject([call])

    def test_dataset_io_and_parse_failures_skip_knowledge(self):
        for payload in (b"{", b"\xff", b'{"x":1,"x":2}', b'{"x":1e400}'):
            with self.subTest(payload=payload):
                self.dataset_path.write_bytes(payload)
                with patch.object(executor, "_read_knowledge") as read:
                    result = self.execute([tool_call(), tool_call("check_knowledge", "call_2")])
                self.assertEqual(result["results"][0]["code"], "dataset_read_error")
                self.assertEqual(result["results"][1]["status"], "skipped")
                read.assert_not_called()
        missing = executor.ResourceBindings(self.directory / "missing.json", self.knowledge_path)
        self.assertEqual(self.execute([tool_call()], missing)["results"][0]["code"], "dataset_read_error")

    def test_knowledge_io_and_encoding_failures(self):
        self.knowledge_path.write_bytes(b"\xff")
        self.assertEqual(self.execute([tool_call("check_knowledge")])["results"][0]["code"], "knowledge_read_error")
        missing = executor.ResourceBindings(self.dataset_path, self.directory / "missing.md")
        result = self.execute([tool_call(), tool_call("check_knowledge", "call_2")], missing)
        self.assertEqual([r["status"] for r in result["results"]], ["success", "failed"])
        self.assertFalse(result["ok"])
        with patch.object(executor, "_read_knowledge", side_effect=PermissionError("private path")):
            row = self.execute([tool_call("check_knowledge")])["results"][0]
        self.assertEqual(row["code"], "knowledge_read_error")
        self.assertNotIn("private path", json.dumps(row))

    def test_resource_limits_and_regular_files(self):
        self.dataset_path.write_bytes(b" " * (executor.MAX_RESOURCE_BYTES + 1))
        self.assertEqual(self.execute([tool_call()])["results"][0]["code"], "dataset_read_error")
        self.dataset_path.write_bytes(self.dataset_bytes)
        self.knowledge_path.write_bytes(b" " * (executor.MAX_RESOURCE_BYTES + 1))
        self.assertEqual(self.execute([tool_call("check_knowledge")])["results"][0]["code"], "knowledge_read_error")
        directory = self.directory / "folder.json"
        directory.mkdir()
        bindings = executor.ResourceBindings(directory, self.knowledge_path)
        self.assertEqual(self.execute([tool_call()], bindings)["results"][0]["code"], "dataset_read_error")

    def test_repeated_checks_reuse_snapshot_but_next_batch_revalidates(self):
        calls = [tool_call("check_knowledge"), tool_call("check_knowledge", "call_2")]
        with patch.object(executor, "_read_knowledge", wraps=executor._read_knowledge) as read:
            self.assertTrue(self.execute(calls)["ok"])
            read.assert_called_once()
        self.write_dataset({})
        self.assertFalse(self.execute(calls)["ok"])

    def test_lf_and_crlf_knowledge_are_consistent(self):
        for newline in (b"\n", b"\r\n"):
            self.knowledge_path.write_bytes(self.knowledge_bytes.replace(b"\r\n", b"\n").replace(b"\n", newline))
            self.assertTrue(self.execute([tool_call("check_knowledge")])["ok"])

    def test_local_configuration_errors(self):
        for strict_v1 in ("false", 0, None):
            with self.assertRaises(ValueError):
                executor.ResourceBindings(strict_v1=strict_v1)
        for field, value in (("dataset_path", self.directory / "other.txt"),
                             ("knowledge_path", self.directory / "other.json")):
            with self.assertRaises(ValueError):
                executor.ResourceBindings(**{field: value})
        with self.assertRaises(TypeError):
            executor.execute_tool_calls([tool_call()], bindings={"dataset_path": self.dataset_path})


if __name__ == "__main__":
    unittest.main()
