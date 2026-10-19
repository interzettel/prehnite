# S04-A04 — real named multi-object export and crash-safe resume

**Original atomic task:** [S04-A04 / issue #30](https://github.com/interzettel/prehnite/issues/30). Exact original acceptance: **"Tests confirm named output hashes across interruption and restart."**

This finishes the CPU-only export step built on already merged
[S04-A02 instance identities](INSTANCE_IDENTITY_CONTRACT.md) and
[S04-A03 explicit region-to-instance binding](OWNER_REGION_INSTANCE_BINDING.md).

It is an **opt-in local export API**, not new automated multi-target segmentation,
a new ComfyUI workflow, a general engine-run change or a visual acceptance record.

## Workflow

The owner creates a source-bound `InstancePlan` with two or more declared
instances. For each declared instance, the owner supplies a verified
`bind_owner_region` receipt and the same local source/candidate masks used
during selection. **Every declared instance must be bound** and all bindings
are validated before the first output is created. Two instances cannot share
the same selected mask, even if they have different owner keys.

```python
from prehnite.instance_export import BoundExport, export_bound_instances

result = export_bound_instances(
    plan,
    source=source_path,
    selections=[
        BoundExport(
            instance_id=first_id,
            receipt=first_binding,
            region=first_region,
            candidate_masks=(mask_a, mask_b),
        ),
        BoundExport(
            instance_id=second_id,
            receipt=second_binding,
            region=second_region,
            candidate_masks=(mask_a, mask_b),
        ),
    ],
    destination_root=private_export_folder,
)
assert result["output_status"] == "written"
assert result["visual_acceptance"] == "not_recorded"
```

Outputs are actual **RGBA PNG cutouts** computed from the original source and
owner-selected grayscale masks. Names come **exclusively** from the deterministic
S04-A02 plan, e.g. `cutouts/collection-01/bag/first-<16hex>.png`.
Source and candidate masks remain byte-for-byte unchanged. Mask detector order
does not determine output names.

The export root contains a create-only per-instance image namespace, the
atomic `_instance_export_journal.json` and a persistent advisory lock marker
`_instance_export.lock`. The lock uses the operating system's per-process
lock (Windows `msvcrt.locking`, Unix `fcntl.flock`): a killed process releases
it without requiring manual recovery.

## Interruption / resume invariants

1. An immutable journal manifest binds the original plan SHA256, source SHA256,
   every owner binding SHA256, mask SHA256 and intended filename.
2. Before exporting anything on replay, the implementation revalidates the
   **entire owner-selected input set and every previously committed PNG hash**.
   Missing/changed sources, changed masks, tampered receipts, altered journal
   manifests, bad outputs and symlinks fail closed.
3. Each new cutout is rendered into a sibling staging file. After verifying
   its decoded bytes, the output is published under its intended final filename
   using a same-filesystem **create-only hardlink**. An existing named output
   is never silently overwritten.
4. Only *after* successful publication is the matching image hash recorded by
   atomic journal replacement.
5. If a process is terminated **after publishing PNG but before journal
   commit**, replay recomputes expected bytes and adopts the published file
   only when its SHA256 matches. If terminated **after journal commit**, replay
   verifies the committed hash and does not regenerate that completed output.
6. A third run, including a fresh interpreter, yields the identical result
   receipt, journal and per-filename hashes, without rewriting already
   committed images. Recorded status is `written`, never `accepted`.

The persistent lock file is intentionally not unlinked after use: deleting a
lock inode could allow a concurrent exporter to lock a *different* inode.
Failed create-only link or filesystem support does not fall back to silently
overwriting existing output. Input manifests remain unchanged.

## Acceptance tests

`tests/test_instance_export.py` exercises actual distinct RGBA images, owner
selection, immutable source/unselected mask bytes, deterministic filenames,
no-op resume, tampered records/output refusal, unsafe path refusal, and **two
real Python subprocess exits** (exit code 83) at
`after_publish` and `after_journal`. Separate fresh interpreter processes
resume the same journal and verify that every named output SHA256 and the
preexisting output modification time remain stable.

No model/checkpoint weights, private source images or paid inference are required
for these tests.

## Boundaries

This proves only the frozen **S04-A04** export/resume criterion. It does not
establish the quality of matting, correct automatic semantic selection, actual
GPU segmentation or independent owner visual acceptance. Existing `prehnite
run` remains single-target. The S04 release parent cannot be closed solely by
these CPU contracts without checking its own broader issue #30 objective and
acceptance (multi-object output/unique named files, explicit selection and
ambiguous assignment refusal).

Do not infer that real-model multi-instance segmentation has been demonstrated
by synthetic PNG fixtures.
