# Offline Agent Evaluation Framework

> Scripted offline results validate evaluation behavior under controlled responses. They do not measure empirical LLM accuracy.

The framework executes 16 deterministic scenarios against the existing Tool 3 orchestrator and read-only executor, scores actual evidence, and produces versioned JSON and Markdown reports. It is separate from the consumer chatbot and FastGPT workflow. No live model is evaluated, no external LLM API is called, and no school API tokens are consumed during these offline runs.

## Architecture and fixtures

```text
Validated scenario manifest + isolated temporary fixture
    -> Scripted local transport -> actual Tool 3 orchestrator and executor
    -> Observed calls, results and resource-integrity evidence
    -> Deterministic scorer -> safe JSON report -> Markdown from the same data
```

| Component | Responsibility |
|---|---|
| [scenarios.json](../evaluations/scenarios.json), [scenario_contract.py](../evaluations/scenario_contract.py) | Sixteen versioned requests, scripted responses, requirements, allowed plans and authored expectation oracles; scripts are data, not executable code. |
| [fixtures.py](../evaluations/fixtures.py) | Fresh temporary dataset/knowledge files for each run, strict-v1 policy, exact SHA-256 hashes, integrity checks and cleanup. |
| [run_tool3.py](../evaluations/run_tool3.py) | Inject a scripted local transport into the real [orchestrator](../tools/tool3_tokenproxy.py), invoke the real [executor](../tools/tool3_executor.py), and retain bounded actual evidence. |
| [score_tool3.py](../evaluations/score_tool3.py) | Pure assessment of required operations and actual behavior, followed by comparison with the authored oracle. |
| [report_tool3.py](../evaluations/report_tool3.py) | Verify offline transport execution, project approved fields, derive totals, and render JSON/Markdown without duplicating orchestration or scoring. |

**F0** copies the approved valid dataset and consistent knowledge. **FD** changes only the logical `LAP-001.price_rmb` value from integer `5799` to boolean `false`, serialized as canonical JSON. **FK** keeps the valid dataset and changes the selected knowledge record's reference price from `5799` to `5800`. All changes occur in temporary copies; source resources are checked for integrity and never rewritten. Prepared-resource hashes and source-resource hashes are reported separately.

Each orchestration allows at most **3 completion attempts, 2 execution rounds and 8 total tool calls**. Completion attempts and scripted transport invocations are separate counters; neither represents a real network request. The reporter records actual network requests as `0` only when offline transport injection and invocations were verified under network/credential guards; otherwise the value is `null`.

## Scenario guide

The table describes the approved scripts, not predictions about a real model. `V` means `validate_products`; `K` means `check_knowledge`.

| Scenario | Fixture | Controlled behavior | Baseline task verdict |
|---|---|---|---|
| AE-01 | F0 | Execute V only, as requested. | pass |
| AE-02 | F0 | Execute K, including its internal dataset-validation prerequisite. | pass |
| AE-03 | F0 | Execute V and K in one permitted batch. | pass |
| AE-04 | F0 | Answer a conceptual question without inspecting files. | pending_review |
| AE-05 | F0 | Claim dataset validity without executing a required check. | fail |
| AE-06 | FD | Execute V and detect the controlled invalid dataset field. | pass |
| AE-07 | FK | Execute K and detect the controlled knowledge inconsistency. | pass |
| AE-08 | FD | Execute V; K is acceptably skipped because the dataset is invalid. | pass |
| AE-09 | F0 | Attempt an unsupported tool name; reject the entire batch. | fail |
| AE-10 | F0 | Attempt unauthorized knowledge arguments; reject the entire batch. | fail |
| AE-11 | F0 | Execute V, receive its result, then execute K in the required order. | pass |
| AE-12 | F0 | Execute V and deliver a final response, omitting required K. | fail |
| AE-13 | F0 | Execute V twice and unnecessary K despite a V-only, once-only request. | fail |
| AE-14 | F0 | Execute V, then receive a scripted HTTP 502; preserve partial results. | fail |
| AE-15 | FD | V detects invalid data; the scripted final explanation claims validation passed. | pending_review |
| AE-16 | F0 | Execute V and K, then attempt a third call that is blocked; no final delivery. | fail |

All 16 approved scenarios are expected to pass their **evaluation expectation** checks, including the intentionally failed agent tasks. These are reference expectations; each run derives its actual classifications and totals from observed execution.

## Running offline checks

Run from the repository root with Python 3.12 and an existing project environment. See [Python setup](../README.md#python-tooling-with-uv) if setup is needed; creating that environment may require runtime downloads. The checks below do not install dependencies or require credentials.

Windows PowerShell:

```powershell
# All 224 Python tests (90 tooling + 134 Agent Evaluation)
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p "test_*.py" -v
# Only the 134 Agent Evaluation tests
.\.venv\Scripts\python.exe -B -m unittest tests.test_tool3_evaluation_foundation tests.test_tool3_evaluation_runner tests.test_tool3_evaluation_scoring tests.test_tool3_evaluation_reporting -v
# All 16 offline execution-contract checks; no report files
.\.venv\Scripts\python.exe -B -m evaluations.run_tool3
```

macOS/Linux:

```sh
./.venv/bin/python -B -m unittest discover -s tests -p "test_*.py" -v
./.venv/bin/python -B -m unittest tests.test_tool3_evaluation_foundation tests.test_tool3_evaluation_runner tests.test_tool3_evaluation_scoring tests.test_tool3_evaluation_reporting -v
./.venv/bin/python -B -m evaluations.run_tool3
```

The [existing cross-platform CI](../.github/workflows/ci.yml) uses unittest discovery on Ubuntu, Windows and macOS, so it automatically includes foundation (28), Runner (25), scorer (43) and reporter (38) tests. Reporter tests already generate full reports in temporary directories and verify JSON/Markdown consistency. The [Node workflow](../.github/workflows/tests.yml) covers the separate chatbot's syntax and 16 Node.js tests. No additional workflow or duplicate report smoke step is required.

## Generating evidence reports

Choose a **fresh explicit output directory**. The following commands select a new temporary location and leave the two reports there for inspection.

Windows PowerShell:

```powershell
$evaluationOutput = Join-Path ([System.IO.Path]::GetTempPath()) ("mytech-eval-" + [guid]::NewGuid().ToString("N"))
.\.venv\Scripts\python.exe -B -m evaluations.report_tool3 --output-dir "$evaluationOutput"
Write-Output "$evaluationOutput"
```

macOS/Linux:

```sh
evaluation_output="$(mktemp -d "${TMPDIR:-/tmp}/mytech-eval.XXXXXX")"
./.venv/bin/python -B -m evaluations.report_tool3 --output-dir "$evaluation_output"
printf '%s\n' "$evaluation_output"
```

The CLI runs all 16 scenarios, scores their actual evidence and writes **`tool3-evaluation.json`** and **`tool3-evaluation.md`**. It creates the selected directory if needed and refuses to overwrite either report. Importing the reporter or calling `generate_report()` creates no report files. The CLI returns `0` when all evaluation expectations pass, even if some agent tasks intentionally fail or await review; unexpected assessments, invalid runs or output failures return nonzero.

JSON schema and scoring rules are versioned `1.0.0`. Reports include manifest version, Git revision and dirty-tree status when available, Python/platform metadata, execution limits, fixture hashes and cleanup status, safe call authorization flags, result IDs/statuses/codes, operation handling, plan checks, failure categories and separate verdicts. Markdown is rendered from that same report object; totals are calculated rather than hard-coded.

Do not commit generated reports. These commands use the system temporary directory to keep evidence output outside application and production-resource directories. Retain or remove those temporary files as needed after inspection.

## Interpreting counts and verdicts

**Required** counts manifest requirements; **met** counts substantive requirements satisfied by actual results; **handled** includes both met requirements and explicitly permitted dependency blocks. No-tool completeness is **not applicable**, not 100%. There is no weighted or percentage score.

Operation states are `met`, `blocked_expected`, `failed_unexpected` and `missing`, with associated actual tool-result IDs. A failed validation with `dataset_invalid` or knowledge check with `knowledge_inconsistent` can meet a requirement to detect the controlled defect. A rejected attempt is not execution evidence. A successful K may satisfy semantic dataset validation when the requirement allows its prerequisite evidence, but it cannot replace a separately requested explicit V call.

AE-08 has **required/met/handled = 2/1/2**: invalid data is detected, while knowledge inspection is acceptably blocked, so deterministic task handling passes. AE-12 has **2/1/1** and fails despite completed orchestration. AE-16 has **2/2/2** but fails because the extra attempted call hits the execution limit and final delivery is absent. Executed-call counts include accepted dispatches returning skipped results; `skipped_count` identifies these separately.

| Verdict | Interpretation |
|---|---|
| Task `pass` / `fail` | Actual deterministic task handling satisfied / violated the scenario requirements. A pass does not certify every explanation's meaning. |
| Task `pending_review` | Deterministic handling passes, but required human review is unresolved. |
| Task `invalid_run` | Runner, fixture or evidence infrastructure is invalid; do not interpret it as agent performance. |
| Expectation `pass` / `fail` | The observed assessment and orchestration contract agree / disagree with the authored oracle. A valid unexpected observation can fail this check without being an infrastructure failure. |
| Expectation `not_evaluable` | Infrastructure failure prevents a valid expectation assessment. |

For example, AE-05 intentionally bypasses a required tool. Correctly identifying that behavior gives **task fail and expectation pass**. The approved baseline distribution is 7 task passes, 7 task failures, 2 pending reviews, 0 invalid runs and 16 passing expectations; regenerate reports to verify it for the current checkout.

AE-04 needs a person to assess conceptual answer correctness. AE-15 needs a person to compare the final explanation with the actual negative validation result. Both remain pending; the manifest's `anticipated_outcome` is never an actual human judgment. The scorer supports explicit in-memory review annotations, but the reporting workflow does not accept or persist them. A future reviewed verdict may disagree with the original pending oracle without implying broken evaluation infrastructure. A deterministic failure always takes precedence over pending review.

## Security, reproducibility and limits

Offline tests use injected scripted responses; reporting additionally guards network entry points and credential prompts. Environment files and API credentials are not needed or read. Only the two allowlisted tools and selected resources are available; no shell actions, arbitrary model-selected paths or agent-invoked knowledge generation are added. The executor's trusted-local-resource boundary is not a sandbox against a hostile local caller or filesystem.

Reports use an explicit safe-field projection. They exclude raw arguments, requests, authorization headers, credentials, hidden reasoning, final explanation text, diagnostics and result data; identifiers/error codes are bounded and sanitized. Consequently, persisted reports alone cannot support retrospective semantic review of an omitted explanation: authorized reviewers need the original in-memory evidence or a separately authorized future evidence-capture workflow.

Stable JSON serialization and scenario ordering omit timestamps, random IDs, output paths and hostnames. Identical evidence, Git state and runtime produce identical report bytes. Exact hashes describe the checked-out resource bytes; checkout line endings, Python/platform metadata, repository revision and dirty state can differ between machines. Unavailable Git metadata and unverified network counts are `null`, not inferred. Fixture integrity checks detect drift but do not restore modified resources.

Exclusive file creation protects existing reports, and ordinary write failures roll back newly created files. The JSON/Markdown pair is **not crash-atomic**. Offline guards are process-wide and intended for serial reporting, not concurrent live-provider work in the same process.

This framework does not measure real-model tool selection, empirical LLM accuracy, general explanation correctness, deployed FastGPT knowledge consistency, browser layout or production reliability. It adds no live evaluation, semantic grader, database, dashboard or consumer-chatbot integration. See [Tool 3 architecture](tool3-architecture.md) for the separate orchestration protocol and its boundaries.
