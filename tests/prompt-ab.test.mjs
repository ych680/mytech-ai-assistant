// DEFERRED reconstructed offline fixtures: exercise native validation behavior.
// These are not the authoritative source or GLM-4.7 import candidates.
import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { Script, createContext } from "node:vm";

const base = new URL("../generated/prompt_ab_test/", import.meta.url);
const graphs = await Promise.all(["mytech-v21-prompt-A-control.json", "mytech-v21-prompt-B-short.json"]
  .map(async name => JSON.parse(await readFile(new URL(name, base), "utf8"))));
const master = JSON.parse(await readFile(new URL("../catalogue/mytech_products_v2_1_test.json", import.meta.url)));
const product = id => master.products.find(p => p.id === id);
const recommendation = id => { const p = product(id); return { category: p.category, recommended_product: p.product,
  price: p.price_rmb, source: p.source, reason: "Matches the reference usage." }; };
const response = ids => ({ answer: "Reference options.", recommendations: ids.map(recommendation), next_step: "Another option?", clarification_needed: false });
const request = (id, usage, budget) => ({ category: product(id).category, main_usage: usage, budget });
const field = (graph, id, key) => graph.nodes.find(n => n.nodeId === id).inputs.find(i => i.key === key).value;

function validate(graph, input) {
  const context = createContext({ input: structuredClone(input) });
  const result = new Script(field(graph, "fakNM8mmlYmewx67", "code") + "\nmain(input);").runInContext(context, { timeout: 1000 });
  return JSON.parse(JSON.stringify(result));
}

function publicRoute(graph, result, previous) {
  const validator = graph.nodes.find(node => node.nodeId === "fakNM8mmlYmewx67");
  const resolve = reference => {
    assert.equal(reference[0], validator.nodeId);
    const output = validator.outputs.find(item => item.id === reference[1]);
    return result[output.key];
  };
  const router = "p4ZeCJXrGirXAQCz";
  const accepted = field(graph, router, "ifElseList")[0].list.every(c => String(resolve(c.variable)) === String(c.value));
  const next = graph.edges.find(e => e.source === router && e.sourceHandle === router + "-source-" + (accepted ? "IF" : "ELSE")).target;
  let memory = structuredClone(previous), terminal = next;
  if (accepted) {
    const lastRecommendations = graph.chatConfig.variables.find(v => v.label === "last_recommendations").key;
    for (const update of field(graph, next, "updateList")) {
      if (update.variable[1] === lastRecommendations) memory = update.value.map(resolve).flat();
    }
    terminal = graph.edges.find(e => e.source === next).target;
  }
  const text = field(graph, terminal, "text");
  const output = JSON.parse(typeof text === "string" ? text : resolve(text));
  assert.deepEqual(Object.keys(output).sort(), ["answer", "recommendations", "next_step", "clarification_needed"].sort());
  assert.equal(typeof output.answer, "string"); assert.equal(typeof output.next_step, "string");
  assert.equal(typeof output.clarification_needed, "boolean");
  return { accepted, memory, output };
}

test("both packaged variants preserve a valid multi-product response and exact four-field contract", () => {
  const input = { raw_json: JSON.stringify(response(["LAP-001", "MOU-004"])),
    active_requests: [request("LAP-001", "Study", 6000), request("MOU-004", "Gaming", 300)],
    previous_recommendations: [], follow_up_intent: "none" };
  const results = graphs.map(graph => publicRoute(graph, validate(graph, input), []));
  assert.deepEqual(results[0], results[1]);
  assert.equal(results[0].accepted, true); assert.equal(results[0].output.recommendations.length, 2);
});

for (const fault of ["price", "source", "category", "budget", "usage", "malformed", "duplicate"]) {
  test(`both A/B validators route ${fault} failure to safe fallback without replacing memory`, () => {
    const output = response(["MOU-004"]), previous = [recommendation("LAP-001"), recommendation("MOU-002")];
    const input = { active_requests: [request("MOU-004", "Gaming", 300)], previous_recommendations: previous, follow_up_intent: "none" };
    if (fault === "price") output.recommendations[0].price++;
    if (fault === "source") output.recommendations[0].source = "Invented source";
    if (fault === "category") output.recommendations[0].category = "Laptop";
    if (fault === "budget") input.active_requests[0].budget = 50;
    if (fault === "usage") output.recommendations = [recommendation("MOU-001")];
    if (fault === "duplicate") output.recommendations.push(recommendation("MOU-002"));
    input.raw_json = fault === "malformed" ? "not JSON" : JSON.stringify(output);
    const results = graphs.map(graph => publicRoute(graph, validate(graph, input), previous));
    assert.deepEqual(results[0], results[1]);
    assert.equal(results[0].accepted, false); assert.deepEqual(results[0].output.recommendations, []);
    assert.deepEqual(results[0].memory, previous);
  });
}

test("both variants retain other-category anchors during targeted cheaper follow-up", () => {
  const previous = [recommendation("LAP-001"), recommendation("MOU-002")];
  const input = { raw_json: JSON.stringify(response(["MOU-004"])), active_requests: [request("MOU-004", "Gaming", 500)],
    previous_recommendations: previous, follow_up_intent: "cheaper" };
  const results = graphs.map(graph => publicRoute(graph, validate(graph, input), previous));
  assert.deepEqual(results[0], results[1]); assert.equal(results[0].accepted, true);
  assert.deepEqual(results[0].memory, [recommendation("LAP-001"), recommendation("MOU-004")]);
});
