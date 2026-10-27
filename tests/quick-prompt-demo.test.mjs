import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { repairFrontend } from "./helpers/v21-repair-frontend.mjs";
import { createTestAdapter } from "../mytech_v2_1_test_adapter.mjs";

const master = JSON.parse(await readFile(new URL("../catalogue/mytech_products_v2_1_test.json", import.meta.url), "utf8"));
const adapter = await createTestAdapter(fileURLToPath(new URL("../generated/v21_quick_prompt_demo/local/", import.meta.url)));
// Deliberately independent of the generator configuration: these are the approved texts.
const starters = [
  ["Gaming Setup ×2", "I need a laptop under ¥6,000 for gaming and a mouse under ¥300 for gaming.", ["LAP-005", "MOU-002"]],
  ["Study Laptop", "I need a laptop under ¥7,000 for study and office work.", ["LAP-001"]],
  ["ANC Headphones", "I need headphones under ¥1,200 for music, commuting, and noise cancellation.", ["AUD-005"]],
  ["Gaming Smartphone", "I need a smartphone under ¥3,000 for gaming.", ["PHO-005"]]
];
const product = id => master.products.find(p => p.id === id);
const rec = id => { const p = product(id); return { category: p.category, recommended_product: p.product, price: p.price_rmb, source: p.source, reason: "Matches the saved usage and budget." }; };
const output = (ids = [], answer = "Reference recommendations.", clarification = false) => ({ answer, recommendations: ids.map(rec), next_step: "Would you like to change your requirements?", clarification_needed: clarification });
const clarification = { answer: "What is your maximum budget and main usage?", recommendations: [], next_step: "Please provide your budget and intended usage.", clarification_needed: true };
const panel = app => app.all().find(e => e.className === "demo-followup");
const actions = app => panel(app)?.children.find(e => e.className === "demo-actions").children || [];
const select = app => panel(app)?.children.find(e => e.className === "demo-category")?.children[0];
const examples = app => app.all().find(e => e.className === "demo-examples");
const exampleButtons = app => examples(app).children.find(e => e.className === "demo-actions").children;
const message = (app, index = app.calls.length - 1) => app.calls[index].payload.message ?? app.calls[index].payload.messages[0].content;
const response = value => ({ ok: true, status: 200, async json() { return { choices: [{ message: { content: JSON.stringify(value) } }] }; } });
const appFor = kind => repairFrontend(kind, "v21_quick_prompt_demo");
async function seed(app, index = 1) { await app.submit(starters[index][1], output(starters[index][2])); }

for (const kind of ["local", "aiep"]) {
  for (const [index, [label, text, ids]] of starters.entries()) {
    test(`${kind}: ${label} clicks submit the exact approved text once`, async () => {
      const app = await appFor(kind);
      assert.equal(app.calls.length, 0);
      assert.equal(app.prompts.length, 4);
      assert.deepEqual(app.prompts.map(b => b.textContent), starters.map(s => s[0]));
      app.setReply(output(ids));
      await app.click(app.prompts[index]);
      assert.equal(app.calls.length, 1);
      assert.equal(message(app), text);
      assert.equal(app.cards(), ids.length);
      assert.ok(panel(app));
      assert.equal(app.evaluate("isGenerating"), false);
      const guard = app.guard(text);
      assert.equal(adapter.validateCompletionTurn(output(ids), guard, [], text).valid, true);
    });
  }

  for (const [index, phrase, next] of [[0, "a cheaper", "LAP-004"], [1, "a more expensive", "LAP-002"], [2, "another", "LAP-002"]]) {
    test(`${kind}: Study Laptop ${phrase} keeps usage, hard budget and FastGPT ID`, async () => {
      const app = await appFor(kind); await seed(app);
      const before = app.state();
      assert.equal(select(app), undefined);
      assert.deepEqual(actions(app).map(b => b.textContent), ["Cheaper", "More Expensive", "Another Option"]);
      assert.ok(actions(app).every(b => !b.disabled));
      app.setReply(output([next]));
      await app.click(actions(app)[index]);
      assert.equal(message(app), `Can you recommend ${phrase} laptop?`);
      const after = app.state();
      assert.equal(after.fastGptChatId, before.fastGptChatId);
      assert.deepEqual(after.sessionContext.requirementsByCategory, before.sessionContext.requirementsByCategory);
      assert.equal(after.sessionContext.requirementsByCategory.Laptop.budget, 7000);
      assert.equal(after.sessionContext.lastRecommendationsByCategory.Laptop.product, product(next).product);
      assert.equal(app.cards(), 2);
      assert.equal(app.calls.length, 2, "visibility never submits automatically");
    });
  }

  test(`${kind}: multi-product selector starts empty and selects only latest valid categories without requests`, async () => {
    const app = await appFor(kind); await seed(app, 0);
    const selector = select(app), oldActions = actions(app), before = app.state();
    assert.equal(selector.value, "");
    assert.equal(selector.attributes["aria-label"], "Category to compare");
    assert.deepEqual(selector.children.map(o => o.value), ["", "Laptop", "Mouse"]);
    assert.ok(oldActions.every(b => b.disabled));
    await app.click(oldActions[0]); assert.equal(app.calls.length, 1);
    selector.value = "Smartphone"; selector.dispatch("change");
    assert.ok(oldActions.every(b => b.disabled));
    selector.value = "Mouse"; selector.dispatch("change");
    assert.equal(app.calls.length, 1);
    assert.ok(oldActions.every(b => !b.disabled));
    app.setReply(output(["MOU-004"])); await app.click(oldActions[0]);
    assert.equal(message(app), "Can you recommend a cheaper mouse?");
    assert.equal(app.state().fastGptChatId, before.fastGptChatId);
    assert.deepEqual(app.state().sessionContext.requirementsByCategory, before.sessionContext.requirementsByCategory);
    assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory.Laptop, before.sessionContext.lastRecommendationsByCategory.Laptop);
    assert.equal(app.state().sessionContext.lastRecommendationsByCategory.Mouse.price, 109);
    await app.click(oldActions[1]); assert.equal(app.calls.length, 2, "retained old controls are inert");
  });

  test(`${kind}: partial output exposes only actually recommended categories`, async () => {
    const app = await appFor(kind);
    await app.submit("I need a laptop under RMB 6000 for gaming and headphones under RMB 800 for music and commuting, noise cancellation.", output(["LAP-005"], "No Headphones match the requirements."));
    assert.ok(panel(app)); assert.equal(select(app), undefined);
    assert.equal(app.evaluate("demoFollowup.category"), "Laptop");
  });

  test(`${kind}: drafts disable follow-ups, including synthetic click and selection events`, async () => {
    const app = await appFor(kind); await seed(app, 0);
    const selector = select(app); selector.value = "Mouse"; selector.dispatch("change");
    app.input(" ");
    assert.equal(selector.disabled, true); assert.ok(actions(app).every(b => b.disabled));
    await app.click(actions(app)[0]);
    assert.equal(app.calls.length, 1); assert.equal(app.elements.get("messageInput").value, " ");
    app.input(""); assert.ok(actions(app).every(b => !b.disabled));
  });

  test(`${kind}: changed requirements invalidate a saved follow-up snapshot`, async () => {
    const app = await appFor(kind); await seed(app);
    const button = actions(app)[0];
    app.guard("I need a laptop under RMB 6000 for gaming.");
    await app.click(button);
    assert.equal(app.calls.length, 1); assert.equal(panel(app), undefined);
  });

  test(`${kind}: unavailable comparison is canonical no-match and retains the validated anchor`, async () => {
    const app = await appFor(kind);
    await app.submit("I need a laptop under RMB 6000 for gaming.", output(["LAP-005"]));
    const before = app.state();
    app.setReply(output([], "No more expensive Laptop matches."));
    await app.click(actions(app)[1]);
    assert.equal(panel(app), undefined);
    assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, before.sessionContext.lastRecommendationsByCategory);
    assert.equal(app.state().fastGptChatId, before.fastGptChatId);
    assert.match(app.text(), /within RMB 6000/);
    assert.doesNotMatch(app.text(), /couldn't safely validate/);
  });

  for (const [label, ids, action] of [["over-budget upgrade", ["LAP-006"], 1], ["wrong usage", ["LAP-003"], 2], ["same identity alternative", ["LAP-001"], 2], ["empty eligible omission", [], 2]]) {
    test(`${kind}: ${label} cannot replace anchors or expose follow-ups`, async () => {
      const app = await appFor(kind); await seed(app);
      const before = app.state();
      app.setReply(output(ids, "No Laptop matches."));
      await app.click(actions(app)[action]);
      assert.equal(panel(app), undefined);
      assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, before.sessionContext.lastRecommendationsByCategory);
      assert.equal(app.cards(), 1);
      assert.match(app.text(), /couldn't safely validate/);
    });
  }

  test(`${kind}: cheaper and more-expensive enforce strict direction inside the unchanged cap`, async () => {
    for (const [action, id] of [[0, "LAP-002"], [1, "LAP-004"], [0, "LAP-001"], [1, "LAP-001"]]) {
      const app = await appFor(kind); await seed(app);
      const before = app.state(); app.setReply(output([id]));
      await app.click(actions(app)[action]);
      assert.equal(panel(app), undefined);
      assert.deepEqual(app.state().sessionContext, before.sessionContext);
      assert.equal(app.cards(), 1);
    }
  });

  test(`${kind}: fresh missing-field clarification displays the actual question and saves no product`, async () => {
    const app = await appFor(kind);
    const before = app.state().fastGptChatId;
    await app.submit("I need a laptop.", clarification);
    assert.match(app.text(), /What is your maximum budget and main usage/);
    assert.doesNotMatch(app.text(), /Please clarify which intended usage/);
    assert.equal(panel(app), undefined); assert.equal(app.cards(), 0);
    assert.equal(app.state().fastGptChatId, before);
    assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, {});
    await app.submit("Under RMB 7000 for study and office work.", output(["LAP-001"]));
    assert.ok(panel(app)); assert.equal(app.cards(), 1);
  });

  for (const [label, text, value] of [
    ["acknowledgement", "I need a laptop.", { ...clarification, answer: "Got it.", next_step: "I have the information." }],
    ["deferral", "I need a laptop.", { ...clarification, answer: "I will recommend a laptop. What budget and usage?" }],
    ["product injection", "I need a laptop.", { ...clarification, recommendations: [rec("LAP-001")] }],
    ["wrong clarification flag", "I need a laptop.", { ...clarification, clarification_needed: false }],
    ["extra contract field", "I need a laptop.", { ...clarification, diagnostic: true }],
    ["false no-match mixed with question", "I need a smartphone.", { ...clarification, answer: "No Smartphone matches. What budget and usage?" }],
    ["unknown usage", "I need a laptop for quantum simulation.", clarification],
    ["contradictory usage", "I need a laptop for gaming but not gaming.", clarification],
    ["ambiguous ownership", "I need a laptop or mouse for gaming.", clarification],
    ["complete request acknowledgement", starters[1][1], output([], "Got it! I now have all the information.")],
    ["false no-match", starters[1][1], output([], "No Laptop matches.")]
  ]) {
    test(`${kind}: clarification correction rejects ${label}`, async () => {
      const app = await appFor(kind); await app.submit(text, value);
      assert.equal(panel(app), undefined); assert.equal(app.cards(), 0);
      assert.equal(app.state().modelHistory.length, 0);
      assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, {});
    });
  }

  test(`${kind}: Help and missing-budget clarification hide controls while retaining anchors`, async () => {
    const app = await appFor(kind); await seed(app);
    const anchors = app.state().sessionContext.lastRecommendationsByCategory;
    await app.submit("What products can you recommend?", output([], "I support nine categories."));
    assert.equal(panel(app), undefined);
    assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, anchors);
    await app.submit("I need headphones for music.", { ...clarification, answer: "What is your maximum budget?", next_step: "Please provide your budget." });
    assert.equal(panel(app), undefined); assert.match(app.text(), /What is your maximum budget/);
    assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, anchors);
  });

  test(`${kind}: a missing-usage question preserves a known budget`, async () => {
    const app = await appFor(kind);
    await app.submit("I need a laptop under RMB 7000.", { ...clarification, answer: "What is your main usage?", next_step: "Please specify the intended usage." });
    assert.match(app.text(), /What is your main usage/);
    assert.doesNotMatch(app.text(), /Please clarify which intended usage/);
    assert.equal(app.state().sessionContext.requirementsByCategory.Laptop.budget, 7000);
    assert.equal(app.state().modelHistory.length, 2);
    assert.equal(panel(app), undefined);
  });

  const reviewedFailures = [
    ["exact acknowledgement without clarification", "I understand what your budget and usage are.", "I have all the details."],
    ["exact false catalogue no-match", "No laptops match in the MyTech test catalogue. What is your budget and main usage?", "Please provide your budget and intended usage."],
    ["exact fabricated product prose", "I recommend the Imaginary Laptop for RMB 1. What is your budget and main usage?", "Please provide your budget and intended usage."]
  ];
  for (const [label, answer, next_step] of reviewedFailures) {
    test(`${kind}: Phase4C rejects ${label} before display or validated history`, async () => {
      const app = await appFor(kind);
      const id = app.state().fastGptChatId;
      await app.submit("I need a laptop.", { answer, next_step, recommendations: [], clarification_needed: true });
      assert.equal(app.state().modelHistory.length, 0);
      assert.equal(app.cards(), 0); assert.equal(panel(app), undefined);
      assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, {});
      assert.equal(app.state().fastGptChatId, id);
      assert.equal(app.text().includes(answer), false);
      assert.equal(app.text().includes(next_step), false);
      assert.ok(app.all().some(e => e.textContent === "Edit and try again"));
    });
  }

  for (const [label, request, answer, next_step] of [
    ["coordinated budget and use questions", "I need a laptop.", "What is your budget, and what will you mainly use the laptop for?", ""],
    ["polite combined request", "I need a laptop.", "Could you tell me your budget and intended usage?", ""],
    ["bounded category-specific neutral offer", "I need a laptop.", "I can help you choose a laptop. What is your budget and main usage?", "Please provide your budget and intended usage."],
    ["neutral acknowledgement plus actual question", "I need a laptop.", "Sure!", "Could you tell me your budget and intended usage?"],
    ["separate complete questions", "I need a laptop.", "What is your budget? What is your main usage?", ""],
    ["category-specific missing budget", "I need a laptop for gaming.", "What is your budget for the laptop?", "Please provide your maximum budget in RMB."],
    ["category-specific missing usage", "I need a laptop under RMB 7000.", "What will you mainly use the laptop for?", "Please specify the intended usage for your laptop."],
    ["Headphones missing budget", "I need headphones for music.", "What is your maximum budget for the headphones?", "Please share your budget."],
    ["Smartphone missing usage", "I need a smartphone under RMB 3000.", "What will you use the smartphone for?", "Please specify your intended usage."],
    ["Mouse missing budget", "I need a mouse for gaming.", "How much can you spend on your mouse?", "Please tell me your budget."]
  ]) {
    test(`${kind}: Phase4C preserves ${label}`, async () => {
      const app = await appFor(kind);
      const before = app.state().fastGptChatId;
      await app.submit(request, { answer, next_step, recommendations: [], clarification_needed: true });
      assert.equal(app.state().modelHistory.length, 2);
      assert.match(app.state().modelHistory.at(-1).content, /"clarification_needed":true/);
      assert.ok(app.text().includes(answer));
      assert.equal(app.cards(), 0); assert.equal(panel(app), undefined);
      assert.equal(app.state().fastGptChatId, before);
      assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, {});
    });
  }

  for (const [label, request, answer, next_step] of [
    ["safe question then invented product", "I need a laptop.", "What is your budget and main usage? I recommend the Imaginary Laptop for RMB 1.", ""],
    ["safe question then plural no-match", "I need a laptop.", "What is your budget and main usage? There are no laptops in the catalogue.", ""],
    ["fabrication only in next_step", "I need a laptop.", "What is your budget and main usage?", "Buy the Imaginary Laptop for RMB 1."],
    ["no-match only in next_step", "I need a laptop.", "What is your budget and main usage?", "No laptops match in the MyTech test catalogue."],
    ["misleading next_step", "I need a laptop.", "What is your budget and main usage?", "I have all the details."],
    ["deferred recommendation next_step", "I need a laptop.", "What is your budget and main usage?", "I will find a suitable laptop for you."],
    ["future promise with embedded question words", "I need a laptop.", "What is your budget and main usage?", "Tell me your budget and usage so I can recommend a laptop later."],
    ["embedded interrogative declaration", "I need a laptop.", "I know what your budget and usage are?", ""],
    ["bare question mark", "I need a laptop.", "Budget and usage?", ""],
    ["unrelated prose", "I need a laptop.", "What is your budget and main usage? The weather is sunny.", ""],
    ["negated question", "I need a laptop.", "What is your budget and main usage? Do not provide your budget.", ""],
    ["category mismatch", "I need a laptop.", "What is your budget and main usage for your smartphone?", ""],
    ["wrong-category neutral offer", "I need a laptop.", "I can help you choose a smartphone. What is your budget and main usage?", ""],
    ["price embedded in a question", "I need a laptop.", "What is your budget of RMB 8000 and main usage?", ""],
    ["only one of two missing fields requested", "I need a laptop.", "What is your budget?", ""],
    ["already supplied budget requested again", "I need a laptop under RMB 7000.", "What is your budget and main usage?", ""],
    ["already supplied usage requested again", "I need a laptop for gaming.", "What is your budget and main usage?", ""],
    ["budget-only unsafe next_step", "I need a laptop for gaming.", "What is your budget?", "I recommend the Imaginary Laptop for RMB 1."],
    ["unsupported current usage", "I need a laptop for quantum simulation.", "What is your budget?", ""],
    ["contradictory current usage", "I need a laptop for gaming but not gaming.", "What is your budget?", ""],
    ["ambiguous current ownership", "I need a laptop or mouse for gaming.", "What is your budget?", ""],
    ["multiple incomplete targets", "I need a laptop and a mouse.", "What is your budget and main usage?", ""],
    ["complete request disguised as clarification", starters[1][1], "What is your budget and main usage?", ""]
  ]) {
    test(`${kind}: Phase4C fails safely for ${label}`, async () => {
      const app = await appFor(kind);
      await app.submit(request, { answer, next_step, recommendations: [], clarification_needed: true });
      assert.equal(app.state().modelHistory.length, 0);
      assert.equal(app.cards(), 0); assert.equal(panel(app), undefined);
      assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, {});
      assert.equal(app.text().includes(answer), false);
      if (next_step) assert.equal(app.text().includes(next_step), false);
    });
  }

  test(`${kind}: Phase4C rejection retains anchors; Restart and a later valid request recover`, async () => {
    const app = await appFor(kind);
    await app.submit("I need a smartphone under RMB 3000 for gaming.", output(["PHO-005"]));
    const before = app.state();
    const answer = reviewedFailures[2][1], next_step = reviewedFailures[2][2];
    await app.submit("I need a laptop.", { answer, next_step, recommendations: [], clarification_needed: true });
    assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, before.sessionContext.lastRecommendationsByCategory);
    assert.deepEqual(app.state().modelHistory, before.modelHistory);
    assert.equal(app.state().fastGptChatId, before.fastGptChatId);
    assert.equal(app.cards(), 1); assert.equal(panel(app), undefined);
    await app.submit("Under RMB 7000 for study and office work.", output(["LAP-001"]));
    assert.equal(app.cards(), 2); assert.ok(panel(app));
    assert.equal(app.state().modelHistory.length, before.modelHistory.length + 2);
    app.restart();
    assert.deepEqual(app.state().modelHistory, []);
    assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, {});
    assert.notEqual(app.state().fastGptChatId, before.fastGptChatId);
    await app.submit("I need a laptop.", { ...clarification, answer: "Could you tell me your budget and intended usage?" });
    assert.equal(app.state().modelHistory.length, 2);
    await app.submit("Under RMB 7000 for study and office work.", output(["LAP-001"]));
    assert.equal(app.cards(), 1); assert.ok(panel(app));
  });

  test(`${kind}: failed new requirements cannot revive previous successful controls`, async () => {
    const app = await appFor(kind); await seed(app);
    const previous = app.state().sessionContext.lastRecommendationsByCategory;
    await app.submit("I need a laptop under RMB 6000 for quantum simulation.", output(["LAP-001"]));
    assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, previous);
    assert.equal(panel(app), undefined);
    await app.submit("What products can you recommend?", output([], "I support nine categories."));
    assert.equal(panel(app), undefined);
  });

  test(`${kind}: More Examples toggles locally and submits exact payloads without restarting`, async () => {
    const app = await appFor(kind), details = examples(app);
    assert.equal(details.tagName, "details"); assert.equal(details.open, false);
    assert.equal(details.children[0].tagName, "summary");
    assert.equal(details.children[0].textContent, "More Examples");
    details.open = true; details.dispatch("toggle"); details.open = false; details.dispatch("toggle");
    assert.equal(app.calls.length, 0);
    assert.match(app.text(), /fresh-conversation example/);
    const id = app.state().fastGptChatId;
    app.setReply(clarification); await app.click(exampleButtons(app)[0]);
    assert.equal(message(app), "I need a laptop."); assert.equal(app.state().fastGptChatId, id);
    assert.equal(panel(app), undefined);
    app.setReply(output([], "No Headphones match the requirements.")); await app.click(exampleButtons(app)[1]);
    assert.equal(message(app), "I need headphones under ¥800 for music, commuting, and noise cancellation.");
    assert.equal(panel(app), undefined); assert.match(app.text(), /within RMB 800/);
    assert.equal(app.state().fastGptChatId, id);
  });

  test(`${kind}: missing example does not erase existing Laptop requirements`, async () => {
    const app = await appFor(kind); await seed(app);
    const before = app.state(); app.setReply(output(["LAP-001"]));
    await app.click(exampleButtons(app)[0]);
    assert.deepEqual(app.state().sessionContext.requirementsByCategory, before.sessionContext.requirementsByCategory);
    assert.equal(app.state().fastGptChatId, before.fastGptChatId);
  });

  test(`${kind}: generation blocks concurrent starter, example and stale follow-up clicks`, async () => {
    const app = await appFor(kind); await seed(app);
    const old = actions(app)[0]; let resolve;
    app.respondWith(() => new Promise(yes => { resolve = yes; }));
    const pending = app.submit("Can you recommend a cheaper laptop?"); await app.flush();
    assert.equal(panel(app), undefined); assert.equal(app.evaluate("isGenerating"), true);
    await app.click(old); await app.click(app.prompts[0]); await app.click(exampleButtons(app)[0]);
    assert.equal(app.calls.length, 2);
    resolve(response(output(["LAP-004"]))); await pending;
    assert.ok(panel(app)); assert.equal(app.cards(), 2);
  });

  for (const mode of ["success", "failure", "timeout"]) {
    test(`${kind}: Restart prevents stale ${mode} from restoring follow-ups or recovery`, async () => {
      const app = await appFor(kind); await seed(app);
      const old = actions(app)[0], oldExample = exampleButtons(app)[0], before = app.state();
      let resolve, reject;
      app.respondWith(() => new Promise((yes, no) => { resolve = yes; reject = no; }));
      const pending = app.submit("Can you recommend a cheaper laptop?"); await app.flush();
      if (mode === "timeout") app.expire();
      app.restart();
      assert.equal(app.calls.at(-1).signal.aborted, true);
      if (mode === "failure") reject(new Error("offline failure")); else resolve(response(output(["LAP-004"])));
      await pending;
      assert.equal(panel(app), undefined); assert.equal(app.cards(), 0);
      assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, {});
      assert.deepEqual(app.state().sessionContext.requirementsByCategory, {});
      assert.equal(app.state().modelHistory.length, 0);
      assert.notEqual(app.state().fastGptChatId, before.fastGptChatId);
      assert.equal(examples(app).open, false);
      await app.click(old); await app.click(oldExample);
      assert.equal(app.calls.length, 2);
      assert.equal(app.all().filter(e => e.className === "recovery-button" && e.textContent === "Edit and try again").length, 0);
    });
  }

  test(`${kind}: a stale response cannot replace a newer successful conversation`, async () => {
    const app = await appFor(kind); await seed(app);
    let resolve;
    app.respondWith(() => new Promise(yes => { resolve = yes; }));
    const pending = app.submit("Can you recommend a cheaper laptop?"); await app.flush();
    app.restart(); app.setReply(output(["PHO-005"]));
    await app.click(app.prompts[3]);
    const currentPanel = panel(app), currentState = app.state();
    resolve(response(output(["LAP-004"]))); await pending;
    assert.equal(panel(app), currentPanel);
    assert.equal(app.evaluate("demoFollowup.category"), "Smartphone");
    assert.deepEqual(app.state(), currentState);
    assert.equal(app.cards(), 1);
  });

  test(`${kind}: an old completion cannot enable controls during a newer pending request`, async () => {
    const app = await appFor(kind); let first, second;
    app.respondWith(() => new Promise(yes => { first = yes; }));
    const old = app.submit(starters[1][1]); await app.flush(); app.restart();
    app.respondWith(() => new Promise(yes => { second = yes; }));
    const current = app.submit(starters[3][1]); await app.flush();
    first(response(output(["LAP-001"]))); await old;
    assert.equal(app.evaluate("isGenerating"), true);
    assert.equal(panel(app), undefined); assert.ok(app.prompts.every(b => b.disabled));
    second(response(output(["PHO-005"]))); await current;
    assert.equal(app.evaluate("isGenerating"), false);
    assert.equal(app.evaluate("demoFollowup.category"), "Smartphone");
  });

  test(`${kind}: timeout hides follow-ups and retains anchors and recovery`, async () => {
    const app = await appFor(kind); await seed(app);
    const before = app.state(); let resolve;
    app.respondWith(() => new Promise(yes => { resolve = yes; }));
    const pending = app.submit("Can you recommend a cheaper laptop?"); await app.flush();
    app.expire(); resolve(response(output(["LAP-004"]))); await pending;
    assert.equal(panel(app), undefined); assert.match(app.text(), /timed out/);
    assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, before.sessionContext.lastRecommendationsByCategory);
    assert.equal(app.state().fastGptChatId, before.fastGptChatId);
    assert.ok(app.all().some(e => e.textContent === "Edit and try again"));
  });

  for (const mode of ["empty", "malformed", "transport"]) {
    test(`${kind}: ${mode} failure hides controls and preserves the recovery path`, async () => {
      const app = await appFor(kind); await seed(app);
      const before = app.state();
      app.respondWith(async () => {
        if (mode === "transport") throw new Error("offline transport");
        return { ok: true, async json() { return { choices: [{ message: { content: mode === "empty" ? "" : "{broken" } }] }; } };
      });
      await app.submit("Can you recommend another laptop?");
      assert.equal(panel(app), undefined);
      assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, before.sessionContext.lastRecommendationsByCategory);
      const recovery = app.all().find(e => e.textContent === "Edit and try again");
      assert.ok(recovery); await app.click(recovery);
      assert.equal(app.elements.get("messageInput").value, "Can you recommend another laptop?");
      assert.equal(app.calls.length, 2);
    });
  }

  test(`${kind}: native keyboard handler preserves Shift+Enter and IME, sends on Enter`, async () => {
    const app = await appFor(kind), input = app.elements.get("messageInput");
    app.input(starters[1][1]); app.setReply(output(["LAP-001"]));
    input.dispatch("keydown", { key: "Enter", shiftKey: true });
    input.dispatch("keydown", { key: "Enter", isComposing: true });
    assert.equal(app.calls.length, 0);
    let prevented = false; input.dispatch("keydown", { key: "Enter", preventDefault() { prevented = true; } });
    await app.flush(); assert.equal(prevented, true); assert.equal(app.calls.length, 1);
    assert.equal(message(app), starters[1][1]);
    assert.ok(actions(app).every(b => b.type === "button"));
  });
}
