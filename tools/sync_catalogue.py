"""Generate isolated v2.1 TEST assets offline, or verify them without writing.

Only generated/v2_1_test and generated/aiep_v2_1_test under --output-root
are writable. Stable assets are read-only templates. No API is called.
"""

import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re
import sys

try:
    from .build_knowledge import render_knowledge
    from .validate_products import TEST_DATASET, load_dataset, validate_dataset
except ImportError:
    from build_knowledge import render_knowledge
    from validate_products import TEST_DATASET, load_dataset, validate_dataset


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_SUBDIR = Path("generated/v2_1_test")
WORKFLOW = "mytech-fastgpt-workflow-v2_1-TEST.json"
KNOWLEDGE = "MyTech_Product_Knowledge_v2_1_TEST.md"
VALIDATOR_ID = "fakNM8mmlYmewx67"
CATALOG_MARKER = "  const PRODUCT_CATALOG = "
FRONTEND = ROOT / "aiep-candidate/site/index.html"
WORKFLOW_TEMPLATE = ROOT / "tools/templates/mytech_current_working_portable.json"
FRONTEND_VALIDATOR = ROOT / "tools/templates/v21_dataset_validation.js"
USAGE_VALIDATOR = ROOT / "tools/templates/v21_usage_validation.js"
VALIDATION_FAILURE = ROOT / "tools/templates/v21_validation_failure.js"
USAGE_COMPATIBILITY = ROOT / "tools/templates/v21_usage_compatibility.json"
RETRIEVAL_ID = "zWAw4oYVL1QMe8YX"
QUERY_BUILDER_ID = "sxwN5Fd17Tc8leTf"
QUERY_OUTPUT_ID = "qLUQfhG0ILRX"
TEST_SETTINGS = ROOT / "tools/templates/v21_test_settings.json"
FRONTEND_RUNTIME = ROOT / "tools/templates/v21_frontend_runtime.js"
CITATION_HELPERS = ROOT / "mytech_v2_1_test_response.mjs"
NORMALIZER_ID = "v21RmbInputNormalize"
EXTRACTOR_ID = "etNrwEXVwr5sySpK"
GUARD_ID = "tWP2LwPvzFadPPtk"
INPUT_NORMALIZATION = ROOT / "tools/templates/v21_input_normalization.js"
SCOPE_CONSISTENCY = ROOT / "tools/templates/v21_scope_consistency.js"
EXTRACTION_RULES = ROOT / "tools/templates/v21_extraction_rules.txt"
STATE_EXTRACTION_PROMPT = ROOT / "tools/templates/v21_state_extraction_prompt.txt"
RECOMMENDATION_PROMPT = ROOT / "tools/templates/v21_recommendation_prompt.txt"
RECOMMENDATION_ID = "pskHz4kajjJnBWwG"


def original_prompt_values(template):
    return {
        "state_extraction": node_input(template, EXTRACTOR_ID, "description")["value"] + EXTRACTION_RULES.read_text(encoding="utf-8"),
        "recommendation": node_input(template, RECOMMENDATION_ID, "systemPrompt")["value"],
    }


def optimized_prompt_values():
    return {
        "state_extraction": STATE_EXTRACTION_PROMPT.read_text(encoding="utf-8") + EXTRACTION_RULES.read_text(encoding="utf-8"),
        "recommendation": RECOMMENDATION_PROMPT.read_text(encoding="utf-8"),
    }


def apply_prompt_optimization(workflow):
    """Replace only two reviewed instruction strings; never trim context/bindings."""
    original = original_prompt_values(load_dataset(WORKFLOW_TEMPLATE))
    optimized = optimized_prompt_values()
    for label, identifier, key in (("state_extraction", EXTRACTOR_ID, "description"),
                                   ("recommendation", RECOMMENDATION_ID, "systemPrompt")):
        field = node_input(workflow, identifier, key)
        if field["value"] != original[label]:
            raise ValueError(f"{label}: unexpected source prompt; review before optimizing")
        if not optimized[label].strip():
            raise ValueError(f"{label}: empty TEST prompt")
        references = lambda text: re.findall(r"\{\{\$([^.$]+)\.([^$]+)\$\}\}", text)
        if references(optimized[label]) != references(original[label]):
            raise ValueError(f"{label}: prompt references changed")
        field["value"] = optimized[label]


def prompt_size_estimate(text):
    """Transparent English-text heuristic, never presented as GLM token counts."""
    return {"characters": len(text), "utf8_bytes": len(text.encode("utf-8")),
            "rough_tokens_chars_div_4": math.ceil(len(text) / 4),
            "rough_tokens_chars_div_5_to_3": [math.ceil(len(text) / 5), math.ceil(len(text) / 3)]}


def prompt_optimization_metadata(template, workflow):
    original = original_prompt_values(template)
    optimized = {"state_extraction": node_input(workflow, EXTRACTOR_ID, "description")["value"],
                 "recommendation": node_input(workflow, RECOMMENDATION_ID, "systemPrompt")["value"]}
    return {
        "scope": "instruction text only; all models, histories, evidence and bindings unchanged",
        "estimate_method": "ceil(characters / 4); 3-5 characters/token sensitivity range; not a GLM tokenizer or full request count",
        "source_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in (STATE_EXTRACTION_PROMPT, RECOMMENDATION_PROMPT)},
        "original": {name: prompt_size_estimate(text) for name, text in original.items()},
        "optimized": {name: prompt_size_estimate(text) for name, text in optimized.items()},
    }


def node_input(workflow, identifier, key):
    node = next(item for item in workflow["nodes"] if item["nodeId"] == identifier)
    return next(item for item in node["inputs"] if item["key"] == key)


def apply_extraction_reliability(workflow):
    """TEST-only input stage, native code schema, and bounded guard overlay."""
    helpers = INPUT_NORMALIZATION.read_text(encoding="utf-8")
    # Copy an already proven native code-node schema, not a new platform schema.
    query = next(item for item in workflow["nodes"] if item["nodeId"] == QUERY_BUILDER_ID)
    normalizer = deepcopy(query)
    normalizer.update(nodeId=NORMALIZER_ID, name="TEST RMB Input Normalization",
                      position={"x": 1000, "y": -800})
    normalizer["inputs"] = [item for item in normalizer["inputs"]
                            if item["key"] in ("system_addInputParam", "codeType", "code", "user_question")]
    next(item for item in normalizer["inputs"] if item["key"] == "code")["value"] = (
        helpers + "\nfunction main({ user_question }) { return normalizeRmbInput(user_question); }\n")
    output_template = next(item for item in query["outputs"] if item["id"] == QUERY_OUTPUT_ID)
    normalizer["outputs"] = [deepcopy(item) for item in query["outputs"]
                             if item["id"] in ("system_rawResponse", "error", "system_addOutputParam")]
    for key, identifier in (("normalized_question", "v21NormalizedQuestion"), ("currency_status", "v21CurrencyStatus")):
        output = deepcopy(output_template)
        output.update(id=identifier, key=key, label=key, valueType="string")
        normalizer["outputs"].append(output)
    if any(item["nodeId"] == NORMALIZER_ID for item in workflow["nodes"]):
        raise ValueError("TEST normalization node already exists; review the structural baseline")
    workflow["nodes"].append(normalizer)
    incoming = [edge for edge in workflow["edges"] if edge["source"] == "448745" and edge["target"] == EXTRACTOR_ID]
    if len(incoming) != 1:
        raise ValueError("Expected the working Current start-to-extraction connection")
    edge = incoming[0]
    index = workflow["edges"].index(edge)
    workflow["edges"][index:index + 1] = [
        {**edge, "target": NORMALIZER_ID, "targetHandle": NORMALIZER_ID + "-target-left"},
        {**edge, "source": NORMALIZER_ID, "sourceHandle": NORMALIZER_ID + "-source-right"},
    ]
    node_input(workflow, EXTRACTOR_ID, "content")["value"] = [NORMALIZER_ID, "v21NormalizedQuestion"]
    node_input(workflow, EXTRACTOR_ID, "description")["value"] += EXTRACTION_RULES.read_text(encoding="utf-8")
    code = node_input(workflow, GUARD_ID, "code")["value"]
    marker = "  // --------------------------------------------------\n  // 3. Deterministically detect common follow-up intent"
    code = replace_once(code, marker, SCOPE_CONSISTENCY.read_text(encoding="utf-8") + "\n" + marker)
    budgets = '''  // Normalize budgets without accepting foreign amounts, booleans or NaN.
  product_requests = product_requests.map(request => request && typeof request === "object"
    ? { ...request, budget: normalizeRmbBudget(request.budget) } : request);
  if (normalizedScope === "supported" && purchaseEvidence && !awaitingTarget && !comparison_cancelled) {
    product_requests = product_requests.map(request => {
      const literal = purchaseEvidence.find(item => categoryKey(item.category) === categoryKey(request?.category));
      return literal?.budget !== null && literal?.budget !== undefined
        ? { ...request, budget: literal.budget } : request;
    });
  }
  // Never convert foreign/mixed/invalid money or reuse old RMB for it.
  if (normalizedScope === "supported" && currentInput.currency_status !== "rmb_or_unspecified") {
    product_requests = product_requests.map(request => request && typeof request === "object"
      && (!targetCategory || categoryKey(request.category) === targetCategory)
      ? { ...request, budget: null } : request);
  }

'''
    code = replace_once(code, "  const target_requests =", budgets + "  const target_requests =")
    old = '''        request == null ||
        request.budget === null ||
        request.budget === undefined ||
        String(request.budget).trim() === ""'''
    code = replace_once(code, old, "        request == null || normalizeRmbBudget(request.budget) === null")
    node_input(workflow, GUARD_ID, "code")["value"] = helpers + "\n" + code


def test_settings():
    settings = load_dataset(TEST_SETTINGS)
    if settings.get("retrieval_similarity") != 0.35:
        raise ValueError("Reviewed TEST retrieval similarity must remain 0.35")
    if settings.get("clarification_reasoning") is not False:
        raise ValueError("TEST clarification reasoning must remain disabled")
    for field in ("clarification_max_tokens", "recommendation_max_tokens"):
        if type(settings.get(field)) is not int or not 256 <= settings[field] <= 8192:
            raise ValueError(f"Invalid TEST setting: {field}")
    if type(settings.get("browser_request_timeout_ms")) is not int or not 5000 <= settings["browser_request_timeout_ms"] <= 300000:
        raise ValueError("Invalid TEST browser timeout")
    return settings


def apply_test_settings(workflow):
    settings = test_settings()
    changes = ((RETRIEVAL_ID, "similarity", settings["retrieval_similarity"]),
               ("ikIzMK483vihRths", "aiChatReasoning", settings["clarification_reasoning"]),
               ("ikIzMK483vihRths", "maxToken", settings["clarification_max_tokens"]),
               ("pskHz4kajjJnBWwG", "maxToken", settings["recommendation_max_tokens"]))
    for identifier, key, value in changes:
        node = next(item for item in workflow["nodes"] if item["nodeId"] == identifier)
        field = next(item for item in node["inputs"] if item["key"] == key)
        field["value"] = value


def harden_validation_code(code):
    """Apply a reviewed TEST-only overlay without editing the stable workflow."""
    policy_marker = "  const USAGE_COMPATIBILITY = "
    if code.count(policy_marker) != 1:
        raise ValueError("Workflow usage policy changed; review the TEST overlay")
    policy_start = code.index(policy_marker) + len(policy_marker)
    original_policy, policy_length = json.JSONDecoder().raw_decode(code[policy_start:])
    policy = load_dataset(USAGE_COMPATIBILITY)
    if (not isinstance(policy, dict) or set(policy) != set(original_policy)
            or any(not isinstance(terms, list) or not terms
                   or any(not isinstance(term, str) or not term.strip() for term in terms)
                   for terms in policy.values())):
        raise ValueError("TEST usage policy requires the supported groups and non-empty term lists")
    code = code[:policy_start] + script_json(policy) + code[policy_start + policy_length:]
    start_marker = "    // Apply the existing response-layer usage vocabulary to comparisons."
    end_marker = "    // 7. Hard-budget validation"
    if code.count(start_marker) != 1 or code.count(end_marker) != 1:
        raise ValueError("Workflow usage guard changed; review the TEST overlay")
    start, end = code.index(start_marker), code.index(end_marker)
    guard = (
        "    // Check every recommendation, including initial turns, against Master Dataset usage tags.\n"
        "    const usageCheck = checkCatalogueUsage(approvedProduct, request.main_usage, PRODUCT_CATALOG, USAGE_COMPATIBILITY);\n"
        "    if (!usageCheck.valid) return invalidResult(\"Usage validation violation: \" + usageCheck.error);\n\n"
    )
    code = code[:start] + guard + code[end:]
    code = replace_once(code, "  // Empty public recommendations do not erase historical comparison anchors.",
                        "  if (!validation_ok) return invalidResult(validation_error);\n\n"
                        "  // Empty public recommendations do not erase historical comparison anchors.")
    failure_start = code.index("  function invalidResult(message) {")
    if not code.endswith("\n  }\n}"):
        raise ValueError("Workflow failure handler changed; review the TEST overlay")
    code = code[:failure_start] + VALIDATION_FAILURE.read_text(encoding="utf-8") + "}"
    code = replace_once(code, "  let answer =", "  if (!data || typeof data !== \"object\" || Array.isArray(data)) return invalidResult(\"Invalid response object.\");\n\n  let answer =")
    code = replace_once(code, "    const approvedProduct = PRODUCT_CATALOG[productName];",
                        "    const approvedProduct = Object.prototype.hasOwnProperty.call(PRODUCT_CATALOG, productName)\n"
                        "      ? PRODUCT_CATALOG[productName] : null;")
    code = replace_once(code, "    const approvedAnchor = PRODUCT_CATALOG[comparisonAnchor?.recommended_product];",
                        "    const approvedAnchor = Object.prototype.hasOwnProperty.call(PRODUCT_CATALOG, comparisonAnchor?.recommended_product)\n"
                        "      ? PRODUCT_CATALOG[comparisonAnchor.recommended_product] : null;")
    return USAGE_VALIDATOR.read_text(encoding="utf-8") + "\n" + code


def json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def script_json(value):
    """JSON safe inside HTML script data and JavaScript literals."""
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), allow_nan=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def catalogue_projection(dataset):
    # Keep the public recommendation contract unchanged; carry all audit fields
    # in each validation entry so no consumer loses identity or review evidence.
    return {p["product"]: {**deepcopy(p), "price": p["price_rmb"]} for p in dataset["products"]}


def validation_code(workflow):
    nodes = [n for n in workflow["nodes"] if n["nodeId"] == VALIDATOR_ID]
    if len(nodes) != 1:
        raise ValueError("Expected exactly one recommendation validation node")
    fields = [i for i in nodes[0]["inputs"] if i["key"] == "code"]
    if len(fields) != 1:
        raise ValueError("Expected exactly one validation code input")
    return fields[0]


def check_workflow_inputs(workflow):
    """Check exported required inputs/references, without claiming runtime import compatibility.

    Portable model/dataset selections and the runtime start input are intentional
    exceptions. They still need account configuration or FastGPT runtime data.
    Native condition/update references and prompt interpolation are checked too.
    """
    errors = []
    nodes = {node["nodeId"]: node for node in workflow["nodes"]}
    if len(nodes) != len(workflow["nodes"]):
        errors.append("workflow: duplicate node IDs")
    variables = {item["key"]: item for item in workflow["chatConfig"]["variables"]}
    if len(variables) != len(workflow["chatConfig"]["variables"]):
        errors.append("workflow: duplicate global variable keys")

    def reference_type(value, path):
        source, identifier = value
        if source == "VARIABLE_NODE_ID":
            output = variables.get(identifier)
        else:
            output = next((item for item in nodes.get(source, {}).get("outputs", [])
                           if item["id"] == identifier), None)
            # Working Current binds optional file inputs to this FastGPT runtime
            # output even though the exported start node lists only userChatInput.
            if output is None and nodes.get(source, {}).get("flowNodeType") == "workflowStart" and identifier == "userFiles":
                return "arrayString"
        if output is None:
            errors.append(f"{path}: unresolved reference {source}.{identifier}")
            return None
        return output.get("valueType")

    def nested_references(value, path, required_reference=False):
        if isinstance(value, list):
            pair = len(value) == 2 and all(isinstance(item, str) for item in value)
            if pair and (required_reference or value[0] in nodes or value[0] == "VARIABLE_NODE_ID"):
                reference_type(value, path)
            else:
                for index, item in enumerate(value):
                    nested_references(item, f"{path}[{index}]", required_reference)
        elif isinstance(value, dict):
            for key, item in value.items():
                nested_references(item, f"{path}.{key}", key == "variable" or (key == "value" and value.get("renderType") == "reference"))
        elif isinstance(value, str):
            for source, identifier in re.findall(r"\{\{\$([^.$]+)\.([^$]+)\$\}\}", value):
                reference_type([source, identifier], path)

    for node in workflow["nodes"]:
        inputs = node.get("inputs", [])
        if len({item["key"] for item in inputs}) != len(inputs):
            errors.append(f"{node['nodeId']}: duplicate input keys")
        outputs = node.get("outputs", [])
        if len({item["id"] for item in outputs}) != len(outputs):
            errors.append(f"{node['nodeId']}: duplicate output IDs")
        for field in inputs:
            key, value = field["key"], field.get("value")
            path = f"{node['nodeId']}.{key}"
            runtime_input = node["flowNodeType"] == "workflowStart" and key == "userChatInput"
            render_types = field.get("renderTypeList", [])
            manual_binding = ((key == "datasets" and (field.get("selectedType") == "selectDataset" or "selectDataset" in render_types))
                              or (key in ("model", "modelId") and (
                                  field.get("selectedType") in ("selectLLMModel", "settingLLMModel")
                                  or any(kind in render_types for kind in ("selectLLMModel", "settingLLMModel")))))
            missing = value is None or value == "" or value == []
            if field.get("required") and missing and not (runtime_input or manual_binding):
                errors.append(f"{path}: required input is unbound")
            native_reference = field.get("selectedType") == "reference" or (
                "selectedType" not in field and "reference" in render_types and isinstance(value, list) and key != "datasets")
            if native_reference and not missing:
                references = [value] if (isinstance(value, list) and len(value) == 2
                                         and all(isinstance(part, str) for part in value)) else value
                if not isinstance(references, list) or not references:
                    errors.append(f"{path}: invalid reference value")
                    continue
                for reference in references:
                    if not (isinstance(reference, list) and len(reference) == 2
                            and all(isinstance(part, str) for part in reference)):
                        errors.append(f"{path}: invalid reference pair")
                        continue
                    actual_type = reference_type(reference, path)
                    expected_type = field.get("valueType")
                    allowed = {expected_type, "any"}
                    if isinstance(expected_type, str) and expected_type.startswith("array"):
                        allowed.add(expected_type[5:].lower())
                    if actual_type and expected_type != "any" and actual_type not in allowed:
                        errors.append(f"{path}: reference type {actual_type} does not match {expected_type}")
            if key != "code":
                nested_references(value, path)
    for edge in workflow["edges"]:
        if edge["source"] not in nodes or edge["target"] not in nodes:
            errors.append("workflow: unresolved edge endpoint")
        if not edge["sourceHandle"].startswith(edge["source"] + "-source-") or edge["targetHandle"] != edge["target"] + "-target-left":
            errors.append("workflow: edge handle does not match endpoint")
    return errors


def assert_workflow_contract(template, generated):
    """Allow only the reviewed validator, settings and extraction reliability overlays."""
    errors = check_workflow_inputs(template) + check_workflow_inputs(generated)
    if errors:
        raise ValueError("\n".join(errors))
    restored = deepcopy(generated)
    validation_code(restored)["value"] = validation_code(template)["value"]
    expected = deepcopy(template)
    apply_test_settings(expected)
    apply_extraction_reliability(expected)
    apply_prompt_optimization(expected)
    if restored != expected:
        raise ValueError("Workflow contract changed outside reviewed TEST overlays; preserve the working Current structure, bindings and schemas")


def catalogue_span(code):
    if code.count(CATALOG_MARKER) != 1:
        raise ValueError("Workflow PRODUCT_CATALOG marker changed; review the template")
    start = code.index(CATALOG_MARKER) + len(CATALOG_MARKER)
    value, length = json.JSONDecoder().raw_decode(code[start:])
    if not isinstance(value, dict) or code[start + length:start + length + 1] != ";":
        raise ValueError("Workflow PRODUCT_CATALOG must remain a plain JSON object")
    return start, start + length


def assert_portable(workflow):
    """Fail closed on bound templates instead of leaking account bindings."""
    def check_ids(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "_id" or key.replace("_", "").lower() in ("teamid", "tmbid", "userid", "ownerid", "appid", "apikey", "accesstoken", "secret", "password"):
                    if item:
                        raise ValueError("Portable workflow must not contain private account metadata or credentials")
                if key.replace("_", "").lower() in ("datasetid", "collectionid") and item not in ("", "REPLACE_AFTER_IMPORT", None):
                    raise ValueError("Portable workflow must not contain concrete knowledge-base IDs")
                if key.replace("_", "").lower() in ("datasetids", "collectionids") and item:
                    raise ValueError("Portable workflow must not contain concrete knowledge-base ID lists")
                check_ids(item)
        elif isinstance(value, list):
            for item in value:
                check_ids(item)

    check_ids(workflow)
    for node in workflow["nodes"]:
        for field in node.get("inputs", []):
            if field["key"] == "datasets":
                if field.get("value") != []:
                    raise ValueError("Portable workflow must have datasets: []")
                description = json.loads(field.get("valueDesc", "[]"))
                if description != [{"datasetId": "REPLACE_AFTER_IMPORT"}]:
                    raise ValueError("Portable workflow must use the dataset placeholder")
            if field["key"] in ("model", "modelId", "rerankModel", "rerankModelId", "datasetSearchExtensionModel", "datasetSearchExtensionModelId") and field.get("value"):
                raise ValueError("Portable workflow must not contain concrete model bindings; reselect models in TEST")


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f"Frontend template changed near {old[:70]!r}; review generator")
    return text.replace(old, new, 1)


def render_frontend(dataset):
    text = FRONTEND.read_text(encoding="utf-8")
    pattern = r'(<script type="application/json" id="mytech-dataset">)([\s\S]*?)(</script>)'
    if len(re.findall(pattern, text)) != 1:
        raise ValueError("Expected one embedded frontend dataset")
    text = re.sub(pattern, lambda m: m[1] + script_json(dataset) + m[3], text)
    contract = {"dataset_name": dataset["dataset_name"], "version": dataset["version"], "count": len(dataset["products"])}
    text = replace_once(text, '    "use strict";', '    "use strict";\n    const TEST_CATALOGUE_CONTRACT = ' + script_json(contract) + ";")
    start = text.index("    function validateProductDataset(dataset) {")
    end = text.index("    async function loadApplicationData()", start)
    text = text[:start] + FRONTEND_VALIDATOR.read_text(encoding="utf-8") + "\n" + text[end:]
    text = replace_once(text, "<title>MyTech v2 — Product Recommendation Chatbot</title>", "<title>MyTech v2.1 TEST — Product Candidates</title>")
    text = replace_once(text, "Reference product data · RMB (¥) · Not live retailer pricing", "v2.1 TEST ONLY · Provisional candidates · Not approved for Current · RMB reference prices")
    text = replace_once(text, 'const KEY_STORE = "tokenproxy-key";', 'const KEY_STORE = "mytech-v21-test-key";')
    helpers = CITATION_HELPERS.read_text(encoding="utf-8").replace("export function ", "function ")
    runtime = FRONTEND_RUNTIME.read_text(encoding="utf-8")
    policy = script_json(load_dataset(USAGE_COMPATIBILITY))
    settings = test_settings()
    injection = ("\n    const TEST_USAGE_POLICY = " + policy + ";\n"
                 "    const TEST_DEFAULT_TIMEOUT_MS = " + str(settings["browser_request_timeout_ms"]) + ";\n"
                 + USAGE_VALIDATOR.read_text(encoding="utf-8") + "\n" + helpers + "\n" + runtime + "\n")
    text = replace_once(text, '    "use strict";', '    "use strict";' + injection)
    text = replace_once(text, 'const HOSTED = /^project-', 'const HOSTED = LOCAL_TEST || /^project-')
    text = text.replace('!HOSTED && !apiKey', '!testConnectionAvailable()')
    text = replace_once(text, '      if (HOSTED) return path;', '      if (LOCAL_TEST) return "/api/test/mytech";\n      if (HOSTED) return path;')
    text = replace_once(text, '      requestTimeoutMs: 60_000,', '      requestTimeoutMs: testBrowserTimeout(),')
    text = replace_once(text, '      maxTokens: 800', '      maxTokens: ' + str(settings["recommendation_max_tokens"]))
    start = text.index('    function usageIsCompatible(product, requestedUsage) {')
    end = text.index('    function validateStructuredOutput(output, guard)', start)
    text = text[:start] + ('    function usageIsCompatible(product, requestedUsage) {\n'
        '      return checkCatalogueUsage(product, requestedUsage, testUsageCatalogue, TEST_USAGE_POLICY).valid;\n    }\n\n') + text[end:]
    text = replace_once(text, 'const required = ["category", "recommended_product", "price", "reason"];',
                        'const required = ["category", "recommended_product", "price", "reason", "source"];')
    text = replace_once(text, 'if (hardBudget && product.price_rmb > hardBudget)',
                        'if (!Number.isFinite(hardBudget) || hardBudget <= 0 || product.price_rmb > hardBudget)')
    text = replace_once(text, 'if (requestedUsage && !usageIsCompatible(product, requestedUsage))',
                        'if (!requestedUsage || !usageIsCompatible(product, requestedUsage))')
    text = replace_once(text, '      const output = coerceStructuredOutput(rawResult);',
                        '      const output = coerceStructuredOutput(rawResult);\n      const display = testDisplayOutput(output);')
    text = replace_once(text, '      if (validation.valid) return output;',
                        '      if (validation.valid && validateStructuredOutput(display, guard).valid) return output;')
    text = replace_once(text, '        addStructuredResponse(response);', '        addStructuredResponse(testDisplayOutput(response));')
    text = replace_once(text, '        usageConstraints: guard.usagesByCategory',
                        '        usageConstraints: guard.usagesByCategory,\n        validationContext: guard')
    text = replace_once(text, '        body: JSON.stringify({\n          chatId: payload.chatId,',
                        '        body: JSON.stringify(LOCAL_TEST ? payload : {\n          chatId: payload.chatId,')
    text = replace_once(text, '      productByName = new Map(dataset.products.map((product) => [product.product, product]));',
                        '      productByName = new Map(dataset.products.map((product) => [product.product, product]));\n'
                        '      testUsageCatalogue = Object.fromEntries(dataset.products.map(product => [product.id, product]));')
    text = replace_once(text, '        initializeKeyPanel();', '        await configureLocalTest();\n        initializeKeyPanel();')
    text = replace_once(text, '      else if (!testConnectionAvailable()) setStatus("unavailable", "FastGPT Key Required");',
                        '      else if (!testConnectionAvailable()) setStatus("unavailable", LOCAL_TEST ? "Configure the separate TEST server connection" : "FastGPT TEST Key Required");')
    text = replace_once(text, '      const timeout = window.setTimeout(() => { timedOut = true; turnController.abort(); }, CONFIG.requestTimeoutMs);',
                        '      const startedAt = testNow();\n      let timingStatus = "rejected";\n'
                        '      const timeout = window.setTimeout(() => { timedOut = true; turnController.abort(); }, testDeadlineMs());')
    text = replace_once(text, '        updateContextAfterResponse(response);', '        updateContextAfterResponse(response);\n        timingStatus = "validated";')
    text = replace_once(text, '        window.clearTimeout(timeout);',
                        '        window.clearTimeout(timeout);\n        emitTestTiming("turn", startedAt, timedOut ? "timeout" : currentRequest !== requestVersion ? "cancelled" : timingStatus);')
    return text


def render_outputs(dataset):
    errors = validate_dataset(dataset, test_v21=True)
    if errors:
        raise ValueError("\n".join(errors))
    workflow = json.loads(WORKFLOW_TEMPLATE.read_text(encoding="utf-8-sig"))
    template = deepcopy(workflow)
    assert_portable(workflow)
    field = validation_code(workflow)
    start, end = catalogue_span(field["value"])
    field["value"] = field["value"][:start] + script_json(catalogue_projection(dataset)) + field["value"][end:]
    field["value"] = harden_validation_code(field["value"])
    apply_test_settings(workflow)
    apply_extraction_reliability(workflow)
    apply_prompt_optimization(workflow)
    assert_workflow_contract(template, workflow)
    assert_portable(workflow)
    # The complete portable working Current graph is authoritative. Only the
    # validator/settings change plus one native input stage and its bounded guard.
    # Existing downstream schemas, IDs, conditions and state bindings stay native.
    outputs = {
        KNOWLEDGE: render_knowledge(dataset),
        WORKFLOW: json_text(workflow),
        "index.html": render_frontend(dataset),
        "catalogue.json": json_text(dataset),
    }
    manifest = {
        "release_scope": "TEST ONLY — not approved for Current or production",
        "master": "catalogue/mytech_products_v2_1_test.json",
        "master_sha256": hashlib.sha256(json_text(dataset).encode("utf-8")).hexdigest(),
        "workflow_template": str(WORKFLOW_TEMPLATE.relative_to(ROOT)),
        "workflow_template_sha256": hashlib.sha256(json_text(template).encode("utf-8")).hexdigest(),
        "test_settings": test_settings(),
        "prompt_optimization": prompt_optimization_metadata(template, workflow),
        "extraction_reliability": {
            "normalizer_node_id": NORMALIZER_ID,
            "source_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                              for path in (INPUT_NORMALIZATION, SCOPE_CONSISTENCY, EXTRACTION_RULES)},
        },
        "product_count": len(dataset["products"]),
        "supported_categories": dataset["supported_categories"],
        "outputs": {name: hashlib.sha256(text.encode("utf-8")).hexdigest() for name, text in outputs.items()},
    }
    outputs["manifest.json"] = json_text(manifest)
    return {name: text.encode("utf-8") for name, text in outputs.items()}


def check_outputs(outputs, directory):
    """Byte-exact read-only check includes facts, metadata, templates and logic."""
    errors = []
    for name, expected in outputs.items():
        path = directory / name
        try:
            if path.read_bytes() != expected:
                errors.append(f"{path}: modified or stale; regenerate from Master Dataset")
        except OSError as error:
            errors.append(f"{path}: {error.strerror}")
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=TEST_DATASET)
    parser.add_argument("--output-root", type=Path, default=ROOT, help="base directory; always writes under generated/v2_1_test")
    parser.add_argument("--check", action="store_true", help="read-only check; exit nonzero on missing, modified or stale outputs")
    args = parser.parse_args(argv)
    try:
        dataset = load_dataset(args.dataset)
        outputs = render_outputs(dataset)  # Validate and render everything before writing.
        try:
            from . import build_aiep_test as aiep
        except ImportError:
            import build_aiep_test as aiep
        aiep_outputs = aiep.render_outputs(dataset)
        aiep_directory = args.output_root.resolve() / aiep.OUTPUT_SUBDIR
        directory = args.output_root.resolve() / OUTPUT_SUBDIR
        if args.check:
            errors = check_outputs(outputs, directory) + aiep.check_outputs(aiep_outputs, aiep_directory)
            if errors:
                raise ValueError("\n".join(errors))
            print(f"Consistent: {len(dataset['products'])} TEST products across all generated catalogues.")
        else:
            # Do not follow output symlinks into stable or unrelated files.
            for path in [directory, directory.parent, *(directory / name for name in outputs)]:
                if path.is_symlink():
                    raise ValueError(f"Refusing symlink output path: {path}")
            aiep.write_outputs(aiep_outputs, aiep_directory)
            directory.mkdir(parents=True, exist_ok=True)
            for name, payload in outputs.items():
                path = directory / name
                if not path.exists() or path.read_bytes() != payload:
                    path.write_bytes(payload)
            print(f"Generated {len(outputs)} TEST files for {len(dataset['products'])} products in {directory}.")
    except (OSError, UnicodeError, ValueError, RecursionError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
