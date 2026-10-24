# v2.1 multi-product usage repair — offline candidate

Prepared on 2026-10-24 (Asia/Hong_Kong). Nothing here publishes a workflow,
changes an AIEP binding, uploads a page, or calls a paid provider.

## Evidence and scope

The actual Original export rejects `gaming, good performance` in 代码运行#2
(`fakNM8mmlYmewx67`): `gaming` is recognized, then the unknown word `good`
causes a safe rejection. Its shared validator is also embedded in the Optimized
export. Existing partial-result handling already accepts a valid Laptop-only
response when another request genuinely has no qualifying product.

The existing frontend independently assigns a trailing `for gaming` only to
Mouse, leaving Laptop usage unset. It also keeps just the first usage keyword
for a category, losing commuting and ANC when Music appears first.

The exact live paired inputs are preserved in
`tests/fixtures/v21_usage_repair.json`:

1. Failed: `I need a laptop under ¥6,000 and a mouse under ¥1000 for gaming.`
2. Passed: `I need a laptop under ¥6,000 for gaming and a mouse under ¥1000 for gaming.`

Both repaired frontends assign Gaming to Laptop and Mouse, with separate caps
6000 and 1000. Offline recommendations resolve full identities from LAP-005 and
MOU-002, priced at 4999 and 229. A separate exact lowercase-input observation
is retained too. The maintainer reports successful FastGPT extraction, queries
and final recommendations, and successful AIEP cards for the positive control.
Exact final JSON and Code Run #2 diagnostics have not been supplied for those
runs; the failed AIEP request is not assumed to have received identical bytes.

## Correction

- The authoritative usage helper explicitly recognizes complete Laptop/Gaming
  phrases such as `gaming, good performance`. This is a qualitative preference
  requiring an actual Gaming tag, not benchmark evidence. `good` and
  `performance` are not generic fillers. Unknown qualifiers, negation, `or`,
  unsupported capabilities and more specific unsupported usages still fail.
- The candidate-only frontend parser retains complete per-category usage
  wording. It shares a trailing `for ...` only in a bounded coordinated form
  with no explicit independent usages. Missing or ambiguous ownership requests
  clarification. It does not reuse another product's budget or usage.
- Both frontends and the Node adapter execute the same usage policy. The
  server honors explicit current targets and refuses recommendations when the
  browser has marked usage ownership as ambiguous.
- Original user messages still reach the existing chat transport, including
  clarification turns, so a later reply does not lose FastGPT conversation
  context. Ambiguous recommendations are rejected, with an explicit browser
  clarification and unchanged validated anchors. Offline tests mock transport.
- The repair workflow adds exact four-field/inner-field and catalogue-fact
  preflight checks before the Original validator body; it does not accept prose
  around JSON. Each request requires a finite positive numeric hard budget.
- A partial response must explain each omitted category in an explicit
  same-clause no-match statement, and the full Master must contain no eligible
  item under that request's budget and complete usage. This is deliberately
  conservative: a retrieval miss alone is not accepted as proof of catalogue
  ineligibility. Free-text explanation checks are bounded lexical checks,
  not a general semantic proof of every sentence.
- Any invalid returned item rejects the entire returned batch. It is never
  silently dropped to rescue the remaining recommendations. Failure outputs
  and comparison-memory bindings preserve previous validated anchors.

### Phase 2B: complete current-turn guards and explicit usage corrections

The final read-only review exposed two additional frontend gaps. The usage
ownership hook changed session requirements after the guard had copied them,
and a replacement with no known usage keyword could leave the old usage intact.

The repair-only generator now runs that hook before copying either constraint
map. Its category-free usage replies bypass the legacy single-keyword fallback;
the complete-usage hook owns those updates, including pending-usage replies.
This avoids both stale guard values and premature assignment to an inferred
category. Budget handling remains unchanged.

Bounded instruction forms such as `Use it for ... instead.`, `I will use it
for ...` and `Change the main usage to ...` recognize a correction even if the
replacement has no known usage keyword. Only the instruction wrapper and a
trailing `instead` are removed. The entire replacement, including unknown
qualifiers, alternatives and negation, reaches the existing strict policy.
Corrections require one current target; multiple or unresolved targets request
clarification without choosing a category or overwriting its constraints.
Unsupported corrections remain in the target's requirements and reject returned
recommendations while preserving previous validated anchors. The original user
message still reaches the existing chat transport.

Eight shared multi-turn fixtures run against the Original repair validator,
Node adapter and both complete frontend candidates. They include:

- Music at RMB 800, followed by `music and commuting, noise cancellation`:
  the guard retains all three requirements and rejects Sony WH-CH520 at 350.
- Music at RMB 1200, or a missing-usage request at that budget, followed by the
  same composite reply: Sony WH-CH720N at 1009 is accepted; WH-CH520 is rejected.
- Music at RMB 1200, followed by `Use it for quantum simulation instead.`:
  the guard retains `quantum simulation`, requests clarification and cannot
  accept a Music-only recommendation by reusing the previous usage.
- Supported explicit replacements, composite corrections, unknown qualifiers
  and negation. Additional tests cover empty corrections, ambiguous ownership
  even when one category has missing usage, independent budgets, immutable guard
  snapshots, anchor preservation, recovery, comparisons and Restart.

These corrections do not change the FastGPT repair workflow bytes or its shared
usage validator. They update only frontend context handling, regression evidence
and strictly dependent candidate/provenance fingerprints.

For Headphones / 800 / Music + commuting + ANC, no product qualifies in the
unchanged Master. AUD-005 supports the usages but costs 1009; AUD-001 at 350
does not establish commuting/ANC. The combined request can therefore accept
LAP-005 alone with an honest Headphones no-match explanation and no budget rise.

## Reproduction and preserved baselines

```sh
uv run --locked python -B tools/build_v21_usage_repair.py
uv run --locked python -B tools/build_v21_usage_repair.py --check
uv run --locked python -B -m unittest discover -s tests -p "test_*.py" -v
node --test tests/*.test.mjs
```

The original catalogue, historical v2 frontend/runtime, Original and Optimized
snapshots, previous generated workflow/A/B exports, and both previous generated
HTML files remain intact. The accepted builders explicitly use the usage helper
from the archived actual Original export to reproduce those baselines. Their
two affected manifests refresh source provenance only; they do not claim the
accepted assets contain the repair. `repair_usage=True` is an explicit opt-in
used by the new builder. The existing default local launch remains the baseline.

The new package is `generated/v21_multiproduct_usage_fix/`:

| Path | Purpose |
| --- | --- |
| `workflow-original-repair.json` | Actual Original plus changes to exactly one validator-code field |
| `local/index.html` | Repaired local TEST frontend, same CSS/cards |
| `local/catalogue.json` | Byte-identical 54-product Master |
| `local/mytech-fastgpt-workflow-v2_1-TEST.json` | Same Original repair graph for the Node adapter |
| `local/MyTech_Product_Knowledge_v2_1_TEST.md` | Unchanged knowledge document; no KB upload required |
| `local/manifest.json` | Local runtime asset fingerprints |
| `aiep/site/index.html` | Separate hosted repair upload candidate |
| `manifest.json` | Source hashes, graph-change scope, output hashes and deployment gates |

`createTestAdapter(candidateLocalDirectory)` and
`createTestServer(testServerConfig(...), {directory: candidateLocalDirectory})`
exercise this package without changing default paths. The regression suite uses
these options with a loopback server and an in-memory provider. Do not supply
real credentials merely to preview or validate the files.

## Checks and deployment gates

The shared fixture suite covers both exact live phrasings, the 300-RMB Mouse
case, independent Study/Gaming usages, compound Headphones no-match, valid
partial output, unsafe full batches, unknown/negated/ambiguous requirements,
exact identities/prices/sources/contracts, independent hard caps, comparisons,
failed-turn memory and restart. Python checks prove deterministic output, POSIX
manifest paths, graph parity, frozen assets, CSS/cards and source fingerprints.
The ordinary strict-v1, catalogue, knowledge, AIEP, A/B and registry checks remain
required. Cross-platform CI includes the candidate's read-only consistency check.

Before any future live change, obtain review of this separate candidate and
capture the current published export/binding and uploaded HTML for rollback.
Use an isolated FastGPT repair application first. The candidate preserves the
Original prompts, models, 20 nodes/18 edges, node/output IDs, RAG settings,
histories, routing and memory bindings. Its export still omits actual KB
selection and a verifiable published revision: manually select the same existing
KB and verify publication and project binding; importing alone proves none of
those connections. Do not substitute the shortened portable/A/B workflow.

Only after separate deployment approval should the isolated application and
`aiep/site/` candidate be tested together. Keep the current working Original app
and AIEP upload available for rollback. The Optimized app remains experimental;
this repair does not promote it or change its archived export. No live validation
or performance improvement is claimed by the offline tests.

## Offline validation and exact change inventory

Local final run: **318 Python tests and 364 Node tests passed**, with no failures
or skips. Ten read-only catalogue/knowledge/AIEP/A/B/registry/repair checks passed.
These are offline results, including mocked provider transport and loopback HTTP.
Phase 2B adds eleven Node tests to the previously reported 353. The initial
sandboxed focused run could not bind its loopback HTTP server (`listen EPERM`);
the full suite passed with local loopback permission and mocked providers.
The new Windows-path simulation passed; fresh hosted Windows/Ubuntu/macOS CI
cannot run until a future reviewed commit/push. No paid requests were executed.

Seven existing files are modified:

- `.github/workflows/ci.yml` — read-only repair-package check.
- `generated/aiep_v2_1_test/manifest.json` — source provenance only, including the frozen helper's actual-export dependency.
- `generated/prompt_ab_test/manifest.json` — source provenance only.
- `mytech_v2_1_test_server.mjs` — ambiguity flag validation and current target selection.
- `tools/build_aiep_test.py` — explicit repair opt-in and baseline provenance.
- `tools/sync_catalogue.py` — frozen baseline helper and candidate-only frontend integration.
- `tools/templates/v21_usage_validation.js` — scoped phrases, complete usage parsing, exact contract and honest partial-result checks.

Seven non-generated files are added:

- `docs/v21-multiproduct-usage-repair.md`
- `tests/fixtures/v21_usage_repair.json`
- `tests/helpers/v21-repair-frontend.mjs`
- `tests/test_v21_usage_repair.py`
- `tests/usage-repair.test.mjs`
- `tools/build_v21_usage_repair.py`
- `tools/templates/v21_frontend_usage.js`

The eight new generated files are listed in the package table above. Total:
**22 paths**. All other tracked files, including historical/group contributions,
Master prices, actual snapshots and accepted HTML, remain byte-identical to the
merged `main` baseline. Repeat generation does not rewrite matching files.

Credential-pattern and populated-sensitive-JSON-field checks inspect public
sources/artifacts only. Findings are limited to the four pre-existing synthetic
test fixtures. Private environment files remain ignored and untracked; their
contents were not read. Candidate symlinks and unexpected output files fail
closed. Git whitespace checks cover modified and new files. No changes are
staged, committed, pushed or deployed.

## Separate unresolved school-demo finding

A complete Gaming Laptop request reportedly returned `recommendations: []`
with `clarification_needed: false` and displayed no recommendation. This remains
a separate unresolved issue. Empty recommendation arrays still pass the current
partial-result helper; that observation does not establish why the live workflow
returned an empty array. This phase does not change that behavior. Investigate
extraction, retrieval, raw recommendation output, Code Run #2 and the actual
frontend-received payload separately before claiming the school-demo issue fixed.
