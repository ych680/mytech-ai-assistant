function completionNegativeClaim(answer, category) {
  // Each category must be the subject/object of its own affirmative negative
  // statement. A mention elsewhere in a clause is not a no-match explanation.
  // These words identify an intended negative result, not proof of its facts.
  // The catalogue calculation supplies that proof; canonical output replaces
  // all model prose on an accepted partial/empty no-match turn.
  const modifier = "(?:(?:valid|suitable|eligible|approved|cheaper|more affordable|less expensive|lower[- ]priced|more expensive|higher[- ]priced|alternative|different|another|other)\\s+)*";
  // One known usage adjective for Laptop only; never arbitrary intervening prose.
  const categorySubject = modifier + (category === "Laptop" ? "(?:gaming\\s+)?" : "") + category + "\\b";
  const subject = "(?:no\\s+" + categorySubject + "|(?:i\\s+)?(?:could(?:n['’]t| not)|can(?:not|['’]t))\\s+find\\s+(?:(?:a|an|any)\\s+)?" + categorySubject + ")";
  return String(answer || "").split(/(?:[.!?;\n](?!\d)|,?\s+(?:and|but)\s+|,\s*)/i)
    .some(clause => new RegExp("^\\s*" + subject + "[\\s\\S]*$", "i").test(clause));
}
