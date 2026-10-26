// Native validator/final branches, Node adapter and both complete frontends.
// Providers, extraction and retrieval evidence are deterministic offline data.
import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { Script, createContext } from "node:vm";
import { createTestAdapter } from "../mytech_v2_1_test_adapter.mjs";
import { createTestServer, testServerConfig } from "../mytech_v2_1_test_server.mjs";
import { repairFrontend } from "./helpers/v21-repair-frontend.mjs";

const root = new URL("../", import.meta.url);
const directory = new URL("generated/v21_completion_fix/local/", root);
const graph = JSON.parse(await readFile(new URL("mytech-fastgpt-workflow-v2_1-TEST.json", directory), "utf8"));
const master = JSON.parse(await readFile(new URL("catalogue.json", directory), "utf8"));
const adapter = await createTestAdapter(fileURLToPath(directory));
const field = (id, key) => graph.nodes.find(n => n.nodeId === id).inputs.find(f => f.key === key).value;
const validator = graph.nodes.find(n => n.nodeId === "fakNM8mmlYmewx67");
const script = new Script(field(validator.nodeId, "code") + "\nmain(input);");
const product = id => master.products.find(p => p.id === id);
const rec = id => { const p = product(id); return { category: p.category, recommended_product: p.product, price: p.price_rmb, source: p.source, reason: "Matches the reference usage and hard budget." }; };
const response = (ids = [], answer = "Reference recommendation.") => ({ answer, recommendations: ids.map(rec), next_step: "Would you like to change your requirements?", clarification_needed: false });
const laptop = { category: "Laptop", budget: 6000, main_usage: "Gaming" };
const mouse = { category: "Mouse", budget: 300, main_usage: "Gaming" };
const headphones = { category: "Headphones", budget: 800, main_usage: "music and commuting, noise cancellation" };
const demoMessage = "I need a laptop under ¥6,000 for gaming.";
const demo = { answer: "Got it! You're looking for a gaming laptop under ¥6,000. I now have all the information I need.", recommendations: [], next_step: "Provide gaming laptop recommendations under ¥6,000", clarification_needed: false };
const input = (output, requests = [laptop], previous = [rec("MOU-002")], intent = "none", evidence) => ({ raw_json: JSON.stringify(output), active_requests: structuredClone(requests), previous_recommendations: structuredClone(previous), follow_up_intent: intent, ...(evidence === undefined ? {} : { retrieved_evidence: evidence }) });
function execute(value) {
  const context = createContext({ input: structuredClone(value) }, { codeGeneration: { strings: false, wasm: false } });
  const result = JSON.parse(JSON.stringify(script.runInContext(context, { timeout: 1000 })));
  assert.deepEqual(context.input, value);
  return result;
}
function finalize(value, result) {
  const resolve = ref => { assert.equal(ref[0], validator.nodeId); return result[validator.outputs.find(f => f.id === ref[1]).key]; };
  const router = "p4ZeCJXrGirXAQCz";
  const accepted = field(router, "ifElseList")[0].list.every(c => String(resolve(c.variable)) === String(c.value));
  let terminal = graph.edges.find(e => e.source === router && e.sourceHandle.endsWith(accepted ? "-IF" : "-ELSE")).target;
  let memory = structuredClone(value.previous_recommendations);
  if (accepted) {
    for (const update of field(terminal, "updateList")) memory = update.value.map(resolve).flat();
    terminal = graph.edges.find(e => e.source === terminal).target;
  }
  const text = field(terminal, "text"), output = JSON.parse(typeof text === "string" ? text : resolve(text));
  assert.deepEqual(Object.keys(output).sort(), ["answer", "recommendations", "next_step", "clarification_needed"].sort());
  return { accepted, output, memory, terminal };
}
// Execute the complete candidate graph and actual ID bindings. Only extraction,
// retrieval and AI outputs are fixtures; no provider or FastGPT runtime is used.
function nativeTurn(message, options = {}) {
  const nodes = new Map(graph.nodes.map(n => [n.nodeId, n]));
  const state = structuredClone({ product_requests: [], last_recommendations: [], follow_up_intent: "none", missing_fields: [], clarification_needed: false, ...options.state });
  const keys = Object.fromEntries(graph.chatConfig.variables.map(v => [v.label, v.key]));
  const globals = new Map(Object.entries(state).map(([key, value]) => [keys[key], value]));
  const values = new Map(), trace = [], queries = [];
  const reference = pair => {
    const source = pair[0] === "VARIABLE_NODE_ID" ? globals : values.get(pair[0]);
    assert.ok(source?.has(pair[1]), `Unresolved candidate reference: ${pair.join(".")}`);
    return structuredClone(source.get(pair[1]));
  };
  const resolve = value => {
    if (Array.isArray(value)) return value.length === 2 && value.every(x => typeof x === "string") ? reference(value) : value.map(resolve);
    return typeof value === "string" ? value.replace(/\{\{\$([^.$]+)\.([^$]+)\$\}\}/g, (_, id, key) => JSON.stringify(reference([id, key]))) : value;
  };
  let current = "448745", output, validation, validatorInput;
  while (current) {
    assert.ok(trace.length < 40);
    const node = nodes.get(current); trace.push(current);
    let result = {}, handle = current + "-source-right";
    if (node.flowNodeType === "workflowStart") result = { userChatInput: message, userFiles: [] };
    else if (node.flowNodeType === "contentExtract") {
      resolve(field(current, "content"));
      result = { product_requests_json: JSON.stringify(options.requests || []), missing_fields_json: "[]", clarification_needed: "false", follow_up_intent: options.intent || "none", scope_status: options.scope || "supported" };
    } else if (node.flowNodeType === "code") {
      const input = Object.fromEntries(node.inputs.filter(f => !["code", "codeType", "system_addInputParam"].includes(f.key)).map(f => [f.key, resolve(f.value)]));
      const context = createContext({ input: structuredClone(input) }, { codeGeneration: { strings: false, wasm: false } });
      result = JSON.parse(JSON.stringify(new Script(field(current, "code") + "\nmain(input);").runInContext(context, { timeout: 1000 })));
      assert.deepEqual(context.input, input);
      if (current === validator.nodeId) { validatorInput = input; validation = result; }
    } else if (node.flowNodeType === "variableUpdate") {
      for (const update of field(current, "updateList")) {
        const value = resolve(update.value);
        globals.set(update.variable[1], update.valueType.startsWith("array") ? value.flat(1) : value);
      }
    } else if (node.flowNodeType === "ifElseNode") {
      const index = field(current, "ifElseList").findIndex(branch => branch.list.every(c => String(reference(c.variable)) === String(c.value)));
      handle = current + "-source-" + (index < 0 ? "ELSE" : index === 0 ? "IF" : "ELSE IF " + index);
    } else if (node.flowNodeType === "datasetSearchNode") {
      queries.push(resolve(field(current, "userChatInput")));
      result = { quoteQA: options.evidence ?? [] };
    } else if (node.flowNodeType === "chatNode") {
      resolve(field(current, "systemPrompt"));
      if (current === "ikIzMK483vihRths") {
        output = { ...response([], "Please clarify your request."), clarification_needed: true };
        if (reference(["tWP2LwPvzFadPPtk", "school1bCancelled"])) output = response([], "The comparison is cancelled.");
        result = { answerText: JSON.stringify(output) };
      } else {
        assert.deepEqual(resolve(field(current, "quoteQA")), options.evidence ?? []);
        result = { answerText: JSON.stringify(options.output || demo) };
      }
    } else if (node.flowNodeType === "answerNode") output = JSON.parse(resolve(field(current, "text")));
    else assert.fail("Unexpected candidate node: " + node.flowNodeType);
    const outputs = new Map(node.outputs.filter(f => Object.hasOwn(result, f.key)).map(f => [f.id, result[f.key]]));
    if (current === "448745") outputs.set("userFiles", []);
    values.set(current, outputs);
    current = graph.edges.find(e => e.source === current && e.sourceHandle === handle)?.target;
  }
  for (const [label, key] of Object.entries(keys)) state[label] = structuredClone(globals.get(key));
  assert.deepEqual(Object.keys(output).sort(), ["answer", "recommendations", "next_step", "clarification_needed"].sort());
  return { output, state, trace, queries, validation, validatorInput };
}
async function across(output, requests, message, valid, previous = []) {
  const value = input(output, requests, previous), result = execute(value), final = finalize(value, result);
  assert.equal(result.validation_ok, valid, result.validation_error);
  assert.equal(adapter.validate(value).valid, valid);
  assert.equal(final.accepted, valid);
  if (!valid) {
    assert.deepEqual(final.memory, previous);
    assert.deepEqual(result.recommendations_to_store, previous);
    assert.deepEqual(final.output.recommendations, []);
    assert.doesNotMatch(final.output.answer + final.output.next_step, /adjust your budget|restate.*budget|no.*catalogue.*match/i);
  }
  for (const kind of ["local", "aiep"]) {
    const app = await repairFrontend(kind, "v21_completion_fix");
    const guard = app.guard(message);
    assert.equal(app.validate(output, guard).valid, valid, kind);
    assert.equal(adapter.validateCompletionTurn(output, guard, previous, message).valid, valid);
    const before = app.state().sessionContext.lastRecommendationsByCategory;
    await app.submit(message, output);
    assert.equal(app.cards(), valid ? output.recommendations.length : 0);
    if (!valid) assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, before);
  }
  return result;
}

test("exact school-demo acknowledgement cannot complete a satisfiable request", async () => {
  await across(demo, [laptop], demoMessage, false, [rec("MOU-002")]);
});
test("rejected school-demo output cannot replace already rendered browser anchors", async () => {
  for (const kind of ["local", "aiep"]) {
    const app = await repairFrontend(kind, "v21_completion_fix");
    await app.submit("I need a laptop under RMB 6000 and a mouse under RMB 300 for gaming.", response(["LAP-005", "MOU-002"]));
    assert.equal(app.cards(), 2);
    const anchors = app.state().sessionContext.lastRecommendationsByCategory;
    await app.submit(demoMessage, demo);
    assert.equal(app.cards(), 2);
    assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, anchors);
    assert.match(app.text(), /couldn't safely validate/i);
  }
});
for (const amount of ["RMB 6000", "RMB 6,000", "¥6000", "¥6,000"]) test(`LAP-005 at 4999 passes under ${amount}`, async () => {
  await across(response(["LAP-005"]), [laptop], `I need a laptop under ${amount} for gaming.`, true);
});
test("false catalogue no-match cannot hide LAP-005 eligibility", async () => {
  await across(response([], "No Laptop in the catalogue matches Gaming within RMB 6000."), [laptop], demoMessage, false);
});
test("genuine Headphones 800 Music + Commuting + ANC no-match passes all layers", async () => {
  const r = await across(response([], "No Headphones in the catalogue match all requirements within RMB 800."), [headphones], "I need headphones under RMB 800 for music and commuting, noise cancellation.", true);
  assert.equal(r.completion_status, "verified_catalogue_no_match");
});
test("acknowledgement and deferral fail even when no catalogue item qualifies", async () => {
  const message = "I need headphones under RMB 800 for music and commuting, noise cancellation.";
  for (const output of [response([], "I have your requirements."), { ...response([], "No Headphones match these requirements."), next_step: "Provide Headphones recommendations next." }]) {
    await across(output, [headphones], message, false);
  }
});
test("all-empty multi-product result cannot hide eligible requests", async () => {
  await across(response([], "No Laptop matches. No Mouse matches."), [laptop, mouse], "I need a laptop under RMB 6000 and a mouse under RMB 300 for gaming.", false);
});
test("all-empty multi-product genuine no-match explains every category", async () => {
  const requests = [{ ...laptop, budget: 100 }, { ...mouse, budget: 50 }];
  await across(response([], "No Laptop matches within RMB 100. No Mouse matches within RMB 50."), requests, "I need a laptop under RMB 100 and a mouse under RMB 50 for gaming.", true);
  await across(response([], "No Laptop matches within RMB 100."), requests, "I need a laptop under RMB 100 and a mouse under RMB 50 for gaming.", false);
});
test("partial result preserves verified Headphones no-match and rejects silent/false omissions", async () => {
  const message = "I need a laptop under RMB 6000 for gaming and headphones under RMB 800 for music and commuting, noise cancellation.";
  await across(response(["LAP-005"], "The Laptop matches. No Headphones match all requirements within RMB 800."), [laptop, headphones], message, true);
  await across(response(["LAP-005"]), [laptop, headphones], message, false);
  await across(response(["LAP-005"], "No Mouse matches."), [laptop, mouse], "I need a laptop under RMB 6000 and a mouse under RMB 300 for gaming.", false);
});
for (const [label, evidence, status] of [
  ["unavailable", undefined, "incomplete_or_evidence_uncertain"], ["empty", [], "retrieval_evidence_empty"],
  ["irrelevant", [product("LAP-001")], "retrieval_evidence_unverified"],
  ["truncated", [{ a: "Product: " + product("LAP-005").product }], "retrieval_evidence_unverified"],
  ["eligible full record", [product("LAP-005")], "incomplete_model_execution"]
]) test(`${label} retrieval evidence is diagnosed without synthesizing products`, () => {
  const value = input(demo, [laptop], [rec("MOU-002")], "none", evidence), r = execute(value);
  assert.equal(r.validation_ok, false); assert.equal(r.completion_status, status);
  assert.deepEqual(r.recommendations, []); assert.deepEqual(r.recommendations_to_store, value.previous_recommendations);
  assert.equal(adapter.validate(value).result.completion_status, status);
});
test("complete RAG Markdown record diagnoses omission, split/mismatched facts do not", async () => {
  const knowledge = await readFile(new URL("MyTech_Product_Knowledge_v2_1_TEST.md", directory), "utf8");
  const record = knowledge.split("\n---\n").find(text => text.includes("Product ID: LAP-005\n"));
  assert.equal(execute(input(demo, [laptop], [], "none", [{ a: record }])).completion_status, "incomplete_model_execution");
  const pieces = record.split("Source:");
  assert.equal(execute(input(demo, [laptop], [], "none", pieces.map(a => ({ a })))).completion_status, "retrieval_evidence_unverified");
  assert.equal(execute(input(demo, [laptop], [], "none", [{ a: record.replace("RMB 4999", "RMB 1") }])).completion_status, "retrieval_evidence_unverified");
  assert.equal(execute(input(demo, [laptop], [], "none", [{ a: record.replace("  - Gaming\n", "") }])).completion_status, "retrieval_evidence_unverified");
  assert.equal(execute(input(demo, [laptop], [], "none", [{ a: record + "\nCategory: Mouse" }])).completion_status, "retrieval_evidence_unverified");
});
test("empty retrieval cannot trigger a fabricated product fallback", async () => {
  const output = response(["LAP-005"]);
  output.recommendations[0].recommended_product = "Invented Gaming Laptop";
  const value = input(output, [laptop], [rec("MOU-002")], "none", []);
  const r = execute(value);
  assert.equal(r.validation_ok, false); assert.equal(adapter.validate(value).valid, false);
  assert.deepEqual(finalize(value, r).memory, value.previous_recommendations);
  for (const kind of ["local", "aiep"]) {
    const app = await repairFrontend(kind, "v21_completion_fix");
    assert.equal(app.validate(output, app.guard(demoMessage)).valid, false);
  }
});
for (const [intent, id, budget] of [["cheaper", "LAP-005", 6000], ["more_expensive", "LAP-005", 6000], ["alternative", "LAP-005", 6000]]) {
  test(`legitimate ${intent} no-result is evaluated relative to LAP-005 and preserves all anchors`, async () => {
    const previous = [rec("MOU-002"), rec(id)], label = intent.replace("_", " ");
    const output = response([], `No ${label} Laptop matches Gaming within RMB ${budget}.`);
    const value = input(output, [{ ...laptop, budget }], previous, intent), result = execute(value), final = finalize(value, result);
    assert.equal(result.validation_ok, true, result.validation_error);
    assert.equal(adapter.validate(value).valid, true); assert.deepEqual(final.memory, previous);
    for (const kind of ["local", "aiep"]) {
      const app = await repairFrontend(kind, "v21_completion_fix");
      await app.submit(demoMessage, response([id]));
      const guard = app.guard(`${label} Laptop.`);
      assert.equal(app.validate(output, guard).valid, true);
      assert.equal(adapter.validateCompletionTurn(output, guard, previous, `${label} Laptop.`).valid, true);
      const before = app.state().sessionContext.lastRecommendationsByCategory;
      await app.submit(`${label} Laptop.`, output);
      assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, before);
    }
  });
}
for (const [intent, anchor, budget] of [["cheaper", "MOU-002", 300], ["more_expensive", "MOU-004", 300], ["alternative", "MOU-002", 300]]) {
  test(`false ${intent} no-result fails when a qualifying Mouse exists`, async () => {
    const output = response([], `No ${intent.replace("_", " ")} Mouse matches.`), previous = [rec(anchor)];
    const value = input(output, [{ ...mouse, budget }], previous, intent), r = execute(value);
    assert.equal(r.validation_ok, false); assert.equal(adapter.validate(value).valid, false);
    assert.deepEqual(finalize(value, r).memory, previous);
    for (const kind of ["local", "aiep"]) {
      const app = await repairFrontend(kind, "v21_completion_fix");
      await app.submit("I need a mouse under RMB 300 for gaming.", response([anchor]));
      const message = `${intent.replace("_", " ")} Mouse.`, guard = app.guard(message);
      assert.equal(app.validate(output, guard).valid, false);
      assert.equal(adapter.validateCompletionTurn(output, guard, previous, message).valid, false);
    }
  });
}
test("comparison cannot reuse forged, absent, ambiguous or cross-category anchors", () => {
  for (const previous of [[], [rec("MOU-002")], [rec("LAP-005"), rec("LAP-005")], [{ ...rec("LAP-005"), price: 1 }]]) {
    const value = input(response([], "No cheaper Laptop matches."), [laptop], previous, "cheaper");
    assert.equal(execute(value).validation_ok, false); assert.deepEqual(finalize(value, execute(value)).memory, previous);
  }
});
test("invalid returned items reject the entire batch and preserve old anchors", async () => {
  const unsafe = response(["LAP-005", "AUD-001"], "No Headphones match all requirements.");
  await across(unsafe, [laptop, headphones], "I need a laptop under RMB 6000 for gaming and headphones under RMB 800 for music and commuting, noise cancellation.", false, [rec("MOU-002")]);
});
test("clarification, cancellation, help, unsupported and Restart survive historical complete requests", async () => {
  for (const kind of ["local", "aiep"]) {
    const app = await repairFrontend(kind, "v21_completion_fix");
    await app.submit(demoMessage, response(["LAP-005"]));
    for (const message of ["Hello", "Hello MyTech", "Hi, what can you do?", "What can you help me with?", "Which product categories can you recommend?", "Tell me a joke.", "What's the weather?", "Help me with my homework.", "I need a camera under RMB 6000.", "I need printers under RMB 6000.", "Cancel that comparison."]) {
      const output = response([], "Please tell me your next request."), guard = app.guard(message);
      assert.equal(app.validate(output, guard).valid, true, message);
      assert.equal(adapter.validateCompletionTurn(output, guard, [rec("LAP-005")], message).valid, true);
    }
    app.restart();
    assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, {});
    assert.deepEqual(app.state().modelHistory, []);
    const output = { ...response([], "What is your maximum budget in RMB?"), clarification_needed: true };
    assert.equal(app.validate(output, app.guard("I need a laptop for gaming.")).valid, true);
  }
});
test("a greeting combined with a purchase still requires completion", async () => {
  for (const kind of ["local", "aiep"]) {
    const app = await repairFrontend(kind, "v21_completion_fix");
    const message = "Hi, I need a laptop under RMB 6000 for gaming.", guard = app.guard(message);
    assert.equal(app.validate(demo, guard).valid, false);
    assert.equal(adapter.validateCompletionTurn(demo, guard, [], message).valid, false);
  }
});
test("local candidate server rejects empty completion and can recover without losing its anchors", async t => {
  let output = response(["LAP-005"]);
  const config = testServerConfig({ MYTECH_TEST_PORT: "0", MYTECH_TEST_FASTGPT_API_KEY: ["offline", "fixture"].join("-"), MYTECH_TEST_FASTGPT_API_URL: "https://example.invalid/chat/completions", MYTECH_TEST_FASTGPT_BINDING: "app-key" });
  const server = await createTestServer(config, { directory: fileURLToPath(directory), fetchImpl: async () => new Response(JSON.stringify({ choices: [{ message: { content: JSON.stringify(output) } }] })) });
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  t.after(() => new Promise(resolve => server.close(resolve)));
  const app = await repairFrontend("local", "v21_completion_fix"), guard = app.guard(demoMessage);
  const post = (message, validationContext) => fetch(`http://127.0.0.1:${server.address().port}/api/test/mytech`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message, validationContext, chatId: "offline-completion-session" }) });
  assert.equal((await post(demoMessage, guard)).status, 200);
  output = demo; assert.equal((await post(demoMessage, guard)).status, 502);
  output = response([], "No cheaper Laptop matches Gaming within RMB 6000.");
  assert.equal((await post("cheaper Laptop.", { ...guard, comparison: "cheaper" })).status, 200);
  output = response([], "Hello! Tell me what you need.");
  assert.equal((await post("Hello", guard)).status, 200);
  output = response(["LAP-005"]); assert.equal((await post(demoMessage, guard)).status, 200);
  const headphonesMessage = "I need headphones under RMB 800 for music and commuting, noise cancellation.";
  output = response([], "No Headphones match within RMB 1200.");
  const normalizedResponse = await post(headphonesMessage, app.guard(headphonesMessage));
  assert.equal(normalizedResponse.status, 200);
  const normalized = JSON.parse((await normalizedResponse.json()).choices[0].message.content);
  assert.match(normalized.answer, /Headphones.*commuting.*noise cancellation.*RMB 800/);
  assert.doesNotMatch(normalized.answer, /1200/);
  assert.deepEqual(Object.keys(normalized).sort(), ["answer", "recommendations", "next_step", "clarification_needed"].sort());
});

for (const [intent, wording, message] of [
  ["cheaper", "lower-priced", "A lower-priced Laptop."], ["cheaper", "lower priced", "A lower-priced Laptop."],
  ["cheaper", "less expensive", "A less expensive Laptop."], ["cheaper", "more affordable", "A more affordable Laptop."],
  ["more_expensive", "higher-priced", "A higher-priced Laptop."], ["more_expensive", "higher priced", "A higher-priced Laptop."],
  ["alternative", "other", "Another Laptop."], ["alternative", "different", "A different Laptop."], ["alternative", "another", "Another Laptop."]
]) test(`Phase 3B comparison no-match accepts ${wording} using actual ${intent} constraints`, async () => {
  const previous = [rec("MOU-002"), rec("LAP-005")], output = response([], `No ${wording} Laptop matches Gaming within RMB 6000.`);
  const value = input(output, [laptop], previous, intent), result = execute(value), final = finalize(value, result);
  assert.equal(result.validation_ok, true, result.validation_error);
  assert.equal(adapter.validate(value).valid, true); assert.deepEqual(final.memory, previous);
  assert.match(final.output.answer, new RegExp(`No ${intent.replace("_", " ")} Laptop product`));
  assert.match(final.output.answer, /MECHREVO.*Gaming.*RMB 6000/);
  const turn = nativeTurn(message, { requests: [laptop], intent, output, state: { product_requests: [laptop], last_recommendations: previous } });
  assert.equal(turn.validation.validation_ok, true); assert.deepEqual(turn.state.last_recommendations, previous);
  assert.ok(turn.trace.includes("b0vXntQUXZL2Mk5m"));
  for (const kind of ["local", "aiep"]) {
    const app = await repairFrontend(kind, "v21_completion_fix");
    await app.submit(demoMessage, response(["LAP-005"]));
    const guard = app.guard(message), before = app.state().sessionContext.lastRecommendationsByCategory;
    assert.equal(app.validate(output, guard).valid, true);
    assert.equal(adapter.validateCompletionTurn(output, guard, previous, message).valid, true);
    await app.submit(message, output);
    assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, before);
    assert.match(JSON.parse(app.state().modelHistory.at(-1).content).answer, new RegExp(`No ${intent.replace("_", " ")} Laptop product`));
  }
});
for (const [intent, anchor, wording] of [["cheaper", "MOU-002", "lower-priced"], ["more_expensive", "MOU-004", "higher-priced"], ["alternative", "MOU-002", "other"]]) {
  test(`Phase 3B ${wording} cannot hide an eligible Mouse`, async () => {
    const previous = [rec(anchor)], output = response([], `No ${wording} Mouse matches.`);
    const value = input(output, [mouse], previous, intent), result = execute(value);
    assert.equal(result.validation_ok, false); assert.deepEqual(finalize(value, result).memory, previous);
    const turn = nativeTurn(`${wording === "other" ? "Another" : wording} Mouse.`, { requests: [mouse], intent, output, state: { product_requests: [mouse], last_recommendations: previous } });
    assert.equal(turn.validation.validation_ok, false); assert.deepEqual(turn.state.last_recommendations, previous);
    for (const kind of ["local", "aiep"]) {
      const app = await repairFrontend(kind, "v21_completion_fix"); await app.submit("I need a mouse under RMB 300 for gaming.", response([anchor]));
      const message = `${wording === "other" ? "Another" : wording} Mouse.`;
      assert.equal(app.validate(output, app.guard(message)).valid, false);
      await app.submit(message, output); assert.equal(app.state().sessionContext.lastRecommendationsByCategory.Mouse.price, rec(anchor).price);
    }
  });
}
for (const [label, requests, ids] of [["fresh", [], []], ["Laptop history", [laptop], ["LAP-005"]], ["multi-product history", [laptop, mouse], ["LAP-005", "MOU-002"]]]) {
  test(`Phase 3B native help survives ${label} without clearing anchors`, async () => {
    const previous = ids.map(rec);
    for (const message of ["What products can you recommend?", "What products do you support?", "What can MyTech recommend?", "Which categories can you recommend?", "Can you help me?", "Hi, what products can you recommend?"]) {
      const turn = nativeTurn(message, { scope: "help", state: { product_requests: requests, last_recommendations: previous } });
      assert.ok(turn.trace.includes("d6kCXfQ1mcJ5hT8J")); assert.equal(turn.validation, undefined);
      assert.deepEqual(turn.state.last_recommendations, previous);
      for (const kind of ["local", "aiep"]) {
        const app = await repairFrontend(kind, "v21_completion_fix");
        if (ids.length) await app.submit(ids.length === 1 ? demoMessage : "I need a laptop under RMB 6000 and a mouse under RMB 300 for gaming.", response(ids));
        const before = app.state().sessionContext.lastRecommendationsByCategory, guard = app.guard(message);
        assert.equal(app.validate(turn.output, guard).valid, true, message);
        assert.equal(adapter.validateCompletionTurn(turn.output, guard, previous, message).valid, true);
        await app.submit(message, turn.output);
        assert.ok(app.text().includes(turn.output.answer)); assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, before);
        assert.equal(app.cards(), ids.length);
      }
    }
  });
}
for (const message of [
  "What products can you recommend? I need a laptop under RMB 6000 for gaming.",
  "What products can you recommend under RMB 6000?", "What products can you recommend for gaming?",
  "Can you help me choose a laptop under RMB 6000 for gaming?", "Hi, what products can you recommend, and I need a laptop under RMB 6000 for gaming."
]) test(`Phase 3B capability grammar cannot bypass purchase completion: ${message}`, async () => {
  for (const kind of ["local", "aiep"]) {
    const app = await repairFrontend(kind, "v21_completion_fix"); await app.submit(demoMessage, response(["LAP-005"]));
    const guard = app.guard(message); assert.equal(guard.completionControl, false);
    assert.equal(app.validate(demo, guard).valid, false);
    assert.equal(adapter.validateCompletionTurn(demo, guard, [rec("LAP-005")], message).valid, false);
    await app.submit(message, demo); assert.equal(app.cards(), 1);
  }
});
for (const [label, answer] of [
  ["wrong budget", "No Headphones match all requirements within RMB 1200."],
  ["wrong usage", "No Headphones match Gaming within RMB 800."],
  ["additional availability claim", "No Headphones match within RMB 800. Headphones are available now."]
]) test(`Phase 3B ${label} is replaced by independently verified current-request wording`, async () => {
  const output = response([], answer), value = input(output, [headphones], [rec("LAP-005")]);
  const r = execute(value), final = finalize(value, r);
  assert.equal(r.validation_ok, true); assert.deepEqual(final.memory, value.previous_recommendations);
  assert.match(final.output.answer, /Headphones.*music and commuting, noise cancellation.*RMB 800/);
  assert.doesNotMatch(final.output.answer, /1200|Gaming|available now/);
  assert.equal(adapter.validate(value).result.normalized_json, r.normalized_json);
  assert.equal(execute({ ...value, raw_json: r.normalized_json }).normalized_json, r.normalized_json, "canonical no-match must be idempotent");
  const message = "I need headphones under RMB 800 for music and commuting, noise cancellation.";
  const turn = nativeTurn(message, { requests: [headphones], output });
  assert.equal(turn.output.answer, final.output.answer);
  for (const kind of ["local", "aiep"]) {
    const app = await repairFrontend(kind, "v21_completion_fix"), guard = app.guard(message);
    assert.equal(app.validate(output, guard).valid, true);
    await app.submit(message, output);
    const accepted = JSON.parse(app.state().modelHistory.at(-1).content);
    assert.match(accepted.answer, /Headphones.*music and commuting, noise cancellation.*RMB 800/);
    assert.doesNotMatch(accepted.answer, /1200|Gaming|available now/); assert.equal(app.cards(), 0);
  }
});
for (const [label, output, requests, message] of [
  ["cross-category availability", response([], "No Laptop matches, and Mouse is available."), [{ ...laptop, budget: 100 }, { ...mouse, budget: 50 }], "I need a laptop under RMB 100 and a mouse under RMB 50 for gaming."],
  ["negated no-match", response([], "It is not true that no Headphones match within RMB 800."), [headphones], "I need headphones under RMB 800 for music and commuting, noise cancellation."],
  ["deferred next_step", { ...response([], "No Headphones match within RMB 800."), next_step: "I will recommend Headphones next." }, [headphones], "I need headphones under RMB 800 for music and commuting, noise cancellation."],
  ["wrong category", response([], "No Mouse matches within RMB 800."), [headphones], "I need headphones under RMB 800 for music and commuting, noise cancellation."]
]) test(`Phase 3B rejects ${label} through every completion layer`, async () => {
  await across(output, requests, message, false, [rec("LAP-005")]);
  const turn = nativeTurn(message, { requests, output, state: { last_recommendations: [rec("LAP-005")] } });
  assert.equal(turn.validation.validation_ok, false); assert.deepEqual(turn.state.last_recommendations, [rec("LAP-005")]);
  assert.ok(turn.trace.includes("zh9L8VeY9vKm3WnU"));
});
test("Phase 3B canonical partial responses retain exact valid items and all omitted categories", async () => {
  const output = response(["LAP-005"], "The Laptop matches. No Headphones match within RMB 1200."), value = input(output, [laptop, headphones]);
  const r = execute(value); assert.equal(r.validation_ok, true);
  assert.deepEqual(r.recommendations, output.recommendations); assert.match(r.answer, /Headphones.*RMB 800/); assert.doesNotMatch(r.answer, /1200/);
  const message = "I need a laptop under RMB 6000 for gaming and headphones under RMB 800 for music and commuting, noise cancellation.";
  const turn = nativeTurn(message, { requests: [laptop, headphones], output }); assert.deepEqual(turn.output.recommendations, output.recommendations);
  for (const kind of ["local", "aiep"]) {
    const app = await repairFrontend(kind, "v21_completion_fix"); await app.submit(message, output);
    assert.equal(app.cards(), 1); const accepted = JSON.parse(app.state().modelHistory.at(-1).content);
    assert.deepEqual(accepted.recommendations, output.recommendations); assert.doesNotMatch(accepted.answer, /1200/);
  }
});
for (const [label, evidence, expected] of [
  ["unavailable", undefined, "completed_grounding_unverified"], ["explicitly empty", [], "completed_grounding_unverified"],
  ["null", null, "completed_grounding_unverified"], ["unknown shape", [{ opaque: "offline diagnostic fixture" }], "completed_grounding_unverified"],
  ["recognizable full record", [product("LAP-005")], "completed_with_recognized_evidence"]
]) test(`Phase 3B ${label} evidence does not masquerade as grounding proof`, () => {
  const value = input(response(["LAP-005"]), [laptop], [], "none", evidence), r = execute(value);
  assert.equal(r.validation_ok, true); assert.equal(r.completion_status, expected);
  assert.deepEqual(r.recommendations, [rec("LAP-005")]); assert.equal(adapter.validate(value).result.completion_status, expected);
});
test("Phase 3B complete native graph forwards the same quoteQA to AI and validator without synthesizing evidence", () => {
  const failed = nativeTurn(demoMessage, { requests: [laptop], output: demo, evidence: [] });
  assert.equal(failed.validation.validation_ok, false); assert.equal(failed.validation.completion_status, "retrieval_evidence_empty");
  assert.deepEqual(failed.validatorInput.retrieved_evidence, []); assert.deepEqual(failed.output.recommendations, []);
  assert.deepEqual(failed.queries, ["Laptop for Gaming within RMB 6000"]);
  const evidence = [product("LAP-005")];
  const recognized = nativeTurn(demoMessage, { requests: [laptop], output: response(["LAP-005"]), evidence });
  assert.deepEqual(recognized.validatorInput.retrieved_evidence, evidence);
  assert.equal(recognized.validation.completion_status, "completed_with_recognized_evidence");
  assert.deepEqual(recognized.state.last_recommendations, [rec("LAP-005")]);
});
