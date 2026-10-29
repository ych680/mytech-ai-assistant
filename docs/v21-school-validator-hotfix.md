# October 29, 2026 validator alignment and no-match hotfix

The school workflow alignment adopts the reviewed PR17/PR18 validator, optional
retrieved-evidence input, internal completion diagnostic, and safe failure response.
The narrow follow-up hotfix recognizes `No cheaper gaming laptop ...` and
`I couldn't find a cheaper gaming laptop ...`. It permits one optional `gaming`
adjective for Laptop only. Independent catalogue eligibility still determines
whether no-match is legitimate under the actual usage, hard budget, comparison
intent, and approved historical anchor. Canonical output and memory rules remain.

The maintainer reports successful school FastGPT deployment and live testing.
The completed private offline verification recorded 291 executed Node checks
passing, two HTTP/socket cases skipped, and 353 Python tests passing. These are
prior verification results, not a new live test or platform compatibility claim.

## Source and preservation

- `tools/build_v21_school_validator_candidate.py`: fingerprint-verified alignment
  preparation with exactly four permitted workflow changes.
- `tools/build_v21_school_nomatch_fix.py`: separate hotfix preparation changing
  only `/nodes/11/inputs/2/value`, specifically `completionNegativeClaim()`.
- `tools/templates/v21_completion_negative_claim.js`: bounded hotfix recognizer.
- `tests/test_v21_school_validator_candidate.py` and
  `tests/test_v21_school_nomatch_fix.py`: portable synthetic preservation tests.
- `tests/school-validator-candidate.test.mjs` and
  `tests/school-validator-nomatch.test.mjs`: opt-in private candidate regressions,
  including replay of existing PR17/PR18 and Quick Prompt Demo suites.

The public workflow snapshots, archived generated packages, registry, historical
completion template, prompts, model/history parameters, frontend, server,
launcher, and AIEP behavior are unchanged by this repository synchronization.
The published snapshots therefore do not represent the October 29 school hotfix.
A new portable snapshot and registry update require a separate sanitization review.
Existing grounding, free-text rationale, request-state, and q-field limitations
are outside this change.

## Verification and private artifacts

Portable checks require no credentials, school exports, or network:

```sh
python -B -m unittest tests.test_v21_school_validator_candidate tests.test_v21_school_nomatch_fix
node --check tools/templates/v21_completion_negative_claim.js
node --check tests/school-validator-candidate.test.mjs
node --check tests/school-validator-nomatch.test.mjs
```

Existing CI discovers both Python test modules. The private Node suites are
discovered by the Node test glob but deliberately skip unless their explicit
candidate/source environment variables are supplied. Public CI does not replay
the full private workflow acceptance suite.

Builders are historical, fingerprint-pinned private preparation tools. They need
the exact original and upgraded exports and private reports; the alignment CLI
also checks its recorded preparation-time clean Git baseline. They are not a
one-command public deployment/rebuild path after this synchronization. Changed
or missing inputs are refused rather than silently replaced.

Raw FastGPT exports, private reports, application/KB identifiers, environment
files, and credentials must remain outside public commits. No sanitized export
is introduced here; no import, publication, deployment, or API-binding change is
performed by this synchronization.
