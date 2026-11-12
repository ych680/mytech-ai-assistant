import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { repairFrontend } from "./helpers/v21-repair-frontend.mjs";

const fixtures = JSON.parse(await readFile(new URL("./fixtures/p05_live_clarifications_2026_11_12.json", import.meta.url)));
const raw = fixtures[2].response;
const appFor = kind => repairFrontend(kind, "v21_quick_prompt_demo");
const outcome = app => JSON.parse(app.evaluate("JSON.stringify(demoResponseOutcome)"));
const reply = value => ({ ok: true, status: 200, async json() {
  return { choices: [{ message: { content: JSON.stringify(value) } }] };
} });
const visible = element => !element.hidden && (!element.parent || visible(element.parent));
const recoveryButtons = app => app.all().filter(element => element.tagName === "button"
  && element.textContent === "Edit and try again");
const labelFor = app => app.all().find(element => element.textContent === "Local clarification");

const categories = [
  ["Laptop", "study and office work"], ["Desktop", "office"], ["Smartphone", "photography"],
  ["Tablet", "study"], ["Headphones", "music"], ["Monitor", "gaming"],
  ["Smartwatch", "fitness"], ["Mouse", "office"], ["Keyboard", "typing"]
];

for (const kind of ["local", "aiep"]) {
  for (const [category, usage] of categories) {
    const noun = category.toLowerCase(), device = `${category === "Headphones" ? "" : "a "}${noun}`;
    for (const [missing, suffix, expected, fields] of [
      ["both", ".", `What's your maximum budget (RMB), and what will you mainly use the ${noun} for?`, ["budget", "main_usage"]],
      ["budget", ` for ${usage}.`, `What's your maximum budget (RMB) for the ${noun}?`, ["budget"]],
      ["usage", " under RMB 6000.", `What will you mainly use the ${noun} for?`, ["main_usage"]]
    ]) {
      test(`${kind}: concise ${category} question when ${missing} missing`, async () => {
        const app = await appFor(kind), id = app.state().fastGptChatId;
        await app.submit(`I need ${device}${suffix}`, raw);
        const result = outcome(app), label = labelFor(app);
        assert.equal(result.kind, "deterministic_clarification");
        assert.equal(result.modelAccepted, false);
        assert.equal(result.category, category);
        assert.deepEqual(result.missingFields, fields);
        assert.deepEqual(result.output, { answer: expected, next_step: "", recommendations: [], clarification_needed: true });
        assert.ok(label);
        assert.equal(label.tagName, "div");
        assert.equal(label.className, "assistant-label", "reuse the existing subtle label styling");
        assert.equal(label.parent.className, "bubble");
        assert.deepEqual(label.parent.children.filter(visible).map(element => element.textContent), ["Local clarification", expected]);
        assert.equal(label.parent.children.filter(element => element.tagName === "button" && visible(element)).length, 0);
        assert.equal(app.evaluate("activeRecovery"), null);
        for (const button of recoveryButtons(app)) {
          assert.equal(button.hidden, true);
          assert.equal(button.disabled, true);
          await app.click(button); // Even a synthetic hidden-button click is inert.
        }
        assert.equal(app.elements.get("messageInput").value, "");
        assert.equal(app.calls.length, 1);
        assert.equal(app.state().fastGptChatId, id);
        assert.deepEqual(app.state().modelHistory, []);
        assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, {});
        assert.equal(app.cards(), 0);
        for (const text of [raw.answer, raw.next_step, "The model response was not accepted.", "Reply with the missing information to continue."]) {
          assert.equal(label.parent.children.filter(visible).some(element => element.textContent.includes(text)), false);
        }
        const requirement = app.state().sessionContext.requirementsByCategory[category];
        assert.equal(requirement.budget, missing === "usage" ? 6000 : null);
        assert.equal(requirement.usage, missing === "budget" ? usage : null);
      });
    }
  }

  for (const mode of ["network", "http", "timeout", "empty", "invalid-json", "invalid-contract", "non-clarification-validation"]) {
    test(`${kind}: ${mode} failure keeps visible working recovery`, async () => {
      const app = await appFor(kind);
      const message = "I need a laptop under RMB 6000 for study and office work.";
      let release;
      app.respondWith(async () => {
        if (mode === "network") throw new Error("offline network failure");
        if (mode === "http") return { ok: false, status: 502, async json() { return { error: "fixture-only" }; } };
        if (mode === "timeout") return new Promise(resolve => { release = resolve; });
        if (mode === "empty" || mode === "invalid-json") return { ok: true, status: 200,
          async json() { return { choices: [{ message: { content: mode === "empty" ? "" : "{broken" } }] }; } };
        if (mode === "invalid-contract") return reply({ ...raw, diagnostic: true });
        return reply({ ...raw, answer: "No laptops match in the catalogue.", clarification_needed: false });
      });
      const pending = app.submit(message);
      if (mode === "timeout") { await app.flush(); app.expire(); release(reply(raw)); }
      await pending;
      assert.deepEqual(outcome(app), { kind: "rejected", modelAccepted: false });
      const button = recoveryButtons(app).find(visible);
      assert.ok(button);
      assert.equal(button.hidden, false);
      assert.equal(button.disabled, false);
      assert.equal(app.evaluate("activeRecovery.button") === button, true);
      const state = app.state(), calls = app.calls.length;
      app.input("Keep my draft");
      await app.click(button);
      assert.equal(app.elements.get("messageInput").value, "Keep my draft");
      app.input("");
      await app.click(button);
      assert.equal(app.elements.get("messageInput").value, message);
      assert.deepEqual(app.state(), state);
      assert.equal(app.calls.length, calls);
      app.restart();
      await app.click(button);
      assert.equal(app.elements.get("messageInput").value, "");
      assert.equal(app.calls.length, calls);
      assert.equal(button.disabled, true);
      assert.equal(outcome(app), null);
    });
  }

  test(`${kind}: a hidden clarification action does not hide the next genuine error recovery`, async () => {
    const app = await appFor(kind);
    await app.submit("I need a laptop.", raw);
    const hidden = recoveryButtons(app)[0];
    assert.equal(hidden.hidden, true);
    app.respondWith(async () => { throw new Error("offline network failure"); });
    await app.submit("Under RMB 6000 for study and office work.");
    const visibleButton = recoveryButtons(app).find(visible);
    assert.ok(visibleButton);
    assert.notEqual(visibleButton, hidden);
    await app.click(hidden);
    assert.equal(app.elements.get("messageInput").value, "");
    await app.click(visibleButton);
    assert.equal(app.elements.get("messageInput").value, "Under RMB 6000 for study and office work.");
  });

  test(`${kind}: Restart suppresses late failure recovery after a local clarification`, async () => {
    const app = await appFor(kind);
    await app.submit("I need a laptop.", raw);
    let reject;
    app.respondWith(() => new Promise((_resolve, no) => { reject = no; }));
    const pending = app.submit("Under RMB 6000 for study and office work.");
    await app.flush();
    app.restart();
    reject(new Error("late offline failure"));
    await pending;
    assert.equal(outcome(app), null);
    assert.equal(recoveryButtons(app).length, 0);
    assert.equal(labelFor(app), undefined);
    assert.deepEqual(app.state().modelHistory, []);
    assert.deepEqual(app.state().sessionContext.activeCategories, []);
  });
}
