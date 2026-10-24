# v2.1 TEST State Extraction reliability fix

Local work on `feat/v21-automated-catalogue`. No credential file, live API,
Current application, deployment or Git write was accessed/performed. The Master
Dataset, stable files and authoritative portable Current snapshot are unchanged.

## Read-only audit and evidence

The reported output was `product_requests_json = "[]"` and
`scope_status = "unrelated"` for:

> I need a laptop under ¥6,000 for gaming.

The previous local TEST workflow fed the raw start message directly into State
Extraction (`etNrwEXVwr5sySpK`). Its native extraction schema defaults requests
to `[]` and scope to `unrelated`, with history 6. Its existing instructions
discuss RMB, approximate amounts and ¥6000 examples, but it had no deterministic
preprocessing for equivalent currency/grouping formats. The portable model
binding is empty; this audit cannot identify the actual live model/settings or
whether the reported value was model-generated or supplied as a field default.

Normalization & Guard (`tWP2LwPvzFadPPtk`) parsed the extraction strings and
trusted unrelated scope except for existing bounded comparison/cancellation
recovery. It did not compare an explicit current purchase against that scope.
Scope Router (`yrfKbYdd3I61H9JN`) correctly routed `unrelated` to its ELSE answer.
The router itself has no reference or condition defect in this reproduction.

Conversation State Update (`hMbWAx9XxkNcfG6V`) is **after** the supported branch.
Unrelated/help/unsupported turns bypass it, preserving old globals. Consequently
Laptop / 6000 / Gaming remaining in state is consistent with the reported
failure; it does not establish that extraction used that state correctly.
Extraction receives recent conversation history, not a direct reference to the
stored request global. Guard receives the global separately. Their views can
therefore differ. Old globals alone must not override an unrelated new task.

An offline native-graph regression reproduces the old unrelated route using the
reported extraction and matching historical state. The confirmed local defect
is the absence of input normalization and a scope-consistency check. **The
trigger for the live model's bad extraction remains unproved.** Currency
tokenization/grouping, output variability/defaults and history interaction are
plausible contributors, not measured root causes.

## Deterministic normalization and structural change

New node `v21RmbInputNormalize` runs before extraction. It copies the existing
Query Builder's native code-node schema and receives the original start input.
It converts these inputs to the same text before the LLM sees the current turn:

| Input amount | Normalized amount | Exact numeric budget |
| --- | --- | --- |
| RMB 6000 | RMB 6000 | 6000 |
| RMB 6,000 | RMB 6000 | 6000 |
| ¥6000 | RMB 6000 | 6000 |
| ¥6,000 | RMB 6000 | 6000 |

CNY and full-width ￥ are also accepted. Valid decimal amounts retain their
digits without rounding up. Sentence commas/periods remain punctuation.
Malformed grouping, non-positive amounts and unsafe magnitudes are marked
invalid and cannot be replaced with an old or invented positive budget.

Explicit foreign/mixed signals (currency symbols, common currency names/codes,
or an unknown three-letter money prefix after budget wording) prevent RMB
normalization. No exchange rate or automatic conversion is used. ¥ is treated
as RMB only without an explicit foreign signal; `JPY ¥6,000` stays unconverted.
Supported turns with foreign/mixed/invalid amounts have the relevant budget
cleared and take the existing budget clarification path, preventing old RMB
values or model-converted numbers from reaching recommendation. This is bounded
currency recognition, not a universal natural-language currency parser.

The TEST graph is now **20 nodes / 18 edges**, an intentional exception to the
earlier 19/17 structural baseline:

```text
Workflow Start → TEST RMB Input Normalization → State Extraction
                                               ↓
                                   Existing Guard → Existing Scope Router
```

One original connection, Start → Extraction, is replaced by two. The other
16 original edges are unchanged. All 19 original node IDs and their output IDs,
all five global variables/defaults, state-writer references, IF/ELSE conditions,
downstream prompt interpolations, retrieval schema, model structure and response
bindings remain intact. Extraction's content reference intentionally changes to
`["v21RmbInputNormalize", "v21NormalizedQuestion"]`. Guard/Query Builder/AI nodes
still have their original raw-question references. No original node is deleted.

A code stage is required to normalize current input deterministically **before
the LLM**, independently of which frontend calls FastGPT. A prompt instruction
or post-extraction number cleanup alone cannot provide that guarantee. The
working Current template remains unedited; the generator applies this explicit
TEST-only overlay. Native schema reuse and offline reference checks do not
establish school runtime/import compatibility.

## Conservative scope safeguard and budget checks

The guard uses current-message evidence, independently of saved globals. A
bounded affirmative purchase phrase must start with wording such as “I need”,
“I want”, “I'm looking for”, or “Can you recommend”, followed by a supported
device and an allowed purchase-detail clause. Multi-product clauses are handled
separately. Quotations, negations, hypothetical statements, repairs, capability
questions, incidental mentions and explicit mixed unsupported requests do not
trigger this recovery.

If that evidence contradicts unrelated/help/unknown scope, or supported scope
has no extracted request, the guard selects **supported clarification**. It
recovers only the explicit current categories and unambiguous literal RMB
budgets. Usage is left unconfirmed (`null`); it does not import stale usage or
approve a recommendation from contradictory extraction. Repeated failures remain
clarifications. A subsequent consistent extraction can proceed normally.
An explicit unsupported extraction/category still follows the existing
unsupported route; this safeguard does not reinterpret every model mistake.

For ordinary consistent extraction, the guard normalizes positive numeric budget
strings and enforces an unambiguous literal RMB cap from a recognized current
purchase. For example, an extracted 9000 cannot override the user's ¥6,000.
Invalid numeric types/booleans/NaN-like strings become missing budgets and cannot
skip the initial hard-budget check. These checks add protection without changing
the downstream recommendation validator or weakening its rules.

The existing clarification router prevents retrieval/recommendation until fields
are confirmed. The request writer records current clarification state; approved
recommendation anchors remain unchanged. Unrelated/help/unsupported turns still
skip state updates. Original target resolution, cancellation, multi-product
separation, budget-update and follow-up logic remain in place. Retrieval stays
at similarity 0.35 with the original grounding/schema. Public output still has
exactly `answer`, `recommendations`, `next_step`, `clarification_needed`.

The scope safeguard is deliberately bounded. It does not guarantee reconstruction
of every English purchase request, correct arbitrary wrong category/usage
extractions, or infer intent from all device mentions. Correct model extraction
outside its recovery grammar continues through the original routes. When the
reported contradiction recurs, clarification rather than automatic recommendation
is the intended safe behavior.

## Separate recommendation fallback

No local execution trace contains the actual failing `raw_json`, validator
`active_requests` or `validation_error` for the separately reported RMB 6000
turn. The reported request text and a generic Validation Fallback response do
not identify which check failed. The existing validator has distinct identity,
category, price, source, usage, hard-budget and follow-up checks; its false branch
intentionally bypasses the recommendation memory writer.

No particular check is blamed for that live failure, and no validator rule was
relaxed or changed to make it disappear. Offline fixtures demonstrate that a
valid gaming product at the correct price/source passes, and an over-budget
product still reaches fallback with its budget error and unchanged memory.
Those are synthetic regression evidence, not a reconstruction of the live
failure. Any later investigation needs the actual TEST execution's internal
validation error and inputs, after review, without altering Current or adding
internal fields to the public contract.

## Regression results

**254 Python tests and 278 Node tests passed**, with no failures, cancellations
or skips. The 22 additional native-graph tests cover:

- Every currency format on fresh/historical conversations and repeated queries.
- Correct, malformed, empty, variable and contradictory extraction fixtures.
- Reproduction of the old branch and safe clarification under the new guard.
- Multi-product separation, punctuated amounts, budget updates and follow-ups.
- Unrelated/help/unsupported semantics and negative/quoted/incidental mentions.
- Foreign/mixed/invalid currencies, numeric-type rejection and hard-budget caps.
- No retrieval during clarification and no invalid recommendation persistence.

Python contract tests enforce the one permitted graph extension, every original
output ID/global/state/condition binding, the new input reference, original
extraction schema/history/model config, exact guard/rule sources and mutation
rejection. Deterministic/55th-product/stale-output tests remain passing.

Also passed: strict-v1 validation (27 products), TEST validation (54 products),
v1 knowledge consistency, both catalogue consistency commands and whitespace
checks. Nine protected inputs retain their pre-work SHA-256 checksums: stable
workflow, dataset, server, response module, HTML, AIEP page, knowledge file,
Master Dataset and portable Current snapshot.

LLM/retrieval outputs in tests are explicit fixtures; the real generated code,
references, routers and state updates execute offline. Local HTTP regression
tests use loopback and a mocked upstream. No live model classification,
retrieval behavior, import migration, platform JS support or runtime latency
was verified. No new import/save was attempted. Model bindings remain manual
and account-specific IDs remain absent from portable outputs.

## Exact file changes

Modified:

- `tools/sync_catalogue.py`
- `tests/test_catalogue_sync.py`
- `tests/test_workflow_import_contract.py`
- `tests/current-workflow-v21.test.mjs`
- `docs/v21-catalogue-sync.md`
- `docs/v21-current-baseline-rebuild.md`
- `docs/v21-performance-and-local-test.md`

Added:

- `tools/templates/v21_input_normalization.js`
- `tools/templates/v21_scope_consistency.js`
- `tools/templates/v21_extraction_rules.txt`
- `docs/v21-state-extraction-reliability.md`

Regenerated with changed bytes:

- `generated/v2_1_test/mytech-fastgpt-workflow-v2_1-TEST.json`
- `generated/v2_1_test/manifest.json`

The manifest records the normalizer ID and source-template hashes. Generation
and check mode both enforce the full reviewed overlay. Generated frontend,
catalogue JSON and RAG Markdown remain unchanged. Stop for review before any
isolated TEST import; no Git write or deployment is part of this change.
