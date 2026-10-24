    // Repair candidate only: retain complete usage wording, including unknown
    // qualifiers. The shared policy decides whether that wording is supported.
    let testUsageOwnershipAmbiguous = false;

    function testUsageClause(text, start, end, category, budgetMatches) {
      const withoutBudgets = (left, right) => {
        let value = "", cursor = left;
        for (const budget of budgetMatches.filter(item => item.index >= left && item.end <= right)) {
          value += text.slice(cursor, budget.index) + " ";
          cursor = budget.end;
        }
        return value + text.slice(cursor, right);
      };
      const clean = value => value.trim()
        .replace(/^(?:please\s+)?(?:(?:(?:can|could|would)\s+you\s+)?(?:recommend|suggest|show|give)(?:\s+me)?|(?:i\s+)?(?:need|want|would like|am looking for))(?:\s+|$)/i, "")
        .replace(/^(?:a|an|the)(?:\s+|$)/i, "")
        .replace(/^[\s,:;]+|[\s,.;!?]+$/g, "")
        .replace(/^(?:(?:main\s+)?usage\s*[:=]?\s*|for\s+)/i, "").trim();
      const noun = text.slice(category.index, category.end);
      const embedded = collectMatches(noun, USAGE_MATCHERS).map(match => noun.slice(match.index, match.end)).join(" ");
      const before = [clean(withoutBudgets(start, category.index)), embedded].filter(Boolean).join(" ");
      const after = clean(withoutBudgets(category.end, end));
      return [before, after].filter(Boolean).join(" and ");
    }

    function assignDetailsToCategories(text, categoryMatches, budgetMatches, usageMatches) {
      testUsageOwnershipAmbiguous = false;
      const starts = [0];
      const connectors = [];
      for (let index = 1; index < categoryMatches.length; index += 1) {
        const previous = categoryMatches[index - 1], current = categoryMatches[index];
        const between = text.slice(previous.end, current.index);
        const boundaries = [...between.matchAll(/[,;]|\b(?:and|also|plus|or)\b/gi)];
        const boundary = boundaries.pop();
        if (!boundary) {
          starts.push(current.index);
          connectors.push("");
          testUsageOwnershipAmbiguous = true;
        } else {
          starts.push(previous.end + boundary.index + boundary[0].length);
          connectors.push(boundary[0].toLowerCase());
        }
      }
      const usages = categoryMatches.map((category, index) => {
        const end = index + 1 < starts.length
          ? starts[index + 1] - connectors[index].length : text.length;
        return testUsageClause(text, starts[index], end, category, budgetMatches);
      });
      const last = categoryMatches.length - 1;
      // The bounded coordinated form 'Laptop under X and Mouse under Y for Z'
      // shares Z only when no device has an explicit independent usage.
      const shared = last > 0 && usages[last] && usages.slice(0, last).every(value => !value)
        && connectors.every(value => ["and", "also", "plus", ","].includes(value))
        && /\bfor\b/i.test(text.slice(categoryMatches[last].end));
      if (connectors.includes("or")) testUsageOwnershipAmbiguous = true;
      categoryMatches.forEach((category, index) => {
        const requirement = requirementFor(category.value);
        const end = categoryMatches[index + 1]?.index ?? text.length;
        const budget = budgetMatches.find(item => item.index >= category.end && item.index < end);
        if (budget) requirement.budget = budget.amount;
        const usage = shared ? usages[last] : usages[index];
        if (usage) requirement.usage = usage;
      });
      if (categoryMatches.length === 1 && budgetMatches.length === 1) {
        requirementFor(categoryMatches[0].value).budget = budgetMatches[0].amount;
      }
    }

    function testUsageOwnershipIssue(text, mentioned, intent, reset, cancelled) {
      if (reset || cancelled || intent) {
        testUsageOwnershipAmbiguous = false;
        return false;
      }
      if (!mentioned.length) {
        testUsageOwnershipAmbiguous = false;
        // Recognize bounded instruction syntax, not new usage vocabulary. Keep
        // the whole replacement, including unsupported qualifiers and negation.
        const correction = /^(?:please\s+)?(?:use\s+(?:it|this|that|them|these|those)\s+for|i\s+(?:will|want\s+to|need\s+to|would\s+like\s+to)\s+use\s+(?:it|this|that|them|these|those)\s+for|(?:change|set|update)\s+(?:(?:the|my|its|their)\s+)?(?:main\s+)?usage\s+to)\b(?:\s+([\s\S]*))?$/i.exec(text.trim().replace(/[.!?]+$/, ""));
        const usages = collectMatches(text, USAGE_MATCHERS);
        const pending = sessionContext.activeCategories.filter(category => !requirementFor(category).usage);
        if (correction || usages.length || (pending.length && !collectBudgetMatches(text).length)) {
          const targets = !correction && pending.length === 1 ? pending : sessionContext.targetCategories;
          if (targets.length !== 1) testUsageOwnershipAmbiguous = true;
          else {
            const budgets = collectBudgetMatches(text);
            const raw = correction
              ? (correction[1] || "").trim().replace(/\s+instead$/i, "").trim()
              : testUsageClause(text, 0, text.length, { index: 0, end: 0 }, budgets);
            requirementFor(targets[0]).usage = raw;
          }
        }
      }
      const targets = sessionContext.targetCategories.length ? sessionContext.targetCategories : sessionContext.activeCategories;
      return testUsageOwnershipAmbiguous || targets.some(category =>
        !parseCatalogueUsage(requirementFor(category).usage, testUsageCatalogue, TEST_USAGE_POLICY, category).valid);
    }
