// Opt-in private candidate verification. Existing suites and packages are untouched.
// Providers/frontends are in-memory fixtures; no socket or model calls are made.
import test, { after } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile, mkdtemp, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const selected = process.env.MYTECH_SCHOOL_CANDIDATE;
if (!selected) {
  test("school-derived private candidate requires explicit MYTECH_SCHOOL_CANDIDATE", { skip: "No private candidate selected; never reads Downloads implicitly." }, () => {});
} else {
  await test("private school-derived candidate regression replay", async t => {
    const pending = [];
    const register = (...args) => {
      const result = t.test(...args);
      pending.push(result);
      return result;
    };
    const root = new URL("../", import.meta.url);
    const sha = raw => createHash("sha256").update(raw).digest("hex");
    const candidatePath = resolve(selected);
    assert.equal(candidatePath.endsWith(".private-export.json"), true);
    const candidateRaw = await readFile(candidatePath);
    const candidate = JSON.parse(candidateRaw);
    const report = JSON.parse(await readFile(join(dirname(candidatePath), "preservation.json"), "utf8"));
    assert.equal(sha(candidateRaw), report.candidate_sha256, "candidate must match the preservation report");
    assert.equal(report.source_school_sha256, "31a3d18d2fcb2ee3c9b1fb215b8b5ce96003cc1f76ca57022d3a40361b8fc738");
    const directory = await mkdtemp(join(tmpdir(), "mytech-school-validator-"));
    after(() => rm(directory, { recursive: true, force: true }));
    // The real, unchanged adapter reads this exact private candidate copy.
    await writeFile(join(directory, "mytech-fastgpt-workflow-v2_1-TEST.json"), candidateRaw);
    await writeFile(join(directory, "catalogue.json"), await readFile(new URL("generated/v21_quick_prompt_demo/local/catalogue.json", root)));
    await writeFile(join(directory, "MyTech_Product_Knowledge_v2_1_TEST.md"),
      await readFile(new URL("generated/v21_quick_prompt_demo/local/MyTech_Product_Knowledge_v2_1_TEST.md", root)));
    const reference = JSON.parse(await readFile(new URL("generated/v21_quick_prompt_demo/workflow-completion-repair.json", root), "utf8"));
    const field = (graph, id, key) => graph.nodes.find(n => n.nodeId === id).inputs.find(i => i.key === key).value;

    register("school candidate preserves models, graph, prompts and reviewed evidence/diagnostic contracts", () => {
      assert.equal(candidate.nodes.length, 20);
      assert.deepEqual(candidate.edges, reference.edges);
      assert.deepEqual(candidate.chatConfig.variables, reference.chatConfig.variables);
      for (const [id, key] of [["etNrwEXVwr5sySpK", "description"], ["ikIzMK483vihRths", "systemPrompt"], ["pskHz4kajjJnBWwG", "systemPrompt"]]) {
        assert.equal(field(candidate, id, "model"), "deepseek/deepseek-v4.1-flash");
        assert.equal(sha(Buffer.from(field(candidate, id, key))), report.preserved.ai_nodes[id].sha256);
      }
      const actual = candidate.nodes.find(n => n.nodeId === "fakNM8mmlYmewx67");
      const reviewed = reference.nodes.find(n => n.nodeId === "fakNM8mmlYmewx67");
      assert.deepEqual(actual, reviewed, "all candidate validator contracts and code must be exactly reviewed");
      assert.equal(actual.inputs[7].required, false);
      assert.equal(actual.inputs[7].valueType, "datasetQuote");
      assert.deepEqual(actual.inputs[7].value, ["zWAw4oYVL1QMe8YX", "quoteQA"]);
      assert.equal(actual.outputs[11].id, "phase3CompletionStatus");
      assert.equal(actual.outputs[11].valueType, "string");
      assert.deepEqual(report.semantic_diff.map(c => c.path), ["/nodes/11/inputs/2/value", "/nodes/11/inputs/7", "/nodes/11/outputs/11", "/nodes/14/inputs/0/value"]);
    });

    async function replay(filename, label, exports = "") {
      const url = new URL(filename, import.meta.url);
      let source = await readFile(url, "utf8");
      assert.equal(sha(Buffer.from(source)), report.sources_sha256["tests/" + filename], "reviewed suite changed");
      // Adapt only suite loading/registration in memory. No existing test is edited.
      // Workflow and adapter read the new candidate. UI checks use unchanged Demo HTML.
      const registration = Symbol.for("mytech.school.candidate.test.registration");
      globalThis[registration] = (name, fn) => register(`${label}: ${name}`, {
        skip: /^local (?:TEST|candidate) server/.test(name) ? "Socket-based test excluded; no HTTP transport authorized." : false
      }, fn);
      let replacements = 0;
      source = source.replace('import test from "node:test";', () => {
        replacements++;
        return 'const test = globalThis[Symbol.for("mytech.school.candidate.test.registration")];';
      });
      source = source.replace(/from "(\.\.?\/[^"\n]+)"/g, (_, relative) => `from ${JSON.stringify(new URL(relative, url).href)}`);
      source = source.replaceAll("import.meta.url", JSON.stringify(url.href));
      source = source.replace(/const packageName = process\.env\.[A-Z_]+ \|\| "[^"]+";/, () => {
        replacements++;
        return 'const packageName = "v21_quick_prompt_demo";';
      });
      source = source.replace(/const directory = new URL\(`generated\/\$\{packageName\}\/local\/`, root\);/, () => {
        replacements++;
        return `const directory = new URL(${JSON.stringify(pathToFileURL(directory + "/").href)});`;
      });
      assert.equal(replacements, 3, "suite-loader contract drift must fail closed");
      try {
        return await import("data:text/javascript;base64," + Buffer.from(source + "\n" + exports).toString("base64"));
      } finally {
        delete globalThis[registration];
      }
    }

    await replay("usage-repair.test.mjs", "school candidate PR17");
    const harness = await replay("completion-repair.test.mjs", "school candidate PR18",
      "export { nativeTurn, response, rec, laptop, mouse };");

    register("school candidate rejects partial completion then accepts a new comparison with preserved anchors", () => {
      const { nativeTurn, response, rec, laptop, mouse } = harness;
      const message = "I need a laptop under RMB 6000 for gaming and a mouse under RMB 300 for gaming.";
      const first = nativeTurn(message, { requests: [laptop, mouse], output: response(["LAP-005", "MOU-002"]) });
      assert.equal(first.validation.validation_ok, true);
      const bad = nativeTurn(message, { state: first.state, requests: [laptop, mouse], output: response(["LAP-005"], "No Mouse matches.") });
      assert.equal(bad.validation.validation_ok, false);
      assert.deepEqual(bad.state.last_recommendations, first.state.last_recommendations);
      assert.equal(bad.trace.includes("oibK1q4js1HXjiO2"), false);
      const next = nativeTurn("Can you recommend a cheaper mouse?", { state: bad.state,
        requests: [laptop, mouse], intent: "cheaper", output: response(["MOU-004"]) });
      assert.equal(next.validation.validation_ok, true);
      assert.deepEqual(next.state.last_recommendations, [rec("LAP-005"), rec("MOU-004")]);
    });
    await Promise.all(pending);
  });
}
