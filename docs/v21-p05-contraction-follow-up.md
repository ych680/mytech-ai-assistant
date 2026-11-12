# P05 clarification contraction follow-up — 2026-11-12

Continued on macOS, branch `repair/p05-live-retest-follow-up`, with HEAD still
`3f4afc2ba0be85be4690f115e92d049fd8e7847b`. The starting tree contained the
previous repair's five modified files and two new files, all uncommitted.
Those changes were retained. No main-branch change, commit, push, merge,
deployment, workflow import, or live/paid API request was performed.

## Historical live retest: FAIL, 2026-11-12 18:49 (Asia/Hong_Kong)

User: `I need a laptop.`

Exact public response reported by the user:

```json
{
  "answer": "What’s your budget and main usage for the laptop?",
  "recommendations": [],
  "next_step": "Please provide your laptop budget and main usage.",
  "clarification_needed": true
}
```

FastGPT correctly identified Laptop and missing fields `budget` and
`main_usage`. The local frontend incorrectly displayed:

> Please clarify which intended usage belongs to each product; no recommendation was accepted.

This remains a **failed live retest**. The earlier failed live retest and its
offline repair evidence remain unchanged in
[the prior report](v21-p05-live-retest-follow-up.md). The original presentation
assessment remains **12 scenarios: 10 PASS, 2 FAIL (P05 and P09)**. No historical
assessment was overwritten or relabeled as a live success.

## Confirmed cause and serving investigation

Before this change, the deterministic builder's `--check` passed. Both generated
frontends contained the prior category-prefixed budget repair, with SHA-256:

| Frontend | Pre-contraction SHA-256 |
| --- | --- |
| Local | `030def648799d145f69a2c8cd527634f9061fabc50c480ff89a97e026d87a3e1` |
| AIEP | `4df19c6c9253dbe596cfebf3f1175c60cfdc04e7086411359525589a1c73f409` |

Fresh offline Local/AIEP harnesses reproduced the exact error using these current
files. Of six baseline cases, **2 passed and 4 failed**: `What is` passed in both
frontends; straight-apostrophe `What's` and U+2019 `What’s` failed in both. Failed
cases accepted zero history entries and returned false from
`demoMissingFieldClarification()`. The uncontracted response accepted two entries.

`parseQuestion()` required `what is` or `what are` at the beginning of the
bounded simple-question production. Existing lowercasing and whitespace cleanup
do not expand contractions. Thus the new `answer` failed parsing even though
the category-prefixed `next_step` was already valid. The existing usage guard
selected the ownership-error message. The failure is reproducible in the current
package without a browser cache, a running old server, or any live service.

At initial inspection, `lsof` found no listener on default demo port 8788 and
no listening Node process. Therefore the HTML/browser state actually used at
18:49 cannot be verified retrospectively. The launcher selects
`generated/v21_quick_prompt_demo/local/`, while the legacy TEST entry point
defaults to `generated/v2_1_test/`. The server reads HTML into memory at startup;
an already running process requires a restart to pick up regenerated files.
It sends `Cache-Control: no-store`; an already loaded browser document still
requires reloading. These facts are separate from the confirmed grammar defect.

A new short-lived offline test starts the actual demo launcher on an ephemeral
loopback port, verifies `/` and `/index.html` against disk and the manifest hash,
checks `Cache-Control: no-store`, and exercises all three wordings through the
local frontend and HTTP server with an injected `.invalid` provider. All return
HTTP 200 and display the clarification. The fixture server is closed afterward.
No existing process or real FastGPT binding was used or restarted.

## Minimal incremental repair

Only the opening of `parseQuestion()`'s existing simple-question production
changed, plus an explanatory comment:

```diff
-const simple = /^(?:what (?:is|are)|(?:could|can) you (?:tell me|provide|specify|share)) (.+)$/.exec(clause);
+// Accept contracted "what is" only as an opening to a parsed question.
+const simple = /^(?:what(?: (?:is|are)|['\u2019]s)|(?:could|can) you (?:tell me|provide|specify|share)) (.+)$/.exec(clause);
```

This accepts only U+0027 and U+2019 apostrophes in that opening. It performs no
general replacement or normalization. The captured remainder must still pass
`parseTerms()`, target-category matching, missing-field coverage, and all later
response/display checks. Question punctuation, single-target ownership, usage
validation, empty recommendation requirement, and four-field contract checks
are unchanged. Unsafe or contradictory extra prose remains rejected.

Incremental changed files are the runtime template, both generated HTML files,
both generated manifests, `tests/p05-clarification-contractions.test.mjs`, and
this report. All generated files were written by the unchanged deterministic
builder. The prior 72-test suite and prior report remain byte-identical to the
start of this follow-up. Workflows, prompts, catalogues, knowledge, recommendation
policy, grounding rules, transport, and Editorial Clean styling are unchanged.

## Exact verification results

Node `v24.21.0`, Python `3.12.15`, macOS:

| Suite/check | Result |
| --- | --- |
| Full Node suite | **881 total: 879 passed, 0 failed, 2 existing skips** |
| Full Python suite | **353 passed, 0 failures/errors/skips** |
| New contraction tests, included in full Node total | **175 passed** (174 harness cases and one loopback HTTP test) |
| Prior category-prefixed budget suite, included above | **72 passed**, unchanged |
| Usage replay against repaired Quick Prompt Demo | **34 passed** |
| Completion replay against repaired Quick Prompt Demo | **64 passed** |
| Read-only consistency commands listed in prior report | **10/10 passed** |
| Frozen preservation SHA-256 fingerprints | **67/67 unchanged** |
| Baseline workflow/catalogue/knowledge/evaluation/document files | **47/47 byte-identical to `3f4afc2`** |
| Repeat deterministic builder | **8/8 output bytes and mtimes unchanged** |
| Exact-diff/whitespace checks | Passed |

The two Node skips are the existing private school candidate suites requiring
explicit selection. Neither was selected. Node suites/replays used loopback
permission for fixture servers. All upstream replies were in-memory fixtures;
no live/paid API calls were made. Full-suite and replay commands are unchanged
from the prior report; the new suite is discovered by `tests/*.test.mjs`.

Both old and new live responses, plus the straight-apostrophe variant, pass in
both generated frontends: original strings display unchanged, two history
entries are accepted, zero cards are displayed, and no product anchor is saved.
Tests cover all four supported single categories, wrong-category questions,
omitted missing fields, fabricated products and prices, unsafe promises and
instructions, negated/contradictory clauses, ambiguous ownership, already
complete requests, unsupported usage, malformed public contracts, and malformed
contraction spellings. Negative controls accept no history or product cards.

Final generated HTML SHA-256:

| Frontend | SHA-256 |
| --- | --- |
| Local, also verified over HTTP | `8452533fdbd6fc01f243e48e25c53bc82a951a07f7bc6a9dd8e6f6f245a47d43` |
| AIEP | `8a256b0bea85c2d0ac733b5799c9ea6254a5c83786b05441264d512e7d16e44d` |

Verification stops here. A fresh real FastGPT retest, historical browser/server
state, other model phrasing, live retrieval/memory, and native browser layout
remain unverified. No live success is claimed. All changes remain uncommitted.
