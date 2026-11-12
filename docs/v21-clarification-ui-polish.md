# Final Local Clarification UI polish — 2026-11-12

Branch: `repair/p05-live-retest-follow-up`. HEAD remains
`3f4afc2ba0be85be4690f115e92d049fd8e7847b`. The starting tree had six modified
files and seven untracked repair/evidence files. All prior work was retained;
no main-branch change, commit, push, merge, deployment, school application change,
or live/paid FastGPT request was made.

The user now reports that P05 and P09 passed live end-to-end retesting on macOS.
That is a new user-reported observation, not a live test performed in this task.
The three historical failed clarification retests, earlier assessment results,
exact JSON fixtures, and all prior reports remain unchanged.

## Before and after

Previously, the fallback displayed four paragraphs plus a recovery action:

> Local clarification
>
> The model response was not accepted.
>
> For Laptop, please tell me your maximum budget in RMB and what you will mainly use it for.
>
> Reply with the missing information to continue.
>
> Edit and try again

It now displays the existing small `assistant-label` style and one question:

> **Local clarification**
>
> What's your maximum budget (RMB), and what will you mainly use the laptop for?

Budget-only:

> What's your maximum budget (RMB) for the laptop?

Usage-only:

> What will you mainly use the laptop for?

The product noun comes from the verified category, lowercased. All nine canonical
nouns work without adding plural suffixes: laptop, desktop, smartphone, tablet,
headphones, monitor, smartwatch, mouse, keyboard. Thus Headphones uses
`the headphones` in all three question forms, without singular pronouns or an
incorrect article. Already validated information is not requested again.

## Exact incremental file/function inventory

1. `tools/templates/v21_quick_prompt_demo.js`:
   `demoSafeClarification()` changes only fixed output wording after all existing
   eligibility/security checks; `next_step` becomes an empty string while all four
   public fields remain present. New `demoRenderClarification()` creates the
   existing assistant bubble with the existing subtle label class and one
   paragraph. New `demoHideClarificationRecovery()` hides and invalidates only
   the fallback's recovery action.
2. `tools/build_v21_quick_prompt_demo.py`, `render_frontend()`:
   uses the dedicated renderer and inserts the fallback-only recovery visibility
   hook with the existing fail-on-drift replacement mechanism.
3. `generated/v21_quick_prompt_demo/local/index.html`: deterministic output.
4. `generated/v21_quick_prompt_demo/aiep/site/index.html`: deterministic output.
5. `generated/v21_quick_prompt_demo/local/manifest.json`: regenerated digest.
6. `generated/v21_quick_prompt_demo/manifest.json`: regenerated source/output digests.
7. `tests/structural-clarification.test.mjs`: updates only the fixed-copy helper
   expectations and asserts removal of technical/repetitive UI text. All context,
   security, history, and negative-response assertions remain intact.
8. `tests/clarification-ui-polish.test.mjs`: 72 new UI/recovery regressions.
9. This new report.

Generated HTML was written only with
`.venv/bin/python -B tools/build_v21_quick_prompt_demo.py`. No CSS, school
workflow/application, prompt, catalogue, knowledge, recommendation/comparison
policy, Node validation policy, or public contract was changed.

## Recovery lifecycle and safety

For an eligible local clarification, the existing recovery element is retained
in the DOM but receives native `hidden`, is disabled, and is invalidated so
`activeRecovery` is null. It is invisible, unfocusable, and inert even under a
synthetic click. This preserves the shared recovery component and its existing
lifecycle. The visible fallback bubble contains only the label and question;
there is no visible or actionable `Edit and try again` control on that response.

Genuine errors do not run that hook. Network/HTTP failures, timeouts, empty or
malformed output, invalid contracts, and non-clarification validation failures
still expose a working recovery action. Tests verify exact draft restoration,
draft protection, no extra request or state change on restore, Restart/stale-action
invalidation, late-failure suppression, and a working error recovery immediately
after a hidden fallback recovery. No global recovery behavior was removed,
disabled, or restyled.

`demoResponseOutcome.kind`, `modelAccepted: false`, verified category/missing
fields, safe output, and `clarification_fallback` timing retain the internal
distinction from an accepted model response. Removing technical UI text does
not change that distinction. Rejected original prose is still excluded from
visible content, validated assistant history, and recommendation anchors.

Byte comparisons confirm that the clarification grammar, eligibility checks,
guard/state consistency, and raw security gates are unchanged. Both frontends'
existing recovery functions, request validation, usage/completion validators,
context parsing, recommendation anchors, and Restart functions are unchanged.
All stylesheet blocks are byte-identical. Existing negative security cases were
not weakened, retargeted, or skipped.

## Offline verification

macOS, Node `v24.21.0`, Python `3.12.15`. All model replies were in-memory
fixtures; loopback fixture servers used local execution permission.

| Check | Pre-polish reported baseline | Post-polish verified result |
| --- | --- | --- |
| Complete Node suite | 1016 passed, 2 skipped | **1090 total: 1088 passed, 0 failed, 2 existing skips** |
| Complete Python suite | 353 passed | **353 passed, no failures/errors/skips** |
| Usage replay against regenerated demo | 34 passed | **34 passed** |
| Completion replay against regenerated demo | 64 passed | **64 passed** |
| Deterministic consistency checks | 10/10 | **10/10** |
| Frozen preservation fingerprints | 67/67 | **67/67 unchanged** |
| Repeat generation | 8 outputs | **All 8 output bytes and mtimes unchanged** |
| New UI/recovery suite | Not present | **72 passed**, included in Node total |
| Existing structural suite | 137 passed | **137 passed**, including same-chat P05 follow-up over HTTP |
| Historical workflow/catalogue/knowledge/evaluation/document files | Preserved | **47/47 byte-identical to `3f4afc2`** |
| Whitespace/exact-diff checks | Passed | **Passed** |

The 72 added tests account exactly for the increased Node pass count: 54 cover
all nine categories and three missing-field combinations across Local and AIEP;
18 cover failure recovery and state lifecycle. They check exact visible bubble
content, the reused label class, hidden/inactive fallback recovery, no rejected
prose, no re-asking supplied fields, unchanged requirements/chat ID, empty
validated fallback history, and no product anchors.

The full suite and replays retain P01/P02 recommendations, P06/P07 comparisons,
P08 honest no-match, P09 unsupported Printer, P10 help/unrelated requests, P11
Restart/isolation, and P12 error recovery. The two existing Node skips are private
school candidate suites requiring explicit selection; neither was selected.

Commands:

```sh
env PATH="$PWD/.venv/bin:$PATH" node --test tests/*.test.mjs
.venv/bin/python -B -m unittest discover -s tests -p 'test_*.py' -v
env MYTECH_REPAIR_PACKAGE=v21_quick_prompt_demo node --test tests/usage-repair.test.mjs
env MYTECH_COMPLETION_PACKAGE=v21_quick_prompt_demo node --test tests/completion-repair.test.mjs
git diff --check
```

The ten checks, each run using `.venv/bin/python -B`, were:
`tools/validate_products.py --strict-v1`,
`tools/build_knowledge.py --check knowledge/MyTech_Product_Knowledge_v1.md`,
`tools/check_catalogue_consistency.py`, `tools/build_aiep_test.py --check`,
`tools/build_prompt_ab_test.py --check`, `tools/build_glm47_prompt_ab.py --check`,
`tools/check_workflow_registry.py`, `tools/build_v21_usage_repair.py --check`,
`tools/build_v21_completion_repair.py --check`, and
`tools/build_v21_quick_prompt_demo.py --check`.

Final HTML SHA-256: Local
`f7fd3ed2481f6e36f711d08aafcc5019041b9ae433a9e55806cd63af963f8b44`;
AIEP `c69238527e78070e612204e96416a426b8d7532414150a8e07069962570ee7ff`.

## Remaining limitations and final macOS live P05 retest

An offline native-browser preview was attempted, but Computer Use permission was
not available. DOM-level visible-content/hidden-control checks passed; no native
screenshot or browser layout verification is claimed. The temporary offline
preview server was stopped. Live model behavior after this polish was not tested.

For one final manual retest, restart the local demo using the established,
explicitly selected TEST environment file and `start-mytech-demo.mjs`, reload
`http://127.0.0.1:8788/`, then press Restart. A running server holds HTML in memory,
so page reload alone does not replace an old server's assets.

1. Submit `I need a laptop.`. If a local fallback is used, expect the small
   `Local clarification` label and the concise two-field question above, with no
   technical rejection text or visible recovery button. An accepted model
   clarification continues to use its normal existing presentation.
2. In the same chat, reply
   `My maximum budget is RMB 6000, mainly for study and office work.`.
   Expect a validated catalogue-grounded Laptop recommendation within RMB 6000,
   preserved category/chat continuity, and no invalid anchor or ownership error.
3. Record the result as a new live observation, preserving the historical
   failures and the user's reported subsequent P05/P09 passes.

No school upload/deployment or live request was performed. All changes remain
uncommitted; work stops after local implementation and offline verification.
