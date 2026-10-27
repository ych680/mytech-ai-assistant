    // UI state is separate from FastGPT memory and the four-field public contract.
    let demoFollowup = null;
    let demoExampleButtons = [];

    function demoInvalidateFollowup() {
      if (!demoFollowup) return;
      demoFollowup.buttons.forEach(button => { button.disabled = true; });
      if (demoFollowup.select) demoFollowup.select.disabled = true;
      demoFollowup.root.remove();
      demoFollowup = null;
    }

    function demoContextMatches(entry) {
      const requirement = sessionContext.requirementsByCategory[entry.category];
      const anchor = sessionContext.lastRecommendationsByCategory[entry.category];
      const product = productByName.get(entry.product);
      return requirement && anchor && product && product.category === entry.category
        && requirement.budget === entry.budget && requirement.usage === entry.usage
        && anchor.product === entry.product && anchor.price === entry.price
        && product.price_rmb === entry.price && entry.price <= entry.budget
        && Number.isFinite(entry.budget) && entry.budget > 0
        && usageIsCompatible(product, entry.usage);
    }

    function demoRefreshControls() {
      const unavailable = isGenerating || !datasetReady || !testConnectionAvailable();
      demoExampleButtons.forEach(button => { button.disabled = unavailable; });
      const state = demoFollowup;
      if (!state) return;
      // Even retained DOM references cannot act on an earlier turn or chat.
      const valid = state.version === requestVersion && state.chatId === fastGptChatId
        && state.entries.every(demoContextMatches);
      if (!valid) { demoInvalidateFollowup(); return; }
      const blocked = unavailable || inputElement.value.length > 0;
      if (state.select) state.select.disabled = blocked;
      state.buttons.forEach(button => { button.disabled = blocked || !state.category; });
    }

    function demoShowFollowup(response, guard, version) {
      demoInvalidateFollowup();
      if (!response.recommendations.length || response.clarification_needed
        || guard.completionControl || guard.cancelled || guard.ambiguousComparison
        || guard.ambiguousBetter || guard.usageClarificationNeeded || version !== requestVersion) return;
      const entries = response.recommendations.map(item => Object.freeze({
        category: item.category, product: item.recommended_product, price: item.price,
        budget: guard.budgetsByCategory[item.category], usage: guard.usagesByCategory[item.category]
      }));
      if (!entries.every(demoContextMatches)) return;
      const root = document.createElement("section");
      root.className = "demo-followup";
      root.setAttribute("aria-label", "Recommendation follow-up");
      const state = { root, entries: Object.freeze(entries), version, chatId: fastGptChatId,
        category: entries.length === 1 ? entries[0].category : "", select: null, buttons: [] };
      demoFollowup = state;
      const context = document.createElement("p");
      context.setAttribute("aria-live", "polite");
      const describe = () => {
        const entry = entries.find(item => item.category === state.category);
        context.textContent = entry
          ? `${entry.category} · ${entry.product} · Maximum ${formatPrice(entry.budget)}`
          : "Choose a recommended category to compare. Your saved maximum budget and usage stay the same.";
      };
      if (entries.length > 1) {
        const label = document.createElement("label");
        label.className = "demo-category";
        label.textContent = "Category to compare";
        const select = document.createElement("select");
        select.setAttribute("aria-label", "Category to compare");
        const placeholder = document.createElement("option");
        placeholder.value = "";
        placeholder.textContent = "Choose a category…";
        select.appendChild(placeholder);
        entries.forEach(entry => {
          const option = document.createElement("option");
          option.value = entry.category;
          option.textContent = entry.category;
          select.appendChild(option);
        });
        select.value = "";
        select.addEventListener("change", () => {
          if (demoFollowup !== state || select.disabled) return;
          state.category = entries.some(entry => entry.category === select.value) ? select.value : "";
          describe();
          demoRefreshControls();
        });
        state.select = select;
        label.appendChild(select);
        root.appendChild(label);
      }
      describe();
      root.appendChild(context);
      const actions = document.createElement("div");
      actions.className = "demo-actions";
      DEMO_PROMPTS.actions.forEach(action => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "recovery-button";
        button.textContent = action.label;
        button.addEventListener("click", () => {
          demoRefreshControls();
          if (demoFollowup !== state || button.disabled || !state.category) return;
          inputElement.value = `Can you recommend ${action.phrase} ${state.category.toLowerCase()}?`;
          autoResizeInput();
          sendMessage();
        });
        state.buttons.push(button);
        actions.appendChild(button);
      });
      root.appendChild(actions);
      messagesElement.appendChild(root);
      demoRefreshControls();
      scrollToNewest();
    }

    function demoResetExamples() {
      // Restart destroys the old details/buttons; retained references are inert.
      demoExampleButtons.forEach(button => { button.disabled = true; });
      demoExampleButtons = [];
      const details = document.createElement("details");
      details.className = "demo-examples";
      const summary = document.createElement("summary");
      summary.textContent = "More Examples";
      const note = document.createElement("p");
      note.textContent = "Clarification is a fresh-conversation example. Use Restart first if you have already supplied Laptop requirements. Examples keep the current conversation.";
      const actions = document.createElement("div");
      actions.className = "demo-actions";
      DEMO_PROMPTS.examples.forEach(example => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "recovery-button";
        button.textContent = example.label;
        button.title = example.prompt;
        button.addEventListener("click", () => {
          if (!demoExampleButtons.includes(button) || button.disabled || isGenerating
            || !datasetReady || !testConnectionAvailable() || inputElement.value.length > 0) return;
          inputElement.value = example.prompt;
          autoResizeInput();
          sendMessage();
        });
        demoExampleButtons.push(button);
        actions.appendChild(button);
      });
      details.append(summary, note, actions);
      messagesElement.appendChild(details);
      demoRefreshControls();
    }

    function demoHasMissingInformation(guard) {
      if (guard.completionControl || guard.cancelled || guard.comparison
        || guard.ambiguousComparison || guard.ambiguousBetter) return false;
      const targets = guard.targetCategories.length ? guard.targetCategories : guard.activeCategories;
      return targets.some(category => guard.budgetsByCategory[category] === undefined
        || !guard.usagesByCategory[category]);
    }

    function demoMissingFieldClarification(output, guard) {
      // This bounded exception accepts complete clarification clauses, never
      // keyword fragments. Original response/display validators still run next.
      if (!isPlainObject(output) || output.clarification_needed !== true
        || !Array.isArray(output.recommendations) || output.recommendations.length
        || typeof output.answer !== "string" || typeof output.next_step !== "string"
        || guard.demoUsageOwnershipAmbiguous || guard.completionControl || guard.cancelled
        || guard.comparison || guard.ambiguousComparison || guard.ambiguousBetter) return false;
      const targets = guard.targetCategories.length ? guard.targetCategories : guard.activeCategories;
      // Category-free questions and pronouns are unambiguous only for one target.
      // Multi-target clarification prose remains outside this narrow exception.
      if (targets.length !== 1 || !IDENTITY.supportedCategories.includes(targets[0])) return false;
      const category = targets[0], noun = category.toLowerCase();
      const missing = new Set();
      const budget = guard.budgetsByCategory[category], usage = guard.usagesByCategory[category];
      if (budget === undefined) missing.add("budget");
      else if (!Number.isFinite(budget) || budget <= 0) return false;
      if (!usage) missing.add("usage");
      else if (!parseCatalogueUsage(usage, testUsageCatalogue, TEST_USAGE_POLICY, category).valid) return false;
      if (!missing.size) return false;

      const device = "(?:the |your )?" + noun;
      const budgetTerm = new RegExp("^(?:(?:your|the) )?(?:maximum )?budget(?: for " + device + ")?(?: in (?:rmb|cny|yuan))?$");
      const usageTerm = new RegExp("^(?:(?:your|the) )?(?:(?:main|intended) )?(?:usage|use|purpose)(?: for " + device + ")?$");
      const parseTerms = value => {
        const terms = value.split(/,? and /);
        if (!terms.length || terms.length > 2) return null;
        const fields = terms.map(term => budgetTerm.test(term) ? "budget" : usageTerm.test(term) ? "usage" : null);
        return fields.every(Boolean) && new Set(fields).size === fields.length ? fields : null;
      };
      const usageQuestion = new RegExp("^what (?:will|do) you (?:mainly )?use (?:" + device + "|it) for$");
      const budgetQuestion = new RegExp("^how much (?:can|would) you (?:spend|like to spend)(?: on " + device + ")?$");
      const parseQuestion = clause => {
        const simple = /^(?:what (?:is|are)|(?:could|can) you (?:tell me|provide|specify|share)) (.+)$/.exec(clause);
        if (simple) return parseTerms(simple[1]);
        if (usageQuestion.test(clause)) return ["usage"];
        if (budgetQuestion.test(clause)) return ["budget"];
        return null;
      };
      const neutral = new Set(["sure", "okay", "thanks", "got it"]);
      const offer = new RegExp("^i can help you choose (?:a |an |the |your )?" + noun + "$");
      const asked = new Set();
      let count = 0;
      for (const field of [output.answer, output.next_step]) {
        const text = field.trim().toLowerCase().replace(/\s+/g, " ");
        if (!text) continue;
        const sentences = text.match(/[^.!?]+(?:[.!?]|$)/g);
        if (!sentences || sentences.join("") !== text) return false;
        for (const sentence of sentences) {
          if (++count > 8) return false;
          const ending = /[.!?]$/.exec(sentence)?.[0] || "";
          const clause = sentence.replace(/[.!?]$/, "").trim();
          if ((neutral.has(clause) || offer.test(clause)) && ending !== "?") continue;
          const directive = /^(?:please )?(?:tell me|provide|specify|share|state) (.+)$/.exec(clause);
          let fields;
          if (directive) fields = parseTerms(directive[1]);
          else {
            if (ending !== "?") return false;
            // A bounded pair of actual questions, e.g. budget + intended use.
            const questions = clause.split(/,? and (?=what |how )/);
            if (questions.length > 2) return false;
            const parsed = questions.map(parseQuestion);
            fields = parsed.every(Boolean) ? parsed.flat() : null;
          }
          if (!fields || fields.some(name => !missing.has(name))) return false;
          fields.forEach(name => asked.add(name));
        }
      }
      return [...missing].every(name => asked.has(name));
    }
