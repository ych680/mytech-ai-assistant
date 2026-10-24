import test from "node:test";
import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import { createHash } from "node:crypto";
import { Script, createContext, runInContext } from "node:vm";

const root = new URL("../", import.meta.url);
const html = await readFile(new URL("generated/aiep_v2_1_test/site/index.html", root), "utf8");
const local = await readFile(new URL("generated/v2_1_test/index.html", root), "utf8");
const master = JSON.parse(await readFile(new URL("catalogue/mytech_products_v2_1_test.json", root)));
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const normal = value => JSON.parse(JSON.stringify(value));
const item = id => master.products.find(product => product.id === id);
const rec = id => { const p = item(id); return { category: p.category, recommended_product: p.product, price: p.price_rmb, source: p.source, reason: "Matches the reference usage [citation:1]." }; };
const output = (ids = [], clarification_needed = false) => ({ answer: "Reference candidates [citation:1].", recommendations: ids.map(rec), next_step: "Another option?", clarification_needed });
const envelope = (value, finish_reason = "stop") => ({ choices: [{ finish_reason, message: { content: JSON.stringify(value), reasoning_content: "PRIVATE_DIAGNOSTIC" } }] });
const response = (body, status = 200) => ({ ok: status >= 200 && status < 300, status, async json() { return body; } });
const descendants = element => element.children.flatMap(child => [child, ...descendants(child)]);

class Element {
  constructor() {
    this.children = []; this.listeners = {}; this.style = {}; this.value = ""; this._text = "";
    this.classList = { add() {}, toggle() {} }; this.scrollHeight = 180;
  }
  set textContent(value) { this._text = value; this.children = []; }
  get textContent() { return this._text; }
  set innerHTML(_) { throw new Error("Unsafe DOM rendering"); }
  append(...children) { for (const child of children) { child.parent = this; this.children.push(child); } }
  appendChild(child) { this.append(child); }
  replaceChildren() { this.children = []; }
  remove() { if (this.parent) this.parent.children = this.parent.children.filter(child => child !== this); }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  dispatch(name) { return this.listeners[name]?.({ preventDefault() {} }); }
  setAttribute() {}
  focus() {}
}

async function harness(options = {}) {
  const elements = new Map(), calls = [], timers = new Map();
  const hostname = options.hostname ?? "project-demo-00.aidcec-ai-agent.com";
  const protocol = options.protocol ?? "https:";
  const baseURI = `${protocol}//${hostname}/index.html`;
  let serial = 0, timerSerial = 0, reply = () => response(envelope(output([], true)));
  function element(id) { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); }
  for (const match of html.matchAll(/<script type="application\/json" id="([^"]+)">([\s\S]*?)<\/script>/g)) element(match[1]).textContent = match[2];
  const context = createContext({
    document: { baseURI, getElementById: element, querySelectorAll: () => [], createElement: () => new Element() },
    location: { hostname, protocol },
    window: { origin: options.documentOrigin ?? `${protocol}//${hostname}`,
      crypto: { randomUUID: () => "offline-conversation-" + ++serial },
      setTimeout(callback, ms) { if (ms < 60_000) { queueMicrotask(callback); return 0; } const id = ++timerSerial; timers.set(id, callback); return id; },
      clearTimeout(id) { timers.delete(id); },
      get localStorage() { throw new Error("Credential storage forbidden"); } },
    AbortController, requestAnimationFrame: callback => callback(),
    console: new Proxy({}, { get() { return () => { throw new Error("Logging forbidden"); }; } }),
    fetch(url, init) {
      assert.equal(url, "/fastgpt/v1/chat/completions");
      const call = { url, ...init, payload: JSON.parse(init.body) }; calls.push(call);
      const pending = Promise.resolve().then(() => reply(call));
      if (options.ignoreAbort) return pending;
      return new Promise((resolve, reject) => {
        const abort = () => { const error = new Error("mock abort"); error.name = "AbortError"; reject(error); };
        init.signal.addEventListener("abort", abort, { once: true });
        pending.then(resolve, reject).finally(() => init.signal.removeEventListener("abort", abort));
      });
    }
  });
  new Script(script.replace(/^    initialize\(\);$/m, "    globalThis.ready = initialize();")).runInContext(context);
  await context.ready;
  const evaluate = code => runInContext(code, context);
  return { elements, calls, evaluate, timers,
    state: () => normal(evaluate("({ sessionContext, modelHistory, fastGptChatId, requestVersion })")),
    submit(question) { element("messageInput").value = question; return evaluate("sendMessage()"); },
    respond(value, status = 200) { reply = () => response(envelope(value), status); },
    transport(callback) { reply = callback; },
    restart() { element("restartButton").dispatch("click"); },
    expire() { for (const timer of [...timers.values()]) timer(); },
    cards: () => descendants(element("messages")).filter(child => child.className === "product-card"),
    text: () => descendants(element("messages")).map(child => child.textContent).join(" ") };
}

test("isolated single upload embeds the 54-product Master and preserves Editorial Clean CSS and cards", async () => {
  assert.deepEqual(await readdir(new URL("generated/aiep_v2_1_test/site/", root)), ["index.html"]);
  assert.ok(Buffer.byteLength(html) < 2_000_000);
  assert.deepEqual(JSON.parse(html.match(/id="mytech-dataset">([\s\S]*?)<\/script>/)[1]), master);
  assert.equal(master.products.length, 54);
  assert.equal(html.match(/<style>([\s\S]*?)<\/style>/)[1], local.match(/<style>([\s\S]*?)<\/style>/)[1]);
  for (const name of ["addStructuredResponse", "addThinkingMessage", "updateSessionContext", "resetConversation"]) {
    const pattern = new RegExp("    function " + name + "\\([\\s\\S]*?(?=\\n    (?:async )?function )");
    assert.equal(script.match(pattern)[0], local.match(pattern)[0]);
  }
  assert.match(html, /v2\.1 TEST ONLY/);
  assert.doesNotMatch(html, /LOCAL_TEST|\/api\/test\/|localhost|127\.0\.0\.1|apiKey|localStorage|Bearer |authorization|id="key-panel"/);
  const manifest = JSON.parse(await readFile(new URL("generated/aiep_v2_1_test/manifest.json", root)));
  assert.equal(manifest.outputs["site/index.html"], createHash("sha256").update(html).digest("hex"));
  assert.match(manifest.transport.binding_status, /UNVERIFIED/);
});

test("hosted request uses only the proxy, final content and current message; startup makes no request", async () => {
  const app = await harness(); assert.equal(app.calls.length, 0);
  app.respond(output(["MOU-004"])); await app.submit("Gaming mouse under RMB 500");
  const sent = app.calls[0];
  assert.deepEqual(Object.keys(sent.payload).sort(), ["chatId", "detail", "max_tokens", "messages", "stream"]);
  assert.deepEqual(sent.payload.messages, [{ role: "user", content: "Gaming mouse under RMB 500" }]);
  assert.equal(sent.payload.max_tokens, 4096); assert.equal(sent.payload.detail, false); assert.equal(sent.payload.stream, false);
  assert.deepEqual(normal(sent.headers), { "content-type": "application/json" });
  assert.equal(sent.redirect, "error");
  assert.equal(Object.hasOwn(sent, "mode"), false);
  assert.equal(Object.hasOwn(sent, "credentials"), false);
  assert.equal(app.cards().length, 1); assert.doesNotMatch(app.text(), /citation:|PRIVATE_DIAGNOSTIC/);
  assert.match(JSON.stringify(app.state().modelHistory), /citation:1/);
  assert.throws(() => app.evaluate('endpoint("/tokenproxy/v1/chat/completions")'), /AIEP_HOST_REQUIRED/);
});

test("opaque-origin document retains the relative AIEP proxy and legacy CORS-capable fetch defaults", async () => {
  const app = await harness({ hostname: "project-emi-10.aidcec-ai-agent.com", documentOrigin: "null" });
  assert.equal(app.evaluate("window.origin"), "null");
  const legacy = await readFile(new URL("aiep-candidate/site/index.html", root), "utf8");
  const legacyFetch = legacy.match(/const response = await fetch\(endpoint\("\/fastgpt\/v1\/chat\/completions"\), \{([\s\S]*?)\n      \}\);/)[1];
  assert.doesNotMatch(legacyFetch, /\b(?:mode|credentials)\s*:/);
  app.respond(output(["MOU-004"])); await app.submit("Gaming mouse under RMB 300");
  const sent = app.calls[0];
  assert.equal(sent.url, "/fastgpt/v1/chat/completions");
  assert.deepEqual(Object.keys(sent).sort(), ["body", "headers", "method", "payload", "redirect", "signal", "url"]);
  // Request construction is offline. It checks URL resolution and defaults,
  // not a browser CORS engine, preflight response or AIEP authentication.
  const request = new Request(new URL(sent.url, app.evaluate("document.baseURI")), {
    method: sent.method, headers: sent.headers, body: sent.body, signal: sent.signal, redirect: sent.redirect
  });
  assert.equal(request.url, "https://project-emi-10.aidcec-ai-agent.com/fastgpt/v1/chat/completions");
  assert.equal(request.mode, "cors"); assert.equal(request.credentials, "same-origin");
  assert.equal(request.redirect, "error"); assert.equal(request.headers.get("content-type"), "application/json");
  assert.equal(request.headers.has("authorization"), false); assert.equal(request.headers.has("origin"), false);
  assert.equal(JSON.parse(await request.text()).messages.length, 1);
  assert.equal(app.cards().length, 1);
});

test("platform CORS rejection in an opaque-origin context fails safely without retries or transport fallback", async () => {
  const app = await harness({ hostname: "project-emi-10.aidcec-ai-agent.com", documentOrigin: "null" });
  app.respond(output(["MOU-002"])); await app.submit("Gaming mouse under RMB 500");
  const before = app.state();
  app.transport(() => { throw new TypeError("Failed to fetch: private platform diagnostic"); });
  await app.submit("Cheaper mouse");
  assert.equal(app.calls.length, 2); assert.ok(app.calls.every(call => call.url === "/fastgpt/v1/chat/completions"));
  assert.equal(app.cards().length, 1); assert.equal(app.elements.get("sendButton").disabled, false);
  assert.deepEqual(app.state().modelHistory, before.modelHistory);
  assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, before.sessionContext.lastRecommendationsByCategory);
  assert.equal(app.state().fastGptChatId, before.fastGptChatId);
  assert.match(app.text(), /Cannot reach the AI service/); assert.doesNotMatch(app.text(), /private platform diagnostic/);
});

for (const [hostname, protocol, hosted] of [
  ["project-cmi-01.aidcec-ai-agent.com", "https:", true], ["PROJECT-EMI-99.AIDCEC-AI-AGENT.COM", "https:", true],
  ["project-demo-00.aidcec-ai-agent.com", "http:", false], ["localhost", "http:", false], ["", "file:", false],
  ["project-demo-00.aidcec-ai-agent.com.evil.test", "https:", false], ["project-cmi-001.aidcec-ai-agent.com", "https:", false]
]) test(`AIEP origin restriction ${protocol}//${hostname}`, async () => {
  const app = await harness({ hostname, protocol }); assert.equal(app.evaluate("HOSTED"), hosted);
  assert.equal(app.elements.get("sendButton").disabled, !hosted);
  if (!hosted) { await app.submit("Hello"); assert.equal(app.calls.length, 0); }
});

test("all 54 exact catalogue identities validate with known compatible usages and complete budgets", async () => {
  const app = await harness();
  for (const p of master.products) {
    const good = { answer: "Reference candidate.", recommendations: [{ category: p.category, recommended_product: p.product, price: p.price_rmb, source: p.source, reason: "Reference match." }], next_step: "", clarification_needed: false };
    const usage = app.evaluate(`Object.keys(TEST_USAGE_POLICY).find(usage => usageIsCompatible(productByName.get(${JSON.stringify(p.product)}), usage))`);
    assert.ok(usage, p.id);
    const guard = { activeCategories: [p.category], targetCategories: [p.category], budgetsByCategory: { [p.category]: p.price_rmb }, usagesByCategory: { [p.category]: usage }, previousRecommendationsByCategory: {}, comparison: null };
    assert.equal(app.evaluate(`validateStructuredOutput(${JSON.stringify(good)}, ${JSON.stringify(guard)}).valid`), true, p.id);
  }
});

test("strict product facts, types, budgets, usage, scope and batches reject atomically", async () => {
  for (const change of [r => { r.price++; }, r => { r.price = String(r.price); }, r => { r.source = "wrong"; },
    r => { delete r.source; }, r => { r.source = null; }, r => { r.category = "Laptop"; },
    r => { r.recommended_product = "Invented mouse"; }, r => { r.extra = true; }, r => { r.reason = ""; }]) {
    const app = await harness(), bad = output(["LAP-005", "MOU-004"]); change(bad.recommendations[1]);
    app.respond(bad); await app.submit("Study laptop under RMB 6000 and gaming mouse under RMB 300");
    assert.equal(app.cards().length, 0); assert.equal(app.state().modelHistory.length, 0); assert.match(app.text(), /couldn't safely validate/i);
  }
  for (const [question, ids] of [
    ["Gaming mouse under RMB 300", ["MOU-001"]], ["Gaming mouse under RMB 100", ["MOU-004"]],
    ["Mouse under RMB 300", ["MOU-004"]], ["Gaming mouse", ["MOU-004"]],
    ["Gaming mouse under RMB 300", ["MOU-004", "MOU-002"]], ["Gaming mouse under RMB 300", ["LAP-005"]]
  ]) {
    const app = await harness(); app.respond(output(ids)); await app.submit(question); assert.equal(app.cards().length, 0, question);
  }
  const app = await harness();
  const guard = app.evaluate('updateSessionContext("Gaming mouse under RMB 300")');
  guard.usagesByCategory.Mouse = "Gaming and quantum analysis";
  assert.equal(app.evaluate(`validateStructuredOutput(${JSON.stringify(output(["MOU-004"]))}, ${JSON.stringify(guard)}).valid`), false);
  app.respond({ ...output(["MOU-004"]), extra: true }); await app.submit("Gaming mouse under RMB 300"); assert.equal(app.cards().length, 0);
});

async function seed() {
  const app = await harness(); app.respond(output(["LAP-005", "MOU-002"]));
  await app.submit("Study laptop under RMB 6000 and gaming mouse under RMB 500"); assert.equal(app.cards().length, 2); return app;
}

test("targeted cheaper/another comparisons retain both requests, anchors and chat ID", async () => {
  const app = await seed(), id = app.state().fastGptChatId;
  app.respond(output(["MOU-004"])); await app.submit("Cheaper mouse"); assert.equal(app.cards().length, 3);
  assert.equal(app.state().sessionContext.requirementsByCategory.Laptop.budget, 6000);
  assert.equal(app.state().sessionContext.requirementsByCategory.Mouse.usage, "Gaming");
  app.respond(output(["MOU-004"])); await app.submit("Another mouse"); assert.equal(app.cards().length, 3);
  app.respond(output(["MOU-002"])); await app.submit("Another mouse"); assert.equal(app.cards().length, 4);
  app.respond(output(["LAP-005"])); await app.submit("Cheaper laptop"); assert.equal(app.cards().length, 4);
  assert.equal(app.state().fastGptChatId, id);
  assert.ok(app.calls.every(call => call.payload.messages.length === 1));
});

test("ambiguous follow-up targets, no-result and cancellation preserve validated anchors", async () => {
  const app = await seed(), before = app.state().sessionContext.lastRecommendationsByCategory;
  app.respond(output([], true)); await app.submit("Anything cheaper?");
  assert.equal(app.state().sessionContext.pendingComparison, "cheaper");
  app.respond(output(["MOU-004"])); await app.submit("Mouse"); assert.equal(app.cards().length, 3);
  app.respond(output([])); await app.submit("Cheaper mouse");
  assert.equal(app.state().sessionContext.lastRecommendationsByCategory.Mouse.product, item("MOU-004").product);
  app.respond(output([], true)); await app.submit("Anything cheaper?"); await app.submit("Cancel that comparison");
  assert.equal(app.state().sessionContext.pendingComparison, null);
  assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory.Laptop, before.Laptop);
  app.respond(output(["MOU-002"], true)); await app.submit("Better mouse"); assert.equal(app.cards().length, 3);
});

for (const status of [401, 402, 403, 429, 500, 502, 504]) test(`safe HTTP ${status} preserves cards/history and recovers`, async () => {
  const app = await seed(), before = app.state();
  app.transport(() => response({ error: { message: "DO_NOT_DISPLAY_UPSTREAM" } }, status));
  await app.submit("Cheaper mouse"); assert.equal(app.cards().length, 2);
  assert.deepEqual(app.state().modelHistory, before.modelHistory); assert.doesNotMatch(app.text(), /DO_NOT_DISPLAY_UPSTREAM/);
  assert.equal(app.elements.get("sendButton").disabled, false);
  app.respond(output(["MOU-004"])); await app.submit("Cheaper mouse"); assert.equal(app.cards().length, 3);
});

test("malformed, truncated, non-JSON HTTP errors and network failures fail safely without automatic retry", async () => {
  const bad = [
    () => response({ choices: [{ message: { content: "prose {not JSON}" } }] }),
    () => response(envelope(output(["MOU-004"]), "length")),
    () => ({ ok: false, status: 502, json: async () => { throw new Error("private upstream"); } }),
    () => { throw new Error("private upstream"); },
    () => response({ choices: [{ message: { content: JSON.stringify({ ...output([]), clarification_needed: "false" }) } }] })
  ];
  for (const reply of bad) {
    const app = await harness(); app.transport(reply); await app.submit("Gaming mouse under RMB 300");
    assert.equal(app.cards().length, 0); assert.equal(app.calls.length, 1); assert.doesNotMatch(app.text(), /private upstream/);
    assert.equal(app.state().modelHistory.length, 0); assert.equal(app.elements.get("sendButton").disabled, false);
  }
});

test("deadline aborts stalled proxy, preserves anchors and exposes edit recovery", async () => {
  const app = await seed(), before = app.state(); let entered;
  const started = new Promise(resolve => { entered = resolve; });
  app.transport(() => { entered(); return new Promise(() => {}); });
  const pending = app.submit("Cheaper mouse"); await started; app.expire(); await pending;
  assert.equal(app.evaluate("CONFIG.requestTimeoutMs"), 120000);
  assert.equal(app.calls.at(-1).signal.aborted, true); assert.match(app.text(), /timed out/i);
  assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, before.sessionContext.lastRecommendationsByCategory);
  assert.deepEqual(app.state().modelHistory, before.modelHistory);
  const recovery = descendants(app.elements.get("messages")).find(child => child.className === "recovery-button");
  recovery.dispatch("click"); assert.equal(app.elements.get("messageInput").value, "Cheaper mouse");
});

for (const lateFailure of [false, true]) test(`Restart discards late ${lateFailure ? "failure" : "success"}, clears state and rotates ID`, async () => {
  const app = await harness({ ignoreAbort: true }); let release, reject, entered;
  const started = new Promise(resolve => { entered = resolve; });
  app.transport(() => { entered(); return new Promise((resolve, fail) => { release = resolve; reject = fail; }); });
  const id = app.state().fastGptChatId, pending = app.submit("Gaming mouse under RMB 300"); await started;
  app.restart(); assert.equal(app.calls[0].signal.aborted, true);
  if (lateFailure) reject(new Error("private stale failure")); else release(response(envelope(output(["MOU-004"]))));
  await pending; assert.notEqual(app.state().fastGptChatId, id); assert.equal(app.cards().length, 0);
  assert.deepEqual(app.state().modelHistory, []); assert.deepEqual(app.state().sessionContext.activeCategories, []);
  assert.doesNotMatch(app.text(), /private stale failure/); assert.equal(app.elements.get("sendButton").disabled, false);
});

test("history is bounded and new browser sessions have independent state", async () => {
  const app = await harness(); for (let i = 0; i < 12; i++) await app.submit("Hello " + i);
  assert.equal(app.state().modelHistory.length, 16);
  const other = await harness(); assert.deepEqual(other.state().modelHistory, []); assert.deepEqual(other.state().sessionContext.activeCategories, []);
});
