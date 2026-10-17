# License policy

Prehnite's original source code is MIT-licensed (see LICENSE). Optional model weights, hosted APIs and separately installed software retain their own licenses and terms. Neither MIT nor the Prehnite package changes those terms.

No checkpoint or dataset is bundled. Users must independently review commercial-use, redistribution, training and output-use restrictions for any model they choose. In particular, Black Forest Labs FLUX weights are not simply MIT because the adapter is MIT. ComfyUI is separately licensed and accessed as a standalone process through an API, not vendored into the core.

When adding a provider, record its model identifier, purpose, endpoint schema, source, terms URL, version, applicable restrictions, and the date verified. Third-party dependency licenses must be reviewed before distribution and publishing on PyPI. No warranty of permission is made for third-party model use.

## Dated external model and checkpoint rights inventory (R06-A02)

See the generated [model rights review](MODEL_RIGHTS_AUDIT.md) and
machine-readable [provenance register](../progress/model_rights_inventory.json).
The review covers all currently registered hosted or user-supplied model
interfaces plus selected checkpoint examples. Every entry records a primary
upstream source, model/use boundary, unresolved training rights and
redistribution concerns. Run `python scripts/model_rights.py --check`
offline to verify source coverage and that no unpublished license approval
is inferred from Prehnite's MIT license.

The review distinguishes `FLUX.1-schnell` upstream weight labeling,
the separately licensed `FLUX.1-dev` non-commercial models, the hosted
`FLUX.3` API, Meta's SAM materials and hosted variants, the separately
licensed Real-ESRGAN implementation versus model weights, and ComfyUI
workflow components and weights. Model terms and versions may change;
the date in the inventory is a **research snapshot, not a legal guarantee**.

Rights remain unresolved until actual checkpoint revisions and hashes,
use scope, commercial/production conditions, training restrictions, API
contracts, derivative/model redistribution and human review are recorded.
No downloaded checkpoint or owner-supplied image is bundled. R06-A02
does not complete the overall R06 release gate or authorize model use.
