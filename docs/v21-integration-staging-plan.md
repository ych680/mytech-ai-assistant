# Phase 3A — final six-commit integration review; NO ACTIONS EXECUTED

Reviewed 2026-10-24 (Asia/Hong_Kong). This reconciles the accepted Phase 1/2
95-path plan plus one required cross-platform line-ending policy into
**six groups / 96 paths**. The additional `.gitattributes` belongs in commit 1
so generated hashes are stable from the first new commit onward.
The accepted Phase 2B private migration and metadata removal add no Git paths.
Every currently modified/untracked public path appears exactly once below.
Nothing is staged, committed, pushed or submitted as a PR. All staging/commit
commands in this document require the user's final review approval first.

| Proposed commit | Paths | Modified tracked | New public |
| --- | ---: | ---: | ---: |
| 1 — Master, generators and reproducible TEST assets | 34 | 2 | 32 |
| 2 — Isolated runtime and Node coverage | 8 | 0 | 8 |
| 3 — GLM A/B candidates and deferred fixtures | 22 | 0 | 22 |
| 4 — Actual Original/Optimized snapshots and registry | 10 | 0 | 10 |
| 5 — Documentation, publication exclusions and CI | 17 | 3 | 14 |
| 6 — Unified public env template/workspace setup | 5 | 1 | 4 |
| **Total** | **96** | **6** | **90** |

The `sh` blocks use zsh/bash/Git Bash continuations. Git accepts these relative
paths on Windows too; an exact native PowerShell first-commit block is provided
at the end. Do not substitute a directory, wildcard, `git add .` or `git add -A`.

Prepared 2026-10-24 on `feat/v21-automated-catalogue`. These are exact proposed staging groups for all current modified/untracked public files, including earlier authorized uncommitted work. No file is staged and no commit/push/PR is authorized by this document. Recheck Git status before applying; preserve any later or group-owned changes.

The branch already includes prerequisite commits `efa65b2` and `c141100` above main; retain and review their diffs. The branch currently has no upstream. Do not reset/rewrite that history to disguise the prerequisites. This Phase 3A review changes only checkout/publication policy and review metadata. The eventual PR also includes earlier workflow/runtime/prompt work; its scope is broader than this review's metadata changes, as detailed below. No live app or AIEP deployment is changed by Git integration.

Raw Downloads exports, `.env*`, private exports, secrets, OS files and virtual environments are excluded. Existing historical files are retained. The commands below use explicit files only; do not substitute a directory-wide or blanket add.

## Commit 1: `feat: add reproducible 54-product v2.1 TEST catalogue assets`

Exact files (34):

```sh
git add -- \
  .gitattributes \
  catalogue/mytech_products_v2_1_test.json \
  generated/aiep_v2_1_test/manifest.json \
  generated/aiep_v2_1_test/site/index.html \
  generated/v2_1_test/MyTech_Product_Knowledge_v2_1_TEST.md \
  generated/v2_1_test/catalogue.json \
  generated/v2_1_test/index.html \
  generated/v2_1_test/manifest.json \
  generated/v2_1_test/mytech-fastgpt-workflow-v2_1-TEST.json \
  mytech_v2_1_test_response.mjs \
  tests/test_aiep_v21_build.py \
  tests/test_catalogue_sync.py \
  tests/test_prompt_optimization.py \
  tests/test_workflow_import_contract.py \
  tools/build_aiep_test.py \
  tools/build_knowledge.py \
  tools/check_catalogue_consistency.py \
  tools/measure_v21_prompts.py \
  tools/sync_catalogue.py \
  tools/templates/mytech_current_working_portable.json \
  tools/templates/v21_aiep_runtime.js \
  tools/templates/v21_aiep_transport.js \
  tools/templates/v21_dataset_validation.js \
  tools/templates/v21_extraction_rules.txt \
  tools/templates/v21_frontend_runtime.js \
  tools/templates/v21_input_normalization.js \
  tools/templates/v21_recommendation_prompt.txt \
  tools/templates/v21_scope_consistency.js \
  tools/templates/v21_state_extraction_prompt.txt \
  tools/templates/v21_test_settings.json \
  tools/templates/v21_usage_compatibility.json \
  tools/templates/v21_usage_validation.js \
  tools/templates/v21_validation_failure.js \
  tools/validate_products.py
```

Before any later approved commit, inspect `git diff --cached --name-status`, `git diff --cached --check` and the complete staged diff; verify this exact allowlist and absence of private files. Stage no files from another group implicitly.

## Commit 2: `feat: add isolated local and hosted v2.1 TEST runtime coverage`

Exact files (8):

```sh
git add -- \
  mytech_v2_1_test_adapter.mjs \
  mytech_v2_1_test_server.mjs \
  tests/aiep-v21.test.mjs \
  tests/catalogue-v21.test.mjs \
  tests/current-workflow-v21.test.mjs \
  tests/local-v21.test.mjs \
  tests/workflow-usage-v21.test.mjs \
  tools/benchmark_v21.mjs
```

Before any later approved commit, inspect `git diff --cached --name-status`, `git diff --cached --check` and the complete staged diff; verify this exact allowlist and absence of private files. Stage no files from another group implicitly.

## Commit 3: `test: preserve isolated GLM A/B candidates and deferred fixtures`

Exact files (22):

```sh
git add -- \
  generated/glm47_prompt_ab/A-glm47-original.json \
  generated/glm47_prompt_ab/B-glm47-short.json \
  generated/glm47_prompt_ab/configuration-checklist.json \
  generated/glm47_prompt_ab/manifest.json \
  generated/glm47_prompt_ab/plan.json \
  generated/glm47_prompt_ab/prompt-changes.diff \
  generated/glm47_prompt_ab/six-request-results-template.csv \
  generated/prompt_ab_test/manifest.json \
  generated/prompt_ab_test/mytech-v21-prompt-A-control.json \
  generated/prompt_ab_test/mytech-v21-prompt-B-short.json \
  generated/prompt_ab_test/node-metrics-template.csv \
  generated/prompt_ab_test/plan.json \
  generated/prompt_ab_test/prompt-changes.diff \
  generated/prompt_ab_test/turn-results-template.csv \
  tests/glm47-prompt-ab.test.mjs \
  tests/prompt-ab.test.mjs \
  tests/test_glm47_prompt_ab.py \
  tests/test_prompt_ab_preparation.py \
  tools/build_glm47_prompt_ab.py \
  tools/build_prompt_ab_test.py \
  tools/templates/v21_glm47_actual_export_review.json \
  tools/templates/v21_working_actual_export_sanitized.json
```

Before any later approved commit, inspect `git diff --cached --name-status`, `git diff --cached --check` and the complete staged diff; verify this exact allowlist and absence of private files. Stage no files from another group implicitly.

## Commit 4: `feat: register actual Original and Optimized workflow snapshots`

Exact files (10):

```sh
git add -- \
  evaluations/records/v2.1/2026-10-24-glm47-t01-smoke.json \
  tests/registered-workflows.test.mjs \
  tests/test_workflow_registry.py \
  tools/check_workflow_registry.py \
  workflow/v2.1/comparison.json \
  workflow/v2.1/optimized/2026-10-24/provenance.json \
  workflow/v2.1/optimized/2026-10-24/workflow.sanitized.json \
  workflow/v2.1/original/2026-10-24/provenance.json \
  workflow/v2.1/original/2026-10-24/workflow.sanitized.json \
  workflow/v2.1/registry.json
```

Before any later approved commit, inspect `git diff --cached --name-status`, `git diff --cached --check` and the complete staged diff; verify this exact allowlist and absence of private files. Stage no files from another group implicitly.

## Commit 5: `docs: integrate version status, smoke evidence and release checks`

Exact files (17):

```sh
git add -- \
  .github/workflows/ci.yml \
  .gitignore \
  CHANGELOG.md \
  README.md \
  docs/v21-aiep-test-deployment.md \
  docs/v21-aiep-test-preservation.json \
  docs/v21-catalogue-sync.md \
  docs/v21-current-baseline-rebuild.md \
  docs/v21-glm47-smoke-test.md \
  docs/v21-integration-staging-plan.md \
  docs/v21-performance-and-local-test.md \
  docs/v21-prompt-ab-broader-plan-deferred.md \
  docs/v21-prompt-ab-validation.md \
  docs/v21-repository-integration-phase1.md \
  docs/v21-state-extraction-reliability.md \
  docs/v21-targeted-llm-latency.md \
  workflow/v2.1/README.md
```

Before any later approved commit, inspect `git diff --cached --name-status`, `git diff --cached --check` and the complete staged diff; verify this exact allowlist and absence of private files. Stage no files from another group implicitly.

## Commit 6: `chore: prepare unified local environment and workspace cleanup`

Exact files (5):

```sh
git add -- \
  .env.example \
  .vscode/settings.json \
  docs/local-workspace.md \
  docs/workspace-cleanup-inventory.json \
  tests/workspace-env.test.mjs
```

Only the public blank template is included; active/retired private env files and
their backups are excluded. No source of credentials is part of this commit.
The native env-file regression uses public/synthetic fixtures only. Before any
later approved commit, inspect the same staged allowlist/diff/whitespace gates.

## Coverage and final gates

These groups cover exactly 96 pending public files, each once. They include six modified tracked files and 90 new public files; unchanged tracked files need no staging. Group 1 keeps the line-ending policy, generators, all required templates and their checked outputs together. Group 2 adds dependent runtime/Node regressions. Group 3 keeps the earlier actual-source/A/B dependencies and seven deferred fixture files intact. Group 4 adds actual snapshots, registry, observed smoke record and read-only security/native-code checks. Group 5 updates current status, documents historical/deferred evidence and enables final CI gates. Group 6 adds the shared public env schema, local setup/retirement record, exact cleanup inventory, minimal settings and five native env-file tests. Archive classifications retain historical files in place.

The Original snapshot is the mixed DeepSeek/GLM AIEP default. Optimized is the actual experimental GLM export. GLM long-prompt A remains a separate experimental control. The observed T01 smoke does not populate the six paired NOT_RUN rows. No automatic promotion is part of any commit.

After all approved commits, verify in a clean checkout: full Python and Node suites, strict-v1 and TEST catalogues, stable knowledge, local/AIEP/deferred/GLM consistency, workflow registry/security and whitespace checks. Require three-platform PR CI; local passes do not prove Windows/Linux behavior. If individual commits must be independently green, validate their committed trees too, rather than accidentally testing unstaged later groups.

Only after later explicit authorization: refresh remote refs, reconcile any new
`main` changes, push this feature branch with upstream tracking and open a draft
PR to main, explicitly listing both prerequisite commits and all six new groups.
No GitHub operation has been performed. An eventual PR contains eight commits
before any separately agreed history changes: two existing plus six proposed.

## Current status and reconciliation

- Branch: `feat/v21-automated-catalogue`; HEAD: `c141100`. Local `main` and cached
  `origin/main` both point to `2a19bee`. Ahead two / behind zero against those
  cached refs; no upstream is configured for the feature branch. No fetch or
  remote-head verification was performed, so refresh refs before a later push/PR.
- Public inventory: 142 files (52 tracked / 90 untracked). Six tracked paths are
  modified; the index is empty. No project path is deleted, moved or renamed.
- The six modified tracked paths are `.env.example`, `.github/workflows/ci.yml`,
  `.gitignore`, `README.md`, `tools/build_knowledge.py`, `tools/validate_products.py`.
  All 90 untracked public paths are explicitly allocated above as proposed adds.
- The Phase 2B environment edit and three Finder removals involved ignored files
  only. Retired private files and restricted backups remain untouched in Phase 3A.
  No extra runtime, catalogue, prompt, UI, generated-output or snapshot edit arose.
- Phase 3A adds `.gitattributes`, updates this review and the two inventory/
  workspace status pointers, and adds narrow `.gitignore` rules for the three
  raw export filenames and `.pytest_cache/`. All other 137 preexisting public
  paths retain their accepted bytes. No existing file was renormalized.

## Included authoritative and generated files

Both actual sanitized exports are in commit 4, together with independent
provenance, registry, exact comparison and the reported smoke evidence:

- `workflow/v2.1/original/2026-10-24/workflow.sanitized.json`
- `workflow/v2.1/optimized/2026-10-24/workflow.sanitized.json`

Registry checks confirm their hashes, 54-product Master projections, 20-node /
18-edge graphs and exactly two model, two prompt and two layout-coordinate
differences. Routing, budgets, usage/product validation, memory and four-field
output otherwise match. Original remains the maintainer-confirmed mixed
DeepSeek/GLM AIEP default; Optimized remains experimental. Both exports omit KB
selections and a verifiable published revision. No account IDs or bindings were
invented to fill those gaps. No workflow import/publication is part of a commit.

Commit 1 includes the LF checkout policy, 54-product Master, generators, all consumed templates,
local assets/RAG knowledge and hosted AIEP HTML/manifest. Commit 2 adds its
isolated local runtime. Commit 3 preserves the GLM long/short controls and older
deferred fixtures, including all required dependencies. The frozen actual
snapshots are distinct from generated import candidates and portable templates.
Historical v2, UAT/evidence, screenshots, Tool 3 and group evaluation work stay
at their existing paths. No regeneration ran in the workspace during this review.

## Publication/security exclusions

| Excluded path/name | Evidence and publication policy |
| --- | --- |
| `.env`, `.env.v21.test`, `.env2`, other `.env*` | Ignored/untracked; no history entries found for those three private paths; contents not read. `.env.example` is the explicit public exception |
| `~/Library/Application Support/MyTech/private-backups/` | Outside the Git worktree; metadata-only checks confirm restricted permissions and unchanged backup files; no backup contents read |
| Downloaded `MyTech v2.1 — TEST Knowledge.json`, `MyTech v2.1 — GLM47 Optimized TEST.json`, `MyTech_Current_Working_Export_Reference.json` | Raw Downloads originals remain outside Git and were not opened; new exact-basename ignore rules protect accidental copies into the repo |
| `/private/exports/`, `/secrets/`, `*.private-export.json`, key/certificate bundles | Explicit ignore rules; no staged/allocated private path |
| `.venv/`, `node_modules/`, `__pycache__/`, `.pytest_cache/`, OS metadata, logs/build caches | Excluded; no machine cache or symlink included in the allowlist |
| `.vscode/*` except `.vscode/settings.json` | Only minimal portable Explorer exclusions may be published; personal editor/launch configuration remains ignored |

`.env.example` has twelve assignment names, blank credential/endpoint/app-ID/
binding placeholders, ports 8787/8788 and existing TEST operational defaults.
It contains no usable provider credential or endpoint. Public scanning includes
that template and all tests: 136 UTF-8 files and 32 JSON files, with six binary
evidence assets skipped. The only four pattern matches are intentional fixtures
in `tests/local-v21.test.mjs` (17/41) and `tests/test_aiep_v21_build.py` (85).
Recursive JSON sensitive-field checks pass. Ancestor changed text blobs also
produce no credential findings. No matched values or private content were
printed. These bounded checks are not a proof covering every secret format.

All 142 public paths are regular files: no Git symlink/submodule modes or
filesystem symlinks. The largest is `workflow/workflow-overview-2.png`, 304,018
bytes; no public file exceeds 10 MiB. Generated hashes/assets and local Markdown
file links resolve. External web links and remote service availability were not
tested. No credential validity or live model-quality claim follows from CI.

## Existing ancestor commits included in the future PR

1. **`efa65b2` — `fix: improve targeted follow-ups and pending-action lifecycle`**
   changes `.github/workflows/ci.yml`, adds `tests/workflow-followup.test.mjs`
   and changes `workflow/mytech-fastgpt-workflow.json`. The historical graph
   remains 18 nodes / 17 edges. It changes guard state/outputs, clarification
   routing and prompt, recommendation prompt, retrieval query targeting,
   validation and memory-writer bindings. It resolves targeted/ambiguous
   comparisons, category continuations, cancellation/stale actions and valid
   anchor retention; tests cover product/usage/budget boundaries. This is a
   genuine inherited workflow/prompt behavior change relative to `main`, not
   documentation-only scope. The accepted HEAD version is preserved here.
2. **`c141100` — `feat: add AIEP deployment candidate and regression tests`**
   adds `aiep-candidate/README.md`, `aiep-candidate/site/index.html`,
   `tests/aiep-candidate.test.mjs` and `tests/aiep-conversation.test.mjs`.
   It preserves the 27-product Editorial Clean candidate, hosted relative proxy,
   documented standalone key mode, strict result checks, targeted conversation
   state and safe error/restart handling. It does not deploy the candidate.
   Current v2.1 generation depends on this candidate as its reviewed UI source.

Together those ancestors touch seven paths (five adds/two modifications).
They are intentional prerequisites and were not rebased, reset or rewritten.
The original local v2 frontend/server/data files are unchanged by them. The
eventual complete tree versus cached `main` has **95 adds, seven modifications,
zero deletions: 102 changed paths**. This count includes ancestor work plus the
96 pending paths, with overlapping CI changes counted once.

## Completed validation and commit-dependency evidence

Full current-workspace runs passed: **304 Python tests / 330 Node tests**, with
no failures, skips or cancellations. Node used default test isolation. Strict-v1
(27 products/nine categories), TEST catalogue (54/nine), historical knowledge,
catalogue sync, AIEP compatibility, deferred/GLM generation checks, actual
workflow registry, security, local-path and whitespace checks passed.
All provider interactions were mocked; no live/paid API calls ran.

The six cumulative proposed trees were separately assembled from tracked HEAD
plus only groups 1 through N in a temporary public-only directory. No private
env, virtual environment, Git index or commit was copied/created. Each tree's
full available Python and Node suites and applicable read-only checks passed:

| Cumulative tree | Python | Node | Applicable consistency gates |
| --- | ---: | ---: | --- |
| Through commit 1 | 269 | 175 | strict-v1, knowledge, catalogue, AIEP |
| Through commit 2 | 269 | 306 | strict-v1, knowledge, catalogue, AIEP |
| Through commit 3 | 292 | 321 | above plus deferred and GLM candidates |
| Through commit 4 | 304 | 325 | above plus actual registry |
| Through commit 5 | 304 | 325 | all above |
| Through commit 6 | 304 | 330 | all above plus unified-env tests |

This verifies that commit 1 does not depend on untracked files left for a later
commit and that later groups introduce their dependencies together. Scratch
copies were temporary and removed; no repository file was deleted or moved.
Final review-only plan text does not alter any tested runtime/generated bytes.
These are local macOS results, not an executed Windows/Linux/GitHub CI result.

The line-ending risk was reproduced without staging or creating Git objects:
`git -c core.autocrlf=true cat-file --filters` at a hashed JSON path introduced
CRLF without attributes. With `.gitattributes`, the same checkout simulation
preserved LF at catalogue, hosted HTML, both snapshot and JS-template paths;
PNG/PDF evidence retained identical bytes. This addresses the deterministic
checkout conversion risk; real Windows CI is still required. No `git add
--renormalize`, reset or working-tree conversion was run.

## Proposed PR scope and remaining review gates

Title: **MyTech v2.1: preserve actual workflow variants and reproducible TEST deployment**.

The PR description should lead with the reproducible 54-product TEST path,
preserved Original default and isolated Optimized experiment, then disclose the
two ancestor changes above. Include the exact source/registry provenance,
read-only checks, cross-platform env instructions and secret exclusions.
Record T01 as one reported smoke PASS: 34.45 s and 0.9531 AI-node credits.
Platform-wide billing is unverified; uncontrolled historical timings do not
demonstrate meaningful prompt latency improvement or model superiority. The
six paired request rows remain NOT_RUN; no automatic 28/80-request campaign.

Ready for the user's **staging/commit review**, with no current local test,
asset-completeness, size, symlink or credential-exclusion blocker identified.
Before remote integration: refresh `main`, reconcile divergence, review the full
102-path/eight-commit PR scope and require existing Ubuntu/Windows/macOS PR CI.
Unexported KB IDs/indexes and published revision remain documented reproduction
limits. Retired private-file deletion is separate and is not a GitHub prerequisite.
Do not publish/import/promote either app or redeploy AIEP as part of this PR.

## Exact first-commit commands — only after final approval

First require the expected feature branch, unchanged reviewed paths and an
empty index. Run these checks; stop if the branch/index differs:

```sh
git branch --show-current
git status --short
git diff --cached --exit-code
```

Then run **only the explicit 34-path `git add --` block under Commit 1 above**.
For native Windows PowerShell, the equivalent exact staging command is:

```powershell
$mytechCommit1Files = @(
  '.gitattributes',
  'catalogue/mytech_products_v2_1_test.json',
  'generated/aiep_v2_1_test/manifest.json',
  'generated/aiep_v2_1_test/site/index.html',
  'generated/v2_1_test/MyTech_Product_Knowledge_v2_1_TEST.md',
  'generated/v2_1_test/catalogue.json',
  'generated/v2_1_test/index.html',
  'generated/v2_1_test/manifest.json',
  'generated/v2_1_test/mytech-fastgpt-workflow-v2_1-TEST.json',
  'mytech_v2_1_test_response.mjs',
  'tests/test_aiep_v21_build.py',
  'tests/test_catalogue_sync.py',
  'tests/test_prompt_optimization.py',
  'tests/test_workflow_import_contract.py',
  'tools/build_aiep_test.py',
  'tools/build_knowledge.py',
  'tools/check_catalogue_consistency.py',
  'tools/measure_v21_prompts.py',
  'tools/sync_catalogue.py',
  'tools/templates/mytech_current_working_portable.json',
  'tools/templates/v21_aiep_runtime.js',
  'tools/templates/v21_aiep_transport.js',
  'tools/templates/v21_dataset_validation.js',
  'tools/templates/v21_extraction_rules.txt',
  'tools/templates/v21_frontend_runtime.js',
  'tools/templates/v21_input_normalization.js',
  'tools/templates/v21_recommendation_prompt.txt',
  'tools/templates/v21_scope_consistency.js',
  'tools/templates/v21_state_extraction_prompt.txt',
  'tools/templates/v21_test_settings.json',
  'tools/templates/v21_usage_compatibility.json',
  'tools/templates/v21_usage_validation.js',
  'tools/templates/v21_validation_failure.js',
  'tools/validate_products.py'
)
git add -- $mytechCommit1Files
```

Review the staged diff and require exactly those 34 paths (32 adds/two modified
tools), no private files and no unexpected content. These commands work in both
shells; run the final commit only after those checks and the requested approval:

```sh
git diff --cached --name-status
git diff --cached --stat
git diff --cached --check
git diff --cached
git commit -m "feat: add reproducible 54-product v2.1 TEST catalogue assets"
```

No command block in this document has been executed against the Git index.
