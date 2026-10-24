# MyTech v2.1 — separate AIEP TEST deployment candidate

Current status (2026-10-24): the maintainer confirms successful university AIEP
deployment and connection to the published **Original** application,
`MyTech v2.1 — TEST Knowledge`. The optimized GLM-4.7 app is experimental and is
not the AIEP default. See the [current registry](../workflow/v2.1/registry.json).
The preparation/browser-origin report below is historical; its earlier UNVERIFIED
status and the generated manifest are preserved as dated preparation evidence.
Repository integration did not redeploy, call FastGPT or independently inspect
the platform, and the exports still omit KB selections/published revision evidence.

Prepared on 2026-10-24 (Asia/Hong_Kong), on `feat/v21-automated-catalogue`.
Status: **browser-origin fix regenerated locally; stopped for review**.
The user reports the previous candidate was uploaded and Chrome rejected a
request to `https://project-emi-10.aidcec-ai-agent.com/fastgpt/v1/chat/completions`
because its request origin is `null`. No upload, live app API call or console
inspection was performed during this fix. This user-reported hostname does not
establish the project's FastGPT application binding.
**AIEP → published MyTech v2.1 TEST binding: UNVERIFIED.**

## Exact upload directory

```text
/Users/chenyupeng/Desktop/mytech-ai-assistant/generated/aiep_v2_1_test/site/
└── index.html
```

Upload the contents of `site/` with `index.html` at the hosted root. The file is
105,527 bytes. No Node/Python server, packages, build command, external assets,
environment files, credentials or local server are required. The parent manifest
and these instructions are review artifacts and must stay outside the upload.
Do not upload `aiep-candidate/site/` (the preserved v2 candidate),
`generated/v2_1_test/` (the local TEST assets and experimental workflow export),
or the repository root. If an uploader accepts only archives, zip only the
single `index.html` at archive root after approval; no archive is needed for
directory/file upload.

The [manifest](../generated/aiep_v2_1_test/manifest.json) records the upload hash,
Master hash, product count, generator/template hashes and unverified binding.
The [preservation snapshot](v21-aiep-test-preservation.json) records 18 existing
non-secret files that remained byte-identical throughout this preparation.

## What the candidate preserves

The generator reuses the working local TEST frontend renderer and embeds the
complete Master Dataset: 54 products across nine categories, including the 27
provisional/unverified additions. It derives the embedded dataset contract,
usage lookup and manifest count from that Master. Product card specifications,
prices, tiers and sources come from the catalogue. The TEST-only/provisional
notice remains visible. The Editorial Clean CSS and card renderer are identical
to the working local TEST page.

Strict checks retain exact product identity, category, numeric reference price,
source, known compatible usage, complete positive hard budgets, active request
scope, comparison direction/anchors and duplicate-category rejection. An invalid
recommendation rejects the entire returned batch. Clarification, cancellation
and ambiguous comparisons cannot display products. No-result replies retain
validated anchors. Citation cleanup changes display copies only; it cannot
repair malformed JSON or change product facts. The embedded reference prompt
is inert; it is never sent to FastGPT.

Conversation IDs, per-category requirements/anchors, targeted follow-ups,
pending comparison resolution, bounded cancellation, 16-message local history,
restart and edit/retry recovery remain intact. Restart aborts pending work,
rotates the ID and discards late replies. There are no automatic retries. Browser
history and constraint maps are used for local validation and are not replayed
upstream. FastGPT must maintain its own state using `chatId`.

## Hosted transport and application binding

The only request is a POST to the project-relative proxy route
`/fastgpt/v1/chat/completions`, permitted only on HTTPS project hostnames matching
the existing AIEP convention: `project-(cmi|emi|demo)-NN.aidcec-ai-agent.com`.
The URL-host check does not establish the document's security origin. Local
files, loopback hosts, HTTP and unrelated hosts disable sending; initialization
makes no request. An offline file preview
is therefore intentionally disconnected.

Requests contain only `chatId`, `stream:false`, `detail:false`, `max_tokens:4096`
and the current user message. The 120-second browser deadline and 4096 token cap
match the local TEST defaults. These do not alter published workflow settings
or prove the proxy has an equivalent deadline. Redirects are rejected. Like the
legacy AIEP request, fetch leaves `mode` and `credentials` unspecified (defaults:
`cors` and `same-origin` respectively). The browser sends no Authorization header,
key, `appId`, model selector or prompt. Browser key entry, storage and direct
external-provider fallbacks have been removed.

**Application selection happens in the AIEP project's server-side FastGPT
connection.** The existing v2 integration documents an AIEP-injected application
credential. A route name, page title, catalogue, manifest, `chatId` or a “Ready to
Connect” label cannot select or prove the connected application. A project using
a Current/v2 credential would still call that app. A 54-product browser page
cannot upgrade its server workflow or knowledge base. The manifest is evidence
for the local artifact, not a runtime binding mechanism.

Evidence: [v2 hosted routing contract](../aiep-candidate/README.md),
[local TEST binding contract](v21-performance-and-local-test.md), and the
candidate's [generated transport](../tools/templates/v21_aiep_transport.js).
No AIEP console or live configuration was accessed. The repository does not
include current console screenshots/full operator guide; the steps below specify
the required settings and evidence without assuming an application dropdown or
inventing a new browser `appId` contract.

## Browser-origin fix and remaining platform requirements

The exact regression was in `tools/build_aiep_test.py`, which inserted
`mode: "same-origin"` and `credentials: "same-origin"` after `method: "POST"`.
The prior generated file had those options at lines 1683–1684. The legacy
`aiep-candidate/site/index.html` request does not specify either option. The
builder now omits both, retaining the relative proxy route, JSON headers/body,
abort signal and `redirect: "error"`. The generated HTML diff contains only
those two removed lines; no catalogue, UI, validation or state code changed.
The transport/runtime templates were inspected and need no functional change.

A sandboxed document can have an opaque security origin even when its URL
resolves on the project hostname. Explicit `same-origin` mode rejects that
request outright. Default `cors` mode allows the browser to evaluate CORS;
it does not grant access. A cross-origin JSON POST needs successful preflight
and response CORS permission. Default credentials do not send cookies on
cross-origin requests. See [MDN Fetch defaults and CORS](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API/Using_Fetch#making_cross-origin_requests)
and [sandbox origin behavior](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/iframe#sandbox).

If the replacement still fails, AIEP support must establish a supported execution
and proxy path for this project: either a page served with the intended origin,
or a supported isolated request bridge/proxy with appropriate authentication and
CORS. For the reported `null` origin, support must check the JSON POST's
`OPTIONS` preflight (POST and `content-type` permission), response CORS headers,
project-scoped authorization and CSP `connect-src` policy. The existing default
cookie behavior may prevent authentication from an opaque document. A parent
sandbox or server CSP cannot be fixed by editing this child's fetch options.
If the platform instead runs `about:srcdoc` with no project location, the existing
host guard will disable sends; AIEP must provide its supported project route or
bridge contract before a reviewed adaptation can be made.

Do not use `no-cors` (its opaque response cannot be parsed or validated), add
client keys/Authorization or force `credentials: "include"` speculatively.
Do not disable browser security, weaken the parent sandbox, or broadly allow
`Origin: null`/all origins on an authenticated proxy as a client-side workaround.
Hard-coding the absolute project URL also does not change the document's origin.
Keep the project-to-published-TEST binding gate separate from CORS acceptance.

Offline tests verify request configuration and safe failure, not real browser
CORS or hosted compatibility. After approval, a later operator can inspect the
frame URL/origin, sandbox/CSP and sanitized OPTIONS/POST status/CORS headers.
Do not export cookies, tokens or Authorization values. No such live requests,
header captures or platform changes were performed during this fix.

## Later operator procedure — after review and separate authorization

1. **Identify the working published TEST app first.** In the FastGPT workspace,
   open the existing MyTech v2.1 TEST application used by the working local TEST
   setup. Record its non-secret application name/identifier and existing
   publication time/revision, if shown. Distinguish it from Current, Stable
   Backup, any duplicate TEST names and unpublished drafts. The operator must
   establish that the provisioned application credential belongs to this exact
   app; a display name alone is insufficient.
2. **Keep its current publication.** Do not import a workflow, edit prompts,
   rebind knowledge/models, save workflow changes or republish it. In particular,
   do not import `generated/v2_1_test/mytech-fastgpt-workflow-v2_1-TEST.json`:
   that local artifact includes shortened prompts awaiting live A/B verification.
   This AIEP candidate intentionally ships no workflow export or knowledge import.
3. **Create a separate AIEP project.** From the AIEP project dashboard, use the
   new-project operation, give it a distinct label such as “MyTech v2.1 TEST”,
   and allocate a new project/site hostname. Do not replace, duplicate over,
   rename, reconnect or upload into the existing v2 project. Record the new
   project identifier/hostname and existing v2 classroom URL separately. If no
   spare project or per-project connection is available, stop before upload.
4. **Set the new project's FastGPT connection in “Publish chatbot”.** Where an
   application selector is offered, select the exact TEST app identified in
   step 1 and check its identifier. Where AIEP takes an application API key,
   the operator supplies the already provisioned key for that exact TEST app
   through AIEP's protected server-side connection form/secret facility. This
   application-scoped credential is the selection mechanism; a classroom model
   key, TokenProxy key or Current credential is unsuitable. Do not put any key
   in the upload, source, browser code, URL, report, chat or screenshot. Do not
   change the local TEST credential/configuration. If the console exposes only
   a global/shared FastGPT binding, stop; changing it could affect v2.
5. **Review the connection before uploading.** Check the new AIEP project ID and
   target TEST app identity with the operator. Keep a sanitized record of which
   app owns the connection, its existing publication revision/time and the
   separate hostname. Mask credential fields and omit all key material. If the
   console cannot show the app identity, use the credential's ownership in the
   selected FastGPT app as operator evidence; do not treat a successful HTTP
   response or a plausible product as identity proof. Record configuration
   confirmation separately from later runtime verification.
6. **Upload the single file into the new project only.** Use the project's static
   file upload and select exactly `generated/aiep_v2_1_test/site/index.html`.
   Confirm it will be served as `/index.html` or the root `/`. Retain the new
   project's intended classroom access/SSO restrictions. If the allocated
   hostname does not match the supported HTTPS convention, stop for a reviewed
   transport update instead of widening the origin rule ad hoc. Re-run offline
   checks after any source change.
7. **Verify the final preview/target, then publish only with approval.** Confirm
   both destination and connection belong to the new project. Publication and
   model-credit-consuming smoke tests are outside this preparation. Do not
   change the classroom entry link until separately authorized live acceptance
   succeeds. Keep the existing v2 URL available throughout.

## Deployment checklist

- [x] Separate upload directory contains exactly one self-contained HTML file.
- [x] 54-product Master, provisional labels, shared usage policy and exact facts
  retained; generator and unified consistency checker cover the AIEP candidate.
- [x] Editorial Clean CSS/card renderer preserved byte-for-byte against local TEST.
- [x] Offline strict response, budget/usage/source, multi-product, follow-up,
  restart, timeout and safe recovery tests passed.
- [x] Original AIEP v2, stable sources, Master and existing local TEST generated
  assets remained byte-identical; no workflow was imported or published.
- [x] Public deployment assets and changed deployment tooling reviewed/scanned
  for accidental credentials. No environment/secret files were read.
- [x] No real API request, credit use, deployment, commit, push or merge performed.
- [ ] Separate TEST project identity and isolation independently confirmed;
  the user reports requests to `project-emi-10.aidcec-ai-agent.com`.
- [ ] **UNVERIFIED: its project-scoped FastGPT connection selects the exact
  currently published MyTech v2.1 TEST application.** Record sanitized evidence.
- [ ] Current, v2/Stable Backup and the working TEST publication/configuration
  confirmed untouched by the later operator setup.
- [ ] Later authorized live smoke checks verify final-content envelope,
  `detail:false`, 4096-token multi-product completion, `chatId` persistence,
  session isolation, hosted access/CSP, sandbox/CORS and cookie/authentication
  behavior, actual gateway deadline and error recovery. Removing the fetch mode
  restriction alone does not establish these.
- [ ] Later browser QA at desktop and 360px width checks cards, keyboard focus,
  starter buttons and the longer TEST notice. No browser was available during
  preparation; offline DOM tests and exact CSS equality do not prove layout.
- [ ] Later acceptance passes; only then approve any classroom link change.

Suggested later manual acceptance sequence (each request may consume credits):
ask for a Study laptop under RMB 6000 plus a Gaming mouse under RMB 300; confirm
both independently; ask “Cheaper mouse”, “Another laptop”, “Anything cheaper?”
then a category-only reply; cancel a pending comparison; ask ambiguous “better”;
use a no-match budget; Restart during a pending request; repeat in an independent
browser session. Check exact returned source/price and that no over-budget or
wrong-usage product appears. Include a case that can exercise an added TEST
product, but use app/credential identity evidence to establish the binding.
Inspect requests without exporting credential-bearing logs: route must be the
project's `/fastgpt/v1/chat/completions` proxy, one current message, no browser
Authorization, no local path. A relative route may still be cross-origin from
an opaque sandbox.
The platform `/_eval/` route alone cannot validate this page's DOM or state.

## Offline commands and evidence

To rebuild **only** this hosted candidate (no local workflow generation):

```sh
.venv/bin/python -B tools/build_aiep_test.py
.venv/bin/python -B tools/build_aiep_test.py --check
```

The existing `sync_catalogue.py` now generates both local TEST and hosted AIEP
outputs; `check_catalogue_consistency.py` checks both, without repairing files.
Use the hosted-only builder for this deployment preparation so the local
experimental workflow export need not be regenerated. Do not edit generated HTML.

```sh
.venv/bin/python -B -m unittest discover -s tests -p 'test_*.py' -v
node --test --test-isolation=none tests/*.test.mjs
.venv/bin/python -B tools/validate_products.py --strict-v1
.venv/bin/python -B tools/build_knowledge.py --check knowledge/MyTech_Product_Knowledge_v1.md
.venv/bin/python -B tools/check_catalogue_consistency.py
.venv/bin/python -B tools/build_aiep_test.py --check
git diff --check
```

Python 3.12.15 / Node 24.21.0: **269 Python tests and 306 Node tests passed**,
including 9 AIEP build tests and 27 AIEP runtime tests. Strict-v1 passed
(27 products / nine categories); stable knowledge check and both 54-product
consistency checks passed. Eight local HTTP integration tests initially could
not bind loopback under the sandbox; the entire Node suite passed after allowing
local listeners, with upstream transports mocked. No external model was called.
CI's existing catalogue step now covers the separate hosted output too.

The runtime suite executes the actual generated inline JavaScript with a mock
DOM and fetch. It accepts all 54 exact catalogue identities with compatible
usage/budget guards; rejects altered facts, missing sources, unsupported usages,
unknown products and unsafe batches; exercises multi-category anchors and late
success/failure after Restart. Two browser-request regressions check the actual
generated fetch options under a simulated `null` document origin, resolve the
relative route to the reported project with an offline `Request` constructor,
verify default CORS mode/no credential override, compare legacy defaults, and
check safe recovery from a simulated platform CORS rejection. No browser CORS
engine or live proxy is exercised. Build tests include a temporary 55th product,
HTML-safe embedding, deterministic generation, stale read-only checks, extra
upload files, symlink rejection and synthetic credential patterns.

The credential scanner reads only public candidate text, reports rule names and
line numbers without matched values, and rejects generation on recognized token,
private-key, literal-credential, URL-credential, AWS-key and JWT patterns. Manual
review also confirms that the candidate contains no credential input/storage or
external fallback. This bounded scan does not certify every possible secret form.

Browser validation is bypassable and is not a trusted replacement for the local
Node validator. AIEP must connect to the published TEST workflow that independently
enforces the 54-product validation contract. Offline fixtures cannot establish
that deployment's knowledge, prompts, models, state persistence or quality.

## Rollback

Before publishing, retain the existing v2 classroom URL and its deployed upload
backup/revision through the platform's normal export/history facility, without
exporting secrets. The unchanged `aiep-candidate/site/index.html` is a v2 source
reference; it is not proof of the exact current hosted revision.

If binding is uncertain, validation fails or the demo is unreliable, leave the
new project unpublished or stop sharing its TEST URL. The existing v2 project
continues to serve its original URL and server-side connection. Do not repoint
the existing project's proxy or change any FastGPT publication as a workaround.

If a classroom link was later changed, restore that link to the retained v2/
Stable Backup URL. Open a fresh conversation; TEST and v2 have different catalogue
contracts and must not share chat IDs/state. If the new TEST project already has
an accepted prior revision, restore its saved static upload revision only; keep
the verified TEST app connection and published workflow unchanged. If no prior
TEST revision exists, unpublish or restrict the new project after authorization
and use the retained v2 URL. No backend workflow rollback is required by this
candidate because it makes no backend changes.

Local candidate cleanup is limited to `generated/aiep_v2_1_test/` after review;
do not use `git reset --hard`, blanket clean commands or remove other uncommitted
v2.1 work. No cleanup, rollback, upload or live setup was executed in this task.
