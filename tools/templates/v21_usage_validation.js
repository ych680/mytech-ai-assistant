// TEST-only deterministic policy. Product evidence always comes from the
// generated Master Dataset; aliases describe requests, never product facts.
function checkCatalogueUsage(product, requestedUsage, catalogue, compatibility) {
  if (typeof requestedUsage !== "string" || !requestedUsage.trim() || requestedUsage.length > 300) {
    return { valid: false, error: "A non-empty, supported main usage is required." };
  }
  const normalize = value => value.normalize("NFKC").toLowerCase()
    .replace(/[\u2010-\u2015_-]/g, " ").replace(/[.,;!?()[\]"]/g, " ")
    .replace(/[&+/]/g, " and ").replace(/\s+/g, " ").trim();
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
  const tags = product.main_usage.map(normalize);
  const supported = requirements.every(requirement => requirement.tag
    ? tags.includes(requirement.tag)
    : tags.some(tag => compatibility[requirement.group].some(term =>
      (" " + tag + " ").includes(" " + normalize(term) + " "))));
  return { valid: supported, error: supported ? "" : "The product's Master Dataset usage tags do not support the requested usage." };
}
