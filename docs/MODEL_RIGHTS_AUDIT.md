# Prehnite — model and checkpoint rights provenance

> Generated from `progress/model_rights_inventory.json` using `python scripts/model_rights.py --write`. Upstream claims and terms review, **not legal clearance, permission to train, or authorization to spend**.

**Source-check date:** 2026-10-17 · **External interfaces:** 9 · **Optional checkpoint examples:** 4 · **Weight hashes independently verified:** 0 · **Rights approved:** 0.

## Hosted and user-supplied adapter boundaries

The registry describes interfaces, not distributed weights. A hosted API's commercial-use label does not grant a license to rehost its checkpoints.

| Provider | Exact model or workflow | Boundary | Original source | Still requires review |
| --- | --- | --- | --- | --- |
| fal | `blackforestlabs/flux-3/klein/text-to-image` | hosted_api | [Terms/endpoint](https://fal.ai/models/blackforestlabs/flux-3/klein/text-to-image) | Hosted/API terms, user-upload rules and any training/distillation restrictions require review; no checkpoint license has been verified. |
| fal | `blackforestlabs/flux-3/text-to-image` | hosted_api | [Terms/endpoint](https://fal.ai/models/blackforestlabs/flux-3/text-to-image/api) | API/output terms and rehosting/fine-tuning rights must be confirmed for the exact hosted endpoint; no local FLUX.3 weights are bundled. |
| fal | `fal-ai/esrgan` | hosted_api | [Terms/endpoint](https://fal.ai/models/fal-ai/esrgan/api) | Exact RealESRGAN_x2plus and alternative pretrained weight redistribution/training conditions must be checked separately; model inference is paid only by opt-in. |
| fal | `fal-ai/sam-3-1/image` | hosted_api | [Terms/endpoint](https://fal.ai/models/fal-ai/sam-3-1/image/api) | Model training, hosted API outputs, trade-controls and redistribution provisions require separately scoped review for this endpoint. |
| fal | `fal-ai/birefnet/v2` | hosted_api | [Terms/endpoint](https://fal.ai/models/fal-ai/birefnet/v2) | Separate code, pretrained checkpoint, training dataset, provider/output and potential redistribution conditions are unresolved. |
| comfyui | `user-workflow` | user_supplied_workflow | [Terms/endpoint](https://github.com/Comfy-Org/ComfyUI/blob/master/LICENSE) | Workflow component provenance and all weight licenses are unknown until the user supplies the exact graph and checkpoint hashes. |
| comfyui | `user-upscale` | user_supplied_workflow | [Terms/endpoint](https://github.com/Comfy-Org/ComfyUI/blob/master/LICENSE) | Local model source, weights, training restrictions and output rights must be reviewed per workflow and checkpoint. |
| comfyui | `user-segmentation` | user_supplied_workflow | [Terms/endpoint](https://github.com/Comfy-Org/ComfyUI/blob/master/LICENSE) | Cannot infer SAM or any other third-party weight redistribution permission from ComfyUI GPL or Prehnite MIT. |
| anthropic | `user-specified` | hosted_api | [Terms/endpoint](https://www.anthropic.com/legal/commercial-terms) | Commercial service contract, model output restrictions, user media handling and model retention conditions need account-specific review. |

## Optional checkpoint examples — none bundled

| Candidate | Upstream label | Terms | Review work |
| --- | --- | --- | --- |
| [FLUX.1 [schnell]](https://github.com/black-forest-labs/flux) | Apache-2.0 (upstream source claims) (upstream_model_weight_license_label) | [Read original terms](https://huggingface.co/black-forest-labs/FLUX.1-schnell) | Check exact checkpoint revision, downstream dependencies and output/competitive-training policy. Upstream license label is not a general FLUX-family grant. Verify the exact weight revision's included notices before distribution. |
| [FLUX.1 [dev]](https://github.com/black-forest-labs/flux) | FLUX [dev] Non-Commercial License v2.0 (model_specific_noncommercial_terms) | [Read original terms](https://bfl.ai/legal/non-commercial-license-terms) | Non-commercial model/derivative use; terms restrict some competitive-model training from outputs. Commercial production/model hosting requires a distinct commercial agreement. Do not treat model/derivative redistribution as MIT or Apache; license text, notices, restrictions and permitted purposes apply. |
| [Meta SAM 3](https://github.com/facebookresearch/sam3) | SAM License (Meta model materials) (model_code_and_weights_license_terms) | [Read original terms](https://github.com/facebookresearch/sam3/blob/main/LICENSE) | SAM License expressly governs models and weights and includes use restrictions; exact checkpoint, training rights and trade-control terms need legal review. Redistribution must follow SAM License, including passing along applicable terms; not MIT by virtue of adapter. |
| [Real-ESRGAN x2plus](https://github.com/xinntao/Real-ESRGAN) | BSD-3-Clause (source repository code) (software_license_only) | [Read original terms](https://github.com/xinntao/Real-ESRGAN/blob/master/LICENSE) | The BSD-3-Clause source code license alone is insufficient evidence about all pretrained checkpoints, datasets or hosted fal terms. Confirm exact named weight download, model metadata and all applicable notice requirements before packaging. |

## Boundaries and next evidence

- **Proven by this register:** every external provider/model in the live capability registry has a separate rights-review entry and authoritative link.
- **Not proven:** exact checkpoint revision and hash, training data provenance, commercial use, model redistribution, local hosting and output rights.
- FLUX.1 dev uses a distinct non-commercial license; FLUX.1 schnell has a separately reported Apache-2.0 label. Neither license transfers to FLUX.3 hosted APIs.
- SAM 3 materials use Meta's SAM License, but the precise rights for the hosted SAM 3.1 variant still need confirmation.
- ComfyUI's GPL and Real-ESRGAN source BSD-3-Clause are software terms, not blanket permission to distribute all checkpoint weights or workflow nodes.
- Hosted providers also have account-specific handling, output and training terms. This tool does not connect to any service or process private images.

## Future closeout procedure

1. Identify exact checkpoint revision, download and full SHA256.
2. Record specific model weights, code, hosted API, training, output-use and redistribution terms independently with primary source and revision.
3. Obtain explicit human legal/commercial review before lifting any restriction. Do not infer a license from MIT project code, GPL UI software, or API marketing.
4. Regenerate this audit and pass `python scripts/model_rights.py --check` on the same commit. Do not commit weights or owner's private media.

**R06-A02 is a documented research inventory, not R06 release sign-off.** R06-A01 dependency closure, R06-A03 media audit, and R06-A04 human release compliance remain separate.
