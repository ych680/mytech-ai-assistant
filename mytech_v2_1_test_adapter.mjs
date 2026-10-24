// Offline TEST adapter. No server, environment reads, credentials or transport.
// The stable mytech_v2_server.mjs deliberately does not import this module.
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { Script, createContext } from "node:vm";
import { validateOutput } from "./mytech_response.mjs";

const DEFAULT_DIRECTORY = fileURLToPath(new URL("./generated/v2_1_test/", import.meta.url));
const WORKFLOW_FILE = "mytech-fastgpt-workflow-v2_1-TEST.json";

export async function createTestAdapter(directory = DEFAULT_DIRECTORY) {
  const [catalogue, workflow] = await Promise.all([
    readFile(resolve(directory, "catalogue.json"), "utf8").then(JSON.parse),
    readFile(resolve(directory, WORKFLOW_FILE), "utf8").then(JSON.parse)
  ]);
  if (catalogue.version !== "2.1-TEST") throw new Error("TEST_CATALOGUE_REQUIRED");
  const code = workflow.nodes.find(node => node.nodeId === "fakNM8mmlYmewx67")
    .inputs.find(field => field.key === "code").value;
  const script = new Script(code + "\nmain(input);");
  const productByName = new Map(catalogue.products.map(product => [product.product, product]));
  if (productByName.size !== catalogue.products.length) throw new Error("DUPLICATE_PRODUCT_NAME");
  const context = { productByName, supportedCategories: catalogue.supported_categories };

  function validate(input) {
    // Reject malformed contracts before the legacy workflow's normalization.
    const errors = [];
    let output;
    try { output = JSON.parse(input.raw_json); }
    catch { return { valid: false, errors: ["Invalid JSON response."] }; }
    const requests = input.active_requests;
    if (!Array.isArray(requests)) return { valid: false, errors: ["Active requests must be an array."] };
    const budgets = {}, seen = new Set();
    for (const request of requests) {
      if (!request || !catalogue.supported_categories.includes(request.category)
        || !Number.isFinite(request.budget) || request.budget <= 0
        || typeof request.main_usage !== "string" || !request.main_usage.trim()
        || seen.has(request.category)) {
        errors.push("Each active request needs a unique supported category, positive hard budget and usage.");
        continue;
      }
      seen.add(request.category);
      budgets[request.category] = request.budget;
    }
    errors.push(...validateOutput(output, budgets, {}, context));
    for (const recommendation of Array.isArray(output?.recommendations) ? output.recommendations : []) {
      const product = productByName.get(recommendation?.recommended_product);
      if (product && recommendation.source !== product.source) errors.push("Exact catalogue source is required.");
    }
    // The generated workflow owns usage validation for initial and follow-up
    // turns alike. Do not maintain a second, potentially divergent usage policy.
    if (errors.length) return { valid: false, errors: [...new Set(errors)] };
    const vmContext = createContext({ input: structuredClone(input) }, { codeGeneration: { strings: false, wasm: false } });
    const result = JSON.parse(JSON.stringify(script.runInContext(vmContext, { timeout: 1000 })));
    return { valid: result.validation_ok, errors: result.validation_ok ? [] : [result.validation_error], result };
  }

  return { catalogue: structuredClone(catalogue), validate };
}
