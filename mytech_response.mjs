const USAGE_COMPATIBILITY = Object.freeze({
  Gaming: ["gaming"],
  Study: ["study", "note-taking", "reading"],
  Office: ["office", "productivity", "multitasking", "home use"],
  Creative: ["creative"],
  Photography: ["photography", "video", "social media"],
  Media: ["media", "entertainment", "video"],
  Music: ["music", "daily music"],
  Calls: ["calls"],
  Travel: ["travel", "commute", "portable"],
  Fitness: ["fitness", "health tracking", "daily health", "daily wear"],
  Development: ["development", "professional productivity", "heavy multitasking"],
  Productivity: ["productivity", "office", "multitasking", "creative work"],
  Typing: ["typing", "office", "productivity"],
  "Noise cancellation": ["noise cancellation", "travel", "commute"],
  Daily: ["daily", "general use", "home use", "daily wear"]
});

export function isPlainObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

export function normaliseOutput(output) {
  if (!isPlainObject(output) || !Array.isArray(output.recommendations)) return output;
  output.recommendations = output.recommendations.map((recommendation) => {
    if (!isPlainObject(recommendation)) return recommendation;
    const normalised = { ...recommendation };
    if (normalised.source === null) delete normalised.source;
    return normalised;
  });
  return output;
}

function usageIsCompatible(product, requestedUsage) {
  const acceptedTerms = USAGE_COMPATIBILITY[requestedUsage];
  if (!acceptedTerms) return true;
  const datasetUsages = product.main_usage.map((usage) => usage.toLowerCase());
  return datasetUsages.some((usage) => acceptedTerms.some((term) => usage.includes(term)));
}

export function validateOutput(output, budgets, usages, { productByName, supportedCategories }) {
  const errors = [];
  if (!isPlainObject(output)) return ["Output is not an object."];

  const allowedTopLevel = ["answer", "recommendations", "next_step", "clarification_needed"];
  const keys = Object.keys(output);
  allowedTopLevel.forEach((key) => {
    if (!keys.includes(key)) errors.push(`Missing ${key}.`);
  });
  keys.forEach((key) => {
    if (!allowedTopLevel.includes(key)) errors.push(`Unsupported field ${key}.`);
  });

  if (typeof output.answer !== "string" || !output.answer.trim()) errors.push("answer must be a non-empty string.");
  if (!Array.isArray(output.recommendations)) errors.push("recommendations must be an array.");
  if (typeof output.next_step !== "string") errors.push("next_step must be a string.");
  if (typeof output.clarification_needed !== "boolean") errors.push("clarification_needed must be a boolean.");

  const recommendations = Array.isArray(output.recommendations) ? output.recommendations : [];
  recommendations.forEach((recommendation, index) => {
    const label = `Recommendation ${index + 1}`;
    if (!isPlainObject(recommendation)) {
      errors.push(`${label} is not an object.`);
      return;
    }
    const allowedFields = ["category", "recommended_product", "price", "reason", "source"];
    const requiredFields = ["category", "recommended_product", "price", "reason"];
    const recommendationKeys = Object.keys(recommendation);
    requiredFields.forEach((key) => {
      if (!recommendationKeys.includes(key)) errors.push(`${label} is missing ${key}.`);
    });
    recommendationKeys.forEach((key) => {
      if (!allowedFields.includes(key)) errors.push(`${label} has unsupported field ${key}.`);
    });

    const product = productByName.get(recommendation.recommended_product);
    if (!product) {
      errors.push(`${label} is not in the approved dataset.`);
      return;
    }
    if (!supportedCategories.includes(recommendation.category) || recommendation.category !== product.category) {
      errors.push(`${label} category does not match the dataset.`);
    }
    if (typeof recommendation.price !== "number" || recommendation.price !== product.price_rmb) {
      errors.push(`${label} price does not match the dataset.`);
    }
    if (typeof recommendation.reason !== "string" || !recommendation.reason.trim()) {
      errors.push(`${label} reason is invalid.`);
    }
    if (Object.prototype.hasOwnProperty.call(recommendation, "source") && recommendation.source !== product.source) {
      errors.push(`${label} source does not match the dataset.`);
    }
    if (budgets[product.category] && product.price_rmb > budgets[product.category]) {
      errors.push(`${label} exceeds the active hard budget.`);
    }
    if (usages[product.category] && !usageIsCompatible(product, usages[product.category])) {
      errors.push(`${label} does not match the dataset usage tags.`);
    }
  });

  const visibleText = [
    typeof output.answer === "string" ? output.answer : "",
    typeof output.next_step === "string" ? output.next_step : "",
    ...recommendations.map((item) => typeof item?.reason === "string" ? item.reason : "")
  ].join(" ");
  if (/\b(?:live (?:price|pricing|availability)|currently in stock|available right now)\b/i.test(visibleText)) {
    errors.push("Output contains an unsupported live price or availability claim.");
  }
  return errors;
}

export function extractFastGptContent(apiResponse) {
  const content = apiResponse?.choices?.[0]?.message?.content;
  return typeof content === "string" ? content.trim() : "";
}

export function parseFastGptResponse(apiResponse) {
  const outputText = extractFastGptContent(apiResponse);
  if (!outputText) throw new Error("EMPTY_MODEL_OUTPUT");
  try {
    return JSON.parse(outputText);
  } catch {
    throw new Error("MODEL_OUTPUT_NOT_JSON");
  }
}
