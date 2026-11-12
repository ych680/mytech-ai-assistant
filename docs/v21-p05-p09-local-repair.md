# P05/P09 local validation repair — 2026-11-12

Baseline: clean `main`, `f619d71f371103b66427dcf5034ebd551fbe5f2a`, origin
`ych680/mytech-ai-assistant`. Local branch: `repair/p05-p09-local-validation`.
No commit, push, merge, deployment, workflow import, or live/paid request was made.

The original presentation assessment remains **12 scenarios: 10 PASS, 2 FAIL
(P05 and P09)**. This report adds offline repair evidence; it does not replace
that historical result or claim a successful live retest.

## Diagnosis and minimum change

| Reproduction | Confirmed cause | Repair |
| --- | --- | --- |
| P05 Turn 1: `I need a laptop.` | `demoMissingFieldClarification()` accepts the answer's budget/usage question, but rejects `Provide your budget and main usage so I can recommend a laptop.` because its complete directive grammar has no purpose-clause production. The usage guard then produces the misleading ownership error. | Accept only the exact category-matched suffix `so I can recommend a laptop` (corresponding noun for other supported categories), after a valid missing-field directive. Existing single-target, missing-field coverage, usage, contract and display checks still run. |
| P05 Turn 2: `My maximum budget is RMB 6000, mainly for study and office work.` | Budget recognition consumes `budget is RMB 6000`, leaving `My maximum  mainly for study and office work` as usage. `testUsageOwnershipIssue()` correctly rejects that malformed local usage. The Node server then rejects the otherwise legitimate Lenovo output against that context. | In `testUsageClause()`, remove `My [maximum]` only immediately before a recognized `budget is …` span, and recognize the leading connector `mainly for`. Preserve the whole remaining usage for the existing policy to validate. |
| P09: `I need a printer under RMB 1000 for home use.` | `USAGE_MATCHERS` recognizes home use, but no supported category exists. Ownership code interprets zero possible targets as ambiguous because its count is not one. | `testUsageOwnershipIssue()` returns no ownership issue when there are no supported active categories. Mixed supported requests and genuine multi-target ambiguity retain their existing checks. |

The server's `validate()` and adapter's `validateCompletionTurn()` need no code
change. The controlled loopback fixture proves that the historical Turn 2 guard
returns **HTTP 502, `{"error":"MODEL_OUTPUT_VALIDATION_FAILED"}`**. Sending that
response through the generated frontend produces the reported **“The AI service
is busy. Try again in a moment.”** The generic message comes from the existing
HTTP-5xx error mapping, rather than evidence of an upstream capacity problem.

The clarification exception still rejects wrong-category purpose clauses,
trailing promises such as “later,” product claims, extra instructions, negation,
unsupported usage, and requests for already supplied fields. It is not a general
prose allowance. Neither usage vocabulary nor recommendation eligibility changed.

## Exact changed-file inventory

- `tools/build_v21_quick_prompt_demo.py`: `render_frontend()` adds three bounded,
  fail-on-drift replacements to the demo overlay. Generated functions affected:
  `testUsageClause()` (its budget masking and leading syntax cleanup) and
  `testUsageOwnershipIssue()` (zero-active-category early return).
- `tools/templates/v21_quick_prompt_demo.js`:
  `demoMissingFieldClarification()` adds the bounded purpose clause.
- `tests/local-v21.test.mjs`: 31 additional regression cases through the existing
  generated Local/AIEP harness, adapter and controlled HTTP server. Includes the
  complete two-turn browser/server path and the historical 502/UI-message path.
- `generated/v21_quick_prompt_demo/local/index.html` and
  `generated/v21_quick_prompt_demo/aiep/site/index.html`: deterministic build output.
- `generated/v21_quick_prompt_demo/local/manifest.json` and
  `generated/v21_quick_prompt_demo/manifest.json`: deterministic output/source hashes.
- This report.

The fingerprinted `tests/quick-prompt-demo.test.mjs` remains unchanged; its entire
164-case suite still runs. New cases live in the existing local validation suite
to preserve the school-export builder's pinned historical test-source hash.

## Offline evidence

| Check | Before repair | After repair |
| --- | --- | --- |
| Exact P05 Turn 1 output, Local and AIEP | Both rejected; no assistant history accepted | Both accepted; zero cards |
| Exact P05 Turn 2 request with canonical Lenovo Xiaoxin 14 fixture, RMB 5799 | Both guards contain malformed usage; completion rejected | Usage is `study and office work`, budget 6000; recommendation displayed |
| Exact P09 request with controlled unsupported-category refusal | Both guards incorrectly require ownership clarification | Both accept refusal; zero cards |
| Current-context P05 HTTP response | 502 | 200 |
| Historical malformed guard retained as a negative fixture | 502 `MODEL_OUTPUT_VALIDATION_FAILED` | Still 502 with the same code and busy-message rendering |

The original targeted baseline run had **7 failures / 7 tests**: the six
Local/AIEP reproductions and the HTTP acceptance case. The HTTP case first
confirmed its explicit historical-502 assertion, then failed expecting 200 for
the browser-produced guard. P05 Turn 1 uses the exact supplied four-field JSON.
P05 Turn 2 uses the exact supplied request and catalogue identity/price, with
controlled answer/reason text because its complete upstream JSON was not supplied.
P09 uses the exact supplied request and a controlled refusal because its exact
upstream prose was not supplied. These are offline fixtures, not new live captures.

Final validation:

| Suite/check | Result |
| --- | --- |
| Complete Node suite | 634 total: 632 passed, 0 failed, 2 skipped (existing private school-export fixtures absent) |
| Local validation + unchanged quick-prompt suites | 205 passed, 0 failed |
| Usage replay against repaired demo | 34 passed, 0 failed |
| Completion replay against repaired demo | 64 passed, 0 failed |
| Quick-prompt Python build suite | 12 passed |
| Completion Python build suite | 10 passed |
| Complete Python suite | 353 total: 347 passed, 0 assertion failures, 3 errors, 3 skipped |
| Deterministic/consistency checks | All 10 passed |
| Frozen preservation fingerprints | All 67 match |
| Repeat demo generation | All 8 output bytes and mtimes unchanged |
| Whitespace check | `git diff --check` passed |

The three Python errors are `WinError 1314` during existing symlink fixture setup:
`test_aiep_v21_build.AiepBuildTests.test_output_symlink_cannot_overwrite_original`,
`test_prompt_ab_preparation.PromptAbPreparationTests.test_symlink_cannot_overwrite_unrelated_file`,
and `test_v21_usage_repair.UsageRepairTests.test_symlink_candidate_is_rejected_without_overwriting_target`.
This Windows account cannot create those symlinks. Tests and security restrictions
were retained. Three other Python symlink tests already skip on this platform.
The full Python suite is therefore **not wholly green**; rerun it on a host with
symlink support. Initial sandbox-only subprocess/temp-access errors were superseded
by the normal-access runs above. Node's Python fixture used `.venv/Scripts` on PATH.

Positive controls retained and passed: P01 multi-product and P02 standard study
recommendation in the quick-prompt suite; P06/P07 cheaper/more-expensive/alternative
comparisons and preserved anchors; P08 genuine Headphones no-match in the completion
replay; P10 help and unrelated requests in that replay; P11 Restart, new chat IDs,
stale-response suppression and state isolation in quick-prompt/local suites.
Negative coverage retains fabricated products, unsupported/negated usage,
ambiguous ownership, hard caps, invalid completion, false no-match, and unsafe
clarification prose; new purpose-clause and mixed printer/device controls also pass.

The ten read-only commands were `validate_products.py --strict-v1`,
`build_knowledge.py --check knowledge/MyTech_Product_Knowledge_v1.md`,
`check_catalogue_consistency.py`, `build_aiep_test.py --check`,
`build_prompt_ab_test.py --check`, `build_glm47_prompt_ab.py --check`,
`check_workflow_registry.py`, `build_v21_usage_repair.py --check`,
`build_v21_completion_repair.py --check`, and `build_v21_quick_prompt_demo.py --check`,
all under `tools/` with the existing Python environment.

## Preservation and remaining acceptance work

No FastGPT workflow, model, prompt, catalogue, recommendation/usage policy,
grounding safeguard, fallback, public four-field JSON contract, server restriction,
CSS, or Editorial Clean design was changed. All workflow/catalogue/knowledge
copies retain their baseline bytes. No `.env` contents or credentials were read
or displayed. Test transport targets `.invalid` and is always injected/mocked.
Assessment/evaluation artifacts were not edited.

Four initially CRLF checkout files (`MyTech_Chatbot_v2.html`, `mytech_response.mjs`,
`mytech_v2_server.mjs`, `workflow/README.md`) prevented the strict frozen-byte build.
Their LF-normalized bytes matched both Git HEAD and the frozen fingerprints.
They were restored to those exact repository LF bytes, as `.gitattributes`
requires; there is no Git content diff for them. No preservation hash was relaxed.

After separate live-retest authorization, run the existing demo launcher with the
approved TEST binding using the project's established environment procedure.
Use Restart before each independent scenario. Submit the exact P05 Turn 1 then
Turn 2 above; expect a clarification followed by a grounded, within-RMB-6000
study/office recommendation, without local validation or busy errors. Inspect the
loopback HTTP status without recording credential headers. Restart, submit the
exact printer request, and expect an unsupported-category refusal with zero cards.
Then repeat P01/P02, P06/P07, P08, P10 and P11, including mixed/ambiguous requests,
negated/unsupported qualifiers and a budget below an otherwise eligible product.
Preserve the original assessment and append the dated live retest separately.

Live extraction, retrieval grounding, FastGPT memory, native browser layout and
the variety of future model wording remain unverified by these offline tests.
The bounded grammar intentionally fails closed on unrecognized prose. This repair
updates only the Quick Prompt Demo package used by `start-mytech-demo.mjs`; frozen
historical packages retain their original behavior. Stop here pending approval
for any commit, push, merge or deployment.
