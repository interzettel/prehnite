# MCP job lifecycle: pause, cancel, reconnect (development)

**Status:** Implemented in development PR #83; requires verified CI/review/merge before evidence credit. Does not certify live paid providers or hardware inference.

Prehnite's local `stdio` MCP server starts a **detached CLI worker**, so an MCP client disconnect does not terminate the batch. The same `PREHNITE_HOME` can be reopened after client/server restart. The worker and clients share a SQLite journal under `workspace/batches/<batch-id>/`.

## Available tools

| Tool | Purpose |
| --- | --- |
| `submit_batch(manifest_filename, profile_filename)` | Validate staged, basename-only YAML files in `requests/` and `profiles/`, and start one detached worker |
| `get_job_status(job_id)` | Persisted lifecycle state, kernel-lock worker liveness, accepted/processed counts and **reserved**, not invoiced, USD |
| `pause_batch(job_id)` | Cooperative request: stop at next safe checkpoint, retain the batch for explicit resumption |
| `cancel_batch(job_id)` | Cooperative irreversible stop for that batch ID; create a new batch ID if new work is desired |
| `resume_batch(job_id)` | Reopen paused/interrupted/failed work from saved allowlisted filenames; validate configuration again |
| `export_batch(job_id)` | Export accepted assets only after no worker is writing (including partial paused/cancelled results) |

A successful pause/cancel request returns `pause_requested`/`cancel_requested` **not** a false claim of immediate termination. `in_flight_stage_may_finish` makes this explicit. A request during a provider operation cannot interrupt a remote queue job or reverse a charge. The next stage/asset checkpoint stops further work; any already-submitted paid request is retained in the existing journal and follows fail-closed recovery rules. No process signals are sent to PIDs. This implementation does **not** issue provider-native cancellation or guarantee that a remote request has ceased or stopped billing.

A `paused` state retains the existing stage journal so a subsequent explicit `resume_batch` can reuse completed local stages and reconnect to persisted remote request IDs. `cancelled` is terminal. `completed` means the worker finished processing and export—not that every requested asset passed quality; inspect accepted/processed/status counts. `failed` means the worker raised an exception; `interrupted` means its formerly reported running/launching state is no longer backed by a live lock after grace. A fresh `launching` state has a bounded 30-second startup grace; after that a stale token can be explicitly superseded on resume.

## Crash, race and identity safeguards

- A unique random launch token is stored in the SQLite control record; **the worker must match it after acquiring the kernel run lock**. Stale/restarted workers cannot take ownership of a newer launch even when OS PIDs are reused.
- Separate Windows/Unix **kernel launch and run locks** serialize simultaneous submit/control calls and prevent two active workers for the same batch. Persistent lock files by themselves **do not** prove liveness.
- A changed manifest/profile fingerprint refuses same-ID continuation. The persisted filenames are looked up only inside the four allowlisted local directories; no MCP client supplies shell commands or arbitrary input/output paths.
- Control state is persisted atomically and checked before provider stages and paid judge dispatch. Current operations are not forcibly killed, preventing accidental redelivery after an ambiguous paid submission.
- The server returns progress measurements sourced from the journal. `accepted_assets` is a count of complete accepted output slots; `processed_assets` is the number of slots with a recorded terminal result. `reserved_usd` is **not** a verified provider invoice.
- `export_batch` refuses to package files while the run lock is held or a newly launched worker may not yet have obtained it. It does not reset a failed/uncertain remote request or mark rejected assets as accepted.

## Offline verification

`pytest -q tests/test_mcp_lifecycle.py tests/test_crash_matrix.py tests/test_paid_safety.py`

The suite uses only synthetic images, mock subprocess launchers, and one real detached **synthetic-demo** CLI subprocess: duplicate parallel submits, reused/fake PID file, reconnect, startup stop, mid-stage pause/cancel, token revocation, idempotent cancel, exporter safety, path validation, and stage reuse after explicit resume. No GPU, cloud credentials, downloads or billable calls are needed.

## Known limits before #41 and the live pilot

- Safe stop is **cooperative** and stage-granular, not instantaneous; a long-running GPU/provider stage is not interrupted. Provider-specific cancellation and remote-stage status are separate future scopes.
- The launch grace is wall-clock based and conservative; on exceptionally slow startups, the operator may need to investigate local logs before explicit resume.
- This design assumes a local filesystem and one user/OS security principal. `PREHNITE_HOME` is **not** a multi-tenant server; filesystem permissions govern access. It does not expose an authenticated public HTTP MCP endpoint.
- Agent reconnect and local worker lifecycle are tested with no-cost synthetic workloads. No guarantee about real fal/Anthropic billable recovery, RTX 4070 behavior, or 90-asset throughput follows from those tests.
- #41 should include 90-slot mixed-failure, pause/resume and kill/recovery scenarios to verify progress truthfulness and full delivery without duplicated paid submissions.
