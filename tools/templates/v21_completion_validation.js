// OFFLINE Phase 3 policy. Catalogue eligibility diagnoses omissions; it never
// manufactures recommendations or substitutes catalogue facts for retrieval.
function completionControlMessage(value) {
  const text = String(value || "").trim().replace(/[.!?]+$/, "");
  if (/^(?:hi|hello|hey)(?:\s+(?:hi|hello|hey|there|mytech))*$/i.test(text)) return true;
  const withoutGreeting = text.replace(/^(?:(?:hi|hello|hey)(?:\s+(?:there|mytech))?[,!]?\s+)+/i, "");
  // Whole capability questions only: no individual shopping category, budget,
  // usage qualifier or appended purchase clause is swallowed by this grammar.
  const capability = /^(?:(?:what|which) (?:(?:types|kinds) of )?(?:products|devices|electronics|electronic products|(?:product )?categories) (?:can|do|does) (?:you|mytech) (?:recommend|support)|what (?:can you|can mytech|do you|does mytech) (?:do|recommend|support|help(?: me)? with)|how can (?:you|mytech) help(?: me)?|(?:can|could) you help(?: me)?)$/i;
  if (capability.test(withoutGreeting)) return true;
  return /^(?:(?:hi|hello|hey)(?:\s+(?:hi|hello|hey|there|mytech))*|what (?:can you|can mytech|do you) (?:do|help(?: me)? with|recommend)|what (?:products|categories) (?:do you|does mytech) support|which (?:product )?categories can you recommend|(?:please )?(?:tell me a joke|write (?:me )?(?:an? |my )?essay|help me with my homework)|what(?:'s| is) the weather|(?:please )?(?:translate|quote|repair)\b.*)$/i.test(withoutGreeting)
    || /^(?:i (?:need|want)|(?:can you )?recommend)\s+(?:an?\s+)?(?:cameras?|printers?|televisions?|tvs?|routers?|speakers?|projectors?|consoles?)\b/i.test(withoutGreeting);
}

function completionNegativeClaim(answer, category) {
  // Each category must be the subject/object of its own affirmative negative
  // statement. A mention elsewhere in a clause is not a no-match explanation.
  // These words identify an intended negative result, not proof of its facts.
  // The catalogue calculation supplies that proof; canonical output replaces
  // all model prose on an accepted partial/empty no-match turn.
  const modifier = "(?:(?:valid|suitable|eligible|approved|cheaper|more affordable|less expensive|lower[- ]priced|more expensive|higher[- ]priced|alternative|different|another|other)\\s+)*";
  const subject = "(?:no\\s+" + modifier + category + "\\b|(?:i\\s+)?(?:could(?:n['’]t| not)|can(?:not|['’]t))\\s+find\\s+(?:(?:a|an|any)\\s+)?" + modifier + category + "\\b)";
  return String(answer || "").split(/(?:[.!?;\n](?!\d)|,?\s+(?:and|but)\s+|,\s*)/i)
    .some(clause => new RegExp("^\\s*" + subject + "[\\s\\S]*$", "i").test(clause));
}

function completionCanonicalNoMatch(output, omissions, intent) {
  const clauses = omissions.map(({ request, anchor }) => {
    const comparison = intent === "none" ? "" : intent === "alternative"
      ? "alternative " : intent === "cheaper" ? "cheaper " : "more expensive ";
    const relative = !anchor ? "" : intent === "alternative"
      ? " different from " + anchor.recommended_product
      : " than " + anchor.recommended_product + " (RMB " + anchor.price + ")";
    return "No " + comparison + request.category + " product" + relative + " in the MyTech test catalogue matches "
      + request.main_usage + " within RMB " + request.budget + ".";
  });
  return { ...output,
    answer: (output.recommendations.length ? "Reference recommendations are shown for the matching requests. " : "") + clauses.join(" "),
    next_step: "Would you like to change your requirements?", clarification_needed: false };
}

function completionHasRecord(evidence, product) {
  if (!Array.isArray(evidence)) return false;
  return evidence.some(chunk => {
    if (!chunk || typeof chunk !== "object") return false;
    // Structured offline records, or complete fields in a single RAG record.
    // Unknown/truncated chunk shapes remain insufficient evidence, never proof
    // of model failure. This recognizer is diagnostic only.
    if (chunk.product === product.product && chunk.category === product.category
      && (chunk.price_rmb ?? chunk.price) === (product.price_rmb ?? product.price)
      && chunk.source === product.source && Array.isArray(chunk.main_usage)
      && chunk.main_usage.length === product.main_usage.length
      && product.main_usage.every(tag => chunk.main_usage.includes(tag))) return true;
    const text = typeof chunk.a === "string" ? chunk.a : typeof chunk.content === "string" ? chunk.content : "";
    return text.split(/(?=^## Product Record:)/m).some(record => {
      const lines = record.split(/\r?\n/).map(line => line.trim());
      const uniqueFields = ["Product: ", "Category: ", "Reference Price: ", "Source: ", "Main Usage:"]
        .every(prefix => lines.filter(line => line.startsWith(prefix)).length === 1);
      const usageStart = lines.indexOf("Main Usage:") + 1;
      const usage = [];
      for (let i = usageStart; i < lines.length && lines[i].startsWith("- "); i++) usage.push(lines[i].slice(2));
      return uniqueFields && usage.length === product.main_usage.length
        && lines.includes("Product: " + product.product)
        && lines.includes("Category: " + product.category)
        && lines.includes("Reference Price: RMB " + (product.price_rmb ?? product.price))
        && lines.includes("Source: " + product.source)
        && product.main_usage.every(tag => usage.includes(tag));
    });
  });
}

function checkRecommendationCompletion(output, requests, catalogue, compatibility, options = {}) {
  const fail = (status, error) => ({ valid: false, status, error });
  if (!Array.isArray(output?.recommendations) || !Array.isArray(requests) || !requests.length) {
    return fail("invalid_completion_context", "A recommendation turn requires active requests and an array of recommendations.");
  }
  const products = Object.values(catalogue);
  const intent = options.intent || "none";
  if (!["none", "cheaper", "more_expensive", "alternative"].includes(intent)) return fail("invalid_completion_context", "Unknown comparison intent.");
  const returned = new Set(output.recommendations.map(item => item?.category));
  if (returned.size !== output.recommendations.length || [...returned].some(category => !requests.some(r => r?.category === category))) {
    return fail("invalid_completion_context", "Recommendations must have unique current-request categories.");
  }
  const seen = new Set();
  const omissions = [];
  for (const request of requests) {
    if (!request || !Number.isFinite(request.budget) || request.budget <= 0 || seen.has(request.category)
      || !products.some(p => p.category === request.category)) return fail("invalid_completion_context", "Each request needs a supported unique category and positive independent hard budget.");
    seen.add(request.category);
    const usage = parseCatalogueUsage(request.main_usage, catalogue, compatibility, request.category);
    if (!usage.valid) return fail("invalid_completion_context", usage.error);
    let anchor;
    if (intent !== "none") {
      const matches = (options.previous || []).filter(p => p?.category === request.category);
      anchor = matches.length === 1 ? matches[0] : null;
      const approved = products.find(p => p.product === anchor?.recommended_product && p.category === request.category);
      if (requests.length !== 1 || !approved || anchor.price !== (approved.price_rmb ?? approved.price)) {
        return fail("invalid_comparison_anchor", "A comparison requires one request and a unique validated same-category anchor.");
      }
    }
    if (returned.has(request.category)) continue;
    const eligible = products.filter(p => p.category === request.category && (p.price_rmb ?? p.price) <= request.budget
      && checkCatalogueUsage(p, request.main_usage, catalogue, compatibility).valid
      && (intent === "none" || (p.product !== anchor.recommended_product
        && (intent === "alternative" || (intent === "cheaper" ? (p.price_rmb ?? p.price) < anchor.price : (p.price_rmb ?? p.price) > anchor.price)))));
    omissions.push({ request, eligible, anchor });
  }
  if (!omissions.length) return { valid: true, status: output.recommendations.every(rec => {
    const product = products.find(p => p.product === rec.recommended_product);
    return product && completionHasRecord(options.evidence, product);
  }) ? "completed_with_recognized_evidence" : "completed_grounding_unverified" };
  const available = omissions.flatMap(item => item.eligible);
  if (available.length) {
    const evidence = options.evidence;
    const status = evidence === undefined ? "incomplete_or_evidence_uncertain"
      : Array.isArray(evidence) && !evidence.length ? "retrieval_evidence_empty"
      : available.some(p => completionHasRecord(evidence, p)) ? "incomplete_model_execution" : "retrieval_evidence_unverified";
    return fail(status, "An eligible catalogue request was omitted. This is not a verified catalogue no-match; no product was substituted.");
  }
  const deferred = /\b(?:(?:i|we) (?:will|shall)|i(?:'m| am) going to|we(?:'re| are) going to|let me|ready to|i now have all the information)\b[^.!?\n]*(?:recommend|find|suggest|information)/i.test([output.answer, output.next_step].join(" "))
    || /^(?:provide|generate|prepare|give)\b[^.!?\n]*\brecommendations?\b/i.test(output.next_step || "");
  if (deferred) return fail("incomplete_model_execution", "The response defers the current recommendation task.");
  for (const { request } of omissions) {
    const explained = completionNegativeClaim(output.answer, request.category);
    if (!explained) return fail("incomplete_model_execution", "Each omitted category needs an explicit verified no-match explanation.");
  }
  if (output.clarification_needed !== false) return fail("incomplete_model_execution", "A verified no-match is not a missing-information clarification.");
  return { valid: true, status: "verified_catalogue_no_match", output: completionCanonicalNoMatch(output, omissions, intent) };
}

// The browser has compact validated anchors and no retrieval trace. It can
// reject an unfulfilled request, but cannot diagnose the live retrieval cause.
function checkClientRecommendationCompletion(output, guard, catalogue, compatibility) {
  const categories = guard.targetCategories?.length ? guard.targetCategories : guard.activeCategories || [];
  const requests = categories.map(category => ({ category, budget: guard.budgetsByCategory?.[category], main_usage: guard.usagesByCategory?.[category] }));
  const control = guard.cancelled || guard.completionControl;
  const clarification = guard.ambiguousComparison || guard.ambiguousBetter || guard.usageClarificationNeeded;
  const incomplete = !requests.length || requests.some(r => !Number.isFinite(r.budget) || r.budget <= 0 || !r.main_usage);
  if (control || clarification || incomplete) return !output?.recommendations?.length
    && (control || !requests.length || output.clarification_needed === true)
    ? { valid: true, status: "non_recommendation_turn" }
    : { valid: false, status: "invalid_completion_context", error: "Clarify the current request before accepting products." };
  const previous = Object.entries(guard.previousRecommendationsByCategory || {}).map(([category, p]) =>
    ({ category, recommended_product: p.product, price: p.price }));
  return checkRecommendationCompletion(output, requests, catalogue, compatibility,
    { intent: guard.comparison === "another" ? "alternative" : guard.comparison || "none", previous });
}
