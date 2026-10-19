# S04-A02 — stable target/instance identity and output namespace

**Original atomic task:** [S04-A02 / issue #30](https://github.com/interzettel/prehnite/issues/30).
**Original acceptance:** "Per-instance IDs and intended outputs remain deterministic
after retries."

This S04-A02 contract defines **identity and intention only**. It never
segments, binds or exports an image, or approves a candidate. Subsequent
[S04-A03](OWNER_REGION_INSTANCE_BINDING.md) provides a separate opt-in,
read-only owner-region to candidate-mask binding contract. **S04-A04
(multi-object export/resume) and independent quality acceptance remain open.** The existing `prehnite run` reviewed-source path stays
single-target; this change does not advertise new multi-instance inference.

## Namespace and identity

The hierarchy is **reviewed source hash → asset ID → target ID → owner-declared
instance key**. These keys must be stable semantic names established by the
operator before binding actual segmentation candidates. Do not construct
instance keys from detector array indices, bounding-box sort order, segmentation
timestamps, filenames, random UUIDs, or whichever candidate scores highest.

The deterministic SHA256 identity includes: contract version, asset ID,
source-image SHA256, target ID, exact target phrase and instance key. A
separate plan digest binds the sorted collection of declared instances.
Changing an identity component changes the instance ID and intended filename
instead of reusing a potentially wrong previously accepted output.

For a plan with owner keys `back-left` and `back-right`, the intended
filenames have this **shape**:

```text
cutouts/product-01/bag/back-left-<derived-16-hex>.png
cutouts/product-01/bag/back-right-<derived-16-hex>.png
```

The corresponding opaque instance IDs are `inst-<derived-24-hex>`.
All paths are canonical POSIX-relative paths validated against traversal and
Windows-reserved names. Paths and IDs are unique within a plan, and target/owner
declaration order cannot change them.

## CPU-only usage

```python
from prehnite.instances import TargetIntent, plan_instance_outputs
plan = plan_instance_outputs(
    asset_id="product-01",
    source_sha256="<actual 64-character lowercase source SHA256>",
    targets=[
        TargetIntent(
            target_id="bag",
            phrase="red backpack",
            instance_keys=("back-left", "back-right"),
        ),
    ],
)
record = plan.to_record()
assert record["binding_status"] == "unbound"
assert record["output_status"] == "not_written"
```

The returned record is JSON-compatible, sorted, hash-bound and stable after
restart. When re-opening a previously recorded identity plan, call
`verify_instance_plan_record(plan, prior_record)`; any altered owner key,
source, target meaning, ordering, intended path or status is refused.

The reader must **not** interpret the plan as evidence that either named output
exists, that either instance was selected, or that an existing mask's contents
match the operator's intended target. A different process can regenerate the
same declarations and compare the exact record; there is no side effect or
implicit network/model call.

## Acceptance evidence and limits

`tests/test_instances.py` checks deterministic IDs and intended output names
across reversed declaration order and a fresh Python interpreter; output
namespace uniqueness across same-phrase objects; source/target/key revision
isolation; strict resume-plan comparison; rejection of ambiguous duplicate
keys, unsafe paths and excessive instances; and no generated image outputs.

This is the **S04-A02 identity contract only**. The separate merged
[S04-A03 owner binding](OWNER_REGION_INSTANCE_BINDING.md) handles explicit
image-region/point selection of already available candidate masks and refuses
ambiguous overlap. Automatic semantic matching remains unclaimed.
**S04-A04's actual image export, interrupted/resumed named output hashes and
parent S04 acceptance are not delivered by either contract**. The 61-unit
release count must not move on the strength of these two atomic requirements.
