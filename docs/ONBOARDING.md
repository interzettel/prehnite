# First run: init and doctor

Prehnite's first-run path should work without a model checkpoint, GPU,
paid account, persistent server or access to the public internet. You can
use it in a Windows PowerShell terminal or Linux/macOS shell.

After `pip install -e .`:

```powershell
prehnite init --destination my-first-batch --batch-id sample-one
prehnite doctor
prehnite validate my-first-batch/manifest.yaml --profile my-first-batch/profile.yaml
prehnite run my-first-batch/manifest.yaml --profile my-first-batch/profile.yaml --workspace workspace
```

`init` creates exactly two validated YAML files using *synthetic demo*
generation, technical checks and `allow_paid: false`, a zero-dollar cap,
and `allow_cloud_uploads: false`. It **never overwrites** existing
`manifest.yaml`/`profile.yaml`; an invalid batch ID and a failed
partial write leave no partially created user files. If there is already a
batch, choose a different destination.

`doctor` emits JSON for humans and agents. It detects Python, operating
system and installed package version, checks optional provider client
installations, and reports ONLY whether `FAL_KEY` or
`ANTHROPIC_API_KEY` has been configured. It never prints secrets, verifies
remote account authorization, reports billable capacity, uploads images,
downloads model weights or benchmarks a GPU. A found credential is **not
proof** that a provider account is usable.

You can optionally ask for a **localhost-only**, unauthenticated
ComfyUI connection probe:

```powershell
prehnite doctor --check-comfyui --comfyui-url http://127.0.0.1:8188
```

The probe uses a short timeout and requests only the local
`/system_stats` path, not models or images. It refuses remote HTTP hosts,
proxies and HTTPS endpoints. A reachable response does **not** establish
that ComfyUI has working model weights, safe workflows, available 8GB VRAM,
or viable inference performance. Those checks remain #24 / D09 hardware
and clean Windows/Linux installation work.

All baseline CLI and initialization tests run offline in GitHub CI. This
is not yet a verified fresh Windows PowerShell installation transcript,
a desktop installer or a model deployment service.
