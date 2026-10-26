// Independent loopback TEST host. Never loads .env or falls back to stable keys.
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { isDeepStrictEqual } from "node:util";
import { performance } from "node:perf_hooks";
import { createTestAdapter } from "./mytech_v2_1_test_adapter.mjs";
import { parseFastGptResponse, validateOutput } from "./mytech_response.mjs";
import { testDisplayOutput } from "./mytech_v2_1_test_response.mjs";

const ROOT = fileURLToPath(new URL("./", import.meta.url));
const ASSETS = ["index.html", "catalogue.json", "mytech-fastgpt-workflow-v2_1-TEST.json", "MyTech_Product_Knowledge_v2_1_TEST.md"];
const MAX_BODY = 65536, MAX_UPSTREAM = 2 * 1024 * 1024;
const plain = value => Boolean(value) && typeof value === "object" && !Array.isArray(value);
const digest = value => createHash("sha256").update(value).digest("hex");
const fail = (code, status = 400) => Object.assign(new Error(code), { code, status });
function integer(value, fallback, min, max) {
  const number = value === undefined || value === "" ? fallback : Number(value);
  if (!Number.isInteger(number) || number < min || number > max) throw fail("INVALID_TEST_CONFIGURATION");
  return number;
}

export function testServerConfig(env = {}) {
  const config = {
    port: integer(env.MYTECH_TEST_PORT, 8788, 0, 65535),
    requestTimeoutMs: integer(env.MYTECH_TEST_REQUEST_TIMEOUT_MS, 120000, 5000, 300000),
    maxTokens: integer(env.MYTECH_TEST_MAX_TOKENS, 4096, 256, 8192),
    apiUrl: env.MYTECH_TEST_FASTGPT_API_URL || "",
    apiKey: env.MYTECH_TEST_FASTGPT_API_KEY || "",
    appId: env.MYTECH_TEST_FASTGPT_APP_ID || "",
    binding: env.MYTECH_TEST_FASTGPT_BINDING || "",
    timings: env.MYTECH_TEST_TIMINGS === "1"
  };
  const anyBinding = config.apiUrl || config.apiKey || config.appId || config.binding;
  config.configured = Boolean(anyBinding);
  if (anyBinding) {
    if (!config.apiUrl || !config.apiKey || !["app-key", "app-id"].includes(config.binding)
      || (config.binding === "app-id" && !config.appId) || (config.binding === "app-key" && config.appId)) {
      throw fail("INCOMPLETE_TEST_BINDING");
    }
    let url;
    try { url = new URL(config.apiUrl); } catch { throw fail("INVALID_TEST_API_URL"); }
    if (url.protocol !== "https:" || url.username || url.password || url.search || url.hash
      || /[\r\n]/.test(config.apiKey)) throw fail("INVALID_TEST_API_CONFIGURATION");
  }
  return Object.freeze(config);
}

async function readLimited(stream, limit) {
  const chunks = []; let size = 0;
  for await (const chunk of stream) {
    size += chunk.length;
    if (size > limit) throw fail("RESPONSE_OR_REQUEST_TOO_LARGE", 413);
    chunks.push(Buffer.from(chunk));
  }
  return Buffer.concat(chunks).toString("utf8");
}

export async function createTestServer(config = testServerConfig(), options = {}) {
  const directory = options.directory || resolve(ROOT, "generated/v2_1_test");
  const [manifest, master, adapter, buffers] = await Promise.all([
    readFile(resolve(directory, "manifest.json"), "utf8").then(JSON.parse),
    readFile(options.masterPath || resolve(ROOT, "catalogue/mytech_products_v2_1_test.json"), "utf8").then(JSON.parse),
    createTestAdapter(directory),
    Promise.all(ASSETS.map(name => readFile(resolve(directory, name))))
  ]);
  if (!isDeepStrictEqual(adapter.catalogue, master) || manifest.product_count !== master.products.length
    || ASSETS.some((name, index) => digest(buffers[index]) !== manifest.outputs[name])) {
    throw fail("STALE_TEST_ASSETS");
  }
  const catalogue = adapter.catalogue;
  const productByName = new Map(catalogue.products.map(product => [product.product, product]));
  const fetchImpl = options.fetchImpl || fetch;
  const sessions = new Map();
  const sessionLimit = 200, ttl = 60 * 60 * 1000;
  const clock = options.now || Date.now;
  const reportTiming = detail => {
    // Fixed schema: never pass prompts, output, IDs, URLs or upstream errors.
    if (options.onTiming) { try { options.onTiming(Object.freeze(detail)); } catch {} }
  };
  function session(chatId) {
    for (const [key, value] of sessions) if (!value.busy && clock() - value.updated > ttl) sessions.delete(key);
    if (!sessions.has(chatId)) {
      if (sessions.size >= sessionLimit) throw fail("TEST_SESSION_CAPACITY", 503);
      sessions.set(chatId, { recommendations: [], updated: clock(), busy: false });
    }
    return sessions.get(chatId);
  }
  function requestContext(body) {
    if (!plain(body) || typeof body.message !== "string" || !body.message.trim() || body.message.length > 8000 || typeof body.chatId !== "string"
      || !/^[A-Za-z0-9][A-Za-z0-9_-]{7,127}$/.test(body.chatId)) throw fail("INVALID_TEST_REQUEST");
    const guard = body.validationContext;
    if (!plain(guard) || !Array.isArray(guard.activeCategories) || !Array.isArray(guard.targetCategories)
      || !plain(guard.budgetsByCategory) || !plain(guard.usagesByCategory)
      || ![null, "cheaper", "more_expensive", "another"].includes(guard.comparison)
      || ["cancelled", "ambiguousComparison", "ambiguousBetter"].some(key => typeof guard[key] !== "boolean")
      || guard.activeCategories.length > catalogue.supported_categories.length
      || guard.activeCategories.some(category => !catalogue.supported_categories.includes(category))
      || new Set(guard.activeCategories).size !== guard.activeCategories.length
      || guard.targetCategories.some(category => !guard.activeCategories.includes(category))) throw fail("INVALID_TEST_CONTEXT");
    if (guard.usageClarificationNeeded !== undefined && typeof guard.usageClarificationNeeded !== "boolean") throw fail("INVALID_TEST_CONTEXT");
    return guard;
  }
  function validate(output, guard, previous, message) {
    const recs = output?.recommendations;
    let acceptedOutput = output;
    const preflight = validateOutput(output, guard.budgetsByCategory, {}, { productByName, supportedCategories: catalogue.supported_categories });
    if (preflight.length || ((output?.clarification_needed || guard.cancelled || guard.ambiguousComparison || guard.ambiguousBetter || guard.usageClarificationNeeded) && recs?.length)) {
      throw fail("MODEL_OUTPUT_VALIDATION_FAILED", 502);
    }
    if (manifest.completion_validation) {
      const completion = adapter.validateCompletionTurn?.(output, guard, previous, message);
      if (!completion?.valid) {
        throw fail("MODEL_OUTPUT_VALIDATION_FAILED", 502);
      }
      if (completion.result?.normalized_json) acceptedOutput = JSON.parse(completion.result.normalized_json);
    }
    if (!recs.length) return { recommendations: previous, output: acceptedOutput }; // Never erase anchors.
    const categories = guard.targetCategories.length ? guard.targetCategories : guard.activeCategories;
    if ((guard.comparison && categories.length !== 1) || recs.some(rec => !categories.includes(rec.category))) {
      throw fail("MODEL_OUTPUT_VALIDATION_FAILED", 502);
    }
    const input = {
      raw_json: JSON.stringify(output),
      active_requests: categories.map(category => ({ category, budget: guard.budgetsByCategory[category], main_usage: guard.usagesByCategory[category] })),
      previous_recommendations: previous,
      follow_up_intent: guard.comparison === "another" ? "alternative" : guard.comparison || "none"
    };
    const result = adapter.validate(input);
    if (!result.valid) throw fail("MODEL_OUTPUT_VALIDATION_FAILED", 502);
    // Browser retains other categories. Merge only validated replacements locally.
    return { recommendations: [...previous.filter(item => !recs.some(rec => rec.category === item.category)), ...structuredClone(recs)], output: acceptedOutput };
  }

  const server = createServer(async (req, res) => {
    const started = performance.now();
    let upstreamMs = 0, validationMs = 0, status = "rejected", heldSession, timer, controller;
    const abort = () => controller?.abort();
    const disconnect = () => { if (!res.writableEnded) abort(); };
    req.on("aborted", abort); res.on("close", disconnect);
    res.setHeader("Cache-Control", "no-store");
    res.setHeader("X-Content-Type-Options", "nosniff");
    res.setHeader("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'");
    function json(code, value) {
      if (res.destroyed) return;
      res.writeHead(code, { "Content-Type": "application/json; charset=utf-8" });
      res.end(JSON.stringify(value));
    }
    try {
      // Protect the loopback host against cross-origin requests and DNS rebinding.
      if (!/^(?:127\.0\.0\.1|localhost)(?::\d+)?$/.test(req.headers.host || "")
        || (req.headers.origin && req.headers.origin !== `http://${req.headers.host}`)
        || req.headers["sec-fetch-site"] === "cross-site") throw fail("LOCAL_ORIGIN_REQUIRED", 403);
      const path = req.url;
      if (req.method === "GET" && (path === "/" || path === "/index.html" || /^\/\?(?:timeout_ms=\d+)?$/.test(path))) {
        res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" }); res.end(buffers[0]); return;
      }
      if (req.method === "GET" && path === "/catalogue.json") { res.writeHead(200, { "Content-Type": "application/json" }); res.end(buffers[1]); return; }
      if (req.method === "GET" && path === "/api/test/config") {
        json(200, { catalogueVersion: "2.1-TEST", productCount: catalogue.products.length,
          requestTimeoutMs: config.requestTimeoutMs, configured: config.configured }); return;
      }
      if (req.method !== "POST" || path !== "/api/test/mytech") throw fail("NOT_FOUND", 404);
      if (!config.configured) throw fail("TEST_CONNECTION_NOT_CONFIGURED", 503);
      if (!/^application\/json(?:;|$)/i.test(req.headers["content-type"] || "")) throw fail("JSON_REQUIRED", 415);
      let body;
      try { body = JSON.parse(await readLimited(req, MAX_BODY)); } catch (error) { throw error.code ? error : fail("INVALID_JSON"); }
      const guard = requestContext(body);
      heldSession = session(body.chatId);
      if (heldSession.busy) { heldSession = null; throw fail("CHAT_BUSY", 409); }
      heldSession.busy = true;
      controller = new AbortController();
      let timedOut = false;
      timer = setTimeout(() => { timedOut = true; controller.abort(); }, config.requestTimeoutMs);
      const upstreamStarted = performance.now();
      let apiResponse;
      try {
        const response = await fetchImpl(config.apiUrl, {
          method: "POST", redirect: "error", signal: controller.signal,
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${config.apiKey}` },
          body: JSON.stringify({ chatId: body.chatId, stream: false, detail: false, max_tokens: config.maxTokens,
            ...(config.binding === "app-id" ? { appId: config.appId } : {}),
            messages: [{ role: "user", content: body.message }] })
        });
        if (!response.ok) throw fail("TEST_UPSTREAM_ERROR", 502);
        apiResponse = JSON.parse(await readLimited(response.body, MAX_UPSTREAM));
        if (apiResponse?.choices?.[0]?.finish_reason === "length") throw fail("TRUNCATED_MODEL_OUTPUT", 502);
      } catch (error) {
        throw timedOut ? fail("TEST_REQUEST_TIMEOUT", 504) : controller.signal.aborted ? fail("TEST_REQUEST_CANCELLED", 499)
          : fail(error.code === "TRUNCATED_MODEL_OUTPUT" ? error.code : "TEST_UPSTREAM_ERROR", 502);
      } finally { upstreamMs = performance.now() - upstreamStarted; }
      const validationStarted = performance.now();
      let output, next;
      try {
        output = parseFastGptResponse(apiResponse); // Only final message content, never reasoning or traces.
        const checked = validate(output, guard, heldSession.recommendations, body.message);
        next = checked.recommendations;
        output = checked.output;
        validate(testDisplayOutput(output), guard, heldSession.recommendations, body.message);
      } catch { throw fail("MODEL_OUTPUT_VALIDATION_FAILED", 502); }
      finally { validationMs = performance.now() - validationStarted; }
      if (controller.signal.aborted || res.destroyed) throw fail("TEST_REQUEST_CANCELLED", 499);
      heldSession.recommendations = next;
      heldSession.updated = clock();
      status = "validated";
      res.setHeader("Server-Timing", `upstream;dur=${upstreamMs.toFixed(1)}, validation;dur=${validationMs.toFixed(1)}, total;dur=${(performance.now() - started).toFixed(1)}`);
      json(200, { choices: [{ message: { role: "assistant", content: JSON.stringify(output) }, finish_reason: "stop" }] });
    } catch (error) {
      status = error.code === "TEST_REQUEST_TIMEOUT" ? "timeout" : controller?.signal.aborted ? "cancelled" : "rejected";
      json(error.status || 500, { error: error.status ? error.code : "TEST_SERVER_ERROR" });
    } finally {
      clearTimeout(timer);
      if (heldSession) heldSession.busy = false;
      req.off("aborted", abort); res.off("close", disconnect);
      if (req.method === "POST" && req.url === "/api/test/mytech") reportTiming({ status,
        upstreamMs: Math.round(upstreamMs), validationMs: Math.round(validationMs), totalMs: Math.round(performance.now() - started) });
    }
  });
  server.requestTimeout = config.requestTimeoutMs + 10000;
  server.headersTimeout = 10000;
  return server;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const config = testServerConfig(process.env); // Explicit TEST names only; no .env loader.
    const server = await createTestServer(config, { onTiming: config.timings ? detail => console.log(JSON.stringify(detail)) : undefined });
    server.on("error", () => { console.error("TEST_SERVER_LISTEN_FAILED"); process.exitCode = 1; });
    server.listen(config.port, "127.0.0.1", () => console.log(`MyTech v2.1 TEST: http://127.0.0.1:${server.address().port} (${config.configured ? "TEST binding configured" : "offline; TEST binding required"})`));
  } catch { console.error("TEST_SERVER_CONFIGURATION_OR_ASSETS_INVALID: check TEST settings and regenerate assets."); process.exitCode = 1; }
}
