# Failure taxonomy and recovery actions (schema v1)

**Status:** Development implementation under [issue #86](https://github.com/interzettel/prehnite/issues/86). Additive fields for existing SQLite, JSON, CSV and offline HTML report contracts. Does not enable extra provider retries.

A stage error may be temporary, fatal, or **ambiguous**. In particular, a remote request that was submitted before a worker lost its acknowledgement could still be billable. This classification makes those differences inspectable, without equating transport exceptions with provider billing evidence.

## Sources of truth

- `report.json.failure_summary` is a **snapshot** of unresolved journal operations and non-accepted assets. `schema_version = 1`. Summary counters do not mean total historical incidents or invoice amounts.
- `report.json.asset_results[asset_id].failure` is set for newly rejected, failed-cutout or error results; previously saved legacy results still receive a conservative fallback *in summary only*.
- `report.json.operations_detail[*].data.failure` is attached to newly failed stage attempts, while pre-existing `status` and `data.error` compatibility fields are retained.
- `operations.csv` adds `failure_code` and `next_action` columns to the end of the existing schema, leaving all original columns intact.
- `report.html` has a compact offline failure-counter view. An upcoming issue #6 dashboard may add filtering and deeper inspection.
- `report.json.batch_failure` represents a cost/budget policy interruption when present. It is not an asset failure.

Each machine-readable `failure` field contains `code`, `category`, `stage`, `provider`, `next_action`, `paid_or_billable`, `request_id_present`, and `automatic_resubmit_allowed` (currently always **false** as a safety boundary).

## Code dictionary

| Code | Meaning | Action |
| --- | --- | --- |
| `remote_submission_ambiguous` | Existing paid stage is submitting/uncertain without durable provider request ID; a call **may** have been billed | `manual_reconcile_before_retry` |
| `remote_request_pending` | Persisted paid stage has a provider ID, including recovered `submitted` or `uncertain` | `inspect_existing_request`, never submit a fresh request |
| `remote_reconciliation_required` | Typed refusal to continue a potentially dispatched paid stage | Manual reconciliation or inspect existing ID |
| `remote_transport_uncertain` | Paid provider operation threw a transport error; its billing state is unknown | Inspect existing ID or manually reconcile |
| `local_transport_failure` | Nonpaid provider stage connection/timing problem | Inspect and retry no-cost stage if appropriate |
| `local_stage_incomplete` | Persisted nonpaid `running` stage with no completion evidence | Inspect and retry nonpaid work |
| `local_stage_failed`, `stage_execution_error` | Local execution failure | Investigate and retry nonpaid work where appropriate |
| `technical_validation` | Invalid stage artifact or reported technical fault | Inspect invalid artifact |
| `artifact_integrity` | Hash/decodability/missing-output violation | Inspect and restore artifact, no blind acceptance |
| `budget_limit` | Approved batch budget exhausted | Request budget review; never silently increase limit |
| `authorization_required` | Paid/upload operation not authorized | Obtain explicit consent |
| `cutout_validation_failed` | Accepted base photo has unresolved named derivative | Inspect or repair cutout without regenerating good image |
| `asset_rejected` | Candidate did not pass acceptance | Inspect/adjust quality policy |
| `asset_processing_error` | Legacy asset error without more specific evidence | Inspect asset stages |
| `asset_incomplete`, `unknown_stage_state` | Missing/unknown status | Manual inspection; never assume safe retry |

These are conservative **operator recommendations**, not autonomous repair plans. A caller must never treat `next_action` as privileged permission for any network activity.

## Safe, bounded output

`failure_summary.unresolved_operations[*].task_key_sha256` contains a SHA256 digest, not the operation key. It never includes raw prompts, provider request IDs, URLs, exception text or local file paths; only a boolean indicates whether a provider request ID exists. The legacy `operations_detail` / CSV and old `data.error` fields may still contain operational/private details, so full reports and ZIP archives must remain **private** and should not be publicly published. This change does not claim to sanitize the entire legacy report.

The summary counts *current* unfinished/error stages; if an operator resumes a stage and it completes, that stage disappears from `unresolved_operations`. An accepted asset likewise disappears from asset-failure counts. This is not a time-series incident log.

## Offline regression coverage

`pytest -q tests/test_failure_taxonomy.py tests/test_crash_matrix.py tests/test_recovery.py tests/test_paid_safety.py tests/test_zip_reproducibility.py`

The suite verifies missing and present remote receipt IDs, fake paid timeout with no second dispatch, typed batch budget stop, corrupt accepted image, cutout rejection without discarding its accepted base photo, nonpaid failure, report/ZIP serialization, and bounded non-secret code fields. Synthetic-only; no API spend.

## Out of scope

Actual remote provider queue cancellation, invoice reconciliation, judge human calibration and automatic targeted cutout repair remain gated separately. The CLI/MCP pause protocol from #38 and 90-asset fixture from #41 remain unchanged. Failure codes are local journal observations, not a guarantee that live providers agree about billing or status.
