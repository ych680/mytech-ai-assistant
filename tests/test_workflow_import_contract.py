"""Regressions against the complete sanitized working Current export, offline."""

from copy import deepcopy
import hashlib
import json
import unittest
from unittest.mock import patch

from tools import sync_catalogue as sync
from tools.validate_products import load_dataset, TEST_DATASET


RETRIEVAL = "zWAw4oYVL1QMe8YX"
QUERY = "sxwN5Fd17Tc8leTf"
QUERY_OUTPUT = "qLUQfhG0ILRX"
NODE_IDS = [
    "userGuide", "448745", "etNrwEXVwr5sySpK", "tWP2LwPvzFadPPtk",
    "hMbWAx9XxkNcfG6V", "yrfKbYdd3I61H9JN", "bgcB6pN1kaSjIiAk",
    "wwmnkseAaXixej19", "fzgLdGhMS3eMuqQt", "ikIzMK483vihRths",
    "pskHz4kajjJnBWwG", "fakNM8mmlYmewx67", "p4ZeCJXrGirXAQCz",
    "oibK1q4js1HXjiO2", "zh9L8VeY9vKm3WnU", "b0vXntQUXZL2Mk5m",
    "d6kCXfQ1mcJ5hT8J", RETRIEVAL, QUERY,
]


def node(graph, identifier):
    return next(item for item in graph["nodes"] if item["nodeId"] == identifier)


def field(graph, identifier, key):
    return next(item for item in node(graph, identifier)["inputs"] if item["key"] == key)


class WorkflowImportContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = load_dataset(sync.WORKFLOW_TEMPLATE)
        cls.generated = load_dataset(sync.ROOT / sync.OUTPUT_SUBDIR / sync.WORKFLOW)
        cls.expected = deepcopy(cls.original)
        sync.apply_test_settings(cls.expected)
        sync.apply_extraction_reliability(cls.expected)
        sync.apply_prompt_optimization(cls.expected)

    def test_template_is_the_reviewed_sanitized_current_snapshot(self):
        # Derived from the supplied working export with only documented account
        # redactions. Updating this fingerprint requires a new baseline review.
        self.assertEqual(hashlib.sha256(sync.json_text(self.original).encode("utf-8")).hexdigest(),
                         "58be7b69fd8a644eb2dc0118b51567e973749cc5d371a24f7074e200504c08e1")

    def test_entire_current_structure_is_preserved_except_authorized_validation_code(self):
        self.assertEqual([n["nodeId"] for n in self.original["nodes"]], NODE_IDS)
        self.assertEqual([n["nodeId"] for n in self.generated["nodes"]], NODE_IDS + [sync.NORMALIZER_ID])
        self.assertEqual(len(self.generated["edges"]), 18)
        self.assertEqual(list(self.generated), ["nodes", "edges", "chatConfig"])
        self.assertEqual(self.generated["edges"], self.expected["edges"])
        self.assertEqual(self.generated["edges"][2:], self.original["edges"][1:])
        self.assertEqual(self.generated["chatConfig"], self.original["chatConfig"])
        for original in self.expected["nodes"]:
            actual = node(self.generated, original["nodeId"])
            self.assertEqual(actual["outputs"], original["outputs"])
            if original["nodeId"] != sync.VALIDATOR_ID:
                self.assertEqual(actual, original)
            else:
                restored = deepcopy(actual)
                next(i for i in restored["inputs"] if i["key"] == "code")["value"] = field(self.original, sync.VALIDATOR_ID, "code")["value"]
                self.assertEqual(restored, original)
        sync.assert_workflow_contract(self.original, self.generated)

    def test_current_retrieval_and_scalar_query_are_copied_without_schema_conversion(self):
        self.assertEqual(node(self.generated, RETRIEVAL), node(self.expected, RETRIEVAL))
        self.assertEqual(node(self.generated, QUERY), node(self.original, QUERY))
        self.assertEqual(node(self.generated, RETRIEVAL)["version"], "4.9.2")
        query = field(self.generated, RETRIEVAL, "userChatInput")
        self.assertEqual(query["valueType"], "string")
        self.assertEqual(query["value"], [QUERY, QUERY_OUTPUT])
        self.assertNotIn("selectedType", query)
        self.assertNotIn("datasetSearchInput", [i["key"] for i in node(self.generated, RETRIEVAL)["inputs"]])
        self.assertEqual(field(self.generated, QUERY, "user_question")["value"], ["448745", "userChatInput"])
        output = next(o for o in node(self.generated, QUERY)["outputs"] if o["id"] == QUERY_OUTPUT)
        self.assertEqual((output["key"], output["valueType"]), ("retrieval_query", "string"))

    def test_current_model_structure_is_native_and_bindings_are_manual(self):
        for identifier in ("etNrwEXVwr5sySpK", "ikIzMK483vihRths", "pskHz4kajjJnBWwG"):
            model = field(self.generated, identifier, "model")
            self.assertEqual(model, field(self.original, identifier, "model"))
            self.assertEqual(model["value"], "")
            self.assertNotIn("modelId", [i["key"] for i in node(self.generated, identifier)["inputs"]])
        self.assertEqual(field(self.generated, RETRIEVAL, "datasets")["value"], [])
        self.assertNotIn("_id", self.generated["chatConfig"])
        sync.assert_portable(self.generated)

    def test_all_globals_conditions_updates_and_prompt_interpolations_match_current(self):
        self.assertEqual([v["key"] for v in self.generated["chatConfig"]["variables"]],
                         ["tsPXY04c", "abIVSlbb", "w967Jp1P", "dMoZisLb", "fD4C5VOp"])
        for original in self.expected["nodes"]:
            for item in original.get("inputs", []):
                if item["key"] != "code":
                    self.assertEqual(field(self.generated, original["nodeId"], item["key"]), item)
        self.assertEqual(sync.check_workflow_inputs(self.original), [])
        self.assertEqual(sync.check_workflow_inputs(self.generated), [])

    def test_implicit_runtime_user_files_are_preserved_but_unknown_outputs_fail(self):
        for identifier in ("ikIzMK483vihRths", "pskHz4kajjJnBWwG"):
            self.assertEqual(field(self.generated, identifier, "fileUrlList")["value"], [["448745", "userFiles"]])
        graph = deepcopy(self.generated)
        field(graph, "ikIzMK483vihRths", "fileUrlList")["value"] = [[QUERY, "userFiles"]]
        self.assertTrue(any("unresolved reference" in error for error in sync.check_workflow_inputs(graph)))

    def test_only_four_reviewed_parameter_changes_are_permitted(self):
        changes = []
        for original in self.original["nodes"]:
            for item in original.get("inputs", []):
                actual = field(self.generated, original["nodeId"], item["key"])
                prompt_overlay = (original["nodeId"] == sync.EXTRACTOR_ID and item["key"] in ("content", "description")) or (original["nodeId"] == sync.RECOMMENDATION_ID and item["key"] == "systemPrompt")
                if actual != item and item["key"] != "code" and not prompt_overlay:
                    changes.append((original["nodeId"], item["key"], actual.get("value")))
                    restored = deepcopy(actual)
                    if "value" in item: restored["value"] = item["value"]
                    else: restored.pop("value", None)
                    self.assertEqual(restored, item)
        self.assertEqual(changes, [("ikIzMK483vihRths", "maxToken", 800),
                                   ("ikIzMK483vihRths", "aiChatReasoning", False),
                                   ("pskHz4kajjJnBWwG", "maxToken", 4096),
                                   (RETRIEVAL, "similarity", 0.35)])
        graph = deepcopy(self.generated)
        field(graph, RETRIEVAL, "similarity")["value"] = 0.4
        with self.assertRaises(ValueError): sync.assert_workflow_contract(self.original, graph)
        settings = sync.test_settings()
        self.assertEqual(settings["retrieval_similarity"], 0.35)
        with patch.object(sync, "load_dataset", return_value={**settings, "retrieval_similarity": 0.4}):
            with self.assertRaisesRegex(ValueError, "0.35"): sync.test_settings()
        manifest = load_dataset(sync.ROOT / sync.OUTPUT_SUBDIR / "manifest.json")
        self.assertEqual(manifest["test_settings"], settings)

    def test_normalization_is_before_extraction_with_original_raw_guard_binding(self):
        first, second = self.generated["edges"][:2]
        self.assertEqual((first["source"], first["target"]), ("448745", sync.NORMALIZER_ID))
        self.assertEqual((second["source"], second["target"]), (sync.NORMALIZER_ID, sync.EXTRACTOR_ID))
        self.assertEqual(field(self.generated, sync.EXTRACTOR_ID, "content")["value"], [sync.NORMALIZER_ID, "v21NormalizedQuestion"])
        self.assertEqual(field(self.generated, sync.GUARD_ID, "user_question"), field(self.original, sync.GUARD_ID, "user_question"))
        self.assertEqual(field(self.generated, sync.EXTRACTOR_ID, "description")["value"],
                         sync.STATE_EXTRACTION_PROMPT.read_text(encoding="utf-8") + sync.EXTRACTION_RULES.read_text(encoding="utf-8"))
        for original in self.original["nodes"]:
            self.assertEqual(node(self.generated, original["nodeId"])["outputs"], original["outputs"])
        native = node(self.generated, sync.NORMALIZER_ID)
        self.assertEqual(native["flowNodeType"], "code")
        self.assertEqual(field(self.generated, sync.NORMALIZER_ID, "codeType"), field(self.original, QUERY, "codeType"))
        self.assertEqual(field(self.generated, sync.NORMALIZER_ID, "user_question")["value"], ["448745", "userChatInput"])
        self.assertEqual(field(self.generated, sync.EXTRACTOR_ID, "extractKeys"), field(self.original, sync.EXTRACTOR_ID, "extractKeys"))
        for target in (sync.NORMALIZER_ID, sync.GUARD_ID):
            graph = deepcopy(self.generated)
            field(graph, target, "code")["value"] += "\n// modified"
            with self.assertRaises(ValueError): sync.assert_workflow_contract(self.original, graph)

    def test_missing_required_inputs_and_extra_fields_are_rejected(self):
        for identifier, key in ((RETRIEVAL, "userChatInput"), (QUERY, "user_question"), (sync.VALIDATOR_ID, "active_requests")):
            for value in (None, [], ""):
                graph = deepcopy(self.generated)
                field(graph, identifier, key)["value"] = value
                with self.assertRaisesRegex(ValueError, "required input is unbound"):
                    sync.assert_workflow_contract(self.original, graph)
        for key in ("search_query", "datasetSearchInput"):
            graph = deepcopy(self.generated)
            node(graph, RETRIEVAL)["inputs"].append({"key": key, "valueType": "string", "required": True,
                                                   "renderTypeList": ["reference"], "value": ["448745", "userChatInput"]})
            with self.assertRaises(ValueError):
                sync.assert_workflow_contract(self.original, graph)

    def test_reference_types_and_node_output_or_global_targets_are_checked(self):
        for reference in (("missing-node", QUERY_OUTPUT), (QUERY, "missing-output"), ("VARIABLE_NODE_ID", "missing-variable"), (QUERY, "school1bHistory")):
            graph = deepcopy(self.generated)
            field(graph, RETRIEVAL, "userChatInput")["value"] = list(reference)
            self.assertTrue(sync.check_workflow_inputs(graph))
            with self.assertRaises(ValueError):
                sync.assert_workflow_contract(self.original, graph)

    def test_nested_update_condition_and_interpolation_references_cannot_drift(self):
        for change in ("update-target", "update-value", "condition", "prompt"):
            graph = deepcopy(self.generated)
            if change == "update-target":
                field(graph, "oibK1q4js1HXjiO2", "updateList")["value"][0]["variable"] = ["VARIABLE_NODE_ID", "missing"]
            elif change == "update-value":
                field(graph, "oibK1q4js1HXjiO2", "updateList")["value"][0]["value"] = [[sync.VALIDATOR_ID, "missing"]]
            elif change == "condition":
                field(graph, "p4ZeCJXrGirXAQCz", "ifElseList")["value"][0]["list"][0]["variable"] = [sync.VALIDATOR_ID, "missing"]
            else:
                field(graph, "pskHz4kajjJnBWwG", "systemPrompt")["value"] += " {{$missing-node.missing-output$}}"
            self.assertTrue(any("unresolved reference" in error for error in sync.check_workflow_inputs(graph)), change)
            with self.assertRaises(ValueError):
                sync.assert_workflow_contract(self.original, graph)

    def test_valid_but_changed_bindings_conditions_and_prompts_are_rejected(self):
        for change in ("update", "condition", "prompt", "query-code", "edge"):
            graph = deepcopy(self.generated)
            if change == "update":
                field(graph, "oibK1q4js1HXjiO2", "updateList")["value"][0]["variable"] = ["VARIABLE_NODE_ID", "tsPXY04c"]
            elif change == "condition":
                field(graph, "p4ZeCJXrGirXAQCz", "ifElseList")["value"][0]["list"][0]["value"] = "false"
            elif change == "prompt":
                field(graph, "pskHz4kajjJnBWwG", "systemPrompt")["value"] += " changed"
            elif change == "query-code":
                field(graph, QUERY, "code")["value"] += "\n// changed"
            else:
                graph["edges"] = list(reversed(graph["edges"]))
            with self.assertRaisesRegex(ValueError, "working Current structure"):
                sync.assert_workflow_contract(self.original, graph)

    def test_duplicates_private_metadata_and_concrete_bindings_fail_closed(self):
        for change in ("node", "input", "output", "global"):
            graph = deepcopy(self.generated)
            if change == "node": graph["nodes"].append(deepcopy(node(graph, QUERY)))
            elif change == "input": node(graph, RETRIEVAL)["inputs"].append(deepcopy(field(graph, RETRIEVAL, "userChatInput")))
            elif change == "output": node(graph, QUERY)["outputs"].append(deepcopy(node(graph, QUERY)["outputs"][-1]))
            else: graph["chatConfig"]["variables"].append(deepcopy(graph["chatConfig"]["variables"][0]))
            self.assertTrue(any("duplicate" in error for error in sync.check_workflow_inputs(graph)))
        for change in ("private", "model", "dataset"):
            graph = deepcopy(self.generated)
            if change == "private": graph["chatConfig"]["_id"] = "private-account-metadata"
            elif change == "model": field(graph, "etNrwEXVwr5sySpK", "model")["value"] = "account-specific-model"
            else: field(graph, RETRIEVAL, "datasets")["value"] = [{"datasetId": "account-specific-dataset"}]
            with self.assertRaises(ValueError): sync.assert_portable(graph)

    def test_generator_checks_contract_and_records_template_provenance(self):
        with patch.object(sync, "assert_workflow_contract", wraps=sync.assert_workflow_contract) as check:
            outputs = sync.render_outputs(load_dataset(TEST_DATASET))
            check.assert_called_once()
        manifest = json.loads(outputs["manifest.json"])
        self.assertEqual(manifest["workflow_template"], "tools/templates/mytech_current_working_portable.json")
        self.assertEqual(len(manifest["workflow_template_sha256"]), 64)
        with patch.object(sync, "assert_workflow_contract", side_effect=ValueError("invalid workflow contract")):
            with self.assertRaisesRegex(ValueError, "invalid workflow contract"):
                sync.render_outputs(load_dataset(TEST_DATASET))


if __name__ == "__main__":
    unittest.main()
