// Opt-in private hotfix tests. Actual candidate code/graph/adapter; fixture AI only.
import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile, mkdtemp, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { Script, createContext } from "node:vm";
import { createTestAdapter } from "../mytech_v2_1_test_adapter.mjs";
import { repairFrontend } from "./helpers/v21-repair-frontend.mjs";

const selected = process.env.MYTECH_NOMATCH_CANDIDATE;
if (!selected) {
  test("school no-match hotfix requires explicit candidate selection", { skip: "No private candidate selected; no Downloads access." }, () => {});
} else {
  await test("school no-match hotfix candidate regression", async t => {
    assert.ok(process.env.MYTECH_NOMATCH_SOURCE, "Explicit upgraded school source required");
    const root = new URL("../", import.meta.url);
    const sha = raw => createHash("sha256").update(raw).digest("hex");
    const candidatePath = resolve(selected);
    const raw = await readFile(candidatePath);
    const sourceRaw = await readFile(resolve(process.env.MYTECH_NOMATCH_SOURCE));
    const graph = JSON.parse(raw.toString("utf8").replace(/^\uFEFF/, ""));
    const source = JSON.parse(sourceRaw.toString("utf8").replace(/^\uFEFF/, ""));
    const report = JSON.parse(await readFile(join(dirname(candidatePath), "nomatch-preservation.json"), "utf8"));
    const master = JSON.parse(await readFile(new URL("catalogue/mytech_products_v2_1_test.json", root), "utf8"));
    const field = (w, id, key) => w.nodes.find(n => n.nodeId === id).inputs.find(f => f.key === key).value;
    const validatorId = "fakNM8mmlYmewx67";
    const code = field(graph, validatorId, "code");
    const oldCode = field(source, validatorId, "code");
    const script = new Script(code + "\nmain(input);");
    const oldScript = new Script(oldCode + "\nmain(input);");
    const product = id => master.products.find(p => p.id === id);
    const rec = id => { const p = product(id); return { category: p.category, recommended_product: p.product,
      price: p.price_rmb, source: p.source, reason: "Matches the reference usage and hard budget." }; };
    const response = (ids = [], answer = "Reference recommendation.") => ({ answer, recommendations: ids.map(rec),
      next_step: "Would you like to change your requirements?", clarification_needed: false });
    const laptop = { category: "Laptop", budget: 6000, main_usage: "gaming" };
    const mouse = { category: "Mouse", budget: 300, main_usage: "gaming" };
    const anchors = [rec("LAP-005"), rec("MOU-004")];
    const exactRaw = `{
  "answer": "No cheaper gaming laptop is available in the current MyTech reference data within your ¥6,000 budget.",
  "recommendations": [],
  "next_step": "Consider adjusting your requirements or budget, or ask about a different product category.",
  "clarification_needed": false
}`;
    const input = (output = JSON.parse(exactRaw), requests = [laptop], previous = anchors, intent = "cheaper") => ({
      raw_json: JSON.stringify(output), active_requests: structuredClone(requests),
      previous_recommendations: structuredClone(previous), follow_up_intent: intent, retrieved_evidence: [] });
    const execute = (value, compiled = script) => {
      const context = createContext({ input: structuredClone(value) }, { codeGeneration: { strings: false, wasm: false } });
      const result = JSON.parse(JSON.stringify(compiled.runInContext(context, { timeout: 1000 })));
      assert.deepEqual(context.input, value, "candidate must not mutate inputs");
      return result;
    };
    const directory = await mkdtemp(join(tmpdir(), "mytech-nomatch-hotfix-"));
    t.after(() => rm(directory, { recursive: true, force: true }));
    // The unchanged adapter reads the selected candidate, not a reference.
    // The export retains its BOM; strip only that BOM in the temporary runtime
    // copy because the adapter uses JSON.parse. Verify semantic identity below.
    await writeFile(join(directory, "mytech-fastgpt-workflow-v2_1-TEST.json"), raw.toString("utf8").replace(/^\uFEFF/, ""));
    assert.deepEqual(JSON.parse(await readFile(join(directory, "mytech-fastgpt-workflow-v2_1-TEST.json"), "utf8")), graph);
    for (const name of ["catalogue.json", "MyTech_Product_Knowledge_v2_1_TEST.md"]) {
      await writeFile(join(directory, name), await readFile(new URL("generated/v21_quick_prompt_demo/local/" + name, root)));
    }
    const adapter = await createTestAdapter(directory);

    await t.test("fingerprints and only the recognizer change; all school architecture, metadata and contracts preserved", async () => {
      assert.equal(sha(raw), report.candidate_sha256);
      assert.equal(sha(sourceRaw), "c7389bf0896b81216604b3c0dde7e79a8d8ed825ffc43e925cb1fe9605d54b84");
      assert.equal(sha(sourceRaw), report.source_school_sha256);
      assert.deepEqual(report.semantic_diff, [{ op: "replace", path: "/nodes/11/inputs/2/value" }]);
      const restored = structuredClone(graph);
      restored.nodes.find(n => n.nodeId === validatorId).inputs.find(f => f.key === "code").value = oldCode;
      assert.deepEqual(restored, source);
      const helper = text => text.match(/function completionNegativeClaim\(answer, category\) \{[\s\S]*?(?=\n\nfunction completionCanonicalNoMatch\()/)[0];
      assert.equal(code.replace(helper(code), helper(oldCode)), oldCode);
      assert.equal(helper(code), (await readFile(new URL("tools/templates/v21_completion_negative_claim.js", root), "utf8")).trimEnd());
      const literal = text => Buffer.from(JSON.stringify(text));
      assert.deepEqual(Buffer.from(raw.toString("utf8").replace(literal(code).toString(), literal(oldCode).toString())), sourceRaw);
      assert.equal(graph.nodes.length, 20); assert.equal(graph.edges.length, 18);
      for (const id of ["etNrwEXVwr5sySpK", "ikIzMK483vihRths", "pskHz4kajjJnBWwG"]) {
        assert.equal(field(graph, id, "model"), "deepseek/deepseek-v4.1-flash");
      }
    });

    await t.test("exact October 29 failure reproduces before fix and canonicalizes after fix without losing either anchor", () => {
      const value = { ...input(), raw_json: exactRaw };
      const before = execute(value, oldScript);
      assert.equal(before.validation_ok, false);
      assert.equal(before.completion_status, "incomplete_model_execution");
      assert.equal(before.validation_error, "incomplete_model_execution: Each omitted category needs an explicit verified no-match explanation.");
      const after = execute(value);
      assert.equal(after.validation_ok, true); assert.equal(after.completion_status, "verified_catalogue_no_match");
      assert.equal(after.validation_error, ""); assert.deepEqual(after.recommendations, []);
      assert.deepEqual(after.recommendations_to_store, anchors);
      const canonical = JSON.parse(after.normalized_json);
      assert.equal(canonical.answer, `No cheaper Laptop product than ${product("LAP-005").product} (RMB 4999) in the MyTech test catalogue matches gaming within RMB 6000.`);
      assert.equal(canonical.next_step, "Would you like to change your requirements?");
      assert.deepEqual(Object.keys(canonical).sort(), ["answer", "recommendations", "next_step", "clarification_needed"].sort());
      assert.deepEqual(adapter.validate(value).result, after);
    });

    for (const answer of ["No cheaper gaming laptop is available.", "No cheaper Laptop is available.",
      "I couldn't find a cheaper gaming laptop.", "I could not find a cheaper gaming laptop."]) {
      await t.test(`bounded negative claim accepted: ${answer}`, () => {
        const r = execute(input(response([], answer)));
        assert.equal(r.validation_ok, true); assert.equal(r.completion_status, "verified_catalogue_no_match");
        assert.deepEqual(r.recommendations_to_store, anchors);
      });
    }

    await t.test("RMB 7999 gaming anchor cannot hide the eligible RMB 4999 cheaper laptop under RMB 8000", () => {
      const value = input(JSON.parse(exactRaw), [{ ...laptop, budget: 8000 }], [rec("LAP-006"), rec("MOU-004")]);
      const r = execute(value);
      assert.equal(r.validation_ok, false); assert.match(r.validation_error, /eligible catalogue request was omitted/);
      assert.deepEqual(r.recommendations_to_store, value.previous_recommendations);
      assert.equal(adapter.validate(value).valid, false);
    });

    for (const answer of ["No cheaper gaming Mouse is available.", "No Mouse matches; Laptop is available.",
      "I will recommend a laptop later.", "Got it.", "It is not true that no cheaper gaming laptop is available.",
      'The report says "No cheaper gaming laptop is available".', "No cheaper imaginary laptop is available.",
      "No cheaper gaming gaming laptop is available.", "No cheaper gaming and office laptop is available."]) {
      await t.test(`unsafe or unrelated prose rejected: ${answer}`, () => {
        const value = input(response([], answer)), r = execute(value);
        assert.equal(r.validation_ok, false); assert.deepEqual(r.recommendations, []);
        assert.deepEqual(r.recommendations_to_store, anchors); assert.equal(adapter.validate(value).valid, false);
      });
    }

    await t.test("gaming adjective remains Laptop-only even for an otherwise eligible Mouse negative claim", () => {
      const r = execute(input(response([], "No cheaper gaming Mouse is available."), [mouse]));
      assert.equal(r.validation_ok, false); assert.match(r.validation_error, /explicit verified no-match/);
      assert.deepEqual(r.recommendations_to_store, anchors);
    });

    await t.test("partial multi-product false omission rejects the entire batch and preserves both anchors", () => {
      const r = execute(input(response(["MOU-004"], "No gaming laptop is available."), [laptop, mouse], anchors, "none"));
      assert.equal(r.validation_ok, false); assert.deepEqual(r.recommendations, []);
      assert.deepEqual(r.recommendations_to_store, anchors);
    });

    for (const [label, mutate] of [
      ["malformed JSON", v => { v.raw_json = "{"; }],
      ["fabricated product", v => { const o = response(["LAP-005"]); o.recommendations[0].recommended_product = "Imaginary Laptop"; v.raw_json = JSON.stringify(o); }],
      ["false price", v => { const o = response(["LAP-005"]); o.recommendations[0].price = 1; v.raw_json = JSON.stringify(o); }],
      ["over-budget product", v => { v.follow_up_intent = "none"; v.active_requests[0].budget = 4000; v.raw_json = JSON.stringify(response(["LAP-005"])); }],
      ["same-price cheaper comparison", v => { v.raw_json = JSON.stringify(response(["LAP-005"])); }],
      ["forged anchor", v => { v.previous_recommendations[0].price = 7999; }],
      ["duplicate anchor", v => { v.previous_recommendations.push(rec("LAP-005")); }],
      ["unknown intent", v => { v.follow_up_intent = "better"; }]
    ]) {
      await t.test(`existing safeguard retained: ${label}`, () => {
        const value = input(); mutate(value); const r = execute(value);
        assert.equal(r.validation_ok, false); assert.deepEqual(r.recommendations, []);
        assert.deepEqual(r.recommendations_to_store, value.previous_recommendations);
      });
    }

    for (const intent of ["cheaper", "more_expensive", "alternative"]) {
      await t.test(`legitimate gaming Laptop ${intent} no-match remains accepted and canonical`, () => {
        const wording = intent === "alternative" ? "alternative" : intent.replace("_", " ");
        const r = execute(input(response([], `No ${wording} gaming laptop is available.`), [laptop], anchors, intent));
        assert.equal(r.validation_ok, true); assert.equal(r.completion_status, "verified_catalogue_no_match");
        assert.deepEqual(r.recommendations_to_store, anchors);
      });
    }

    // Replay pinned existing suites against the selected candidate, altering only
    // module registration and directory loading in memory. Archived files stay intact.
    async function replay(filename, label, exported = "") {
      const url = new URL(filename, import.meta.url);
      let sourceText = await readFile(url, "utf8");
      assert.equal(sha(Buffer.from(sourceText)), report.sources_sha256["tests/" + filename]);
      const pending = [], key = Symbol.for("mytech.nomatch.test.registration");
      globalThis[key] = (name, fn) => {
        const promise = t.test(`${label}: ${name}`, { skip: /^local (?:TEST|candidate) server/.test(name)
          ? "Socket/HTTP test deliberately excluded; offline candidate verification." : false }, fn);
        pending.push(promise); return promise;
      };
      let changes = 0;
      sourceText = sourceText.replace('import test from "node:test";', () => { changes++; return 'const test = globalThis[Symbol.for("mytech.nomatch.test.registration")];'; });
      sourceText = sourceText.replace(/from "(\.\.?\/[^"\n]+)"/g, (_, relative) => `from ${JSON.stringify(new URL(relative, url).href)}`);
      if (filename === "quick-prompt-demo.test.mjs") {
        sourceText = sourceText.replace('new URL("../generated/v21_quick_prompt_demo/local/", import.meta.url)', () => {
          changes++; return JSON.stringify(pathToFileURL(directory + "/").href);
        });
        assert.equal(changes, 2);
      } else {
        sourceText = sourceText.replace(/const packageName = process\.env\.[A-Z_]+ \|\| "[^"]+";/, () => {
          changes++; return 'const packageName = "v21_quick_prompt_demo";';
        });
        sourceText = sourceText.replace(/const directory = new URL\(`generated\/\$\{packageName\}\/local\/`, root\);/, () => {
          changes++; return `const directory = new URL(${JSON.stringify(pathToFileURL(directory + "/").href)});`;
        });
        assert.equal(changes, 3);
      }
      sourceText = sourceText.replaceAll("import.meta.url", JSON.stringify(url.href));
      try {
        const module = await import("data:text/javascript;base64," + Buffer.from(sourceText + "\n" + exported).toString("base64"));
        await Promise.all(pending); return module;
      } finally { delete globalThis[key]; }
    }
    await replay("usage-repair.test.mjs", "candidate PR17");
    const native = await replay("completion-repair.test.mjs", "candidate PR18", "export { nativeTurn, response, rec, laptop, mouse };");
    await replay("quick-prompt-demo.test.mjs", "candidate Quick Prompt Demo");

    await t.test("full graph reproduces the initial pair, cheaper mouse, then exact cheaper-laptop no-match", async () => {
      const first = native.nativeTurn("I need a laptop under RMB 6000 for gaming and a mouse under RMB 300 for gaming.",
        { requests: [laptop, mouse], output: native.response(["LAP-005", "MOU-002"]) });
      assert.equal(first.validation.validation_ok, true);
      const second = native.nativeTurn("Can you recommend a cheaper mouse?", { state: first.state,
        requests: [laptop, mouse], intent: "cheaper", output: native.response(["MOU-004"]) });
      assert.equal(second.validation.validation_ok, true);
      const before = structuredClone(second.state);
      const third = native.nativeTurn("Can you recommend a cheaper laptop?", { state: second.state,
        requests: [laptop, mouse], intent: "cheaper", output: JSON.parse(exactRaw) });
      assert.equal(third.validation.validation_ok, true);
      assert.equal(third.validation.completion_status, "verified_catalogue_no_match");
      assert.deepEqual(third.validation.recommendations_to_store, before.last_recommendations);
      assert.deepEqual(third.state.last_recommendations, before.last_recommendations);
      assert.deepEqual(third.state.product_requests, before.product_requests);
      assert.deepEqual(third.validatorInput.active_requests, [laptop]);
      assert.equal(third.trace.includes("oibK1q4js1HXjiO2"), true);
      assert.deepEqual(third.output, JSON.parse(third.validation.normalized_json));
      for (const kind of ["local", "aiep"]) {
        const app = await repairFrontend(kind, "v21_quick_prompt_demo");
        await app.submit("I need a laptop under RMB 6000 for gaming and a mouse under RMB 300 for gaming.", first.output);
        await app.submit("Can you recommend a cheaper mouse?", second.output);
        const prior = app.state().sessionContext.lastRecommendationsByCategory;
        await app.submit("Can you recommend a cheaper laptop?", third.output);
        assert.deepEqual(app.state().sessionContext.lastRecommendationsByCategory, prior);
        assert.doesNotMatch(app.text(), /couldn't safely validate/);
      }
    });

    await t.test("failed follow-up skips recommendation writer and subsequent valid turn uses preserved anchors", () => {
      const state = { product_requests: [laptop, mouse], last_recommendations: anchors };
      const bad = native.nativeTurn("Can you recommend a cheaper laptop?", { state, requests: [laptop, mouse],
        intent: "cheaper", output: response([], "No cheaper gaming Mouse is available.") });
      assert.equal(bad.validation.validation_ok, false); assert.deepEqual(bad.state.last_recommendations, anchors);
      assert.equal(bad.trace.includes("oibK1q4js1HXjiO2"), false);
      const next = native.nativeTurn("Can you recommend a more expensive mouse?", { state: bad.state,
        requests: [laptop, mouse], intent: "more_expensive", output: response(["MOU-002"]) });
      assert.equal(next.validation.validation_ok, true);
      assert.deepEqual(next.state.last_recommendations, [rec("LAP-005"), rec("MOU-002")]);
    });
  });
}
