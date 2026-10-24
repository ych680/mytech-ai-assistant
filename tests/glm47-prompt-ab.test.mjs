// Actual exported source and GLM import candidates; no model/network execution.
import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { Script, createContext } from "node:vm";

const root = new URL("../", import.meta.url);
const [source, a, b] = await Promise.all([
  "tools/templates/v21_working_actual_export_sanitized.json", "generated/glm47_prompt_ab/A-glm47-original.json",
  "generated/glm47_prompt_ab/B-glm47-short.json"
].map(async name => JSON.parse(await readFile(new URL(name, root), "utf8"))));
const field = (graph, id, key) => graph.nodes.find(n => n.nodeId === id).inputs.find(i => i.key === key).value;
const master = JSON.parse(await readFile(new URL("catalogue/mytech_products_v2_1_test.json", root)));
const rec = id => { const p = master.products.find(p => p.id === id); return { category: p.category, recommended_product: p.product,
  price: p.price_rmb, source: p.source, reason: "Reference usage match." }; };
const output = recommendations => ({ answer: "Reference options.", recommendations, next_step: "Another option?", clarification_needed: false });
const validate = (graph, input) => JSON.parse(JSON.stringify(new Script(field(graph, "fakNM8mmlYmewx67", "code") + "\nmain(input);")
  .runInContext(createContext({ input: structuredClone(input) }), { timeout: 1000 })));

test("both target nodes use actual-export GLM selector; clarification remains unchanged", () => {
  for (const graph of [a, b]) {
    for (const id of ["etNrwEXVwr5sySpK", "pskHz4kajjJnBWwG"]) assert.equal(field(graph, id, "model"), "glm-4.7");
    assert.equal(field(graph, "ikIzMK483vihRths", "model"), field(source, "ikIzMK483vihRths", "model"));
  }
});

test("currency normalization and validation for independent budgets match actual exported code", () => {
  const input = { raw_json: JSON.stringify(output([rec("LAP-001"), rec("MOU-004")])),
    active_requests: [{ category: "Laptop", budget: 6000, main_usage: "Study" }, { category: "Mouse", budget: 300, main_usage: "Gaming" }],
    previous_recommendations: [], follow_up_intent: "none" };
  const results = [source, a, b].map(graph => validate(graph, input));
  assert.deepEqual(results[1], results[0]); assert.deepEqual(results[2], results[0]); assert.equal(results[0].validation_ok, true);
  for (const graph of [source, a, b]) {
    const code = field(graph, "v21RmbInputNormalize", "code");
    const result = new Script(code + '\nmain({ user_question: "I need a laptop under ¥6,000 for gaming." });').runInContext(createContext({}));
    assert.match(result.normalized_question, /RMB 6000/);
  }
});

for (const fault of ["budget", "usage", "source", "price"]) test(`GLM A/B retains actual validation and anchor protection for ${fault} failure`, () => {
  const recommendations = [rec("MOU-004")], previous = [rec("LAP-001"), rec("MOU-002")];
  const input = { active_requests: [{ category: "Mouse", budget: 300, main_usage: "Gaming" }], previous_recommendations: previous, follow_up_intent: "none" };
  if (fault === "budget") input.active_requests[0].budget = 50;
  if (fault === "usage") recommendations[0] = rec("MOU-001");
  if (fault === "source") recommendations[0].source = "Wrong source";
  if (fault === "price") recommendations[0].price++;
  input.raw_json = JSON.stringify(output(recommendations));
  const results = [source, a, b].map(graph => validate(graph, input));
  assert.deepEqual(results[1], results[0]); assert.deepEqual(results[2], results[0]);
  assert.equal(results[0].validation_ok, false); assert.deepEqual(results[0].recommendations, []);
  assert.deepEqual(results[0].recommendations_to_store, previous);
});
