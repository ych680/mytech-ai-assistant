// Both actual snapshots: execute native validators/routers without model calls.
import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { Script, createContext } from "node:vm";

const root = new URL("../", import.meta.url);
const registry = JSON.parse(await readFile(new URL("workflow/v2.1/registry.json", root)));
const graphs = await Promise.all(["original", "optimized"].map(async role =>
  JSON.parse(await readFile(new URL(registry.variants[role].snapshot, root)))));
const master = JSON.parse(await readFile(new URL(registry.catalogue.master, root)));
const item = id => master.products.find(p => p.id === id);
const rec = id => { const p = item(id); return { category: p.category, recommended_product: p.product, price: p.price_rmb,
  source: p.source, reason: "Matches the reference usage." }; };
const reply = ids => ({ answer: "Reference options.", recommendations: ids.map(rec), next_step: "Another option?", clarification_needed: false });
const field = (graph, id, key) => graph.nodes.find(n => n.nodeId === id).inputs.find(f => f.key === key).value;
function run(graph, input) {
  const result = JSON.parse(JSON.stringify(new Script(field(graph, "fakNM8mmlYmewx67", "code") + "\nmain(input);")
    .runInContext(createContext({ input: structuredClone(input) }), { timeout: 1000 })));
  const validator = graph.nodes.find(n => n.nodeId === "fakNM8mmlYmewx67");
  const resolve = reference => {
    assert.equal(reference[0], validator.nodeId);
    return result[validator.outputs.find(o => o.id === reference[1]).key];
  };
  const router = "p4ZeCJXrGirXAQCz";
  const valid = field(graph, router, "ifElseList")[0].list.every(c => String(resolve(c.variable)) === String(c.value));
  let terminal = graph.edges.find(e => e.source === router && e.sourceHandle.endsWith(valid ? "-IF" : "-ELSE")).target;
  let memory = structuredClone(input.previous_recommendations);
  if (valid) {
    const variable = graph.chatConfig.variables.find(v => v.label === "last_recommendations").key;
    for (const update of field(graph, terminal, "updateList")) if (update.variable[1] === variable) memory = update.value.map(resolve).flat();
    terminal = graph.edges.find(e => e.source === terminal).target;
  }
  const text = field(graph, terminal, "text");
  const output = JSON.parse(typeof text === "string" ? text : resolve(text));
  assert.deepEqual(Object.keys(output).sort(), ["answer", "recommendations", "next_step", "clarification_needed"].sort());
  assert.equal(typeof output.answer, "string"); assert.equal(typeof output.next_step, "string");
  assert.equal(typeof output.clarification_needed, "boolean");
  return { valid, output, memory };
}

test("registered actual versions preserve IDs, routing and deterministic code", () => {
  const [a, b] = graphs;
  assert.deepEqual(a.edges, b.edges); assert.deepEqual(a.chatConfig, b.chatConfig);
  assert.deepEqual(a.nodes.map(n => n.nodeId), b.nodes.map(n => n.nodeId));
  for (const node of a.nodes) {
    assert.deepEqual(node.outputs, b.nodes.find(n => n.nodeId === node.nodeId).outputs);
    for (const f of node.inputs) if (f.key === "code") assert.equal(f.value, field(b, node.nodeId, "code"));
  }
});

test("both actual versions accept independent multi-product budgets with four-field public output", () => {
  const input = { raw_json: JSON.stringify(reply(["LAP-001", "MOU-004"])), previous_recommendations: [], follow_up_intent: "none",
    active_requests: [{ category: "Laptop", budget: 6000, main_usage: "Study" }, { category: "Mouse", budget: 300, main_usage: "Gaming" }] };
  const results = graphs.map(graph => run(graph, input)); assert.deepEqual(results[0], results[1]);
  assert.equal(results[0].valid, true); assert.equal(results[0].output.recommendations.length, 2);
});

test("unsafe batch in either actual version uses fallback without replacing approved anchors", () => {
  const previous = [rec("LAP-001"), rec("MOU-002")];
  const input = { raw_json: JSON.stringify(reply(["LAP-001", "MOU-001"])), previous_recommendations: previous, follow_up_intent: "none",
    active_requests: [{ category: "Laptop", budget: 6000, main_usage: "Study" }, { category: "Mouse", budget: 300, main_usage: "Gaming" }] };
  const results = graphs.map(graph => run(graph, input)); assert.deepEqual(results[0], results[1]);
  assert.equal(results[0].valid, false); assert.deepEqual(results[0].output.recommendations, []); assert.deepEqual(results[0].memory, previous);
});

test("both actual snapshots retain unrelated anchor during targeted cheaper comparison", () => {
  const previous = [rec("LAP-001"), rec("MOU-002")];
  const input = { raw_json: JSON.stringify(reply(["MOU-004"])), previous_recommendations: previous, follow_up_intent: "cheaper",
    active_requests: [{ category: "Mouse", budget: 500, main_usage: "Gaming" }] };
  const results = graphs.map(graph => run(graph, input)); assert.deepEqual(results[0], results[1]);
  assert.equal(results[0].valid, true); assert.deepEqual(results[0].memory, [rec("LAP-001"), rec("MOU-004")]);
});
