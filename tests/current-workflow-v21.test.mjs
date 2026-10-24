// Execute the preserved Current graph. LLM/retrieval fixtures are offline only.
import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { Script, createContext } from "node:vm";

const baseline = JSON.parse(await readFile(new URL("../tools/templates/mytech_current_working_portable.json", import.meta.url), "utf8"));
const generated = JSON.parse(await readFile(new URL("../generated/v2_1_test/mytech-fastgpt-workflow-v2_1-TEST.json", import.meta.url), "utf8"));
const master = JSON.parse(await readFile(new URL("../catalogue/mytech_products_v2_1_test.json", import.meta.url), "utf8"));
const ids = { start: "448745", guard: "tWP2LwPvzFadPPtk", clarify: "ikIzMK483vihRths", recommend: "pskHz4kajjJnBWwG",
  query: "sxwN5Fd17Tc8leTf", validate: "fakNM8mmlYmewx67", writer: "oibK1q4js1HXjiO2", fallback: "zh9L8VeY9vKm3WnU" };
const product = id => master.products.find(item => item.id === id);
const rec = id => { const p = product(id); return { category: p.category, recommended_product: p.product, price: p.price_rmb, source: p.source, reason: "Matches the reference usage." }; };
const reply = recommendations => ({ answer: "Reference recommendations.", recommendations, next_step: "Would you like another option?", clarification_needed: false });
const laptop = { category: "Laptop", budget: 6000, main_usage: "study" };
const mouse = { category: "Mouse", budget: 300, main_usage: "gaming" };
const initial = (requests = [laptop, mouse], recommendations = [rec("LAP-001"), rec("MOU-002")]) => ({
  product_requests: structuredClone(requests), last_recommendations: structuredClone(recommendations),
  follow_up_intent: "none", missing_fields: [], clarification_needed: false
});
function turn(question, options = {}, graph = generated) {
  const nodes = new Map(graph.nodes.map(node => [node.nodeId, node]));
  const state = structuredClone(options.state || initial([], []));
  const variableKeys = Object.fromEntries(graph.chatConfig.variables.map(item => [item.label, item.key]));
  const globals = new Map(Object.entries(state).map(([label, value]) => [variableKeys[label], value]));
  const values = new Map(), trace = [], prompts = {}, queries = [];
  const field = (id, key) => nodes.get(id).inputs.find(item => item.key === key);
  function reference(pair) {
    const source = pair[0] === "VARIABLE_NODE_ID" ? globals : values.get(pair[0]);
    assert.ok(source?.has(pair[1]), `Unresolved Current binding ${pair.join(".")}`);
    return structuredClone(source.get(pair[1]));
  }
  function resolve(value) {
    if (Array.isArray(value)) {
      if (value.length === 2 && value.every(part => typeof part === "string")) return reference(value);
      return value.map(resolve);
    }
    if (typeof value === "string") return value.replace(/\{\{\$([^.$]+)\.([^$]+)\$\}\}/g,
      (_, id, key) => JSON.stringify(reference([id, key])));
    return value;
  }
  let current = ids.start, response;
  while (current) {
    assert.ok(trace.length < 40, "Unexpected Current graph cycle");
    trace.push(current);
    const node = nodes.get(current);
    let result = {}, handle = current + "-source-right";
    if (node.flowNodeType === "workflowStart") result = { userChatInput: question, userFiles: [] };
    else if (node.flowNodeType === "contentExtract") {
      options.observeExtraction?.(resolve(field(current, "content").value));
      result = { product_requests_json: "[]", missing_fields_json: "[]", clarification_needed: "false", follow_up_intent: "none", scope_status: "supported", ...options.extraction };
    }
    else if (node.flowNodeType === "code") {
      const input = Object.fromEntries(node.inputs.filter(item => !["code", "codeType", "system_addInputParam"].includes(item.key)).map(item => [item.key, resolve(item.value)]));
      const context = createContext({ input }, { codeGeneration: { strings: false, wasm: false } });
      const before = structuredClone(input);
      result = JSON.parse(JSON.stringify(new Script(field(current, "code").value + "\nmain(input);").runInContext(context, { timeout: 1000 })));
      assert.deepEqual(context.input, before);
      if (current === ids.validate) options.observeValidation?.(structuredClone(result));
    } else if (node.flowNodeType === "variableUpdate") {
      for (const update of field(current, "updateList").value) {
        const value = resolve(update.value);
        globals.set(update.variable[1], update.valueType.startsWith("array") ? value.flat(1) : value);
      }
    } else if (node.flowNodeType === "ifElseNode") {
      const index = field(current, "ifElseList").value.findIndex(branch => branch.list.every(condition => {
        assert.equal(condition.condition, "equalTo");
        return String(reference(condition.variable)) === String(condition.value);
      }));
      handle = current + "-source-" + (index < 0 ? "ELSE" : index === 0 ? "IF" : "ELSE IF " + index);
    } else if (node.flowNodeType === "datasetSearchNode") {
      const query = resolve(field(current, "userChatInput").value);
      assert.equal(typeof query, "string"); queries.push(query); result = { quoteQA: [] };
    } else if (node.flowNodeType === "chatNode") {
      prompts[current] = resolve(field(current, "systemPrompt").value);
      resolve(field(current, "fileUrlList").value);
      if (current === ids.clarify) {
        response = { answer: "Please clarify your request.", recommendations: [], next_step: "Tell me the missing details.", clarification_needed: true };
        result = { answerText: JSON.stringify(response) };
      } else result = { answerText: JSON.stringify(options.modelResponse || reply([])) };
    } else if (node.flowNodeType === "answerNode") response = JSON.parse(resolve(field(current, "text").value));
    else assert.fail("Unexpected node type " + node.flowNodeType);
    const outputs = new Map(node.outputs.filter(item => Object.hasOwn(result, item.key)).map(item => [item.id, result[item.key]]));
    if (current === ids.start) outputs.set("userFiles", []);
    values.set(current, outputs);
    current = graph.edges.find(edge => edge.source === current && edge.sourceHandle === handle)?.target;
  }
  for (const [label, key] of Object.entries(variableKeys)) state[label] = structuredClone(globals.get(key));
  assert.deepEqual(Object.keys(response).sort(), ["answer", "recommendations", "next_step", "clarification_needed"].sort());
  return { state, trace, response, prompts, queries };
}

const withoutInputStage = result => ({ ...result, trace: result.trace.filter(id => id !== "v21RmbInputNormalize") });
// Compare execution/state/public output under fixed model fixtures; prompt
// wording is deliberately different and gets separate content/binding checks.
const executionWithoutRecommendationWording = result => ({ ...result, prompts: Object.fromEntries(
  Object.entries(result.prompts).map(([id, prompt]) => [id, id === ids.recommend ? "reviewed recommendation prompt" : prompt])) });
function executeCode(identifier, input, expression = "main(input)") {
  const node = generated.nodes.find(item => item.nodeId === identifier);
  const code = node.inputs.find(field => field.key === "code").value;
  const context = createContext({ input: structuredClone(input) }, { codeGeneration: { strings: false, wasm: false } });
  const before = structuredClone(context.input);
  const result = new Script(code + "\n" + expression).runInContext(context, { timeout: 1000 });
  assert.deepEqual(context.input, before);
  return JSON.parse(JSON.stringify(result));
}

test("working Current baseline and TEST have identical successful baseline conversation behavior", () => {
  for (const [question, requests, recommendations] of [
    ["I need a study laptop under RMB 6000.", [laptop], [rec("LAP-001")]],
    ["I need a study laptop under RMB 6000 and a gaming mouse under RMB 300.", [laptop, mouse], [rec("LAP-001"), rec("MOU-002")]]
  ]) {
    const options = { extraction: { product_requests_json: JSON.stringify(requests) }, modelResponse: reply(recommendations) };
    assert.deepEqual(executionWithoutRecommendationWording(withoutInputStage(turn(question, options))),
      executionWithoutRecommendationWording(turn(question, options, baseline)));
  }
});

test("initial 54-product recommendation traverses native query/retrieval/validation and memory", () => {
  const request = { ...laptop, main_usage: "gaming" };
  const result = turn("I need a gaming laptop under RMB 6000.", { extraction: { product_requests_json: JSON.stringify([request]) }, modelResponse: reply([rec("LAP-005")]) });
  assert.deepEqual(result.response.recommendations, [rec("LAP-005")]);
  assert.deepEqual(result.state.last_recommendations, [rec("LAP-005")]);
  assert.ok(result.trace.includes(ids.writer));
  assert.match(result.queries[0], /Laptop for gaming within RMB 6000/);
});

test("initial usage failure follows Current's fallback and cannot reach the state writer", () => {
  const state = initial();
  const result = turn("I need a gaming laptop under RMB 6000.", { state, extraction: { product_requests_json: JSON.stringify([{ ...laptop, main_usage: "gaming" }]) }, modelResponse: reply([rec("LAP-001")]) });
  assert.deepEqual(result.response.recommendations, []);
  assert.ok(result.trace.includes(ids.fallback));
  assert.ok(!result.trace.includes(ids.writer));
  assert.deepEqual(result.state.last_recommendations, state.last_recommendations);
});

test("clarification route and prompt bindings are unchanged from working Current", () => {
  const options = { state: initial(), extraction: { product_requests_json: JSON.stringify([{ category: "Tablet", budget: null, main_usage: "study" }]), missing_fields_json: '["budget"]', clarification_needed: "true" } };
  const result = turn("I need a tablet for study.", options);
  assert.deepEqual(withoutInputStage(result), turn("I need a tablet for study.", options, baseline));
  assert.equal(result.response.clarification_needed, true);
  assert.deepEqual(result.queries, []);
  assert.ok(result.prompts[ids.clarify]);
  assert.deepEqual(result.state.last_recommendations, options.state.last_recommendations);
});

test("cheaper and alternative follow-ups preserve scope, budgets, usage and unrelated memory", () => {
  for (const intent of ["cheaper", "alternative"]) {
    const state = initial();
    const result = turn(intent === "cheaper" ? "cheaper Mouse" : "another Mouse", { state,
      extraction: { follow_up_intent: intent, product_requests_json: JSON.stringify([{ category: "Mouse", budget: null, main_usage: null }]) }, modelResponse: reply([rec("MOU-004")]) });
    assert.deepEqual(result.response.recommendations, [rec("MOU-004")]);
    assert.deepEqual(result.state.product_requests, state.product_requests);
    assert.deepEqual(result.state.last_recommendations, [state.last_recommendations[0], rec("MOU-004")]);
    assert.match(result.queries[0], /Mouse for gaming within RMB 300/);
  }
});

test("pending comparison clarifies then resolves Mouse through Current's bindings", () => {
  const first = turn("Anything cheaper?", { state: initial(), extraction: { scope_status: "help" } });
  assert.equal(first.response.clarification_needed, true);
  assert.equal(first.state.follow_up_intent, "cheaper");
  assert.deepEqual(first.queries, []);
  const next = turn("Mouse", { state: first.state,
    extraction: { product_requests_json: '[{"category":"Mouse","budget":null,"main_usage":null}]', clarification_needed: "true", missing_fields_json: '["budget","main_usage"]' }, modelResponse: reply([rec("MOU-004")]) });
  assert.deepEqual(next.response.recommendations, [rec("MOU-004")]);
  assert.deepEqual(next.state.last_recommendations, [rec("LAP-001"), rec("MOU-004")]);
});

test("multi-request invalid batch never persists partial recommendations", () => {
  const state = initial();
  const result = turn("I need a study laptop under RMB 6000 and a gaming mouse under RMB 300.", { state,
    extraction: { product_requests_json: JSON.stringify([laptop, mouse]) }, modelResponse: reply([rec("LAP-001"), rec("MOU-001")]) });
  assert.deepEqual(result.response.recommendations, []);
  assert.deepEqual(result.state.last_recommendations, state.last_recommendations);
  assert.ok(!result.trace.includes(ids.writer));
});

test("unknown usage, bad facts and hard-budget failures all retain Current memory", () => {
  const state = initial();
  for (const [usage, recommendation] of [
    ["gaming and quantum simulation", rec("MOU-004")], ["gaming", { ...rec("MOU-004"), price: 1 }],
    ["gaming", { ...rec("MOU-004"), source: "invented" }], ["gaming", rec("MOU-006")]
  ]) {
    const result = turn("I need a mouse under RMB 300 for " + usage + ".", { state,
      extraction: { product_requests_json: JSON.stringify([{ ...mouse, main_usage: usage }]) }, modelResponse: reply([recommendation]) });
    assert.deepEqual(result.response.recommendations, []);
    assert.deepEqual(result.state.last_recommendations, state.last_recommendations);
    assert.ok(!result.trace.includes(ids.writer));
  }
});

test("no-result comparison preserves anchors through the unchanged Current writer binding", () => {
  const state = initial();
  const result = turn("cheaper Mouse", { state, extraction: { follow_up_intent: "cheaper", product_requests_json: '[{"category":"Mouse","budget":null,"main_usage":null}]' }, modelResponse: reply([]) });
  assert.deepEqual(result.response.recommendations, []);
  assert.deepEqual(result.state.last_recommendations, state.last_recommendations);
  assert.ok(result.trace.includes(ids.writer));
});

const currencies = ["RMB 6000", "RMB 6,000", "¥6000", "¥6,000"];
for (const currency of currencies) {
  test(`${currency}: normalized before extraction on fresh, historical and repeated requests`, () => {
    const request = { category: "Laptop", budget: 6000, main_usage: "Gaming" };
    for (const startingState of [initial([], []), initial([{ ...laptop, budget: 3000 }], [rec("LAP-001")])]) {
      let state = startingState;
      for (let repeat = 0; repeat < 3; repeat++) {
        let actualInput;
        const result = turn(`I need a laptop under ${currency} for gaming.`, { state,
          extraction: { product_requests_json: JSON.stringify([{ ...request, budget: currency }]) },
          modelResponse: reply([rec("LAP-005")]), observeExtraction: value => { actualInput = value; } });
        assert.equal(actualInput, "I need a laptop under RMB 6000 for gaming.");
        assert.deepEqual(result.state.product_requests, [request]);
        assert.deepEqual(result.response.recommendations, [rec("LAP-005")]);
        assert.ok(result.trace.includes(ids.writer)); assert.ok(!result.trace.includes("wwmnkseAaXixej19"));
        assert.match(result.queries[0], /Laptop for Gaming within RMB 6000/);
        state = result.state;
      }
    }
  });

  test(`${currency}: inconsistent empty/unrelated extraction clarifies without stale facts or new recommendations`, () => {
    for (const state of [initial([], []), initial(), initial([{ ...laptop, main_usage: "Gaming" }], [rec("LAP-005")])]) {
      let previous = state;
      for (let repeat = 0; repeat < 2; repeat++) {
        const result = turn(`I need a laptop under ${currency} for gaming.`, { state: previous,
          extraction: { scope_status: "unrelated", product_requests_json: "[]" }, modelResponse: reply([rec("LAP-005")]) });
        assert.equal(result.response.clarification_needed, true);
        assert.deepEqual(result.state.product_requests, [{ category: "Laptop", budget: 6000, main_usage: null }]);
        assert.deepEqual(result.state.missing_fields, ["main_usage"]);
        assert.deepEqual(result.state.last_recommendations, previous.last_recommendations);
        assert.deepEqual(result.response.recommendations, []); assert.deepEqual(result.queries, []);
        assert.ok(result.trace.includes(ids.clarify)); assert.ok(!result.trace.includes(ids.writer));
        assert.ok(!result.trace.includes("wwmnkseAaXixej19"));
        previous = result.state;
      }
      const recovered = turn("gaming", { state: previous,
        extraction: { product_requests_json: '[{"category":"Laptop","budget":6000,"main_usage":"gaming"}]' }, modelResponse: reply([rec("LAP-005")]) });
      assert.deepEqual(recovered.response.recommendations, [rec("LAP-005")]);
    }
  });

  test(`${currency}: a budget update preserves usage and the other active product`, () => {
    let actualInput;
    const requests = [{ ...laptop, budget: currency }, mouse];
    const result = turn(`My laptop budget is now ${currency}.`, { state: initial(),
      extraction: { product_requests_json: JSON.stringify(requests) }, modelResponse: reply([rec("LAP-001"), rec("MOU-002")]),
      observeExtraction: value => { actualInput = value; } });
    assert.equal(actualInput, "My laptop budget is now RMB 6000.");
    assert.deepEqual(result.state.product_requests, [laptop, mouse]);
    assert.deepEqual(result.response.recommendations, [rec("LAP-001"), rec("MOU-002")]);
  });
}

test("new request evidence cannot arise solely from prior Laptop state or device mentions", () => {
  for (const [question, scope, requests] of [
    ["Tell me a joke about a laptop.", "unrelated", []],
    ['Translate "I need a laptop under ¥6,000 for gaming."', "unrelated", []],
    ['"I need a laptop under ¥6,000 for gaming."', "unrelated", []],
    ["I don't need a laptop.", "unrelated", []],
    ["I need a laptop repaired.", "unrelated", []],
    ["If I need a laptop, what does that phrase mean?", "unrelated", []],
    ["Can you recommend books about laptops?", "unsupported", [{ category: "Book", budget: null, main_usage: null }]],
    ["I need a camera under RMB 6000.", "unsupported", [{ category: "Camera", budget: 6000, main_usage: "photography" }]],
    ["I need a laptop and a camera under RMB 6000.", "unsupported", [{ ...laptop }, { category: "Camera", budget: 6000, main_usage: "photography" }]],
    ["Do you support laptops?", "help", []], ["Hello MyTech", "help", []], ["What can MyTech recommend?", "help", []]
  ]) {
    const state = initial();
    const result = turn(question, { state, extraction: { scope_status: scope, product_requests_json: JSON.stringify(requests) } });
    assert.deepEqual(result.state, state, question);
    assert.deepEqual(result.queries, [], question);
    assert.ok(result.trace.includes(scope === "help" ? "d6kCXfQ1mcJ5hT8J" : scope === "unsupported" ? "bgcB6pN1kaSjIiAk" : "wwmnkseAaXixej19"), question);
  }
});

test("scope safeguard covers malformed extraction and help/default labels while respecting unsupported", () => {
  for (const scope of ["help", "unrelated", "unknown", "supported"]) {
    const result = turn("I need a laptop under ¥6,000 for gaming.", { extraction: { scope_status: scope, product_requests_json: "not JSON" } });
    assert.equal(result.response.clarification_needed, true); assert.deepEqual(result.queries, []);
    assert.deepEqual(result.state.product_requests, [{ category: "Laptop", budget: 6000, main_usage: null }]);
  }
  const result = turn("I need a laptop under ¥6,000 for gaming.", { extraction: { scope_status: "unsupported" } });
  assert.ok(result.trace.includes("bgcB6pN1kaSjIiAk"));
});

test("multiple RMB formats remain independent; contradictory multi-product extraction clarifies the whole batch", () => {
  const question = "I need a laptop under ¥6,000 for study and a mouse under RMB 300 for gaming.";
  const good = turn(question, { extraction: { product_requests_json: JSON.stringify([laptop, mouse]) }, modelResponse: reply([rec("LAP-001"), rec("MOU-002")]) });
  assert.deepEqual(good.state.product_requests, [laptop, mouse]); assert.equal(good.response.recommendations.length, 2);
  const bad = turn(question, { state: initial(), extraction: { scope_status: "unrelated" } });
  assert.deepEqual(bad.state.product_requests, [{ category: "Laptop", budget: 6000, main_usage: null }, { category: "Mouse", budget: 300, main_usage: null }]);
  assert.equal(bad.response.clarification_needed, true); assert.deepEqual(bad.queries, []);
  assert.deepEqual(bad.state.last_recommendations, initial().last_recommendations);
  const punctuated = turn("I need a study laptop under ¥6,000, and a gaming mouse under RMB 300.", {
    extraction: { product_requests_json: JSON.stringify([laptop, mouse]) }, modelResponse: reply([rec("LAP-001"), rec("MOU-002")]) });
  assert.deepEqual(punctuated.state.product_requests, [laptop, mouse]); assert.equal(punctuated.response.recommendations.length, 2);
});

test("foreign/mixed currencies are never converted, reused from history or sent to recommendation", () => {
  for (const currency of ["USD 6000", "$6000", "EUR 6000", "€6000", "HK$6000", "JPY ¥6,000", "¥6,000 Japanese yen", "ZAR 6000", "XYZ 6000", "₽6000", "RMB 6000 and USD 100"]) {
    const question = `I need a laptop under ${currency} for gaming.`;
    const normalized = executeCode("v21RmbInputNormalize", { user_question: question });
    assert.equal(normalized.normalized_question, question, currency); assert.equal(normalized.currency_status, "foreign_or_mixed", currency);
    for (const state of [initial([], []), initial([{ ...laptop, main_usage: "Gaming" }], [rec("LAP-005")])]) {
      const result = turn(question, { state, extraction: { product_requests_json: '[{"category":"Laptop","budget":6000,"main_usage":"Gaming"}]' }, modelResponse: reply([rec("LAP-005")]) });
      assert.equal(result.response.clarification_needed, true, currency); assert.deepEqual(result.queries, []);
      assert.equal(result.state.product_requests[0].budget, null, currency); assert.ok(result.state.missing_fields.includes("budget"));
      assert.deepEqual(result.state.last_recommendations, state.last_recommendations); assert.ok(!result.trace.includes(ids.writer));
    }
  }
});

test("normalization is idempotent, preserves exact amounts, and rejects invalid numeric extraction", () => {
  for (const text of ["RMB 6000", "RMB 6,000", "¥6000", "¥6,000", "CNY 6,000", "RMB 6000.50"]) {
    const first = executeCode("v21RmbInputNormalize", { user_question: text });
    const second = executeCode("v21RmbInputNormalize", { user_question: first.normalized_question });
    assert.deepEqual(second, first); assert.equal(first.currency_status, "rmb_or_unspecified");
    assert.equal(first.normalized_question, text.endsWith(".50") ? "RMB 6000.50" : "RMB 6000");
  }
  for (const text of ["¥6,00", "RMB 60,00", "¥-6000", "¥6000abc"]) {
    assert.equal(executeCode("v21RmbInputNormalize", { user_question: text }).normalized_question, text);
  }
  for (const text of ["RMB 6000 for CAD design", "Please try a laptop under ¥6000", "A laptop with RTX4060 under ¥6000"]) {
    assert.equal(executeCode("v21RmbInputNormalize", { user_question: text }).currency_status, "rmb_or_unspecified", text);
  }
  for (const budget of [false, true, -1, 0, "NaN", "Infinity", "USD 6000", "6,00", {}, [], null]) {
    const result = turn("I need a laptop for gaming.", { extraction: { product_requests_json: JSON.stringify([{ category: "Laptop", budget, main_usage: "gaming" }]) } });
    assert.equal(result.response.clarification_needed, true, JSON.stringify(budget));
    assert.deepEqual(result.queries, []); assert.ok(result.state.missing_fields.includes("budget"));
  }
});

test("invalid explicitly stated RMB amounts cannot reuse a valid old or hallucinated numeric budget", () => {
  for (const currency of ["¥6,00", "RMB 60,00", "¥-6000", "RMB 0", "RMB 6000abc", "RMB 9007199254740992"]) {
    const question = `I need a laptop under ${currency} for gaming.`;
    assert.equal(executeCode("v21RmbInputNormalize", { user_question: question }).currency_status, "invalid_rmb_amount");
    const result = turn(question, { state: initial(),
      extraction: { product_requests_json: '[{"category":"Laptop","budget":6000,"main_usage":"gaming"}]' }, modelResponse: reply([rec("LAP-005")]) });
    assert.equal(result.state.product_requests[0].budget, null); assert.deepEqual(result.queries, []);
    assert.equal(result.response.clarification_needed, true); assert.deepEqual(result.state.last_recommendations, initial().last_recommendations);
  }
});

test("a literal current hard budget overrides an inflated extraction without weakening validation", () => {
  let validation;
  const result = turn("I need a laptop under ¥6,000 for gaming.", { state: initial(),
    extraction: { product_requests_json: '[{"category":"Laptop","budget":9000,"main_usage":"gaming"}]' },
    modelResponse: reply([rec("LAP-006")]), observeValidation: value => { validation = value; } });
  assert.equal(result.state.product_requests[0].budget, 6000);
  assert.equal(validation.validation_ok, false); assert.match(validation.validation_error, /budget/i);
  assert.ok(result.trace.includes(ids.fallback)); assert.ok(!result.trace.includes(ids.writer));
  assert.deepEqual(result.state.last_recommendations, initial().last_recommendations);
});

test("comparison memory still resolves after normalized currency input", () => {
  const first = turn("I need a laptop under ¥6,000 for gaming.", {
    extraction: { product_requests_json: '[{"category":"Laptop","budget":6000,"main_usage":"gaming"}]' }, modelResponse: reply([rec("LAP-005")]) });
  for (const phrase of ["cheaper Laptop", "another Laptop"]) {
    const result = turn(phrase, { state: first.state, extraction: { scope_status: "unrelated" }, modelResponse: reply([]) });
    assert.deepEqual(result.state.product_requests, first.state.product_requests);
    assert.deepEqual(result.state.last_recommendations, first.state.last_recommendations);
    assert.match(result.queries[0], /RMB 6000/); assert.ok(!result.trace.includes("wwmnkseAaXixej19"));
  }
});

test("reported empty/unrelated output reproduces the old branch and is now caught deterministically", () => {
  const state = initial([{ category: "Laptop", budget: 6000, main_usage: "Gaming" }], [rec("LAP-005")]);
  const options = { state, extraction: { product_requests_json: "[]", scope_status: "unrelated" } };
  const previous = turn("I need a laptop under ¥6,000 for gaming.", options, baseline);
  assert.ok(previous.trace.includes("wwmnkseAaXixej19")); assert.deepEqual(previous.state, state);
  const current = turn("I need a laptop under ¥6,000 for gaming.", options);
  assert.ok(current.trace.includes(ids.clarify)); assert.ok(!current.trace.includes("wwmnkseAaXixej19"));
  assert.deepEqual(current.state.last_recommendations, state.last_recommendations);
});

test("variable classifications on repeated identical requests cannot silently enter unrelated", () => {
  let state = initial();
  for (const scope of ["supported", "unrelated", "supported", "help"]) {
    const result = turn("I need a laptop under ¥6,000 for gaming.", { state,
      extraction: { scope_status: scope, product_requests_json: scope === "supported" ? '[{"category":"Laptop","budget":6000,"main_usage":"gaming"}]' : "[]" },
      modelResponse: reply([rec("LAP-005")]) });
    assert.ok(!result.trace.includes("wwmnkseAaXixej19"));
    assert.equal(result.response.clarification_needed, scope !== "supported");
    assert.deepEqual(result.state.last_recommendations, [rec("LAP-005")]);
    state = result.state;
  }
});

test("shortened recommendation instructions render exact request/anchor inputs without replaying other categories", () => {
  const multiple = turn("I need a study laptop under RMB 6000 and a gaming mouse under RMB 300.", {
    extraction: { product_requests_json: JSON.stringify([laptop, mouse]) }, modelResponse: reply([rec("LAP-001"), rec("MOU-002")]) });
  assert.ok(multiple.prompts[ids.recommend].includes(JSON.stringify([laptop, mouse])));
  const comparison = turn("Cheaper mouse", { state: initial(), extraction: { scope_status: "help" }, modelResponse: reply([rec("MOU-004")]) });
  const prompt = comparison.prompts[ids.recommend];
  assert.ok(prompt.includes(JSON.stringify([mouse])));
  assert.ok(prompt.includes(JSON.stringify([rec("MOU-002")])));
  assert.ok(prompt.includes('Follow-up intent:\n"cheaper"'));
  assert.ok(!prompt.includes(rec("LAP-001").recommended_product));
  assert.ok(!prompt.includes("{{$"));
  assert.deepEqual(comparison.state.last_recommendations, [rec("LAP-001"), rec("MOU-004")]);
});
