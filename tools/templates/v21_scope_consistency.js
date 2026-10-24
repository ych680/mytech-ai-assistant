  // TEST-only consistency check, before comparison resolution. History alone
  // never supplies purchase intent or repairs a contradictory extraction.
  const currentInput = normalizeRmbInput(user_question);
  const purchaseEvidence = currentPurchaseEvidence(user_question);
  const hasExtractedUnsupported = product_requests.some(request => {
    const category = String(request?.category || "").trim().toLowerCase();
    return category && !Object.prototype.hasOwnProperty.call(supportedCategories, category);
  });
  const scopeContradiction = purchaseEvidence && normalizedScope !== "unsupported" && !hasExtractedUnsupported
    && (normalizedScope !== "supported" || product_requests.length === 0);
  if (scopeContradiction) {
    // Recover only literal current category/budget. Usage is unconfirmed when
    // extraction contradicts the message, so use the existing clarification path.
    product_requests = purchaseEvidence.map(request => ({ ...request, main_usage: null }));
    normalizedScope = "supported";
    normalizedIntent = "none";
    missing_fields = ["main_usage"];
    clarification_needed = true;
  }
