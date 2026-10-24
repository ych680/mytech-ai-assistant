# v2.1 TEST targeted LLM latency optimization

Phase 2: [separate Prompt A/B exports, import gates, measurement plan and checklist](v21-prompt-ab-validation.md).
The original offline-only results below remain historical evidence, not live A/B results.

Local branch: `feat/v21-automated-catalogue`. This changes only two TEST prompt
strings. No credential file, live API, school settings, Current app, import,
deployment, commit, push or merge was accessed/performed. Keep **glm-4.7** as the
baseline; no model selection/configuration was changed. Portable account model
bindings remain empty for manual TEST configuration.

## Read-only audit

The supplied successful execution reports 36.50 seconds total: State Extraction
11.97, Recommendation Assistant 24.13, Retrieval 0.25. The two LLM stages sum to
36.10 seconds, approximately 98.9% of total. This is one reported execution,
not a controlled before/after benchmark. It has no input/output token counts,
time-to-first-token, cache or provider queue measurements, so it cannot separate
prefill, decoding, reasoning/internal processing and service latency.

The actual local TEST export had 20 nodes / 18 edges:

| Node | Instruction size before | Audited inputs/configuration |
| --- | --- | --- |
| State Extraction `etNrwEXVwr5sySpK` | 11,634 characters, including reliability appendix | Normalized current question; native history=6; unchanged five-field extraction schema |
| Recommendation `pskHz4kajjJnBWwG` | 11,087 characters | Current target requests, same-category comparison anchors, intent; raw question; retrieved quoteQA; native history=6; maxToken=4096; reasoning=false |

Extraction repeated follow-up preservation/scope priority in several sections,
expanded three equivalent examples over many lines, repeated greeting variants,
and restated missing-field and budget-update rules. Recommendation repeated
category/price/usage/source eligibility across grounding, selection, comparison
and output sections; duplicated category lists and full no-result JSON schema;
and repeated English/length constraints.

Neither instruction contains a full product catalogue. The 54-product
PRODUCT_CATALOG belongs to deterministic code validation, not these LLM inputs.
The retrieved product evidence, current requests and historical comparison
anchors are distinct inputs and were retained. Some history may overlap these
inputs, but this export/timing evidence does not prove that it is unnecessary.
Extraction especially needs history because its input does not directly bind
the saved request global. No history or product evidence was removed.

## Implemented scope

- `v21_state_extraction_prompt.txt` consolidates the original state rules and
  examples. The existing `v21_extraction_rules.txt` currency/scope appendix is
  appended **byte-for-byte unchanged**.
- `v21_recommendation_prompt.txt` states each eligibility constraint once, shares
  common comparison constraints, keeps distinct cheaper/more_expensive/alternative
  tests, and uses one JSON example plus the empty-array rule.
- Both request compact JSON/array encoding without changing data or whitespace
  inside string values. Existing answer/reason/next-step length rules remain;
  there are no new word limits or smaller token caps.
- The generator checks the expected original source prompts and exact ordered
  interpolation references before replacing the two strings. Manifest metadata
  records source hashes, exact sizes and the estimation method. Generation and
  read-only consistency checking enforce the same output.

An independent comparison with the pre-work TEST export confirms the only JSON
differences are extraction `description` and recommendation `systemPrompt`.
All 20 node IDs, output IDs, 18 edges, input bindings, five globals, native schemas,
guard/normalizer/query/validator code, routers, state updates, file inputs, model
parameters, history settings and retrieval configuration are unchanged.
Similarity remains 0.35. All three recommendation interpolation occurrences
remain, in the same order:

```text
{{$tWP2LwPvzFadPPtk.school1bTargets$}}
{{$sxwN5Fd17Tc8leTf.school1bHistory$}}
{{$VARIABLE_NODE_ID.fD4C5VOp$}}
```

The user question, RAG quoteQA and comparison state are not trimmed, minified,
duplicated or re-bound by code. Only the model is asked to omit output formatting
whitespace; exact product/source strings remain protected.

## Rule-preservation review

| Original rule group | Location in shorter instructions |
| --- | --- |
| Extraction 1–6, 15–16: history, newest changes, no guessing, separate multiple requests, exact approximate budgets | State and Budget; Completeness |
| Intent mapping and follow-up priority, 7/14/19, three category-specific examples | Follow-up Priority; all intents and example state values retained |
| Scope definitions, 8/10–12/17–18; greetings, capabilities, unrelated/unsupported, mixed greeting/request | Scope; no category substitution or unrelated-task reinterpretation |
| Unsure which device, rule 9 | Scope: supported clarification, relevant history only |
| Required fields, rule 13; structured output/no recommendations/reasoning, rule 20 | Completeness and Output; native extractKeys unchanged |
| Currency normalization, foreign budget protection, repeated-query scope/current-state rules | Existing reliability appendix unchanged; deterministic nodes unchanged |
| Recommendation current targets/unique same-category anchor/no-result relevance | Current Turn State, all references unchanged |
| Retrieved-only facts, no invention, exact identity/category/price/source, supported usage, no live prices | Grounding and Eligibility |
| Hard budgets including approximate wording, no similarity override or category substitution | Eligibility 1–5; reject failing candidates |
| Multiple requests, one product each, best eligible usage/budget match | Multiple Requests; Eligibility selection |
| Cheaper/more-expensive/alternative/none, no-result behavior | Comparisons; strict direction/different-product/current-budget requirements |
| English with exact names/source exception, concise answer/reason/next-step, rejected-product explanations only when asked | Language and Length |
| Four top-level fields, exact recommendation fields, JSON only, false clarification flag | Output; one schema plus empty-array rule |

Every distinct rule remains represented. This review and static regression
anchors do not prove identical probabilistic model behavior after wording changes.
Deterministic identity, source, category, exact price, usage, hard-budget,
comparison and memory checks remain unchanged and still reject unsafe output.

## Size estimates, not speed measurements

No GLM tokenizer is installed locally; none was downloaded. Estimates below use
**ceil(character count / 4)** for English instructions/JSON. The tool also gives
a 3–5 characters/token sensitivity range; it is not a statistical confidence
interval or a bound on actual GLM tokens. UTF-8 byte counts are reported separately.

| Static instructions | Original characters | Optimized characters | Character reduction | Rough tokens before → after |
| --- | ---: | ---: | ---: | ---: |
| State Extraction, including unchanged reliability appendix | 11,634 | 5,615 | 51.7% | 2,909 → 1,404 |
| Recommendation, with reference placeholders | 11,087 | 5,164 | 53.4% | 2,772 → 1,291 |

The corresponding sensitivity ranges are 2,327–3,878 → 1,123–1,872 for extraction
and 2,218–3,696 → 1,033–1,722 for recommendation. Extraction's native extractKeys
serialize to another 1,136 characters (~284 tokens by the same heuristic),
**unchanged**. Counting instructions plus that serialized schema gives roughly
3,193 → 1,688 tokens, still excluding the question, history and runtime wrappers.

The measurement tool renders the three unchanged recommendation placeholders
using explicit Master Dataset fixtures and compact JSON interpolation:

| Rendered recommendation system prompt only | Original characters / rough tokens | Optimized characters / rough tokens |
| --- | ---: | ---: |
| Single gaming Laptop request, no anchor | 11,047 / 2,762 | 5,124 / 1,281 |
| Nine separate category requests, no anchors | 11,529 / 2,883 | 5,606 / 1,402 |
| Targeted cheaper Mouse with exact prior recommendation/source | 11,202 / 2,801 | 5,279 / 1,320 |

These are input-fixture estimates, not complete school API requests: actual
serialization, platform/tool instructions, current-question messages, conversation
history and RAG quotation wrappers/content are not measured here. Their bindings
and limits are unchanged. Actual generated output tokens are unknown. Compact
JSON may avoid formatting tokens, but no output-token saving or speedup was
measured. Do not scale the 36.50-second execution by the character reductions.

Reproduce offline without network or credentials:

```sh
.venv/bin/python -B tools/measure_v21_prompts.py
```

## Verification and risks

**260 Python tests and 279 Node tests passed**, with no failures, skips or
cancellations. Also passed: strict-v1 (27 products), TEST catalogue validation
(54 products), v1 knowledge consistency, both catalogue consistency commands,
deterministic generation/stale-output/55th-product regressions and whitespace
checks. Nine protected inputs retain their pre-work SHA-256 checksums, including
the Master, portable Current snapshot and stable application files.

New tests verify exactly two instruction-value changes, all native input bindings,
interpolation sources/order/occurrences, unchanged reliability appendix and native
extraction schema, history/model/cap preservation, reviewed rule anchors, valid
four-field JSON examples, transparent estimates, source hashes and fail-closed
behavior for empty prompts or reference drift. Native graph fixtures render exact
current multi-request and targeted comparison inputs without leaking another
category's anchor. Existing currency, scope, multi-turn, usage, budget, source,
comparison, memory and frontend tests remain passing.

The baseline-vs-TEST execution test now explicitly compares state/routing/public
output under fixed model fixtures; it does not assert identical recommendation
prompt text. Separate checks cover that intentionally changed text and its
bindings. Offline fixtures cannot test the LLM's semantic equivalence, extraction
reliability, product selection, output brevity or runtime latency. Fewer repeated
instructions can change attention/compliance; shorter text is not automatically
better or faster. No actual performance improvement is claimed.

## Proposed A/B validation after review

Use separate isolated TEST variants with only the two prompt texts differing.
Keep glm-4.7, model parameters, native history settings, 54-product knowledge
version/chunks, similarity 0.35 and all validators identical. Use separate chat
IDs and reset/replay identical histories; alternate variant order and repeat
cases to observe variation. Do not modify Current. No A/B requests/imports were
made during this work.

Compare semantic extraction/state, routing, retrieved grounding and accepted
public results, allowing JSON formatting and concise wording to differ. Cover:

1. Fresh and repeated gaming Laptop requests under all four RMB currency formats;
   historical Study/Gaming state; malformed amounts and explicit USD/JPY/mixed
   currencies. Check clarification/recovery and hard budget exactly.
2. Single and multi-product requests with different budgets/usages, including a
   large batch to detect truncation, mixed constraints and partial no-results.
3. Budget decreases/increases and approximate updates; genuine usage/category
   corrections; preserve other requests and approved anchors.
4. Cheaper, more_expensive and alternative; ambiguous multi-category targets,
   category-only resolution, cancellation, no valid comparison and repeated
   product rejection. Invalid replies must not replace memory.
5. Help/repeated greetings, greeting plus purchase, unsupported/mixed unsupported,
   unrelated tasks, quoted device mentions and unsure-device clarification.
6. Category/usage mismatches, wrong names/prices/sources, over-budget or missing
   evidence, Chinese source context and exact unmodified identity/source strings.
   Require grounded products, English prose and the four-field JSON contract.

Record actual input/output token counts when available, per-node and total
latencies, timeouts, fallback/clarification/error rates and quality violations.
Compare median/p95 over repeated **valid** outcomes while reporting failures
separately; a fast wrong route/fallback is not a speed improvement. Restore the
longer wording if quality or state reliability regresses. Keep performance
conclusions pending measured A/B evidence.

## Exact file changes

Modified: `tools/sync_catalogue.py`, `tests/test_catalogue_sync.py`,
`tests/test_workflow_import_contract.py`, `tests/current-workflow-v21.test.mjs`,
`docs/v21-catalogue-sync.md`, `docs/v21-performance-and-local-test.md`.

Added: `tools/templates/v21_state_extraction_prompt.txt`,
`tools/templates/v21_recommendation_prompt.txt`, `tools/measure_v21_prompts.py`,
`tests/test_prompt_optimization.py`, and this report.

Regenerated with changed bytes:
`generated/v2_1_test/mytech-fastgpt-workflow-v2_1-TEST.json` and
`generated/v2_1_test/manifest.json`. Generated RAG, frontend and catalogue facts
remain unchanged. Stop for review before any isolated import or online testing.
