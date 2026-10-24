  function invalidResult(message) {
    const safe = {
      answer: "I couldn't safely validate a recommendation for your requirements.",
      recommendations: [],
      next_step: "Please restate the category, maximum budget and main usage.",
      clarification_needed: true
    };
    return {
      ...safe,
      validation_ok: false,
      validation_error: message,
      // Current's validation router skips its writer on failure. Keep safe
      // memory output too, so rejected results cannot replace prior anchors.
      recommendations_to_store: Array.isArray(previous_recommendations)
        ? previous_recommendations.map(item => ({ ...item })) : [],
      normalized_json: JSON.stringify(safe)
    };
  }
