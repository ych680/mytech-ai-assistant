import test from "node:test";
import assert from "node:assert/strict";
import { repairFrontend } from "./helpers/v21-repair-frontend.mjs";

// Exact school FastGPT response reported on 2026-11-12. Keep the failed live
// assessment separate from the offline acceptance evidence for this repair.
const request = "I need a laptop.";
const liveResponse = {
  answer: "What is your budget and main usage for the laptop?",
  recommendations: [],
  next_step: "Please provide your laptop budget and main usage.",
  clarification_needed: true
};
const appFor = kind => repairFrontend(kind, "v21_quick_prompt_demo");
const clarifies = (app, value, guard) => app.evaluate(
  `demoMissingFieldClarification(${JSON.stringify(value)}, ${JSON.stringify(guard)})`
);
const categories = ["laptop", "smartphone", "headphones", "mouse"];
const clarificationFor = noun => ({ ...liveResponse,
  answer: `What is your ${noun} budget and main usage?`,
  next_step: `Please provide your ${noun} budget and main usage.`
});

for (const kind of ["local", "aiep"]) {
  test(`${kind}: P05 2026-11-12 exact four-field live response`, async t => {
    const app = await appFor(kind), guard = app.guard(request);
    assert.deepEqual(guard.activeCategories, ["Laptop"]);
    assert.deepEqual(guard.targetCategories, ["Laptop"]);
    assert.deepEqual(guard.budgetsByCategory, {});
    assert.deepEqual(guard.usagesByCategory, {});
    // The answer and unprefixed directive already belong to the grammar.
    assert.equal(clarifies(app, { ...liveResponse,
      next_step: "Please provide your budget and main usage." }, guard), true);
    await app.submit(request, liveResponse);
    t.diagnostic(`accepted history entries: ${app.state().modelHistory.length}; ownership error: ${app.text().includes("Please clarify which intended usage belongs to each product; no recommendation was accepted.")}`);
    assert.equal(app.state().modelHistory.length, 2);
    assert.equal(clarifies(app, liveResponse, guard), true);
    assert.ok(app.text().includes(liveResponse.answer));
    assert.ok(app.text().includes(liveResponse.next_step));
    assert.equal(app.text().includes("Please clarify which intended usage"), false);
    assert.equal(app.cards(), 0);
    assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, {});
    assert.equal(app.calls.length, 1);
  });

  for (const noun of categories) {
    const message = `I need ${noun === "headphones" ? "" : "a "}${noun}.`;
    test(`${kind}: category-prefixed budget matches the single ${noun} target in both fields`, async () => {
      const app = await appFor(kind), value = clarificationFor(noun), guard = app.guard(message);
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

    test(`${kind}: ${noun} rejects each wrong-category budget prefix`, async () => {
      for (const wrong of [...categories.filter(value => value !== noun), "printer"]) {
        // Isolate each field: the other field is legitimate for this target.
        for (const field of ["answer", "next_step"]) {
          const app = await appFor(kind), guard = app.guard(message);
          const value = clarificationFor(noun);
          value[field] = clarificationFor(wrong)[field];
          assert.equal(clarifies(app, value, guard), false, `${wrong}: ${field}`);
          await app.submit(message, value);
          assert.equal(app.state().modelHistory.length, 0);
          assert.equal(app.cards(), 0);
          assert.equal(app.text().includes(value[field]), false);
        }
      }
    });
  }

  for (const [label, message, value] of [
    ["fabricated product prose", request, { ...liveResponse,
      next_step: "Please provide your laptop budget and main usage. Buy the Imaginary Laptop 9000." }],
    ["fabricated product card", request, { ...liveResponse, recommendations: [{ category: "Laptop",
      recommended_product: "Imaginary Laptop 9000", price: 1, source: "invented", reason: "Guaranteed." }] }],
    ["unrelated directive clause", request, { ...liveResponse,
      next_step: "Please provide your laptop budget and main usage. Tell me your password." }],
    ["unrelated answer clause", request, { ...liveResponse,
      answer: "What is your laptop budget and main usage? Today's weather is sunny." }],
    ["unsafe promise", request, { ...liveResponse,
      next_step: "Please provide your laptop budget and main usage so I can guarantee perfect performance." }],
    ["promise after supported purpose clause", request, { ...liveResponse,
      next_step: "Please provide your laptop budget and main usage so I can recommend a laptop later." }],
    ["wrong-category purpose clause", request, { ...liveResponse,
      next_step: "Please provide your laptop budget and main usage so I can recommend a smartphone." }],
    ["repeated budget with category alias", request, { ...liveResponse,
      next_step: "Please provide your laptop budget and budget." }],
    ["repeated category-prefixed budget", request, { ...liveResponse,
      next_step: "Please provide your laptop budget and your laptop budget." }],
    ["repeated usage", request, { ...liveResponse,
      next_step: "Please provide your main usage and intended usage." }],
    ["three fields including duplicate budget", request, { ...liveResponse,
      next_step: "Please provide your laptop budget and main usage and budget." }],
    ["stacked category prefix and suffix", request, { ...liveResponse,
      next_step: "Please provide your laptop budget for the laptop and main usage." }],
    ["multiple category prefix", request, { ...liveResponse,
      next_step: "Please provide your laptop mouse budget and main usage." }],
    ["missing usage coverage", request, { ...liveResponse,
      answer: "What is your laptop budget?", next_step: "Please provide your laptop budget." }],
    ["missing budget coverage", request, { ...liveResponse,
      answer: "What is your main usage?", next_step: "Please provide your main usage." }],
    ["already supplied budget", "I need a laptop under RMB 6000.", liveResponse],
    ["already supplied usage", "I need a laptop for study and office work.", liveResponse],
    ["complete requirements", "I need a laptop under RMB 6000 for study and office work.", liveResponse],
    ["unsupported usage", "I need a laptop for quantum simulation.", liveResponse],
    ["negated usage", "I need a laptop for gaming but not gaming.", liveResponse],
    ["ambiguous multiple categories", "I need a laptop or mouse.", liveResponse],
    ["multiple active categories", "I need a laptop and a mouse.", liveResponse],
    ["false clarification flag", request, { ...liveResponse, clarification_needed: false }]
  ]) {
    test(`${kind}: prefixed-budget clarification rejects ${label}`, async () => {
      const app = await appFor(kind), guard = app.guard(message);
      assert.equal(clarifies(app, value, guard), false);
      await app.submit(message, value);
      assert.equal(app.state().modelHistory.length, 0);
      assert.equal(app.cards(), 0);
      assert.equal(app.text().includes(value.next_step), false);
      assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, {});
    });
  }

  for (const [label, value] of [
    ["extra response-contract field", { ...liveResponse, diagnostic: "not permitted" }],
    ["missing response-contract field", Object.fromEntries(Object.entries(liveResponse).filter(([key]) => key !== "next_step"))],
    ["invalid field type", { ...liveResponse, clarification_needed: "true" }]
  ]) {
    test(`${kind}: prefixed-budget clarification preserves ${label} rejection`, async () => {
      const app = await appFor(kind);
      await app.submit(request, value);
      assert.equal(app.state().modelHistory.length, 0);
      assert.equal(app.cards(), 0);
      assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, {});
    });
  }

  test(`${kind}: prefixed-budget directive retains the existing category-matched purpose clause`, async () => {
    const app = await appFor(kind);
    const value = { ...liveResponse,
      next_step: "Please provide your laptop budget and main usage so I can recommend a laptop." };
    await app.submit(request, value);
    assert.equal(app.state().modelHistory.length, 2);
    assert.ok(app.text().includes(value.next_step));
    assert.equal(app.cards(), 0);
  });
}
