// Exercise native Node --env-file loading using public/synthetic fixtures only.
// Never open the workspace's private environment files or contact an upstream.
import test from "node:test";
import assert from "node:assert/strict";
import { readFile, mkdtemp, writeFile, rm } from "node:fs/promises";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { tmpdir } from "node:os";
import { join } from "node:path";

const execute = promisify(execFile);
const template = await readFile(new URL("../.env.example", import.meta.url), "utf8");
const moduleUrl = new URL("../mytech_v2_1_test_server.mjs", import.meta.url).href;
const fields = Object.fromEntries(template.split(/\r?\n/).filter(line => /^[A-Z][A-Z0-9_]*=/.test(line))
  .map(line => { const i = line.indexOf("="); return [line.slice(0, i), line.slice(i + 1)]; }));
const legacy = Object.fromEntries(["API_KEY", "API_URL", "APP_ID"].map((name, i) =>
  [`FASTGPT_${name}`, ["synthetic-legacy-only", "https://legacy.invalid/v1/chat/completions", "synthetic-legacy-app"][i]]));
const bound = binding => Object.fromEntries(["API_URL", "API_KEY", "BINDING", "APP_ID"].map((name, i) =>
  [`MYTECH_TEST_FASTGPT_${name}`, ["https://test.invalid/v1/chat/completions", "synthetic-test-only", binding,
    binding === "app-id" ? "synthetic-test-app" : ""][i]]));

async function load(t, overrides = {}, inherited = {}) {
  const directory = await mkdtemp(join(tmpdir(), "mytech-public-env-test-"));
  t.after(() => rm(directory, { recursive: true, force: true }));
  const path = join(directory, ".env");
  await writeFile(path, Object.entries({ ...fields, ...overrides }).map(([key, value]) => `${key}=${value}`).join("\n") + "\n");
  // Preserve only OS launch essentials; do not inherit developer credentials.
  const env = Object.fromEntries(["SystemRoot", "SYSTEMROOT", "WINDIR", "TEMP", "TMP"].filter(key => process.env[key] !== undefined)
    .map(key => [key, process.env[key]]));
  const script = `import { testServerConfig } from ${JSON.stringify(moduleUrl)};
    try {
      const c = testServerConfig(process.env);
      console.log(JSON.stringify({ configured: c.configured, port: c.port, binding: c.binding,
        timeout: c.requestTimeoutMs, maxTokens: c.maxTokens, timings: c.timings,
        testKeySelected: c.apiKey === "synthetic-test-only", testUrlSelected: c.apiUrl === "https://test.invalid/v1/chat/completions",
        testIdSelected: c.appId === "synthetic-test-app", legacyPort: process.env.PORT }));
    } catch (error) { console.log(JSON.stringify({ error: error.code })); }`;
  const { stdout, stderr } = await execute(process.execPath,
    [`--env-file=${path}`, "--input-type=module", "-e", script], { env: { ...env, ...inherited }, timeout: 15000 });
  assert.equal(stderr, "");
  return JSON.parse(stdout);
}

test("shared public template loads with safe defaults and no configured TEST binding", async t => {
  for (const key of ["FASTGPT_API_KEY", "FASTGPT_API_URL", "FASTGPT_APP_ID", "MYTECH_TEST_FASTGPT_API_URL",
    "MYTECH_TEST_FASTGPT_API_KEY", "MYTECH_TEST_FASTGPT_BINDING", "MYTECH_TEST_FASTGPT_APP_ID"]) assert.equal(fields[key], "");
  const result = await load(t);
  assert.equal(result.configured, false);
  assert.equal(result.port, 8788); assert.equal(result.legacyPort, "8787");
  assert.equal(result.timeout, 120000); assert.equal(result.maxTokens, 4096); assert.equal(result.timings, false);
});

test("one native env-file preserves independent legacy and TEST app-key bindings", async t => {
  const result = await load(t, { ...legacy, ...bound("app-key"), PORT: "9876" });
  assert.equal(result.configured, true); assert.equal(result.binding, "app-key");
  assert.equal(result.testKeySelected, true); assert.equal(result.testUrlSelected, true);
  assert.equal(result.testIdSelected, false); assert.equal(result.port, 8788); assert.equal(result.legacyPort, "9876");
});

test("one native env-file selects only the TEST app-id, independently of the legacy id", async t => {
  const result = await load(t, { ...legacy, ...bound("app-id") });
  assert.equal(result.configured, true); assert.equal(result.binding, "app-id");
  assert.equal(result.testIdSelected, true); assert.equal(result.testKeySelected, true); assert.equal(result.testUrlSelected, true);
});

test("legacy credentials cannot enable TEST or repair an incomplete TEST binding", async t => {
  assert.equal((await load(t, legacy)).configured, false);
  const partial = bound("app-key"); partial["MYTECH_TEST_FASTGPT_API_KEY"] = "";
  assert.equal((await load(t, { ...legacy, ...partial })).error, "INCOMPLETE_TEST_BINDING");
  assert.equal((await load(t, { ...legacy, ...bound("app-key"), MYTECH_TEST_FASTGPT_APP_ID: "synthetic-test-app" })).error,
    "INCOMPLETE_TEST_BINDING");
});

test("native env-file honors inherited variable precedence documented for migration", async t => {
  const result = await load(t, {}, { MYTECH_TEST_PORT: "8899", PORT: "8799" });
  assert.equal(result.port, 8899); assert.equal(result.legacyPort, "8799");
});
