import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createContext, Script } from "node:vm";

const graph = JSON.parse((await readFile(new URL("../workflow/mytech-fastgpt-workflow.json", import.meta.url), "utf8")).replace(/^\uFEFF/, ""));
const dataset = JSON.parse(await readFile(new URL("../mytech_v1_product_dataset.json", import.meta.url), "utf8"));
const nodes = new Map(graph.nodes.map((node) => [node.nodeId, node]));
const ids = {
  start: "448745", extract: "o92mVeWzf02489Q2", guard: "pcta8CyBWPIfyJ15",
  scope: "y641hB3ildC7AsuP", saveRequests: "tVqEyTvHnHG9GG1D",
  clarifyRouter: "eFBvwYEwOHscUxgq", clarify: "aLzbBILzQ9D2UP7s",
  query: "evMBfmr3j2paOLIN", retrieve: "tagxGUFuwllhR19r",
  recommend: "iNTsE0ZHUg0tFRoW", validate: "qJnK807UNriMndON",
  saveRecommendations: "kwf3AIYyYZnAujyW", final: "g0XnV4TXVNeoEYPT"
};
const variableKeys = Object.fromEntries(graph.chatConfig.variables.map((item) => [item.label, item.key]));
const field = (id, key) => nodes.get(id).inputs.find((item) => item.key === key);
const output = (id, key) => nodes.get(id).outputs.find((item) => item.key === key);
const laptop = { category: "Laptop", budget: 6000, main_usage: "studying" };
const mouse = { category: "Mouse", budget: 300, main_usage: "gaming" };
function recommendation(name, reason = "Suitable for the stated usage.") {
  const product = dataset.products.find((item) => item.product === name);
  assert.ok(product, name);
  return { category: product.category, recommended_product: name, price: product.price_rmb, reason, source: product.source };
}
const laptopRec = recommendation("Lenovo Xiaoxin 14 (2025, Ryzen 7 H255, 16GB/512GB)");
const mouseRec = recommendation("Logitech G304 LIGHTSPEED");
const officeRec = recommendation("Logitech M240");
const premiumMouseRec = recommendation("Logitech MX Master 3S");
const publicResponse = (recommendations = [], answer = "No matching product.") => ({
  answer, recommendations, next_step: "Would you like to adjust your requirements?", clarification_needed: false
});
function execute(id, input) {
  const executedInput = structuredClone(input);
  const before = structuredClone(executedInput);
  const context = createContext({ input: executedInput }, { codeGeneration: { strings: false, wasm: false } });
  const result = new Script(`${field(id, "code").value}\nmain(input);`).runInContext(context, { timeout: 1000 });
  assert.deepEqual(context.input, before, `${id} mutated input`);
  return JSON.parse(JSON.stringify(result));
}
function initialState(requests = [laptop, mouse], recommendations = [laptopRec, mouseRec]) {
  return { product_requests: structuredClone(requests), last_recommendations: structuredClone(recommendations),
    follow_up_intent: "none", missing_fields: [], clarification_needed: false };
}

// Execute actual exported code, routing handles and reference bindings. LLM and
// retrieval nodes are explicit offline fixtures; this is not a FastGPT runtime.
function turn(question, options = {}) {
  const state = structuredClone(options.state || initialState());
  const globals = new Map(Object.entries(state).map(([key, value]) => [variableKeys[key], value]));
  const values = new Map();
  const trace = [];
  const prompts = {};
  const retrievalInputs = [];
  let response;
  function reference(pair) {
    const source = pair[0] === "VARIABLE_NODE_ID" ? globals : values.get(pair[0]);
    assert.ok(source?.has(pair[1]), `Unresolved reference ${pair.join(".")}`);
    return structuredClone(source.get(pair[1]));
  }
  function resolve(value) {
    if (Array.isArray(value)) {
      if (value.length === 2 && value.every((part) => typeof part === "string")) return reference(value);
      return value.map(resolve);
    }
    if (typeof value === "string") return value.replace(/\{\{\$([^.$]+)\.([^$]+)\$\}\}/g,
      (_, id, key) => JSON.stringify(reference([id, key])));
    return value;
  }
  let current = ids.start;
  while (current) {
    assert.ok(trace.length < 30, "Workflow cycle");
    trace.push(current);
    const node = nodes.get(current);
    let result = {};
    let handle = `${current}-source-right`;
    if (node.flowNodeType === "workflowStart") result = { userChatInput: question };
    else if (node.flowNodeType === "contentExtract") result = {
      product_requests_json: "[]", missing_fields_json: "[]", clarification_needed: "false",
      follow_up_intent: "none", scope_status: "supported", ...options.extraction
    };
    else if (node.flowNodeType === "code") result = execute(current, Object.fromEntries(node.inputs
      .filter((item) => !["code", "codeType", "system_addInputParam"].includes(item.key))
      .map((item) => [item.key, resolve(item.value)])));
    else if (node.flowNodeType === "variableUpdate") {
      for (const update of field(current, "updateList").value) {
        const value = resolve(update.value);
        globals.set(update.variable[1], update.valueType.startsWith("array") ? value.flat(1) : value);
      }
    } else if (node.flowNodeType === "ifElseNode") {
      const branch = field(current, "ifElseList").value.find((candidate) => candidate.list.every((condition) => {
        assert.equal(condition.condition, "equalTo");
        // Exported input-mode conditions store boolean literals as strings.
        return String(reference(condition.variable)) === String(condition.value);
      }));
      handle = `${current}-source-${branch?.branchId || "ELSE"}`;
    } else if (node.flowNodeType === "datasetSearchNode") {
      retrievalInputs.push(resolve(field(current, "datasetSearchInput").value));
      result = { quoteQA: [] };
    } else if (node.flowNodeType === "chatNode") {
      prompts[current] = resolve(field(current, "systemPrompt").value);
      if (current === ids.clarify) {
        assert.match(prompts[current], /follow_up_target/);
        // Response fixtures exercise delivery/contract only. They do not prove
        // the model follows the prompt; route and state assertions are separate.
        const fixture = { answer: "Would you like a cheaper Laptop or Mouse?", recommendations: [],
          next_step: "Tell me which category you mean.", clarification_needed: true };
        response = options.clarification || fixture;
        result = { answerText: JSON.stringify(response) };
      } else result = { answerText: JSON.stringify(options.modelResponse || publicResponse()) };
    } else if (node.flowNodeType === "answerNode") response = JSON.parse(resolve(field(current, "text").value));
    else assert.fail(`Unhandled node ${current}`);
    values.set(current, new Map(node.outputs.filter((item) => Object.hasOwn(result, item.key))
      .map((item) => [item.id, result[item.key]])));
    current = graph.edges.find((edge) => edge.source === current && edge.sourceHandle === handle)?.target;
  }
  for (const [label, key] of Object.entries(variableKeys)) state[label] = structuredClone(globals.get(key));
  return { state, trace, response, prompts, retrievalInputs,
    value: (id, key) => values.get(id)?.get(output(id, key)?.id) };
}
function assertPublic(response) {
  assert.deepEqual(Object.keys(response).sort(), ["answer", "recommendations", "next_step", "clarification_needed"].sort());
  assert.equal(typeof response.answer, "string");
  assert.equal(typeof response.next_step, "string");
  assert.equal(typeof response.clarification_needed, "boolean");
  assert.ok(Array.isArray(response.recommendations));
}
function assertTarget(result, request, anchor) {
  assert.deepEqual(result.state.product_requests, [laptop, mouse]);
  assert.deepEqual(result.value(ids.guard, "target_requests"), [request]);
  assert.equal(result.value(ids.guard, "follow_up_intent"), "cheaper");
  assert.equal(result.value(ids.guard, "scope_status"), "supported");
  assert.equal(result.retrievalInputs.length, 1);
  const queries = result.retrievalInputs[0].flat();
  assert.equal(queries.length, 1);
  assert.match(queries[0], new RegExp(`Active category: ${request.category}`));
  assert.match(queries[0], new RegExp(`Previous price: RMB ${anchor.price}`));
  assert.deepEqual(result.value(ids.query, "comparison_history"), [anchor]);
  assert.equal(result.trace.at(-1), ids.final);
  assertPublic(result.response);
}

test("T07 targets Mouse, ignores altered extraction and retains both saved requests and anchors", () => {
  const result = turn("Can you recommend a cheaper mouse?", {
    extraction: { scope_status: "help", product_requests_json: JSON.stringify([{ category: "Mouse", budget: 9000, main_usage: "office" }]) },
    modelResponse: publicResponse([], "No matching Laptop.")
  });
  assertTarget(result, mouse, mouseRec);
  assert.deepEqual(result.response.recommendations, []);
  assert.match(result.response.answer, /Mouse/);
  assert.doesNotMatch(result.response.answer, /Laptop/);
  assert.deepEqual(result.state.last_recommendations, [laptopRec, mouseRec]);
  assert.ok(result.prompts[ids.recommend].includes('"category":"Mouse"'));
  assert.ok(!result.prompts[ids.recommend].includes(laptopRec.recommended_product));
});

test("explicit cheaper Laptop processes only Laptop and preserves Mouse state", () => {
  const result = turn("Can you recommend a cheaper laptop?");
  assertTarget(result, laptop, laptopRec);
  assert.deepEqual(result.state.last_recommendations, [laptopRec, mouseRec]);
  assert.match(result.response.answer, /Laptop/);
});

test("ambiguous cheaper comparison takes clarification edges without retrieval or memory writes", () => {
  const result = turn("Anything cheaper?");
  assert.deepEqual(result.state.product_requests, [laptop, mouse]);
  assert.deepEqual(result.state.last_recommendations, [laptopRec, mouseRec]);
  assert.deepEqual(result.value(ids.guard, "target_requests"), []);
  assert.deepEqual(result.state.missing_fields, ["follow_up_target"]);
  assert.equal(result.state.follow_up_intent, "cheaper");
  assert.equal(result.state.clarification_needed, true);
  assert.ok(result.trace.includes(ids.clarify));
  assert.ok(!result.trace.includes(ids.query));
  assert.ok(!result.trace.includes(ids.retrieve));
  assert.ok(!result.trace.includes(ids.saveRecommendations));
  assert.equal(result.response.clarification_needed, true);
  assert.deepEqual(result.response.recommendations, []);
  assert.match(result.response.answer, /Laptop.*Mouse/);
  assertPublic(result.response);
});

test("Mouse continuation resolves saved cheaper intent with the original budget and Gaming usage", () => {
  const pending = turn("Anything cheaper?");
  const result = turn("Mouse", { state: pending.state, extraction: {
    scope_status: "help", clarification_needed: "true", missing_fields_json: '["budget","main_usage"]',
    product_requests_json: '[{"category":"Mouse","budget":null,"main_usage":null}]'
  } });
  assertTarget(result, mouse, mouseRec);
  assert.deepEqual(result.state.missing_fields, []);
  assert.equal(result.state.clarification_needed, false);
});

for (const [question, intent] of [
  ["Show me a more expensive mouse.", "more_expensive"],
  ["Give me an alternative laptop.", "alternative"],
  ["Can you recommend another mouse?", "alternative"]
]) test(`explicit target: ${question}`, () => {
  const result = turn(question);
  assert.equal(result.value(ids.guard, "follow_up_intent"), intent);
  assert.deepEqual(result.state.product_requests, [laptop, mouse]);
  assert.equal(result.value(ids.guard, "target_requests").length, 1);
  assert.equal(result.retrievalInputs[0].flat().length, 1);
});

test("reordered request/history arrays still use only the Mouse anchor", () => {
  for (const requests of [[mouse, laptop], [laptop, mouse]]) {
    for (const history of [[laptopRec, mouseRec], [mouseRec, laptopRec]]) {
      const result = turn("A cheaper mouse, please?", { state: initialState(requests, history) });
      assert.deepEqual(result.state.product_requests, requests);
      assert.deepEqual(result.value(ids.guard, "target_requests"), [mouse]);
      assert.deepEqual(result.value(ids.query, "comparison_history"), [mouseRec]);
      assert.ok(!JSON.stringify(result.retrievalInputs).includes(String(laptopRec.price)));
    }
  }
});

test("query builder has no index fallback and does not select duplicate same-category anchors", () => {
  for (const history of [[laptopRec], [], [mouseRec, { ...mouseRec, category: " MOUSE " }]]) {
    const result = execute(ids.query, { user_question: "A cheaper mouse?", active_requests: [mouse],
      follow_up_intent: "cheaper", previous_recommendations: history });
    assert.equal(result.retrieval_queries.length, 1);
    assert.doesNotMatch(result.retrieval_queries[0], /Previous recommendation:|Previous price:/);
    assert.deepEqual(result.comparison_history, []);
  }
});

test("category matching normalizes case and whitespace", () => {
  const result = turn("A cheaper mouse?", { state: initialState([laptop, { ...mouse, category: " mOuSe " }],
    [laptopRec, { ...mouseRec, category: " MOUSE " }]) });
  assert.equal(result.value(ids.guard, "target_requests")[0].category, "Mouse");
  assert.ok(result.trace.includes(ids.final));
});

for (const question of ["A cheaper laptop or mouse?", "A cheaper mouse and laptop?"]) {
  test(`multiple explicit targets require clarification: ${question}`, () => {
    const result = turn(question);
    assert.ok(result.trace.includes(ids.clarify));
    assert.ok(!result.trace.includes(ids.retrieve));
    assert.deepEqual(result.state.product_requests, [laptop, mouse]);
  });
}

test("duplicate stored target requests are never resolved by choosing the first", () => {
  const requests = [laptop, mouse, { ...mouse, budget: 500 }];
  const result = turn("A cheaper mouse?", { state: initialState(requests) });
  assert.ok(!result.trace.includes(ids.retrieve));
  assert.equal(result.response.clarification_needed, true);
  assert.deepEqual(result.state.product_requests, requests);
});

for (const question of ["Anything cheaper?", "Give me an alternative.", "Show me a more expensive one."]) {
  test(`single-product follow-up remains supported: ${question}`, () => {
    const result = turn(question, { state: initialState([laptop], [laptopRec]), extraction: { scope_status: "unrelated" } });
    assert.deepEqual(result.state.product_requests, [laptop]);
    assert.deepEqual(result.value(ids.guard, "target_requests"), [laptop]);
    assert.ok(result.trace.includes(ids.retrieve));
    assertPublic(result.response);
  });
}

for (const [question, intent] of [
  ["Could I get something cheaper?", "cheaper"],
  ["Can I have a more affordable option?", "cheaper"],
  ["Do you have something cheaper?", "cheaper"],
  ["Could I get a more expensive one?", "more_expensive"],
  ["Could I get a different one?", "alternative"]
]) test(`audit: single saved request survives extraction loss: ${question}`, () => {
  const result = turn(question, { state: initialState([laptop], [laptopRec]), extraction: {
    scope_status: "supported", follow_up_intent: intent, product_requests_json: "[]"
  } });
  assert.deepEqual(result.state.product_requests, [laptop]);
  assert.deepEqual(result.value(ids.guard, "target_requests"), [laptop]);
  assert.equal(result.state.follow_up_intent, intent);
  assert.ok(result.trace.includes(ids.saveRequests));
  assert.ok(result.trace.includes(ids.retrieve));
  assert.match(result.retrievalInputs[0].flat()[0], /Hard budget: RMB 6000/);
  assert.match(result.retrievalInputs[0].flat()[0], /Main usage: studying/);
  assert.deepEqual(result.state.last_recommendations, [laptopRec]);
  assertPublic(result.response);
});

test("audit: single-product recovery does not overwrite explicit new budget or usage", () => {
  const updated = { ...laptop, budget: 7000, main_usage: "office" };
  const result = turn("Could I get something cheaper for office under RMB 7000?", {
    state: initialState([laptop], [laptopRec]), extraction: {
      follow_up_intent: "cheaper", product_requests_json: JSON.stringify([updated])
    }
  });
  assert.deepEqual(result.state.product_requests, [updated]);
  assert.deepEqual(result.value(ids.guard, "target_requests"), [updated]);
});

test("audit: an unrecognized single comparison clarifies without erasing the saved request", () => {
  const result = turn("I'd prefer a less costly option.", { state: initialState([laptop], [laptopRec]),
    extraction: { follow_up_intent: "cheaper" }, clarification: {
      answer: "Please restate the comparison and its requirements.", recommendations: [], next_step: "Include the product category.", clarification_needed: true
    } });
  assert.deepEqual(result.state.product_requests, [laptop]);
  assert.ok(result.trace.includes(ids.clarify));
  assert.ok(!result.trace.includes(ids.retrieve));
});

test("audit: comparison without saved context asks for details without inventing a request", () => {
  const result = turn("Could I get something cheaper?", { state: initialState([], []),
    extraction: { follow_up_intent: "cheaper" }, clarification: {
      answer: "What product do you need?", recommendations: [], next_step: "Tell me the category.", clarification_needed: true
    } });
  assert.deepEqual(result.state.product_requests, []);
  assert.deepEqual(result.state.last_recommendations, []);
  assert.ok(result.trace.includes(ids.clarify));
  assert.ok(!result.trace.includes(ids.retrieve));
});

test("audit: a standalone comparison cannot invent context from fabricated extraction", () => {
  const result = turn("Could I get something cheaper?", { state: initialState([], []), extraction: {
    follow_up_intent: "cheaper", product_requests_json: JSON.stringify([laptop])
  }, clarification: { answer: "What product do you need?", recommendations: [], next_step: "Tell me the category.", clarification_needed: true } });
  assert.deepEqual(result.state.product_requests, []);
  assert.ok(result.trace.includes(ids.clarify));
  assert.ok(!result.trace.includes(ids.retrieve));
});

test("audit: a new explicit comparison category preserves only the facts actually supplied", () => {
  const result = turn("Could I get a cheaper mouse?", { state: initialState([], []), extraction: {
    follow_up_intent: "cheaper", product_requests_json: JSON.stringify([{ ...mouse, budget: 9000, main_usage: "office" }])
  }, clarification: { answer: "What is your Mouse budget?", recommendations: [], next_step: "Tell me the budget.", clarification_needed: true } });
  assert.deepEqual(result.state.product_requests, [{ category: "Mouse", budget: null, main_usage: null }]);
  assert.ok(result.trace.includes(ids.clarify));
  assert.ok(!result.trace.includes(ids.retrieve));
});

test("audit: single-product recovery cannot hijack an unrelated cheaper request", () => {
  const state = initialState([laptop], [laptopRec]);
  const result = turn("Could I get something cheaper for a train trip?", {
    state, extraction: { scope_status: "unrelated", follow_up_intent: "cheaper" }
  });
  assert.deepEqual(result.state, state);
  assert.ok(!result.trace.includes(ids.saveRequests));
  assert.ok(!result.trace.includes(ids.retrieve));
});

for (const [question, intent] of [["Give me an alternative.", "alternative"], ["Anything more expensive?", "more_expensive"]]) {
  test(`audit: ambiguous ${intent} persists intent and resolves only Mouse`, () => {
    const pending = turn(question, { clarification: {
      answer: `Do you mean a ${intent} Laptop or Mouse?`, recommendations: [], next_step: "Choose the category.", clarification_needed: true
    } });
    assert.equal(pending.state.follow_up_intent, intent);
    assert.match(pending.prompts[ids.clarify], new RegExp(`Pending comparison intent:\\s*"${intent}"`));
    assert.deepEqual(pending.state.missing_fields, ["follow_up_target"]);
    assert.ok(!pending.trace.includes(ids.retrieve));
    const resolved = turn("Mouse", { state: pending.state });
    assert.equal(resolved.state.follow_up_intent, intent);
    assert.deepEqual(resolved.value(ids.guard, "target_requests"), [mouse]);
    assert.deepEqual(resolved.state.product_requests, [laptop, mouse]);
    assert.deepEqual(resolved.value(ids.query, "comparison_history"), [mouseRec]);
    assert.ok(resolved.trace.includes(ids.retrieve));
  });
}

test("unsupported cheaper Camera stays unsupported and does not alter saved context", () => {
  const state = initialState();
  const result = turn("Recommend a cheaper camera.", { state, extraction: { scope_status: "unsupported",
    follow_up_intent: "cheaper", product_requests_json: '[{"category":"Camera","budget":1000,"main_usage":"photography"}]' } });
  assert.equal(result.value(ids.guard, "scope_status"), "unsupported");
  assert.deepEqual(result.state, state);
  assert.ok(!result.trace.includes(ids.retrieve));
  assertPublic(result.response);
});

for (const question of ["Is the train cheaper than a taxi?", "Write a cheaper travel itinerary.",
  "Give me an alternative to writing my essay.", "I do not want a cheaper option.", "Explain cheaper mouse technology."]) {
  test(`unrelated or negated wording cannot recover product state: ${question}`, () => {
    const state = initialState();
    const result = turn(question, { state, extraction: { scope_status: "unrelated", follow_up_intent: "cheaper" } });
    assert.equal(result.value(ids.guard, "scope_status"), "unrelated");
    assert.deepEqual(result.state, state);
    assert.ok(!result.trace.includes(ids.retrieve));
  });
}

test("a new supported request replaces pending clarification instead of inheriting cheaper intent", () => {
  const pending = turn("Anything cheaper?");
  const keyboard = { category: "Keyboard", budget: 300, main_usage: "office" };
  const result = turn("I need a keyboard for office under RMB 300.", { state: pending.state,
    extraction: { product_requests_json: JSON.stringify([keyboard]) },
    modelResponse: publicResponse([recommendation("Logitech K848")], "Here is a keyboard.") });
  assert.equal(result.state.follow_up_intent, "none");
  assert.deepEqual(result.state.missing_fields, []);
  assert.deepEqual(result.state.product_requests, [keyboard]);
  assert.deepEqual(result.state.last_recommendations, [recommendation("Logitech K848")]);
});

test("a category-only reply without pending comparison is not assigned stale intent", () => {
  const state = { ...initialState(), follow_up_intent: "cheaper", missing_fields: [] };
  const result = turn("Mouse", { state, extraction: { product_requests_json: '[{"category":"Mouse","budget":null,"main_usage":null}]' },
    clarification: { answer: "What is your Mouse budget?", recommendations: [], next_step: "", clarification_needed: true } });
  assert.equal(result.value(ids.guard, "follow_up_intent"), "none");
});

test("non-supported turns do not consume or rewrite a pending clarification", () => {
  const pending = turn("Anything cheaper?");
  for (const [question, scope] of [["Hello", "help"], ["Write an essay", "unrelated"], ["A camera", "unsupported"]]) {
    const other = turn(question, { state: pending.state, extraction: { scope_status: scope } });
    assert.deepEqual(other.state, pending.state);
    assert.ok(!other.trace.includes(ids.saveRequests));
    assert.ok(!other.trace.includes(ids.retrieve));
    assertTarget(turn("Mouse", { state: other.state }), mouse, mouseRec);
  }
});

for (const scope of ["unrelated", "help", "supported", "unsupported"]) {
  test(`audit: cancellation persists through the writer even when extraction says ${scope}`, () => {
    const pending = turn("Anything cheaper?");
    const cancelled = turn("Never mind, cancel that comparison.", { state: pending.state,
      extraction: { scope_status: scope }, clarification: {
        answer: "The comparison is cancelled.", recommendations: [], next_step: "Tell me what you need next.", clarification_needed: false
      } });
    assert.equal(cancelled.value(ids.guard, "comparison_cancelled"), true);
    assert.equal(cancelled.value(ids.guard, "skip_retrieval"), true);
    assert.equal(cancelled.state.follow_up_intent, "none");
    assert.deepEqual(cancelled.state.missing_fields, []);
    assert.equal(cancelled.state.clarification_needed, false);
    assert.deepEqual(cancelled.state.product_requests, [laptop, mouse]);
    assert.deepEqual(cancelled.state.last_recommendations, [laptopRec, mouseRec]);
    assert.ok(cancelled.trace.includes(ids.saveRequests));
    assert.ok(cancelled.trace.indexOf(ids.saveRequests) < cancelled.trace.indexOf(ids.clarifyRouter));
    assert.ok(cancelled.trace.includes(ids.clarify));
    assert.ok(!cancelled.trace.includes(ids.retrieve));
    assert.ok(!cancelled.trace.includes(ids.saveRecommendations));
    assertPublic(cancelled.response);
    assert.match(cancelled.prompts[ids.clarify], /Comparison cancelled:\s*true/);
    const next = turn("Mouse", { state: cancelled.state, extraction: {
      product_requests_json: '[{"category":"Mouse","budget":null,"main_usage":null}]', clarification_needed: "true"
    }, clarification: { answer: "What is your Mouse budget?", recommendations: [], next_step: "", clarification_needed: true } });
    assert.equal(next.state.follow_up_intent, "none");
    assert.ok(!next.state.missing_fields.includes("follow_up_target"));
    assert.ok(!next.trace.includes(ids.retrieve));
  });
}

test("audit: cancellation wording inside an unrelated task does not cancel shopping context", () => {
  const pending = turn("Anything cheaper?");
  const other = turn('Write a story where someone says "never mind, cancel that comparison".', {
    state: pending.state, extraction: { scope_status: "unrelated" }
  });
  assert.deepEqual(other.state, pending.state);
  assert.ok(!other.trace.includes(ids.saveRequests));
});

for (const negation of ["I do not want a cheaper option.", "I don't need a cheaper option.", "Not a more expensive mouse."]) {
  test(`audit: complete current request supersedes pending intent: ${negation}`, () => {
    const pending = turn("Anything cheaper?");
    const updated = { category: "Mouse", budget: 150, main_usage: "office" };
    const result = turn(`${negation} I need a mouse for office under RMB 150.`, { state: pending.state,
      extraction: { follow_up_intent: "none", product_requests_json: JSON.stringify([updated]) },
      modelResponse: publicResponse([officeRec], "Here is a Mouse for office.") });
    assert.deepEqual(result.state.product_requests, [updated]);
    assert.deepEqual(result.value(ids.guard, "target_requests"), [updated]);
    assert.equal(result.state.follow_up_intent, "none");
    assert.deepEqual(result.state.missing_fields, []);
    assert.ok(result.trace.includes(ids.retrieve));
    assert.deepEqual(result.response.recommendations, [officeRec]);
    assert.match(result.retrievalInputs[0].flat()[0], /Hard budget: RMB 150/);
    assert.match(result.retrievalInputs[0].flat()[0], /Main usage: office/);
  });
}

for (const usage of ["gaming", "play game", "play games", "playing games", "video games", "competitive gaming", "games"]) {
  test(`audit: actual cheaper validator rejects Office-only Mouse for ${usage}`, () => {
    const result = execute(ids.validate, { raw_json: JSON.stringify(publicResponse([officeRec])),
      active_requests: [{ ...mouse, main_usage: usage }], previous_recommendations: [laptopRec, mouseRec], follow_up_intent: "cheaper" });
    assert.equal(result.validation_ok, false);
    assert.match(result.validation_error, /Usage validation violation/);
  });
}

test("audit: a Gaming alias can still accept the approved Gaming Mouse with a valid comparison", () => {
  const result = execute(ids.validate, { raw_json: JSON.stringify(publicResponse([mouseRec])),
    active_requests: [{ ...mouse, main_usage: "playing games" }], previous_recommendations: [premiumMouseRec], follow_up_intent: "cheaper" });
  assert.equal(result.validation_ok, true, result.validation_error);
});

test("audit: mutation assertions observe the actual executed VM input", () => {
  const code = field(ids.guard, "code");
  const saved = code.value;
  try {
    code.value = `${saved}\ninput.mutationSentinel = true;`;
    assert.throws(() => execute(ids.guard, { user_question: "Hello", scope_status: "help" }), /mutated input/);
  } finally {
    code.value = saved;
  }
});

test("unhandled comparison with field edits requires restatement and does not leave a resumable old-budget action", () => {
  const result = turn("A cheaper mouse under RMB 100 for office.", { extraction: {
    follow_up_intent: "cheaper", product_requests_json: '[{"category":"Mouse","budget":100,"main_usage":"office"}]'
  }, clarification: { answer: "Please restate the category, budget and usage for your comparison.",
    recommendations: [], next_step: "Include the updated requirements.", clarification_needed: true } });
  assert.ok(result.trace.includes(ids.clarify));
  assert.ok(!result.trace.includes(ids.retrieve));
  assert.deepEqual(result.state.product_requests, [laptop, mouse]);
  assert.deepEqual(result.state.missing_fields, ["follow_up_details"]);
  assert.equal(result.state.follow_up_intent, "none");
});

test("successful targeted recommendation merges only its category; a second comparison uses the new anchor", () => {
  const officeMouse = { ...mouse, budget: 500, main_usage: "office" };
  const state = initialState([laptop, officeMouse], [laptopRec, premiumMouseRec]);
  const cheaper = turn("A cheaper mouse?", { state, modelResponse: publicResponse([officeRec], "Here is a cheaper Mouse.") });
  assert.deepEqual(cheaper.response.recommendations, [officeRec]);
  assert.deepEqual(cheaper.state.last_recommendations, [laptopRec, officeRec]);
  assert.deepEqual(cheaper.state.product_requests, [laptop, officeMouse]);
  const more = turn("A more expensive mouse?", { state: cheaper.state, modelResponse: publicResponse([premiumMouseRec]) });
  assert.deepEqual(more.value(ids.query, "comparison_history"), [officeRec]);
  assert.deepEqual(more.state.last_recommendations, [laptopRec, premiumMouseRec]);
});

test("a no-result follow-up retains the anchor for the next comparison", () => {
  const noResult = turn("A cheaper mouse?");
  const next = turn("An alternative mouse?", { state: noResult.state });
  assert.deepEqual(next.value(ids.query, "comparison_history"), [mouseRec]);
  assert.deepEqual(next.state.last_recommendations, [laptopRec, mouseRec]);
});

test("a valid alternative is accepted but the identical product is rejected", () => {
  const state = initialState([laptop, { ...mouse, budget: 500, main_usage: "office" }], [laptopRec, premiumMouseRec]);
  const valid = turn("An alternative mouse?", { state, modelResponse: publicResponse([officeRec]) });
  assert.deepEqual(valid.response.recommendations, [officeRec]);
  const repeated = turn("An alternative mouse?", { state, modelResponse: publicResponse([premiumMouseRec]) });
  assert.equal(repeated.value(ids.validate, "validation_ok"), false);
  assert.deepEqual(repeated.state.last_recommendations, state.last_recommendations);
});

test("comparison still respects an exact hard-budget boundary and rejects one RMB over it", () => {
  for (const budget of [429, 428]) {
    const state = initialState([laptop, { ...mouse, budget, main_usage: "office" }], [laptopRec, officeRec]);
    const result = turn("A more expensive mouse?", { state, modelResponse: publicResponse([premiumMouseRec]) });
    assert.equal(result.value(ids.validate, "validation_ok"), budget === 429);
  }
});

for (const [name, recommendations] of [
  ["Office-only Mouse for Gaming", [officeRec]],
  ["unrelated Laptop", [laptopRec]],
  ["same Mouse for cheaper", [mouseRec]],
  ["over-budget Mouse", [premiumMouseRec]],
  ["incorrect reference price", [{ ...mouseRec, price: 228 }]],
  ["incorrect source", [{ ...mouseRec, source: "Different source" }]],
  ["unknown product", [{ ...mouseRec, recommended_product: "Unknown Mouse" }]],
  ["duplicate category", [officeRec, mouseRec]]
]) test(`invalid targeted result cannot replace history: ${name}`, () => {
  const result = turn("A cheaper mouse?", { modelResponse: publicResponse(recommendations) });
  assert.equal(result.value(ids.validate, "validation_ok"), false);
  assert.ok(!result.trace.includes(ids.saveRecommendations));
  assert.deepEqual(result.state.last_recommendations, [laptopRec, mouseRec]);
  assert.deepEqual(result.response.recommendations, []);
  assertPublic(result.response);
});

test("missing, duplicated or corrupt comparison anchors fail safely", () => {
  for (const history of [[laptopRec], [laptopRec, mouseRec, mouseRec],
    [laptopRec, { ...mouseRec, price: NaN }], [laptopRec, { ...mouseRec, recommended_product: "Unknown Mouse" }]]) {
    const result = turn("An alternative mouse?", { state: initialState([laptop, mouse], history), modelResponse: publicResponse([mouseRec]) });
    assert.equal(result.value(ids.validate, "validation_ok"), false);
    assert.ok(!result.trace.includes(ids.saveRecommendations));
  }
});

test("ordinary no-result retains anchors; a normal successful request retains baseline replacement semantics", () => {
  const state = initialState();
  const none = turn("A gaming mouse under RMB 50.", { state,
    extraction: { product_requests_json: JSON.stringify([{ ...mouse, budget: 50 }]) } });
  assert.deepEqual(none.state.last_recommendations, state.last_recommendations);
  const normal = turn("I need a laptop for studying under RMB 6000.", { state,
    extraction: { product_requests_json: JSON.stringify([laptop]) }, modelResponse: publicResponse([laptopRec]) });
  assert.deepEqual(normal.state.last_recommendations, [laptopRec]);
});

test("graph bindings separate full state, current targets, comparison history and memory output", () => {
  assert.equal(graph.nodes.length, 18);
  assert.equal(graph.edges.length, 17);
  assert.equal(graph.chatConfig.variables.length, 5, "No new persistent variable is needed");
  const target = output(ids.guard, "target_requests");
  assert.equal(target?.valueType, "arrayObject");
  for (const id of [ids.query, ids.validate]) assert.deepEqual(field(id, "active_requests").value, [ids.guard, target.id]);
  assert.deepEqual(field(ids.guard, "stored_follow_up_intent").value, ["VARIABLE_NODE_ID", variableKeys.follow_up_intent]);
  assert.deepEqual(field(ids.guard, "stored_missing_fields").value, ["VARIABLE_NODE_ID", variableKeys.missing_fields]);
  const requestUpdate = field(ids.saveRequests, "updateList").value.find((item) => item.variable[1] === variableKeys.product_requests);
  assert.deepEqual(requestUpdate.value, [[ids.guard, output(ids.guard, "product_requests").id]]);
  const memory = output(ids.validate, "recommendations_to_store");
  assert.equal(memory?.valueType, "arrayObject");
  assert.deepEqual(field(ids.saveRecommendations, "updateList").value[0].value, [[ids.validate, memory.id]]);
  assert.equal(output(ids.query, "retrieval_queries").valueType, "arrayString");
  assert.deepEqual(field(ids.retrieve, "datasetSearchInput").value, [[ids.query, output(ids.query, "retrieval_queries").id]]);
  assert.deepEqual(field(ids.retrieve, "datasets").value, []);
  assert.ok(field(ids.recommend, "systemPrompt").value.includes(`{{$${ids.guard}.${target.id}$}}`));
  assert.ok(field(ids.recommend, "systemPrompt").value.includes(`{{$${ids.query}.${output(ids.query, "comparison_history").id}$}}`));
  assert.ok(graph.edges.some((edge) => edge.source === ids.clarifyRouter && edge.target === ids.clarify));
  assert.ok(graph.edges.some((edge) => edge.source === ids.clarifyRouter && edge.target === ids.query && edge.sourceHandle.endsWith("-ELSE")));
  const skip = output(ids.guard, "skip_retrieval");
  const cancelled = output(ids.guard, "comparison_cancelled");
  assert.equal(skip?.valueType, "boolean");
  assert.equal(cancelled?.valueType, "boolean");
  assert.deepEqual(field(ids.clarifyRouter, "ifElseList").value[0].list[0].variable, [ids.guard, skip.id]);
  assert.ok(field(ids.clarify, "systemPrompt").value.includes(`{{$${ids.guard}.${cancelled.id}$}}`));
});

test("all node/global reference pairs and output types resolve in the exported schema", () => {
  const variables = new Map(graph.chatConfig.variables.map((item) => [item.key, item]));
  function visit(value) {
    if (Array.isArray(value)) {
      if (value.length === 2 && value.every((part) => typeof part === "string") && (value[0] === "VARIABLE_NODE_ID" || nodes.has(value[0]))) {
        assert.ok(value[0] === "VARIABLE_NODE_ID" ? variables.has(value[1]) : nodes.get(value[0]).outputs.some((item) => item.id === value[1]), value.join("."));
      } else value.forEach(visit);
    } else if (value && typeof value === "object") Object.values(value).forEach(visit);
  }
  for (const node of graph.nodes) {
    visit(node.inputs);
    assert.equal(new Set(node.outputs.map((item) => item.id)).size, node.outputs.length);
    for (const item of node.inputs) {
      if (Array.isArray(item.value) && item.value.length === 2 && nodes.has(item.value[0])) {
        const sourceType = nodes.get(item.value[0]).outputs.find((entry) => entry.id === item.value[1]).valueType;
        assert.ok(item.valueType === "any" || item.valueType === sourceType, `${node.nodeId}.${item.key}: ${sourceType} -> ${item.valueType}`);
      }
    }
  }
});

test("all 27 products pass catalogue and usage validation with a real comparison intent", () => {
  assert.equal(dataset.products.length, 27);
  assert.equal(new Set(dataset.products.map((item) => item.category)).size, 9);
  for (const product of dataset.products) {
    const request = { category: product.category, budget: product.price_rmb, main_usage: product.main_usage[0] };
    const previous = dataset.products.find((item) => item.category === product.category && item.price_rmb !== product.price_rmb);
    const intent = product.price_rmb < previous.price_rmb ? "cheaper" : "more_expensive";
    const result = execute(ids.validate, { raw_json: JSON.stringify(publicResponse([recommendation(product.product)])),
      active_requests: [request], previous_recommendations: [recommendation(previous.product)], follow_up_intent: intent });
    assert.equal(result.validation_ok, true, `${product.product}: ${result.validation_error}`);
    assertPublic(JSON.parse(result.normalized_json));
  }
});

test("comparison usage tags exactly mirror the approved dataset without changing product facts", () => {
  const expression = field(ids.validate, "code").value.match(/const PRODUCT_CATALOG = (\{[\s\S]*?\n  \});/)[1];
  const catalogue = JSON.parse(JSON.stringify(new Script(`(${expression})`).runInNewContext({}, { timeout: 1000 })));
  assert.deepEqual(Object.keys(catalogue).sort(), dataset.products.map((item) => item.product).sort());
  for (const product of dataset.products) assert.deepEqual(catalogue[product.product], {
    category: product.category, price: product.price_rmb, source: product.source, main_usage: product.main_usage
  });
});
