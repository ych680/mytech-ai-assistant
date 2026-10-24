# MyTech v2.1 actual workflow snapshots

The [registry](registry.json) is the repository's version/status index. It
preserves two actual exports separately from generated candidates:

| Role | Application | Snapshot | Default |
| --- | --- | --- | --- |
| Original | MyTech v2.1 — TEST Knowledge | [2026-10-24 snapshot](original/2026-10-24/workflow.sanitized.json) | Maintainer-confirmed AIEP default |
| Optimized | MyTech v2.1 — GLM47 Optimized TEST | [2026-10-24 snapshot](optimized/2026-10-24/workflow.sanitized.json) | Experimental; not default |

Each sibling `provenance.json` records the raw source filename/hash, sanitized
hash and removed `/chatConfig/_id` account metadata. Both downloaded originals
remain outside the repository and unchanged. No API credential is included.
Snapshot prompts, models, code, IDs, settings and layout are preserved exactly.

Both workflows have 20 nodes/18 edges and the Master-derived 54-product validator.
The [machine comparison](comparison.json) records exactly two model changes,
two instruction changes and two editor-coordinate changes. All routing, native
schemas/bindings, history, limits, RAG settings, validation, memory and public
four-field contract are otherwise identical. See the
[integration report](../../docs/v21-repository-integration-phase1.md) for details.

The exports omit active KB selections (`datasets=[]`) and contain no verifiable
published revision. The optimized smoke report names `MyTech v2.1 — TEST Knowledge`
as its KB; the export still does not prove a KB ID/index or equivalence to the
Original app's active KB. Maintainer reports and export-level facts are recorded
separately. Preserve the same existing KB when reproducing an app after approval;
do not upload/rechunk/re-embed knowledge or overwrite live applications here.

Reproduction roles:

- `catalogue/mytech_products_v2_1_test.json` owns product facts. The registry check
  compares every snapshot's full validator catalogue with it.
- `tools/sync_catalogue.py` generates local TEST/RAG/catalogue assets;
  `tools/build_aiep_test.py` reuses its renderer for hosted AIEP assets.
  The generated workflow uses short prompts and blank model bindings; it is
  not the actual Original snapshot.
- `tools/build_glm47_prompt_ab.py` generates experimental GLM long/short A/B
  candidates from the earlier reviewed actual-source path, which remains intact.
  GLM long A is not the deployed mixed-model Original. Actual Optimized matches
  generated B except for two editor coordinates.
- Frozen actual snapshots are reviewed evidence, not generator outputs. New
  exports get a new version directory and provenance; do not overwrite old
  snapshots or silently regenerate them after a Master edit.
- `tools/check_workflow_registry.py` is read-only, needs no Downloads or secrets,
  and checks snapshot hashes, actual configuration, catalogue parity, deployment
  roles and recorded differences. Existing paths/tests/assets are unchanged.

The Original application remains in place for rollback/classroom use. The
[single optimized smoke observation](../../docs/v21-glm47-smoke-test.md) is not a
completed controlled A/B evaluation or evidence supporting default promotion.
