import test from "node:test";
import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import { Script, createContext, runInContext } from "node:vm";

const html = await readFile(new URL("../aiep-candidate/site/index.html", import.meta.url), "utf8");
const original = await readFile(new URL("../MyTech_Chatbot_v2.html", import.meta.url), "utf8");
const dataset = JSON.parse(await readFile(new URL("../mytech_v1_product_dataset.json", import.meta.url), "utf8"));
const referencePrompt = await readFile(new URL("../mytech_v1_system_prompt.txt", import.meta.url), "utf8");
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const fakeKey = "openapi-" + "test-only-not-a-credential";
const normal = (value) => JSON.parse(JSON.stringify(value));
const descendants = (element) => element.children.flatMap((child) => [child, ...descendants(child)]);
const emptyOutput = () => ({ answer: "Tell me your requirements.", recommendations: [], next_step: "", clarification_needed: true });
const envelope = (output) => ({ choices: [{ message: { content: JSON.stringify(output) } }] });
const response = (body, status = 200) => ({ ok: status >= 200 && status < 300, status, async json() { return body; } });

// Minimal DOM, fake storage, manual deadline and mocked fetch. No server or real key.
class Element {
  constructor(tag = "div") {
    this.tagName = tag; this.children = []; this.listeners = {}; this.value = "";
    this.hidden = false; this.checked = false; this.disabled = false; this.style = {};
    this.dataset = {}; this.scrollHeight = 180; this.classList = { add() {}, toggle() {} };
    this._text = "";
  }
  set textContent(text) { this._text = text; this.children = []; }
  get textContent() { return this._text; }
  set innerHTML(_) { throw new Error("Unsafe rendering forbidden"); }
  append(...children) { children.forEach((child) => { child.parent = this; this.children.push(child); }); }
  appendChild(child) { this.append(child); }
  replaceChildren() { this.children = []; }
  remove() { if (this.parent) this.parent.children = this.parent.children.filter((child) => child !== this); }
  setAttribute() {}
  addEventListener(type, listener) { this.listeners[type] = listener; }
  dispatch(type) { return this.listeners[type]?.({ preventDefault() {} }); }
  focus() {}
}

async function harness(options = {}) {
  const elements = new Map();
  for (const match of html.matchAll(/<([a-z]+)\b[^>]*\bid="([^"]+)"[^>]*>/gi)) {
    const element = new Element(match[1]);
    element.hidden = /\bhidden\b/.test(match[0]); elements.set(match[2], element);
  }
  for (const match of html.matchAll(/<script type="application\/json" id="([^"]+)">([\s\S]*?)<\/script>/g)) {
    elements.get(match[1]).textContent = match[2];
  }
  const prompts = [...html.matchAll(/data-prompt="([^"]+)"/g)].map((match) => {
    const button = new Element("button"); button.dataset.prompt = match[1]; return button;
  });
  const requests = [], storageCalls = [], timers = new Map();
  let serial = 0, timerSerial = 0;
  let reply = () => response(envelope(emptyOutput()));
  const saved = new Map(options.saved ? [["tokenproxy-key", options.saved]] : []);
  const store = Object.fromEntries(["getItem", "setItem", "removeItem"].map((method) => [method, (...args) => {
    storageCalls.push(method);
    if (options.storageFailure === method) throw new Error("Storage denied");
    if (method === "getItem") return saved.get(args[0]) || null;
    if (method === "setItem") saved.set(...args);
    if (method === "removeItem") saved.delete(args[0]);
  }]));
  const window = {
    crypto: { randomUUID: () => "test-conversation-" + (++serial) },
    setTimeout(callback, ms) {
      if (ms < 60_000) { queueMicrotask(callback); return 0; }
      const id = ++timerSerial; timers.set(id, callback); return id;
    },
    clearTimeout(id) { timers.delete(id); }
  };
  Object.defineProperty(window, "localStorage", { get() {
    storageCalls.push("access");
    if (options.storageFailure === "access") throw new Error("Sandbox storage denied");
    return store;
  } });
  const context = createContext({
    document: { getElementById: (id) => elements.get(id), querySelectorAll: () => prompts, createElement: (tag) => new Element(tag) },
    location: { hostname: options.hostname ?? "project-cmi-01.aidcec-ai-agent.com", protocol: options.protocol ?? "https:" },
    window, AbortController, requestAnimationFrame: (callback) => callback(),
    console: new Proxy({}, { get() { return () => { throw new Error("Credential logging forbidden"); }; } }),
    fetch(url, init) {
      requests.push({ url, ...init, payload: JSON.parse(init.body) });
      const pending = Promise.resolve(reply(requests.at(-1)));
      if (options.ignoreAbort) return pending;
      return new Promise((resolve, reject) => {
        const abort = () => { const error = new Error("Aborted"); error.name = "AbortError"; reject(error); };
        init.signal.addEventListener("abort", abort, { once: true });
        pending.then(resolve, reject).finally(() => init.signal.removeEventListener("abort", abort));
      });
    }
  });
  assert.equal((script.match(/^    initialize\(\);$/gm) || []).length, 1);
  new Script(script.replace(/^    initialize\(\);$/m, "    globalThis.ready = initialize();")).runInContext(context);
  await context.ready;
  const evaluate = (code) => runInContext(code, context);
  return {
    elements, prompts, requests, storageCalls, saved, timers, evaluate,
    state: () => normal(evaluate("({sessionContext, fastGptChatId, modelHistory, requestVersion})")),
    submit(text) { elements.get("messageInput").value = text; return evaluate("sendMessage()"); },
    setKey(key = fakeKey, remember = false) {
      elements.get("key").value = key; elements.get("remember").checked = remember;
      elements.get("key-form").dispatch("submit");
    },
    respondWith(callback) { reply = callback; },
    expire() { for (const callback of [...timers.values()]) callback(); },
    cards: () => descendants(elements.get("messages")).filter((item) => item.className === "product-card"),
    text: () => descendants(elements.get("messages")).map((item) => item.textContent).join(" ")
  };
}

test("single upload file embeds unchanged data/prompt and preserves original Editorial Clean styles", async () => {
  const site = new URL("../aiep-candidate/site/", import.meta.url);
  assert.deepEqual(await readdir(site), ["index.html"]);
  assert.ok(Buffer.byteLength(html) < 2_000_000);
  const app = await harness();
  assert.deepEqual(normal(app.evaluate("productDataset")), dataset);
  assert.equal(JSON.parse(app.elements.get("mytech-reference-prompt").textContent), referencePrompt);
  assert.equal(html.match(/<style>([\s\S]*?)<\/style>/)[1].replace(/\r\n/g, "\n"), original.match(/<style>([\s\S]*?)<\/style>/)[1].replace(/\r\n/g, "\n"));
  for (const name of ["addStructuredResponse", "addThinkingMessage", "autoResizeInput"]) {
    const pattern = new RegExp("    function " + name + "\\([\\s\\S]*?(?=\\n    (?:async )?function )");
    assert.equal(script.match(pattern)[0].replace(/\r/g, "").trimEnd(), original.match(pattern)[0].replace(/\r/g, "").trimEnd());
  }
  assert.equal(app.requests.length, 0, "initialization makes no health or asset fetch");
  assert.equal(dataset.products.length, 27);
  assert.equal(dataset.supported_categories.length, 9);
});

for (const [hostname, hosted] of [
  ["project-cmi-01.aidcec-ai-agent.com", true], ["PROJECT-EMI-99.AIDCEC-AI-AGENT.COM", true],
  ["project-demo-00.aidcec-ai-agent.com", true], ["project-cmi-1.aidcec-ai-agent.com", false],
  ["project-cmi-001.aidcec-ai-agent.com", false], ["project-cmi-01.aidcec-ai-agent.com.evil.test", false],
  ["evil-project-cmi-01.aidcec-ai-agent.com", false], ["localhost", false]
]) test(`host classification: ${hostname}`, async () => {
  const app = await harness({ hostname, storageFailure: "access" });
  assert.equal(app.evaluate("HOSTED"), hosted);
  assert.equal(app.elements.get("key-panel").hidden, hosted);
  if (hosted) {
    assert.equal(app.storageCalls.length, 0);
    assert.equal(app.elements.get("sendButton").disabled, false);
  }
});

test("official protected endpoint and header routing is retained", async () => {
  const app = await harness();
  assert.equal(app.evaluate('endpoint("/fastgpt/v1/chat/completions")'), "/fastgpt/v1/chat/completions");
  assert.deepEqual(normal(app.evaluate("headers()")), { "content-type": "application/json" });
  await app.submit("Hello");
  assert.equal(app.requests[0].url, "/fastgpt/v1/chat/completions");
  assert.deepEqual(Object.keys(app.requests[0].headers), ["content-type"]);
  assert.deepEqual(app.requests[0].payload.messages, [{ role: "user", content: "Hello" }]);
  assert.deepEqual(Object.keys(app.requests[0].payload).sort(), ["chatId", "max_tokens", "messages", "stream"]);
  assert.equal(app.requests[0].payload.stream, false);
  assert.equal(app.requests[0].payload.max_tokens, 800);
  assert.match(app.requests[0].payload.chatId, /^mytech-/);
});

for (const [hostname, protocol, privateMode] of [
  ["", "file:", true], ["localhost", "http:", true], ["127.0.0.1", "http:", true],
  ["example.github.io", "https:", false], ["localhost.evil.test", "https:", false], ["::1", "http:", false]
]) test(`key mode and PRIVATE: ${protocol}//${hostname}`, async () => {
  const app = await harness({ hostname, protocol });
  assert.equal(app.evaluate("PRIVATE"), privateMode);
  assert.equal(app.elements.get("remember-row").hidden, !privateMode);
  await app.submit("Hello");
  assert.equal(app.requests.length, 0);
  app.setKey();
  assert.equal(app.elements.get("key").value, "");
  assert.equal(app.elements.get("key").placeholder, "Key set");
  await app.submit("Hello");
  assert.equal(app.requests[0].url, "https://maas.eduhk.hk/api/v1/chat/completions");
  assert.equal(app.requests[0].headers.authorization, "Bearer " + fakeKey);
  for (const path of ["/v1/chat/completions", "/api/v1/chat/completions", "/fastgpt/v1/chat/completions"]) {
    assert.equal(app.evaluate(`endpoint(${JSON.stringify(path)})`), "https://maas.eduhk.hk/api/v1/chat/completions");
  }
  assert.equal(app.evaluate('endpoint("/tokenproxy/v1/chat/completions")'), "https://api.aidcec-ai-agent.com/v1/chat/completions");
  assert.equal(app.evaluate('endpoint("/kb/v1/search")'), "https://db.aidcec-ai-agent.com/kb/v1/search");
  assert.equal(app.evaluate('endpoint("/v1/search")'), "https://api.aidcec-ai-agent.com/v1/search");
  if (!privateMode) assert.deepEqual(app.storageCalls, []);
});

for (const failure of ["access", "getItem", "setItem", "removeItem"]) {
  test(`storage ${failure} failure never disables memory-only key mode`, async () => {
    const app = await harness({ hostname: "localhost", protocol: "http:", storageFailure: failure });
    app.setKey(fakeKey, true);
    await app.submit("Hello");
    assert.equal(app.requests.length, 1);
    app.elements.get("forget").dispatch("click");
    assert.equal(app.evaluate("apiKey"), "");
    assert.equal(app.elements.get("sendButton").disabled, true);
    if (failure === "removeItem" || failure === "access") {
      assert.match(app.elements.get("key-status").textContent, /could not be cleared/i);
    }
  });
}

test("remember requires private origin and consent; uncheck and Forget remove the saved value", async () => {
  const app = await harness({ hostname: "localhost" });
  app.setKey(); assert.equal(app.saved.size, 0);
  app.setKey(fakeKey, true); assert.equal(app.saved.get("tokenproxy-key"), fakeKey);
  app.elements.get("remember").checked = false;
  app.elements.get("remember").dispatch("change"); assert.equal(app.saved.size, 0);
  app.setKey(fakeKey, true);
  app.elements.get("forget").dispatch("click"); assert.equal(app.saved.size, 0);
  const shared = await harness({ hostname: "example.github.io", saved: fakeKey });
  shared.setKey(fakeKey, true); assert.deepEqual(shared.storageCalls, []);
  const restored = await harness({ hostname: "localhost", saved: fakeKey });
  assert.equal(restored.evaluate("apiKey"), fakeKey);
  assert.equal(restored.elements.get("remember").checked, true);
});

test("wrong provider and empty key are rejected without requests, logging or key previews", async () => {
  const app = await harness({ hostname: "localhost" });
  for (const key of ["", "not-a-key", "tp-live-" + "test-only-not-a-credential"]) {
    app.setKey(key); await app.submit("Hello");
    assert.equal(app.requests.length, 0);
    assert.equal(app.evaluate("apiKey"), "");
    assert.ok(!app.elements.get("key-status").textContent.includes(key || "never-in-status"));
  }
});

for (const status of [401, 402, 403, 429, 500, 502, 504]) {
  for (const hosted of [true, false]) test(`friendly HTTP ${status}, ${hosted ? "hosted" : "key"} mode`, async () => {
    const app = await harness({ hostname: hosted ? undefined : "localhost" });
    if (!hosted) app.setKey();
    app.respondWith(() => response({ error: { message: fakeKey } }, status));
    await app.submit("Hello");
    const expected = status === 401 ? (hosted ? /reload.*sign in/i : /key.*not accepted/i)
      : status === 402 ? /budget.*used up/i : status === 403 ? (hosted ? /paused/i : /cannot use/i)
      : status === 429 ? /wait a few seconds/i : /service is busy/i;
    assert.match(app.text(), expected);
    assert.ok(!app.text().includes(fakeKey));
    assert.equal(app.requests.length, 1);
    assert.equal(app.cards().length, 0);
    assert.equal(app.elements.get("sendButton").disabled, false);
    assert.equal(app.state().modelHistory.length, 0);
    assert.equal(app.timers.size, 0);
  });
}

test("non-JSON error, network error and invalid success restore controls without raw errors", async () => {
  for (const reply of [
    () => ({ ok: false, status: 500, async json() { throw new Error(fakeKey); } }),
    () => Promise.reject(new Error(fakeKey)),
    () => ({ ok: true, status: 200, async json() { throw new Error(fakeKey); } }),
    () => response({ output: emptyOutput(), provider: "fastgpt", appId: "old-envelope" })
  ]) {
    const app = await harness(); app.respondWith(reply);
    await app.submit("Hello");
    assert.ok(!app.text().includes(fakeKey));
    assert.equal(app.cards().length, 0);
    assert.equal(app.elements.get("sendButton").disabled, false);
    assert.equal(app.requests.length, 1);
  }
});

test("timeout is reported, thinking removed, controls restored and no retry sent", async () => {
  const app = await harness();
  app.respondWith(() => new Promise(() => {}));
  const turn = app.submit("Hello");
  assert.equal(app.elements.get("sendButton").disabled, true);
  app.expire(); await turn;
  assert.match(app.text(), /timed out/i);
  assert.doesNotMatch(app.text(), /Thinking\.\.\./);
  assert.equal(app.elements.get("sendButton").disabled, false);
  assert.equal(app.requests.length, 1);
  assert.equal(app.state().modelHistory.length, 0);
  assert.equal(app.timers.size, 0);
});

test("strict native content parsing accepts only plain JSON or one complete lowercase json fence", async () => {
  const app = await harness();
  const text = JSON.stringify(emptyOutput());
  for (const content of [text, ` \n${text} \n`, "```json\n" + text + "\n```", "```json\r\n" + text + "\r\n```"])
    assert.deepEqual(normal(app.evaluate(`coerceStructuredOutput(${JSON.stringify({ choices: [{ message: { content } }] })})`)), emptyOutput());
  for (const content of ["", "Here: " + text, "<thinking>plan</thinking>" + text, text + text,
    "```JSON\n" + text + "\n```", "```\n" + text + "\n```", "```json\n{" ]) {
    assert.throws(() => app.evaluate(`coerceStructuredOutput(${JSON.stringify({ choices: [{ message: { content } }] })})`));
  }
});

test("strict catalogue/shape validation blocks unsafe cards through the real submission path", async () => {
  const product = dataset.products.find((item) => item.id === "LAP-001");
  const valid = { answer: "A reference laptop.", recommendations: [{ category: product.category,
    recommended_product: product.product, price: product.price_rmb, reason: "For study.", source: product.source }], next_step: "", clarification_needed: false };
  for (const mutate of [
    (o) => { delete o.answer; }, (o) => { o.extra = "no"; }, (o) => { o.clarification_needed = "false"; },
    (o) => { o.recommendations[0].recommended_product = "Invented laptop"; },
    (o) => { o.recommendations[0].price += 1; }, (o) => { o.recommendations[0].price = String(product.price_rmb); },
    (o) => { o.recommendations[0].category = "Mouse"; }, (o) => { o.recommendations[0].source = "Unapproved"; },
    (o) => { o.recommendations[0].reason = ""; }, (o) => { o.recommendations[0].extra = true; },
    (o) => { o.recommendations.push({ ...o.recommendations[0] }); }, (o) => { o.clarification_needed = true; },
    (o) => { o.answer = "Currently in stock"; }
  ]) {
    const app = await harness(); const output = structuredClone(valid); mutate(output);
    app.respondWith(() => response(envelope(output)));
    await app.submit("I need a laptop under RMB 6000 for study.");
    assert.equal(app.cards().length, 0);
    assert.match(app.text(), /couldn't safely validate/i);
  }
  for (const source of [null, undefined, product.source]) {
    const app = await harness(); const output = structuredClone(valid);
    if (source === undefined) delete output.recommendations[0].source;
    else output.recommendations[0].source = source;
    app.respondWith(() => response(envelope(output)));
    await app.submit("I need a laptop under RMB 6000 for study.");
    assert.equal(app.cards().length, 1);
  }
  for (const [budget, usage, count] of [[5799, "study", 1], [5798, "study", 0], [6000, "gaming", 0]]) {
    const app = await harness(); app.respondWith(() => response(envelope(valid)));
    await app.submit(`I need a laptop under RMB ${budget} for ${usage}.`);
    assert.equal(app.cards().length, count);
  }
});

test("truncated responses, invalid catalogue initialization and prompt corruption fail closed", async () => {
  const app = await harness();
  app.respondWith(() => response({ ...envelope(emptyOutput()), choices: [{ finish_reason: "length", message: { content: JSON.stringify(emptyOutput()) } }] }));
  await app.submit("Hello"); assert.match(app.text(), /couldn't safely validate/i);
  app.elements.get("mytech-dataset").textContent = JSON.stringify({ ...dataset, products: [] });
  await app.evaluate("initialize()");
  assert.equal(app.elements.get("sendButton").disabled, true);
  app.elements.get("mytech-dataset").textContent = JSON.stringify(dataset);
  app.elements.get("mytech-reference-prompt").textContent = JSON.stringify("wrong prompt");
  await app.evaluate("initialize()"); assert.equal(app.evaluate("datasetReady"), false);
});

test("upload has no external assets, forbidden APIs, credential literals or unsafe rendering", () => {
  assert.equal((script.match(/\bfetch\(/g) || []).length, 1);
  assert.match(script, /fetch\(endpoint\("\/fastgpt\/v1\/chat\/completions"\)/);
  assert.doesNotMatch(html, /\/api\/mytech|\/api\/health|MyTechModel|api\.openai\.com|<script\s+src=|<link\s|@import/);
  assert.doesNotMatch(script, /innerHTML|insertAdjacentHTML|document\.write|\beval\s*\(|console\.|\b(?:alert|confirm|prompt)\s*\(|window\.open|sessionStorage|indexedDB|serviceWorker|document\.cookie/);
  assert.doesNotMatch(html, /\b(?:openapi|tp-live|sk)-[A-Za-z0-9._-]{8,}/);
  assert.ok(html.includes('type="password"'));
});
