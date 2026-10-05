import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import {
  extractFastGptContent,
  parseFastGptResponse,
  normaliseOutput,
  validateOutput
} from "../mytech_response.mjs";

const dataset = JSON.parse(await readFile(
  new URL("../mytech_v1_product_dataset.json", import.meta.url), "utf8"
));
const catalogue = {
  productByName: new Map(dataset.products.map((product) => [product.product, product])),
  supportedCategories: dataset.supported_categories
};
const product = dataset.products.find((item) => item.category === "Laptop");

function recommendation(overrides = {}) {
  return {
    category: product.category,
    recommended_product: product.product,
    price: product.price_rmb,
    reason: "Suitable for study using the reference catalogue.",
    source: product.source,
    ...overrides
  };
}

function output(recommendations = [recommendation()]) {
  return {
    answer: "Here is a reference recommendation.",
    recommendations,
    next_step: "Tell me if you need another option.",
    clarification_needed: false
  };
}

function envelope(content) {
  return { choices: [{ message: { content } }] };
}

function validate(value, budgets = {}, usages = {}) {
  return validateOutput(value, budgets, usages, catalogue);
}

test("extracts the first FastGPT message and parses JSON with surrounding whitespace", () => {
  const expected = output();
  const text = JSON.stringify(expected);
  const response = envelope(` \n${text}\t `);
  response.choices.push({ message: { content: "invalid second choice" } });
  assert.equal(extractFastGptContent(response), text);
  assert.deepEqual(parseFastGptResponse(response), expected);
});

test("preserves empty-content and malformed-JSON error codes", () => {
  for (const response of [undefined, null, {}, { choices: [] }, envelope(null), envelope(42), envelope(""), envelope(" \n ")]) {
    assert.equal(extractFastGptContent(response), "");
    assert.throws(() => parseFastGptResponse(response), { message: "EMPTY_MODEL_OUTPUT" });
  }
  for (const content of ["{", "not JSON", "```json\n{}\n```", "prefix {} suffix"]) {
    assert.throws(() => parseFastGptResponse(envelope(content)), { message: "MODEL_OUTPUT_NOT_JSON" });
  }
  // Parsing accepts JSON values; validation is responsible for the object contract.
  assert.equal(parseFastGptResponse(envelope("null")), null);
  assert.deepEqual(validate(null), ["Output is not an object."]);
});

test("normalizes optional source while preserving current mutation behavior", () => {
  const absent = recommendation();
  delete absent.source;
  const original = [recommendation({ source: null }), absent, recommendation(), null];
  const value = output(original);
  assert.strictEqual(normaliseOutput(value), value);
  assert.notStrictEqual(value.recommendations, original);
  assert.notStrictEqual(value.recommendations[0], original[0]);
  assert.equal(original[0].source, null);
  assert.deepEqual(value.recommendations[0], absent);
  assert.deepEqual(value.recommendations[1], absent);
  assert.deepEqual(value.recommendations[2], recommendation());
  assert.equal(value.recommendations[3], null);
  assert.deepEqual(validate(output(value.recommendations.slice(0, 3))), []);
  for (const untouched of [null, [], { recommendations: "invalid" }]) {
    assert.strictEqual(normaliseOutput(untouched), untouched);
  }
});

test("rejects missing, unsupported, and invalid response fields", () => {
  for (const field of ["answer", "recommendations", "next_step", "clarification_needed"]) {
    const value = output();
    delete value[field];
    assert.ok(validate(value).includes(`Missing ${field}.`));
  }
  for (const [field, value, error] of [
    ["answer", " ", "answer must be a non-empty string."],
    ["answer", 42, "answer must be a non-empty string."],
    ["recommendations", {}, "recommendations must be an array."],
    ["next_step", null, "next_step must be a string."],
    ["clarification_needed", "false", "clarification_needed must be a boolean."],
    ["extra", true, "Unsupported field extra."]
  ]) {
    assert.ok(validate({ ...output(), [field]: value }).includes(error));
  }
  for (const field of ["category", "recommended_product", "price", "reason"]) {
    const rec = recommendation();
    delete rec[field];
    assert.ok(validate(output([rec])).includes(`Recommendation 1 is missing ${field}.`));
  }
  assert.deepEqual(validate(output([null])), ["Recommendation 1 is not an object."]);
  assert.deepEqual(validate(output([recommendation({ extra: true })])), ["Recommendation 1 has unsupported field extra."]);
  for (const reason of [" ", null, 42]) {
    assert.deepEqual(validate(output([recommendation({ reason })])), ["Recommendation 1 reason is invalid."]);
  }
  assert.deepEqual(validate({ ...output(), answer: "This is currently in stock." }), [
    "Output contains an unsupported live price or availability claim."
  ]);
});

test("accepts catalogue recommendations and valid no-result or clarification responses", () => {
  assert.deepEqual(validate(output()), []);
  const noResult = { ...output([]), answer: "No suitable product is available in the reference catalogue.", next_step: "" };
  assert.deepEqual(validate(noResult), []);
  assert.deepEqual(validate({ ...noResult, answer: "What is your maximum budget?", clarification_needed: true }), []);
});

test("rejects unknown products and category, price, and source mismatches", () => {
  for (const [overrides, error] of [
    [{ recommended_product: "Unknown product" }, "Recommendation 1 is not in the approved dataset."],
    [{ category: "Mouse" }, "Recommendation 1 category does not match the dataset."],
    [{ category: "Unsupported" }, "Recommendation 1 category does not match the dataset."],
    [{ price: product.price_rmb + 1 }, "Recommendation 1 price does not match the dataset."],
    [{ price: String(product.price_rmb) }, "Recommendation 1 price does not match the dataset."],
    [{ source: "Different source" }, "Recommendation 1 source does not match the dataset."],
    [{ source: null }, "Recommendation 1 source does not match the dataset."]
  ]) {
    assert.deepEqual(validate(output([recommendation(overrides)])), [error]);
  }
});

test("accepts the exact hard-budget boundary and rejects over-budget products", () => {
  assert.deepEqual(validate(output(), { [product.category]: product.price_rmb }), []);
  assert.deepEqual(validate(output(), { [product.category]: product.price_rmb - 1 }), [
    "Recommendation 1 exceeds the active hard budget."
  ]);
  assert.deepEqual(validate(output(), { Mouse: 1 }), []);
});

test("validates recognized usage constraints and preserves unrecognized-usage behavior", () => {
  assert.deepEqual(validate(output(), {}, { [product.category]: "Study" }), []);
  assert.deepEqual(validate(output(), {}, { [product.category]: "Gaming" }), [
    "Recommendation 1 does not match the dataset usage tags."
  ]);
  assert.deepEqual(validate(output(), {}, { [product.category]: "Unrecognized usage" }), []);
  assert.deepEqual(validate(output(), {}, { Mouse: "Gaming" }), []);
});
