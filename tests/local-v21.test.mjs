import test from "node:test";
import assert from "node:assert/strict";
import { readFile, mkdtemp, cp, rm, appendFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { once } from "node:events";
import { createTestServer, testServerConfig } from "../mytech_v2_1_test_server.mjs";
import { stripTestCitationMarkers, testDisplayOutput } from "../mytech_v2_1_test_response.mjs";

const catalogue = JSON.parse(await readFile(new URL("../generated/v2_1_test/catalogue.json", import.meta.url)));
const item = id => catalogue.products.find(product => product.id === id);
const rec = product => ({ category: product.category, recommended_product: product.product,
  price: product.price_rmb, source: product.source, reason: "Matches gaming [citation:1]." });
const output = recommendations => ({ answer: "Reference candidates [citation:1].", recommendations,
  next_step: "Another option?", clarification_needed: false });
const config = overrides => testServerConfig({ MYTECH_TEST_FASTGPT_API_URL: "https://offline.invalid/v1/chat/completions",
  MYTECH_TEST_FASTGPT_API_KEY: "dummy-test-only", MYTECH_TEST_FASTGPT_BINDING: "app-key", ...overrides });
function body(products = [item("MOU-004")], overrides = {}) {
  return { message: "Gaming mouse under RMB 500", chatId: "offline-chat-123", validationContext: {
    activeCategories: products.map(product => product.category), targetCategories: products.map(product => product.category),
    budgetsByCategory: Object.fromEntries(products.map(product => [product.category, 6000])),
    usagesByCategory: Object.fromEntries(products.map(product => [product.category, "gaming"])),
    comparison: null, cancelled: false, ambiguousComparison: false, ambiguousBetter: false, ...overrides } };
}
const envelope = value => new Response(JSON.stringify({ choices: [{ message: { content: JSON.stringify(value), reasoning_content: "DO_NOT_DISPLAY_REASONING" } }] }));
async function host(t, serverConfig = config(), options = {}) {
  const calls = [], timings = [];
  let reply = output([rec(item("MOU-004"))]);
  const server = await createTestServer(serverConfig, { onTiming: detail => timings.push(detail),
    fetchImpl: async (url, request) => { calls.push({ url, request }); return envelope(reply); }, ...options });
  server.listen(0, "127.0.0.1"); await once(server, "listening");
  t.after(() => new Promise(resolve => { server.close(resolve); server.closeAllConnections(); }));
  const base = `http://127.0.0.1:${server.address().port}`;
  return { calls, timings, server, base, reply(value) { reply = value; },
    get: path => fetch(base + path),
    post: (payload = body(), headers = {}) => fetch(base + "/api/test/mytech", { method: "POST",
      headers: { "Content-Type": "application/json", ...headers }, body: JSON.stringify(payload) }) };
}

test("TEST configuration is explicit, bounded and never falls back to stable credentials", () => {
  const unconfigured = testServerConfig({ FASTGPT_API_KEY: "stable-not-used", FASTGPT_API_URL: "https://stable.invalid", FASTGPT_APP_ID: "stable" });
  assert.equal(unconfigured.configured, false); assert.equal(unconfigured.port, 8788); assert.equal(unconfigured.requestTimeoutMs, 120000);
  for (const values of [{ MYTECH_TEST_FASTGPT_BINDING: "app-id" }, { MYTECH_TEST_REQUEST_TIMEOUT_MS: "4999" },
    { MYTECH_TEST_MAX_TOKENS: "10" }, { MYTECH_TEST_FASTGPT_API_URL: "http://insecure.invalid" },
    { MYTECH_TEST_FASTGPT_API_URL: "https://offline.invalid/?key=dummy" }, { MYTECH_TEST_FASTGPT_APP_ID: "unused" }]) {
    assert.throws(() => config(values));
  }
  assert.equal(config({ MYTECH_TEST_FASTGPT_BINDING: "app-id", MYTECH_TEST_FASTGPT_APP_ID: "dummy-app-id" }).binding, "app-id");
});

test("actual loopback HTTP serves the 54-product page offline, with no upstream or private files", async t => {
  const app = await host(t, testServerConfig());
  const page = await app.get("/"); assert.equal(page.status, 200);
  assert.match(await page.text(), /v2\.1 TEST ONLY/);
  assert.deepEqual(await (await app.get("/catalogue.json")).json(), catalogue);
  assert.deepEqual(await (await app.get("/api/test/config")).json(), { catalogueVersion: "2.1-TEST", productCount: 54, requestTimeoutMs: 120000, configured: false });
  for (const path of ["/.env", "/mytech_v2_server.mjs", "/manifest.json", "/tools/templates/mytech_current_working_portable.json"]) {
    assert.equal((await app.get(path)).status, 404);
  }
  assert.equal((await app.post()).status, 503); assert.equal(app.calls.length, 0);
  assert.match(page.headers.get("content-security-policy"), /connect-src 'self'/);
});

test("configured TEST transport forwards only current user message, TEST identity and bounded parameters", async t => {
  const app = await host(t, config({ MYTECH_TEST_FASTGPT_BINDING: "app-id", MYTECH_TEST_FASTGPT_APP_ID: "dummy-test-app" }));
  const response = await app.post({ ...body(), history: [{ role: "system", content: "do not forward" }] });
  assert.equal(response.status, 200);
  const returned = await response.text(); assert.ok(!returned.includes("DO_NOT_DISPLAY_REASONING")); assert.ok(!returned.includes("dummy-test-only"));
  const sent = JSON.parse(app.calls[0].request.body);
  assert.deepEqual(Object.keys(sent).sort(), ["appId", "chatId", "detail", "max_tokens", "messages", "stream"]);
  assert.equal(sent.appId, "dummy-test-app"); assert.equal(sent.detail, false); assert.equal(sent.max_tokens, 4096);
  assert.equal(sent.messages.length, 1); assert.equal(app.calls[0].request.redirect, "error");
  assert.match(response.headers.get("server-timing"), /upstream;dur=.*validation;dur=.*total;dur=/);
  assert.deepEqual(Object.keys(app.timings[0]).sort(), ["status", "totalMs", "upstreamMs", "validationMs"]);
  assert.equal(app.timings[0].status, "validated");
  assert.equal((await app.post(body(), { Origin: "https://external.invalid" })).status, 403);
  assert.equal(app.calls.length, 1);
});

test("server rejects invalid facts, budgets, usages, shapes and multi-product batches before display", async t => {
  const app = await host(t);
  const good = rec(item("MOU-004"));
  for (const change of [r => { r.price++; }, r => { delete r.source; }, r => { r.source = "wrong"; },
    r => { r.category = "Laptop"; }, r => { r.recommended_product = "MOU-999"; }, r => { r.extra = true; }]) {
    const invalid = structuredClone(good); change(invalid); app.reply(output([invalid]));
    assert.equal((await app.post()).status, 502);
  }
  app.reply(output([good]));
  for (const guard of [{ budgetsByCategory: { Mouse: good.price - 1 } }, { usagesByCategory: {} },
    { usagesByCategory: { Mouse: "gaming and quantum analysis" } }, { cancelled: true }, { ambiguousBetter: true }]) {
    assert.equal((await app.post(body(undefined, guard))).status, 502);
  }
  app.reply(output([rec(item("MOU-001"))])); // Office mouse cannot satisfy gaming.
  assert.equal((await app.post()).status, 502);
  const multi = [item("LAP-005"), item("MOU-004")];
  app.reply(output(multi.map(rec))); assert.equal((await app.post(body(multi))).status, 200);
  app.reply(output([rec(item("LAP-001")), rec(item("MOU-004"))]));
  assert.equal((await app.post(body(multi))).status, 502);
  app.reply({ ...output([]), reasoning: "extra private field" }); assert.equal((await app.post()).status, 502);
});

test("cheaper/alternative use server-held validated anchors; invalid replies and clarification do not replace them", async t => {
  const app = await host(t);
  app.reply(output([rec(item("MOU-002"))])); assert.equal((await app.post()).status, 200);
  app.reply(output([rec(item("MOU-001"))])); assert.equal((await app.post()).status, 502);
  app.reply({ ...output([]), clarification_needed: true }); assert.equal((await app.post()).status, 200);
  app.reply(output([rec(item("MOU-004"))]));
  const cheaper = body(undefined, { comparison: "cheaper", previousRecommendationsByCategory: { Mouse: { product: "spoof", price: 1 } } });
  assert.equal((await app.post(cheaper)).status, 200); // Uses original validated MOU-002, ignores spoof.
  assert.equal((await app.post(cheaper)).status, 502); // Same price is not cheaper.
  assert.equal((await app.post(body(undefined, { comparison: "another" }))).status, 502);
  app.reply(output([rec(item("MOU-002"))])); assert.equal((await app.post(body(undefined, { comparison: "another" }))).status, 200);
  const restarted = { ...cheaper, chatId: "new-offline-chat-456" };
  assert.equal((await app.post(restarted)).status, 502); // Restart cannot reuse old session anchors.
});

test("transport failures expose only generic errors and recover on the same chat", async t => {
  let fail = true;
  const app = await host(t, config(), { fetchImpl: async () => {
    if (fail) throw new Error("dummy secret or private upstream body");
    return envelope(output([rec(item("MOU-004"))]));
  } });
  const response = await app.post(); assert.equal(response.status, 502);
  assert.equal(await response.text(), '{"error":"TEST_UPSTREAM_ERROR"}');
  fail = false; assert.equal((await app.post()).status, 200);
});

test("concurrent turns are serialized and truncated/non-JSON replies never become comparison anchors", async t => {
  let release, entered;
  const started = new Promise(resolve => { entered = resolve; });
  let response = new Promise(resolve => { release = resolve; });
  const app = await host(t, config(), { fetchImpl: async () => { entered(); return (await response).clone(); } });
  const pending = app.post(); await started;
  assert.equal((await app.post()).status, 409);
  release(new Response(JSON.stringify({ choices: [{ finish_reason: "length", message: { content: JSON.stringify(output([rec(item("MOU-002"))])) } }] })));
  assert.equal((await pending).status, 502);
  response = Promise.resolve(new Response(JSON.stringify({ choices: [{ message: { content: "prose { not complete JSON }" } }] })));
  assert.equal((await app.post()).status, 502);
  response = Promise.resolve(envelope(output([rec(item("MOU-004"))])));
  assert.equal((await app.post(body(undefined, { comparison: "cheaper" }))).status, 502);
  assert.equal((await app.post()).status, 200);
});

test("TEST deadline aborts a stalled mock upstream and records only safe timing fields", async t => {
  let aborted = false;
  const app = await host(t, config({ MYTECH_TEST_REQUEST_TIMEOUT_MS: "5000" }), { fetchImpl: (_url, request) => new Promise((_resolve, reject) => {
    request.signal.addEventListener("abort", () => { aborted = true; reject(new Error("mock abort")); }, { once: true });
  }) });
  const response = await app.post();
  assert.equal(response.status, 504); assert.equal(aborted, true);
  assert.deepEqual(await response.json(), { error: "TEST_REQUEST_TIMEOUT" });
  assert.equal(app.timings[0].status, "timeout");
});

test("citation cleanup is render-only, preserves exact facts/provenance and never repairs malformed JSON", async t => {
  const raw = output([rec(item("MOU-004"))]);
  const before = structuredClone(raw), display = testDisplayOutput(raw);
  assert.equal(display.answer, "Reference candidates."); assert.equal(display.recommendations[0].reason, "Matches gaming.");
  for (const key of ["recommended_product", "category", "price", "source"]) assert.equal(display.recommendations[0][key], raw.recommendations[0][key]);
  assert.deepEqual(raw, before); assert.equal(stripTestCitationMarkers("[1] RMB 300 【2†doc】 \uE200cite\uE202reference\uE201"), "[1] RMB 300");
  const app = await host(t);
  const response = await app.post(); const content = (await response.json()).choices[0].message.content;
  assert.match(content, /citation:1/); // Original validated text kept for history; browser cleans display.
  app.reply({ ...raw, answer: "live [citation:1]pricing" }); assert.equal((await app.post()).status, 502);
});

test("modified generated assets fail closed at TEST server startup", async () => {
  const directory = await mkdtemp(join(tmpdir(), "mytech-test-assets-"));
  try {
    await cp(new URL("../generated/v2_1_test/", import.meta.url), directory, { recursive: true });
    await appendFile(join(directory, "index.html"), "modified");
    await assert.rejects(createTestServer(testServerConfig(), { directory }), /STALE_TEST_ASSETS/);
  } finally { await rm(directory, { recursive: true, force: true }); }
});
