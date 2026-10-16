# Local ComfyUI API workflow contract fixtures

Prehnite supports the ComfyUI **local HTTP** queue, but does not ship
ComfyUI, checkpoints, a weight-download script or a ready-to-run model.
The three JSON fixtures in [tests/fixtures/comfy](../tests/fixtures/comfy/)
exist solely to exercise mapping of API-format node inputs. They have
incomplete model connections and deliberately nonexistent checkpoint names;
**they are not executable model workflows or benchmarks**.

| Fixture | Mapping | What the offline tests prove |
| --- | --- | --- |
| `generate_api.json` | `prompt_node=6`, `seed_node=3`, `size_node=5` | Prompt, seed and 2K/4K requested dimensions appear in the queued graph |
| `upscale_api.json` | `input_node=10` | Input image reference injected once; existing prompt ID retrieves result without resubmitting |
| `segment_api.json` | `input_node=20`, `target_node=21` | Target text and input image mapped; bad mappings fail before local upload |

The fake `httpx.Client` reproduces `/prompt`, `/history/<prompt_id>`,
`/view`, and `/upload/image` response shapes without a network request,
using a small synthetic PNG. It exercises cancellation-free queue completion,
binary downloads and resume-by-prompt-ID. **Stage-specific graph mappings
are checked before local uploads**, avoiding needless disclosure of source
bytes if a graph has mismatched node names.

Use `examples/profile-comfyui.yaml` as a starting point for *your own*
valid exported API workflow and replace its graph names/node IDs. Export
from an installed ComfyUI instance and check the actual input names before
running; Prehnite cannot infer whether your custom graph is semantically
correct, licensed for a given purpose or fits your VRAM.

Not yet proven: live ComfyUI conformance, error/cancellation and
queue-history edge cases ([#23](https://github.com/interzettel/prehnite/issues/23)),
or actual 8GB RTX 4070 Laptop VRAM, cold-start and throughput benchmarks
([#24](https://github.com/interzettel/prehnite/issues/24)).
No model weights, external inference or paid API calls are included.
