# MyTech v2.1 — Repository Integration Phase 1

Recorded 2026-10-24, Asia/Hong_Kong; branch `feat/v21-automated-catalogue`.
Scope: preserve actual exports and integrate repository metadata, documentation
and offline checks. No live application, AIEP, model/prompt, UI, recommendation
logic or existing generated asset was changed. No commit, push, PR or merge ran.

## Actual exports and sanitation

Both exact files were inspected read-only from macOS Downloads. The historical
`MyTech_Current_Working_Export_Reference.json` was not treated as v2.1 source.

| Actual application | Raw bytes | Raw SHA-256 |
| --- | ---: | --- |
| MyTech v2.1 — TEST Knowledge | 190,315 | `3e6087b7572ea4c7cfa702c895f5b6a369e6a31c032cfd4264d5d2e72b736f60` |
| MyTech v2.1 — GLM47 Optimized TEST | 177,583 | `2e058ac56aa61f66320b4e8d100f92182bc42af65b06e46ab0aa73aad467f326` |

Before copying, credential patterns and recursively recognized sensitive fields,
including native key/value inputs, were checked without printing matched values.
Neither export produced findings. Each contained only `/chatConfig/_id` account
metadata requiring redaction; that path was removed and JSON formatting normalized.
All other values were preserved. Raw originals remain outside Git, unchanged.

The [registry](../workflow/v2.1/registry.json) points to versioned actual snapshots
and separate provenance files under `workflow/v2.1/{original,optimized}/2026-10-24/`.
The sanitized Original is byte-identical to the previously reviewed source at
`tools/templates/v21_working_actual_export_sanitized.json`; both paths remain.
The sanitized Optimized is new actual-app evidence, not a renamed generated candidate.
Snapshot/provenance hashes are checked without requiring Downloads in CI.

## Original versus Optimized

Both have 20 nodes/18 edges, identical node/output IDs, native schemas, edges,
globals, routing, RAG settings, extraction schema, state writers, validators,
memory protection and public four-field JSON output. Their complete validator
catalogues match the 54-product Master, including the 27 provisional additions.

| Difference | Original | Optimized |
| --- | --- | --- |
| Extraction model `etNrwEXVwr5sySpK` | `deepseek/deepseek-v4.1-flash` | `glm-4.7` |
| Recommendation model `pskHz4kajjJnBWwG` | `deepseek/deepseek-v4.1-flash` | `glm-4.7` |
| Extraction description | 11,634 chars | 5,615 chars |
| Recommendation system prompt | 11,087 chars | 5,164 chars |
| `v21RmbInputNormalize` editor position | x=645, y=-1425 | x=960, y=-1575 |

The position is the only difference beyond the two intended models and two
prompts: it contributes two JSON coordinate fields and has no runtime edge/code
effect. [comparison.json](../workflow/v2.1/comparison.json) records exactly six
changed JSON paths and no other changes. Clarification stays `glm-4.7`, history 6,
reasoning off and maxToken 800. Extraction/Recommendation histories remain 6;
Recommendation maxToken stays 4096. RAG remains embedding search, similarity
0.35, limit 5000, rerank/query extension disabled. No parameters were normalized
or silently overwritten to manufacture parity.

The actual Optimized snapshot differs from generated
`generated/glm47_prompt_ab/B-glm47-short.json` only in those two layout coordinates.
GLM long-prompt A remains an experiment control, not the default mixed-model
Original. The general generated TEST workflow has shortened prompts and blank
portable model selectors; it is not the Original deployed workflow either.

## Deployment, KB and performance evidence

Original **MyTech v2.1 — TEST Knowledge** remains the default application for the
successful university AIEP deployment, with confirmed binding per the maintainer.
The registry separately records this later deployment evidence; the old generated
manifest's preparation-time UNVERIFIED status is preserved byte-for-byte.
No platform configuration was inspected or changed during this integration.

Both exports have `datasets.value=[]`, so their runtime KB IDs/index versions
cannot be independently established from JSON. The optimized smoke-test report
names `MyTech v2.1 — TEST Knowledge` as its KB; it does not prove identical KB
IDs/indexes in both apps. Neither export proves a publication revision or whether
it represents the editor draft. These known limits are recorded rather than
filled with invented IDs or changed live bindings.

One real optimized T01 smoke test is recorded as **maintainer-reported PASS**:
the Gaming Laptop recommendation costs RMB 4,999 within RMB 6,000. Extraction
took 12.33 s, Recommendation 21.69 s and total workflow 34.45 s. Combined AI-node
credits were 0.9531; other nodes account for approximately 0.43 s. Platform-wide
billed credits were not independently verified. See the
[full experiment record](v21-glm47-smoke-test.md) and its structured JSON.

Historical longer-prompt GLM 36.5 s and mixed-model 5.05 s observations are
unpaired and do not show model superiority or causal prompt savings. The
optimized workflow remains about 34 seconds and experimental. **Prompt shortening
has not demonstrated a meaningful latency improvement. No complete six-request
A/B evaluation has been performed.** The existing six NOT_RUN rows remain intact;
no 28/80-request campaign or additional test was executed.

## Sources and generated assets

- Historical v2 remains 27 products, with all original runtime/source/history paths.
- The v2.1 Master remains 54 products/nine categories. `tools/sync_catalogue.py`
  maintains local TEST catalogue/RAG/frontend/workflow consumers; the separate
  AIEP builder reuses its reviewed frontend renderer and Master.
- Actual Original/Optimized snapshots are frozen export evidence. The registry
  checker compares both full product projections with the Master, preventing a
  future Master edit from silently leaving snapshots on different product facts.
- Existing generated assets, prompt templates, servers and historical snapshots
  are preserved. Versioned snapshots add provenance without changing old consumers.
  Reproduction instructions distinguish actual snapshots from generated candidates.

## Security and regression review

Environment files were not read. `.env`, `.env.v21.test` and `.env2` remain
ignored/untracked. Raw Downloads exports are outside the repository. New narrow
ignore rules cover `/private/exports/`, `/secrets/` and `*.private-export.json`;
reviewed public snapshots remain eligible for Git. No blanket JSON ignore was added.
The public scanner reports paths/rules/lines only; synthetic security fixtures
must be identified explicitly rather than excluding all tests from scanning.

New checks cover snapshot/provenance hashes, Original default/no automatic
promotion, actual model/prompt identity, source consistency, complete Master
projections, missing KB/publication evidence, sensitive fields, path traversal,
symlink rejection, smoke arithmetic and the separation of smoke versus A/B.
Native Node regressions execute both actual validators/router/public answer paths
for valid/unsafe multi-product output and targeted comparison memory.

Only metadata, docs, new registry checking/tests and private-export ignore rules
were added/updated. Existing frontend, server, generation logic and prompt/product
behavior were not modified. The exact [staging plan](v21-integration-staging-plan.md)
groups all pending public files, including earlier uncommitted work, without
staging anything. Existing prerequisite commits `efa65b2` and `c141100` remain.

## Final inventory and Git status

The branch remains `feat/v21-automated-catalogue` at `c141100`, ahead of the
last synchronized `main` by two commits, behind by zero, with no upstream.
There are **52 tracked files, 85 untracked public files, five modified tracked
files and zero staged files**. No deletion, move or rename was performed.
Remote state was not refreshed; these comparisons use existing local refs.

The 137-file tracked/untracked public inventory is grouped below. Ignored local
environment/cache files are outside this inventory and were not opened.

| Location | Files | Role and preservation policy |
| --- | ---: | --- |
| Repository root | 15 | Historical v2 runtime/data/prompt, isolated v2.1 runtime, README/changelog and configuration; preserve paths |
| `.github/` | 2 | Existing CI workflows; add registry gate to cross-platform CI |
| `aiep-candidate/` | 2 | Historical v2 hosted candidate; unchanged |
| `catalogue/` | 1 | Authoritative 54-product TEST Master; unchanged |
| `docs/` | 18 | Historical evidence, TEST preparation, deployment and integration guides |
| `evaluations/` | 8 | Historical evaluation records plus separate reported T01 smoke record |
| `generated/` | 21 | Reproducible local/AIEP/GLM/deferred outputs; unchanged in this phase |
| `knowledge/` | 1 | Historical 27-product RAG source; unchanged |
| `tests/` | 29 | Existing suites plus Python/Node actual-snapshot regressions |
| `tools/` | 28 | Existing generators/templates/tools plus read-only registry checker |
| `workflow/` | 12 | Historical references plus six versioned snapshot/registry JSON files and guide |

This phase adds **15 public files**: six workflow JSON records, the workflow guide,
one smoke JSON, one checker, two test files, CHANGELOG and three integration/smoke/
staging documents. Five preexisting metadata/doc files changed: `.gitignore`,
`.github/workflows/ci.yml`, README, AIEP deployment guide and prompt A/B guide.
The other **116 preexisting inspected public files are byte-identical**, including
all old runtime, prompt/template, catalogue, generated and historical files.
The earlier modifications to `tools/build_knowledge.py` and
`tools/validate_products.py` were preserved exactly, not edited in this phase.

The [exact staging allowlists](v21-integration-staging-plan.md) enumerate all
90 pending public paths once across five proposed commits (33 / 8 / 22 / 10 / 17
files). They preserve earlier uncommitted work and require review before use.

## Completed offline checks

All commands below passed locally. Python used the existing environment without
dependency installation; Node providers were mocked and transport tests used
local loopback only. No live FastGPT/TokenProxy request or credit use occurred
during repository integration.

```sh
.venv/bin/python -B -m unittest discover -s tests -p 'test_*.py' -v
node --test --test-isolation=none tests/*.test.mjs
.venv/bin/python -B tools/validate_products.py --strict-v1
.venv/bin/python -B tools/validate_products.py --dataset catalogue/mytech_products_v2_1_test.json --test-v21
.venv/bin/python -B tools/build_knowledge.py --check knowledge/MyTech_Product_Knowledge_v1.md
.venv/bin/python -B tools/check_catalogue_consistency.py
.venv/bin/python -B tools/build_aiep_test.py --check
.venv/bin/python -B tools/build_prompt_ab_test.py --check
.venv/bin/python -B tools/build_glm47_prompt_ab.py --check
.venv/bin/python -B tools/check_workflow_registry.py
git diff --check
```

Results: **304 Python tests passed; 325 Node tests passed**, with no failures,
skips or cancellations. Historical strict-v1 validation passed for 27 products /
nine categories; TEST validation passed for 54 / nine. Stable knowledge,
catalogue/local/AIEP, deferred fixtures, GLM candidates and actual registry checks
all passed. Node's local run used disabled test isolation; the proposed CI retains
its ordinary isolated runner and must pass on all three platforms before merge.
Local success does not substitute for unexecuted GitHub CI or a live A/B test.

## Final security and preservation findings

- Scanned all **130 public UTF-8 text files**; skipped six binary assets and the
  tracked `.env.example` without reading its contents. The 30 public JSON files
  contain no nonempty recognized sensitive fields. No actual credential was found
  by the bounded pattern/field checks. This is not a proof covering every possible
  secret format.
- Four pattern matches are intentional synthetic security fixtures only:
  `tests/local-v21.test.mjs` lines 17 and 41, and two rules on
  `tests/test_aiep_v21_build.py` line 85. Matched values were not printed.
  Tests were included in scanning rather than blanket-excluded.
- `.env`, `.env.v21.test` and `.env2` are ignored and untracked; no environment
  contents were accessed. Downloads originals remain outside Git; both SHA-256
  hashes **and modification times are unchanged**. Only the reviewed sanitized
  snapshots are proposed for staging.
- Preservation hashes verified the 116 unchanged preexisting public files and
  exactly five intended metadata changes. Local documentation links, explicit
  staging-plan coverage/uniqueness and the empty Git index were checked.

Open review limits remain the unexported KB IDs/indexes, unverified publication
revision, unpaired performance observations and pending three-platform CI.
The phase stops for review before any staging, commit, GitHub or deployment action.
