// Headless candidate frontend with an in-memory provider, never network I/O.
import { readFile } from "node:fs/promises";
import { Script, createContext, runInContext } from "node:vm";

class Element {
  constructor(tag = "div") {
    this.tagName = tag; this.children = []; this.listeners = {}; this.style = {}; this.value = "";
    this._text = ""; this.classList = { add() {}, toggle() {} }; this.scrollHeight = 180;
    this.disabled = false; this.hidden = false; this.open = false; this.dataset = {}; this.attributes = {};
  }
  set textContent(value) { this._text = value; this.children = []; }
  get textContent() { return this._text; }
  set innerHTML(_) { throw new Error("Unsafe DOM rendering"); }
  append(...children) { for (const child of children) { child.parent = this; this.children.push(child); } }
  appendChild(child) { this.append(child); }
  replaceChildren() { this.children.forEach(child => { child.parent = null; }); this.children = []; }
  remove() { if (this.parent) this.parent.children = this.parent.children.filter(child => child !== this); }
  addEventListener(name, fn) { this.listeners[name] = fn; }
  dispatch(name, event = {}) { return this.listeners[name]?.({ preventDefault() {}, ...event }); }
  setAttribute(key, value) { this.attributes[key] = value; }
  focus() { this.focused = true; }
}

const normal = value => JSON.parse(JSON.stringify(value));
const descendants = element => element.children.flatMap(child => [child, ...descendants(child)]);

export async function repairFrontend(kind, packageName = "v21_multiproduct_usage_fix") {
  const local = kind === "local";
  const file = local ? "local/index.html" : "aiep/site/index.html";
  const html = await readFile(new URL("../../generated/" + packageName + "/" + file, import.meta.url), "utf8");
  const elements = new Map(), calls = [];
  const element = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const prompts = [...html.matchAll(/<button class="prompt-button" type="button" data-prompt="([^"]+)">([^<]+)<\/button>/g)].map(match => {
    const button = new Element("button");
    button.dataset.prompt = match[1]; button.textContent = match[2]; return button;
  });
  for (const match of html.matchAll(/<script type="application\/json" id="([^"]+)">([\s\S]*?)<\/script>/g)) element(match[1]).textContent = match[2];
  const hostname = local ? "localhost" : "project-demo-00.aidcec-ai-agent.com";
  const timers = new Map();
  let serial = 0, timerId = 0, reply = { answer: "Please clarify.", recommendations: [], next_step: "State usage.", clarification_needed: true }, provider = null;
  const context = createContext({ document: { baseURI: `https://${hostname}/index.html`, getElementById: element, querySelectorAll: selector => selector === ".prompt-button" ? prompts : [], createElement: tag => new Element(tag) },
    location: { hostname, protocol: local ? "http:" : "https:", search: "" },
    window: { origin: `https://${hostname}`, crypto: { randomUUID: () => "offline-repair-" + ++serial },
      setTimeout(fn, ms) { const id = ++timerId; if (ms < 60000) queueMicrotask(fn); else timers.set(id, fn); return id; }, clearTimeout(id) { timers.delete(id); }, localStorage: { getItem() { return null; }, setItem() {}, removeItem() {} } },
    AbortController, URLSearchParams, requestAnimationFrame: fn => fn(),
    fetch: async (url, init) => {
      if (url === "/api/test/config") return { ok: true, async json() { return { catalogueVersion: "2.1-TEST", productCount: 54, requestTimeoutMs: 120000, configured: true }; } };
      if (url !== (local ? "/api/test/mytech" : "/fastgpt/v1/chat/completions")) throw new Error("Unexpected network target");
      const call = { url, payload: JSON.parse(init.body), signal: init.signal };
      calls.push(call);
      if (provider) return provider(call);
      return { ok: true, status: 200, async json() { return { choices: [{ message: { content: JSON.stringify(reply) } }] }; } };
    }
  });
  const script = html.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^    initialize\(\);$/m, "    globalThis.ready = initialize();");
  new Script(script).runInContext(context);
  await context.ready;
  const evaluate = source => runInContext(source, context);
  const flush = async () => { for (let i = 0; i < 50; i++) await Promise.resolve(); };
  return { calls, evaluate, elements, prompts, flush,
    all() { return descendants(element("messages")); },
    respondWith(fn) { provider = fn; },
    setReply(output) { reply = output; provider = null; },
    async click(button) { button.dispatch("click"); await flush(); },
    input(value) { element("messageInput").value = value; element("messageInput").dispatch("input"); },
    expire() { for (const fn of timers.values()) fn(); },
    guard(message) { return normal(evaluate(`updateSessionContext(${JSON.stringify(message)})`)); },
    validate(output, guard) { return normal(evaluate(`validateStructuredOutput(${JSON.stringify(output)},${JSON.stringify(guard)})`)); },
    async submit(message, output = reply) { reply = output; element("messageInput").value = message; await evaluate("sendMessage()"); },
    restart() { element("restartButton").listeners.click(); },
    state() { return normal(evaluate("({ sessionContext, modelHistory, fastGptChatId })")); },
    cards() { return descendants(element("messages")).filter(item => item.className === "product-card").length; },
    text() { return descendants(element("messages")).map(item => item.textContent).join(" "); }
  };
}
