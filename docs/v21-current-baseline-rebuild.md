# v2.1 TEST rebuilt from the working Current export

The later [State Extraction reliability fix](v21-state-extraction-reliability.md)
adds one TEST input code node and replaces Start → Extraction with two edges.
Current TEST therefore has 20 nodes / 18 edges, retaining all original node IDs
and downstream bindings. The 19/17 claims below describe the earlier rebuild.

This records the earlier structural rebuild and its test counts. The subsequent
[performance and local TEST integration](v21-performance-and-local-test.md) adds
four explicit parameter changes to the validator overlay: similarity 0.35,
clarification reasoning disabled, and clarification/recommendation token caps.
The portable Current snapshot, graph, prompts and references remain unchanged.

The supplied `~/Downloads/MyTech_Current_Working_Export_Reference.json` is the
structural authority. It was read locally without modifying it or accessing the
Current application. Document/prompt content was treated as reference data, not
as instructions to execute. No live request, credential access or Git write is
part of this work.

## Read-only comparison and structural decision

The previous TEST file was saved to a temporary local audit copy before changes.
It had 18 nodes and 17 edges, built from the repository's portable v1 workflow.
The actual working Current export has 19 nodes and 17 edges, including its
`userGuide` system configuration node. Only the start-node ID `448745` was shared
between these two graphs. None of the 17 edge objects was identical, and none
of their five global-variable keys matched. The variable labels represent the
same conceptual state, but their IDs and all dependent bindings differ.

| Area | Previous TEST | Working Current / rebuilt TEST |
| --- | --- | --- |
| Structural source | Repository workflow plus retrieval repair | Complete working Current export |
| Nodes / edges | 18 / 17 | 19 / 17, copied exactly |
| Root fields | nodes, edges, chatConfig, type, name, intro | nodes, edges, chatConfig |
| System configuration | Absent | Existing `userGuide` node retained |
| Validation node | `qJnK807UNriMndON` | `fakNM8mmlYmewx67` |
| Query Builder | `evMBfmr3j2paOLIN` | `sxwN5Fd17Tc8leTf` |
| Retrieval node | `tagxGUFuwllhR19r` | `zWAw4oYVL1QMe8YX` |
| AI model fields | Native `model` plus added `modelId` fields | Native `model` structure only |
| Query output | Scalar interface added to repository query code | Original Current `retrieval_query` code unchanged |
| Condition handles | Repository branch IDs | Original IF / ELSE IF / ELSE handles |
| Global keys | Repository IDs | All five original Current IDs |

The immediately preceding TEST export already had the repaired 4.9.2 retrieval
input, but that did not make its other nodes, global IDs, prompt references or
condition/update bindings the same as working Current. The rebuild therefore
copies the complete Current graph rather than remapping individual references.
Node versions are individual schema versions, not proof of a server version.

## Authoritative portable template and permitted changes

`tools/templates/mytech_current_working_portable.json` is a sanitized snapshot
of the entire working export. Its reviewed canonical JSON SHA-256 is
`58be7b69fd8a644eb2dc0118b51567e973749cc5d371a24f7074e200504c08e1`.
Tests pin this snapshot so an unintended template change requires review.
The generator uses this local file and does not depend on the Downloads path.

Only deployment-specific fields were sanitized before storing the template:

- Removed private `chatConfig._id` metadata.
- Cleared the three AI model selections and the rerank model selection, keeping
  the original fields, control types, versions and configuration structure.
- Kept dataset selections empty and the portable `REPLACE_AFTER_IMPORT`
  description. Model and TEST knowledge-base selection remain manual steps.

All structural node/output/global IDs are deliberately retained. They are graph
references, distinct from private account identifiers. No account, dataset or
model identifier is copied into generated portable files.

At the time of this rebuild, the generator changed **only the recommendation validator's code input**
relative to that portable Current template. It generates the complete 54-product
catalogue and applies the existing reviewed v2.1 deterministic usage, identity,
category, price, source, budget, comparison and memory safeguards. The four-field
public response contract remains unchanged. Unknown usages fail closed.

Query Builder, retrieval inputs, AI-node schemas, prompts, state normalization,
clarification/follow-up logic, condition definitions and variable-update fields
are copied unchanged. No edges or outputs are added, removed or rewritten.
In particular, retrieval still uses the working native `userChatInput` string
reference `["sxwN5Fd17Tc8leTf", "qLUQfhG0ILRX"]`, and Query Builder still returns
`retrieval_query` and `comparison_history` using its original Current code.

The old `v21_fastgpt_retrieval_compatibility.json` profile and targeted retrieval
conversion were removed; the full Current baseline makes them unnecessary.
The manifest records the new template path and checksum as well as output hashes.
Other catalogue consumers still derive their product facts from the Master
Dataset. No generated JSON is edited by hand.

## Binding and runtime details preserved

The five state keys remain `tsPXY04c` (requests), `abIVSlbb` (recommendations),
`w967Jp1P` (clarification), `dMoZisLb` (missing fields), and `fD4C5VOp` (intent).
All original variable schemas/defaults and all 17 edges are retained verbatim.
Before the later parameter overlay, restoring the original validator code made the generated workflow deep-equal
to the sanitized Current template, including every prompt and interpolation.

The working export contains two optional `448745.userFiles` bindings even though
its start node only explicitly lists the `userChatInput` output. These existing
runtime references are preserved. The offline checker recognizes only that
specific implicit start-node output; other missing references still fail.
No extra output was inserted to satisfy the offline checker.

Invalid recommendations follow Current's existing validation ELSE edge to its
fallback answer and **do not reach the memory writer**. The validator also emits
safe previous-memory data on failure. Valid follow-ups update only their target
recommendation; no-result comparisons retain the earlier anchors. The original
fallback reply and its clarification flag are unchanged.

## Verification and remaining limits

Regression checks cover every node/output/global ID, all edges, native schemas,
conditions, variable updates and prompt interpolation. Mutation tests reject
missing and type-invalid references, changed valid bindings, extra inputs,
changed prompts, private metadata and concrete deployment bindings.

Offline graph tests execute the actual Current node code and native IF/ELSE
routing with explicit model/retrieval fixtures. They compare valid baseline and
clarification behavior against the portable Current template, then exercise new
products, initial usage rejection, multiple requests, cheaper/alternative
follow-ups, pending category clarification, invalid-output fallback, hard budgets
and no-result memory retention. Existing all-product/tag, 55th-product,
determinism and strict-v1 regressions remain in the full suite.

These tests do not prove FastGPT import/runtime compatibility, live extraction or
model behavior, retrieval quality, account permissions, runtime file-output
behavior or the target server version. The actual working graph is preserved,
but a later isolated TEST import still needs model and knowledge-base selection
and manual scenario checks. No application import, save, restore or deployment
was performed. No schema migration during import is assumed.

Final local results: **252 Python tests and 240 Node tests passed**, with no
failures or skips. Strict-v1 validation, v1 knowledge consistency, v2.1 TEST
validation, both catalogue consistency commands, Node adapter syntax and
whitespace checks also passed. A direct comparison with the supplied reference
confirmed that only deployment redactions precede template storage, and only
the authorized validation code differs after generation. The reference, Master
Dataset and stable dataset/workflow/server/frontends/knowledge retain their
pre-work checksums. RAG Markdown, AIEP HTML and Node catalogue facts are unchanged.

## Exact file inventory for this rebuild

Modified:

- `tools/sync_catalogue.py`
- `tools/templates/v21_validation_failure.js` (comment reflects Current's router)
- `mytech_v2_1_test_adapter.mjs`
- `tests/test_catalogue_sync.py`
- `tests/test_workflow_import_contract.py`
- `tests/catalogue-v21.test.mjs`
- `tests/workflow-usage-v21.test.mjs`
- `.github/workflows/ci.yml`
- `docs/v21-catalogue-sync.md`

Added:

- `tools/templates/mytech_current_working_portable.json`
- `tests/current-workflow-v21.test.mjs` (nine offline native-graph scenarios)
- `docs/v21-current-baseline-rebuild.md`

Removed:

- `tools/templates/v21_fastgpt_retrieval_compatibility.json`

Regenerated:

- `generated/v2_1_test/mytech-fastgpt-workflow-v2_1-TEST.json`
- `generated/v2_1_test/manifest.json`
