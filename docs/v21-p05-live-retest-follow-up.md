# P05 live retest follow-up repair — 2026-11-12

Starting working tree: clean, on `repair/p05-p09-local-validation` at
`3f4afc2ba0be85be4690f115e92d049fd8e7847b`. Created isolated branch
`repair/p05-live-retest-follow-up` from that commit. HEAD remains unchanged;
changes are uncommitted. No main-branch modification, deployment, merge,
commit, push, workflow import, or live/paid request was performed.

## Historical live result retained: FAIL

The user reported a real school FastGPT retest on **2026-11-12**:

User: `I need a laptop.`

```json
{
  "answer": "What is your budget and main usage for the laptop?",
  "recommendations": [],
  "next_step": "Please provide your laptop budget and main usage.",
  "clarification_needed": true
}
```

FastGPT correctly identified missing fields `budget` and `main_usage`, with
Laptop as the only active category. The local frontend displayed:

> Please clarify which intended usage belongs to each product; no recommendation was accepted.

This remains a **failed live retest**, as reported by the user. The offline
repair below does not supersede it or establish a successful live retest.
The original presentation assessment remains **12 scenarios: 10 PASS, 2 FAIL
(P05 and P09)**. All earlier assessment/evaluation documents remain unchanged.

## Reproduction, diagnosis, and exact runtime change

Before the repair, the exact four-field response failed both generated Local
and AIEP frontends: **0 passes / 2 failures**. Both produced the exact ownership
error above, accepted zero model-history entries, and displayed zero cards.
The same response with only `laptop` removed from `next_step` was accepted by
`demoMissingFieldClarification()`, isolating the category-prefixed budget term.

The bounded `budgetTerm` grammar supported `your budget`, `maximum budget`, and
`budget for the laptop`, but rejected `your laptop budget`. The surrounding
missing-information gate consequently rejected the response and selected the
existing ownership-error message.

The sole runtime edit is in `tools/templates/v21_quick_prompt_demo.js`:

```diff
 const device = "(?:the |your )?" + noun;
-const budgetTerm = new RegExp("^(?:(?:your|the) )?(?:maximum )?budget(?: for " + device + ")?(?: in (?:rmb|cny|yuan))?$");
+// A category may precede budget only when it names the sole target.
+const budgetTerm = new RegExp("^(?:(?:your|the) )?(?:(?:maximum )?budget(?: for " + device + ")?|" + noun + " budget)(?: in (?:rmb|cny|yuan))?$");
```

The added alternative is the current sole supported target noun followed by
`budget`. Existing optional determiners and currency suffixes still apply.
No general category vocabulary or free-prose allowance was added. Combined
prefix/suffix forms such as `your laptop budget for the laptop` remain rejected.

The single-target prerequisite, missing-field coverage, checks against asking
for already supplied fields, usage validation, duplicate-field rejection within
a clause, purpose-clause bounds, safety checks, grounding checks, and public
four-field response contract are unchanged. Both response fields may legitimately
repeat the same question, as the exact live response does. No workflow, prompt,
knowledge base, catalogue, recommendation policy, transport, or UI design changed.

## Changed-file inventory

1. `tools/templates/v21_quick_prompt_demo.js`: one regex change plus comment.
2. `generated/v21_quick_prompt_demo/local/index.html`: generated runtime change.
3. `generated/v21_quick_prompt_demo/aiep/site/index.html`: same generated change.
4. `generated/v21_quick_prompt_demo/local/manifest.json`: generated HTML digest.
5. `generated/v21_quick_prompt_demo/manifest.json`: generated source/output digests.
6. `tests/p05-live-retest.test.mjs`: 72 new offline tests, 36 for each frontend.
7. This new report; existing assessment and repair reports are preserved.

Generated files were written only by
`.venv/bin/python -B tools/build_v21_quick_prompt_demo.py`. The builder itself
and the fingerprinted historical quick-prompt test suite were not changed.

## Offline verification

Host: macOS, Node `v24.21.0`, Python `3.12.15`. All upstream model responses
were injected fixtures; no real FastGPT or paid requests were made.

| Suite/check | Result |
| --- | --- |
| New exact-response and negative-control suite | 72 passed, 0 failed |
| Full Node suite | 706 total: 704 passed, 0 failed, 2 existing skips |
| Full Python suite | 353 passed, 0 failures/errors/skips |
| Usage regressions replayed against repaired demo | 34 passed, 0 failed |
| Completion regressions replayed against repaired demo | 64 passed, 0 failed |
| Read-only consistency checks | 10 of 10 passed |
| Frozen preservation SHA-256 fingerprints | 67 of 67 unchanged |
| Baseline workflow/catalogue/knowledge/evaluation/document files | 47 of 47 byte-identical to `3f4afc2` |
| Repeat deterministic generation | All 8 output bytes and mtimes unchanged |
| Whitespace checks | Passed |

The exact live response now displays both original strings, accepts two
model-history entries, displays zero cards, and saves no recommendation anchor
in both generated frontends. New tests also exercise all four supported target
categories, each wrong supported category and Printer in each response field,
fabricated product prose/cards, unrelated clauses, unsafe promises, wrong-category
purpose clauses, duplicate budget/usage terms, incomplete missing-field coverage,
already supplied fields, unsupported/negated usage, ambiguous or multiple active
categories, and malformed response contracts. Negative controls accept no history,
display no cards, and create no recommendation anchors.

The Node skips are the existing explicit-selection private school candidate
suites; neither private candidate was selected. Initial sandbox runs failed
because loopback `listen` was denied (`EPERM`); rerunning the full Node suite
and both replays with loopback permission passed. No test was disabled or
relaxed. The prior report's Windows symlink errors did not recur on this host.

Commands used:

```sh
node --test tests/p05-live-retest.test.mjs
env PATH="$PWD/.venv/bin:$PATH" node --test tests/*.test.mjs
.venv/bin/python -B -m unittest discover -s tests -p 'test_*.py' -v
env MYTECH_REPAIR_PACKAGE=v21_quick_prompt_demo node --test tests/usage-repair.test.mjs
env MYTECH_COMPLETION_PACKAGE=v21_quick_prompt_demo node --test tests/completion-repair.test.mjs
git diff --check
```

The ten consistency commands, each run with `.venv/bin/python -B`, were:
`tools/validate_products.py --strict-v1`,
`tools/build_knowledge.py --check knowledge/MyTech_Product_Knowledge_v1.md`,
`tools/check_catalogue_consistency.py`, `tools/build_aiep_test.py --check`,
`tools/build_prompt_ab_test.py --check`, `tools/build_glm47_prompt_ab.py --check`,
`tools/check_workflow_registry.py`, `tools/build_v21_usage_repair.py --check`,
`tools/build_v21_completion_repair.py --check`, and
`tools/build_v21_quick_prompt_demo.py --check`.

## Remaining risks and stopping point

Live FastGPT extraction, retrieval grounding, memory, browser layout, and other
model wording remain unverified by this offline repair. The grammar intentionally
rejects unrecognized wording. The private school candidate suites remain unrun.
Only the Quick Prompt Demo package was regenerated; historical packages retain
their original behavior. Local verification is complete; no live retest,
commit, push, merge, or deployment has been performed.
