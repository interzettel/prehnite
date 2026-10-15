"""Sequential, resumable, cost-controlled production engine."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Callable

from .images import image_info, make_cutout, preview_cutout, resize_to
from .judges import HaikuJudge, technical
from .manifest import resolve_input, validate_job
from .providers import get_provider
from .reporting import export_report, package
from .schema import Asset, Endpoint, Manifest, Profile
from .store import Journal


class BudgetExceeded(RuntimeError):
    pass


def fingerprint(manifest: Manifest, profile: Profile) -> str:
    value = manifest.model_dump_json() + profile.model_dump_json()
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class Engine:
    def __init__(self, manifest: Manifest, profile: Profile, workspace: Path,
                 inputs: Path = Path("inputs")):
        validate_job(manifest, profile, inputs)
        self.manifest = manifest
        self.profile = profile
        self.inputs = inputs
        self.journal = Journal(workspace, manifest.id)
        checksum = fingerprint(manifest, profile)
        previous = self.journal.fact("configuration_sha256")
        if previous is not None and previous != checksum:
            raise ValueError("Batch ID reused with changed manifest/profile; choose a new ID")
        self.journal.set_fact("configuration_sha256", checksum)
        self.journal.set_fact("manifest", manifest.model_dump())
        self.journal.set_fact("profile", profile.model_dump())

    def cost(self, stage: str) -> float:
        if not self.profile.costs.allow_paid:
            raise PermissionError("Paid inference is disabled")
        if stage not in self.profile.costs.estimates_usd:
            raise ValueError(f"No explicit cost estimate for paid operation {stage}")
        estimate = self.profile.costs.estimates_usd[stage]
        if estimate < 0:
            raise ValueError("Negative estimate")
        if self.journal.reserved() + estimate > self.profile.costs.max_usd + 1e-9:
            raise BudgetExceeded("Estimated/committed cost exceeds batch spending limit")
        return estimate

    def stage(self, key: str, stage: str, endpoint: Endpoint, output: Path,
              invoke: Callable, price_key: str = "") -> Path:
        previous = self.journal.get(key)
        if previous and previous["status"] == "completed" and output.is_file():
            image_info(output)
            return output
        if previous and previous["status"] == "uncertain":
            raise RuntimeError(f"Ambiguous remote submission {key}: reconcile before retry")
        resume_id = previous["request_id"] if previous else None
        paid = endpoint.provider in ("fal", "anthropic")
        estimate = (float(previous["reserved_usd"]) if previous else
                    self.cost(price_key) if paid else 0.0)
        if not previous:
            self.journal.put(key, stage, "submitting" if paid else "running",
                             path=str(output), provider=endpoint.provider,
                             model=endpoint.model, reserved_usd=estimate)
        def on_submit(request_id: str):
            nonlocal resume_id
            resume_id = request_id
            self.journal.put(key, stage, "submitted", request_id=request_id,
                             path=str(output), provider=endpoint.provider,
                             model=endpoint.model, reserved_usd=estimate)
        try:
            result = invoke(on_submit, resume_id)
            image_info(result.path)
            self.journal.put(key, stage, "completed", request_id=resume_id,
                             path=str(output), provider=endpoint.provider,
                             model=endpoint.model, reserved_usd=estimate,
                             data=result.metadata)
            return output
        except Exception as exc:
            # A failed remote get() with a request ID can be resumed without rebilling.
            status = "submitted" if resume_id else "uncertain" if paid else "failed"
            self.journal.put(key, stage, status, request_id=resume_id,
                             path=str(output), provider=endpoint.provider,
                             model=endpoint.model, reserved_usd=estimate,
                             data={"error": str(exc)[:500]})
            raise

    def generate(self, asset: Asset, variant: str, attempt: int, root: Path) -> Path:
        tier = "2k" if variant == "enhanced_2k" else "4k"
        prefix = f"{asset.id}:a{attempt}:{variant}"
        original = root / "generated.png"
        ep = self.profile.generation
        provider = get_provider(ep)
        seed = (asset.seed if asset.seed is not None else
                int(hashlib.sha256(asset.id.encode()).hexdigest()[:8], 16)) + attempt - 1
        self.stage(prefix + ":generate", "generation", ep, original,
                   lambda on_submit, resume: provider.generate(
                       asset.prompt, asset.aspect_ratio, tier, seed, original, ep,
                       on_submit, resume), f"generation:{tier}")
        if variant == "enhanced_2k":
            ep = self.profile.upscale
            provider = get_provider(ep)
            up = root / "upscaled.png"
            self.stage(prefix + ":upscale", "upscaling", ep, up,
                       lambda on_submit, resume: provider.upscale(
                           original, up, ep, on_submit, resume), "upscale")
            original = up
        final = root / "final.png"
        if not final.is_file():
            resize_to(original, final, asset.target_size)
        image_info(final)
        return final

    def adjudicate(self, asset: Asset, candidates: dict[str, Path],
                   attempt: int) -> tuple[str | None, float | None, str]:
        judge = self.profile.judge
        if judge.provider == "demo":
            for path in candidates.values():
                if technical(path, asset.target_size).scores["A"] < 1:
                    return None, 0.0, "Technical validation failed"
            return next(iter(candidates)), None, "Technical-only; visually unverified"
        if judge.provider == "disabled":
            return next(iter(candidates)), None, "No judge configured"
        if judge.provider != "anthropic":
            raise ValueError("Unsupported judge provider")
        if len(candidates) != 2:
            raise ValueError("Haiku pair judge requires exactly two candidates")
        paths = dict(zip(("A", "B"), candidates.values()))
        total = {key: [] for key in paths}
        for kind in ("blind", "prompt"):
            key = f"{asset.id}:a{attempt}:judge:{kind}"
            record = self.journal.get(key)
            if record and record["status"] == "completed":
                raw = record["data"]
            else:
                estimate = self.cost("judge") if not record else record["reserved_usd"]
                self.journal.put(key, "judge", "submitting", provider="anthropic",
                                 model=judge.model, reserved_usd=estimate)
                try:
                    verdict = HaikuJudge(judge).review(
                        paths, asset.prompt if kind == "prompt" else None, kind)
                except Exception as exc:
                    self.journal.put(key, "judge", "uncertain", provider="anthropic",
                                     model=judge.model, reserved_usd=estimate,
                                     data={"error": str(exc)[:500]})
                    raise
                raw = {"winner": verdict.winner, "scores": verdict.scores,
                       "reason": verdict.reason}
                self.journal.put(key, "judge", "completed", provider="anthropic",
                                 model=judge.model, reserved_usd=estimate, data=raw,
                                 tokens_in=verdict.tokens_in, tokens_out=verdict.tokens_out)
            for label in paths:
                total[label].append(float(raw["scores"][label]))
        # Gate on worst-of-two rubrics; do not average away important violations.
        ranking = sorted(((min(scores), key) for key, scores in total.items()), reverse=True)
        score, label = ranking[0]
        selection = list(candidates)[("A", "B").index(label)]
        if score < self.profile.policy.minimum_score:
            return None, score, "Quality threshold not met"
        return selection, score, "Two independent Haiku rubrics"

    def cutout(self, asset: Asset, selected: Path, name: str, attempt: int,
               target_output: Path) -> dict:
        ep = self.profile.segmentation
        provider = get_provider(ep)
        root = self.journal.root / "intermediates" / asset.id / "cutouts" / name
        mask = root / "mask.png"
        key = f"{asset.id}:cutout:{name}:mask"
        self.stage(key, "segmentation", ep, mask,
                   lambda on_submit, resume: provider.segment(
                       selected, name, mask, ep, on_submit, resume), "segmentation")
        # Retry is a real edge-refinement alternative, not a redundant paid model call.
        problems = []
        for refine in (False, True)[:self.profile.policy.maximum_attempts]:
            output = root / ("refined.png" if refine else "raw.png")
            try:
                stats = make_cutout(selected, mask, output, refine=refine)
                if stats["coverage"] < self.profile.policy.cutout_minimum_coverage:
                    raise ValueError("Mask coverage below threshold")
                if self.profile.judge.provider == "anthropic":
                    original_preview = root / "source_preview.jpg"
                    # A flat RGB image suffices for original preview.
                    from .judges import preview
                    from PIL import Image
                    with Image.open(selected) as im:
                        rgb = im.convert("RGB")
                        rgb.thumbnail((1100, 1100))
                        rgb.save(original_preview, "JPEG", quality=85)
                    composite = preview_cutout(output, root / "cutout_preview.jpg")
                    eval_key = f"{asset.id}:cutout:{name}:judge:{int(refine)}"
                    old = self.journal.get(eval_key)
                    if old and old["status"] == "completed":
                        score = float(old["data"]["score"])
                    elif old:
                        raise RuntimeError("Ambiguous paid cutout judgment; reconcile first")
                    else:
                        estimate = self.cost("judge")
                        self.journal.put(eval_key, "cutout_judge", "submitting",
                                         provider="anthropic", model=self.profile.judge.model,
                                         reserved_usd=estimate)
                        try:
                            verdict = HaikuJudge(self.profile.judge).review(
                                {"A": original_preview, "B": composite},
                                f"Extract the full {name}", "cutout")
                        except Exception as exc:
                            self.journal.put(eval_key, "cutout_judge", "uncertain",
                                             provider="anthropic", model=self.profile.judge.model,
                                             reserved_usd=estimate, data={"error": str(exc)[:500]})
                            raise
                        score = verdict.scores["B"]
                        self.journal.put(eval_key, "cutout_judge", "completed",
                                         provider="anthropic", model=self.profile.judge.model,
                                         reserved_usd=estimate, tokens_in=verdict.tokens_in,
                                         tokens_out=verdict.tokens_out,
                                         data={"score": score, "reason": verdict.reason})
                    if score < self.profile.policy.minimum_score:
                        raise ValueError("Cutout visual score below configured threshold")
                target_output.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(output, target_output)
                return {"status": "accepted", "stats": stats, "refined": refine}
            except ValueError as exc:
                problems.append(str(exc))
        raise ValueError("Cutout rejected: " + "; ".join(problems))

    def process(self, asset: Asset) -> dict:
        output_root = self.journal.root / "selected"
        final_output = output_root / asset.output.image
        saved = self.journal.fact("results", {}).get(asset.id)
        if saved and saved.get("status") == "accepted" and all(
            (output_root / path).is_file() for path in saved["outputs"]):
            return saved
        if saved and saved.get("status") == "failed_cutouts" and final_output.is_file():
            outputs = [asset.output.image]
            failures = []
            for target in asset.targets:
                destination = output_root / asset.output.cutouts[target]
                if destination.is_file():
                    outputs.append(asset.output.cutouts[target])
                    continue
                try:
                    self.cutout(asset, final_output, target, 1, destination)
                    outputs.append(asset.output.cutouts[target])
                except ValueError as exc:
                    failures.append(str(exc))
            return {**saved, "status": "failed_cutouts" if failures else "accepted",
                    "outputs": outputs, "reason": "; ".join(failures)}
        last_reason = "No acceptable candidate"
        for attempt in range(1, self.profile.policy.maximum_attempts + 1):
            candidates: dict[str, Path] = {}
            if asset.source:
                candidates["source"] = resolve_input(self.inputs, asset.source)
            else:
                for variant in self.profile.variants:
                    root = self.journal.root / "intermediates" / asset.id / (
                        f"attempt-{attempt}") / variant
                    candidates[variant] = self.generate(asset, variant, attempt, root)
            if len(candidates) == 1 and self.profile.judge.provider == "anthropic":
                # Single-candidate prompt fidelity is not yet implemented.
                raise ValueError("Haiku pairwise judge needs both variants")
            winner, score, reason = self.adjudicate(asset, candidates, attempt)
            if score is None and self.profile.policy.uncertain == "reject":
                last_reason = "Visual quality unverified and policy rejects uncertainty"
                break
            if winner is None:
                last_reason = reason
                if asset.source:
                    break  # A fixed source cannot improve by repeating an identical judge call.
                continue
            final_output.parent.mkdir(parents=True, exist_ok=True)
            resize_to(candidates[winner], final_output, asset.target_size)
            outputs = [asset.output.image]
            cutout_failures = []
            for target in asset.targets:
                destination = output_root / asset.output.cutouts[target]
                try:
                    self.cutout(asset, final_output, target, attempt, destination)
                    outputs.append(asset.output.cutouts[target])
                except ValueError as exc:
                    cutout_failures.append(f"{target}: {exc}")
            if cutout_failures:
                # Keep accepted image; next run can retry only failed cutout.
                return {"status": "failed_cutouts", "outputs": outputs,
                        "reason": "; ".join(cutout_failures),
                        "winning_variant": winner, "quality_score": score}
            return {"status": "accepted", "outputs": outputs,
                    "winning_variant": winner, "quality_score": score,
                    "visual_quality_verified": score is not None,
                    "reason": reason, "attempt": attempt}
        return {"status": "rejected", "outputs": [], "reason": last_reason}

    def run(self) -> dict:
        results = self.journal.fact("results", {})
        for asset in self.manifest.assets:
            if results.get(asset.id, {}).get("status") == "accepted" and all(
                (self.journal.root / "selected" / path).is_file()
                for path in results[asset.id].get("outputs", [])):
                continue
            try:
                result = self.process(asset)
            except BudgetExceeded:
                self.journal.set_fact("results", results)
                export_report(self.journal)
                raise
            except Exception as exc:
                result = {"status": "error", "outputs": [], "reason": str(exc)[:500]}
            results[asset.id] = result
            self.journal.set_fact("results", results)
            export_report(self.journal)
        report = export_report(self.journal)
        package(self.journal)
        return report
