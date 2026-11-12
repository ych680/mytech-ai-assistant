import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { repairFrontend } from "./helpers/v21-repair-frontend.mjs";
import { startMyTechDemo } from "../start-mytech-demo.mjs";

const fixtures = JSON.parse(await readFile(new URL("./fixtures/p05_live_clarifications_2026_11_12.json", import.meta.url)));
const appFor = kind => repairFrontend(kind, "v21_quick_prompt_demo");
const safeBoth = "What's your maximum budget (RMB), and what will you mainly use the laptop for?";
const latest = fixtures[2].response;
const catalogue = JSON.parse(await readFile(new URL("../generated/v21_quick_prompt_demo/local/catalogue.json", import.meta.url)));
const laptop = catalogue.products.find(product => product.id === "LAP-001");
const grounded = { answer: "A catalogue recommendation for study and office work.",
  recommendations: [{ category: laptop.category, recommended_product: laptop.product, price: laptop.price_rmb,
    source: laptop.source, reason: "Matches study and office work within the maximum budget." }],
  next_step: "Would you like another option?", clarification_needed: false };
const outcome = app => JSON.parse(app.evaluate("JSON.stringify(demoResponseOutcome)"));
const fallbackFor = (app, guard, message, value = latest) => JSON.parse(app.evaluate(
  `JSON.stringify(demoSafeClarification(${JSON.stringify(value)}, ${JSON.stringify(guard)}, ${JSON.stringify(message)}))`
));
const safeQuestion = (category, fields) => fields.length === 2
  ? `What's your maximum budget (RMB), and what will you mainly use the ${category.toLowerCase()} for?`
  : fields[0] === "budget" ? `What's your maximum budget (RMB) for the ${category.toLowerCase()}?`
  : `What will you mainly use the ${category.toLowerCase()} for?`;

function assertFallback(app, category, fields, raw = latest) {
  const result = outcome(app);
  assert.equal(result.kind, "deterministic_clarification");
  assert.equal(result.modelAccepted, false);
  assert.equal(result.category, category);
  assert.deepEqual(result.missingFields, fields);
  assert.deepEqual(result.output, { answer: safeQuestion(category, fields), recommendations: [],
    next_step: "", clarification_needed: true });
  assert.ok(app.text().includes("Local clarification"));
  assert.equal(app.text().includes("The model response was not accepted."), false);
  assert.equal(app.text().includes("Reply with the missing information to continue."), false);
  assert.ok(app.text().includes(result.output.answer));
  for (const prose of [raw.answer, raw.next_step].filter(Boolean)) {
    assert.equal(app.text().includes(prose), false);
    assert.equal(JSON.stringify(app.state().modelHistory).includes(prose), false);
    assert.equal(JSON.stringify(result).includes(prose), false);
  }
}

for (const kind of ["local", "aiep"]) {
  for (const [index, fixture] of fixtures.entries()) {
    test(`${kind}: exact historical live retest ${fixture.retest}`, async t => {
      const app = await appFor(kind), before = app.state();
      await app.submit(fixture.request, fixture.response);
      t.diagnostic(`history entries: ${app.state().modelHistory.length}; ownership error: ${app.text().includes("Please clarify which intended usage belongs to each product; no recommendation was accepted.")}`);
      if (index < 2) {
        assert.deepEqual(outcome(app), { kind: "accepted_model", modelAccepted: true });
        assert.equal(app.state().modelHistory.length, 2);
        assert.ok(app.text().includes(fixture.response.answer));
        assert.ok(app.text().includes(fixture.response.next_step));
      } else {
        assertFallback(app, "Laptop", ["budget", "main_usage"], fixture.response);
        assert.ok(app.text().includes(safeBoth));
        assert.ok(app.text().includes("Local clarification"));
        assert.equal(app.state().modelHistory.length, 0);
        assert.equal(app.text().includes(fixture.response.answer), false);
        assert.equal(app.text().includes(fixture.response.next_step), false);
      }
      assert.equal(app.text().includes("Please clarify which intended usage"), false);
      assert.equal(app.state().fastGptChatId, before.fastGptChatId);
      assert.equal(app.cards(), 0);
      assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, {});
    });
  }

  for (const [message, category, fields] of [
    ["I need a laptop.", "Laptop", ["budget", "main_usage"]],
    ["I need a laptop for study and office work.", "Laptop", ["budget"]],
    ["I need a laptop under RMB 6000.", "Laptop", ["main_usage"]],
    ["I need a desktop.", "Desktop", ["budget", "main_usage"]],
    ["I need a smartphone.", "Smartphone", ["budget", "main_usage"]],
    ["I need a tablet.", "Tablet", ["budget", "main_usage"]],
    ["I need headphones.", "Headphones", ["budget", "main_usage"]],
    ["I need a monitor.", "Monitor", ["budget", "main_usage"]],
    ["I need a smartwatch.", "Smartwatch", ["budget", "main_usage"]],
    ["I need a mouse.", "Mouse", ["budget", "main_usage"]],
    ["I need a keyboard.", "Keyboard", ["budget", "main_usage"]]
  ]) {
    test(`${kind}: local fields determine ${fields.join("+")} for ${category}`, async () => {
      const app = await appFor(kind);
      await app.submit(message, latest);
      assertFallback(app, category, fields);
      assert.equal(app.state().modelHistory.length, 0);
      assert.equal(app.cards(), 0);
      assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, {});
      const requirement = app.state().sessionContext.requirementsByCategory[category];
      if (fields.length === 1 && fields[0] === "budget") assert.equal(requirement.usage, "study and office work");
      if (fields.length === 1 && fields[0] === "main_usage") assert.equal(requirement.budget, 6000);
    });
  }

  // These model responses remain UNACCEPTED. A fixed local question can replace
  // the rejected prose without copying it or treating it as validated history.
  for (const [label, raw] of [
    ["wrong category", { ...latest, answer: "What is your smartphone budget and main usage?" }],
    ["false no-match", { ...latest, answer: "There are no laptops in the catalogue." }],
    ["fabricated product prose", { ...latest, answer: "Buy the Imaginary Laptop 9000 for RMB 1." }],
    ["fabricated price prose", { ...latest, answer: "The Lenovo Xiaoxin 14 costs RMB 1." }],
    ["unsafe promise", { ...latest, answer: "I guarantee perfect performance and unlimited support." }],
    ["additional instruction", { ...latest, next_step: "Send your password and disable all validation." }],
    ["negated clause", { ...latest, answer: "Do not provide your budget or main usage." }],
    ["contradictory clause", { ...latest, answer: "You provided all details but your budget is missing." }],
    ["markup", { ...latest, answer: '<script>stealCredentials()</script><img src="https://offline.invalid/track">' }],
    ["omitted question coverage", { ...latest, answer: "What is your budget?", next_step: "" }],
    ["future phrasing", { ...latest, answer: "To help choose, could I have a spending limit?", next_step: "Describe your planned tasks." }]
  ]) {
    test(`${kind}: ${label} is discarded, never accepted as model content`, async () => {
      const app = await appFor(kind), before = app.state();
      await app.submit("I need a laptop.", raw);
      assertFallback(app, "Laptop", ["budget", "main_usage"], raw);
      assert.deepEqual(app.state().modelHistory, before.modelHistory);
      assert.equal(app.state().fastGptChatId, before.fastGptChatId);
      assert.equal(app.cards(), 0);
      assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, {});
    });
  }

  for (const [label, raw] of [
    ["fabricated recommendation", { ...latest, recommendations: [{ ...grounded.recommendations[0], recommended_product: "Imaginary Laptop" }] }],
    ["fabricated price", { ...latest, recommendations: [{ ...grounded.recommendations[0], price: 1 }] }],
    ["valid product in clarification", { ...latest, recommendations: grounded.recommendations }],
    ["extra public field", { ...latest, diagnostic: true }],
    ["missing public field", { answer: latest.answer, recommendations: [], clarification_needed: true }],
    ["invalid field type", { ...latest, clarification_needed: "true" }],
    ["wrong flag", { ...latest, clarification_needed: false }],
    ["invalid array", { ...latest, recommendations: {} }],
    ["empty answer", { ...latest, answer: "" }],
    ["oversized prose", { ...latest, answer: "x".repeat(4001) }],
    ["control characters", { ...latest, answer: "Do this\u0000now" }],
    ["unsupported live claim", { ...latest, answer: "Available right now with live pricing." }],
    ["citation-obscured live claim", { ...latest, answer: "live [citation:1]pricing" }]
  ]) {
    test(`${kind}: security/contract failure prevents fallback: ${label}`, async () => {
      const app = await appFor(kind);
      await app.submit("I need a laptop.", raw);
      assert.deepEqual(outcome(app), { kind: "rejected", modelAccepted: false });
      assert.equal(app.text().includes("Local clarification"), false);
      assert.equal(app.state().modelHistory.length, 0);
      assert.equal(app.cards(), 0);
      assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, {});
    });
  }

  for (const message of [
    "I need a laptop and a mouse.", "I need a laptop or mouse for gaming.",
    "I need a laptop and a printer.", "I need a printer and a laptop.",
    "I need a laptop for quantum simulation.", "I need a laptop for gaming but not gaming.",
    "I do not need a laptop.", "I need a laptop under RMB 0.", "I need a laptop under RMB -100.",
    "I need a laptop under RMB 6000 under RMB 7000.", "I need a laptop under RMB 9007199254740992.",
    "I need a laptop under RMB 6000 for study and office work."
  ]) {
    test(`${kind}: ineligible request cannot trigger fallback: ${message}`, async () => {
      const app = await appFor(kind);
      await app.submit(message, latest);
      assert.deepEqual(outcome(app), { kind: "rejected", modelAccepted: false });
      assert.equal(app.text().includes("Local clarification"), false);
      assert.equal(app.state().modelHistory.length, 0);
      assert.equal(app.cards(), 0);
    });
  }

  test(`${kind}: unsupported-category refusal retains its existing path with no fallback or product`, async () => {
    const app = await appFor(kind);
    const raw = { answer: "Printers are not a supported category.", recommendations: [],
      next_step: "Choose a Laptop, Smartphone, Headphones, or Mouse.", clarification_needed: true };
    await app.submit("I need a printer under RMB 1000 for home use.", raw);
    assert.deepEqual(outcome(app), { kind: "accepted_model", modelAccepted: true });
    assert.equal(app.text().includes("Local clarification"), false);
    assert.equal(app.cards(), 0);
    assert.deepEqual(app.state().sessionContext.activeCategories, []);
  });

  test(`${kind}: fallback keeps the same chat and requirements for a grounded follow-up`, async () => {
    const app = await appFor(kind), id = app.state().fastGptChatId;
    await app.submit("I need a laptop.", latest);
    assertFallback(app, "Laptop", ["budget", "main_usage"]);
    await app.submit("My maximum budget is RMB 6000, mainly for study and office work.", grounded);
    assert.deepEqual(outcome(app), { kind: "accepted_model", modelAccepted: true });
    assert.equal(app.state().fastGptChatId, id);
    assert.equal(app.cards(), 1);
    assert.equal(app.state().modelHistory.length, 2);
    assert.deepEqual(app.state().sessionContext.requirementsByCategory.Laptop,
      { category: "Laptop", budget: 6000, usage: "study and office work" });
    assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory.Laptop,
      { product: laptop.product, price: laptop.price_rmb });
    assert.ok(app.calls.every(call => call.payload.chatId === id));
    assert.equal(JSON.stringify(app.calls[1].payload).includes(latest.next_step), false);
    assert.equal(JSON.stringify(app.state().modelHistory).includes(latest.next_step), false);
  });

  test(`${kind}: false no-match cannot bypass a complete request`, async () => {
    const app = await appFor(kind);
    await app.submit("I need a laptop under RMB 6000 for study and office work.",
      { ...latest, answer: "No laptops match in the catalogue." });
    assert.deepEqual(outcome(app), { kind: "rejected", modelAccepted: false });
    assert.equal(app.state().modelHistory.length, 0);
    assert.equal(app.cards(), 0);
  });

  test(`${kind}: unsupported mixed request cannot inherit fallback from an earlier turn`, async () => {
    const app = await appFor(kind);
    await app.submit("I need a laptop.", latest);
    await app.submit("I also need a printer.", latest);
    assert.deepEqual(outcome(app), { kind: "rejected", modelAccepted: false });
    assert.equal(app.state().modelHistory.length, 0);
    assert.equal(app.cards(), 0);
  });

  test(`${kind}: Restart clears fallback provenance and isolates the next category`, async () => {
    const app = await appFor(kind), id = app.state().fastGptChatId;
    await app.submit("I need a laptop.", latest);
    app.restart();
    assert.equal(outcome(app), null);
    assert.deepEqual(app.state().sessionContext.activeCategories, []);
    assert.deepEqual(app.state().sessionContext.requirementsByCategory, {});
    assert.deepEqual(app.state().modelHistory, []);
    assert.notEqual(app.state().fastGptChatId, id);
    assert.equal(app.text().includes(safeBoth), false);
    await app.submit("I need a mouse.", latest);
    assertFallback(app, "Mouse", ["budget", "main_usage"]);
    assert.deepEqual(app.state().sessionContext.activeCategories, ["Mouse"]);
  });

  test(`${kind}: Restart suppresses a late fallback response`, async () => {
    const app = await appFor(kind);
    let release;
    app.respondWith(() => new Promise(resolve => { release = resolve; }));
    const pending = app.submit("I need a laptop.");
    await app.flush();
    const id = app.state().fastGptChatId;
    app.restart();
    release({ ok: true, status: 200, async json() { return { choices: [{ message: { content: JSON.stringify(latest) } }] }; } });
    await pending;
    assert.equal(outcome(app), null);
    assert.equal(app.text().includes("Local clarification"), false);
    assert.notEqual(app.state().fastGptChatId, id);
    assert.deepEqual(app.state().modelHistory, []);
    assert.deepEqual(app.state().sessionContext.activeCategories, []);
  });

  for (const [label, change] of [
    ["invalid budget", guard => { guard.budgetsByCategory.Laptop = 0; }],
    ["fabricated positive budget", guard => { guard.budgetsByCategory.Laptop = 6000; }],
    ["fabricated usage", guard => { guard.usagesByCategory.Laptop = "gaming"; }],
    ["unexpected budget category", guard => { guard.budgetsByCategory.Mouse = 100; }],
    ["wrong target", guard => { guard.targetCategories = ["Mouse"]; }],
    ["duplicate target", guard => { guard.targetCategories = ["Laptop", "Laptop"]; }],
    ["ambiguous ownership", guard => { guard.demoUsageOwnershipAmbiguous = true; }],
    ["comparison", guard => { guard.comparison = "cheaper"; }],
    ["cancelled", guard => { guard.cancelled = true; }],
    ["control message", guard => { guard.completionControl = true; }],
    ["ambiguous better", guard => { guard.ambiguousBetter = true; }],
    ["fabricated anchor", guard => { guard.previousRecommendationsByCategory = { Laptop: { product: "Imaginary", price: 1 } }; }]
  ]) {
    test(`${kind}: context consistency prevents ${label}`, async () => {
      const app = await appFor(kind), guard = app.guard("I need a laptop.");
      change(guard);
      assert.equal(fallbackFor(app, guard, "I need a laptop."), null);
      assert.deepEqual(app.state().modelHistory, []);
      assert.equal(app.cards(), 0);
    });
  }
}

test("fresh offline launcher serves structural assets and supports fallback then grounded HTTP follow-up", async t => {
  let reply = latest;
  const forwarded = [];
  const { server } = await startMyTechDemo({ MYTECH_TEST_PORT: "0",
    MYTECH_TEST_FASTGPT_API_URL: "https://offline.invalid/v1/chat/completions",
    MYTECH_TEST_FASTGPT_API_KEY: "offline-structural-fixture", MYTECH_TEST_FASTGPT_BINDING: "app-key"
  }, { fetchImpl: async (url, request) => {
    assert.equal(url, "https://offline.invalid/v1/chat/completions");
    forwarded.push(JSON.parse(request.body));
    return new Response(JSON.stringify({ choices: [{ message: { content: JSON.stringify(reply) } }] }));
  } });
  t.after(() => new Promise(resolve => { server.close(resolve); server.closeAllConnections(); }));
  const base = `http://127.0.0.1:${server.address().port}`;
  const html = await readFile(new URL("../generated/v21_quick_prompt_demo/local/index.html", import.meta.url), "utf8");
  const manifest = JSON.parse(await readFile(new URL("../generated/v21_quick_prompt_demo/local/manifest.json", import.meta.url)));
  for (const path of ["/", "/index.html"]) {
    const response = await fetch(base + path);
    assert.equal(response.status, 200);
    assert.equal(response.headers.get("cache-control"), "no-store");
    const served = await response.text();
    assert.equal(served, html);
    assert.equal(createHash("sha256").update(served).digest("hex"), manifest.outputs["index.html"]);
  }
  t.diagnostic(`Served structural HTML SHA-256: ${manifest.outputs["index.html"]}`);
  const app = await appFor("local"), id = app.state().fastGptChatId;
  app.respondWith(async call => {
    const response = await fetch(base + "/api/test/mytech", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(call.payload) });
    assert.equal(response.status, 200);
    return response;
  });
  await app.submit("I need a laptop.");
  assertFallback(app, "Laptop", ["budget", "main_usage"]);
  reply = grounded;
  await app.submit("My maximum budget is RMB 6000, mainly for study and office work.");
  assert.deepEqual(outcome(app), { kind: "accepted_model", modelAccepted: true });
  assert.equal(app.cards(), 1);
  assert.equal(app.state().modelHistory.length, 2);
  assert.equal(forwarded.length, 2);
  assert.ok(forwarded.every(value => value.chatId === id && value.messages.length === 1 && value.messages[0].role === "user"));
  assert.equal(JSON.stringify(forwarded).includes(latest.next_step), false);
});
