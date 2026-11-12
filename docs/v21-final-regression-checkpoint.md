# Final regression audit and live acceptance checkpoint — 2026-11-12

Repository: `ych680/mytech-ai-assistant`. Branch:
`repair/p05-live-retest-follow-up`. Approved parent/base:
`3f4afc2ba0be85be4690f115e92d049fd8e7847b`. This record adds final manual
acceptance and pre-commit audit evidence; it does not revise historical results.
The user explicitly authorized a normal commit and branch push after all checks
pass. No PR, merge, deployment, or school application update is authorized.

## Final manual acceptance, confirmed by the user

Both final tests were performed by the user on macOS on November 12, 2026.
No live or paid FastGPT request was made during this automated audit.

**P05: LIVE PASS.** Turn 1, `I need a laptop.`, displayed the subtle
`Local clarification` label and:

> What's your maximum budget (RMB), and what will you mainly use the laptop for?

There was no visible recovery button, rejected model prose, or recommendation
card. This was a deterministic local fallback, not acceptance of unvalidated
model text. In the same conversation, the user replied:

> My maximum budget is RMB 6000, mainly for study and office work.

Laptop, budget RMB 6,000, and Study/Office usage were preserved. A validated
model recommendation displayed **Lenovo Xiaoxin 14 (2025, Ryzen 7 H255,
16GB/512GB)** at catalogue reference price **RMB 5,799**, with the product card
and follow-up controls.

**P09: LIVE PASS**, approximately **20:23 Asia/Hong_Kong**. The request
`I need a printer under RMB 1000 for home use.` was identified as unsupported.
The reported response had zero recommendations and `clarification_needed: false`.
The frontend displayed the supported-category explanation, with no incorrect
usage-ownership clarification or product card. Exact response prose and raw
runtime logs were not supplied; none are fabricated here.

**Reporting distinction:** initial evaluation **10/12 PASS, 2 FAIL (P05/P09)**;
post-repair P05 **PASS**; post-repair P09 **PASS**; cumulative scenario coverage
**12/12 with PASS evidence**. This is **not** evidence that the final candidate
completed all twelve scenarios in one fresh live evaluation.

The initial P05/P09 diagnosis remains in
[the original repair report](v21-p05-p09-local-repair.md). Subsequent failed
wordings, bounded grammar repairs, exact live JSON, structural context-derived
fallback, and final UI polish remain in the four reports and fixture listed
below. This new acceptance record supplements those historical failures.

## Preflight and final offline audit

The repository root and origin URL matched the approved repository. The active
branch and HEAD matched the approved base, the index was empty, and the fifteen
existing changed/new files matched the reviewed repair inventory. The remote
repair branch did not exist. GitHub `main` and cached `origin/main` were at
`f619d71f371103b66427dcf5034ebd551fbe5f2a`. Local `main` was already older, at
`4745b7a792036785d54a2210b62a0b9100bb8779`; it was left untouched.

No development or validation changes were made during this checkpoint. The only
new project content is this acceptance/audit document. The existing repair
candidate was tested again using Node `v24.21.0` and Python `3.12.15` on macOS:

| Check | Final actual result |
| --- | --- |
| Complete Node suite | **1090 total: 1088 passed, 0 failed, 2 existing skips** |
| Complete Python suite | **353 passed, no failures/errors/skips** |
| UI/recovery regressions, included in Node total | **72 passed** |
| Usage replay against the repaired demo | **34 passed** |
| Completion replay against the repaired demo | **64 passed** |
| Established consistency checks | **10/10 passed** |
| Frozen preservation fingerprints | **67/67 unchanged** |
| Historical workflow/catalogue/knowledge/evaluation/document files | **47/47 byte-identical to the approved base** |
| Generated Local/AIEP outputs | **8/8 reproducible and fresh; repeat generation changes neither bytes nor mtimes** |
| Manifest source/output hashes | **All verified** |
| Whitespace, reviewed-file and staged-content checks | Required before commit |

The full suites were run with `node --test tests/*.test.mjs` (the existing Python
environment's `bin` directory added to PATH for fixtures) and
`.venv/bin/python -B -m unittest discover -s tests -p 'test_*.py' -v`.
Replays used the existing `MYTECH_REPAIR_PACKAGE=v21_quick_prompt_demo` and
`MYTECH_COMPLETION_PACKAGE=v21_quick_prompt_demo` test entry points.
The ten established consistency commands are recorded in
[the UI-polish report](v21-clarification-ui-polish.md). No weaker replacement
commands or live model calls were used.

The two Node skips remain the explicitly selected private school candidate
suites. No private candidate was selected. Public regression and synthetic
builder fixtures ran normally; private school-export behavior is not claimed.

## Presentation scenario coverage in passing offline suites

| Scenario | Available regression evidence |
| --- | --- |
| P01 Laptop + Mouse | Quick-prompt Gaming Setup, independent category constraints |
| P02 Study Laptop | Quick-prompt standard recommendation and catalogue checks |
| P03 ANC Headphones | Quick-prompt ANC starter, all requested usages validated |
| P04 Gaming Smartphone | Quick-prompt Gaming Smartphone starter |
| P05 Clarification + recommendation | Structural, UI-polish, Local/AIEP and loopback two-turn tests |
| P06 Cheaper | Quick-prompt, usage/completion replays, hard cap and anchor checks |
| P07 Alternative | Quick-prompt and replay identity/direction/anchor checks |
| P08 Honest no-match | Completion replay verifies genuine Headphones no-match and false-omission rejection |
| P09 Unsupported Printer | Local/frontend scope controls, unsupported refusals, mixed-request rejection |
| P10 Help/unrelated | Quick-prompt/completion control tests without product leakage |
| P11 Restart/isolation | Quick-prompt, structural and UI-polish stale-response/chat-ID tests |
| P12 Failure/recovery | UI-polish, quick-prompt, local transport and existing recovery tests |

The deterministic question derives only from a verified, incomplete single
supported target. Rejected model prose is not displayed or stored as validated
history. The fallback recovery control is hidden and invalidated; real failures
retain draft restoration and stale-request protection. Normal recommendation,
source, price, usage, hard-budget, comparison, no-match and grounding checks remain
strict. Existing validators, Node policy, catalogue, workflows and CSS were not
changed by this audit, and preservation checks confirm their protected bytes.

## Security review and exact commit inventory

The existing credential scanner reports no findings in public generated assets,
runtime/builder source, reports, or the remaining reviewed fixtures. It flags
only two reviewed `literal-credential` occurrences: the fixed dummy keys at
`tests/p05-clarification-contractions.test.mjs:30` and
`tests/structural-clarification.test.mjs:276`. Both are explicitly synthetic
offline fixture values, use `.invalid` endpoints and injected providers, and are
not real secrets. Their exact values and locations were checked rather than
generally exempting test files. Scanner coverage is heuristic, not proof against
every possible secret type.

Explicit staging is limited to these **16 files** relative to the approved base:

1. `tools/build_v21_quick_prompt_demo.py`
2. `tools/templates/v21_quick_prompt_demo.js`
3. `generated/v21_quick_prompt_demo/local/index.html`
4. `generated/v21_quick_prompt_demo/aiep/site/index.html`
5. `generated/v21_quick_prompt_demo/local/manifest.json`
6. `generated/v21_quick_prompt_demo/manifest.json`
7. `tests/clarification-ui-polish.test.mjs`
8. `tests/p05-clarification-contractions.test.mjs`
9. `tests/p05-live-retest.test.mjs`
10. `tests/structural-clarification.test.mjs`
11. `tests/fixtures/p05_live_clarifications_2026_11_12.json`
12. `docs/v21-clarification-ui-polish.md`
13. `docs/v21-p05-contraction-follow-up.md`
14. `docs/v21-p05-live-retest-follow-up.md`
15. `docs/v21-structural-clarification-repair.md`
16. `docs/v21-final-regression-checkpoint.md`

Scope is two source files, four deterministic output files, five test/fixture
files, and five evidence reports. The approved base already contains the initial
P05/P09 repairs and their history. No private environment files, backups, caches,
virtual environment, private exports, temporary diffs, runtime logs, presentation
artifacts, or unrelated files belong in this checkpoint.

This document records the pre-commit audit. The normal commit/push outcome,
complete commit SHA, fetched branch equality, working-tree cleanliness, protected
remote `main`, and actual GitHub status results are reported separately after
those operations. Current workflow triggers target PRs and/or pushes to `main`;
a repair-branch push alone does not establish a CI pass. No merge, deployment,
school update, or presentation artifact generation follows this checkpoint.
