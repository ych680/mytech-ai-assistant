# MyTech v2 — INT6137 Step 3.2 AIEP candidate

Status: isolated candidate for review, not published or live-verified. Based on
`efa65b2` (Phase1B.1), following the complete official INT6137 AIEP SKILL.md supplied
by the maintainer. The original Windows frontend, Node server, response utilities,
catalogue, reference prompt, knowledge and FastGPT workflow are unchanged.

## Upload artifact

Only `site/index.html` is intended for a later, separately authorized upload.
It contains the Editorial Clean styles, starter questions, card renderers and
unchanged 27-product / nine-category catalogue and reference prompt. The data is
inert JSON with HTML-sensitive characters escaped, loaded and validated without
asset fetches. The reference prompt is not sent upstream: the published FastGPT
application owns its prompts and model settings. No build, packages, server or
additional assets are needed. Tests enforce one upload file and a size below
2,000,000 bytes; documentation and tests must not be uploaded.

## Two runtime modes

The official `HOSTED`, `PRIVATE`, `endpoint()` and `headers()` implementations are
retained. All API requests use `endpoint("/fastgpt/v1/chat/completions")`.

| Mode | Endpoint | Authentication |
| --- | --- | --- |
| Matching AIEP project hostname | `/fastgpt/v1/chat/completions` | No browser Authorization header; AIEP injects its configured credential |
| All other origins, including double-click `file:` | `https://maas.eduhk.hk/api/v1/chat/completions` | Runtime FastGPT password input; bearer header only to this documented service |

Hosted mode never loads a saved key and hides the key panel. The page does not
probe a health endpoint or claim authentication has succeeded before a validated
response. In key mode, use the FastGPT application key associated with MyTech v2
— Current. Classroom model keys are rejected; there is no TokenProxy fallback.
No credential is embedded or shipped, and no key prefix or raw service error is
displayed. The application key identifies the FastGPT app; the page invents no
`appId` or model identifier.

Remember is available only for `file:`, `localhost` and `127.0.0.1`, with explicit
consent. Shared sites never access storage. Every storage operation is guarded;
failures leave runtime-key use working and report if a saved value could not be
updated or removed. Forget clears the in-memory key even if browser storage fails.
Key changes and Forget abort pending work and clear conversation state.

## Request and response contract

Requests contain `chatId`, `stream: false`, `max_tokens: 800` and a single current
user message. They send neither the browser's accumulated history nor constraint
maps. This preserves the original current-message-plus-ID approach; proxy support
for `chatId` and persistent FastGPT variables still requires live verification.
The guide does not document `chatId` or `appId` behavior. No history-replay fallback
is implemented. Stored browser history is capped at 16 messages and records only
validated successful turns.

Responses are read only from `choices[0].message.content`. The page accepts whole
JSON or one complete lowercase `json` fence, normalizes optional `source: null`,
then requires exactly `answer`, `recommendations`, `next_step` and
`clarification_needed`, with strict types. A truncation finish reason, prose,
reasoning wrappers, malformed content or invalid products fails safely. There is
no partial-card rendering.

Checks cover approved identity/category/exact price/source, hard budgets,
recognized usage labels, duplicate categories, active requests and comparison
targets/anchors. The original safe DOM renderer uses text nodes, including for
model text. Clarification/cancellation cannot render recommendations. Valid
no-result responses retain comparison anchors.

## Conversation changes confined to this candidate

- Targeted alternatives such as “another mouse” keep the conversation ID.
- Switching between saved Mouse and Laptop comparisons retains both categories'
  requirements and recommendation anchors.
- An ambiguous comparison remembers its intent until a category-only continuation;
  bounded cancellation clears that intent without resetting the conversation.
- Explicit new conversations, Restart and credential changes rotate the ID. A
  normal category switch alone does not rotate it.
- Restart aborts in-flight fetches; request-version checks discard late success
  and failure, including transports that ignore cancellation.

HTTP 401, 402, 403, 429 and 5xx use mode-appropriate messages. Non-JSON errors,
network failure and invalid responses are handled without raw upstream messages.
A 60-second browser deadline reports timeout separately from Restart. Controls
recover, failed turns do not enter replay history, and retries require a user
action. An interrupted request may already have updated upstream state; client
cancellation is not proof of server rollback.

## Security boundary and release blockers

Removing Node removes its independent trusted response-validation boundary,
request-size enforcement, upstream timeout and response headers. Browser checks
protect the normal rendering path but can be bypassed; they are not trusted
server validation, authentication or rate limiting.

The committed FastGPT workflow independently enforces catalogue facts, active
requests, duplicate-category checks, hard budgets and comparison constraints on
its recommendation-validation path. It also owns RAG and conversation variables.
Its parsing/normalization and usage checks are not identical to Node's, and its
clarification branches do not all pass through that recommendation validator.
Verify the published Current application rather than assuming the export proves
its runtime configuration.

Before release, separately authorize and verify:

1. AIEP Publish chatbot is mapped to Current with the intended application key;
   leave Stable Backup and its existing connection untouched.
2. The proxy preserves `chatId`, consecutive-turn memory and session isolation.
3. FastGPT accepts this request without an invented `model`/`appId`, and the
   token cap does not truncate the largest supported multi-product JSON output.
4. Actual hosted CSP/sandbox behavior, SSO/access settings, errors and platform
   rate/concurrency protections meet the intended group-testing requirements.
5. The loss of independent Node validation is accepted. Native proxy hosting alone
   does not demonstrate an equivalent trusted validation layer.

## Offline verification

The candidate suites execute its actual inline script with a minimal DOM, mocked
fetch, fake runtime credentials, manual deadlines and fake storage. They never
call a service or use a real credential. Node 24 is used for the commands below;
in-process test isolation avoids restricted-environment child-process failures.

```powershell
node --test --test-isolation=none tests/aiep-candidate.test.mjs tests/aiep-conversation.test.mjs
node --test --test-isolation=none tests/response.test.mjs tests/frontend-recovery.test.mjs tests/workflow-followup.test.mjs
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p "test_*.py" -v
.\.venv\Scripts\python.exe -B tools/validate_products.py --strict-v1
.\.venv\Scripts\python.exe -B tools/build_knowledge.py --check knowledge/MyTech_Product_Knowledge_v1.md
node --check tests/aiep-candidate.test.mjs
node --check tests/aiep-conversation.test.mjs
git diff --check
```

The candidate test also compiles its inline script and checks unchanged original
styles/renderers, exact embedded reference data, routes, storage exceptions,
errors, strict validation, starter buttons and cards. These mocked checks do not
prove real browser layout, live proxy compatibility or real-model quality. The
existing CI files are intentionally unchanged; run candidate suites explicitly.

## Later manual acceptance and evaluation

No live requests, credential setup or publishing are part of Step 3.2.
After separate authorization, test the single file by double-clicking it, then
test the published AIEP mode. Replay approved T01 / T06 / T07 / T08 / T09 / T10 /
T11 through the complete page using the original scripts and expected outcomes.
Check all starters, single/multiple cards, constraints, ambiguous continuations,
cancellation, restart/key changes during requests, invalid responses, timeout,
keyboard focus and 360 px width. Inspect browser requests without copying keys
into reports. Hosted requests must have no Authorization header.

Use the published site's `/_eval/` with the FastGPT preset for separate workflow
evaluation. The official guide explicitly says it directly calls the chat route
and does not execute this page's JavaScript. Its results cannot verify cards,
browser state, storage, transport adaptation or UI recovery. The preset requests
`detail: true`; AI judging additionally requires TokenProxy, and evaluator removal
of reasoning blocks can mask a difference from this page's strict parser. Use
explicit checks and preserve browser E2E evidence separately.

If candidate acceptance fails, leave it unpublished or revert the shared entry
point to the independently retained Stable Backup deployment. Start fresh
conversations on rollback. Do not overwrite the legacy application or credential.
