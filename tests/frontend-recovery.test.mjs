import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createContext, runInContext, Script } from "node:vm";

const html = await readFile(new URL("../MyTech_Chatbot_v2.html", import.meta.url), "utf8");
const dataset = JSON.parse(await readFile(
  new URL("../mytech_v1_product_dataset.json", import.meta.url), "utf8"
));
const inlineScript = html.match(/<script>([\s\S]*?)<\/script>/)[1];
// Skip only automatic bootstrap/data fetching; exercise the actual frontend functions.
assert.equal((inlineScript.match(/^    initialize\(\);$/gm) || []).length, 1);
const frontendScript = new Script(inlineScript.replace(/^    initialize\(\);$/m, ""));

class Element {
  constructor(tagName = "div") {
    this.tagName = tagName;
    this.children = [];
    this.listeners = {};
    this.value = "";
    this.style = {};
    this.scrollHeight = 180;
    this.disabled = false;
    this.focusCount = 0;
    this.classList = { add() {}, toggle() {} };
  }
  append(...children) {
    children.forEach((child) => {
      child.parent = this;
      this.children.push(child);
    });
  }
  appendChild(child) { this.append(child); }
  replaceChildren() { this.children = []; }
  remove() {
    this.parent.children = this.parent.children.filter((child) => child !== this);
  }
  setAttribute() {}
  addEventListener(type, listener) { this.listeners[type] = listener; }
  // Intentionally invoke listeners even when disabled to test handler-level guards.
  dispatch(type) { return this.listeners[type]?.({}); }
  focus() { this.focusCount += 1; }
}

function harness() {
  const elements = new Map();
  const requests = [];
  let networkCalls = 0;
  let chatIdSequence = 0;
  let respond = () => Promise.reject(new Error("MODEL_REQUEST_FAILED"));
  const context = createContext({
    document: {
      getElementById(id) {
        if (!elements.has(id)) elements.set(id, new Element());
        return elements.get(id);
      },
      querySelectorAll: () => [],
      createElement: (tag) => new Element(tag)
    },
    window: {
      crypto: { randomUUID: () => `test-conversation-id-${++chatIdSequence}` },
      setTimeout(callback) { callback(); },
      MyTechModel: {
        provider: "fastgpt",
        appId: "test-app",
        call(payload, options) {
          requests.push({ payload, signal: options.signal });
          return respond(payload, options);
        }
      }
    },
    AbortController,
    requestAnimationFrame(callback) { callback(); },
    fetch() {
      networkCalls += 1;
      throw new Error("Real network access is forbidden in this harness");
    },
    fixtureDataset: dataset
  });
  frontendScript.runInContext(context);
  const evaluate = (code) => runInContext(code, context);
  evaluate(`
    productDataset = fixtureDataset;
    productByName = new Map(productDataset.products.map(product => [product.product, product]));
    datasetReady = true;
    modelConnectionReady = true;
    resetConversation();
  `);
  const input = elements.get("messageInput");
  const messages = elements.get("messages");
  return {
    input, messages, requests, evaluate,
    get networkCalls() { return networkCalls; },
    respondWith(callback) { respond = callback; },
    submit(text) { input.value = text; return evaluate("sendMessage()"); },
    draft(text) { input.value = text; input.dispatch("input"); },
    recovery() { return evaluate("activeRecovery?.button"); },
    state() {
      return evaluate("JSON.stringify({ sessionContext, fastGptChatId, modelHistory, requestVersion })");
    }
  };
}

function recoveryButtons(element) {
  return element.children.flatMap((child) => [
    ...(child.className === "recovery-button" ? [child] : []),
    ...recoveryButtons(child)
  ]);
}

function deferred() {
  let reject;
  const promise = new Promise((resolve, rejectPromise) => { reject = rejectPromise; });
  return { promise, reject };
}

test("safe failure creates an action that restores submitted text without requests or state changes", async () => {
  const app = harness();
  const submitted = "I need a laptop under ¥6000 for study.\nKeep  these spaces — please.";
  await app.submit(`  ${submitted}\n `);
  const button = app.recovery();
  assert.equal(button.textContent, "Edit and try again");
  assert.equal(button.type, "button");
  assert.equal(button.disabled, false);
  assert.equal(recoveryButtons(app.messages).length, 1);
  assert.deepEqual(button.parent.children.slice(0, -1).map((child) => child.textContent), [
    "MyTech could not reach the secure FastGPT connection.",
    "Please check the server connection and try again."
  ]);
  assert.equal(app.requests[0].payload.message, submitted);
  const state = app.state();
  const focusCount = app.input.focusCount;
  app.input.style.height = "0px";
  button.dispatch("click");
  assert.equal(app.input.value, submitted);
  assert.equal(app.input.style.height, "132px");
  assert.equal(app.input.style.overflowY, "auto");
  assert.equal(app.input.focusCount, focusCount + 1);
  assert.equal(app.requests.length, 1);
  assert.equal(app.networkCalls, 0);
  assert.equal(app.state(), state);
  assert.equal(button.disabled, true);
});

test("drafts, including whitespace, are protected and clearing a draft re-enables recovery", async () => {
  const app = harness();
  await app.submit("Original request");
  const button = app.recovery();
  for (const draft of ["New draft", " \n\t "]) {
    app.draft(draft);
    assert.equal(button.disabled, true);
    button.dispatch("click");
    assert.equal(app.input.value, draft);
  }
  app.draft("");
  assert.equal(button.disabled, false);
  button.dispatch("click");
  assert.equal(app.input.value, "Original request");
  assert.equal(app.requests.length, 1);
});

test("generation disables recovery and its click handler independently protects the composer", async () => {
  const app = harness();
  await app.submit("Original request");
  const button = app.recovery();
  app.evaluate("setGenerating(true)");
  assert.equal(button.disabled, true);
  const state = app.state();
  button.dispatch("click");
  assert.equal(app.input.value, "");
  assert.equal(app.state(), state);
  assert.equal(app.requests.length, 1);
  app.evaluate("setGenerating(false)");
  assert.equal(button.disabled, false);
});

test("only a valid newer submission invalidates the old action permanently", async () => {
  const app = harness();
  await app.submit("Original request");
  const oldButton = app.recovery();
  await app.submit(" \n ");
  assert.equal(app.recovery(), oldButton);
  app.draft("");
  const pending = deferred();
  app.respondWith(() => pending.promise);
  const submission = app.submit("New request");
  assert.equal(oldButton.disabled, true);
  assert.equal(app.recovery(), undefined);
  oldButton.dispatch("click");
  assert.equal(app.input.value, "");
  pending.reject(new Error("MODEL_REQUEST_FAILED"));
  await submission;
  const newButton = app.recovery();
  assert.notEqual(newButton, oldButton);
  oldButton.dispatch("click");
  assert.equal(app.input.value, "");
  newButton.dispatch("click");
  assert.equal(app.input.value, "New request");
});

test("restart permanently invalidates existing recovery", async () => {
  const app = harness();
  await app.submit("Original request");
  const button = app.recovery();
  app.evaluate("resetConversation()");
  assert.equal(button.disabled, true);
  assert.equal(app.recovery(), undefined);
  assert.equal(recoveryButtons(app.messages).length, 0);
  const state = app.state();
  button.dispatch("click");
  assert.equal(app.input.value, "");
  assert.equal(app.state(), state);
});

for (const errorName of ["AbortError", "Error"]) {
  test(`restart followed by ${errorName} from a stale request creates no recovery`, async () => {
    const app = harness();
    const pending = deferred();
    app.respondWith(() => pending.promise);
    const submission = app.submit("Pending request");
    app.evaluate("resetConversation()");
    assert.equal(app.requests[0].signal.aborted, true);
    const state = app.state();
    const error = new Error("Late failure");
    error.name = errorName;
    pending.reject(error);
    await submission;
    assert.equal(app.recovery(), undefined);
    assert.equal(recoveryButtons(app.messages).length, 0);
    assert.equal(app.messages.children.length, 1);
    assert.equal(app.state(), state);
    assert.equal(app.evaluate("isGenerating"), false);
  });
}

test("restored text subsequently uses the existing request, validation, and rendering path", async () => {
  const app = harness();
  const text = "I need a laptop under ¥6000 for study.";
  await app.submit(text);
  const button = app.recovery();
  button.dispatch("click");
  const product = dataset.products.find((item) => item.category === "Laptop");
  const output = {
    answer: "Here is a reference recommendation.",
    recommendations: [{
      category: product.category,
      recommended_product: product.product,
      price: product.price_rmb,
      reason: "Suitable for study.",
      source: product.source
    }],
    next_step: "Tell me if you need another option.",
    clarification_needed: false
  };
  app.respondWith(() => Promise.resolve(output));
  await app.evaluate("sendMessage()");
  assert.equal(app.requests.length, 2);
  assert.equal(app.requests[1].payload.message, text);
  assert.equal(app.requests[1].payload.chatId, app.requests[0].payload.chatId);
  assert.equal(app.recovery(), undefined);
  assert.equal(button.disabled, true);
  assert.equal(app.evaluate("modelHistory.length"), 2);
  assert.equal(app.evaluate("sessionContext.lastRecommendationsByCategory.Laptop.product"), product.product);
  assert.match(app.evaluate("JSON.stringify(modelHistory)"), /reference recommendation/);
  assert.equal(app.networkCalls, 0);
});
