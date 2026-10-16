# Local, content-addressed stage caching

Repeated generation, upscaling or segmentation can waste money even when
the requested output is identical. Prehnite offers an **optional local
cache** of fully decoded, verified stage images. It is disabled by default.

## Activation

Add the following to a profile:

```yaml
cache:
  enabled: true
  namespace: my-private-studio
  allow_paid: false
  model_revisions: {}
```

The namespace is a **deliberate sharing boundary**: batches with the same
namespace and identical cache keys can reuse image bytes. Other namespaces
cannot see the same record through Prehnite's normal lookup. The namespace
itself is stored only as SHA256 in cache paths and receipts, never as text.
Do not regard a namespace string as a password or an access control system;
the host filesystem account and directory permissions remain the real
security boundary. All cache files are stored under
`workspace/.prehnite-cache/<namespace-hash>/`.

For provider-based (paid) caching, you must additionally set both
`allow_paid: true` and a pinned, immutable model revision:

```yaml
cache:
  enabled: true
  namespace: my-private-studio
  allow_paid: true
  model_revisions:
    generation: pinned-model-contract-2026-10
    upscaling: pinned-upscaler-contract-2026-10
    segmentation: pinned-mask-contract-2026-10
```

This is separate from and **does not override** the production cost-policy
flags `costs.allow_paid`, `costs.allow_cloud_uploads`, `costs.max_usd`,
or current required price estimates. Those are still validated before
a batch starts. Reuse of a previously charged output does not prove its
old provider invoice cost is zero or that you own its redistribution rights.
Check the provider's caching/retention terms before enabling paid reuse.

## What forms the cache key?

A canonical JSON hash of:

- Explicit namespace SHA256 and cache contract version
- Prehnite pipeline/package version
- Stage kind: generation, upscaling or segmentation
- Provider name, exact model ID, model revision and endpoint options
- Generation: exact prompt text, seed, aspect ratio and tier
- Upscaling: SHA256 of the image source and upscale factor
- Segmentation: SHA256 of the selected source and the exact target phrase

The exact prompt and source-image content are *used in memory to compute
the key* but are not stored in cache metadata. Stage images themselves
are stored locally in a single immutable ZIP containing their bytes
and a SHA256 receipt. Cache entries are either absent, fully valid, or
rejected as corrupt; partial or tampered entries are never a silent miss
that triggers another billable model call.

For mutable ComfyUI graphs and external model aliases, owners must pin and
update the `model_revisions` string whenever workflow or checkpoint bytes
change; Prehnite cannot attest to those external weights in this first
implementation. Without a revision pin, caching is disabled for non-demo
providers rather than guessing the endpoint's identity.

## Safety and economics

A cache hit on a *new* batch stage is recorded as a completed journal
operation with a `cache_hit` flag, artifact SHA256, and **zero newly
reserved inference spend**. The old batch's historical reservation is not
altered. A previously started paid operation always follows its own
provider-ID recovery rules, even if a seemingly matching cache record
exists; a cache hit cannot reconcile an ambiguous historical charge.

Caching only covers image-generation, upscaling and segmentation stage
artifacts. It does **not** cache paid judge verdicts, accepted final
output files, actual provider invoices, or external model weights.
The cache makes no claims of reproducible live-model inference when the
upstream model/weights/endpoint changes unexpectedly.

The cache does not contact the network, synchronize across machines,
or silently share artifacts with other users. Be mindful that a local
workspace or backup may contain copyright-protected/private image content.
Clear or isolate the `.prehnite-cache` folder when disposing of a
workspace, and do not sync it without consent.

See [issue #18](https://github.com/interzettel/prehnite/issues/18)
and the [stage cache tests](../tests/test_cache.py).
