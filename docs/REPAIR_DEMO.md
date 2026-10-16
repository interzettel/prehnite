# Experiment 001 — local product cutout correction

Tracking: [#31](https://github.com/interzettel/prehnite/issues/31) · coordination: [#29](https://github.com/interzettel/prehnite/issues/29).

## Run offline

Install the repository in editable mode, then run:

    python -m pip install -e ".[dev]"
    python scripts/repair_demo.py --workspace ./prehnite-repair-demo

Open **prehnite-repair-demo/evidence/experiment-001/report.html** in a browser.
The paired **report.json** includes exact SHA256 receipts, a stable operation ID,
technical metrics, zero-provider-call evidence, and withheld-mask IoU. The HTML
embeds PNGs and uses no remote resources, scripts or model inference.

## Scope

Synthetic RGB product and hair-like portrait controls are produced locally.
The product has a known flat background and deliberately dilated alpha mask.
The repair implementation **never reads the reference mask**; the report
generator uses that reference only to measure whether the change helped.

Detection requires a PNG RGB source and identically sized grayscale PNG mask,
bounded size (4 million pixels, 16 MiB per file), an isolated subject, uniform
frame background and background-colored alpha pixels within four pixels of
exterior-connected transparency. Only those pixels lose alpha. Empty/full
masks, excessive (>12%) removals, invalid geometry and ambiguous backgrounds
are refused. The portrait control always abstains; this operation is not
reliable for hair, fine edges or translucent materials.

Each repair operation has a stable ID derived from batch, asset, target,
source/mask SHA256, algorithm, policy and one-attempt allowance, and is
recorded in the existing SQLite journal before execution. Results live under
an isolated operation directory, not selected production outputs. A crash
before publication may recompute the same local candidate on replay; a crash
after publication verifies existing bytes and adopts only an exact match.
Exactly-once means **one accepted logical operation**, not zero repeated
CPU computation. Changed inputs do not reset the one-attempt cap per target.
Previously accepted artifacts and remotely uncertain stages remain untouched.

## Limits and follow-ups

A technically accepted synthetic result does **not** establish human-rated
quality, real-world product matting, color spill decontamination, or portrait
fidelity. No existing Engine cutout-acceptance path changes in this tranche.
No hosted providers, credentials, licensing-restricted weights or paid inference
are used. The full S03/S05 ledger units and human benchmark #28/#32 remain
open; this PR is a demonstrator with durable behavior and isolated evidence.
