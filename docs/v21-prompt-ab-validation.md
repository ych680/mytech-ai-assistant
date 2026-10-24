# MyTech v2.1 — six-request GLM-4.7 prompt A/B experiment

Subsequent repository integration preserves the actual Original and Optimized
exports in the [workflow registry](../workflow/v2.1/registry.json). A separate
[maintainer-reported T01 smoke test](v21-glm47-smoke-test.md) passed with 34.45 s
total latency; it is not a completed paired A/B run and does not populate the
six NOT_RUN result rows below. No meaningful prompt latency improvement has
been demonstrated. Original remains the AIEP default.

Prepared 2026-10-24 (Asia/Hong_Kong), `feat/v21-automated-catalogue`.
Status: **import candidates prepared from the actual supplied export; KB binding
and publication revision remain pending. Stop for review.**
No import, live API request, credits, app/website change, commit, push or merge
was performed. The current published DeepSeek-powered TEST app and AIEP remain
protected. No API credential was accessed.

The comparison is **GLM-4.7 long prompts versus GLM-4.7 short prompts**.
DeepSeek TEST is the functional source, not a latency comparator or load target.
Model changes are confined to the isolated A/B import files/apps.

## Final files

Directory: `generated/glm47_prompt_ab/`.

| File | Purpose |
| --- | --- |
| [A-glm47-original.json](../generated/glm47_prompt_ab/A-glm47-original.json) | Original actual prompts; both target nodes set to GLM-4.7 |
| [B-glm47-short.json](../generated/glm47_prompt_ab/B-glm47-short.json) | Derived from A, changing only two instruction values |
| [prompt-changes.diff](../generated/glm47_prompt_ab/prompt-changes.diff) | Exact A/B prompt diff |
| [manifest.json](../generated/glm47_prompt_ab/manifest.json) | Source/provenance hashes, graph/code inventory, model/prompt changes and pending gates |
| [configuration-checklist.json](../generated/glm47_prompt_ab/configuration-checklist.json) | Preserved settings and KB/publication limitations |
| [plan.json](../generated/glm47_prompt_ab/plan.json) | Three pairs, six scheduled single-turn requests |
| [six-request-results-template.csv](../generated/glm47_prompt_ab/six-request-results-template.csv) | Six NOT_RUN rows; all measurements NA |

These files are native FastGPT workflow imports, not AIEP uploads. Both candidates
require selection of the same existing TEST KB after import because the actual
export omits it. They are not claimed to be ready for live execution.

## Actual export and comparison

The user supplied `~/Downloads/MyTech v2.1 — TEST Knowledge.json`, newly exported
from the actual working FastGPT TEST application: **190,315 bytes**.
Original SHA-256:
`3e6087b7572ea4c7cfa702c895f5b6a369e6a31c032cfd4264d5d2e72b736f60`.
The file was inspected read-only and remains unchanged.

Credential-pattern scanning and a recursive check of nonempty credential fields
found no secrets before copying. Only `/chatConfig/_id` account metadata was
removed from the repository copy; JSON formatting was normalized. No workflow
logic, setting, model, prompt, code or layout changed in this source copy:
[sanitized actual export](../tools/templates/v21_working_actual_export_sanitized.json).
The [review record](../tools/templates/v21_glm47_actual_export_review.json) pins
original/copy hashes, the redaction, comparisons and limitations. Scanning is
bounded and does not certify every possible secret encoding.

The actual export, not the old portable snapshot or reconstructed A, is now the
authoritative source. Comparison with reconstructed A found exactly seven
semantic JSON differences:

| Path | Difference in actual export |
| --- | --- |
| `/chatConfig/_id` | Account metadata, removed from repository copy |
| `/nodes/2/inputs/0/value` | Extraction model bound to `deepseek/deepseek-v4.1-flash` |
| `/nodes/9/inputs/0/value` | Clarification model bound to `glm-4.7` |
| `/nodes/10/inputs/0/value` | Recommendation model bound to `deepseek/deepseek-v4.1-flash` |
| `/nodes/17/inputs/0/valueDesc` | Dataset type declaration instead of local import placeholder |
| `/nodes/19/position/x` | Editor layout coordinate |
| `/nodes/19/position/y` | Editor layout coordinate |

The two original prompts match reconstructed A exactly: 11,634 and 11,087
characters. Every remaining code value, ID, output, state/routing binding,
parameter and schema matches. New A/B retain the actual layout and declaration.

### Evidence limits

**KB binding is absent:** Retrieval has `datasets.value=[]`; `valueDesc` is only
the type declaration `{ datasetId: string; }[]`, not a selected dataset. The
active KB name/ID/version cannot be recovered. Similarity is verified as 0.35,
but two empty selections do not prove runtime KB parity. An operator must bind
the same actual existing unchanged 54-product TEST KB in both isolated apps.
Do not create, edit, upload, rechunk or re-embed a KB for this experiment.

**Published revision is unverified:** the user identifies the fresh export as
the working application. The JSON has no verifiable publication revision/time
or published-versus-editor-draft marker. Settings/prompts are verified as
exported; correspondence to the exact current published revision is not
independently proven. Confirm it in a later read-only operator review. Do not
republish the live app to resolve uncertainty.

**GLM selector evidence:** the actual Clarification node already selects the
native value `glm-4.7`; that exact selector is used for the other two nodes.
No account-specific identifier was guessed. This is export evidence, not a
live availability, native extraction-feature, quota or model-success test.

## Controlled configuration and verified parity

| Role / node | Actual source | A | B |
| --- | --- | --- | --- |
| State Extraction `etNrwEXVwr5sySpK` | `deepseek/deepseek-v4.1-flash` | `glm-4.7`, original prompt | `glm-4.7`, short prompt |
| Recommendation `pskHz4kajjJnBWwG` | `deepseek/deepseek-v4.1-flash` | `glm-4.7`, original prompt | `glm-4.7`, short prompt |
| Clarification `ikIzMK483vihRths` | `glm-4.7` | unchanged | unchanged |

Sanitized source → A changes exactly two model selector values. A → B changes
exactly State Extraction `description.value` and Recommendation `systemPrompt.value`.
The metadata redaction occurred once before A/B construction and is separately
recorded. No local graph overlays/reconstruction are applied.

| Instruction | A characters | B characters | Reduction |
| --- | ---: | ---: | ---: |
| State Extraction, including unchanged reliability appendix | 11,634 | 5,615 | 51.74% |
| Recommendation | 11,087 | 5,164 | 53.42% |

Verified exported parity:

- Exactly 20 nodes / 18 edges; all node/output IDs, edges, native schemas and
  actual layout retained. Every non-prompt JSON value is identical in A and B.
- Other model selections/parameters/settings unchanged. Extraction and
  Recommendation histories remain 6; Recommendation cap 4096; Clarification
  cap 800, reasoning off, history 6. Unspecified parameters remain unspecified;
  effective provider defaults still need runtime review.
- RAG similarity 0.35, limit 5000, embedding search, rerank/query extension off;
  query/quoteQA bindings unchanged. Existing KB identity remains pending.
- Currency normalization, extraction schema, ordered prompt references, routing,
  globals/state writers, budget/usage/identity/category/price/source validation,
  comparisons and memory-protection code are byte-identical to actual source.
- Public output retains exactly `answer`, `recommendations`, `next_step`,
  `clarification_needed`, with unchanged product fields, fallback and no-result
  behavior. Extraction retains its separate five-field schema.

The manifest contains node/output inventories, source code hashes and proof
flags for source→A and A→B boundaries. Native-code tests compare actual source,
A and B for currency normalization, independent budgets and invalid
budget/usage/source/price anchor protection. They do not run GLM or prove prompt
reliability. Broader offline routing/fallback/state tests remain enabled.

## Exact later import procedure

None of these platform operations has been performed.

1. Identify the working **published** MyTech v2.1 TEST app/revision and confirm
   its long prompts/configuration match this export. Record sanitized evidence;
   stop if the exported editor draft differs. Leave DeepSeek TEST/AIEP unchanged.
2. Identify its actual existing 54-product TEST KB and version/index. The JSON
   omitted this selection; record the nonsecret identity for matching A and B.
3. Create two new empty advanced workflow apps, e.g. `MyTech v2.1 GLM47 A long`
   and `MyTech v2.1 GLM47 B short`. Neither may be the working DeepSeek app or
   connected to AIEP. No API key needs to enter the source or import files.
4. In only the new A editor, use native JSON workflow import with
   `generated/glm47_prompt_ab/A-glm47-original.json`. In only the new B editor,
   import `generated/glm47_prompt_ab/B-glm47-short.json`. Do not import the older
   reconstructed package, overwrite TEST, or upload anything to AIEP.
5. Select exactly the same existing KB from step 2 in both Retrieval nodes.
   Preserve similarity 0.35 and every other retrieval setting. Do not modify
   knowledge contents. If import silently resets settings, stop for review.
6. Confirm both target nodes show `glm-4.7`, Clarification stays unchanged, and
   every exposed parameter matches A/B: temperature, reasoning, token caps,
   histories, extraction schema, references, query/RAG, validation/routing/memory.
   Do not accept model selection resetting other parameters. Operator/platform
   confirmation of GLM support for native extraction remains required.
7. Confirm all 20 nodes, 18 edges and node/output IDs survived native import.
   Compare A/B after KB selection: only the two prompts may differ. Record
   isolated app identities/revisions and sanitized configuration evidence.
   Publish only isolated apps if required and separately authorized.
8. Approve a platform-credit cap and **six-request maximum** before sending.
   Use the same native FastGPT execution/trace path in both apps, sequentially;
   do not compare one through AIEP with another through a different path.

Configuration checklist:

- [x] Actual supplied export scanned/compared read-only; source copy has only
  documented account-metadata removal.
- [x] Target GLM selectors verified against actual export evidence.
- [x] A retains actual original prompts; B differs only in the intended two fields.
- [x] Export-level graph/code/parameters/output equality checked offline.
- [ ] Published revision matches exported editor configuration.
- [ ] Same actual existing 54-product KB bound in both isolated apps; version/index
  and similarity 0.35 confirmed. **Export omitted the selection.**
- [ ] Native import, model-feature support and final configuration parity reviewed.
- [ ] Separate apps, six distinct fresh conversations and credit cap approved.
- [ ] DeepSeek TEST/AIEP untouched; proceed only after review.

## Initial plan: three pairs, six requests total

| Pair | Identical A/B message | Expected result |
| --- | --- | --- |
| G01 | `I need a laptop under ¥6,000 for gaming.` | Raw extraction Laptop / 6000 / Gaming, supported; recommendation route; one eligible grounded Laptop <=6000 |
| G02 | `I need a laptop for studying under RMB 6000 and a gaming mouse under RMB 300.` | Separate budgets/usages; two valid grounded products; no Office-only Gaming mouse or unsafe batch |
| G03 | `I need a gaming mouse.` | Missing budget only; clarification route; no recommendations; ask only for budget |

Order: **G01-A, G01-B, G02-B, G02-A, G03-A, G03-B**.
Each request uses a new distinct conversation: six conversations, one turn each.
There are **no warm-ups, repeats, retries, clarification-answer continuations or
extra follow-ups**. A failed send counts toward six. Stop on setup/safety/credit
problems; do not automatically rerun anything.

The broader currency, comparison, cancellation, restart, no-match and fault suite
is retained in [deferred history](v21-prompt-ab-broader-plan-deferred.md) and the
offline tests. The old 28/80-request schedule is superseded and **not authorized**.
Its generated artifacts explicitly say DO_NOT_IMPORT and remain offline fixtures.

## Measurements and interpretation

Copy the results template outside the generated directory before recording data.
Its six NOT_RUN/NA placeholders contain no measurements. For each request record:

| Metric | Definition |
| --- | --- |
| State Extraction latency | Native trace elapsed ms for `etNrwEXVwr5sySpK`, same method in A/B |
| Recommendation latency | Trace ms for `pskHz4kajjJnBWwG`; G03 has `recommendation_executed=0`, duration `NA`, not zero |
| Total workflow latency | Native total elapsed ms including clarification; not the sum of node durations |
| Platform credits | Attributable debit and actual platform unit. If only a shared meter exists, isolate usage or record NA. Record aggregate scope once, without duplicate per-request credit claims |
| Extraction/routing correctness | Compare raw extraction to expected category, exact budget/null and usage; inspect actual branch. Record bad extraction even if a downstream guard repairs it |
| JSON validity | Final public JSON parses with exactly four required keys/types; product facts/source match the unchanged Master |
| Validation/fallback | Trace-confirmed `accepted`, `validator_fallback`, `not_executed_clarification`, `error`, or `NA`. Empty products alone do not prove fallback |
| Turn pass | All assertions met; no wrong identity/category/price/source, over-budget/usage violation, wrong scope or unsafe batch |

Retain failures and sanitized evidence references, without keys, cookies or raw
private exports. Usage limits are not consumed credits. Character/token savings
are not measured debit savings. Label unavailable/aggregate measurements honestly.
For each pair report A/B values and `100*(B-A)/A` when both exist and A is nonzero.
Keep G03 separate because it skips Recommendation Assistant. A fast wrong route,
fallback or missing recommendation is not a speed improvement.

One observation per variant/scenario is exploratory: no p95, significance,
reliability-equivalence or rollout claim. Stop/review if B regresses on safety,
extraction/routing/schema or unexpected fallback. Incomplete/noisy evidence is
inconclusive. Any additional request or production prompt change needs review.

Rollback means stopping the isolated apps while retaining working DeepSeek
TEST/AIEP. No live prompt replacement is part of this phase. Preserve evidence;
archive experimental apps only under later authorization.

## Offline checks

```sh
.venv/bin/python -B tools/build_glm47_prompt_ab.py
.venv/bin/python -B tools/build_glm47_prompt_ab.py --check
.venv/bin/python -B tools/build_prompt_ab_test.py --check
.venv/bin/python -B tools/check_catalogue_consistency.py
.venv/bin/python -B tools/build_aiep_test.py --check
.venv/bin/python -B -m unittest discover -s tests -p 'test_*.py' -v
node --test --test-isolation=none tests/*.test.mjs
.venv/bin/python -B tools/validate_products.py --strict-v1
.venv/bin/python -B tools/build_knowledge.py --check knowledge/MyTech_Product_Knowledge_v1.md
git diff --check
```

The active builder defaults to the pinned actual source/review, verifies hashes
and provenance, rejects known reconstructions/blank model choices/reference drift
and environment-file inputs. It never obtains A through the old reconstruction
builder. Without a source its library returns a blocked plan with no fabricated
workflow exports. Symlinks and unexpected files/results fail closed; read-only
checks never repair artifacts. It has no live execution or API capability.

Final offline results: **292 Python tests and 321 Node tests passed**, with no
failures, skips or cancellations. This includes 13 new actual-export/GLM build
tests and 6 actual-source/GLM native-code tests, while retaining the broader
offline suite. Also passed: strict-v1 (27 products / nine categories), stable
knowledge consistency, all 54-product catalogue/AIEP checks, active/deferred A/B
checks and `git diff --check`. Local HTTP tests used loopback listeners with
mocked provider transports; no model or live API was called.

Final preservation review: the downloaded original's bytes/hash and modification
time are unchanged. Thirty protected pre-existing template/deployment/Master
files remain byte-identical, including existing local TEST and AIEP assets.
Credential-pattern review passed across 25 explicit public source/artifact files;
no environment file was read. The exact A/B JSON differences are only
`/nodes/2/inputs/1/value` and `/nodes/10/inputs/13/value`. No requests were executed
and no performance or credit saving is claimed.
