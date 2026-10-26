# Phase 3B — empty recommendation completion repair

Prepared offline on 2026-10-27 (Asia/Hong_Kong), for independent pre-commit review.

This report includes the three corrections authorized after the first independent
review returned REVIEW. The approved 20-path inventory and four changed workflow
locations are retained. No prompt, model, public-contract or graph scope expansion
was needed. The changes are ready for another independent read-only review;
this is not a claim that the live school-demo cause has been established.

## Base and authorization

Local clean `main` and remote `refs/heads/main` were both verified at
`860b744a9d9f956a7dfa296dea5843fdb3385c38`. The requested remote repair branch
did not exist. Work is on `fix/v21-empty-recommendation-completion`, with HEAD
still at that base. Nothing is staged, committed, pushed, imported or deployed.
No private environment file or credential was read. Providers in tests are
in-memory mocks; loopback servers do not call paid services.

The new package derives from the **committed PR #17 repair**, whose workflow
SHA-256 is `e41498899c13434c68ee3de9691cfd9d705ecc81ba4629ba5c241d622bae551c`.
It is not derived afresh from the older Original validator. Generation checks
that fingerprint and the reproducibility of the entire PR17 package first.

## Behavior and exact workflow changes

`tools/templates/v21_completion_validation.js` replaces the candidate's old
partial-only helper. Every complete current request must have either a valid
returned item or a catalogue-verified negative result. This also applies when the
whole array is empty. Catalogue facts are used to reject unsupported omissions
and construct truthful negative-result wording; they are never turned into
synthesized recommendations.

The first review exposed three causes and their corrections:

1. Comparison explanations required a single literal intent word. Eligibility
   still uses the actual intent, validated anchor, hard budget and complete usage;
   the explanation now accepts equivalent wording such as lower-priced, higher-
   priced, less expensive, more affordable and other. A generic explicit negative
   statement is also sufficient when comparison eligibility is independently
   verified. The output always names the actual comparison and anchor.
2. Retained purchase targets were applied to a capability question missing from
   the control recognizer. Fully matched generic capability-question grammar now
   includes `What products can you recommend?` and `Can you help me?`, independently
   of prior state. A budget, usage qualifier, specific shopping category or added
   purchase clause prevents that help match. Native help is displayed unchanged
   and does not erase anchors. The existing bounded non-help controls are retained.
3. Same-clause keyword matching could attach one category's negation to another,
   accept negated claims, and preserve wrong budgets or future promises. Each
   omitted category now needs its own direct negative subject/object statement.
   Acknowledgements, missing-category explanations, negated preambles and explicit
   deferred promises fail. After independent eligibility verification, all answer
   and next-step prose on accepted empty/partial no-match turns is replaced with
   canonical wording from the real request, usage, cap, intent and approved anchor.
   Thus a model claim about RMB 1200 for an actual RMB 800 request is safely
   normalized to RMB 800, rather than being labelled as verified model prose.

The canonicalizer retains the exact validated recommendation objects, including
their reasons, prices and sources. A partial result has a neutral introduction
and one verified negative statement per omitted category. Its next step asks
whether the user wants to change requirements and promises no future result.
No-match normalization reaches the native final-response branch, both candidate
frontends, their assistant history and the candidate local server's wire response.
PR17's old empty-comparison rewrite is removed only from the new validator code;
it cannot overwrite the canonical result with an unproved claim about retrieval.

Comparison eligibility requires exactly one current target and one approved,
same-category historical product with its exact reference price. Candidates
must satisfy current category, independent hard budget and complete usage:

- `cheaper`: different product and strictly lower reference price.
- `more_expensive`: different product and strictly higher price, still within
  the current cap.
- `alternative`: a different identity; the existing anchor alone is not an
  available alternative.

A genuine no-match can therefore pass even when the catalogue still contains
the previously recommended product. Comparisons with absent, duplicate, forged
or cross-category anchors fail. Valid partial results still require an explicit
negative statement for each omitted category, then receive a verified canonical
explanation. Any unsafe returned item rejects
the whole batch. The existing usage parser, qualitative Laptop/Gaming allowance,
product facts, contract checks and comparison memory rules remain in force.

The separate workflow keeps 20 nodes, 18 edges, all prior IDs, global state and
memory/router references. Only these fields differ from PR17:

| Field | Change |
| --- | --- |
| `/nodes/11/inputs/2/value` — `fakNM8mmlYmewx67` code | Shared completion policy; canonical no-match output; completion diagnostic; truthful failure object |
| `/nodes/11/inputs/7` | New optional `retrieved_evidence`, native `datasetQuote` reference to `zWAw4oYVL1QMe8YX.quoteQA` |
| `/nodes/11/outputs/11` | Internal string `completion_status`, ID `phase3CompletionStatus` |
| `/nodes/14/inputs/0/value` — `zh9L8VeY9vKm3WnU` text | Same truthful four-field failure object as the validator |

All previous inputs and outputs retain their definitions. The published public
contract still contains exactly `answer`, `recommendations`, `next_step` and
`clarification_needed`. Internal diagnostics are not added to that JSON.

The failure response is:

```json
{
  "answer": "I couldn't complete a verified recommendation for this request. No product was accepted.",
  "recommendations": [],
  "next_step": "Please try again; your current requirements have not been changed.",
  "clarification_needed": false
}
```

The existing validation router takes its failure branch, skips the recommendation
writer, and preserves all prior approved anchors. This response does not claim
that the budget caused failure or ask the user to repeat already known facts.
Native missing-field clarification and cancellation branches are unchanged.

**Recommendation prompt/model changes: none.** No prompt change is proposed as
part of this repair. Model bindings, history, token limits, RAG configuration,
extraction, scope routing and conversation-control code are preserved.

## Retrieval evidence and uncertainty

Completion diagnostics distinguish:

| Internal status | Interpretation |
| --- | --- |
| `completed_grounding_unverified` | All returned items pass catalogue checks, but at least one has no recognized complete record in the bound evidence; output remains accepted |
| `completed_with_recognized_evidence` | All returned items pass catalogue checks and complete matching records are recognizable in bound evidence; this is not proof of model use |
| `verified_catalogue_no_match` | Every omitted request has no eligible catalogue item, including comparison constraints; canonical output expresses that verified result |
| `retrieval_evidence_empty` | An eligible request was omitted and the bound array is empty; the cause of that emptiness is unknown |
| `retrieval_evidence_unverified` | An eligible request was omitted and no complete eligible record is recognized in the supplied evidence shape |
| `incomplete_model_execution` | An eligible full record is recognizable in bound evidence but omitted, or a no-match/deferral explanation is incomplete |
| `incomplete_or_evidence_uncertain` | An eligible request was omitted and retrieval evidence is unavailable to the checking layer |
| `invalid_completion_context` / `invalid_comparison_anchor` | Eligibility cannot safely be established |
| `not_evaluated` | An existing contract/item safeguard rejected the response before completion checking |

The candidate receives the search node's `quoteQA` output through the existing
AI Chat #2 `quoteQA` reference and the new optional validator `datasetQuote`
reference. The full offline graph test resolves both native bindings to the same
fixture value. This proves the exported references, not live FastGPT import or
runtime delivery. The exported KB selection is still empty and unverified.
The fixtures are explicitly synthetic; none is represented as a captured live
retrieval response.

The evidence recognizer accepts exact structured catalogue records or a single
RAG Markdown record in `a`/`content` with unique category, identity, price, source
and the complete contiguous usage list. It does not combine separate chunks or
conflicting records. Unknown formats, altered facts and truncated records never
establish that the model had sufficient evidence. Recognition affects diagnostics
only; it never permits an otherwise invalid output or creates product cards.

Successful recommendations still pass when evidence is absent, empty, null or an
unknown shape, provided all existing catalogue/item safeguards pass. Their status
now states that grounding is unverified. No strict retrieval gate was introduced.
An empty array cannot distinguish an actual zero-hit search from an unconfigured
dataset, omitted/unavailable binding, error fallback or other runtime condition.
Undefined indicates an unavailable value at this checking layer, not its cause.
Unknown shapes may contain useful evidence in fields the recognizer does not
understand; facts may also be split between question/answer fields or chunks.
No production evidence schema, provenance or model-context rendering is proved
by this repository. Recognizing complete facts does not prove the model used
them or that they survived prompt construction/truncation.

The Node adapter and browsers usually receive final content without the RAG
trace. They conservatively report uncertainty for an eligible omission. They
cannot infer the precise live cause from the four-field JSON alone. Even the
workflow diagnostic is not proof of the final rendered model context or provider
truncation; those still require logs.

Candidate frontend checks run only in the new generated pages. Existing guard
constraints determine recommendation versus clarification/comparison/cancellation
handling. Bounded greeting, capability, unrelated and unsupported-message forms
preserve non-recommendation behavior after earlier complete requests. They are
not a universal natural-language scope classifier. Unknown forms can fail safely;
native FastGPT scope routing remains unchanged. A greeting combined with a
purchase cannot authorize an empty acknowledgement as completion.

`mytech_v2_1_test_server.mjs` enables the extra gate only when the selected local
manifest has `completion_validation: true`. Thus its prior empty-result shortcut
cannot bypass completion for this package. It uses server-held validated anchors
and recomputes the bounded message-control flag, rather than trusting a browser's
claim to bypass checks. Default and PR17 package behavior remain unchanged.

A separate future grounding implementation should first capture a redacted,
versioned live `datasetQuote` contract with execution success, configured
dataset/collection identity and complete returned records. A deterministic
adapter could then normalize and link evidence to exact catalogue identities,
prices, sources and requested usage. Verify how that evidence is rendered into
the model context and how errors/empty searches are represented. Start with
diagnostics and fixture tests against real redacted shapes; enable a strict gate
only after that contract and failure handling receive separate review. Do not
ask an LLM to generate an evidence envelope, infer a successful retrieval from
an empty array, or reject every unrecognized shape as definitively ungrounded.

## File inventory

Six existing files change:

- `.github/workflows/ci.yml`: read-only candidate check and PR17 regression replay.
- `mytech_v2_1_test_adapter.mjs`: candidate-specific turn validation using the
  embedded policy and compatibility map; prior workflow selection stays default.
- `mytech_v2_1_test_server.mjs`: candidate-manifest opt-in before the empty shortcut.
  Phase 3B also returns the candidate's accepted canonical output on the wire;
  default/PR17 output remains unchanged.
- `tests/helpers/v21-repair-frontend.mjs`: optional package selection.
- `tests/usage-repair.test.mjs`: allow replay against either reviewed package,
  without changing the original assertions or default package.
- `generated/v21_multiproduct_usage_fix/manifest.json`: only two source
  fingerprints for the adapter/server refresh; old output hashes do not change.

Six non-generated files are added:

- `tools/build_v21_completion_repair.py`
- `tools/templates/v21_completion_validation.js`
- `tests/completion-repair.test.mjs`
- `tests/test_v21_completion_repair.py`
- `tests/fixtures/v21_completion_preservation.json`
- `docs/v21-empty-recommendation-completion-repair.md`

Eight files are added under `generated/v21_completion_fix/`:

- `workflow-completion-repair.json`
- `manifest.json`
- `local/mytech-fastgpt-workflow-v2_1-TEST.json`
- `local/index.html`
- `local/catalogue.json`
- `local/MyTech_Product_Knowledge_v2_1_TEST.md`
- `local/manifest.json`
- `aiep/site/index.html`

Total: **20 paths**, comprising 6 modified and 14 new files. Existing published
HTML is not overwritten. The separate AIEP page is a review artifact only.

## Regression and verification evidence

Final local results:

| Check | Result |
| --- | --- |
| Complete Python unittest suite | 328 passed; zero failures/errors/skips |
| Complete Node.js suite | 428 passed; zero failures/skips |
| Additional PR17 suite replay against Phase 3 | 34 passed; zero failures/skips |
| Completion-specific tests within those totals | 64 Node tests, including 34 Phase 3B cases; 10 Python tests |
| Existing protected file SHA-256 checks | 49 unchanged baseline files |
| Consistency commands below | All passed |
| Repeated generation / read-only `--check` | Deterministic; unchanged bytes and mtimes on repeat; stale checks do not repair files |
| Whitespace / public credential scan / staged diff | Clean; no credentials found in changed public artifacts; index empty |

New regression coverage includes the exact school-demo JSON; LAP-005 at RMB 4999
under all four RMB/¥6000 formats; false and genuine catalogue no-match; fully
empty and partially omitted multi-product results; every category explained;
all three valid comparison no-result cases; false comparison no-match with an
eligible Mouse; bad anchors; absent/empty/irrelevant/truncated/complete retrieval;
split and conflicting evidence; fabricated products; whole-batch rejection;
native final response/router/writer behavior; prior-anchor preservation; help,
unsupported requests, clarification, cancellation, greeting plus purchase,
Restart; and mocked local-server rejection/recovery.

The unchanged PR17 tests additionally exercise composite usage, multi-turn
corrections, shared usages, independent budgets, exact facts, ambiguous ownership,
transport continuity, comparisons and Restart against the new package. All four
checking layers are covered: candidate validator/final branches, Node adapter,
local frontend and AIEP frontend.

The 34 Phase 3B cases cover nine comparison wording variants, false comparison
claims for each intent, genuine native help before purchases and after single-
and multi-product purchases, five help-shaped shopping messages, canonical
wrong-budget/wrong-usage/availability normalization, cross-category and negated
claims, deferred next steps, canonical partial results and idempotence, five
grounding diagnostic boundaries, and full candidate-native graph traversal.
The local HTTP test also verifies that normalized no-match text reaches the
wire response rather than only an internal validator result. Both frontends'
displayed responses and stored assistant history are checked. All original
Phase 3 and PR17 assertions remain in place; only renamed diagnostic expectations
are updated.

Commands used (the local `--offline` option prevents dependency downloads):

```sh
uv run --locked --offline python -B -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/*.test.mjs
MYTECH_REPAIR_PACKAGE=v21_completion_fix node --test tests/usage-repair.test.mjs
python3 -B tools/validate_products.py --strict-v1
python3 -B tools/build_knowledge.py --check knowledge/MyTech_Product_Knowledge_v1.md
python3 -B tools/check_catalogue_consistency.py
python3 -B tools/sync_catalogue.py --check
python3 -B tools/build_aiep_test.py --check
python3 -B tools/build_prompt_ab_test.py --check
python3 -B tools/build_glm47_prompt_ab.py --check
python3 -B tools/check_workflow_registry.py
python3 -B tools/build_v21_usage_repair.py --check
python3 -B tools/build_v21_completion_repair.py --check
git diff --check
```

Loops use mock providers only. Test environment-file checks use the public
`.env.example` and temporary synthetic files, not the private IDE-open `.env`.
Candidate builders scan public outputs for credential patterns and populated
sensitive JSON fields. Source/output symlinks and unexpected package files fail
closed. The fixture hashes protect the Original and Optimized snapshots, Master
prices, legacy v2 and all existing generated workflow/HTML assets. New catalogue
and knowledge copies are byte-identical to the prior versions; CSS, embedded
dataset and card-rendering function are also unchanged.

## Review readiness and remaining limits

Ready for an independent **pre-commit review**, not for live promotion. The
repair contains the false-success path without adding retries or making the
system generate an omitted recommendation. Safe rejection may therefore replace
an acknowledgement when retrieval/model execution is still incomplete.

Negative-intent recognition remains bounded and may reject unusual honest
wording. Accepted no-match prose is generated only from verified current-request
eligibility; arbitrary model prose is not certified as true. Evidence recognition
deliberately errs toward unverified evidence and does not enforce grounding.
Windows path simulation passes; actual hosted
Windows/Ubuntu/macOS CI has not run because nothing has been pushed. Native
FastGPT import and account-specific `datasetQuote` runtime compatibility are
unverified. The original export still omits active KB selection and published
revision; this package does not change either.

The exact live trigger on October 24 at approximately 16:47 HKT still needs:
the application/published revision and execution IDs; exact input/history and
saved state; extraction outputs/defaults/errors; guard outputs and executed
branches; retrieval query, actual KB/collection IDs, chunks/scores and `quoteQA`;
rendered recommendation prompt, raw answer and finish reason; Code Run #2 inputs
and diagnostics; and exact FastGPT/AIEP final payloads. No log claim has been
substituted for this missing evidence.

Review should focus on comparison eligibility, the conservative treatment of
retrieval uncertainty, and preservation of controls/anchors. Prompts, models,
KBs and deployments remain outside this change. Stop here before staging or
committing.
