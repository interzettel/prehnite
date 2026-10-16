# Optional local Parquet datasets

**Status:** Stacked development work in issue #91. Depends on unmerged #89 / PR #90. No SaaS, GPU, model API or provider invoice required.

Parquet is useful for batch comparisons, DuckDB/Polars/Pandas queries and filtering hundreds of runs without loading their images. The package remains lightweight: **PyArrow is not installed by default, and no Parquet files are written by an ordinary run, export or MCP call.**

## Opt in deliberately

```bash
python -m pip install "prehnite[parquet]"
prehnite export offline-90-v1 --workspace workspace --parquet
```

An MCP agent may explicitly call `export_batch(job_id, include_parquet=True)` with PyArrow installed. This is not permission to submit or retry inference. Exports refuse an active worker's journal. Without PyArrow, requesting Parquet raises an actionable error and never silently substitutes JSON for Parquet. Running `prehnite export ...` without the switch continues to package only the regular JSON/CSV/HTML and accepted images.

The opt-in archive contains `_prehnite/analytics.parquet`, `_prehnite/asset-observations.parquet` and `_prehnite/parquet-manifest.json`. The existing SHA256 ZIP receipt covers all three. Each local Parquet pair has an independent publication digest marker, written last, which also references the exact current `analytics.json` digest: stale/tampered/half-published Parquet artifacts cannot be silently packaged. Parquet bytes need not match between Arrow versions or systems; verified **data and schemas**, row order per file and same-environment replay are the contracts.

## Two stable typed tables (v1)

**`analytics.parquet`:** long-form metric facts, one row per `analytics.csv` metric, sorted by `section/group/measure`.

| Field | Arrow type | Meaning |
| --- | --- | --- |
| `schema_version` | int16 (non-null) | Dataset schema v1 |
| `section`, `group`, `measure`, `unit` | string (non-null) | Only bounded aggregate dimensions; no raw identifiers |
| `value_integer` | int64 (nullable) | Counts of assets, operations and tokens |
| `value_usd` | decimal128(20, 6) (nullable) | **Reserved/estimated USD only**; not actual provider invoices |
| `value_ms` | float64 (nullable) | **Observed local** stage invocation p95 only; not remote latency |

Each row uses **exactly one** typed value field (or all null for an unknown measurement), with no implicit zero or made-up amount. `reserved_usd_per_accepted_asset` is null when zero assets are accepted. File metadata records `prehnite.dataset`, schema v1, a limited privacy-basis label and unverified invoice status. Decimal USD preserves six digits after the decimal.

**`asset-observations.parquet`:** one row per required manifest slot, including pending and failures, in manifest order.

| Field | Arrow type | Meaning |
| --- | --- | --- |
| `schema_version`, `slot_ordinal` | int16, int32 | Version; 1-based position, **not** raw asset ID |
| `source_mode`, `aspect_ratio`, `status` | string | Bounded cohort and state fields |
| `failure_code` | nullable string | Known conservative code or legacy status |
| `requested_cutouts`, `selected_outputs` | int16 | Required cutouts and count of published outputs |

This table **never includes prompts, source paths, image bytes, output names, provider request IDs, timestamps or filenames**. Manifest position is pseudonymous *within the file*, not a promise of irreversibility if the recipient also possesses the original manifest. Treat all run analytics as private by default; do not publish them as public CI artifacts for real users. The automated examples contain only synthetic fixture data.

Both files use ZSTD and Parquet format version 1.0 for common reader compatibility. Writing a pair uses temporary files plus a final digest publication marker. ZIP packaging verifies header/footer marker, digest and current analytics version before including them; no optional dependency is needed merely to validate packaged bytes.

## Query locally

After exporting a few runs into separate directories, DuckDB (separately installed, optional) can query Parquet without a service:

```sql
SELECT section, "group", measure,
       SUM(value_integer) AS total_count
FROM read_parquet('/private/prehnite-runs/*/analytics.parquet')
WHERE unit = 'assets' AND value_integer IS NOT NULL
GROUP BY section, "group", measure
ORDER BY section, "group", measure;
```

Use separate directory names to distinguish batches in a multi-run query; the Parquet tables intentionally contain **no raw batch identifier**. The file path should remain local/private.

## Tests and unresolved dependencies

`python -m pip install -e ".[dev,parquet]"` then `python -m pytest -q tests/test_optional_parquet.py` on Windows/Ubuntu. The full default test suite is also checked **without PyArrow** to prove the optional dependency stays optional. Test scenarios cover 90 distinct synthetic slots, 18 requested cutouts, nullable-versus-zero counts and USD, explicit CLI/MCP opt-in, no accidental default ZIP changes, privacy-bounded columns, stale/tampered Parquet refusal and same-process re-export.

This does not implement human aesthetic ranking, a calibrated judge, cross-run ingestion UI, verified invoices, Parquet for every raw attempt/pixel, or a central data lake. Those are separate research/feature decisions with privacy, licensing and cost gates.
