import test from "node:test";
import assert from "node:assert/strict";
import { readFile, mkdtemp, writeFile, rm } from "node:fs/promises";
import { execFileSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { createContext, Script, runInContext } from "node:vm";
import { createTestAdapter } from "../mytech_v2_1_test_adapter.mjs";

const root = fileURLToPath(new URL("../", import.meta.url));
const generated = join(root, "generated/v2_1_test");
const master = JSON.parse(await readFile(join(root, "catalogue/mytech_products_v2_1_test.json"), "utf8"));
const html = await readFile(join(generated, "index.html"), "utf8");
const graph = JSON.parse(await readFile(join(generated, "mytech-fastgpt-workflow-v2_1-TEST.json"), "utf8"));
const code = graph.nodes.find(node => node.nodeId === "fakNM8mmlYmewx67").inputs.find(field => field.key === "code").value;
const workflowScript = new Script(code + "\nmain(input);");
const adapter = await createTestAdapter();
const product = id => master.products.find(item => item.id === id);
const rec = item => ({ category: item.category, recommended_product: item.product,
  price: item.price_rmb, source: item.source, reason: "Matches the TEST catalogue usage." });
const output = recommendations => ({ answer: "TEST reference recommendations.", recommendations,
  next_step: "Would you like another option?", clarification_needed: false });
const request = (item, usage = item.main_usage[0], budget = item.price_rmb) => ({ category: item.category, budget, main_usage: usage });
const input = (item, options = {}) => ({ raw_json: JSON.stringify(output([rec(item)])),
  active_requests: [request(item)], previous_recommendations: [], follow_up_intent: "none", ...options });
function workflowValidate(value) {
  return JSON.parse(JSON.stringify(workflowScript.runInContext(createContext({ input: structuredClone(value) }), { timeout: 1000 })));
}

test("working Current Query Builder code preserves its query content, budgets, usage and comparison history", async () => {
  const original = JSON.parse((await readFile(join(root, "tools/templates/mytech_current_working_portable.json"), "utf8")).replace(/^\uFEFF/, ""));
  function build(workflow, input) {
    const code = workflow.nodes.find(node => node.nodeId === "sxwN5Fd17Tc8leTf").inputs.find(field => field.key === "code").value;
    const context = createContext({ input: structuredClone(input) });
    const before = structuredClone(context.input);
    const result = new Script(code + "\nmain(input);").runInContext(context, { timeout: 1000 });
    assert.deepEqual(context.input, before);
    return JSON.parse(JSON.stringify(result));
  }
  const laptop = product("LAP-001"), mouse = product("MOU-004");
  const cases = [
    { user_question: "Fallback question", active_requests: [], previous_recommendations: [], follow_up_intent: "none" },
    { user_question: "Study laptop", active_requests: [request(laptop, "study", 6000)], previous_recommendations: [], follow_up_intent: "none" },
    { user_question: "Study laptop and gaming mouse", active_requests: [request(laptop, "study", 6000), request(mouse, "gaming", 300)], previous_recommendations: [], follow_up_intent: "none" },
    ...["cheaper", "more_expensive", "alternative"].map(follow_up_intent => ({
      user_question: "Another Mouse", active_requests: [request(mouse, "gaming", 300)],
      previous_recommendations: [rec(laptop), rec(product("MOU-002"))], follow_up_intent
    }))
  ];
  for (const input of cases) {
    const previous = build(original, input), current = build(graph, input);
    assert.equal(typeof current.retrieval_query, "string");
    assert.equal(current.retrieval_query, previous.retrieval_query);
    assert.deepEqual(current.comparison_history, previous.comparison_history);
    assert.deepEqual(Object.keys(current).sort(), ["comparison_history", "retrieval_query"]);
  }
});

class Element {
  constructor() {
    this.children = []; this.listeners = {}; this.style = {}; this.value = ""; this._text = "";
    this.classList = { add() {}, toggle() {} }; this.scrollHeight = 180;
  }
  set textContent(value) { this._text = value; this.children = []; }
  get textContent() { return this._text; }
  append(...children) { for (const child of children) { child.parent = this; this.children.push(child); } }
  appendChild(child) { this.append(child); }
  replaceChildren() { this.children = []; }
  remove() { this.parent.children = this.parent.children.filter(child => child !== this); }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  setAttribute() {}
  focus() {}
}
const descendants = element => element.children.flatMap(child => [child, ...descendants(child)]);
async function frontend(source = html, options = {}) {
  const elements = new Map();
  function element(id) { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); }
  for (const match of source.matchAll(/<script type="application\/json" id="([^"]+)">([\s\S]*?)<\/script>/g)) element(match[1]).textContent = match[2];
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1];
  let response;
  const calls = [], timings = [];
  let failNext = false;
  const transport = options.transport;
  let serial = 0;
  const context = createContext({
    document: { getElementById: element, querySelectorAll: () => [], createElement: () => new Element() },
    location: { hostname: options.local ? "127.0.0.1" : "project-demo-00.aidcec-ai-agent.com", protocol: options.local ? "http:" : "https:", search: "" },
    window: { crypto: { randomUUID: () => "offline-test-" + ++serial },
      setTimeout(callback, ms) { if (ms < 60_000) queueMicrotask(callback); return 1; }, clearTimeout() {},
      dispatchEvent(event) { timings.push(event.detail); },
      get localStorage() { throw new Error("No storage access allowed"); } },
    CustomEvent: class { constructor(name, options) { this.type = name; this.detail = options.detail; } },
    AbortController, requestAnimationFrame: callback => callback(),
    fetch(url, options) {
      calls.push({ url, options });
      // Mock only: never delegates to native fetch or a live server.
      if (url === "/api/test/config") return Promise.resolve({ ok: true, json: async () => ({
        catalogueVersion: "2.1-TEST", productCount: master.products.length, requestTimeoutMs: 120000, configured: optionsConfigured
      }) });
      if (failNext) { failNext = false; return Promise.reject(new Error("offline simulated transport error")); }
      if (transport) return transport(url, options);
      return Promise.resolve({ ok: true, json: async () => ({ choices: [{ message: { content: JSON.stringify(response) } }] }) });
    }
  });
  const optionsConfigured = options.configured !== false;
  new Script(script.replace(/^    initialize\(\);$/m, "    globalThis.ready = initialize();")).runInContext(context);
  await context.ready;
  const evaluate = text => runInContext(text, context);
  return { evaluate, elements, calls, timings, failNext() { failNext = true; },
    async submit(question, reply) { response = reply; element("messageInput").value = question; await evaluate("sendMessage()"); },
    cards: () => descendants(element("messages")).filter(item => item.className === "product-card"),
    text: () => descendants(element("messages")).map(item => item.textContent).join(" ") };
}

test("local TEST frontend configures its separate route and renders only validated display text", async () => {
  const app = await frontend(html, { local: true });
  assert.equal(app.calls.length, 1); assert.equal(app.calls[0].url, "/api/test/config");
  assert.equal(app.evaluate("CONFIG.requestTimeoutMs"), 120000);
  assert.equal(app.evaluate("testDeadlineMs()"), 125000);
  assert.equal(app.evaluate("CONFIG.maxTokens"), 4096);
  const response = output([{ ...rec(product("MOU-004")), reason: "Gaming [citation:1]." }]);
  response.answer = "Reference [citation:1].";
  await app.submit("Gaming mouse under RMB 300", response);
  assert.equal(app.cards().length, 1); assert.ok(!app.text().includes("citation:"));
  assert.match(app.evaluate("JSON.stringify(modelHistory)"), /citation:1/);
  assert.equal(app.calls[1].url, "/api/test/mytech");
  assert.ok(JSON.parse(app.calls[1].options.body).validationContext);
  assert.ok(!("Authorization" in app.calls[1].options.headers));
  assert.equal(app.timings[0].status, "validated");
  assert.deepEqual(Object.keys(app.timings[0]).sort(), ["durationMs", "phase", "status"]);
});

test("unconfigured local TEST host disables sends and never falls back to school or stable routing", async () => {
  const app = await frontend(html, { local: true, configured: false });
  assert.equal(app.evaluate("testConnectionAvailable()"), false);
  await app.submit("Gaming mouse under RMB 300", output([rec(product("MOU-004"))]));
  assert.equal(app.calls.length, 1); assert.equal(app.cards().length, 0);
  assert.equal(app.evaluate("apiKey"), "");
});

test("TEST frontend failures preserve memory and allow recovery; Restart rotates chat and clears context", async () => {
  const app = await frontend(html, { local: true });
  await app.submit("Gaming mouse under RMB 500", output([rec(product("MOU-002"))]));
  const chat = app.evaluate("fastGptChatId");
  const memory = app.evaluate("JSON.stringify(sessionContext.lastRecommendationsByCategory)");
  app.failNext(); await app.submit("Cheaper mouse", output([rec(product("MOU-004"))]));
  assert.equal(app.evaluate("JSON.stringify(sessionContext.lastRecommendationsByCategory)"), memory);
  assert.equal(app.evaluate("isGenerating"), false);
  assert.equal(app.evaluate("activeRecovery !== null"), true);
  await app.submit("Cheaper mouse", output([rec(product("MOU-004"))]));
  assert.notEqual(app.evaluate("JSON.stringify(sessionContext.lastRecommendationsByCategory)"), memory);
  app.evaluate("resetConversation()");
  assert.notEqual(app.evaluate("fastGptChatId"), chat);
  assert.equal(app.evaluate("modelHistory.length"), 0);
  assert.equal(app.evaluate("JSON.stringify(sessionContext.lastRecommendationsByCategory)"), "{}");
  assert.equal(app.cards().length, 0);
});

test("TEST frontend rejects missing/unknown usage, missing source and citation-obscured claims", async () => {
  const app = await frontend();
  const item = product("MOU-004");
  const guard = { activeCategories: [item.category], targetCategories: [item.category], budgetsByCategory: { Mouse: 500 },
    usagesByCategory: { Mouse: "gaming" }, previousRecommendationsByCategory: {} };
  for (const usage of ["", "quantum analysis", "gaming and quantum analysis"]) {
    const badGuard = { ...guard, usagesByCategory: { Mouse: usage } };
    assert.equal(app.evaluate(`validateStructuredOutput(${JSON.stringify(output([rec(item)]))}, ${JSON.stringify(badGuard)}).valid`), false);
  }
  const missing = rec(item); delete missing.source;
  await app.submit("Gaming mouse under RMB 500", output([missing]));
  assert.equal(app.cards().length, 0);
  await app.submit("Gaming mouse under RMB 500", { ...output([rec(item)]), answer: "live [citation:1]pricing" });
  assert.equal(app.cards().length, 0);
  assert.equal(app.evaluate("modelHistory.length"), 0);
});

test("generated TEST Restart suppresses late replies even if a transport ignores abort", async () => {
  let release, signal;
  const app = await frontend(html, { local: true, transport: (_url, options) => {
    signal = options.signal; return new Promise(resolve => { release = resolve; });
  } });
  const pending = app.submit("Gaming mouse under RMB 300", output([rec(product("MOU-004"))]));
  const chat = app.evaluate("fastGptChatId");
  assert.equal(app.evaluate("isGenerating"), true);
  app.evaluate("resetConversation()"); assert.equal(signal.aborted, true);
  release({ ok: true, json: async () => ({ choices: [{ message: { content: JSON.stringify(output([rec(product("MOU-004"))])) } }] }) });
  await pending;
  assert.equal(app.cards().length, 0); assert.notEqual(app.evaluate("fastGptChatId"), chat);
  assert.equal(app.evaluate("modelHistory.length"), 0); assert.equal(app.evaluate("isGenerating"), false);
  assert.equal(app.timings[0].status, "cancelled");
});

test("TEST page keeps Editorial Clean CSS and validates configurable browser deadlines", async () => {
  const stable = await readFile(join(root, "aiep-candidate/site/index.html"), "utf8");
  assert.equal(html.match(/<style>([\s\S]*?)<\/style>/)[1], stable.match(/<style>([\s\S]*?)<\/style>/)[1]);
  const app = await frontend();
  for (const [value, expected] of [[180000, 180000], [4999, 120000], [300001, 120000], ["90000", 90000], ["invalid", 120000]]) {
    assert.equal(app.evaluate(`window.MYTECH_TEST_CONFIG = {requestTimeoutMs:${JSON.stringify(value)}}; testBrowserTimeout()`), expected);
  }
});

test("Node catalogue and initialized AIEP preserve all 54 Master Dataset records", async () => {
  assert.deepEqual(adapter.catalogue, master);
  const app = await frontend();
  assert.equal(app.evaluate("datasetReady"), true);
  assert.deepEqual(JSON.parse(app.evaluate("JSON.stringify(productDataset)")), master);
  assert.equal(app.calls.length, 0);
  assert.match(html, /v2\.1 TEST ONLY/);
  assert.match(html, /KEY_STORE = "mytech-v21-test-key"/);
});

test("every TEST product passes real workflow catalogue and Node adapter validation", () => {
  for (const item of master.products) {
    const value = input(item);
    assert.equal(workflowValidate(value).validation_ok, true, item.id);
    const before = structuredClone(value);
    const result = adapter.validate(value);
    assert.equal(result.valid, true, item.id + JSON.stringify(result.errors));
    assert.deepEqual(value, before);
  }
});

test("every TEST product renders its exact identity, price, category, source and specs", async () => {
  const app = await frontend();
  for (const item of master.products) {
    app.evaluate("resetConversation()");
    // Direct guard with a recognized compatible usage exercises all products
    // independently of the natural-language parser's intentionally limited lexicon.
    const guard = { activeCategories: [item.category], targetCategories: [item.category],
      budgetsByCategory: { [item.category]: item.price_rmb }, usagesByCategory: { [item.category]: item.main_usage[0] }, previousRecommendationsByCategory: {} };
    const validation = app.evaluate(`validateStructuredOutput(${JSON.stringify(output([rec(item)]))}, ${JSON.stringify(guard)})`);
    assert.equal(validation.valid, true, item.id);
    app.evaluate(`addStructuredResponse(${JSON.stringify(output([rec(item)]))})`);
    const card = app.cards()[0];
    const fields = Object.fromEntries(descendants(card).map(child => [child.className, child.textContent]));
    assert.equal(fields["product-name"], item.product);
    assert.equal(fields["product-meta"], `${item.category} · ${item.tier} · Reference price`);
    assert.equal(fields["product-price"], `¥${new Intl.NumberFormat("en-US").format(item.price_rmb)}`);
    assert.equal(fields["product-source"], `Source: ${item.source}`);
    assert.equal(fields["product-specs"], item.key_features.join(" · "));
  }
  assert.equal(app.calls.length, 0);
});

test("initial recommendations enforce Gaming usage in Node and real AIEP submission", async () => {
  const office = product("MOU-001"), gaming = product("MOU-004");
  for (const item of [office, gaming]) {
    assert.equal(adapter.validate(input(item, { active_requests: [request(item, "gaming", 300)] })).valid, item === gaming);
    const app = await frontend();
    await app.submit("I need a gaming mouse under RMB 300.", output([rec(item)]));
    assert.equal(app.cards().length, item === gaming ? 1 : 0);
    if (item === office) assert.match(app.text(), /couldn't safely validate/i);
  }
});

test("FastGPT TEST export rejects initial usage mismatches before returning or storing recommendations", () => {
  const value = input(product("LAP-001"), { active_requests: [request(product("LAP-001"), "gaming", 6000)] });
  const result = workflowValidate(value);
  assert.equal(result.validation_ok, false);
  assert.deepEqual(result.recommendations, []);
  assert.deepEqual(result.recommendations_to_store, []);
  assert.equal(adapter.validate(value).valid, false);
  const valid = input(product("LAP-005"), { active_requests: [request(product("LAP-005"), "gaming", 6000)] });
  assert.equal(workflowValidate(valid).validation_ok, true);
});

test("recognized usage aliases and compound requirements remain checked", () => {
  for (const usage of ["Gaming", "play games", "playing games", "video games", "competitive gaming", "study and gaming"]) {
    const value = input(product("MOU-001"), { active_requests: [request(product("MOU-001"), usage, 300)] });
    assert.equal(adapter.validate(value).valid, false, usage);
  }
});

for (const [name, change] of [
  ["unknown product or ID in name", rec => { rec.recommended_product = "MOU-999"; }],
  ["incorrect price", rec => { rec.price += 1; }],
  ["string price", rec => { rec.price = String(rec.price); }],
  ["incorrect category", rec => { rec.category = "Laptop"; }],
  ["incorrect source", rec => { rec.source = "invented"; }],
  ["missing source", rec => { delete rec.source; }],
  ["missing name", rec => { delete rec.recommended_product; }],
  ["missing reason", rec => { delete rec.reason; }],
  ["unsupported product_id", rec => { rec.product_id = "MOU-004"; }]
]) test(`TEST adapter rejects ${name}`, () => {
  const value = input(product("MOU-004"));
  const response = JSON.parse(value.raw_json); change(response.recommendations[0]);
  value.raw_json = JSON.stringify(response);
  assert.equal(adapter.validate(value).valid, false);
});

test("workflow, Node and AIEP enforce exact hard-budget boundaries", async () => {
  const item = product("MOU-004");
  for (const budget of [item.price_rmb - 1, item.price_rmb, item.price_rmb + 1]) {
    const value = input(item, { active_requests: [request(item, "gaming", budget)] });
    assert.equal(workflowValidate(value).validation_ok, budget >= item.price_rmb);
    assert.equal(adapter.validate(value).valid, budget >= item.price_rmb);
    const app = await frontend();
    await app.submit(`I need a gaming mouse under RMB ${budget}.`, output([rec(item)]));
    assert.equal(app.cards().length, budget >= item.price_rmb ? 1 : 0);
  }
});

test("missing request facts, invalid output shapes and duplicate categories fail closed", () => {
  for (const raw_json of ["not JSON", "null", "[]", '{}', JSON.stringify({ ...output([]), recommendations: {} })]) {
    assert.equal(adapter.validate(input(product("MOU-004"), { raw_json })).valid, false);
  }
  for (const field of ["budget", "category", "main_usage"]) {
    const value = input(product("MOU-004")); delete value.active_requests[0][field];
    assert.equal(adapter.validate(value).valid, false);
  }
  const item = product("MOU-004");
  assert.equal(adapter.validate(input(item, { raw_json: JSON.stringify(output([rec(item), rec(item)])) })).valid, false);
});

test("comparison validation preserves anchors, direction, hard budgets, category and usage", () => {
  const gaming = product("MOU-004"), anchor = product("MOU-002");
  const value = input(gaming, { active_requests: [request(gaming, "gaming", 300)],
    previous_recommendations: [rec(product("LAP-001")), rec(anchor)], follow_up_intent: "cheaper" });
  const result = adapter.validate(value);
  assert.equal(result.valid, true);
  assert.deepEqual(result.result.recommendations_to_store, [rec(product("LAP-001")), rec(gaming)]);
  for (const item of [anchor, product("MOU-001"), product("LAP-005")]) {
    const invalid = { ...value, raw_json: JSON.stringify(output([rec(item)])) };
    assert.equal(adapter.validate(invalid).valid, false);
  }
  for (const previous of [[], [rec(anchor), rec(anchor)], [{ ...rec(anchor), price: 1 }]]) {
    assert.equal(adapter.validate({ ...value, previous_recommendations: previous }).valid, false);
  }
  assert.equal(adapter.validate({ ...value, follow_up_intent: "more_expensive" }).valid, false);
  assert.equal(adapter.validate({ ...value, follow_up_intent: "alternative" }).valid, true);
  assert.equal(adapter.validate({ ...value, raw_json: JSON.stringify(output([rec(anchor)])), follow_up_intent: "alternative" }).valid, false);
  const empty = adapter.validate({ ...value, raw_json: JSON.stringify(output([])) });
  assert.equal(empty.valid, true);
  assert.deepEqual(empty.result.recommendations_to_store, value.previous_recommendations);
});

test("TEST frontend dataset validation rejects missing fields, IDs, duplicates and invalid prices", async () => {
  const app = await frontend();
  for (const change of [
    d => { d.products[3].id = "MOU-004"; }, d => { d.products[3].id = "LAP-0000"; },
    d => { d.products[3].product = d.products[0].product; }, d => { d.products[3].price_rmb = 0; },
    d => { delete d.products[3].source; }, d => { delete d.products[3].review_status; },
    d => { d.products[3].review_status = "CURRENT"; }, d => { d.version = "1.0"; }
  ]) {
    const data = structuredClone(master); change(data);
    assert.throws(() => app.evaluate(`validateProductDataset(${JSON.stringify(data)})`));
  }
});

test("55th product regenerates and works in actual workflow, Node adapter and AIEP", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "mytech-v21-"));
  try {
    const data = structuredClone(master);
    const added = { ...structuredClone(product("MOU-004")), id: "MOU-007", product: "55th TEST Gaming Mouse", price_rmb: 123 };
    data.products.push(added);
    const dataset = join(temporary, "master.json");
    await writeFile(dataset, JSON.stringify(data));
    execFileSync(process.platform === "win32" ? "python" : "python3", ["-B", join(root, "tools/sync_catalogue.py"), "--dataset", dataset, "--output-root", temporary]);
    const directory = join(temporary, "generated/v2_1_test");
    const expanded = await createTestAdapter(directory);
    assert.equal(expanded.catalogue.products.length, 55);
    const result = expanded.validate(input(added, { active_requests: [request(added, "gaming", 123)] }));
    assert.equal(result.valid, true, JSON.stringify(result.errors));
    assert.equal(result.result.recommendations[0].recommended_product, added.product);
    const app = await frontend(await readFile(join(directory, "index.html"), "utf8"));
    assert.equal(app.evaluate("productDataset.products.length"), 55);
    await app.submit("I need a gaming mouse under RMB 123.", output([rec(added)]));
    assert.equal(app.cards().length, 1);
    assert.ok(app.text().includes(added.product));
  } finally { await rm(temporary, { recursive: true, force: true }); }
});
