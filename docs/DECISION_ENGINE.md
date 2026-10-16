# Provider-neutral decision engine · first offline tranche

[Tracking issue #116](https://github.com/interzettel/prehnite/issues/116) · related [provider choice #21](https://github.com/interzettel/prehnite/issues/21), [local judge Q05 #27](https://github.com/interzettel/prehnite/issues/27), [human calibration #28](https://github.com/interzettel/prehnite/issues/28), [repair #31](https://github.com/interzettel/prehnite/issues/31), and experimental [Jev #107](https://github.com/interzettel/prehnite/issues/107).

## Owner decisions (2026-10-16)

- **Mixed image assets:** separate product/object and portrait benchmarks, not one pooled artificial quality score.
- **Bounded automatic technical rejection and local targeted repair:** expressly allowed, with maximum attempts and stage-aware limits. Never mutate previously accepted deliverables.
- **Synthetic and rights-cleared evaluation material first:** owner may supply real samples later.
- **Local-first, no credentials, paid inference, subscriptions or cloud uploads** in this tranche.

## Implemented contract

`src/prehnite/decision_engine.py` contains pure typed capabilities/evidence and a **non-mutating action planner**. It supports the initial declared provider families:

| Family | Typed responses in this tranche | Evidence qualification |
| --- | --- | --- |
| Jev 1.14 | yes probability, Choice, ordered-score semantics (not reinterpreted), experimental Box | Official offline fixture parser; no TypeSafe HTTP |
| OpenAI-compatible VLMs | typed probability, categorical choice, rubric in *Prehnite internal mock schema* | No invented universal chat-completions wire payload |
| Anthropic | existing validated rubric Verdict | Scores are rubric satisfaction, **not** probabilities |
| Local | deterministic technical flag | Technical check is not a judgment of aesthetic quality |

`require_capability` gates required kind, media type and external upload approval. This step **does not install any OpenAI, Anthropic, Jev or Comfy model** and does not read env keys or dispatch HTTP requests. Model revision identifiers in mocks are versioned labels, not evidence that external provider APIs were called or work interchangeably.

`DecisionEvidence` records the provider, model, typed value, specific bounded subject, image SHA256 and the explicit uncalibrated status. An abstention is its own typed status. It refuses falsified calibration, booleans masquerading as probabilities, malformed bounding boxes, changing/unsupported provider capabilities, nonfinite values and unbound image data.

### Bounded local candidate policy

`RepairLimits` **defaults to advisory-only**; an operator who wants deterministic automatic actions opts in to `allow_technical_auto_rejection=True` and `allow_local_mask_repair=True`. Per-stage attempts are bounded 1–5 and mask repairs 0–3. Paid additional USD must be *exactly zero*; no implied provider authorization is possible. A `DecisionPlan` never performs execution or changes an accepted output.

| Input evidence | Authorized action (with opt-in) |
| --- | --- |
| Known empty mask or alpha-edge contamination on cutout/segmentation | Schedule **at most** allowed local mask repair(s); then reject only the *unaccepted candidate* |
| Full-frame mask, invalid image geometry/encoding | Reject unaccepted candidate after deterministic local validation |
| Multiple product/person instances, unverified image quality, model disagreement or abstention | Human review |
| Existing accepted image, ambiguous billable submission, active remote submission, exhausted total stage attempts | Human review, **no remote retry or overwrite** |
| Jev/OpenAI/Anthropic probability or rubric alone, regardless of confidence | Human review until real calibration + another reviewed policy gate |

There is no model-driven automatic accept or irreversible deletion. Explicit permission to *attempt* automatic local repair is not permission for the model to bill, overwrite or delete an accepted asset. The existing engine's cutout refine path remains unchanged in this tranche; **this planner is a tested decision contract, not yet a connected repair executor**. Wiring it to the persistent journal/unique local operation IDs and trustworthy alpha-edge detectors is next in #31/#29. That code must revalidate all preconditions on replay, preserve accepted artifacts, and avoid a paid re-segmentation call for a local mask-only repair.

### Synthetic product / portrait acceptance fixtures

`tests/test_decision_engine.py` covers product empty/full masks, multi-object ambiguity; portrait alpha-edge contamination, ambiguity and invalid geometry. Tests exercise the same typed contract with mocked Jev/OpenAI-compatible/Anthropic/local evidence, caps, billing uncertainty, accepted-output preservation, explicit abstentions, malformed payloads and zero-USD guarantees.

The suite uses synthetic **records**, not images. It therefore does **not** prove hair masking fidelity, perceptual quality, real VLM correctness, segmentation quality, GPU performance, provider interoperability, or calibration. Those require documented rights-cleared inputs and owner-reviewed acceptance experiments.

## Next reviewable increments

1. Wire the deterministic local-repair plan to a persistent per-mask operation with bounded retry, result SHA256, and isolated saved outputs; test hard-kill/replay.
2. Add concrete foreground matte cleanup and edge/color contamination diagnostics against synthetic checkerboards, hard backgrounds, translucent edges and hair-like fixtures, separately for portrait/product.
3. Assemble permitted human-reviewed cohorts; compare provider/judge disagreement and **cost per human-accepted deliverable** under explicitly authorized inference budgets. The Jev danger-zone switch remains independently opt-in, and no live model credentials are needed now.

Every production score must specify what was measured and its uncertainty; a typed probability alone is not a calibrated quality grade.
