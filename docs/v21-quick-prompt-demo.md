# MyTech v2.1 Phase 4B/4C — offline Quick Prompt Demo candidate

Prepared on 2026-10-27, Asia/Hong_Kong, for independent pre-commit review.

Phase 4C corrects the unsafe clarification exception reproduced by the independent
Phase 4B review. The correction remains inside the existing 20-path inventory.

The new candidate adds four concise starters, validated contextual comparisons,
and optional classroom examples. It also preserves a native missing-information
question that PR18's frontend previously masked with a usage-ownership error.
This is an offline frontend candidate, not a deployment or evidence of live RAG
success.

## Verified base and scope

Before creating `feat/v21-quick-prompt-demo`, local `main`, `origin/main`, and
GitHub's `refs/heads/main` all matched
`e50dbfe025f102644355ec7d0d1ff38370af19e7`. The working tree and index were clean.
The branch retains that HEAD. No staging, commits, pushes, pull requests, imports,
publication, or deployed application changes are part of this work.

No private environment file or credential was read. Providers in tests are
in-memory fixtures; server tests use loopback HTTP. The initial sandboxed Node
suite could not bind loopback (`listen EPERM`); the complete suite passed with
loopback permission. No paid requests were made.

## Source of truth and generated mapping

The original chain is preserved:

`aiep-candidate/site/index.html` → catalogue/AIEP builders → PR17 usage repair →
PR18 completion repair → **new Quick Prompt Demo overlay**.

`tools/build_v21_quick_prompt_demo.py` first verifies the 67 protected baseline
fingerprints, renders PR18 in memory, and checks that its committed package is
current. It derives both new frontends from those checked bytes. A changed
baseline or stale parent fails closed. Earlier generators and release packages
are not edited. Generation never makes requests.

| Authoritative input | Result in `generated/v21_quick_prompt_demo/` |
| --- | --- |
| `tools/templates/v21_quick_prompt_demo.json` | Exact primary labels/payload attributes and optional example/action definitions in both HTML files |
| `tools/templates/v21_quick_prompt_demo.js` | Shared follow-up lifecycle, examples and narrow clarification-display helper in both HTML files |
| `tools/templates/v21_quick_prompt_demo.css` | Separate scoped style block in both HTML files; previous style blocks remain exact |
| `tools/build_v21_quick_prompt_demo.py` | Deterministic HTML overlay and source/output manifests |
| Checked PR18 `workflow-completion-repair.json` | Byte-identical root workflow and local workflow copies |
| Checked PR18 catalogue and knowledge | Byte-identical local copies |
| `tests/fixtures/v21_quick_prompt_demo_preservation.json` | Frozen baseline verification and manifest source fingerprint |

Run the builder to regenerate; never manually edit generated HTML. The local
manifest retains `completion_validation: true` for the existing TEST server's
strict PR18 adapter path. The default server directory and all default launches
remain unchanged; the new package requires an explicit candidate directory.

## User-visible behavior

Exactly four primary buttons use the existing `sendMessage()` path:

| Label | Exact submission |
| --- | --- |
| Gaming Setup ×2 | `I need a laptop under ¥6,000 for gaming and a mouse under ¥300 for gaming.` |
| Study Laptop | `I need a laptop under ¥7,000 for study and office work.` |
| ANC Headphones | `I need headphones under ¥1,200 for music, commuting, and noise cancellation.` |
| Gaming Smartphone | `I need a smartphone under ¥3,000 for gaming.` |

The unchanged TEST usage policy and hard caps admit these catalogue candidates:

- Gaming setup: LAP-005 at 4999; MOU-002 at 229 or MOU-004 at 109.
- Study/Office Laptop: LAP-001 at 5799, LAP-002 at 6599 or LAP-004 at 3299.
- Music/commuting/noise-cancellation Headphones: AUD-005 at 1009.
- Gaming Smartphone: PHO-005 at 1999 or PHO-006 at 2599.

These are catalogue eligibility findings at reference prices, not retrieval or
availability guarantees. The catalogue still contains 54 TEST products and its
provisional research status is unchanged.

After a non-empty validated result, a separate scrolling follow-up region shows
the selected category/product and saved maximum budget. A single result uses its
actual category. Multiple results require a labeled selector, initially empty;
actions stay disabled until a category is chosen. Options contain only valid
categories returned in the latest response, including for partial results.

The three actions submit only bounded category-qualified messages, for example:

- `Can you recommend a cheaper laptop?`
- `Can you recommend a more expensive laptop?`
- `Can you recommend another laptop?`

They add no budget, product identity, usage text or extra instructions. Existing
validation enforces lower price, higher price within the unchanged hard cap, or
a different qualifying product respectively. The existing FastGPT chat ID and
category-specific requirements persist. A missing alternative is an honest
comparison no-match, not a reason to synthesize a recommendation or raise a cap.

The UI stores an immutable copy of the accepted categories, products, prices,
budgets and complete usage strings, tied to the request version and chat ID.
It also checks that current requirements and validated anchors still match.
Retained old anchors alone cannot enable actions. Visibility and selection never
submit requests. Actions disable during generation or any composer draft,
including whitespace; handlers independently check those conditions.

A valid new submission removes previous controls. Help, clarification, no-match,
invalid output, timeout and transport failure leave them hidden. Validated
anchors retain their established memory behavior. Restart clears the selection
and UI, rotates the ID, and prevents old controls or delayed success/failure from
changing the new conversation. Tests also cover a stale result arriving after a
new success and during a newer pending turn.

The collapsed native **More Examples** disclosure sits inside the scrolling
conversation, outside the fixed-height composer. Expanding/collapsing sends
nothing. Its optional buttons submit:

- Clarification: `I need a laptop.`
- Honest No-Match: `I need headphones under ¥800 for music, commuting, and noise cancellation.`

The visible note identifies Clarification as a fresh-conversation example and
asks the presenter to use Restart first if Laptop requirements already exist.
Clicking an example never silently restarts. At 800, no Headphones satisfy all
three usages; AUD-005 costs 1009. The Gaming Laptop and ANC starters each have
only one qualifying product, so comparisons can legitimately have no result.
Study Laptop, Mouse and Smartphone provide more comparison opportunities.

## Phase 4C — bounded clarification correction

The independent review returned REVIEW: the former exception found interrogative
words anywhere in the response and required only some clauses to mention the
missing fields. Thus an embedded “what” in a declaration could pass. A valid
question also allowed unrelated unsafe clauses through. The unchanged PR18
checker treats an incomplete empty clarification as a non-recommendation turn,
so it cannot supply the missing prose check.

For `I need a laptop.`, both candidates formerly accepted these exact pairs with
`recommendations: []` and `clarification_needed: true`:

| `answer` | `next_step` | Phase 4C result |
| --- | --- | --- |
| `I understand what your budget and usage are.` | `I have all the details.` | Rejected |
| `No laptops match in the MyTech test catalogue. What is your budget and main usage?` | `Please provide your budget and intended usage.` | Rejected |
| `I recommend the Imaginary Laptop for RMB 1. What is your budget and main usage?` | `Please provide your budget and intended usage.` | Rejected |

Rejected text is not displayed or stored in validated assistant history; no new
product card or follow-up is created. Existing validated anchors and history are
preserved. Recovery, subsequent valid replies and Restart remain functional.

The corrected `demoMissingFieldClarification(output, guard)` now requires:

1. No products, `clarification_needed: true`, string answer/next-step fields,
   exactly one supported current target, and actual missing budget or usage.
   Any supplied budget must be positive and finite; supplied usage must pass the
   existing strict policy. Unsupported/contradictory usage and ambiguous ownership
   do not qualify.
2. Every sentence in **both** `answer` and `next_step` must match a whole bounded
   clarification form or an explicit neutral acknowledgement. No unmatched clause
   is discarded. At most eight sentences are accepted across both fields.
3. Questions use anchored forms such as `What is your budget?`, `What will you
   mainly use the laptop for?`, or `Could you tell me your budget and intended
   usage?`. Interrogative forms require their question terminator. Requests use
   bounded `Please provide/specify/share/state ...` or `Tell me ...` forms. Field
   terms are limited to budget/maximum budget and main/intended usage/use/purpose,
   with optional reference to the actual category and RMB/CNY/yuan budget units.
   A bounded pair of budget and use questions is supported.
4. Every requested field must actually be missing, and all missing fields must be
   requested. Questions about another category, already supplied fields, prices,
   product identities or extra constraints fail.
5. Neutral clauses are exactly `Sure`, `Okay`, `Thanks`, `Got it`, or a bounded
   `I can help you choose ...` offer naming the current category. Neutral clauses
   alone cannot establish clarification. Claims that information is already known,
   recommendations, no-match/availability claims, promises, contradictions and
   unrelated prose have no accepted production in this grammar.
6. The original full response and display validators still run afterward. The
   completion policy, canonical no-match logic, four-field public contract and
   product security semantics remain unchanged. A complete supported request
   continues through strict PR18 recommendation-completion validation.

These representative responses now pass on both candidates for the fresh
incomplete Laptop request:

- `What is your budget, and what will you mainly use the laptop for?`
- `Could you tell me your budget and intended usage?`
- `I can help you choose a laptop. What is your budget and main usage?`

Category-specific budget-only and usage-only questions also pass when only that
field is missing. Unknown wording, unsupported formatting and multi-target
clarification prose fail safely; this exception intentionally does not attempt
general natural-language interpretation or resolve multi-category ownership.

The only additional source change necessary for Phase 4C is the new candidate's
builder hook: it applies this check to genuine missing-budget requests too, which
previously bypassed the usage-only hook. Control/help, cancellation and comparison
paths keep their original validation behavior. No shared validator, workflow,
prompt/model/routing or server change is needed.

## Preservation, tests and checks

Final offline validation:

| Check | Result |
| --- | --- |
| Complete Python suite | 340 passed; no failures or skips |
| Complete Node suite | 592 passed; no failures or skips |
| New UI suite, included above | 164 passed across Local and AIEP |
| New Python suite, included above | 12 passed |
| PR17 replay against new package | 34 passed |
| PR18 replay against new package | 64 passed |
| Read-only consistency commands below | All 10 passed |
| Baseline preservation | All 67 fingerprints match |
| Repeat generation | All 8 output bytes and mtimes unchanged |
| Public credential-pattern / sensitive JSON checks | Passed |
| Whitespace and index checks | Passed; nothing staged |

The UI suite exercises actual generated primary button attributes and native
click/change/input/keydown handlers through the in-memory DOM. It covers exact
payloads, no initialization submission, concurrency, category selection, latest
snapshots, hard caps, strict comparison direction, identity changes, legitimate
and false no-match, malformed/empty/error responses, help, clarification and
unsafe bypass attempts, composer drafts, recovery, Restart and asynchronous races.
Existing PR17/PR18 assertions are retained and parameterized for candidate replay.

Phase 4C adds 74 permanent cases to the earlier 90-case UI suite. They cover all
three exact review reproductions, all representative legitimate questions,
category-specific missing fields, safe neutral acknowledgements, unsafe answer
and next-step mixtures, false plural no-match, fabricated products/prices,
embedded interrogatives, deferred/misleading next steps, missing-field coverage,
already supplied fields, unknown/contradictory usage, ambiguous/multiple targets,
complete requests disguised as clarification, unchanged prior anchors/history,
recovery without restarting, and Restart followed by valid requests. Tests execute
the full generated Local and AIEP submission/validation/rendering paths.

The first Phase 4C full Node run encountered `listen EPERM` for loopback server
tests in the default sandbox. Filtered replays passed 33 PR17 and 63 PR18 cases
with server cases excluded; those filtered results were not counted as complete
replays. With loopback execution permission, the full 592-test Node suite and
both complete 34/64-case replays passed. Providers remained mocked throughout.

Python checks prove deterministic portable manifests, source hashes, frozen
baseline bytes, exact workflow/catalogue/knowledge copies, unchanged original
styles/cards/transport/validators/keyboard handlers, credential exclusions,
read-only `--check`, symlink rejection, native accessible elements, focus rules,
wrapping styles and unchanged fixed-composer geometry. Existing reduced-motion
rules remain intact; the added styles introduce no animations.

**Visual limitation:** Chrome UI automation was attempted, but macOS
Accessibility/Screen Recording access was not granted. No browser screenshot,
real viewport overflow measurement, native tab-order or screen-reader result is
claimed. Mobile/desktop rendering, disclosure expansion, long product names,
focus navigation and reduced-motion behavior still need a real-browser review.
The temporary loopback mock preview was stopped after the attempt.

The mock DOM is a handler-level harness: it fabricates missing ID elements,
records focus with a flag, invokes event handlers directly, and assigns the
disclosure's `.open` state. It does not establish native focus/tab order,
summary/button keyboard activation, layout or screen-reader behavior. These
limits remain manual acceptance work; no browser permissions were requested
during Phase 4C.

Reproduction, with no private environment loading or real provider:

```sh
uv run --locked python -B tools/build_v21_quick_prompt_demo.py
uv run --locked python -B tools/build_v21_quick_prompt_demo.py --check
uv run --locked python -B -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/*.test.mjs
MYTECH_REPAIR_PACKAGE=v21_quick_prompt_demo node --test tests/usage-repair.test.mjs
MYTECH_COMPLETION_PACKAGE=v21_quick_prompt_demo node --test tests/completion-repair.test.mjs
```

The final two environment assignments use POSIX shell syntax; CI sets the same
variables through its cross-platform `env` mapping. The ten consistency commands:

```sh
uv run --locked python -B tools/validate_products.py --strict-v1
uv run --locked python -B tools/build_knowledge.py --check knowledge/MyTech_Product_Knowledge_v1.md
uv run --locked python -B tools/check_catalogue_consistency.py
uv run --locked python -B tools/build_aiep_test.py --check
uv run --locked python -B tools/build_prompt_ab_test.py --check
uv run --locked python -B tools/build_glm47_prompt_ab.py --check
uv run --locked python -B tools/check_workflow_registry.py
uv run --locked python -B tools/build_v21_usage_repair.py --check
uv run --locked python -B tools/build_v21_completion_repair.py --check
uv run --locked python -B tools/build_v21_quick_prompt_demo.py --check
```

CI retains its existing jobs and adds the new read-only build check plus both
regression replays. Hosted Ubuntu/macOS/Windows CI has not run: no commit or push
is authorized in this phase. Local tests include Windows-path simulation.

## Full changed-file inventory — 20 paths

Four existing files:

- `.github/workflows/ci.yml` — new check and replay steps.
- `tests/helpers/v21-repair-frontend.mjs` — actual generated buttons, attributes,
  selection/input events, controlled providers and deadlines for lifecycle tests.
- `tests/usage-repair.test.mjs` — allow new candidate in the existing replay.
- `tests/completion-repair.test.mjs` — configurable candidate; existing assertions
  and default PR18 target retained.

Eight new source/test/documentation files:

- `tools/build_v21_quick_prompt_demo.py`
- `tools/templates/v21_quick_prompt_demo.json`
- `tools/templates/v21_quick_prompt_demo.js`
- `tools/templates/v21_quick_prompt_demo.css`
- `tests/quick-prompt-demo.test.mjs`
- `tests/test_v21_quick_prompt_demo.py`
- `tests/fixtures/v21_quick_prompt_demo_preservation.json`
- `docs/v21-quick-prompt-demo.md`

Eight new generated files:

- `generated/v21_quick_prompt_demo/aiep/site/index.html`
- `generated/v21_quick_prompt_demo/local/index.html`
- `generated/v21_quick_prompt_demo/local/manifest.json`
- `generated/v21_quick_prompt_demo/manifest.json`
- `generated/v21_quick_prompt_demo/workflow-completion-repair.json`
- `generated/v21_quick_prompt_demo/local/mytech-fastgpt-workflow-v2_1-TEST.json`
- `generated/v21_quick_prompt_demo/local/catalogue.json`
- `generated/v21_quick_prompt_demo/local/MyTech_Product_Knowledge_v2_1_TEST.md`

## Independent review and future deployment

The corrected unstaged offline candidate is ready for another independent
read-only pre-commit review. The previous review's unsafe clarification finding
has permanent reproductions and now rejects all three responses. No independent
approval of Phase 4C is claimed. Review the bounded complete-clause grammar,
missing-budget hook, current-context snapshot checks, lifecycle/race coverage,
byte-preservation evidence and outstanding real-browser visual checks.

Phase 4C changes only eight of the existing twenty paths: the shared demo JS
template, new candidate builder, focused Node tests, this report, both new HTML
files, and their two manifests. The primary-prompt JSON, CSS, helper, Python
tests, preservation fixture, CI/replay changes and four copied runtime assets
retain their Phase 4B bytes. All 67 protected baselines remain unchanged.

Future live work requires separate authorization, rollback captures of current
published application/binding/HTML, an isolated TEST application and verified KB
and published-revision bindings. The AIEP route alone proves no project binding.
FastGPT conversation persistence, extraction and live RAG grounding remain
unverified; browser history/constraint maps are not forwarded by the hosted
transport. Catalogue eligibility and mocked success must not be presented as
live success. The public four-field contract and PR18 workflow remain unchanged.
