# S04-A03 — Owner-selected region to instance binding

**Original atomic task:** [S04-A03 / issue #30](https://github.com/interzettel/prehnite/issues/30). **Exact criterion:** "Selection resolves requested target without destroying unrelated masks."

The implementation in `src/prehnite/instance_binding.py` is a **CPU-only, opt-in, read-only mask binding contract**. It builds on the already merged [S04-A02 identity plan](INSTANCE_IDENTITY_CONTRACT.md) and does **not** change the existing single-target Engine, segmentation model, cutout review state, or existing accepted images.

## How an owner selects an instance

1. Create an immutable source-bound `InstancePlan` (S04-A02), with explicit target ID, target phrase and stable per-instance keys.
2. Supply the original source image and a bounded list of **separately stored PNG grayscale instance masks**, each matching the source's exact pixel geometry. All files are identified by their actual SHA256.
3. An owner identifies an intended `instance_id`, a rectangle in source coordinates `(x0, y0, x1, y1)`, and a point `(seed_x, seed_y)` strictly inside that rectangle.
4. **Only one** candidate mask may contain the owner point. Any overlapping masks on the seed, no mask on the seed, duplicate mask bytes, changed source, ambiguous disconnected components, invalid mask channels/geometry or unsafe path alias leads to a refusal. The binder never selects "the first mask," guesses from confidence scores or mutates another mask.
5. A content-bound JSON-compatible receipt records the planned instance and intended filename, exact owner region, selected mask SHA256 and the **complete sorted inventory of all unselected mask SHA256 values**. The receipt explicitly records `output_status: not_written` and `visual_acceptance: not_recorded`.

For example, given a 80×64 source and two distinct overlapping masks, a seed at (12,22) in the left mask but outside the right binds the left mask. A seed in their common area refuses `multiple_masks_at_owner_seed`; to resolve it, the owner must supply a different unambiguous point or differently separated candidate masks. This prevents silently swapping a requested instance when detector ordering changes.

```python
from prehnite.instances import TargetIntent, plan_instance_outputs
from prehnite.instance_binding import OwnerRegion, bind_owner_region

plan = plan_instance_outputs(
    asset_id="tabletop",
    source_sha256="<the actual lower-case source SHA256>",
    targets=[TargetIntent("mug", "two mugs", ("owner-left", "owner-right"))],
)
left_id = next(item.instance_id for item in plan.instances
               if item.instance_key == "owner-left")
receipt = bind_owner_region(
    plan,
    instance_id=left_id,
    source=source_path,                 # existing local source image
    candidate_masks=[mask_left_path, mask_right_path],
    region=OwnerRegion(5, 5, 76, 58, 12, 22),
)
assert receipt["output_status"] == "not_written"
assert receipt["visual_acceptance"] == "not_recorded"
```

For a restart or changed candidate inventory, call `verify_owner_region_binding` with the previous receipt and the actual on-disk input files. It rechecks the bytes/selection and refuses a changed identity or receipt. **Neither function writes a mask, creates a cutout, or changes the source.**

## Acceptance verification

`tests/test_instance_binding.py` includes two overlapping synthetic objects; unique left/right owner selection; order-independent candidate receipt; arbitrary filename independence; exact untouched source and unrelated-mask bytes; ambiguously overlapping seed and background-point refusal; disconnected mask rejection; geometry/channel, wrong source, duplicate bytes and tampering refusals; fresh binding verification; and missing/out-of-bounds owner intent.

This validates a bounded, unambiguous owner-selection interface. It does **not** claim semantic object recognition from coordinates: the owner is responsible for the intended region and the target ID. It also does not establish exact per-instance opaque/translucent matting quality or a live detector's mask-separation capability.

**Next stage now implemented independently:** [S04-A04](MULTI_INSTANCE_EXPORT_RESUME.md) writes actual named PNG exports and verifies them through journal-backed interrupted/resumed execution. This S04-A03 function itself still performs no image export, external model call, paid API, GPU benchmark or auto-acceptance. Parent S04's 61-unit release credit and any human cutout quality claims require separate acceptance evidence.
