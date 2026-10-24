"""Offline prompt/structure checks; these cannot prove live model equivalence."""
from copy import deepcopy
import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import sync_catalogue as sync
from tools.measure_v21_prompts import report


class PromptOptimizationTests(unittest.TestCase):
    def setUp(self):
        self.before = sync.load_dataset(sync.WORKFLOW_TEMPLATE)
        sync.apply_test_settings(self.before)
        sync.apply_extraction_reliability(self.before)
        self.after = deepcopy(self.before)
        sync.apply_prompt_optimization(self.after)

    def test_only_two_instruction_values_change_in_the_entire_twenty_node_graph(self):
        restored = deepcopy(self.after)
        changed = []
        for identifier, key in ((sync.EXTRACTOR_ID, "description"), (sync.RECOMMENDATION_ID, "systemPrompt")):
            self.assertNotEqual(sync.node_input(self.before, identifier, key), sync.node_input(restored, identifier, key))
            sync.node_input(restored, identifier, key)["value"] = sync.node_input(self.before, identifier, key)["value"]
            changed.append((identifier, key))
        self.assertEqual(restored, self.before)
        self.assertEqual((len(self.after["nodes"]), len(self.after["edges"])), (20, 18))
        for identifier in (sync.EXTRACTOR_ID, sync.RECOMMENDATION_ID):
            self.assertEqual(sync.node_input(self.after, identifier, "history")["value"], 6)
            self.assertEqual(sync.node_input(self.after, identifier, "model")["value"], "")
        self.assertEqual(sync.check_workflow_inputs(self.after), [])
        self.assertEqual(sync.node_input(self.after, sync.RECOMMENDATION_ID, "maxToken")["value"], 4096)

    def test_interpolation_sources_order_and_occurrences_are_exactly_preserved(self):
        pattern = r"\{\{\$([^.$]+)\.([^$]+)\$\}\}"
        original = sync.node_input(self.before, sync.RECOMMENDATION_ID, "systemPrompt")["value"]
        optimized = sync.node_input(self.after, sync.RECOMMENDATION_ID, "systemPrompt")["value"]
        references = [(sync.GUARD_ID, "school1bTargets"), (sync.QUERY_BUILDER_ID, "school1bHistory"), ("VARIABLE_NODE_ID", "fD4C5VOp")]
        self.assertEqual(re.findall(pattern, original), references)
        self.assertEqual(re.findall(pattern, optimized), references)
        for identifier, key in ((sync.EXTRACTOR_ID, "content"), (sync.EXTRACTOR_ID, "extractKeys"),
                                (sync.RECOMMENDATION_ID, "quoteQA"), (sync.RECOMMENDATION_ID, "userChatInput"),
                                (sync.RECOMMENDATION_ID, "fileUrlList")):
            self.assertEqual(sync.node_input(self.after, identifier, key), sync.node_input(self.before, identifier, key))

    def test_extraction_rule_inventory_and_reliability_appendix_are_preserved(self):
        prompt = sync.node_input(self.after, sync.EXTRACTOR_ID, "description")["value"]
        self.assertTrue(prompt.endswith(sync.EXTRACTION_RULES.read_text(encoding="utf-8")))
        # Review anchors cover the distinct original rule groups, not token count
        # alone. Human/live review is still necessary for semantic equivalence.
        for clause in ["never mix their fields", "newest valid correction wins", "hard maximum", "never increase", "round up",
                       "none, cheaper, more_expensive or alternative", "supported, unsupported, help or unrelated",
                       "not help/unrelated", "unless explicitly updated", "unsure which device", "only if clearly relevant",
                       "never substitute", "repeated/stylistic", "greeting plus a product request", "not reinterpret",
                       "category, budget and main_usage", "product_requests_json", "missing_fields_json", "No product recommendations",
                       "Never convert explicitly foreign", "Do not invent an exchange rate"]:
            self.assertIn(clause.lower(), prompt.lower(), clause)
        for category in sync.load_dataset(sync.TEST_DATASET)["supported_categories"]:
            self.assertIn(category, prompt)

    def test_recommendation_safety_comparison_language_and_output_rules_remain_explicit(self):
        prompt = sync.node_input(self.after, sync.RECOMMENDATION_ID, "systemPrompt")["value"]
        for clause in ["only these current-turn requests", "unique same-category", "retrieved product records", "outside/model knowledge",
                       "not live retailer prices", "Never relabel or substitute", "<= the active hard budget", "around/about/approximately/roughly",
                       "explicitly changed", "supports the requested main usage", "exactly match the retrieved record",
                       "not recommendation ranking", "at most one", "strictly lower", "strictly higher", "different product",
                       "no valid same-category", "cheapest category/usage match exceeds budget", "clarification_needed is always false",
                       "Use English", "product/source names exactly", "unless that translated form is provided",
                       "two short sentences", "one short beginner-friendly sentence", "unless explicitly asked", "unless needed for clarity",
                       "No Markdown", "Do not change string values", "recommendations=[]"]:
            self.assertIn(clause.lower(), prompt.lower(), clause)
        example = next(line for line in prompt.splitlines() if line.startswith('{"answer":'))
        data = json.loads(example)
        self.assertEqual(set(data), {"answer", "recommendations", "next_step", "clarification_needed"})
        self.assertIs(data["clarification_needed"], False)
        self.assertEqual(set(data["recommendations"][0]), {"category", "recommended_product", "price", "reason", "source"})
        self.assertIsInstance(data["recommendations"][0]["price"], int)

    def test_estimates_are_explicit_heuristics_and_manifest_records_exact_source_hashes(self):
        result = report()
        self.assertIn("not a GLM tokenizer", result["estimate_method"])
        self.assertIn("not a confidence interval", result["limitations"])
        self.assertEqual(result["original"]["state_extraction"]["characters"], 11634)
        self.assertEqual(result["original"]["recommendation"]["characters"], 11087)
        for name, text in sync.optimized_prompt_values().items():
            metrics = result["optimized"][name]
            self.assertEqual(metrics["characters"], len(text))
            self.assertEqual(metrics["utf8_bytes"], len(text.encode("utf-8")))
            self.assertEqual(metrics["rough_tokens_chars_div_4"], (len(text) + 3) // 4)
            self.assertLess(metrics["characters"], result["original"][name]["characters"])
        for fixture in result["fixture_rendered_recommendation_system_prompt_only"].values():
            self.assertLess(fixture["optimized"]["characters"], fixture["original"]["characters"])
        outputs = sync.render_outputs(sync.load_dataset(sync.TEST_DATASET))
        manifest = json.loads(outputs["manifest.json"])
        for path in (sync.STATE_EXTRACTION_PROMPT, sync.RECOMMENDATION_PROMPT):
            self.assertEqual(manifest["prompt_optimization"]["source_sha256"][path.name], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_changed_source_or_missing_added_duplicate_interpolation_fails_closed(self):
        altered = deepcopy(self.before)
        sync.node_input(altered, sync.RECOMMENDATION_ID, "systemPrompt")["value"] += " changed"
        with self.assertRaisesRegex(ValueError, "unexpected source prompt"): sync.apply_prompt_optimization(altered)
        original = sync.RECOMMENDATION_PROMPT.read_text(encoding="utf-8")
        reference = "{{$tWP2LwPvzFadPPtk.school1bTargets$}}"
        for text in (original.replace(reference, ""), original + reference, original + " {{$unknown.node$}}", ""):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "prompt.txt"
                path.write_text(text, encoding="utf-8")
                with patch.object(sync, "RECOMMENDATION_PROMPT", path):
                    with self.assertRaises(ValueError): sync.apply_prompt_optimization(deepcopy(self.before))


if __name__ == "__main__":
    unittest.main()
