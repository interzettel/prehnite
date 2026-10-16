# Offline production analytics — first dashboard tranche (#6 / #89)

**Development branch / PR pending review.** A bounded continuation of the already-shipped offline visual gallery; it is **not** a complete analytics platform or a validated visual-quality system.

## Open the dashboard

Use the normal `prehnite run` or MCP worker with a validated manifest and profile. The batch writes:

| File | Purpose |
| --- | --- |
| `gallery.html` | One self-contained, responsive offline dashboard: numeric KPIs, accessible CSS bar charts and tables, plus the existing verified asset thumbnails and alpha-checkerboard cutouts |
| `analytics.json` | Versioned, deterministic, aggregate-only snapshot (schema v1) |
| `analytics.csv` | Versioned, tidy aggregate rows: `schema_version,section,group,measure,value,unit` |
| `report.json` | Existing full report, with an additive `analytics` object |
| `prehnite-<batch-id>.zip` | Existing deterministic accepted output archive; now also includes both aggregate files under `_prehnite/`, checked by SHA256 manifest |

No JavaScript, CDN, external font, network image, cloud analytics, subscription, GPU or paid API is required to view the HTML. Thumbnail images are locally embedded using data URIs. The page retains CSP `connect-src 'none'` and has no external requests.

## How metrics are defined

- **Required slots:** all distinct manifest asset IDs, regardless of how many candidates/attempts an asset received. Pending = no terminal result. Accepted numerator / required denominator is **required-slot completion**, not human visual-quality approval.
- **Source groups:** `local_source` (existing user image) versus `demo_or_model_generated` (assets originally requested through a prompt). They describe input mode, not image content or actual image-model quality.
- **Aspect-ratio groups:** five supported manifest ratios. Manifest v1 contains no semantic category field, so the dashboard **does not invent categories**.
- **Stage operations and retry distribution:** each unique task journal key is a stage operation. An attempt is a recorded *local invocation*. Zero recorded attempts can mean a cache hit, an operation that did not dispatch, or incomplete old evidence; it must not automatically be labeled a cache hit.
- **Stage/provider observed p95:** nearest-rank p95 of *measured local invocation+publication* durations. Incomplete/missing durations are excluded and counted separately; unknown is shown as **unknown**, never 0. This is not remote-model latency.
- **Reserved USD and reserved/accepted:** estimated reservations across all journal tasks, including failures. Invoiced USD remains **unknown**, and partial provider-reported dollars are explicitly labeled separate. Zero accepted slots makes the denominator-based cost *undefined*.
- **Tokens:** sums of journal input/output token fields. Not proof of external charges.
- **Failure summary:** counts *currently* failed/rejected assets by typed `failure.code` when present (for future C10 work), otherwise legacy status; stage incompletes are recorded separately. No historical incident/time series or claims of provider refunds. Only a constrained snake-case code vocabulary can pass through the aggregate; prompt text, exceptions, request IDs, local absolute paths and source pixels are **not** exported in aggregate files.

The dashboard is useful for production visibility, *not* a cost–quality Pareto frontier: quality scores have not been calibrated against human acceptance (#28). Cost quotes must not be confused with actual invoices.

## Tests and evidence

Run `python -m pytest -q tests/test_analytics_dashboard.py`, plus the existing suite. The [90-slot synthetic production benchmark](OFFLINE_90_BENCHMARK.md) now additionally verifies 90 required, 90 accepted, 48 unique demo-stage invocations, two aggregate exports in the ZIP, local chart markup, digest inventory, pause/crash/reconnect and byte-identical replay **within each OS run**. Both Windows and Ubuntu CI jobs are required for the PR.

A resumed or interrupted batch produces a new *current snapshot*; it does not preserve an incident history. Generating analytics is deterministic for fixed journal records; measured durations vary between fresh independent runs.

## Privacy and future scope

The new aggregate files have no raw asset IDs, prompts, source file names, request IDs or provider error messages, but `gallery.html` embeds pixels and displays asset names and legacy error reasons. **Keep all full batch reports, ZIPs and galleries private**. A public share/export mode requires an explicit separate privacy scrub and consent design (#68).

The parent [#6](https://github.com/interzettel/prehnite/issues/6) remains open for Parquet via an optional dependency, deeper alpha side-by-side comparison, semantic categories after schema design, richer drilldowns, and approved quality/cost benchmarks. This tranche meets only the no-service aggregated charts/CSV/JSON/visual-gallery objectives.
