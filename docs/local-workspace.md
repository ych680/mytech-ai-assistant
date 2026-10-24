# Local workspace and unified environment — Phase 2

Phase 3A integration note: the [final six-commit review](v21-integration-staging-plan.md)
now allocates **96 paths**, adding only `.gitattributes` to the accepted 95-path
plan to preserve byte hashes under Windows checkout. The Phase 2/2B counts below
remain historical checkpoint records; no private configuration was changed again.

## Current status — Phase 2B completed, 2026-10-24

The approved local consolidation **succeeded**. `.env` is the one active local
configuration for both Node servers. Its original legacy bytes were preserved
as a prefix; the seven existing TEST assignments were appended without changing
their parsed values. Default `PORT` and the optional TEST app-ID field were
added to complete the public schema. No credential was replaced, printed or
transmitted to an external service. `.env2` was backed up but never merged over
the authoritative legacy `.env` settings. No required-name or merge conflict
was found. The active `.env` now has owner-only mode `0600`.

Names present, without values:

```text
PORT
FASTGPT_API_KEY
FASTGPT_API_URL
FASTGPT_APP_ID
MYTECH_TEST_FASTGPT_API_URL
MYTECH_TEST_FASTGPT_API_KEY
MYTECH_TEST_FASTGPT_BINDING
MYTECH_TEST_FASTGPT_APP_ID
MYTECH_TEST_PORT
MYTECH_TEST_REQUEST_TIMEOUT_MS
MYTECH_TEST_MAX_TOKENS
MYTECH_TEST_TIMINGS
```

The optional TEST app-ID assignment may be empty under app-key binding. No
legacy-to-TEST credential fallback was added. Native Node env-file resolution
was checked against both original sources without logging their values.

Both commands were launched successfully from this checkout and the servers
remain running locally:

```sh
node --env-file=.env mytech_v2_server.mjs
node --env-file=.env mytech_v2_1_test_server.mjs
```

Local GET verification passed for ports **8787** and **8788**, legacy health,
TEST configuration, exact original HTML content, the historical 27-product
catalogue and Master-equal 54-product TEST catalogue. Both servers refused
`/.env` with 404. The previously running TEST server was restarted to load the
consolidated file. No chat request or live model/API validation was performed.
Offline configuration separation does **not** prove current credential validity
or remotely establish which application/KB a provider credential selects.

Before mutation, exact backups of `.env`, `.env.v21.test` and `.env2` were created
and byte-verified outside the repository at:

```text
~/Library/Application Support/MyTech/private-backups/2026-10-24-phase2b-455402b6/
```

The backup directory and its private parents have mode `0700`; backup files
have mode `0600`. The private migration journal records recovery state and
local process IDs, without publishing credentials. **`.env.v21.test` and `.env2`
are retired configurations**, retained unchanged at their original paths for
final review. They remain ignored/untracked and are no longer the documented
normal launch source. Do not delete them without the requested final review.
For rollback, stop both local servers, restore `.env` from the restricted backup
and use the former TEST launch with `.env.v21.test`; then clear inherited overrides
as described in the preparation record. Rollback was not needed because all
verification passed.

Only the three authorized, ignored/untracked Finder metadata files were removed:
`.DS_Store`, `generated/.DS_Store`, `generated/aiep_v2_1_test/.DS_Store`.
No source, generated asset, workflow, test, evaluation or group file was removed
or relocated. Finder can regenerate its metadata. The exact inventory records
these three entries as removed rather than silently dropping the audit history.

Validation passed: **304 Python tests, 330 Node tests** (default isolation, no
failures/skips/cancellations); strict-v1 and TEST catalogue validation; stable
knowledge; catalogue, AIEP, deferred/GLM workflow outputs; actual workflow registry;
security and whitespace checks. The security scan covered 135 public UTF-8 files
and 32 JSON files, excluding all private env/backup contents. Its only four
matches were the previously documented synthetic test fixtures. No actual
credential finding was identified by these bounded checks.

All 141 public paths from accepted Phase 2 remain. Only README, this guide,
the local TEST launch/performance guide and cleanup inventory received Phase 2B
documentation/status updates; the other **137 public files are byte-identical**.
All six previously modified tracked files and 89 preexisting untracked public
assets remain; no runtime, prompt, UI, catalogue, generated or actual-snapshot
bytes changed. Git remains on `feat/v21-automated-catalogue` at `c141100` with six
modified tracked files, 89 untracked public files and an empty index. The proposed
95-path staging plan remains complete. No staging/commit/push/PR/merge or live
FastGPT/AIEP modification occurred. Windows/Linux runtime verification and later
cross-platform CI remain outstanding; the scripts/configuration were not changed.

## Accepted Phase 2 preparation record — historical

The following records the pre-migration audit and approved procedure. Its
"not performed" and future-approval statements describe the Phase 2 checkpoint;
the Phase 2B status above supersedes them for this local checkout.

Reviewed 2026-10-24 (Asia/Hong_Kong), branch `feat/v21-automated-catalogue`.
Private environment migration is **prepared, not performed**. No file was deleted,
moved or renamed; no runtime, UI, prompt, generated asset or live platform changed.

## Variable-name audit and application boundaries

Only assignment names were inspected in the three private files. Value bytes
were skipped without retaining, comparing, displaying or hashing them. The audit
cannot establish whether credentials are current, equal or bound to the right app.

| File | Names found | Git status | Decision |
| --- | --- | --- | --- |
| `.env` | `FASTGPT_API_KEY`, `FASTGPT_API_URL`, `FASTGPT_APP_ID` | Ignored, untracked | Preserve; future single active file |
| `.env.v21.test` | `MYTECH_TEST_FASTGPT_API_URL`, `MYTECH_TEST_FASTGPT_API_KEY`, `MYTECH_TEST_FASTGPT_BINDING`, `MYTECH_TEST_PORT`, `MYTECH_TEST_REQUEST_TIMEOUT_MS`, `MYTECH_TEST_MAX_TOKENS`, `MYTECH_TEST_TIMINGS` | Ignored, untracked | Preserve as current TEST source until approved migration |
| `.env2` | `FASTGPT_API_KEY`, `FASTGPT_API_URL`, `FASTGPT_APP_ID` | Ignored, untracked | Ownership/currentness unknown; do not assume duplicate values |
| `.env.example` | Four legacy and eight TEST names below | Tracked, public | Updated blank placeholders/defaults only |

No duplicate assignment names were found in the private files. Neither server
loads a dotenv file itself. Node's `--env-file` populates its environment; each
server already selects its own namespace. No server code change is needed.
The independent Tool 3 CLI uses hidden `getpass` input and intentionally reads
no credentials from files or environment variables. It remains unchanged and
adds no variables to this schema.

| Namespace | Consumer and defaults | Application |
| --- | --- | --- |
| `FASTGPT_API_KEY`, `FASTGPT_API_URL`, `FASTGPT_APP_ID`, `PORT` | `mytech_v2_server.mjs`; port 8787; all three binding values required for API readiness | Historical 27-product v2 app; preserve its independent binding |
| `MYTECH_TEST_FASTGPT_API_URL`, `MYTECH_TEST_FASTGPT_API_KEY`, `MYTECH_TEST_FASTGPT_BINDING`, `MYTECH_TEST_FASTGPT_APP_ID` | `mytech_v2_1_test_server.mjs`; all four blank means offline assets-only; a partial binding fails startup | Explicitly verified 54-product v2.1 TEST app; never use legacy credentials as fallback |
| `MYTECH_TEST_PORT` | TEST port, default 8788 | Independent of `PORT` |
| `MYTECH_TEST_REQUEST_TIMEOUT_MS` | 120000; range 5000–300000 | Preserve existing TEST value during migration |
| `MYTECH_TEST_MAX_TOKENS` | 4096; range 256–8192 | Preserve existing TEST output limit |
| `MYTECH_TEST_TIMINGS` | `0` (off); `1` enables bounded timing logs | Preserve existing preference |

The [public schema](../.env.example) leaves credentials/URLs/app IDs/binding mode
empty. These blanks are placeholders. Populate them privately later. TEST URLs
must be HTTPS without userinfo/query/fragment. Choose exactly one binding mode:

- `app-key`: independently verified TEST application key; leave
  `MYTECH_TEST_FASTGPT_APP_ID` empty.
- `app-id`: independently verified TEST credential plus TEST application ID.

Do not infer a binding mode from the absence of an ID in the current private
file. It was not inspected. Never reuse `FASTGPT_APP_ID` implicitly.
Original **MyTech v2.1 — TEST Knowledge** remains the default working AIEP app;
**MyTech v2.1 — GLM47 Optimized TEST** remains experimental. The unified file
does not change AIEP or select/promote an optimized workflow automatically. It
provides one local TEST slot, not simultaneous Original/Optimized credentials.
Keep later controlled A/B testing in separately verified applications/conversations.

## Final launch commands — after approved private migration

Run from the repository root in two terminals, using Node 24 (the CI version).
No npm install or dotenv package is needed. These commands work in macOS zsh
and Windows PowerShell; repository paths contain no OS-specific separators.

```sh
# Terminal 1: historical v2
node --env-file=.env mytech_v2_server.mjs

# Terminal 2: v2.1 TEST
node --env-file=.env mytech_v2_1_test_server.mjs
```

Open `http://127.0.0.1:8787/` and `http://127.0.0.1:8788/`, respectively, unless
the retained private configuration deliberately overrides those defaults.
No upstream model request occurs at startup; submitting a chat is a separate
live action and is not part of this phase. Both processes receive the file's
variables, but their server code selects separate credential namespaces.

**Before migration**, continue the already-working local launch method. If the
existing TEST file was your source, its explicit command remains
`node --env-file=.env.v21.test mytech_v2_1_test_server.mjs`; using only the current
legacy `.env` will not load those TEST settings. Bare
`node mytech_v2_1_test_server.mjs` loads no env file and remains useful for
offline assets-only startup when no TEST variables are inherited.

For a brand-new checkout only, create `.env` from the public template **only if
it does not exist**. Never use a plain overwrite copy against this workspace:

```sh
# macOS zsh; noclobber protects an existing destination, including a race.
(set -C; cat .env.example > .env)
chmod 600 .env
```

```powershell
# Windows PowerShell; overwrite=false refuses an existing destination.
[System.IO.File]::Copy((Join-Path $PWD '.env.example'), (Join-Path $PWD '.env'), $false)
```

If the destination exists, stop and use the reviewed migration below. Restrict
Windows file/folder permissions to the intended user using local NTFS security
settings; do not put the file in a shared/synced folder.

## Exact secure migration procedure — requires later approval

1. Stop local servers. Confirm which legacy credential set is authoritative
   (`.env` versus `.env2`) with its owner; identical variable names do not prove
   identical values. Independently confirm that the TEST credential/mode selects
   the intended published TEST app. Do not print keys or request chat completions
   to establish this. KB/publication limits in the workflow registry still apply.
2. Make an access-restricted, non-synced backup of all three private files outside
   the repository using a local secret manager or OS file tools. Preserve original
   names with a local date suffix. Do not add backups to Git, chat or evaluation
   records. On macOS restrict the directory to owner access and files to mode
   600; on Windows restrict the NTFS ACL to the owner. Record backup locations
   privately. No backup or credential copy was made by this phase.
3. Edit the existing `.env` in a private local editor. Preserve its selected
   legacy `FASTGPT_*` values. Add `PORT` only if needed, retaining port 8787 by
   default. Copy the seven existing `MYTECH_TEST_*` assignments from the current
   TEST file into that same private `.env` without changing their values. Add
   `MYTECH_TEST_FASTGPT_APP_ID` only if required by the already-verified mode;
   leave it blank in app-key mode. Preserve custom port/timeout/token/timing
   settings. Keep each name exactly once. Do not copy the public template over
   `.env`, bulk-merge `.env2`, or paste credentials into terminal arguments.
4. Check for inherited overrides before launching. Native Node environment
   variables take precedence over `--env-file`. Clear only the relevant names
   in each launch terminal as below. These commands remove shell bindings and
   never print their values; they do not edit the private file.

   ```sh
   # macOS zsh
   unset PORT FASTGPT_API_KEY FASTGPT_API_URL FASTGPT_APP_ID \
     MYTECH_TEST_FASTGPT_API_URL MYTECH_TEST_FASTGPT_API_KEY \
     MYTECH_TEST_FASTGPT_BINDING MYTECH_TEST_FASTGPT_APP_ID MYTECH_TEST_PORT \
     MYTECH_TEST_REQUEST_TIMEOUT_MS MYTECH_TEST_MAX_TOKENS MYTECH_TEST_TIMINGS
   ```

   ```powershell
   # Windows PowerShell
   $mytechEnvNames = @(
     'PORT', 'FASTGPT_API_KEY', 'FASTGPT_API_URL', 'FASTGPT_APP_ID',
     'MYTECH_TEST_FASTGPT_API_URL', 'MYTECH_TEST_FASTGPT_API_KEY',
     'MYTECH_TEST_FASTGPT_BINDING', 'MYTECH_TEST_FASTGPT_APP_ID', 'MYTECH_TEST_PORT',
     'MYTECH_TEST_REQUEST_TIMEOUT_MS', 'MYTECH_TEST_MAX_TOKENS', 'MYTECH_TEST_TIMINGS'
   )
   $mytechEnvNames | ForEach-Object { Remove-Item "Env:$_" -ErrorAction SilentlyContinue }
   ```

5. Run the offline checks below. Start each server with the final `.env` commands
   and inspect only local page/config readiness. Do not submit a chat or print
   the environment. TEST must refuse partial bindings and must never become
   configured through legacy fields. A local ready flag cannot prove which
   remote application a key selects; retain the independent operator evidence.
6. Only after both launches are accepted, change personal launch shortcuts to
   reference `.env`. With separate approval, archive `.env.v21.test` and `.env2`
   to the restricted backup location. Do not delete either now. The desired end
   state is one active `.env`; archival copies remain private and inactive.
7. Rollback: stop both servers, restore the original `.env` from the private
   backup, restore archived originals to their previous paths if moved later,
   clear inherited overrides and use the previously working launch methods.
   No workflow/AIEP rollback is necessary because this migration changes neither.

## Cleanup inventory and dependencies

The [exact machine-readable inventory](workspace-cleanup-inventory.json) lists
every public tracked/untracked path, private env path and observed cache/OS item,
including Git tracking, category, dependencies and recovery. Categories describe
review decisions; **ARCHIVE means retain in place now**, not an executed move.

| Category / exact path or group | Reason, dependencies and recovery |
| --- | --- |
| KEEP — all historical v2 files, `aiep-candidate/`, `workflow/mytech-fastgpt-workflow.json`, group evaluation code/evidence, CI, tests | Active compatibility, group work and historical evidence; existing references stay intact |
| KEEP — `catalogue/`, all `tools/templates/`, `generated/v2_1_test/`, `generated/aiep_v2_1_test/`, `generated/glm47_prompt_ab/`, both actual `workflow/v2.1/` snapshots | Master/generator/hash/test/deployment dependencies; no deletion or relocation proposed |
| ARCHIVE in place — seven exact files under `generated/prompt_ab_test/` listed below | Superseded reconstructed experiment, but builder/checker, Python/Node tests and CI still consume them; moving/deleting would break checks |
| ARCHIVE in place — `docs/v21-prompt-ab-broader-plan-deferred.md` | Deferred 28/80-request history linked by the active six-request plan; retain links and prior evidence |
| KEEP — `tools/templates/v21_working_actual_export_sanitized.json` | Content duplicates the Original snapshot, but GLM builder, registry and tests use this exact source path/hash; not safe to delete |
| KEEP — `tools/templates/mytech_current_working_portable.json` | Distinct portable reconstruction used by catalogue generation/native-contract tests; not the actual exported Original |
| KEEP — `.env`, `.env.v21.test`, `.env2` | Private credentials remain untouched. The latter two are conditional future private-archive candidates only after migration/owner approval; recover from restricted backups |
| SAFE TO DELETE AFTER APPROVAL — `.DS_Store`, `generated/.DS_Store`, `generated/aiep_v2_1_test/.DS_Store` | Ignored/untracked Finder metadata; no application/test dependency; Finder recreates it. No deletion performed |
| HIDE FROM VS CODE — `.venv/`, cache patterns in settings | Local environment/cache noise; no move or deletion; undo the settings change to show them |

The seven exact ARCHIVE-in-place generated paths are:

- `generated/prompt_ab_test/manifest.json`
- `generated/prompt_ab_test/mytech-v21-prompt-A-control.json`
- `generated/prompt_ab_test/mytech-v21-prompt-B-short.json`
- `generated/prompt_ab_test/node-metrics-template.csv`
- `generated/prompt_ab_test/plan.json`
- `generated/prompt_ab_test/prompt-changes.diff`
- `generated/prompt_ab_test/turn-results-template.csv`

All eight ARCHIVE-in-place paths are currently **untracked**. Their dependency
analysis includes `tools/build_prompt_ab_test.py`, `tests/test_prompt_ab_preparation.py`,
`tests/prompt-ab.test.mjs`, active documentation/plan links and CI's read-only
check. A later relocation requires updating all consumers and regenerating to a
reviewed scratch directory, then rerunning regressions. Restore original bytes
at original paths from a reviewed private backup to undo an approved move;
version control cannot recover currently untracked files. No relocation is
recommended during this phase or before a reviewed preservation commit.

The other dated documents are retained evidence, not disposable duplicates.
`tools/measure_v21_prompts.py` is used by tests and latency notes;
`tools/benchmark_v21.mjs` is used by local performance documentation. No unused
public script was established by the reference audit. No public project file
is proposed for deletion. The historical Downloads export remains outside the
repository and is not a cleanup target.

## VS Code scope

`.vscode/settings.json` only hides `.venv`, `__pycache__`, `.pytest_cache`,
`node_modules` and OS metadata in Explorer. It hides no catalogue, workflow,
test, source, deployment, environment or historical evidence file. Missing cache
directories are merely covered by future patterns. No global editor setting,
Python interpreter, launch binding or terminal environment is changed.
The Git ignore exception admits only this shared settings file; other personal
`.vscode` files remain ignored. Rollback removes/reverts that settings file after
approval and restores the previous ignore rule; no source/runtime rollback is needed.

## Validation and preservation

Use an existing Python environment; do not regenerate outputs as a cleanup step.
From the repository root, macOS uses `.venv/bin/python`; Windows uses
`.\.venv\Scripts\python.exe`. The arguments are identical. With uv already
available, `uv run --locked --offline python` is another option when its local
environment/cache is populated; no setup download is needed for this review.

```sh
.venv/bin/python -B -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/*.test.mjs
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

New Node regressions load only the public template and temporary synthetic env
fixtures, exercising native `--env-file`, defaults, app-key/app-id separation,
missing TEST credentials and inherited-variable precedence. They import the real
TEST config function without starting an upstream request. Real private env
values are never used in these tests.

Completed locally with Node 24.21.0 and Python 3.12.15:

- **304 Python tests passed**; **330 Node tests passed**, with zero failures,
  skips or cancellations. The full Node suite passed with its default test
  isolation, matching the CI invocation. Local HTTP test providers were mocked.
- Historical strict-v1 validation passed (27 products/nine categories); TEST
  catalogue validation passed (54/nine). Historical knowledge, catalogue outputs,
  AIEP compatibility, deferred fixtures, GLM candidates and actual workflow
  registry checks all passed. `git diff --check` and local documentation links passed.
- Security review scanned **135 public UTF-8 text files** and recursively checked
  **32 JSON files** for nonempty recognized sensitive fields. Six binary evidence
  assets were skipped. No actual credential finding was identified by these
  bounded checks; the same four known synthetic fixture matches remain at
  `tests/local-v21.test.mjs` lines 17/41 and `tests/test_aiep_v21_build.py` line 85.
  No matched values were printed. Private value content was never included in
  scans or tests. Heuristic scanning does not prove absence of every secret type.
- All **137 preexisting public paths remain**. Of these, **132 are byte-identical**.
  The only five edited existing public files in Phase 2 are `.env.example`,
  `.gitignore`, README, the local TEST performance guide and the staging-plan
  addendum. Four public files were added: settings, this guide, the inventory
  JSON and native-env regression suite.
- All five previously modified tracked files remain: `.github/workflows/ci.yml`,
  `tools/build_knowledge.py` and `tools/validate_products.py` are byte-identical
  to the accepted Phase 1 workspace; README and `.gitignore` retain their earlier
  integration changes plus the documented Phase 2 edits. All **85 earlier untracked
  assets remain**; 83 are byte-identical, and only the two guides received the
  intentional documentation updates above. No runtime/template/catalogue/
  generated output, actual workflow snapshot or group evaluation file changed.
- `.env`, `.env.v21.test` and `.env2` retain their inode, size and modification
  time. All remain ignored and untracked. No private backup, migration or
  deletion was performed. The only env-content inspection was assignment names;
  public `.env.example` was deliberately updated.
- The exact inventory covers **141 public files** (52 tracked and 89 untracked):
  **133 KEEP**, **eight ARCHIVE in place**. Extra entries cover three private env
  files, three Finder files and the existing virtual environment. The settings
  file alone is eligible for Git under `.vscode`; personal launch/settings files
  other than that explicit exception remain ignored.
- Git remains on `feat/v21-automated-catalogue`, HEAD `c141100`, with **six modified
  tracked files, 89 untracked public files, zero staged files and no deletions**.
  The sixth modified tracked path is `.env.example`. No commit/push/PR/merge,
  live API call, credit spend, FastGPT modification or AIEP change occurred.

The configuration and commands use cross-platform Node APIs and native Node
env-file loading; PowerShell and macOS procedures are documented separately.
This local macOS run does not establish a Windows/Linux pass. Require the existing
Ubuntu/Windows/macOS PR CI after later authorization; no remote CI was triggered.

## Before GitHub integration

The [Phase 1 staging plan](v21-integration-staging-plan.md) remains its reviewed
90-path baseline; phase 2 does not stage any of it. After approval, retain its
five groups and review their newly edited metadata/docs. Add a sixth explicit
workspace group for these five additional pending paths:

```sh
git add -- .env.example .vscode/settings.json docs/local-workspace.md \
  docs/workspace-cleanup-inventory.json tests/workspace-env.test.mjs
```

Proposed later commit: `chore: prepare unified local environment and workspace cleanup`.
Do not run it now. The complete proposed allowlist is 95 pending paths, with no
private files. Review staged diffs/secret scan, test committed trees and require
the existing three-platform PR CI after later authorization. No cleanup move,
credential migration or optimized-workflow promotion is a prerequisite to
preserving the current working project on GitHub.
