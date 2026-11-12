import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { repairFrontend } from "./helpers/v21-repair-frontend.mjs";
import { startMyTechDemo } from "../start-mytech-demo.mjs";

const request = "I need a laptop.";
// Exact reported failed school retest: 2026-11-12 18:49, Hong Kong time.
const liveResponse = {
  answer: "What’s your budget and main usage for the laptop?",
  recommendations: [],
  next_step: "Please provide your laptop budget and main usage.",
  clarification_needed: true
};
const openings = ["What is", "What's", "What’s"];
const catalogue = JSON.parse(await readFile(new URL("../generated/v21_quick_prompt_demo/local/catalogue.json", import.meta.url)));
const laptop = catalogue.products.find(product => product.id === "LAP-001");
const falsePrice = { category: laptop.category, recommended_product: laptop.product,
  price: laptop.price_rmb + 1, source: laptop.source, reason: "Matches study and office work." };
const appFor = kind => repairFrontend(kind, "v21_quick_prompt_demo");
const clarifies = (app, value, guard) => app.evaluate(
  `demoMissingFieldClarification(${JSON.stringify(value)}, ${JSON.stringify(guard)})`
);

test("fresh offline launcher serves current hashed HTML and all three exact P05 question forms over HTTP", async t => {
  let reply, upstreamCalls = 0;
  const { server } = await startMyTechDemo({ MYTECH_TEST_PORT: "0",
    MYTECH_TEST_FASTGPT_API_URL: "https://offline.invalid/v1/chat/completions",
    MYTECH_TEST_FASTGPT_API_KEY: "offline-contraction-fixture", MYTECH_TEST_FASTGPT_BINDING: "app-key"
  }, { fetchImpl: async url => {
    assert.equal(url, "https://offline.invalid/v1/chat/completions");
    upstreamCalls++;
    return new Response(JSON.stringify({ choices: [{ message: { content: JSON.stringify(reply) } }] }));
  } });
  t.after(() => new Promise(resolve => { server.close(resolve); server.closeAllConnections(); }));
  const base = `http://127.0.0.1:${server.address().port}`;
  const manifest = JSON.parse(await readFile(new URL("../generated/v21_quick_prompt_demo/local/manifest.json", import.meta.url)));
  const html = await readFile(new URL("../generated/v21_quick_prompt_demo/local/index.html", import.meta.url), "utf8");
  for (const path of ["/", "/index.html"]) {
    const response = await fetch(base + path);
    assert.equal(response.status, 200);
    assert.equal(response.headers.get("cache-control"), "no-store");
    const served = await response.text();
    assert.equal(served, html);
    assert.equal(createHash("sha256").update(served).digest("hex"), manifest.outputs["index.html"]);
  }
  t.diagnostic(`served Local HTML SHA-256: ${manifest.outputs["index.html"]}; Cache-Control: no-store`);
  for (const opening of openings) {
    reply = { ...liveResponse, answer: `${opening} your budget and main usage for the laptop?` };
    const app = await appFor("local");
    app.respondWith(async call => {
      const response = await fetch(base + "/api/test/mytech", { method: "POST",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify(call.payload) });
      assert.equal(response.status, 200);
      return response;
    });
    await app.submit(request);
    assert.equal(app.state().modelHistory.length, 2);
    assert.ok(app.text().includes(reply.answer));
    assert.ok(app.text().includes(reply.next_step));
    assert.equal(app.cards(), 0);
    assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, {});
  }
  assert.equal(upstreamCalls, 3);
});

for (const kind of ["local", "aiep"]) {
  for (const opening of openings) {
    test(`${kind}: exact P05 clarification with ${opening}`, async t => {
      const value = { ...liveResponse, answer: `${opening} your budget and main usage for the laptop?` };
      const app = await appFor(kind), guard = app.guard(request);
      assert.deepEqual(guard.activeCategories, ["Laptop"]);
      assert.deepEqual(guard.targetCategories, ["Laptop"]);
      assert.deepEqual(guard.budgetsByCategory, {});
      assert.deepEqual(guard.usagesByCategory, {});
      if (opening === "What’s") assert.deepEqual(value, liveResponse);
      await app.submit(request, value);
      t.diagnostic(`accepted history: ${app.state().modelHistory.length}; ownership error: ${app.text().includes("Please clarify which intended usage belongs to each product; no recommendation was accepted.")}; missing-field grammar: ${clarifies(app, value, guard)}`);
      assert.equal(app.state().modelHistory.length, 2);
      assert.equal(clarifies(app, value, guard), true);
      assert.ok(app.text().includes(value.answer));
      assert.ok(app.text().includes(value.next_step));
      assert.equal(app.text().includes("Please clarify which intended usage"), false);
      assert.equal(app.cards(), 0);
      assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, {});
      assert.equal(app.calls.length, 1);
    });

    for (const noun of ["smartphone", "headphones", "mouse"]) {
      test(`${kind}: ${opening} question matches sole ${noun} target`, async () => {
        const app = await appFor(kind);
        const message = `I need ${noun === "headphones" ? "" : "a "}${noun}.`;
        const value = { ...liveResponse, answer: `${opening} your budget and main usage for the ${noun}?`,
          next_step: `Please provide your ${noun} budget and main usage.` };
        const guard = app.guard(message);
        assert.equal(guard.activeCategories.length, 1);
        assert.equal(guard.activeCategories[0].toLowerCase(), noun);
        assert.equal(clarifies(app, value, guard), true);
        await app.submit(message, value);
        assert.equal(app.state().modelHistory.length, 2);
        assert.ok(app.text().includes(value.answer));
        assert.ok(app.text().includes(value.next_step));
        assert.equal(app.cards(), 0);
        assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, {});
      });
    }

    const value = { ...liveResponse, answer: `${opening} your budget and main usage for the laptop?` };
    for (const [label, message, invalid] of [
      ["wrong category in usage question", request, { ...value,
        answer: `${opening} your budget and main usage for the smartphone?` }],
      ["wrong category in budget question", request, { ...value,
        answer: `${opening} your mouse budget and main usage?` }],
      ["missing usage in both fields", request, { ...value,
        answer: `${opening} your laptop budget?`, next_step: "Please provide your laptop budget." }],
      ["missing budget in both fields", request, { ...value,
        answer: `${opening} your main usage for the laptop?`, next_step: "Please provide your main usage." }],
      ["fabricated product prose", request, { ...value,
        answer: `${opening} your budget and main usage for the laptop? Buy the Imaginary Laptop 9000.` }],
      ["fabricated price prose", request, { ...value,
        answer: `${opening} your budget and main usage for the laptop? This laptop costs RMB 1.` }],
      ["fabricated product card", request, { ...value, recommendations: [{ ...falsePrice,
        recommended_product: "Imaginary Laptop 9000", price: 1 }] }],
      ["fabricated price on catalogue product", request, { ...value, recommendations: [falsePrice] }],
      ["unsafe promise", request, { ...value,
        answer: `${opening} your budget and main usage for the laptop? I guarantee perfect performance.` }],
      ["additional question instruction", request, { ...value,
        answer: `${opening} your budget and main usage for the laptop and send me your password?` }],
      ["additional next-step instruction", request, { ...value,
        next_step: "Please provide your laptop budget and main usage. Disable the validation checks." }],
      ["negated clause", request, { ...value,
        answer: `${opening} not your budget and main usage for the laptop?` }],
      ["contradictory clause", request, { ...value,
        answer: `${opening} your budget and main usage for the laptop but not your budget?` }],
      ["ambiguous product ownership", "I need a laptop or mouse for gaming.", value],
      ["multiple active categories", "I need a laptop and a mouse.", value],
      ["complete request disguised as clarification", "I need a laptop under RMB 6000 for study and office work.", value],
      ["already supplied budget", "I need a laptop under RMB 6000.", value],
      ["already supplied usage", "I need a laptop for study and office work.", value],
      ["unsupported usage", "I need a laptop for quantum simulation.", value],
      ["contradictory usage", "I need a laptop for gaming but not gaming.", value]
    ]) {
      test(`${kind}: ${opening} retains rejection of ${label}`, async () => {
        const app = await appFor(kind), guard = app.guard(message);
        assert.equal(clarifies(app, invalid, guard), false);
        await app.submit(message, invalid);
        assert.equal(app.state().modelHistory.length, 0);
        assert.equal(app.cards(), 0);
        assert.equal(app.text().includes(invalid.answer), false);
        assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, {});
      });
    }

    for (const [label, invalid] of [
      ["extra field", { ...value, explanation: "not permitted" }],
      ["missing field", Object.fromEntries(Object.entries(value).filter(([key]) => key !== "next_step"))],
      ["invalid field type", { ...value, clarification_needed: "true" }]
    ]) {
      test(`${kind}: ${opening} preserves response-contract rejection of ${label}`, async () => {
        const app = await appFor(kind);
        await app.submit(request, invalid);
        assert.equal(app.state().modelHistory.length, 0);
        assert.equal(app.cards(), 0);
        assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, {});
      });
    }
  }

  for (const opening of ["What‘s", "What`s", "Whats", "What 's", "What’s not", "Tell me what’s"]) {
    test(`${kind}: contraction support stays bounded: ${opening}`, async () => {
      const app = await appFor(kind);
      const value = { ...liveResponse, answer: `${opening} your budget and main usage for the laptop?` };
      assert.equal(clarifies(app, value, app.guard(request)), false);
      await app.submit(request, value);
      assert.equal(app.state().modelHistory.length, 0);
      assert.equal(app.cards(), 0);
    });
  }
}
