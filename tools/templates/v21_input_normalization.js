// TEST-only pure input helpers. No currency conversion and no history inference.
function normalizeRmbInput(value) {
  const text = String(value == null ? "" : value);
  const codes = "(?:USD|EUR|GBP|JPY|HKD|AUD|CAD|SGD|NZD|KRW|TWD|INR|CHF|THB|MYR|IDR|PHP|VND|ZAR|BRL|AED|SAR|RUB|TRY|PLN|SEK|NOK|DKK)";
  const foreign = /\b(?:dollars?|euros?|pounds?|yen|rupees?|won|baht|ringgit|rand|dirhams?|francs?|roubles?|rubles?)\b|JP\s*[¥￥]/i.test(text)
    || new RegExp("\\b" + codes + "\\s*[¥￥$]?\\s*\\d|\\d\\s*" + codes + "\\b|\\b(?:in|currency(?: is)?)\\s+" + codes + "\\b", "i").test(text)
    || [...text.matchAll(/\b(?:under|below|up to|budget(?: is| of| in| to)?|maximum)\s+([A-Za-z]{3})\s*(?=\d)/gi)].some(match => !["RMB", "CNY", "MAX"].includes(match[1].toUpperCase()))
    || [...text.matchAll(/\p{Sc}/gu)].some(match => !["¥", "￥"].includes(match[0]));
  if (foreign) return { normalized_question: text, currency_status: "foreign_or_mixed" };
  const amount = "(?:[1-9]\\d{0,2}(?:,\\d{3})+|(?:0|[1-9]\\d*))(?:\\.\\d+)?";
  const completeAmount = new RegExp("^" + amount + "$");
  const statedAmounts = [...text.matchAll(/(?:\b(?:RMB|CNY)\s*|[¥￥]\s*)([+-]?\d[\w.,+-]*)/gi)];
  if (statedAmounts.some(match => {
    const number = match[1].replace(/[.,]$/, ""); // Sentence punctuation, not decimal rounding.
    const numeric = Number(number.replace(/,/g, ""));
    return !completeAmount.test(number) || !Number.isFinite(numeric) || numeric <= 0 || numeric > Number.MAX_SAFE_INTEGER;
  })) return { normalized_question: text, currency_status: "invalid_rmb_amount" };
  const currency = new RegExp("(\\b(?:RMB|CNY)\\s*|[¥￥]\\s*)(" + amount + ")(?!\\w|[,.]\\d)", "gi");
  const normalized = text.replace(currency, (whole, _prefix, number) => {
    const digits = number.replace(/,/g, "");
    const numeric = Number(digits);
    return Number.isFinite(numeric) && numeric > 0 && numeric <= Number.MAX_SAFE_INTEGER ? "RMB " + digits : whole;
  });
  return { normalized_question: normalized, currency_status: "rmb_or_unspecified" };
}

function normalizeRmbBudget(value) {
  if (typeof value === "number") return Number.isFinite(value) && value > 0 && value <= Number.MAX_SAFE_INTEGER ? value : null;
  if (typeof value !== "string") return null;
  const normalized = normalizeRmbInput(value.trim());
  if (normalized.currency_status !== "rmb_or_unspecified") return null;
  const match = /^(?:RMB\s+)?((?:[1-9]\d{0,2}(?:,\d{3})+|(?:0|[1-9]\d*))(?:\.\d+)?)$/i.exec(normalized.normalized_question);
  if (!match) return null;
  return normalizeRmbBudget(Number(match[1].replace(/,/g, "")));
}

function currentPurchaseEvidence(value) {
  // Recognize an explicit, bounded purchase utterance, not arbitrary category
  // mentions, quotations, capability questions, repairs or negative intent.
  const text = normalizeRmbInput(value).normalized_question.trim().replace(/[.!?]+$/, "");
  if (/["“”\n]/.test(text) || /\b(?:not|never|don't|do not|if|pretend|translate|translation|quote|repair|broken)\b/i.test(text)) return null;
  if (/[.!?]/.test(text.replace(/(\d)\.(?=\d)/g, "$1_"))) return null;
  const lead = /^(?:please\s+)?(?:i\s+(?:need|want)\s+|i(?:'d| would)\s+like\s+|i(?:'m| am)\s+looking for\s+|(?:(?:can|could|would) you\s+(?:please\s+)?)?(?:recommend|suggest|find|show)\s+(?:me\s+)?)/i.exec(text);
  if (!lead) return null;
  const body = text.slice(lead[0].length);
  // Mixed unsupported requests are left to the original extractor/whitelist.
  if (/\b(?:cameras?|printers?|televisions?|TVs?|routers?|speakers?|projectors?|consoles?)\b/i.test(body)) return null;
  const names = { laptop: "Laptop", laptops: "Laptop", desktop: "Desktop", desktops: "Desktop",
    smartphone: "Smartphone", smartphones: "Smartphone", tablet: "Tablet", tablets: "Tablet",
    headphone: "Headphones", headphones: "Headphones", monitor: "Monitor", monitors: "Monitor",
    smartwatch: "Smartwatch", smartwatches: "Smartwatch", mouse: "Mouse", mice: "Mouse", keyboard: "Keyboard", keyboards: "Keyboard" };
  const noun = "(?:" + Object.keys(names).sort((a, b) => b.length - a.length).join("|") + ")";
  const modifier = "(?:(?:a|an|some|new|gaming|study|office|budget|portable)\\s+)*";
  const clauses = body.split(new RegExp("(?:,?\\s+and\\s+|,?\\s+plus\\s+|;\\s*)(?=" + modifier + noun + "\\b)", "i"));
  const result = [], seen = new Set();
  for (const clause of clauses) {
    const match = new RegExp("^" + modifier + "(" + noun + ")\\b(.*)$", "i").exec(clause.trim());
    if (!match) return null;
    const tail = match[2].trim();
    if (tail && !/^(?:under|below|up to|less than|around|about|for|with (?:a )?budget|budget)\b/i.test(tail)) return null;
    const category = names[match[1].toLowerCase()];
    if (seen.has(category)) return null; // Ambiguous duplicate requests need extraction/clarification.
    seen.add(category);
    const amounts = [...clause.matchAll(/\bRMB\s+(\d+(?:\.\d+)?)(?!\w|[,.]\d)/gi)];
    const range = /\d\s*(?:[-–—]|to|or)\s*(?:RMB\s*)?\d/i.test(clause);
    result.push({ category, budget: amounts.length === 1 && !range ? normalizeRmbBudget(amounts[0][1]) : null });
  }
  return result.length ? result : null;
}
