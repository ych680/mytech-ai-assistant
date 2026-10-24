# MyTech v2.1 TEST performance and local frontend integration

Latest work: [targeted LLM latency optimization](v21-targeted-llm-latency.md).
Only two TEST instruction strings change; graph/bindings/history/models/evidence
stay unchanged. The linked report includes reproducible size estimates, full
regression results and A/B scenarios; no runtime speedup is claimed.

Subsequent change: [State Extraction reliability fix](v21-state-extraction-reliability.md).
TEST now adds one deterministic input node before extraction (20 nodes / 18
edges), a bounded scope consistency guard and extraction guidance. The 19/17
structure and overlay inventory below record the earlier performance workstream.
The launch commands and TEST-only API configuration remain applicable.

Local work on `feat/v21-automated-catalogue`. No Current/stable source, Master
Dataset, credential file, hosted deployment or live application was changed.
No live FastGPT request, commit, push, merge or deployment was performed.
All 27 added candidates remain provisional/unverified and TEST-only.

## Audit findings and parameter synchronization

The authoritative portable Current snapshot still has 19 nodes, 17 edges and
five global variables. The TEST generator previously inherited similarity 0.40.
`tools/templates/v21_test_settings.json` now explicitly sets 0.35; the generator
rejects any other value rather than silently reverting. The manifest records
these settings. Byte-exact check mode detects stale/modified assets without
writing; regression tests reject changing the generated threshold back to 0.40.

Four parameter values and the existing v2.1 validator overlay are the only
workflow differences from the portable Current template:

| Node / parameter | Portable Current | Generated TEST |
| --- | --- | --- |
| Retrieval `similarity` | 0.40 | 0.35 |
| Clarification `aiChatReasoning` | true | false |
| Clarification `maxToken` | unset | 800 |
| Recommendation `maxToken` | unset | 4096 |

Every original node/output ID, edge, global schema/default, reference,
variable-update input, condition, interpolation, prompt and code node outside
the validator is preserved. Tests compare the entire graph with exactly these
allowlisted overlays. Retrieval still uses native version 4.9.2 with
`userChatInput = ["sxwN5Fd17Tc8leTf", "qLUQfhG0ILRX"]`. Search mode remains
`embedding`, retrieval limit 5000, reranking and query extension disabled.
Individual node versions do not establish a server version.

## Latency evidence and safe changes

The only cloud timing evidence available is the reported 30–70 seconds per
turn. There is no local execution trace separating extraction, retrieval,
clarification or recommendation durations. Attribution below describes likely
cost contributors, not measured cloud bottlenecks.

| Stage | Audited configuration | Action / reason |
| --- | --- | --- |
| State Extraction | 10,368-character instructions; history 6 | Preserve extraction/multi-request/follow-up rules; select a fast structured-output model manually |
| Clarification | 2,153-character prompt; history 6; reasoning true | Disable reasoning, cap output at 800; retain all required-field and follow-up logic |
| Recommendation | 11,087-character prompt; history 6; reasoning false | Keep quality baseline and grounding; bound native output at 4096 for multi-product JSON |
| Retrieval | Limit 5000, embedding search, no rerank/extension | Sync proven similarity 0.35; retain the rest |
| Local adapter | Compile VM script and load catalogue once | Reuse for requests; validation is small local work in the offline measurement |
| Stable frontend/server | 60-second deadlines | Stable unchanged; isolated TEST server defaults to 120 seconds, browser allows 5 seconds of local overhead |
| TEST UI | Minimum thinking indicator 1 second | Retain behavior; delay overlaps the request and adds no 1-second suffix to a long response |

No prompts or history windows were shortened blindly. Token caps are explicit
limits, not evidence of reduced latency; original model defaults are unknown.
The browser request `max_tokens` rises from 800 to 4096 to avoid truncating
multi-product JSON. A length-truncated response is rejected. Lower similarity
may increase retrieved context. Longer deadlines prevent premature cancellation
but are not a speed improvement. School/gateway deadlines may still be shorter.

Model selection remains manual and account-specific bindings stay empty:

1. State Extraction: choose an available fast lightweight model that passes
   structured extraction, multiple requests, budget updates, pending comparison
   target resolution and cancellation tests. Do not choose by latency alone.
2. Clarification: choose an available lightweight instruction model, with
   reasoning off. Check four-field JSON, missing fields and recovery.
3. Recommendation: retain **glm-4.7 as the quality baseline if available** in
   the TEST app. Compare alternatives only against the same grounded scenarios,
   hard budgets, usage checks and follow-up memory protections.

No replacement model is assumed available. Portable files contain role guidance
in the manifest but no concrete account model IDs. Offline fixtures cannot
measure model quality, live structured extraction or any model's latency.

`Server-Timing` reports upstream (all remote workflow stages combined), local
validation and total milliseconds on successful responses. Optional
`MYTECH_TEST_TIMINGS=1` logs only status and three durations, including failures.
The browser emits `mytech:test-timing` events with only phase, duration and
status. No message, chat ID, product, key, endpoint, response body or reasoning
is included. Upstream requests use `detail:false`; only final message content
is parsed and only the validated four-field contract is returned.

Offline microbenchmark on this machine, 200 validations after 20 warmups:
startup 1.092 ms, median 0.472 ms, p95 0.595 ms. Reproduce with
`node tools/benchmark_v21.mjs`. This excludes network, extraction, retrieval and
model execution and is not an end-to-end speedup measurement.

## Independent local launch

The shared-file setup and exact macOS/Windows migration steps are in
[local workspace configuration](local-workspace.md). Phase 2B consolidation and
local startup succeeded in this checkout. Launch with
`node --env-file=.env mytech_v2_1_test_server.mjs`. The retained `.env.v21.test`
and `.env2` are retired configurations for recovery/final review, not normal
launch sources. Node loads the selected file; the server itself has no dotenv
loader and never falls back to legacy credentials. Other checkouts must supply
their own independently verified private configuration.

For offline assets-only launch from an existing repository checkout with Python
environment and Node available, check existing generated assets without rewriting:

```sh
cd ~/Desktop/mytech-ai-assistant
.venv/bin/python -B tools/check_catalogue_consistency.py
node mytech_v2_1_test_server.mjs
```

Open **http://127.0.0.1:8788/**. Without explicit TEST settings this serves the
54-product page but disables sends and returns 503 on the TEST API route.
No request is made upstream at startup. This command never loads `.env` and
ignores `FASTGPT_*`, `PORT` and all stable server settings. Opening an HTML file
directly is not a substitute for this server.

To connect later, a human must configure an independently verified TEST app
endpoint and TEST credential in the ignored private `.env` after approved
migration (or an explicitly selected private file/secret manager beforehand),
without putting secrets in command arguments, HTML or tracked repository files:

| Environment variable | Purpose |
| --- | --- |
| `MYTECH_TEST_FASTGPT_API_URL` | Full HTTPS chat-completions URL, no userinfo/query/fragment |
| `MYTECH_TEST_FASTGPT_API_KEY` | TEST credential, server-side only |
| `MYTECH_TEST_FASTGPT_BINDING` | Explicit `app-key` or `app-id` |
| `MYTECH_TEST_FASTGPT_APP_ID` | Required only in `app-id` mode; omitted in `app-key` mode |
| `MYTECH_TEST_PORT` | Optional loopback port; default 8788 |
| `MYTECH_TEST_REQUEST_TIMEOUT_MS` | Optional 5000–300000; default 120000 |
| `MYTECH_TEST_MAX_TOKENS` | Optional 256–8192; default 4096 |
| `MYTECH_TEST_TIMINGS` | Optional `1` for safe timing logs |

After approved shared-file setup, run
`node --env-file=.env mytech_v2_1_test_server.mjs`.
In app-key mode, the key itself must belong to the isolated TEST app;
in app-id mode the server explicitly sends the configured TEST app ID too.
The server cannot prove remotely that a human-provided key points to TEST.
Partial/ambiguous bindings fail startup; there is no stable fallback. Values
are never returned in browser config, logs or error responses.

The browser first reads same-origin `/api/test/config` and then POSTs to
`/api/test/mytech`. The server sends only the current user message and chat ID
upstream, with `stream:false`, bounded `max_tokens`, and `detail:false`. Browser
history/constraints are local validation data and are not replayed as messages.
The existing school-hosted route remains `/fastgpt/v1/chat/completions`, using
the supported school proxy/authentication flow. A **separate TEST proxy/app
binding must be established manually** before any hosted use; the stable proxy
must not be assumed to point to TEST. No hosted route was changed or tested.

## Validation, UI and state

The server serves only the allowlisted page/catalogue, binds to 127.0.0.1 and
rejects cross-origin POSTs/invalid Host headers. It verifies asset hashes and
deep equality with the Master Dataset before listening. Catalogue size derives
from the Master and manifest; temporary 55th-product fixtures still regenerate
all consumers. Do not edit generated files by hand.

Node validation reuses the generated FastGPT validator plus strict public-shape
preflight; the frontend embeds the same reviewed usage helper/policy. Both
require exact identity, category, numeric reference price and source, complete
positive hard budgets and supported usages. Unknown/unsupported usages fail.
Multiple recommendations are validated as a batch. Comparison direction and
target scope remain enforced. Server-held validated anchors override untrusted
browser anchor hints; invalid replies/help/clarification do not replace them.
One turn per chat runs at once. Restart rotates the chat ID, clears UI history
and context, and aborts the old request. Errors preserve prior approved cards
and support the existing edit/retry interaction.

The CSS, Editorial Clean design and card structure are unchanged. Product facts
and source cards always come from the catalogue. Citation cleanup happens only
after complete JSON parsing, only in display copies of `answer`, `next_step`
and `reason`. Recognized `[citation:n]`, `【n†source】` and citation-delimiter
markers are hidden; bare `[1]`, numbers and all identity/category/price/source
fields remain unchanged. Original validated text stays in conversation history,
retaining provenance markers. Both raw and cleaned copies must validate, so a
marker cannot disguise a prohibited live-price claim. Unknown markers are left
intact rather than stripped with a broad heuristic.

## Verification and limits

Final local results: **253 Python tests and 256 Node tests passed**, with zero
failures, skips or cancellations. Strict-v1 validation (27 products), TEST
validation (54 products), v1 knowledge consistency, both generated-asset check
commands, Node syntax and whitespace checks passed. The HTTP suite exercised a
real loopback listener with mocked upstream responses, including a five-second
timeout. Checksums matched all nine protected pre-work inputs: stable workflow,
dataset, server, response module, AIEP page, HTML, v1 knowledge, Master Dataset
and portable Current template.

Run offline checks:

```sh
.venv/bin/python -B -m unittest discover -s tests -p 'test_*.py'
node --test tests/*.test.mjs
.venv/bin/python -B tools/validate_products.py --strict-v1
.venv/bin/python -B tools/validate_products.py --dataset catalogue/mytech_products_v2_1_test.json --test-v21
.venv/bin/python -B tools/build_knowledge.py --check knowledge/MyTech_Product_Knowledge_v1.md
.venv/bin/python -B tools/sync_catalogue.py --check
.venv/bin/python -B tools/check_catalogue_consistency.py
```

The local HTTP tests use real loopback sockets with an injected mock upstream;
they never contact FastGPT. Frontend tests execute the generated script in a
minimal DOM harness, not a visual browser. Existing strict-v1 tests remain
unchanged. Determinism, stale-output detection, all Master facts, every usage
tag, compound/unknown usages, initial/follow-up safety, 55th-product expansion,
native graph references, routing, recovery, citation handling, timeout and memory
protection are checked.

Remaining risks: live model/extraction behavior, school endpoint/app-key
semantics, platform timeout limits, remote persistence and hosted auth require
later isolated TEST verification. A locally aborted request may already have
committed remotely; the local server cannot roll back remote FastGPT state.
Local comparison memory is bounded to 200 chats and expires after an hour of
inactivity; after a server restart/expiry, start a new UI conversation rather
than continuing remote history without local anchors. This loopback host is not
a public deployment. No FastGPT runtime/import compatibility or cloud speedup
is claimed from these offline checks.

## File inventory for this workstream

Modified: `tools/sync_catalogue.py`, `tests/test_catalogue_sync.py`,
`tests/test_workflow_import_contract.py`, `tests/catalogue-v21.test.mjs`,
`.github/workflows/ci.yml`, `README.md`, `docs/v21-catalogue-sync.md`,
`docs/v21-current-baseline-rebuild.md`.

Added: `tools/templates/v21_test_settings.json`,
`tools/templates/v21_frontend_runtime.js`, `mytech_v2_1_test_server.mjs`,
`mytech_v2_1_test_response.mjs`, `tools/benchmark_v21.mjs`,
`tests/local-v21.test.mjs`, and this report.

Regenerated with changed bytes: `generated/v2_1_test/index.html`,
`generated/v2_1_test/mytech-fastgpt-workflow-v2_1-TEST.json`,
`generated/v2_1_test/manifest.json`. The generated catalogue JSON and RAG Markdown,
Master Dataset, portable Current snapshot and all stable sources are unchanged.
