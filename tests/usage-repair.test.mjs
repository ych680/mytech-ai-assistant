// Shared fixtures execute the actual Original repair code, Node adapter and
// both complete generated frontends. Every provider response is in memory.
import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { Script, createContext } from "node:vm";
import { createTestAdapter } from "../mytech_v2_1_test_adapter.mjs";
import { createTestServer, testServerConfig } from "../mytech_v2_1_test_server.mjs";
import { repairFrontend as packageFrontend } from "./helpers/v21-repair-frontend.mjs";

const root = new URL("../", import.meta.url);
const packageName = process.env.MYTECH_REPAIR_PACKAGE || "v21_multiproduct_usage_fix";
assert.ok(["v21_multiproduct_usage_fix", "v21_completion_fix", "v21_quick_prompt_demo"].includes(packageName));
const repairFrontend = kind => packageFrontend(kind, packageName);
const directory = new URL(`generated/${packageName}/local/`, root);
const fixtures = JSON.parse(await readFile(new URL("tests/fixtures/v21_usage_repair.json", root), "utf8"));
const master = JSON.parse(await readFile(new URL("catalogue/mytech_products_v2_1_test.json", root), "utf8"));
const graph = JSON.parse(await readFile(new URL("mytech-fastgpt-workflow-v2_1-TEST.json", directory), "utf8"));
const node = graph.nodes.find(item => item.nodeId === "fakNM8mmlYmewx67");
const code = node.inputs.find(item => item.key === "code").value;
const script = new Script(code + "\nmain(input);");
const adapter = await createTestAdapter(fileURLToPath(directory));
const product = id => master.products.find(item => item.id === id);
const rec = id => { const p = product(id); return { category: p.category, recommended_product: p.product,
  price: p.price_rmb, source: p.source, reason: "Matches the recorded catalogue usage and independent hard budget." }; };
const output = c => ({ answer: c.answer, recommendations: c.products.map(rec), next_step: "Keep each budget or revise the unmatched requirements?", clarification_needed: false });
const input = (c, reply = output(c), previous = []) => ({ raw_json: JSON.stringify(reply), active_requests: structuredClone(c.requests), previous_recommendations: structuredClone(previous), follow_up_intent: "none" });
function execute(value) {
  const copy = structuredClone(value), context = createContext({ input: copy }, { codeGeneration: { strings: false, wasm: false } });
  const result = JSON.parse(JSON.stringify(script.runInContext(context, { timeout: 1000 })));
  assert.deepEqual(context.input, value, "validator must not mutate its input");
  return result;
}
const caseById = id => fixtures.cases.find(item => item.id === id);

for (const c of fixtures.cases) test(`usage repair cross-layer fixture: ${c.id}`, async () => {
  const value = input(c), result = execute(value);
  assert.equal(result.validation_ok, c.valid, result.validation_error);
  assert.equal(adapter.validate(value).valid, c.valid);
  const states = [];
  for (const kind of ["local", "aiep"]) {
    const app = await repairFrontend(kind), guard = app.guard(c.message);
    assert.deepEqual(guard.budgetsByCategory, Object.fromEntries(c.requests.map(r => [r.category, r.budget])));
    for (const request of c.requests) assert.equal(guard.usagesByCategory[request.category].toLowerCase(), request.main_usage.toLowerCase());
    assert.equal(guard.usageClarificationNeeded, false);
    assert.equal(app.validate(output(c), guard).valid, c.valid, `${kind}: ${JSON.stringify(app.validate(output(c), guard))}`);
    states.push({ budgets: guard.budgetsByCategory, usages: guard.usagesByCategory });
  }
  assert.deepEqual(states[0], states[1]);
});

test("exact paired live inputs assign the same usages/budgets and render both complete cards", async () => {
  const pair = fixtures.paired_live_control;
  const c = caseById("shared-gaming-1000-paired-failure");
  assert.equal(c.message, pair.failed_input);
  assert.equal(caseById("explicit-gaming-1000-paired-success").message, pair.successful_input);
  for (const kind of ["local", "aiep"]) {
    const guards = [];
    for (const message of [pair.failed_input, pair.successful_input]) {
      const app = await repairFrontend(kind);
      guards.push(app.guard(message));
      await app.submit(message, output(c));
      assert.equal(app.cards(), 2);
      assert.match(app.text(), /4,999/); assert.match(app.text(), /229/);
      for (const id of c.products) { assert.ok(app.text().includes(product(id).product)); assert.ok(app.text().includes(product(id).source)); }
      assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, {
        Laptop: { product: product("LAP-005").product, price: 4999 }, Mouse: { product: product("MOU-002").product, price: 229 }
      });
    }
    assert.deepEqual(guards[0], guards[1]);
  }
  assert.equal(fixtures.live_evidence.code_run_2_output_captured, false);
  assert.equal(fixtures.live_evidence.aiep_response_identical_to_fastgpt_run_verified, false);
});

test("Headphones no-match is computed from all requirements; the budget is never widened", () => {
  const context = createContext({ master, eligible: [] });
  new Script(code + '\neligible = master.products.filter(p => p.category === "Headphones" && p.price_rmb <= 800 && checkCatalogueUsage(p, "music and commuting, noise cancellation", Object.fromEntries(master.products.map(p => [p.id,p])), { Music:["music"], Travel:["commute","travel"], "Noise cancellation":["noise cancellation"] }).valid).map(p=>p.id);').runInContext(context);
  assert.deepEqual(JSON.parse(JSON.stringify(context.eligible)), []);
  const c = caseById("headphones-no-match"), tooExpensive = output({ ...c, products: ["AUD-005"] });
  assert.equal(execute(input(c, tooExpensive)).validation_ok, false);
});

test("partial recommendations require an honest category-specific no-match and never salvage an unsafe item", async () => {
  const c = caseById("laptop-headphones-partial"), previous = [rec("MOU-002")];
  assert.equal(execute(input(c)).validation_ok, true);
  for (const reply of [{ ...output(c), answer: "Here is the laptop." }, output({ ...c, products: ["LAP-005", "AUD-001"] })]) {
    const result = execute(input(c, reply, previous));
    assert.equal(result.validation_ok, false);
    assert.deepEqual(result.recommendations, []);
    assert.deepEqual(result.recommendations_to_store, previous);
    for (const kind of ["local", "aiep"]) { const app = await repairFrontend(kind); assert.equal(app.validate(reply, app.guard(c.message)).valid, false); }
  }
  const available = caseById("shared-gaming-300");
  assert.equal(execute(input(available, { ...output(available), recommendations: [rec("LAP-005")], answer: "No Mouse in the catalogue matches." })).validation_ok, false);
});

test("unknown qualifiers, negation, contradictions and alternatives fail closed in every layer", async () => {
  for (const usage of [...fixtures.rejected_usages, "gaming, good performance and quantum simulation"]) {
    const c = { ...caseById("laptop-performance"), message: `I need a laptop under RMB 6000 for ${usage}.`, requests: [{ category: "Laptop", budget: 6000, main_usage: usage }] };
    const value = input(c, output(c), [rec("MOU-002")]), result = execute(value);
    assert.equal(result.validation_ok, false, usage);
    assert.deepEqual(result.recommendations_to_store, value.previous_recommendations);
    assert.equal(adapter.validate(value).valid, false);
    for (const kind of ["local", "aiep"]) {
      const app = await repairFrontend(kind);
      assert.equal(app.guard(c.message).usageClarificationNeeded, true, usage);
      await app.submit(c.message, output(c));
      assert.equal(app.calls.length, 1, "the original turn must reach the mocked chat to preserve backend context");
      assert.equal(app.cards(), 0); assert.match(app.text(), /clarify/i);
    }
  }
  for (const message of ["I need a laptop or a mouse under RMB 300 for gaming.", "I need a laptop under RMB 6000 for study and a mouse under RMB 300."]) {
    for (const kind of ["local", "aiep"]) { const app = await repairFrontend(kind); await app.submit(message); assert.equal(app.calls.length, 1); assert.match(app.text(), /clarify/i); }
  }
});

test("facts, hard budgets and exact four-field JSON remain mandatory across layers", async () => {
  const c = caseById("shared-gaming-1000-paired-failure");
  const mutations = [r => { r.recommendations[0].recommended_product = "MECHREVO Jiaolong 16K"; },
    r => { r.recommendations[0].price = 4998; }, r => { r.recommendations[0].price = "4999"; },
    r => { r.recommendations[0].source = "unverified alternative"; }, r => { r.recommendations[0].category = "laptop"; },
    r => { r.recommendations.push(rec("LAP-005")); }, r => { r.extra = true; }, r => { delete r.answer; },
    r => { r.recommendations[0].extra = true; }, r => { delete r.recommendations[0].source; },
    r => { r.recommendations[0] = null; }, r => { r.recommendations = "not an array"; },
    r => { r.clarification_needed = true; }, r => { r.recommendations[1] = rec("MOU-006"); }];
  for (const mutate of mutations) {
    const reply = output(c); mutate(reply);
    assert.equal(execute(input(c, reply)).validation_ok, false);
    assert.equal(adapter.validate(input(c, reply)).valid, false);
    for (const kind of ["local", "aiep"]) { const app = await repairFrontend(kind); assert.equal(app.validate(reply, app.guard(c.message)).valid, false); }
  }
  const value = input(c); value.active_requests[1].budget = 100;
  assert.equal(execute(value).validation_ok, false); assert.equal(adapter.validate(value).valid, false);
  for (const budget of [null, 0, -1, true, "1000"]) {
    const bad = input(c); bad.active_requests[1].budget = budget;
    assert.equal(execute(bad).validation_ok, false); assert.equal(adapter.validate(bad).valid, false);
  }
  const prose = input(c); prose.raw_json = "Some prose " + prose.raw_json;
  assert.equal(execute(prose).validation_ok, false);
});

test("shared context, targeted comparisons, failed turns and restart preserve validated memory", async () => {
  const c = caseById("shared-gaming-1000-paired-failure");
  for (const kind of ["local", "aiep"]) {
    const app = await repairFrontend(kind);
    await app.submit(c.message, output(c));
    const saved = app.state(), guard = app.guard("Cheaper Mouse.");
    assert.equal(guard.usagesByCategory.Mouse, "gaming"); assert.equal(guard.budgetsByCategory.Mouse, 1000);
    assert.deepEqual(guard.targetCategories, ["Mouse"]);
    const cheaper = { ...output(c), recommendations: [rec("MOU-004")] };
    const request = { raw_json: JSON.stringify(cheaper), active_requests: [{ category: "Mouse", budget: 1000, main_usage: "gaming" }], previous_recommendations: [rec("LAP-005"), rec("MOU-002")], follow_up_intent: "cheaper" };
    const result = execute(request);
    assert.equal(result.validation_ok, true);
    assert.deepEqual(result.recommendations_to_store, [rec("LAP-005"), rec("MOU-004")]);
    await app.submit("Cheaper Mouse.", cheaper);
    assert.equal(app.state().sessionContext.lastRecommendationsByCategory.Laptop.product, saved.sessionContext.lastRecommendationsByCategory.Laptop.product);
    const good = app.state().sessionContext.lastRecommendationsByCategory;
    await app.submit("I need a mouse under RMB 1000 for gaming.", { ...cheaper, recommendations: [rec("MOU-001")] });
    assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, good);
    const id = app.state().fastGptChatId;
    app.restart();
    assert.notEqual(app.state().fastGptChatId, id);
    assert.deepEqual(app.state().sessionContext.requirementsByCategory, {});
    assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, {});
    assert.deepEqual(app.state().modelHistory, []);
  }
});

test("all exact Master usage tags remain valid and qualitative performance is Laptop/Gaming scoped", async () => {
  const helper = await readFile(new URL("tools/templates/v21_usage_validation.js", root), "utf8");
  const policy = JSON.parse(await readFile(new URL("tools/templates/v21_usage_compatibility.json", root), "utf8"));
  const catalogue = Object.fromEntries(master.products.map(p => [p.id, p]));
  for (const p of master.products) for (const usage of p.main_usage) {
    assert.equal(new Script(helper + "\ncheckCatalogueUsage(product, usage, catalogue, policy).valid;").runInNewContext({ product: p, usage, catalogue, policy }), true, `${p.id}: ${usage}`);
  }
  for (const id of ["LAP-001", "MOU-002"]) assert.equal(new Script(helper + '\ncheckCatalogueUsage(product, "gaming, good performance", catalogue, policy).valid;').runInNewContext({ product: product(id), catalogue, policy }), false);
  for (const usage of ["gaming with good performance", "gaming and good performance", "good performance for gaming"]) {
    assert.equal(new Script(helper + "\ncheckCatalogueUsage(product, usage, catalogue, policy).valid;").runInNewContext({ product: product("LAP-005"), usage, catalogue, policy }), true);
  }
  for (const kind of ["local", "aiep"]) {
    const app = await repairFrontend(kind);
    assert.equal(app.guard("I need a gaming PC under RMB 6000.").usagesByCategory.Desktop, "gaming");
    assert.equal(app.guard("I need a competitive gaming PC under RMB 6000.").usagesByCategory.Desktop, "competitive gaming");
  }
});

test("missing-budget and missing-usage replies retain complete original chat context without losing qualifiers", async () => {
  const c = caseById("shared-gaming-300"), mouseReply = { ...output(c), recommendations: [rec("MOU-004")] };
  const clarification = { answer: "Please state the missing requirement.", recommendations: [], next_step: "State the missing budget or usage.", clarification_needed: true };
  for (const kind of ["local", "aiep"]) {
    const app = await repairFrontend(kind);
    await app.submit("I need a gaming mouse.", clarification);
    await app.submit("RMB 300.", mouseReply);
    assert.equal(app.state().sessionContext.requirementsByCategory.Mouse.budget, 300);
    assert.equal(app.state().sessionContext.requirementsByCategory.Mouse.usage, "gaming");
    assert.equal(app.cards(), 1);
    const messages = app.calls.map(call => kind === "local" ? call.payload.message : call.payload.messages[0].content);
    assert.deepEqual(messages, ["I need a gaming mouse.", "RMB 300."]);
    app.restart();
    await app.submit("I need a mouse under RMB 300.", clarification);
    await app.submit("quantum simulation", mouseReply);
    assert.equal(app.state().sessionContext.requirementsByCategory.Mouse.usage, "quantum simulation");
    assert.equal(app.cards(), 0);
    await app.submit("gaming", mouseReply);
    assert.equal(app.cards(), 1);
    assert.equal(app.state().sessionContext.requirementsByCategory.Mouse.budget, 300);
  }
});

for (const c of fixtures.context_corrections) test(`current-turn usage correction across layers: ${c.id}`, async () => {
  const initial = { ...output({ answer: "Initial catalogue response.", products: c.initial_products }), clarification_needed: !c.initial_products.length };
  const reply = output({ answer: "Recommendation checked against the current requirements.", products: c.products });
  const previous = c.initial_products.map(rec);
  for (const kind of ["local", "aiep"]) {
    const app = await repairFrontend(kind);
    await app.submit(c.initial_message, initial);
    const saved = app.state().sessionContext.lastRecommendationsByCategory;
    const guard = app.guard(c.message);
    assert.equal(guard.usagesByCategory.Headphones, c.usage);
    assert.equal(guard.usagesByCategory.Headphones ?? "", app.state().sessionContext.requirementsByCategory.Headphones.usage);
    assert.deepEqual(guard.budgetsByCategory, { Headphones: c.budget });
    assert.equal(guard.usageClarificationNeeded, c.usage_clarification);
    assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, saved);
    assert.equal(app.validate(reply, guard).valid, c.valid);
    const requests = guard.targetCategories.map(category => ({ category, budget: guard.budgetsByCategory[category], main_usage: guard.usagesByCategory[category] }));
    const value = { raw_json: JSON.stringify(reply), active_requests: requests, previous_recommendations: previous, follow_up_intent: "none" };
    const result = execute(value);
    assert.equal(result.validation_ok, c.valid, result.validation_error);
    assert.equal(adapter.validate(value).valid, c.valid);
    if (!c.valid) assert.deepEqual(result.recommendations_to_store, previous);
    if (c.usage.includes("commuting")) {
      const stale = { ...reply, recommendations: [rec("AUD-001")] };
      assert.equal(app.validate(stale, guard).valid, false, "Music alone cannot establish commuting and ANC");
      assert.equal(adapter.validate({ ...value, raw_json: JSON.stringify(stale) }).valid, false);
    }
    const snapshot = structuredClone(guard);
    app.guard("Use it for music instead.");
    assert.deepEqual(guard, snapshot, "later turns cannot mutate a previously captured guard");

    // Exercise sendMessage separately, without a preparatory guard() call that
    // could mask the production update-order bug by updating context twice.
    const display = await repairFrontend(kind);
    await display.submit(c.initial_message, initial);
    const beforeCards = display.cards(), beforeMemory = display.state().sessionContext.lastRecommendationsByCategory;
    await display.submit(c.message, reply);
    assert.equal(display.state().sessionContext.requirementsByCategory.Headphones.usage, c.usage);
    assert.equal(display.cards(), beforeCards + (c.valid ? 1 : 0));
    if (c.valid) {
      const p = product(c.products[0]);
      assert.deepEqual(display.state().sessionContext.lastRecommendationsByCategory.Headphones, { product: p.product, price: p.price_rmb });
    } else assert.deepEqual(display.state().sessionContext.lastRecommendationsByCategory, beforeMemory);
    if (c.usage_clarification) assert.match(display.text(), /clarify/i);
    const last = display.calls.at(-1).payload;
    assert.equal(kind === "local" ? last.message : last.messages[0].content, c.message);
    if (kind === "local") {
      assert.equal(last.validationContext.usagesByCategory.Headphones, c.usage);
      assert.equal(last.validationContext.usageClarificationNeeded, c.usage_clarification);
    }
  }
});

test("explicit usage instructions preserve unsupported wording and accept bounded supported replacements", async () => {
  const initial = output({ answer: "Music headphones.", products: ["AUD-001"] });
  const cases = [
    ["Please use it for music instead.", "music", false],
    ["I will use it for music instead.", "music", false],
    ["Change the main usage to music.", "music", false],
    ["Use it for.", "", true],
    ["Use it for music or gaming instead.", "music or gaming", true],
    ["Use it for music instead of quantum simulation.", "music instead of quantum simulation", true],
    ["Use it for not music instead.", "not music", true]
  ];
  for (const kind of ["local", "aiep"]) for (const [message, usage, clarification] of cases) {
    const app = await repairFrontend(kind);
    await app.submit("I need headphones under RMB 1200 for music.", initial);
    const guard = app.guard(message);
    assert.equal(app.state().sessionContext.requirementsByCategory.Headphones.usage, usage);
    assert.equal(guard.usagesByCategory.Headphones ?? "", usage);
    assert.equal(guard.usageClarificationNeeded, clarification);
    assert.equal(app.validate(initial, guard).valid, !clarification);
  }
});

test("ambiguous pronoun corrections do not choose a category or overwrite its constraints", async () => {
  const c = caseById("shared-gaming-1000-paired-failure");
  for (const kind of ["local", "aiep"]) for (const message of ["Use it for quantum simulation instead.", "Use them for study instead."]) {
    const app = await repairFrontend(kind);
    await app.submit(c.message, output(c));
    const saved = app.state().sessionContext;
    const guard = app.guard(message);
    assert.equal(guard.usageClarificationNeeded, true);
    assert.deepEqual(app.state().sessionContext.requirementsByCategory, saved.requirementsByCategory);
    assert.deepEqual(guard.budgetsByCategory, { Laptop: 6000, Mouse: 1000 });
    assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, saved.lastRecommendationsByCategory);
    assert.equal(app.validate(output(c), guard).valid, false);
    await app.submit(message, output(c));
    assert.equal(app.cards(), 2); assert.match(app.text(), /clarify/i);
    assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, saved.lastRecommendationsByCategory);
  }
  for (const kind of ["local", "aiep"]) {
    const app = await repairFrontend(kind);
    app.guard("I need headphones under RMB 1200 for music and a mouse under RMB 300.");
    const saved = app.state().sessionContext.requirementsByCategory;
    const guard = app.guard("Use it for gaming instead.");
    assert.equal(guard.usageClarificationNeeded, true, "a missing usage does not identify the pronoun's target");
    assert.deepEqual(app.state().sessionContext.requirementsByCategory, saved);
  }
});

test("targeted usage corrections preserve independent budgets, anchors, comparisons and restart", async () => {
  const c = caseById("shared-gaming-1000-paired-failure");
  const mouseReply = output({ answer: "Gaming mouse.", products: ["MOU-002"] });
  for (const kind of ["local", "aiep"]) {
    const app = await repairFrontend(kind);
    await app.submit(c.message, output(c));
    await app.submit("I need headphones under RMB 1200 for music.", output({ answer: "Music headphones.", products: ["AUD-001"] }));
    const saved = app.state().sessionContext;
    await app.submit("Use it for quantum simulation instead.", output({ answer: "Unsafe reuse.", products: ["AUD-001"] }));
    assert.equal(app.cards(), 3);
    assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, saved.lastRecommendationsByCategory);
    const guard = app.guard("Use it for music instead.");
    assert.equal(guard.usageClarificationNeeded, false);
    assert.deepEqual(guard.targetCategories, ["Headphones"]);
    assert.deepEqual(guard.budgetsByCategory, { Laptop: 6000, Mouse: 1000, Headphones: 1200 });
    assert.deepEqual(guard.usagesByCategory, { Laptop: "gaming", Mouse: "gaming", Headphones: "music" });
    await app.submit("Use it for music instead.", output({ answer: "Music headphones.", products: ["AUD-001"] }));
    await app.submit("I need a mouse under RMB 1000 for gaming.", mouseReply);
    const beforeComparison = app.state().sessionContext.lastRecommendationsByCategory;
    await app.submit("Cheaper Mouse.", output({ answer: "Cheaper Gaming mouse.", products: ["MOU-004"] }));
    assert.equal(app.state().sessionContext.lastRecommendationsByCategory.Mouse.price, 109);
    assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory.Laptop, beforeComparison.Laptop);
    assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory.Headphones, beforeComparison.Headphones);
    app.restart();
    assert.deepEqual(app.state().sessionContext.requirementsByCategory, {});
    assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, {});
    assert.deepEqual(app.state().modelHistory, []);
    assert.equal(app.guard("I need headphones under RMB 1200 for music.").usageClarificationNeeded, false);
  }
});

test("Original comparison directions and no-match memory remain valid in the repair", () => {
  const c = caseById("shared-gaming-1000-paired-failure");
  for (const [intent, previousId, nextId] of [["cheaper", "MOU-002", "MOU-004"], ["alternative", "MOU-002", "MOU-004"], ["more_expensive", "MOU-004", "MOU-002"]]) {
    const previous = [rec("LAP-005"), rec(previousId)];
    const value = { raw_json: JSON.stringify({ ...output(c), recommendations: [rec(nextId)] }), active_requests: [{ category: "Mouse", budget: 1000, main_usage: "gaming" }], previous_recommendations: previous, follow_up_intent: intent };
    assert.equal(execute(value).validation_ok, true);
    assert.deepEqual(execute(value).recommendations_to_store, [previous[0], rec(nextId)]);
    assert.equal(adapter.validate(value).valid, true);
    const noMatch = { ...value, raw_json: JSON.stringify({ ...output(c), recommendations: [] }) };
    assert.deepEqual(execute(noMatch).recommendations_to_store, previous);
    const repeated = { ...value, raw_json: JSON.stringify({ ...output(c), recommendations: [rec(previousId)] }) };
    assert.equal(execute(repeated).validation_ok, false);
    assert.deepEqual(execute(repeated).recommendations_to_store, previous);
  }
});

test("local TEST server uses the repair directory, retains chat transport and rejects ambiguous recommendations", async t => {
  const config = testServerConfig({ MYTECH_TEST_PORT: "0", MYTECH_TEST_FASTGPT_API_KEY: ["offline", "fixture"].join("-"), MYTECH_TEST_FASTGPT_API_URL: "https://example.invalid/chat/completions", MYTECH_TEST_FASTGPT_BINDING: "app-key" });
  const c = caseById("shared-gaming-1000-paired-failure");
  let calls = 0;
  const server = await createTestServer(config, { directory: fileURLToPath(directory), fetchImpl: async () => {
    calls += 1; return new Response(JSON.stringify({ choices: [{ message: { content: JSON.stringify(output(c)) } }] }));
  } });
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  t.after(() => new Promise(resolve => server.close(resolve)));
  const app = await repairFrontend("local"), guard = app.guard(c.message);
  const endpoint = `http://127.0.0.1:${server.address().port}/api/test/mytech`;
  const post = g => fetch(endpoint, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: c.message, chatId: "offline-repair-http", validationContext: g }) });
  assert.equal((await post({ ...guard, usageClarificationNeeded: true })).status, 502);
  assert.equal(calls, 1);
  assert.equal((await post(guard)).status, 200); assert.equal(calls, 2);
});
