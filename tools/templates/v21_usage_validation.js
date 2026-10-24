// TEST-only deterministic policy. Product evidence always comes from the
// generated Master Dataset; aliases describe requests, never product facts.
function normalizeCatalogueUsage(value) {
  return value.normalize("NFKC").toLowerCase()
    .replace(/[\u2010-\u2015_-]/g, " ").replace(/[.,;!?()[\]"]/g, " ")
    .replace(/[&+/]/g, " and ").replace(/\s+/g, " ").trim();
}

function parseCatalogueUsage(requestedUsage, catalogue, compatibility, category) {
  if (typeof requestedUsage !== "string" || !requestedUsage.trim() || requestedUsage.length > 300) {
    return { valid: false, error: "A non-empty, supported main usage is required." };
  }
  const normalize = normalizeCatalogueUsage;
  const vocabulary = new Map();
  for (const entry of Object.values(catalogue)) {
    for (const tag of entry.main_usage) {
      vocabulary.set(normalize(tag), { tag: normalize(tag) });
    }
  }
  for (const group of Object.keys(compatibility)) {
    vocabulary.set(normalize(group), { group });
  }
  const aliases = {
    Gaming: ["game", "games", "play game", "play games", "playing games", "play a game", "playing a game", "video games", "videogames", "video gaming", "play video games", "playing video games", "playing computer games", "casual gaming"],
    Study: ["studying", "studies", "school", "schoolwork", "school work", "coursework", "homework", "student", "classes", "classwork", "taking notes", "take notes"],
    Office: ["work", "working", "office work", "office tasks", "business", "documents", "document editing", "spreadsheets"],
    Creative: ["design", "designing", "graphic design", "illustration", "video editing", "photo editing", "photo and video editing"],
    Photography: ["photo", "photos", "take photos", "taking photos", "photo taking", "take pictures", "taking pictures", "camera quality"],
    Media: ["movies", "videos", "watch movies", "watching movies", "watch videos", "watching videos", "video streaming", "streaming"],
    Music: ["listen to music", "listening to music", "listening", "audio", "songs", "podcasts"],
    Calls: ["call", "calling", "video calls", "voice calls"],
    Travel: ["travelling", "traveling", "commuting", "portable", "portability", "on the go"],
    Fitness: ["exercise", "exercising", "workout", "workouts", "working out", "daily health", "health monitoring"],
    Development: ["programming", "coding", "software development", "software programming", "software engineering"],
    Productivity: ["productive work", "multi tasking"],
    Typing: ["type documents"],
    "Noise cancellation": ["noise cancelling", "noise canceling", "active noise cancellation", "anc"],
    Daily: ["everyday", "everyday use", "basic use", "normal use", "casual use"]
  };
  for (const [group, phrases] of Object.entries(aliases)) {
    for (const phrase of phrases) {
      // Explicit dataset phrases take priority over aliases with broader meaning.
      if (!vocabulary.has(phrase)) vocabulary.set(phrase, { group });
    }
  }
  // Complete, category-scoped phrases: a qualitative Gaming preference, not
  // evidence of benchmarks. Never make 'good' or 'performance' filler words.
  if (category === "Laptop") {
    for (const phrase of ["gaming good performance", "gaming and good performance", "gaming with good performance", "good performance for gaming"]) {
      vocabulary.set(phrase, { tag: "gaming" });
    }
  }
  const phrases = [...vocabulary.keys()].sort((a, b) => b.split(" ").length - a.split(" ").length || b.length - a.length);
  const fillers = new Set(["i", "am", "would", "like", "want", "need", "looking", "it", "this", "device", "my", "mainly", "mostly", "primarily", "for", "to", "the", "a", "an", "and", "also", "use", "using", "with", "please", "only"]);
  const words = normalize(requestedUsage).split(" ");
  const requirements = [];
  for (let index = 0; index < words.length;) {
    const phrase = phrases.find(candidate => {
      const parts = candidate.split(" ");
      return parts.every((part, offset) => words[index + offset] === part);
    });
    if (phrase) {
      requirements.push(vocabulary.get(phrase));
      index += phrase.split(" ").length;
    } else if (fillers.has(words[index])) {
      index += 1;
    } else {
      // Includes unknown qualifiers, negation and ambiguous 'or' expressions.
      // A recognized substring must never hide unsupported request wording.
      return { valid: false, error: "Unrecognized or ambiguous main usage; please restate the intended use." };
    }
  }
  if (!requirements.length) return { valid: false, error: "A supported main usage is required." };
  return { valid: true, requirements };
}

function checkCatalogueUsage(product, requestedUsage, catalogue, compatibility) {
  const parsed = parseCatalogueUsage(requestedUsage, catalogue, compatibility, product.category);
  if (!parsed.valid) return parsed;
  const normalize = normalizeCatalogueUsage;
  const tags = product.main_usage.map(normalize);
  const supported = parsed.requirements.every(requirement => requirement.tag
    ? tags.includes(requirement.tag)
    : tags.some(tag => compatibility[requirement.group].some(term =>
      (" " + tag + " ").includes(" " + normalize(term) + " "))));
  return { valid: supported, error: supported ? "" : "The product's Master Dataset usage tags do not support the requested usage." };
}

function checkPartialCatalogueRecommendations(output, requests, catalogue, compatibility) {
  if (!Array.isArray(output?.recommendations)) return { valid: false, error: "Recommendations must be an array." };
  if (output.recommendations.some(item => !item || typeof item.category !== "string")) return { valid: false, error: "Invalid recommendation category." };
  if (!output.recommendations.length) return { valid: true };
  const returned = new Set(output.recommendations.map(item => item.category));
  for (const request of requests.filter(item => !returned.has(item.category))) {
    const parsed = parseCatalogueUsage(request.main_usage, catalogue, compatibility, request.category);
    if (!parsed.valid) return parsed;
    if (!Number.isFinite(request.budget) || request.budget <= 0) {
      return { valid: false, error: "A positive independent hard budget is required." };
    }
    const eligible = Object.values(catalogue).some(product => product.category === request.category
      && (product.price_rmb ?? product.price) <= request.budget
      && checkCatalogueUsage(product, request.main_usage, catalogue, compatibility).valid);
    if (eligible) return { valid: false, error: "A partial response cannot claim no catalogue match for an eligible request." };
    // The four-field contract has no structured no-match field. Require an
    // explicit same-clause explanation; do not infer honesty from an omission.
    const explained = output.answer.split(/[.!?;\n]/).some(clause => {
      const text = clause.toLowerCase();
      return text.includes(request.category.toLowerCase())
        && /\b(?:no\b[^.!?;\n]*(?:match(?:es|ing)?|qualif\w*|available)|could(?:n['’]t| not) find|cannot find|can['’]t find)\b/.test(text);
    });
    if (!explained) return { valid: false, error: "A partial response must explicitly explain each unmatched category." };
  }
  return { valid: true };
}

function checkUsageRepairResponseContract(data, catalogue) {
  const exact = (value, keys) => value && typeof value === "object" && !Array.isArray(value)
    && Object.keys(value).length === keys.length && keys.every(key => Object.prototype.hasOwnProperty.call(value, key));
  if (!exact(data, ["answer", "recommendations", "next_step", "clarification_needed"])
    || typeof data.answer !== "string" || !data.answer.trim() || typeof data.next_step !== "string"
    || typeof data.clarification_needed !== "boolean" || !Array.isArray(data.recommendations)
    || (data.clarification_needed && data.recommendations.length)) return false;
  return data.recommendations.every(item => {
    if (!exact(item, ["category", "recommended_product", "price", "reason", "source"])
      || !["category", "recommended_product", "reason", "source"].every(key => typeof item[key] === "string" && item[key].trim())
      || !Number.isFinite(item.price) || item.price <= 0) return false;
    const product = Object.prototype.hasOwnProperty.call(catalogue, item.recommended_product) ? catalogue[item.recommended_product] : null;
    return Boolean(product) && item.category === product.category && item.price === (product.price_rmb ?? product.price)
      && item.source === product.source;
  });
}
