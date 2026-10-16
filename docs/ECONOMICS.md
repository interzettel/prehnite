# Batch economics — what the numbers actually mean

Prehnite's goal is to minimize cost per **accepted usable asset**, not to
maximize raw image generations. To avoid false financial claims, its
`report.json` contains `economics` with intentionally separate fields.

| Field | Meaning |
| --- | --- |
| `reserved_usd_total` | The sum of estimate reservations for unique journaled operation keys, including rejected and failed work. Not an invoice and not necessarily a worst-case guarantee. |
| `reserved_usd_per_accepted_asset` | Reserved total divided by final `accepted` assets. **Null** if nothing was accepted, even if some work costs money. |
| `provider_reported_usd_partial_total` | Optional, explicitly partial sum of provider-reported numbers **only when an adapter supplies such metadata**. Not an invoice or reconciliation proof. Null if none exist. |
| `provider_reported_operation_count` | Number of operation rows providing the optional reported amount. Do not assume reporting coverage from total operations alone. |
| `actual_invoiced_usd_total` | **Null** until a separate reconciliation process verifies a provider invoice. No such process is currently implemented. |
| `actual_invoiced_usd_per_accepted_asset` | **Null** until invoice reconciliation exists; never silently substitute estimates. |
| `attempts_started` | Append-only local invocation records. Reopening a remote ID after interruption creates another invocation, but does *not* create another spending reservation for the same operation. |
| `retry_attempts` | Sum of additional local attempts per operation key after its first observed attempt; this is *not* a count of new paid submissions. |
| `attempts_with_observed_duration` | Local invocations with a measured monotonic elapsed duration; includes successful and failed calls. |
| `attempts_without_finished_timing` | Open/abandoned records (e.g., terminated worker); time is unknown, **not** zero. |
| `stages[...].observed_elapsed_ms_p95` | Nearest-rank 95th percentile of known local invocation-plus-publish durations for each stage. Null if none. **Not** provider-internal latency. |

## Instrumentation and reliability

The SQLite journal creates an attempt row just before each call to a
provider stage, and persists the row before the call. The same accounting
is applied to optional Anthropic judging calls. Success/failure updates
record monotonic elapsed milliseconds. An abrupt process death leaves the
attempt in `incomplete` state, visibly excluded from duration statistics.
Old batches may have task rows but no recorded attempts; this means timing
coverage is **unknown**, not that the model was instantaneous.

No raw prompts, keys, receipts or remote request IDs are added by this
aggregation. Existing detailed operation exports may contain request IDs;
do not share `operations.csv` publicly without reviewing it.

The HTML report shows a compact stage breakdown. The JSON report includes
the full machine-readable economics summary and coverage labels. Because
ZIP exports include `report.json` and `report.html`, economics are also
available in self-contained accepted-asset deliveries.

## Sample calculation

In an offline synthetic 90-operation replay:

- 90 reserved operations at $0.025 each = **$2.25 reserved**.
- 72 accepted assets, 18 rejected or otherwise not accepted.
- Reserved cost per accepted asset = **$0.03125**.
- Seven failed local stage invocations and one abandoned invocation contribute
  eight extra attempts but **no second reservation** per operation.
- The actual provider invoice is **unknown**. No live inference or spending
  is performed by this fixture.

This is an *illustrative accounting fixture*, not a claim about achievable
per-photo prices. Real provider pricing, invoices, GPU power costs, human
review time and visual-quality acceptance benchmarks are separate future
measurements. See [#17](https://github.com/interzettel/prehnite/issues/17)
and [#42](https://github.com/interzettel/prehnite/issues/42).

All report calculations should remain deterministic for a fixed SQLite
snapshot, independent of current clock time or runtime locale.
