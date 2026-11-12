# Structural clarification reliability repair — 2026-11-12

Continued on `repair/p05-live-retest-follow-up`, HEAD
`3f4afc2ba0be85be4690f115e92d049fd8e7847b`. The starting tree contained the
previous five modified files and four new files, all uncommitted. Those repairs,
their tests, and their evidence reports were preserved. No commit, push, merge,
deployment, school application change, or live/paid API request was made.

## Historical evidence and root cause

All three reported P05 live retests on 2026-11-12 remain **FAIL** in the evidence
record. The original presentation assessment remains **12 scenarios: 10 PASS,
2 FAIL (P05 and P09)**. The earlier live failures and offline outcomes remain
unchanged in [the budget-prefix report](v21-p05-live-retest-follow-up.md) and
[the contraction report](v21-p05-contraction-follow-up.md). Exact public JSON for
all three retests is preserved in
[`p05_live_clarifications_2026_11_12.json`](../tests/fixtures/p05_live_clarifications_2026_11_12.json).
Only the second retest has a supplied time: 18:49 Asia/Hong_Kong.

The latest reported response to `I need a laptop.` was:

```json
{
  "answer": "What is your budget for the laptop?",
  "recommendations": [],
  "next_step": "Please also share your main usage so I can refine the recommendation.",
  "clarification_needed": true
}
```

FastGPT correctly identified Laptop, with `budget` and `main_usage` missing.
The frontend displayed the usage-ownership error. Its local context actually
had one target and no ownership ambiguity; missing usage also raises the generic
usage-clarification flag. The restrictive complete-clause grammar recognized
the budget question but not the next-step directive. That gate selected the
misleading ownership error. Previous repairs addressed other grammar spellings;
they could not make unrestricted natural-language clarification reliable.

At the start of this investigation, the real local listener on port 8788 returned
HTTP 200, `Cache-Control: no-store`, and Local HTML SHA-256
`8452533fdbd6fc01f243e48e25c53bc82a951a07f7bc6a9dd8e6f6f245a47d43`.
It exactly matched the previous repaired generated file and manifest. The builder
check also passed. Thus the latest failure reproduced with the current assets;
it did not require a stale server or browser cache.

The six baseline Local/AIEP fixture cases produced **4 passes, 2 failures**:
the first two reported wordings passed in both frontends after the earlier
repairs; the newest wording failed in both and produced the exact ownership
error. This is offline evidence, not a revision of any historical live verdict.

## Architecture reviewed and design

The frontend updates local requirements from user input before requesting the
model. The shared usage parser preserves unsupported qualifiers and negation.
Its local guard provides active/target categories, budgets, usage, ownership,
comparison/control flags, and recommendation anchors. This verified context,
rather than model prose, supplies the deterministic missing-field decision.

The Node server checks the public contract, catalogue identity, prices, sources,
hard budgets, and the completion/usage validator. Its completion policy permits
empty, clarification-marked responses for incomplete requests. It keeps only
validated product anchors, and empty responses do not erase them. It forwards
only the current user message with the existing FastGPT chat ID. The frontend's
`modelHistory` is a local record; it is not forwarded as a model prompt.

The repair adds a separate **deterministic clarification fallback** without
extending the model-prose grammar:

1. The existing strictly recognized and fully validated model-response path is
   preserved, including original validated history and recommendation handling.
2. When the incomplete-request gate rejects model prose, a fallback is considered
   only for exactly the four public fields, correct field types, a nonempty
   answer, `clarification_needed: true`, and empty recommendations. Raw and
   citation-cleaned versions must pass the existing response/security validator.
   Oversized text and control characters also prevent fallback.
3. Eligibility requires exactly one supported active category and the same sole
   target; no ownership ambiguity, comparison, cancellation, control/reset,
   pending comparison, or ambiguous "better" request; and at most one recognized
   budget in the current message. Guard categories, requirements, and anchors
   must agree with the current local state. Present budgets must be positive
   safe integers; present usage must pass the unchanged category usage policy.
   Malformed/unsupported request wording is not converted into a missing field.
4. At least one required field must genuinely be absent. Only that local absence
   determines `budget` and/or `main_usage`. Model text contributes no category,
   field name, budget, usage, price, or recommendation to the fallback.
5. Fixed text is constructed and checked with the existing output validator.
   For both missing Laptop fields the question is exactly:

   > For Laptop, please tell me your maximum budget in RMB and what you will mainly use it for.

   Budget-only and usage-only questions omit the already supplied information.
6. The normal text bubble displays **Local clarification** and **The model
   response was not accepted.** before the fixed question. The existing edit
   recovery action remains available. No CSS or card design changes were made.

Internal `demoResponseOutcome` distinguishes `accepted_model`,
`deterministic_clarification`, and `rejected`. A fallback records
`modelAccepted: false` plus only the locally derived category, missing fields,
and safe output. Timing uses `clarification_fallback`. None of this metadata is
added to the public JSON contract or sent upstream.

The rejected original prose is never rendered, inserted into validated
`modelHistory`, saved as an anchor, or copied into fallback metadata. The safe
fallback also is not represented as a validated model-history turn. Existing
user requirements and FastGPT chat ID remain unchanged. The next user reply
therefore uses the same conversation and completes the local requirements;
its recommendation must pass every existing validator. Restart clears fallback
provenance and requirements, rotates the chat ID, and suppresses late responses.

## Security impact

Wrong-category text, fabricated product/price prose, false no-match claims,
promises, contradictory prose, and additional instructions remain **unaccepted
model responses**. In an otherwise eligible incomplete request, their text may
be discarded in favor of the same fixed local question. This does not validate
their claims. New tests explicitly check the negative acceptance flag, absence
of original prose from UI/history/metadata, unchanged chat/requirements, and no
cards or anchors. A complete request's false no-match still fails validation.

Nonempty recommendations, malformed contracts, unsupported live claims (also
after citation cleanup), invalid request budgets/usages, mixed unsupported
requests, ambiguous/multiple active targets, forged state, and control/comparison
contexts cannot enable the fallback. Unsupported-category refusals keep their
existing path and cannot authorize supported product cards. Recommendation and
comparison validation, catalogue grounding, and product eligibility are unchanged.

**No existing negative test expectation was changed, retargeted, or disabled.**
All historical tests remain byte-identical. The new assertions strengthen the
distinction between rejecting original model content and displaying a safe local
question. The UI is not claiming that rejected prose was validated.

## Exact incremental changed files

1. `tools/templates/v21_quick_prompt_demo.js`: local eligibility, fixed-question
   construction, and outcome state; no new model-prose grammar alternatives.
2. `tools/build_v21_quick_prompt_demo.py`: bounded, fail-on-drift insertion into
   the incomplete-request rejection path, accepted/rejected/fallback provenance,
   fallback text rendering, timing, and Restart cleanup.
3. `generated/v21_quick_prompt_demo/local/index.html`: deterministic build output.
4. `generated/v21_quick_prompt_demo/aiep/site/index.html`: deterministic build output.
5. `generated/v21_quick_prompt_demo/local/manifest.json`: regenerated output hash.
6. `generated/v21_quick_prompt_demo/manifest.json`: regenerated source/output hashes.
7. `tests/fixtures/p05_live_clarifications_2026_11_12.json`: exact historical fixtures.
8. `tests/structural-clarification.test.mjs`: 137 new offline regressions.
9. This new report.

Generated HTML was written only by the deterministic builder. The Node server,
adapter, completion validator, 54-product catalogue, workflows, prompts,
knowledge, recommendation policy, CSS, and public JSON structure were not edited.

## Verification results

macOS, Node `v24.21.0`, Python `3.12.15`:

| Check | Result |
| --- | --- |
| Exact historical fixtures before this repair | 4 passed, 2 failed |
| All three historical fixtures afterward, Local and AIEP | 6 passed: 4 accepted-model responses, 2 deterministic fallbacks |
| New structural suite | 137 passed, 0 failed |
| Complete Node suite | **1018 total: 1016 passed, 0 failed, 2 existing skips** |
| Complete Python suite | **353 passed, 0 failures/errors/skips** |
| Usage replay against regenerated demo | 34 passed |
| Completion replay against regenerated demo | 64 passed |
| Read-only consistency checks | 10/10 passed |
| Frozen preservation fingerprints | 67/67 unchanged |
| Historical workflow/catalogue/knowledge/evaluation/document files | 47/47 byte-identical to `3f4afc2` |
| Previous P05 suites and evidence reports | All 247 tests and both reports unchanged |
| Repeat deterministic generation | All 8 output bytes and mtimes unchanged |
| Exact-diff and whitespace checks | Passed |

The existing private school candidate suites account for the two Node skips.
All model providers in automated tests were injected `.invalid` fixtures. Node
tests used loopback permission. No real credentials or live API were used.
The full-suite, replay, and ten consistency commands are the same ones recorded
in the earlier reports. The new suite is included in `tests/*.test.mjs`.

New cases cover all nine supported categories; budget-only, usage-only and both
missing; unsafe and misleading prose disposal; strict contract/security failures;
invalid/contradictory/unsupported requests; forged guard state; the same-ID
two-turn grounded Laptop recommendation; Restart and stale-response suppression.
A real loopback launcher test verifies the served HTML and manifest hash,
`no-store`, and the complete fallback-to-recommendation HTTP path. Prior P01/P02
starters, P06/P07 comparisons and anchors, P08 Headphones no-match, P10 help and
unrelated turns, and P11 Restart/isolation remain covered by passing unchanged
quick-prompt, completion, usage, and local suites.

Final Local HTML SHA-256 is
`d53a64cc85072eef490e131b1db65dc249fbc63741548a29d5271a61a2ea7cb5`;
AIEP HTML is
`cc9e57c88f628e4567229edd760c592592242e40b74ebadcbc6225ca8aa7c549`.

## Remaining live checks and stopping point

The pre-existing process on port 8788 was left running. A final read-only GET
confirmed that it still serves the old `8452533f…` HTML because assets are loaded
into memory at startup. A fresh offline fixture process served the new `d53a64cc…`
HTML correctly and was closed after testing. **Restart the existing local demo
server and reload the page before the next live retest.**

Using the established TEST binding procedure, stop the old demo in its terminal
and relaunch `start-mytech-demo.mjs` with the same explicitly selected approved
environment file. Reload `http://127.0.0.1:8788/`, confirm the served hash above,
then use Restart before each independent scenario:

1. Submit `I need a laptop.`. A valid bounded model question may display normally;
   unfamiliar wording with an eligible envelope should display the labeled local
   question for budget and usage, with zero cards and no ownership error.
2. Reply `My maximum budget is RMB 6000, mainly for study and office work.`.
   Expect a catalogue-grounded, within-budget recommendation on the same chat ID.
   A local fallback must not have been inserted as validated model history.
3. Repeat budget-only/usage-only requests, unsupported and ambiguous requests,
   P01/P02/P06/P07/P08/P10/P11, and Restart/state-isolation checks. Append the live
   outcomes separately; do not revise the three historical failures.

Live extraction, retrieval grounding, school-side chat memory, additional model
wording, and native browser layout still need observation. This repair controls
local display/history only; it does not rewrite FastGPT's own remote history.
Safety failures outside the eligible envelope/context still reject the turn.
No live success, statistical reliability, or production readiness is claimed.
Work stops after local verification, with all changes uncommitted.
