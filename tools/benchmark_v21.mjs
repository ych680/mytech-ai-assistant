// Offline local validation cost only. No transport, secrets, prompts or outputs logged.
import { performance } from "node:perf_hooks";
import { createTestAdapter } from "../mytech_v2_1_test_adapter.mjs";

const started = performance.now();
const adapter = await createTestAdapter();
const startupMs = performance.now() - started;
const samples = [];
for (let index = 0; index < 220; index++) {
  const product = adapter.catalogue.products[index % adapter.catalogue.products.length];
  const input = {
    raw_json: JSON.stringify({ answer: "TEST reference candidate.", recommendations: [{
      category: product.category, recommended_product: product.product, price: product.price_rmb,
      reason: "Matches a Master Dataset usage tag.", source: product.source
    }], next_step: "", clarification_needed: false }),
    active_requests: [{ category: product.category, budget: product.price_rmb, main_usage: product.main_usage[0] }],
    previous_recommendations: [], follow_up_intent: "none"
  };
  const before = performance.now();
  if (!adapter.validate(input).valid) throw new Error("OFFLINE_VALIDATION_FAILED");
  if (index >= 20) samples.push(performance.now() - before);
}
samples.sort((a, b) => a - b);
console.log(JSON.stringify({ scope: "offline validation only; excludes FastGPT, retrieval, model and network latency",
  products: adapter.catalogue.products.length, samples: samples.length,
  startupMs: +startupMs.toFixed(3), medianMs: +samples[Math.floor(samples.length * .5)].toFixed(3),
  p95Ms: +samples[Math.ceil(samples.length * .95) - 1].toFixed(3) }, null, 2));
