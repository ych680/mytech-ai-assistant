"""Offline prompt estimates only: no tokenizer download, credentials or live calls."""

import json
import re

try:
    from . import sync_catalogue as sync
except ImportError:
    import sync_catalogue as sync


def report():
    template = sync.load_dataset(sync.WORKFLOW_TEMPLATE)
    workflow = sync.deepcopy(template)
    sync.apply_test_settings(workflow)
    sync.apply_extraction_reliability(workflow)
    sync.apply_prompt_optimization(workflow)
    result = sync.prompt_optimization_metadata(template, workflow)
    result["input_limits"] = {"state_extraction_history": sync.node_input(workflow, sync.EXTRACTOR_ID, "history")["value"],
                              "recommendation_history": sync.node_input(workflow, sync.RECOMMENDATION_ID, "history")["value"],
                              "recommendation_max_tokens": sync.node_input(workflow, sync.RECOMMENDATION_ID, "maxToken")["value"]}
    result["unchanged_extraction_schema"] = sync.prompt_size_estimate(sync.script_json(sync.node_input(workflow, sync.EXTRACTOR_ID, "extractKeys")["value"]))
    dataset = sync.load_dataset(sync.TEST_DATASET)
    products = {product["id"]: product for product in dataset["products"]}
    first = {category: next(product for product in dataset["products"] if product["category"] == category)
             for category in dataset["supported_categories"]}
    def request(product):
        return {"category": product["category"], "budget": product["price_rmb"], "main_usage": product["main_usage"][0]}
    anchor = products["MOU-002"]
    history = [{"category": anchor["category"], "recommended_product": anchor["product"], "price": anchor["price_rmb"],
                "reason": "Matches the requested usage.", "source": anchor["source"]}]
    fixtures = {
        "single_request": ([{"category": "Laptop", "budget": 6000, "main_usage": "gaming"}], [], "none"),
        "nine_requests": ([request(product) for product in first.values()], [], "none"),
        "targeted_follow_up": ([{"category": "Mouse", "budget": 300, "main_usage": "gaming"}], history, "cheaper"),
    }
    prompts = {"original": sync.original_prompt_values(template)["recommendation"],
               "optimized": sync.node_input(workflow, sync.RECOMMENDATION_ID, "systemPrompt")["value"]}
    result["fixture_rendered_recommendation_system_prompt_only"] = {}
    for name, (requests, previous, intent) in fixtures.items():
        values = {("tWP2LwPvzFadPPtk", "school1bTargets"): requests,
                  ("sxwN5Fd17Tc8leTf", "school1bHistory"): previous,
                  ("VARIABLE_NODE_ID", "fD4C5VOp"): intent}
        estimates = {}
        for version, prompt in prompts.items():
            # Compact JSON interpolation is an explicit fixture assumption;
            # the school runtime's actual serialization/token overhead is unknown.
            rendered = re.sub(r"\{\{\$([^.$]+)\.([^$]+)\$\}\}",
                              lambda match: json.dumps(values[match[1], match[2]], ensure_ascii=False, separators=(",", ":")), prompt)
            estimates[version] = sync.prompt_size_estimate(rendered)
        result["fixture_rendered_recommendation_system_prompt_only"][name] = estimates
    result["limitations"] = "No live history, RAG quotes, runtime wrappers, current-question or output token totals included; no GLM tokenizer available. Sensitivity range is not a confidence interval."
    return result


if __name__ == "__main__":
    print(json.dumps(report(), ensure_ascii=False, indent=2))
