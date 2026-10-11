# Tool 3 — Native LLM Tool Orchestrator

Tool 3 is an independent Python agent prototype merged through [PR #9](https://github.com/ych680/mytech-ai-assistant/pull/9). It demonstrates native LLM tool calling over two existing, deterministic local operations. The consumer-facing MyTech chatbot continues to use its browser, Node.js backend, and FastGPT RAG workflow; it does not invoke Tool 3.

## Native Tool-Calling Loop

```text
User request → Python orchestrator ↔ TokenProxy LLM
                      ↓               native tool_calls
             Validate entire batch
                      ↓
             Allowlisted executor
                      ↓
        Dataset validation / Knowledge checking
                      ↓
     role:tool results → LLM → Final explanation
```

1. [`tool3_tokenproxy.py`](../tools/tool3_tokenproxy.py) sends the request and two function schemas using the TokenProxy chat-completions API. The configured model is `tokenproxy/vision`, with native `tool_calls` and `tool_choice`.
2. The model may request `validate_products` or `check_knowledge`. Arguments use only `selected_dataset` and, for knowledge checks, `selected_knowledge`; trusted local `ResourceBindings` select the actual files and validation policy.
3. [`tool3_executor.py`](../tools/tool3_executor.py) validates the entire batch before resource access. Fixed dispatch invokes the [dataset validator](../tools/validate_products.py) or [knowledge checker](../tools/build_knowledge.py), never a model-supplied command.
4. Every knowledge check first requires valid dataset content. An invalid dataset produces failed validation or a skipped knowledge check without reading the knowledge file. Dataset loading/validation is shared within a batch and repeated for a later batch.
5. The orchestrator preserves the assistant's calls and returns each structured result in a `role:tool` message associated with its `tool_call_id`. The model can request another bounded round or provide a final explanation.

The result separates `assistant_response` from authoritative `tool_results`, with `status`, `code`, `execution_status`, `api_requests`, and `tool_rounds`. Per-call statuses are `success`, `failed`, or `skipped`. Earlier executed results remain available after later provider or limit failures.

## Execution and Security Boundaries

| Boundary | Implemented behavior |
|---|---|
| Tool dispatch | Only `validate_products` and `check_knowledge`; no arbitrary Python, shell commands, subprocess dispatch, or file-writing actions. |
| Arguments | Exact envelopes and keys, unique bounded call IDs, bounded JSON argument strings, and rejection of duplicate JSON keys and unauthorized resource identifiers. |
| Loop limits | At most three completion attempts, two tool-execution rounds, and eight total calls. Further selection is disabled with `tool_choice: none`; unexpected additional calls are rejected. |
| Resource/result limits | Regular bound files checked against a 2 MiB limit; bounded diagnostics, provider responses, and serialized conversation/tool messages. |
| HTTP | TLS verification, redirects disabled, proxy discovery disabled, no automatic retries, and a 60-second network-operation timeout. This is not a hard overall wall-clock deadline. |
| Credentials | Opt-in CLI uses hidden runtime `getpass` input; no credential-file/environment loading or key arguments. Secure-entry failure aborts the CLI. |
| Provider errors | Sanitized failure codes omit raw provider error bodies and credential-bearing exception details. |

The executor is an allowlist over trusted local resources, not a sandbox against a hostile local caller or filesystem. Tool diagnostics are sent back to the external model during live orchestration. The API endpoint and model are fixed in the adapter.

The executor exposes only Tool 2's **read-only checking** capability. Tool 2 can separately create a new Markdown file through its explicit CLI, but the agent cannot invoke generation. Controlled Knowledge Generation / Phase 3 is not implemented.

## Verification Evidence

| Evidence | What it establishes |
|---|---|
| **90 offline Python tests** | 15 validator, 12 knowledge builder/checker, 29 executor, and 34 TokenProxy adapter tests. Provider responses are scripted; adapter tests exercise the real executor, while live-CLI acceptance is mocked. |
| **16 offline Node.js tests** | Eight response-helper and eight frontend-recovery tests for the separate consumer chatbot. |
| **GitHub Actions** | [Cross-platform CI](../.github/workflows/ci.yml) runs the Python/Node suites and catalogue/knowledge checks on Ubuntu, Windows, and macOS for PRs targeting `main`. The [Node workflow](../.github/workflows/tests.yml) also runs on pushes to `main`. [Run history](https://github.com/ych680/mytech-ai-assistant/actions) supplies revision-specific CI results. |
| **Manual live TokenProxy smoke test** | The maintainer reported successful execution of both tools: 27 products in nine categories validated, 27 knowledge records consistent, three API requests, and two tool rounds. |

The manual result demonstrates an actual provider/tool/result-feedback integration for the fixed request. It is separate from mocked tests and CI; it is not a real-model accuracy benchmark. Future runs may choose a different valid call sequence within the same limits.

## Reproducing Checks

Use Python 3.12. The [README's Python setup and offline commands](../README.md#python-tooling-with-uv) cover locked uv setup, all Python tests, strict dataset validation, and knowledge checking, with direct commands for an existing environment. These checks need no FastGPT or TokenProxy credentials. Initial runtime setup may require downloads.

To deliberately repeat the live demonstration from the repository root:

```sh
uv run --locked python -B -m tools.tool3_tokenproxy --live
```

Run in a terminal supporting hidden credential entry. The CLI asks for the key securely, calls TokenProxy with the fixed validation-and-consistency request, and prints structured JSON. Exit code `0` requires completed orchestration and successful records for **both** named tools; otherwise it returns `1`. Omitting `--live` displays help without credential entry or API calls.

## Prototype Limitations

- A model may answer without tools; the result reports `no_tools_executed` and `execution_status: not_run`. A completed explanation does not guarantee all requested operations were performed.
- Generated explanations can contradict tool evidence. Use structured tool results to determine what actually executed; no independent semantic fact-checker is implemented.
- The loop is bounded within one invocation, with no persistent cross-invocation conversation, general autonomous planning, or automatic repair/retry of rejected calls.
- Knowledge consistency compares local JSON and Markdown. It does not inspect the deployed FastGPT knowledge base or compare the workflow's static validation catalogue.
- There is no public production deployment or measured real-model tool-selection/task-completion accuracy. The agent preserves the classroom catalogue's 27 reference products across nine categories.
