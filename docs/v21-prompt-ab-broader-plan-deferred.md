> DEFERRED HISTORY ONLY. The active experiment is the six-request GLM-4.7 plan in [the current guide](v21-prompt-ab-validation.md). The 28/80-request schedule below is superseded and is not authorized to run. Reconstructed exports are offline fixtures, not the authoritative working baseline.

# MyTech v2.1 — Prompt Optimization Phase 2: A/B validation preparation

Prepared 2026-10-24 (Asia/Hong_Kong), branch `feat/v21-automated-catalogue`.
Status: **offline preparation complete; stop for review before import or requests**.
The user reports successful university AIEP deployment, confirmed binding to the
published working FastGPT TEST app, a rotated credential and increased usage
limit. No credential was read and no deployment, app, model or KB was accessed
or modified during this preparation. Increased quota is not A/B run approval.

## Import package and exact prompt changes

Directory: `generated/prompt_ab_test/`.

| File | Purpose |
| --- | --- |
| [mytech-v21-prompt-A-control.json](../generated/prompt_ab_test/mytech-v21-prompt-A-control.json) | Portable long-prompt control, for a new isolated A app only |
| [mytech-v21-prompt-B-short.json](../generated/prompt_ab_test/mytech-v21-prompt-B-short.json) | Portable shortened-prompt candidate, for a new isolated B app only |
| [prompt-changes.diff](../generated/prompt_ab_test/prompt-changes.diff) | Full exact textual diff of the two instruction values |
| [manifest.json](../generated/prompt_ab_test/manifest.json) | SHA-256 provenance, prompt hashes/sizes and invariant graph/code audit |
| [plan.json](../generated/prompt_ab_test/plan.json) | Exact messages, expected assertions, schedule and request ceiling |
| [turn-results-template.csv](../generated/prompt_ab_test/turn-results-template.csv) | Empty turn-level results sheet; no invented measurements |
| [node-metrics-template.csv](../generated/prompt_ab_test/node-metrics-template.csv) | Empty per-node measurements sheet |

Import exactly the relevant workflow JSON file through FastGPT's advanced/native
workflow JSON import. The directory is not a website upload. Do not upload it to
AIEP or import either JSON into the current published TEST app.

| Node / instruction value | A: long | B: short | Reduction |
| --- | ---: | ---: | ---: |
| State Extraction `etNrwEXVwr5sySpK`, input `description.value` | 11,634 chars | 5,615 chars | 51.74% |
| Recommendation Assistant `pskHz4kajjJnBWwG`, input `systemPrompt.value` | 11,087 chars | 5,164 chars | 53.42% |

The State Extraction reliability appendix (`v21_extraction_rules.txt`) remains
byte-identical in both variants. Recommendation interpolation references remain
identical and in the same order: current targets from `tWP2LwPvzFadPPtk`,
same-category history from `sxwN5Fd17Tc8leTf`, and intent variable `fD4C5VOp`.
Exact original/shortened hashes and full instructions are in the package. These
are character reductions, not measured token, credit or latency savings.
In these exports the exact changed JSON paths are `/nodes/2/inputs/1/value`
and `/nodes/10/inputs/13/value`; the node IDs/input keys above are the semantic
identifiers to use when reviewing the FastGPT editor.

## Provenance: what is verified and what remains a gate

The repository contains the reviewed portable working Current snapshot and
TEST overlays, plus the shortened generated TEST workflow. It does **not**
contain a fresh sanitized export of the now-published working TEST application.
A is reconstructed by restoring the two known pre-shortening instruction values
on the existing generated 54-product TEST graph. B is a byte-exact copy of that
existing shortened workflow. The generator validates the source graph against
all reviewed TEST overlays before preparing the pair.

Consequently, **exact parity with the current live long prompts/configuration
is pending operator confirmation**. The user's confirmed AIEP binding establishes
the application connection; it does not supply prompt text or bound configuration
for an offline comparison. Do not call the reconstructed A a fresh live export.
If the published prompts or non-prompt configuration differ, stop and obtain a
reviewed credential-free baseline before testing. Do not repair this discrepancy
by changing the working TEST app or silently applying other local overlays.

Verified local A-versus-B invariants:

- Exactly 20 nodes / 18 edges, identical original node and output IDs/order,
  native node schemas, all edges, reference bindings and five global variables.
- All JSON outside the two instruction string values is deeply equal, including
  every model field, history/reasoning/token setting, file input, extraction
  schema, retrieval field, condition, state update and answer binding.
- Extraction and Recommendation history remain 6. Recommendation cap remains
  4096. Clarification reasoning remains off and its cap remains 800. Retrieval
  similarity remains 0.35; native search/query/quoteQA settings are unchanged.
- All code nodes are byte-identical: currency normalization, scope guard, query
  builder, usage validation, catalogue/price/source checks, positive hard-budget
  protection, comparison direction, memory and validation fallback. The embedded
  catalogue remains the 54-product Master, including provisional labels.
- The public contract remains exactly `answer`, `recommendations`, `next_step`,
  `clarification_needed`; product rows retain exact category, name, numeric price,
  reason and source. The extraction schema remains its separate five-field schema.

Portable model selectors are blank and retrieval has no concrete dataset
binding. Their equality proves local structure, **not actual live model/KB parity**.
The manifest explicitly marks this pending. No bound model IDs, KB IDs, application
credential, API endpoint or live state were exported. The graph fingerprint with
the two prompts masked and all code hashes support later configuration review.

## Exact later import and isolation procedure

These steps are instructions for a later approved operation; none were performed.
Console labels may vary. Use the existing native workflow import, not conversion
to a simple chat app or a different workflow schema.

1. Identify the current **published working MyTech v2.1 TEST** app by its
   non-secret app identifier and publication revision/time. Record the AIEP
   project binding as the protected existing destination. Leave its prompts,
   credentials, usage limit, publication and AIEP connection unchanged.
2. In a read-only review, compare that published version's State Extraction and
   Recommendation instruction text with package A, including whitespace and the
   extraction reliability appendix. Inspect the published version rather than an
   unpublished draft. Confirm the other configuration in the invariant list.
   Keep only sanitized configuration evidence; do not copy credential fields or
   a raw account export into this repository. If exact prompt/configuration
   parity cannot be established, leave the gate pending and do not run A/B.
3. Create **two new empty advanced workflow applications**, for example
   `MyTech v2.1 Prompt A/B — A control` and `MyTech v2.1 Prompt A/B — B short`.
   Record both new app identifiers and check neither equals the working TEST app.
   Using two isolated apps avoids using the classroom deployment as a load target.
4. Open only the new A app's workflow editor and import
   `generated/prompt_ab_test/mytech-v21-prompt-A-control.json`. Review its 20 nodes
   and 18 edges. Open only the new B app and import
   `generated/prompt_ab_test/mytech-v21-prompt-B-short.json`. Do not use
   `generated/v2_1_test/` as an ambiguous source directory or overwrite an app.
5. Populate the blank model selectors in **both** isolated apps with precisely
   the existing working app's State Extraction, Clarification and Recommendation
   models and all exposed parameters. Do not choose a default or “faster” model.
   Historical guidance mentions glm-4.7, but the actual working selection is the
   control; it was not inspected here. Preserve temperature, reasoning, caps,
   histories, output/tool schema, retry/cache behavior and any account settings.
6. Bind both Retrieval nodes to the **same existing unchanged 54-product TEST KB**
   used by the working app. Preserve dataset selection, embedding/index version,
   chunking, similarity 0.35, search mode, limit, rerank and query-extension fields.
   Do not import/rechunk/re-embed knowledge, create a replacement KB or edit it.
7. Compare the imported A/B graphs after binding. All model/KB bindings and other
   settings must match each other and the working baseline. Only the two
   instruction values may differ between A and B. Confirm the normalizer, guard,
   validator, state writers, fallback route and four-field public outputs. If
   import drops nodes, resets settings or changes IDs/references, stop for review
   instead of editing the live application. Record the two isolated app
   revisions, prompt fingerprints and sanitized parameter inventory.
8. Save/publish **only the isolated apps**, if publication is required by the
   chosen test path and separately authorized. Use the same native FastGPT debug/
   execution path for both variants so per-node traces are comparable. Do not
   compare A through AIEP with B through another endpoint. Do not bind either
   experimental app to AIEP, change the existing AIEP upload or rotate/read a key
   for this preparation. Native console testing avoids a need for a new client
   integration; any later API harness/credentials require separate authorization.
9. Confirm an operator-approved request and credit ceiling before the first run.
   Use distinct new chats for every variant/scenario/repetition, with the same
   user sequence within each pair. Preserve each scenario's chat for its own
   follow-ups. Never reuse a working classroom chat or share A/B session IDs.

## Small controlled protocol

The exact messages and semantic assertions are in `plan.json`; concise wording
and eligible product selection may differ, but catalogue facts and state rules
may not. Four RMB forms normalize to the same hard budget, 6000.

| Scenario | Turns | Expected behavior |
| --- | ---: | --- |
| C01–C04: Gaming laptop under `RMB 6000`, `RMB 6,000`, `¥6000`, `¥6,000` | 4 fresh chats | Supported Laptop / 6000 / Gaming; one grounded eligible laptop |
| S01: Study laptop under RMB 6000 | 1 | Exact identity/source/price; correct usage and hard budget |
| M01: Study laptop under 6000 plus Gaming mouse under 300 | 1 | Two independent valid requests/recommendations; Office-only mouse is invalid |
| T01: Study laptop + Gaming mouse; cheaper mouse; another laptop; more expensive mouse | 4 in one chat | Only named category changes; retain other request/anchor; strict direction and current budget |
| N01: Gaming mouse under RMB 50 | 1 | Truthful no-match, empty recommendations, no budget widening |
| Q01: Gaming mouse; then RMB 300 | 2 in one chat | Ask only for missing budget, then retain Mouse/Gaming and recommend |

This is **9 scenarios / 13 turns per variant per repetition**. Before measured
work, perform one identical fresh single-product warm-up in each isolated app,
label and exclude those two turns from latency/quality aggregates but include
their credits. First measured repetition: 26 requests; initial smoke including
warm-ups: **28 requests**. Review it before continuing. Three repetitions total:
78 measured requests plus 2 warm-ups, **80 requests maximum**, with no automatic
retries. Do not start the remaining repetitions without the approved credit
headroom. A stopped/failed send still counts toward the ceiling.

Alternate whole scenario-pair order: for zero-based scenario/repetition indices,
use AB when their sum is even and BA otherwise. Run sequentially, with no
overlapping A/B work or unrelated account load if credit metering is shared.
Keep the schedule, client region, entry path and time window comparable. Record
warm/cold/cache/queue conditions if exposed; do not silently discard slow runs.
Any rerun gets a new pair/session, remains in the log, and needs extra budget
approval beyond the fixed ceiling. Do not substitute a different test after
seeing a result.

For T01, compare against **each variant's own last validated anchor**. A cheaper
choice may not exist if the initial answer already selected the cheapest match;
a truthful no-match is then correct. Replaying identical user text does not
guarantee identical model-generated assistant histories or retrieval queries.
Treat stateful trajectories as reliability evidence and report anchor/history
differences; do not attribute their follow-up latency differences solely to
prompt length. Fresh currency/single/multi cases are the cleaner paired timing
comparison. Do not inject hidden state or change bindings to force equal anchors.

### Controlled validation fallback

N01 is an expected no-match, not necessarily a validator failure. Do not combine
those outcomes. Real live runs may have zero validator fallbacks; that is valid
measurement, not a reason to loosen validation or manufacture a bad request.

`tests/prompt-ab.test.mjs` deterministically injects seven faults into **both
packaged validators offline**: wrong exact price, source, category, over-budget
product, wrong usage, malformed JSON and duplicate-category batch. It executes
the native validation router and public failure answer and verifies four fields,
zero unsafe recommendations and preserved prior memory. It also verifies a
valid multi-product result and a targeted cheaper follow-up. These tests consume
no model credits and isolate fallback behavior independently of model variation.
Do not edit live code nodes, poison the KB or disable validators to force an
online fallback. During approved live runs, record actual validation-node rejects
when traces expose them; keep them separate from intended no-match/clarification.

## Measurements and decision rule

Copy the empty CSV templates **outside** `generated/prompt_ab_test/` before
recording actual results so generation cannot erase evidence. Each emitted turn
gets a unique `run_id`; `pair_id` ties the same scenario/repetition across A/B,
and `session_label` is a harmless local label rather than an app chat token.
Use 1/0 for reviewed booleans, `NA` for unobservable/inapplicable values. Missing
measurements are never zero. Keep app/revision/model/KB fingerprints in a
sanitized campaign note; do not record credentials, cookies or account secrets.

| Metric | Definition and source |
| --- | --- |
| Per-node latency | Execution trace duration in ms for **every executed node**, joined by `run_id` and node ID. Report State Extraction, Retrieval, Clarification and Recommendation separately; retain guard/router/validator times too. Mark skipped nodes `executed=0`, duration `NA`. Same trace method for both apps. |
| Total latency | `total_workflow_ms` from the native execution trace plus separate `wall_ms` from submit to final complete public response. Document timing method/resolution. Do not sum node times and call that total; overhead/concurrency may differ. |
| Valid recommendation rate | Sum of exact catalogue/usage/budget/scope-valid **public** recommendations divided by all returned public recommendations. Zero returned means `NA`, not 100%. Record numerator and denominator. |
| Eligible-request fulfillment | Valid public recommendations / oracle-eligible active request slots. Judge eligibility independently from the model using Master and the actual comparison anchor. Missing retrieval evidence is recorded separately as a retrieval miss; it cannot turn a missed eligible recommendation into success. Report per-case counts because follow-up anchor-dependent denominators can differ. |
| Turn pass rate | Turns meeting **all** case assertions, state/scope rules and four-field schema / all measured turns, including failed requests. Record `scope_ok`, `state_ok`, `json_contract_ok`, `turn_pass` and violation details; do not count a fast wrong-scope/fallback answer as a pass. |
| Validation fallback rate | Trace-confirmed validator-rejected turns / all measured submitted turns; also report per validator-executed turn. Public empty recommendations alone do not identify this route. Record the trace evidence or `NA`; keep intentional no-match, clarification, timeout, parse failure and transport error separate. |
| Credit consumption | App/trace-attributable platform debit per request if shown; otherwise isolated before/after meter delta for each run block, labelled with its scope and actual unit. Record warm-ups/failures too. Input/output tokens are separate supporting measurements, not assumed credits or prices. |

`outcome` labels: `recommendation`, `no_match`, `clarification`,
`validation_fallback`, `invalid_public_response`, `timeout`, `transport_error`,
or `other_error`. Label whether a no-match/clarification is expected via
`expected_kind` and case assertions. `validation_fallback` CSV column is the
trace-confirmed flag; an error may occur before a validator executes.
`safety_violations` counts exposed wrong identity/category/source/price/usage,
hard-budget breaches, unsafe batches or corrupted state, with details in a
sanitized evidence note. Retain raw trace-invalid candidate counts separately
in notes; a safely rejected candidate is not an exposed recommendation.

Record actual model/trace input and output token counts when available; never
derive billed tokens/credits from the 52–53% character reductions. If only a
shared account meter exists, exclude unrelated usage from the window or mark
credit attribution unavailable. Do not repeat a block debit on every turn and
sum it again. Report block-level deltas once using `credit_scope=block:<label>`;
per-request data uses `credit_scope=request`. Do not sum per-node credits and
turn/block totals together. Platform rounding, caching and background usage may
limit precision; unknown credit cost remains unknown.

After each paired repetition, report counts and errors for both variants,
per-scenario median/maximum node/total/wall latencies, and paired percent change
`100 * (B - A) / A`. Separate fresh eligible recommendation cases from clarification,
no-match and comparison cases. Report completion/latency for failures separately
as well as all-turn totals so excluding failures cannot create a false speedup.
Three observations per scenario are too few for meaningful scenario p95 or
statistical equivalence; do not claim either. If reporting a pooled p95, give
the count/mix and label it descriptive only.

Predeclare a **provisional** benefit threshold: at least 10% lower paired median
fresh eligible-case total latency, supported by lower extraction/recommendation
node times, with no new safety, state, scope or JSON failures; no lower
eligible-request fulfillment/turn pass rate; and no higher unexpected validation
fallback rate versus A. Credits must stay within the operator's approved cap
and be reported as measured, not presumed lower. This small sample can screen
for regressions; it cannot prove reliability equivalence. If timing is noisy,
incomplete or mixed, or either control/configuration is unreliable, classify the
result **inconclusive** and keep the working long prompts. Any serious regression
stops the campaign. Further runs or rollout need review; no automatic promotion.

## A/B checklist and rollback

- [x] Separate deterministic A/B exports prepared; exactly two prompt values differ.
- [x] Local 20/18 graph, IDs, all non-prompt settings/bindings and code verified.
- [x] Full prompt diff, manifest, controlled plan and empty measurement CSVs prepared.
- [x] Offline validation fallback, multi-product and targeted-memory checks pass.
- [ ] Published working TEST prompts/configuration match reconstructed control A;
  record read-only, sanitized evidence. **Required before live A/B.**
- [ ] Two isolated apps created/imported; actual models/parameters and existing
  unchanged TEST KB match working control and each other; import parity reviewed.
- [ ] Working TEST publication, confirmed AIEP connection and rotated credential
  left unchanged; no experimental app is connected to AIEP.
- [ ] Request ceiling, credit ceiling, schedule and trace/meter method approved.
- [ ] Run only the 28-request smoke first; review quality and credit headroom.
- [ ] Finish at most 80 total approved requests; retain failures and sanitized evidence.
- [ ] Compare reliability before latency/credits; keep result inconclusive if evidence
  is insufficient; do not change the working prompts as part of this phase.

Rollback consists of stopping the isolated campaign and retaining the working
TEST/AIEP deployment. No live prompt replacement is part of the experiment, so
no production restoration is needed. Retain A/B evidence and published revisions;
unpublish/archive experimental apps only under later authorization. Do not
rebind AIEP or edit the working app as a rollback step.

## Offline regeneration and checks

```sh
.venv/bin/python -B tools/build_prompt_ab_test.py
.venv/bin/python -B tools/build_prompt_ab_test.py --check
.venv/bin/python -B tools/check_catalogue_consistency.py
.venv/bin/python -B -m unittest discover -s tests -p 'test_*.py' -v
node --test --test-isolation=none tests/*.test.mjs
.venv/bin/python -B tools/validate_products.py --strict-v1
.venv/bin/python -B tools/build_knowledge.py --check knowledge/MyTech_Product_Knowledge_v1.md
git diff --check
```

The new builder writes only `generated/prompt_ab_test/`. It checks existing local
generated assets read-only; it does not call the catalogue writer or regenerate
AIEP. `--check` never repairs artifacts. Extra files or output symlinks fail
closed. Generated text is scanned for accidental credential patterns; exports
also require portable model/KB bindings. CI runs the new read-only check.

The [earlier optimization report](v21-targeted-llm-latency.md) records 260 Python /
279 Node tests from that workstream; the subsequent browser fix recorded 269 /
306. Phase 2 reruns the full suites, including 10 new A/B build tests and 9 new
A/B native-validator tests. Final run results are recorded below after execution.
No live performance or credit saving is claimed.

Final offline run: **279 Python tests and 315 Node tests passed**, with no failures,
skips or cancellations. Also passed: strict-v1 (27 products / nine categories),
stable knowledge consistency, all 54-product local/AIEP catalogue checks, the
separate A/B read-only check, credential-pattern review of 13 explicit public
files, and `git diff --check`. Loopback HTTP tests use mocked upstream transports;
listener permission was allowed for those existing tests only. No live API calls
or model credits were used.

Thirty previously existing public/template/deployment files retain their pre-task
SHA-256 checksums, including both prompt sources, existing generated TEST/AIEP
assets, Master, portable working snapshot, servers and validation templates.
Only the new isolated A/B directory was generated. Changed repository documents
and CI add instructions/checks; no existing workflow export, frontend or template
was rewritten during this phase.
