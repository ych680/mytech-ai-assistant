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

const recommendation = (id) => {
  const product = dataset.products.find((item) => item.id === id);
  return { category: product.category, recommended_product: product.product, price: product.price_rmb, reason: "Matches the reference requirements.", source: product.source };
};
const output = (recommendations = [], clarification_needed = false) => ({ answer: "Reference response.", recommendations, next_step: "Tell me if you need anything else.", clarification_needed });
const laptop = recommendation("LAP-001"), mouse = recommendation("MOU-002");
const initialQuestion = "I need a laptop under RMB 6000 for study and a mouse under RMB 300 for gaming.";

async function seed() {
  const app = await harness();
  app.respondWith(() => response(envelope(output([laptop, mouse]))));
  await app.submit(initialQuestion);
  assert.equal(app.cards().length, 2);
  return app;
}

test("another Mouse preserves ID, both saved requests, budgets and unrelated recommendation anchor", async () => {
  const app = await seed(); const before = app.state();
  app.respondWith(() => response(envelope(output()))); // Valid no-match preserves anchors.
  await app.submit("Can you recommend another mouse?");
  const after = app.state();
  assert.equal(after.fastGptChatId, before.fastGptChatId);
  assert.deepEqual(after.sessionContext.requirementsByCategory, before.sessionContext.requirementsByCategory);
  assert.deepEqual(after.sessionContext.activeCategories, ["Laptop", "Mouse"]);
  assert.deepEqual(after.sessionContext.targetCategories, ["Mouse"]);
  assert.deepEqual(after.sessionContext.lastRecommendationsByCategory, before.sessionContext.lastRecommendationsByCategory);
  assert.equal(app.requests[1].payload.chatId, app.requests[0].payload.chatId);
  assert.equal(app.state().modelHistory.length, 4);
});

test("cheaper Mouse then cheaper Laptop retain the conversation and category constraints", async () => {
  const app = await seed(); const before = app.state();
  app.respondWith(() => response(envelope(output())));
  await app.submit("Can you recommend a cheaper mouse?");
  await app.submit("Can you recommend a cheaper laptop?");
  assert.ok(app.requests.every((request) => request.payload.chatId === before.fastGptChatId));
  assert.deepEqual(app.state().sessionContext.requirementsByCategory, before.sessionContext.requirementsByCategory);
  assert.deepEqual(app.state().sessionContext.targetCategories, ["Laptop"]);
  assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, before.sessionContext.lastRecommendationsByCategory);
});

test("Anything cheaper then Mouse resumes the pending intent and rejects an Office-only cheaper mouse", async () => {
  const app = await seed(); const before = app.state();
  app.respondWith(() => response(envelope(output([], true))));
  await app.submit("Anything cheaper?");
  assert.equal(app.state().sessionContext.pendingComparison, "cheaper");
  assert.deepEqual(app.state().sessionContext.targetCategories, []);
  app.respondWith(() => response(envelope(output([recommendation("MOU-001")]))));
  await app.submit("Mouse");
  assert.equal(app.state().sessionContext.pendingComparison, null);
  assert.equal(app.state().fastGptChatId, before.fastGptChatId);
  assert.deepEqual(app.state().sessionContext.requirementsByCategory, before.sessionContext.requirementsByCategory);
  assert.match(app.text(), /couldn't safely validate/i);
  assert.equal(app.cards().length, 2, "only the initial validated cards remain");
});

test("cancellation clears pending intent, preserves constraints and Mouse does not resume the cheaper action", async () => {
  const app = await seed(); const before = app.state();
  app.respondWith(() => response(envelope(output([], true))));
  await app.submit("Anything cheaper?");
  await app.submit("Cancel that.");
  assert.equal(app.state().sessionContext.pendingComparison, null);
  app.respondWith(() => response(envelope(output([mouse]))));
  await app.submit("Mouse");
  assert.equal(app.state().fastGptChatId, before.fastGptChatId);
  assert.deepEqual(app.state().sessionContext.requirementsByCategory, before.sessionContext.requirementsByCategory);
  assert.equal(app.cards().length, 3, "normal same-price recommendation does not inherit cheaper constraint");
});

test("new explicit category details supersede pending action without overwriting another category", async () => {
  const app = await seed(); const before = app.state();
  app.respondWith(() => response(envelope(output([], true))));
  await app.submit("Anything cheaper?");
  await app.submit("I need a mouse under RMB 500 for office.");
  assert.equal(app.state().fastGptChatId, before.fastGptChatId);
  assert.equal(app.state().sessionContext.pendingComparison, null);
  assert.deepEqual(app.state().sessionContext.requirementsByCategory.Laptop, before.sessionContext.requirementsByCategory.Laptop);
  assert.deepEqual(app.state().sessionContext.requirementsByCategory.Mouse, { category: "Mouse", budget: 500, usage: "Office" });
});

test("ambiguous comparisons, wrong target, repeated alternative and non-cheaper responses never add cards", async () => {
  for (const [question, recommendations] of [
    ["Anything cheaper?", [mouse]], ["Can you recommend a cheaper mouse?", [laptop]],
    ["Can you recommend another mouse?", [mouse]], ["Can you recommend a cheaper mouse?", [mouse]],
    ["Can you recommend a more expensive mouse?", [mouse]], ["Cancel that.", [mouse]]
  ]) {
    const app = await seed(); app.respondWith(() => response(envelope(output(recommendations))));
    await app.submit(question);
    assert.equal(app.cards().length, 2, question);
    assert.match(app.text(), /couldn't safely validate/i);
  }
});

test("no-result comparison retains anchors and a complete new request updates only its own constraint", async () => {
  const app = await seed(); const before = app.state();
  app.respondWith(() => response(envelope(output())));
  await app.submit("A cheaper mouse?");
  await app.submit("I need a laptop under RMB 7000 for study.");
  assert.equal(app.state().fastGptChatId, before.fastGptChatId);
  assert.equal(app.state().sessionContext.requirementsByCategory.Laptop.budget, 7000);
  assert.equal(app.state().sessionContext.requirementsByCategory.Mouse.budget, 300);
  assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, before.sessionContext.lastRecommendationsByCategory);
});

for (const late of ["resolve", "reject"]) test(`Restart suppresses late ${late} even when transport ignores abort`, async () => {
  const app = await harness({ ignoreAbort: true });
  let resolve, reject;
  app.respondWith(() => new Promise((yes, no) => { resolve = yes; reject = no; }));
  const turn = app.submit(initialQuestion); const id = app.state().fastGptChatId;
  app.elements.get("restartButton").dispatch("click");
  const afterRestart = app.state();
  assert.notEqual(afterRestart.fastGptChatId, id);
  assert.equal(app.requests[0].signal.aborted, true);
  if (late === "resolve") resolve(response(envelope(output([laptop, mouse]))));
  else reject(new Error("late error"));
  await turn;
  assert.deepEqual(app.state(), afterRestart);
  assert.equal(app.cards().length, 0);
  assert.equal(app.elements.get("messages").children.length, 1);
  assert.equal(app.evaluate("activeRecovery"), null);
  assert.equal(app.timers.size, 0);
});

test("key change and Forget isolate pending conversations and discard late results", async () => {
  const app = await harness({ hostname: "localhost", ignoreAbort: true }); app.setKey();
  for (const action of ["change", "forget"]) {
    if (action === "forget") app.setKey();
    let resolve;
    app.respondWith(() => new Promise((yes) => { resolve = yes; }));
    const turn = app.submit(initialQuestion); const before = app.state();
    if (action === "change") app.setKey(fakeKey + "-changed");
    else app.elements.get("forget").dispatch("click");
    const after = app.state();
    assert.notEqual(after.fastGptChatId, before.fastGptChatId);
    assert.deepEqual(after.sessionContext.activeCategories, []);
    assert.equal(app.requests.at(-1).signal.aborted, true);
    resolve(response(envelope(output([laptop, mouse])))); await turn;
    assert.deepEqual(app.state(), after);
    assert.equal(app.cards().length, 0);
  }
});

test("explicit new conversation rotates; ordinary category switches and now/next comparisons do not", async () => {
  const app = await seed(); const id = app.state().fastGptChatId;
  app.respondWith(() => response(envelope(output())));
  for (const text of ["Now a cheaper mouse?", "Next, a cheaper laptop?", "I need a monitor under RMB 2000 for gaming."]) {
    await app.submit(text); assert.equal(app.state().fastGptChatId, id);
  }
  await app.submit("Start over.");
  assert.notEqual(app.state().fastGptChatId, id);
  assert.deepEqual(app.state().sessionContext.activeCategories, []);
  assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, {});
});

test("all starter buttons submit their original text through native transport and block concurrent sends", async () => {
  for (let i = 0; i < 5; i++) {
    const app = await harness(); assert.equal(app.prompts.length, 5);
    app.prompts[i].dispatch("click");
    for (let j = 0; j < 20; j++) await Promise.resolve();
    assert.equal(app.requests.length, 1);
    assert.equal(app.requests[0].payload.messages[0].content, app.prompts[i].dataset.prompt);
    assert.equal(app.evaluate("isGenerating"), false);
  }
  const app = await harness(); let resolve;
  app.respondWith(() => new Promise((yes) => { resolve = yes; }));
  const turn = app.submit("Hello"); app.prompts[0].dispatch("click");
  await app.submit("Cannot send twice"); assert.equal(app.requests.length, 1);
  resolve(response(envelope(output()))); await turn;
});

test("all 27 approved products render exact catalogue facts using text nodes", async () => {
  for (const product of dataset.products) {
    const app = await harness();
    const rec = recommendation(product.id);
    rec.reason = '<img src=x onerror="throw 1">';
    app.respondWith(() => response(envelope(output([rec]))));
    await app.submit(`I need a ${product.category} under RMB ${product.price_rmb}.`);
    const cards = app.cards(); assert.equal(cards.length, 1, product.id);
    const contents = descendants(cards[0]);
    for (const [className, text] of [
      ["product-name", product.product], ["product-meta", `${product.category} · ${product.tier} · Reference price`],
      ["product-specs", product.key_features.join(" · ")], ["product-source", `Source: ${product.source}`],
      ["product-reason", rec.reason]
    ]) assert.equal(contents.find((item) => item.className === className).textContent, text);
    assert.equal(contents.filter((item) => item.tagName === "img").length, 0);
  }
});

test("recovery preserves drafts, sends no request on restore, and is invalidated by Restart", async () => {
  const app = await harness(); app.respondWith(() => response({}, 500));
  await app.submit(initialQuestion);
  const recovery = app.evaluate("activeRecovery.button");
  app.elements.get("messageInput").value = "  "; recovery.dispatch("click");
  assert.equal(app.elements.get("messageInput").value, "  ");
  app.elements.get("messageInput").value = ""; recovery.dispatch("click");
  assert.equal(app.elements.get("messageInput").value, initialQuestion);
  assert.equal(app.requests.length, 1);
  app.elements.get("restartButton").dispatch("click"); recovery.dispatch("click");
  assert.equal(app.elements.get("messageInput").value, "");
  assert.equal(app.state().modelHistory.length, 0);
});

test("bounded cancellation matches the verified workflow; quoted wording does not consume pending intent", async () => {
  for (const phrase of ["Never mind, cancel that comparison.", "Please cancel the follow-up.", "Stop this comparison."]) {
    const app = await seed(); app.respondWith(() => response(envelope(output([], true))));
    await app.submit("Anything cheaper?"); await app.submit(phrase);
    assert.equal(app.state().sessionContext.pendingComparison, null);
  }
  const app = await seed(); app.respondWith(() => response(envelope(output([], true))));
  await app.submit("Anything cheaper?");
  await app.submit('Write a story where someone says "never mind, cancel that comparison".');
  assert.equal(app.state().sessionContext.pendingComparison, "cheaper");
  await app.submit("Write a story about a more expensive train ticket.");
  assert.equal(app.state().sessionContext.pendingComparison, "cheaper");
});

test("negated comparisons do not override a complete replacement request", async () => {
  const app = await seed(); app.respondWith(() => response(envelope(output([], true))));
  await app.submit("Anything cheaper?");
  app.respondWith(() => response(envelope(output([recommendation("MOU-001")]))));
  await app.submit("I do not want a cheaper option. I need a mouse for office under RMB 150.");
  assert.equal(app.state().sessionContext.pendingComparison, null);
  assert.equal(app.cards().length, 3);
  assert.equal(app.state().sessionContext.requirementsByCategory.Laptop.budget, 6000);
});

test("history remains bounded and separate browsers have independent session state", async () => {
  const app = await harness();
  for (let i = 0; i < 12; i++) await app.submit("Hello " + i);
  assert.equal(app.state().modelHistory.length, 16);
  assert.ok(app.requests.every((request) => request.payload.messages.length === 1));
  const other = await harness();
  assert.deepEqual(other.state().modelHistory, []);
  assert.deepEqual(other.state().sessionContext.activeCategories, []);
  assert.equal(other.requests.length, 0);
});

test("T06 exact adjective-before-category input rejects the Office-only M240", async () => {
  const question = "I need a laptop for studying under RMB 6000 and a gaming mouse under RMB 300.";
  const app = await harness();
  const guard = normal(app.evaluate(`updateSessionContext(${JSON.stringify(question)})`));
  assert.deepEqual(guard.budgetsByCategory, { Laptop: 6000, Mouse: 300 });
  const invalid = output([laptop, recommendation("MOU-001")]);
  const validation = normal(app.evaluate(`validateStructuredOutput(${JSON.stringify(invalid)}, ${JSON.stringify(guard)})`));
  assert.equal(validation.valid, false);
  assert.ok(validation.errors.some((error) => /usage tags for Gaming/.test(error)));
  assert.deepEqual(guard.usagesByCategory, { Laptop: "Study", Mouse: "Gaming" });
  app.respondWith(() => response(envelope(invalid)));
  await app.submit(question);
  assert.equal(app.cards().length, 0);
  assert.match(app.text(), /couldn't safely validate/i);
  assert.equal(app.state().modelHistory.length, 0);
});

for (const [name, question] of [
  ["gaming mouse", "I need a laptop for studying under RMB 6000 and a gaming mouse under RMB 300."],
  ["mouse for gaming", "I need a laptop for studying under RMB 6000 and a mouse for gaming under RMB 300."],
  ["both modifiers", "I need a study laptop under RMB 6000 and a gaming mouse under RMB 300."],
  ["Mouse first", "I need a gaming mouse under RMB 300 and a laptop for studying under RMB 6000."],
  ["study modifier after Mouse clause", "I need a mouse for gaming under RMB 300 and a study laptop under RMB 6000."],
  ["usage phrase starts second clause", "I need a laptop for studying under RMB 6000; for gaming I need a mouse under RMB 300."],
  ["usage phrases start both clauses", "For studying I need a laptop under RMB 6000 and for gaming I need a mouse under RMB 300."],
  ["additional Mouse adjective", "I need a laptop for studying under RMB 6000 and a gaming wireless mouse under RMB 300."]
]) test(`multi-product usage ownership: ${name}`, async () => {
  const app = await harness();
  app.respondWith(() => response(envelope(output([laptop, mouse]))));
  await app.submit(question);
  assert.equal(app.cards().length, 2, "approved Study Laptop and Gaming Mouse are accepted");
  const context = app.state().sessionContext;
  assert.equal(context.requirementsByCategory.Laptop.usage, "Study");
  assert.equal(context.requirementsByCategory.Mouse.usage, "Gaming");
  assert.equal(context.requirementsByCategory.Laptop.budget, 6000);
  assert.equal(context.requirementsByCategory.Mouse.budget, 300);
  const chatId = app.state().fastGptChatId;
  app.respondWith(() => response(envelope(output([laptop, recommendation("MOU-001")]))));
  await app.submit(question);
  assert.equal(app.cards().length, 2, "invalid second response adds no cards");
  assert.match(app.text(), /couldn't safely validate/i);
  assert.equal(app.state().fastGptChatId, chatId);
});

for (const [question, usages] of [
  ["I need a laptop under RMB 6000 and a gaming mouse under RMB 300.", { Mouse: "Gaming" }],
  ["I need a study laptop under RMB 6000 and a mouse under RMB 300.", { Laptop: "Study" }],
  ["I need a laptop for studying under RMB 6000 and a mouse under RMB 300.", { Laptop: "Study" }],
  ["I need a laptop under RMB 6000 and a mouse for gaming under RMB 300.", { Mouse: "Gaming" }],
  ["I need a gaming mouse under RMB 300 and a laptop under RMB 6000.", { Mouse: "Gaming" }],
  ["I need a mouse under RMB 300 and a study laptop under RMB 6000.", { Laptop: "Study" }]
]) test(`one product's usage is not copied to another: ${question}`, async () => {
  const app = await harness();
  const guard = normal(app.evaluate(`updateSessionContext(${JSON.stringify(question)})`));
  assert.deepEqual(guard.usagesByCategory, usages);
  assert.equal(guard.budgetsByCategory.Laptop, 6000);
  assert.equal(guard.budgetsByCategory.Mouse, 300);
});

test("scoped usage edits preserve an unrelated saved usage and conversation ID", async () => {
  const app = await seed();
  const before = app.state();
  const question = "I need a study laptop under RMB 7000 and a mouse under RMB 500.";
  app.respondWith(() => response(envelope(output([], true))));
  await app.submit(question);
  assert.equal(app.state().fastGptChatId, before.fastGptChatId);
  assert.deepEqual(app.state().sessionContext.requirementsByCategory, {
    Laptop: { category: "Laptop", budget: 7000, usage: "Study" },
    Mouse: { category: "Mouse", budget: 500, usage: "Gaming" }
  });
  assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, before.sessionContext.lastRecommendationsByCategory);
});
