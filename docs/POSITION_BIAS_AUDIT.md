# Fixed-rubric positional-bias audit

When two pictures are judged side by side, presentation order can influence
the result. To test that, the *same two unmodified image files* are reviewed
with the *same prompt and exact rubric* twice: once **A=image1, B=image2**,
then **A=image2, B=image1**. Scores and winners are remapped back to stable
candidate IDs rather than treated as interchangeable A/B labels.

The implementation is [`prehnite.position_audit`](../src/prehnite/position_audit.py).
It is **injection-only**: a reviewer callback must be provided explicitly.
Importing or running this module never creates a paid model client. The
callback receives an insertion-ordered map of A/B image paths, the unchanged
prompt and the unchanged rubric, and returns a typed `Verdict` or equivalent
validated mapping. `check_verdict` enforces complete finite scores,
winner consistency and valid tie/neither abstentions.

## Try it without a model

After `pip install -e .`, run:

```bash
python examples/position_bias_demo.py --output position-audit.json
```

This generates two 64-pixel synthetic PNGs in a disposable local directory,
uses a deliberately first-position-biased fake judge, and writes a deterministic
JSON report. There are **no model weights, API credentials, network calls, fees
or private-user media** in this demonstration.

The report exposes each observed order, displayed winner, *identity-mapped*
winner, identity-mapped scores, first-position winner count, decisiveness,
abstentions, order-invariance, two-order winner flip, per-candidate score
shifts and **mean first-slot score lift**. Example:
a consistent model chooses red both times (A then B), while a first-slot
bias chooses red first and blue second. A `tie` or `neither` is an
abstention, *not* a win for A.

## Interpretation and safety

A single A/B+B/A trial is a **diagnostic**, not a calibrated bias probability
or quality score. Two runs are correlated and may be stochastic. The report
has no p-value, statistical significance, human-agreement claim, or
automatic approval gate. Positive first-slot score lift and winner flips
are warning signals, not proof of causality.

A serious study needs independently sourced, rights-cleared images and
explicit permission for any personal data, a fixed rubric chosen *before*
results, stratification by scene/defect type, randomized pair order across
trials, multiple seeds/judges, repeated independent runs, uncertainty
intervals, calibration against blinded human annotations and a prespecified
meaningful-effect threshold. For example, a hypothetical `0.05` slot-lift
threshold must be chosen by the owner **before** running a study, validated
against judge/human disagreement, and not retroactively optimized to pass.
No human ground truth or externally validated cutoff currently exists.

The report deliberately does not store local absolute image paths, but it
contains the **prompt, rubric, candidate IDs and SHA256 image fingerprints**.
Do not commit a real-user report or private images to the public repository
without reviewing their consent and sharing implications. Input files are
hashed before and after each invocation to reject mutation; this is not a
security sandbox against a malicious judge callback.

If you later connect a paid judge, this diagnostic is **two billable reviews
per pair**, not one. Require separate owner authorization, a positive
`max_usd`, explicit cloud-upload permission and budget estimation before
any such work. The audited output must also distinguish prompt-visible
vs prompt-blind rubrics; **changing the rubric between orders invalidates
the positional-bias comparison**. Nothing in this fixture establishes
production judge quality.
