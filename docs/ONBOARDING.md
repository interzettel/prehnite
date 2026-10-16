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

## Windows and Linux clean-install evidence

CI uses an isolated virtual environment on **both** `windows-latest`
(PowerShell runner) and `ubuntu-latest`. The
[`scripts/smoke_install.py`](../scripts/smoke_install.py) procedure
builds a wheel and sdist, verifies their package/version/Python metadata,
installs only the new wheel and its mandatory dependencies, checks that
`torch`, `fal_client`, `anthropic` and `mcp` did not install implicitly,
then executes the CLI commands `init`, `doctor`, `validate`, `run`
and validates the generated ZIP checksum and contents.

The Actions job log is a reproducible CI transcript, **not** proof of an
installed Windows desktop environment or actual local NVIDIA hardware.
No provider API key, cloud account, ComfyUI service or GPU weight file is
necessary for these tests. The independent real Windows 8GB VRAM model
benchmark remains [#24](https://github.com/interzettel/prehnite/issues/24).
No artifacts are tagged, uploaded as releases, or published to PyPI.
