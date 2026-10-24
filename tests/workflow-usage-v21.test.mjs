// Execute the generated FastGPT TEST code and its actual memory/public bindings.
// No model, server, credentials or network calls are involved.
import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { Script, createContext } from "node:vm";
import { createTestAdapter } from "../mytech_v2_1_test_adapter.mjs";

const graph = JSON.parse(await readFile(new URL("../generated/v2_1_test/mytech-fastgpt-workflow-v2_1-TEST.json", import.meta.url), "utf8"));
const master = JSON.parse(await readFile(new URL("../catalogue/mytech_products_v2_1_test.json", import.meta.url), "utf8"));
const node = graph.nodes.find(item => item.nodeId === "fakNM8mmlYmewx67");
const script = new Script(node.inputs.find(item => item.key === "code").value + "\nmain(input);");
const adapter = await createTestAdapter();
const product = id => master.products.find(item => item.id === id);
const rec = item => ({ category: item.category, recommended_product: item.product,
  price: item.price_rmb, source: item.source, reason: "Matches the reference usage tags." });
const response = recommendations => ({ answer: "Reference recommendations.", recommendations,
  next_step: "Would you like another option?", clarification_needed: false });
const request = (item, main_usage, budget = item.price_rmb) => ({ category: item.category, main_usage, budget });
const value = (item, usage, options = {}) => ({ raw_json: JSON.stringify(response([rec(item)])),
  active_requests: [request(item, usage)], previous_recommendations: [], follow_up_intent: "none", ...options });

function execute(input) {
  const copy = structuredClone(input), before = structuredClone(copy);
  const context = createContext({ input: copy }, { codeGeneration: { strings: false, wasm: false } });
  const result = JSON.parse(JSON.stringify(script.runInContext(context, { timeout: 1000 })));
  assert.deepEqual(context.input, before, "Validation must not mutate conversation input");
  return result;
}

function persistAndReply(input, result) {
  const variable = label => graph.chatConfig.variables.find(item => item.label === label).key;
  const state = { [variable("last_recommendations")]: structuredClone(input.previous_recommendations),
    [variable("product_requests")]: structuredClone(input.active_requests) };
  const previousRequests = structuredClone(state[variable("product_requests")]);
  function resolve(reference) {
    assert.equal(reference[0], node.nodeId);
    const output = node.outputs.find(item => item.id === reference[1]);
    assert.ok(output);
    assert.ok(Object.hasOwn(result, output.key));
    return structuredClone(result[output.key]);
  }
  const router = graph.nodes.find(item => item.nodeId === "p4ZeCJXrGirXAQCz");
  const branch = router.inputs.find(item => item.key === "ifElseList").value[0];
  const accepted = branch.list.every(condition => String(resolve(condition.variable)) === String(condition.value));
  const route = graph.edges.find(edge => edge.source === router.nodeId && edge.sourceHandle === router.nodeId + "-source-" + (accepted ? "IF" : "ELSE"));
  let terminal;
  if (accepted) {
    const writer = graph.nodes.find(item => item.nodeId === route.target);
    for (const update of writer.inputs.find(item => item.key === "updateList").value) {
      state[update.variable[1]] = update.value.map(resolve).flat(1);
    }
    terminal = graph.nodes.find(item => item.nodeId === graph.edges.find(edge => edge.source === writer.nodeId).target);
  } else {
    terminal = graph.nodes.find(item => item.nodeId === route.target);
  }
  const text = terminal.inputs.find(item => item.key === "text").value;
  const publicReply = JSON.parse(typeof text === "string" ? text : resolve(text));
  assert.deepEqual(Object.keys(publicReply).sort(), ["answer", "recommendations", "next_step", "clarification_needed"].sort());
  assert.equal(typeof publicReply.answer, "string");
  assert.equal(typeof publicReply.next_step, "string");
  assert.equal(typeof publicReply.clarification_needed, "boolean");
  assert.deepEqual(state[variable("product_requests")], previousRequests);
  return { memory: state[variable("last_recommendations")], publicReply };
}

test("initial gaming accepts a gaming Laptop and rejects a Study/Office-only Laptop", () => {
  for (const [id, valid] of [["LAP-005", true], ["LAP-001", false]]) {
    const input = value(product(id), "gaming", { active_requests: [request(product(id), "gaming", 6000)] });
    const result = execute(input);
    assert.equal(result.validation_ok, valid);
    assert.equal(adapter.validate(input).valid, valid);
    const saved = persistAndReply(input, result);
    assert.equal(saved.publicReply.recommendations.length, valid ? 1 : 0);
    assert.equal(saved.memory.length, valid ? 1 : 0);
  }
});

test("every exact Master Dataset tag passes initial and valid comparison usage checks", () => {
  for (const item of master.products) {
    const anchor = master.products.find(other => other.category === item.category && other.price_rmb !== item.price_rmb);
    for (const usage of item.main_usage) {
      for (const intent of ["none", item.price_rmb < anchor.price_rmb ? "cheaper" : "more_expensive", "alternative"]) {
        const input = value(item, usage, { previous_recommendations: [rec(anchor)], follow_up_intent: intent });
        const result = execute(input);
        assert.equal(result.validation_ok, true, `${item.id}: ${usage}, ${intent}: ${result.validation_error}`);
        assert.equal(adapter.validate(input).valid, true, `${item.id}: adapter ${usage}`);
      }
    }
  }
});

for (const [id, usage] of [
  ["MOU-004", "  I mainly need it for PLAYING VIDEO GAMES.  "],
  ["MOU-004", "play game"], ["MOU-004", "playing games"],
  ["MOU-004", "casual gaming"], ["MOU-004", "videogames"],
  ["LAP-001", "studying"], ["LAP-001", "schoolwork"], ["LAP-001", "office work"],
  ["LAP-005", "study & gaming"], ["LAP-005", "study/gaming"], ["LAP-005", "studying and playing games"],
  ["DES-003", "programming"], ["DES-003", "coding"], ["DES-003", "software development"],
  ["LAP-002", "video editing"], ["DES-006", "content creation"], ["TAB-006", "drawing"],
  ["LAP-002", "photo and video editing"],
  ["PHO-002", "taking photos"], ["TAB-002", "watching videos"],
  ["AUD-002", "noise-cancelling"], ["AUD-002", "active noise cancellation"],
  ["TAB-001", "note taking"], ["AUD-004", "voice chat"],
  ["WAT-006", "outdoor sports and hiking"], ["MOU-006", "competitive gaming"],
  ["MOU-006", "ＦＰＳ"], ["LAP-001", "I would like to use it for study, office, and daily use."]
]) test(`supported natural-language usage: ${id} / ${usage}`, () => {
  const input = value(product(id), usage);
  const result = execute(input);
  assert.equal(result.validation_ok, true, result.validation_error);
  assert.equal(adapter.validate(input).valid, true);
});

test("unknown, missing, mixed, negated and ambiguous usages fail on every recommendation intent", () => {
  const item = product("MOU-004");
  for (const usage of ["quantum simulation", "gaming and quantum simulation", "quantum gaming", "gamingish",
    "not gaming", "gaming or study", "gaming without latency", "for", "", null, 42, ["Gaming"]]) {
    for (const intent of ["none", "cheaper", "more_expensive", "alternative"]) {
      const input = value(item, usage, { active_requests: [request(item, usage, 500)],
        previous_recommendations: [rec(product("MOU-002"))], follow_up_intent: intent });
      const result = execute(input);
      assert.equal(result.validation_ok, false, `${usage}, ${intent}`);
      assert.match(result.validation_error, /usage/i);
      const saved = persistAndReply(input, result);
      assert.deepEqual(saved.memory, input.previous_recommendations);
      assert.deepEqual(saved.publicReply.recommendations, []);
      assert.equal(adapter.validate(input).valid, false);
    }
  }
});

test("matching a broad substring cannot bypass a specific requested capability", () => {
  for (const [id, usage] of [["MOU-004", "competitive gaming"], ["LAP-003", "coding"],
    ["PHO-004", "photography"], ["WAT-004", "health tracking"], ["MOU-001", "typing"]]) {
    const result = execute(value(product(id), usage));
    assert.equal(result.validation_ok, false, `${id} / ${usage}`);
    assert.match(result.validation_error, /usage/i);
  }
  // A new Travel-only product cannot become ANC-capable through a loose alias.
  const code = node.inputs.find(item => item.key === "code").value;
  const policy = JSON.parse(code.match(/const USAGE_COMPATIBILITY = (\{[^\n]+\});/)[1]);
  const context = createContext({ product: { main_usage: ["Travel"] }, catalogue: { TravelOnly: { main_usage: ["Travel"] } }, policy });
  new Script(code).runInContext(context);
  const result = new Script('checkCatalogueUsage(product, "noise cancelling", catalogue, policy);').runInContext(context);
  assert.equal(result.valid, false);
});

test("multi-product requests validate usages independently and reject the entire unsafe batch", () => {
  const laptop = product("LAP-001"), mouse = product("MOU-004");
  const previous = [rec(product("LAP-002")), rec(product("MOU-002"))];
  const input = value(laptop, "study", { raw_json: JSON.stringify(response([rec(laptop), rec(mouse)])),
    active_requests: [request(laptop, "study", 6000), request(mouse, "gaming", 300)], previous_recommendations: previous });
  const good = execute(input);
  assert.equal(good.validation_ok, true);
  assert.equal(adapter.validate(input).valid, true);
  assert.deepEqual(persistAndReply(input, good).memory, [rec(laptop), rec(mouse)]);
  for (const requests of [
    [request(laptop, "gaming", 6000), request(mouse, "study", 300)],
    [request(laptop, "study", 6000), request(mouse, "gaming and unknown task", 300)]
  ]) {
    const invalid = { ...input, active_requests: requests };
    const result = execute(invalid);
    assert.equal(result.validation_ok, false);
    assert.deepEqual(persistAndReply(invalid, result).memory, previous);
    assert.deepEqual(result.recommendations, []);
  }
});

test("cheaper and alternative follow-ups keep valid anchors and enforce usage and direction", () => {
  const mouse = product("MOU-004"), anchor = product("MOU-002");
  const previous = [rec(product("LAP-001")), rec(anchor)];
  for (const intent of ["cheaper", "alternative"]) {
    const input = value(mouse, "playing games", { active_requests: [request(mouse, "playing games", 300)],
      previous_recommendations: previous, follow_up_intent: intent });
    const good = execute(input);
    assert.equal(good.validation_ok, true);
    assert.deepEqual(persistAndReply(input, good).memory, [previous[0], rec(mouse)]);
    for (const candidate of [product("MOU-001"), anchor]) {
      const invalid = { ...input, raw_json: JSON.stringify(response([rec(candidate)])) };
      const result = execute(invalid);
      assert.equal(result.validation_ok, false);
      assert.deepEqual(persistAndReply(invalid, result).memory, previous);
    }
    const empty = { ...input, raw_json: JSON.stringify(response([])) };
    assert.deepEqual(persistAndReply(empty, execute(empty)).memory, previous);
  }
});

test("all rejection paths preserve prior memory and the four-field public contract", () => {
  const mouse = product("MOU-004"), previous = [rec(product("LAP-001")), rec(product("MOU-002"))];
  const base = value(mouse, "gaming", { previous_recommendations: previous });
  const variants = [];
  for (const change of [r => { r.recommended_product = "unknown"; }, r => { r.recommended_product = "constructor"; },
    r => { r.category = "Laptop"; }, r => { r.price += 1; }, r => { r.source = "invented"; }]) {
    const reply = response([rec(mouse)]); change(reply.recommendations[0]);
    variants.push({ ...base, raw_json: JSON.stringify(reply) });
  }
  variants.push({ ...base, active_requests: [request(mouse, "gaming", mouse.price_rmb - 1)] },
    { ...base, raw_json: JSON.stringify(response([rec(mouse), rec(mouse)])) },
    { ...base, raw_json: "not JSON" }, { ...base, raw_json: "null" },
    { ...base, raw_json: JSON.stringify(response([rec(product("MOU-001"))])) });
  for (const input of variants) {
    const result = execute(input);
    assert.equal(result.validation_ok, false);
    assert.deepEqual(result.recommendations, []);
    const saved = persistAndReply(input, result);
    assert.deepEqual(saved.memory, previous);
    assert.deepEqual(saved.publicReply.recommendations, []);
    assert.equal(saved.publicReply.clarification_needed, false, "Working Current fallback branch is preserved");
  }
});
