// Offline only: injected providers in-process, blocked fetch in CLI children.
import test from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { readFile, mkdtemp, writeFile, copyFile, symlink, realpath, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { startMyTechDemo } from "../start-mytech-demo.mjs";

const root = fileURLToPath(new URL("../", import.meta.url));
const launcher = join(root, "start-mytech-demo.mjs");
const html = await readFile(new URL("../generated/v21_quick_prompt_demo/local/index.html", import.meta.url), "utf8");
const starters = [
  ["Gaming Setup ×2", "I need a laptop under ¥6,000 for gaming and a mouse under ¥300 for gaming."],
  ["Study Laptop", "I need a laptop under ¥7,000 for study and office work."],
  ["ANC Headphones", "I need headphones under ¥1,200 for music, commuting, and noise cancellation."],
  ["Gaming Smartphone", "I need a smartphone under ¥3,000 for gaming."]
];
const bound = binding => ({ MYTECH_TEST_FASTGPT_API_URL: "https://synthetic-provider.invalid/v1/chat/completions",
  MYTECH_TEST_FASTGPT_API_KEY: "synthetic-launcher-secret", MYTECH_TEST_FASTGPT_BINDING: binding,
  MYTECH_TEST_FASTGPT_APP_ID: binding === "app-id" ? "synthetic-launcher-app" : "" });
const safeEnv = Object.fromEntries(["SystemRoot", "SYSTEMROOT", "WINDIR", "TEMP", "TMP"]
  .filter(key => process.env[key] !== undefined).map(key => [key, process.env[key]]));
const blockFetch = `data:text/javascript,${encodeURIComponent('globalThis.fetch = () => { throw new Error("Live fetch forbidden in launcher tests"); };')}`;

const testResources = new WeakMap();
function resources(t) {
  if (!testResources.has(t)) {
    const owned = { stops: [], directories: [] };
    testResources.set(t, owned);
    t.after(async () => {
      for (const stop of owned.stops) await stop();
      for (const directory of owned.directories) await rm(directory, { recursive: true, force: true });
    });
  }
  return testResources.get(t);
}
async function temporary(t) {
  const directory = await mkdtemp(join(tmpdir(), "mytech-launcher-"));
  resources(t).directories.push(directory);
  return directory;
}
async function directoryAlias(t, target) {
  const alias = join(await temporary(t), "alias");
  await symlink(target, alias, process.platform === "win32" ? "junction" : "dir");
  return alias;
}
function cli(t, { entry = launcher, env = {}, cwd = root, args = [] } = {}) {
  const child = spawn(process.execPath, [`--import=${blockFetch}`, ...args, entry], {
    cwd, env: { ...safeEnv, MYTECH_TEST_PORT: "0", ...env }, stdio: ["ignore", "pipe", "pipe"]
  });
  const state = { stdout: "", stderr: "" };
  child.stdout.on("data", chunk => { state.stdout += chunk; });
  child.stderr.on("data", chunk => { state.stderr += chunk; });
  const exited = new Promise((resolve, reject) => { child.once("error", reject); child.once("close", resolve); });
  resources(t).stops.push(async () => { if (child.exitCode === null && child.signalCode === null) child.kill(); await exited; });
  async function ready() {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => { child.kill(); reject(new Error("CLI startup timed out")); }, 15000);
      const check = () => {
        const url = state.stdout.match(/http:\/\/127\.0\.0\.1:\d+/)?.[0];
        const complete = entry.endsWith("start-mytech-demo.mjs") ? state.stdout.includes("Stop with Ctrl+C.") : true;
        if (url && complete) { clearTimeout(timer); child.stdout.off("data", check); resolve(url); }
      };
      child.stdout.on("data", check);
      exited.then(() => { clearTimeout(timer); reject(new Error("CLI exited before startup")); }, reject);
      check();
    });
  }
  return { state, ready, exited };
}
async function host(t, env = {}, options = {}) {
  const result = await startMyTechDemo({ MYTECH_TEST_PORT: "0", ...env }, options);
  t.after(() => new Promise(resolve => { result.server.close(resolve); result.server.closeAllConnections(); }));
  assert.equal(result.server.address().address, "127.0.0.1");
  return { ...result, base: `http://127.0.0.1:${result.server.address().port}` };
}

test("launcher serves exact Quick Prompt Demo HTML and four unchanged starter labels/payloads offline", async t => {
  const app = await host(t, {}, { fetchImpl: () => assert.fail("No upstream allowed") });
  for (const path of ["/", "/index.html"]) {
    const response = await fetch(app.base + path);
    assert.equal(response.status, 200); assert.equal(await response.text(), html);
  }
  assert.deepEqual([...html.matchAll(/<button class="prompt-button" type="button" data-prompt="([^"]+)">([^<]+)<\/button>/g)]
    .map(([, prompt, label]) => [label, prompt]), starters);
  assert.equal(app.configured, false);
  assert.equal((await fetch(app.base + "/api/test/mytech", { method: "POST" })).status, 503);
  for (const path of ["/.env", "/.env.private.test", "/manifest.json", "/start-mytech-demo.mjs"]) {
    assert.equal((await fetch(app.base + path)).status, 404);
  }
});

test("launcher reuses TEST transport and budget validation with an in-memory provider", async t => {
  const catalogue = JSON.parse(await readFile(new URL("../generated/v21_quick_prompt_demo/local/catalogue.json", import.meta.url)));
  const product = catalogue.products.find(p => p.id === "MOU-004");
  const output = { answer: "Reference recommendation.", recommendations: [{ category: product.category,
    recommended_product: product.product, price: product.price_rmb, source: product.source, reason: "Matches gaming usage." }],
    next_step: "Would you like another option?", clarification_needed: false };
  const calls = [];
  const app = await host(t, bound("app-id"), { fetchImpl: async (url, request) => {
    calls.push({ url, request });
    return new Response(JSON.stringify({ choices: [{ message: { content: JSON.stringify(output) } }] }));
  } });
  const body = { message: "I need a mouse under ¥300 for gaming.", chatId: "launcher-offline-chat", validationContext: {
    activeCategories: ["Mouse"], targetCategories: ["Mouse"], budgetsByCategory: { Mouse: 300 }, usagesByCategory: { Mouse: "gaming" },
    comparison: null, cancelled: false, ambiguousComparison: false, ambiguousBetter: false } };
  const post = () => fetch(app.base + "/api/test/mytech", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const response = await post(); assert.equal(response.status, 200);
  const text = await response.text(); assert.deepEqual(JSON.parse(JSON.parse(text).choices[0].message.content), output);
  assert.ok(!text.includes("synthetic-launcher"));
  assert.equal(calls[0].url, bound("app-id").MYTECH_TEST_FASTGPT_API_URL);
  assert.equal(calls[0].request.headers.Authorization, "Bearer synthetic-launcher-secret");
  const sent = JSON.parse(calls[0].request.body);
  assert.equal(sent.appId, "synthetic-launcher-app"); assert.equal(sent.chatId, body.chatId);
  assert.deepEqual(sent.messages, [{ role: "user", content: body.message }]);
  body.validationContext.budgetsByCategory.Mouse = product.price_rmb - 1;
  assert.equal((await post()).status, 502);
});

test("both explicit synthetic env files launch the same demo without disclosing bindings", async t => {
  const cwd = await temporary(t);
  for (const [filename, binding] of [[".env.v21.test", "app-key"], [".env.private.test", "app-id"]]) {
    await writeFile(join(cwd, filename), Object.entries({ ...bound(binding), MYTECH_TEST_PORT: "0" })
      .map(([key, value]) => `${key}=${value}`).join("\n"));
    const app = cli(t, { cwd, env: { MYTECH_TEST_PORT: undefined }, args: [`--env-file=${filename}`] });
    const base = await app.ready();
    assert.equal(await (await fetch(base)).text(), html);
    assert.match(app.state.stdout, /MyTech v2\.1 Quick Prompt Demo \(four-button frontend\)/);
    assert.match(app.state.stdout, /TEST API binding: configured/);
    assert.equal(app.state.stderr, "");
    const publicConfig = await (await fetch(base + "/api/test/config")).text();
    for (const value of ["synthetic-launcher-secret", "synthetic-launcher-app", "synthetic-provider.invalid", "Bearer", "Authorization"]) {
      assert.ok(!(app.state.stdout + app.state.stderr + publicConfig).includes(value));
    }
  }
});

test("original TEST entry point retains its default frontend and startup message", async t => {
  const app = cli(t, { entry: join(root, "mytech_v2_1_test_server.mjs") });
  const base = await app.ready();
  assert.equal(await (await fetch(base)).text(), await readFile(new URL("../generated/v2_1_test/index.html", import.meta.url), "utf8"));
  assert.match(app.state.stdout, /^MyTech v2\.1 TEST: http:\/\/127\.0\.0\.1:\d+ \(offline; TEST binding required\)/);
});

test("launcher never loads implicit env files or falls back to legacy API credentials", async t => {
  const cwd = await temporary(t);
  for (const filename of [".env", ".env.v21.test", ".env.private.test"]) {
    await writeFile(join(cwd, filename), Object.entries(bound("app-id")).map(([k, v]) => `${k}=${v}`).join("\n"));
  }
  const app = cli(t, { cwd, env: { FASTGPT_API_KEY: "synthetic-legacy-secret", FASTGPT_APP_ID: "synthetic-legacy-app",
    FASTGPT_API_URL: "https://legacy.invalid" } });
  const base = await app.ready();
  assert.match(app.state.stdout, /TEST API binding: not configured \(offline\)/);
  assert.equal((await (await fetch(base + "/api/test/config")).json()).configured, false);
  assert.equal((await fetch(base + "/api/test/mytech", { method: "POST" })).status, 503);
  const incomplete = cli(t, { cwd, env: { ...bound("app-id"), MYTECH_TEST_FASTGPT_API_KEY: "",
    FASTGPT_API_KEY: "synthetic-legacy-secret" } });
  assert.equal(await incomplete.exited, 1);
  assert.match(incomplete.state.stderr, /MYTECH_DEMO_START_FAILED/);
  assert.ok(!incomplete.state.stderr.includes("synthetic"));
});

test("occupied TEST port has a clear sanitized startup error", async t => {
  const occupied = await host(t);
  const app = cli(t, { env: { ...bound("app-id"), MYTECH_TEST_PORT: String(occupied.server.address().port) } });
  assert.equal(await app.exited, 1); assert.equal(app.state.stdout, "");
  assert.match(app.state.stderr, /MYTECH_DEMO_PORT_IN_USE: MYTECH_TEST_PORT is already occupied/);
  assert.ok(!app.state.stderr.includes("synthetic"));
});

test("missing generated assets fail clearly without exposing configuration", async t => {
  const cwd = await temporary(t);
  for (const name of ["start-mytech-demo.mjs", "mytech_v2_1_test_server.mjs", "mytech_v2_1_test_adapter.mjs",
    "mytech_response.mjs", "mytech_v2_1_test_response.mjs"]) await copyFile(join(root, name), join(cwd, name));
  const alias = await directoryAlias(t, cwd);
  const aliasedEntry = join(alias, "start-mytech-demo.mjs");
  // Like macOS /var versus /private/var: argv retains the alias, ESM resolves it.
  assert.notEqual(aliasedEntry, await realpath(aliasedEntry));
  for (const [entry, args] of [[join(cwd, "start-mytech-demo.mjs"), []], [aliasedEntry, []],
    [aliasedEntry, ["--preserve-symlinks-main"]]]) {
    const app = cli(t, { cwd, entry, args, env: bound("app-id") });
    assert.equal(await app.exited, 1); assert.equal(app.state.stdout, "");
    assert.match(app.state.stderr, /MYTECH_DEMO_ASSETS_INVALID: required generated Quick Prompt Demo assets are missing or stale/);
    for (const value of ["synthetic", cwd, alias, "Bearer", "Authorization"]) {
      assert.ok(!app.state.stderr.includes(value));
    }
  }
});

test("launcher starts through a directory alias", async t => {
  const alias = await directoryAlias(t, root);
  for (const args of [[], ["--preserve-symlinks-main"]]) {
    const app = cli(t, { entry: join(alias, "start-mytech-demo.mjs"), args });
    const base = await app.ready();
    assert.equal(await (await fetch(base)).text(), html);
    assert.match(app.state.stdout, /TEST API binding: not configured \(offline\)/);
    assert.equal(app.state.stderr, "");
  }
});

test("importing the launcher leaves CLI startup inactive", async t => {
  const cwd = await temporary(t);
  const wrapper = join(cwd, "import-launcher.mjs");
  const script = `await import(${JSON.stringify(pathToFileURL(launcher).href)}); console.log("import completed");`;
  await writeFile(wrapper, script);
  // An ordinary importing entrypoint, stdin-style argv, and empty argv[1].
  for (const options of [{ entry: wrapper },
    { entry: "-", args: ["--input-type=module", "--eval", script, "--"] },
    { entry: "", args: ["--input-type=module", "--eval", script, "--"] }]) {
    const app = cli(t, { cwd, env: bound("app-id"), ...options });
    assert.equal(await app.exited, 0);
    assert.equal(app.state.stdout.trim(), "import completed");
    assert.equal(app.state.stderr, "");
  }
});
