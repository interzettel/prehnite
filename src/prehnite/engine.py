"""Sequential, resumable, cost-controlled production engine."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from pathlib import Path
from typing import Callable

from .images import image_info, make_cutout, preview_cutout, resize_to, sha256
from .artifacts import (ArtifactIntegrityError, atomic_copy_image, atomic_resize,
                        temporary_sibling, verified_image)
from .cache import CacheIntegrityError, StageCache
from .judges import HaikuJudge, check_verdict, technical
from .manifest import resolve_input, validate_job
from .providers import get_provider
from .reporting import export_report, package
from .schema import Asset, Endpoint, Manifest, Profile
from .store import Journal, JobStopped


class BudgetExceeded(RuntimeError):
    pass


def fingerprint(manifest: Manifest, profile: Profile) -> str:
    value = manifest.model_dump_json() + profile.model_dump_json()
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class Engine:
    def __init__(self, manifest: Manifest, profile: Profile, workspace: Path,
                 inputs: Path = Path("inputs"), job_token: str | None = None):
        validate_job(manifest, profile, inputs)
        self.manifest = manifest
        self.job_token = job_token
        self.profile = profile
        self.inputs = inputs
        self.journal = Journal(workspace, manifest.id)
        self.cache = StageCache(workspace, profile.cache) if profile.cache.enabled else None
        checksum = fingerprint(manifest, profile)
        previous = self.journal.fact("configuration_sha256")
        if previous is not None and previous != checksum:
            raise ValueError("Batch ID reused with changed manifest/profile; choose a new ID")
        self.journal.set_fact("configuration_sha256", checksum)
        self.journal.set_fact("manifest", manifest.model_dump())
        self.journal.set_fact("profile", profile.model_dump())
        self.verify_input_sources()

    def verify_input_sources(self) -> None:
        # The manifest/profile fingerprint does not include original-image bytes.
        # Without this guard a cached accepted export might be represented as
        # deriving from a different source than the one originally processed.
        fingerprints = {
            asset.id: sha256(resolve_input(self.inputs, asset.source))
            for asset in self.manifest.assets if asset.source
        }
        old = self.journal.fact("input_file_sha256")
        if old is None:
            if fingerprints and self.journal.fact("results", {}):
                raise ArtifactIntegrityError(
                    "Legacy accepted batch has no original-input fingerprints; "
                    "verify it manually and start a new batch ID"
                )
            self.journal.set_fact("input_file_sha256", fingerprints)
        elif old != fingerprints:
            raise ArtifactIntegrityError(
                "Original input bytes changed since batch started; "
                "start a new batch ID to protect provenance"
            )

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
              invoke: Callable, price_key: str = "",
              cache_request: dict | None = None) -> Path:
        self.journal.job_checkpoint(self.job_token)
        previous = self.journal.get(key)
        if previous and previous["status"] == "completed":
            try:
                verified_image(output, previous["data"].get("artifact_sha256"))
                return output
            except ArtifactIntegrityError:
                # A completed stage with a lost/corrupt output must never be
                # trusted. A known paid request ID permits *retrieval*, not resubmit.
                pass
        paid = endpoint.provider in ("fal", "anthropic")
        if previous and previous["status"] == "uncertain":
            raise RuntimeError(f"Ambiguous remote submission {key}: reconcile before retry")
        # The journal commits 'submitting' BEFORE the external call. If a
        # process dies between remote submission and receipt of a request ID,
        # assuming that no charge occurred would risk paying twice.
        if previous and paid and not previous["request_id"]:
            raise RuntimeError(
                f"Paid request {key} has no recoverable provider ID; "
                "reconcile it manually before retrying"
            )
        # A previous remote stage always requires its own journal recovery;
        # never conceal an ambiguous paid call by restoring an unrelated
        # cached result under the same image-stage key.
        cache_key = (self.cache.key(stage, endpoint, cache_request)
                     if self.cache and cache_request is not None else None)
        if previous is None and cache_key:
            cached = self.cache.restore(cache_key, output)
            if cached is not None:
                self.journal.put(key, stage, "completed",
                                 path=str(output), provider=endpoint.provider,
                                 model=endpoint.model, reserved_usd=0.0,
                                 data={"artifact_sha256": cached["sha256"],
                                       "artifact_bytes": output.stat().st_size,
                                       "cache_hit": True, "cache_key": cache_key})
                return output
        resume_id = previous["request_id"] if previous else None
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
        attempt_id = self.journal.begin_attempt(key, stage, endpoint.provider)
        started = time.perf_counter()
        try:
            with temporary_sibling(output) as temp:
                result = invoke(on_submit, resume_id, temp)
                if result.path.resolve() != temp.resolve():
                    raise ValueError("Provider wrote outside the atomic staging target")
                info = image_info(temp)
                # The existing published output survives an interrupted provider
                # write, and only fully decoded bytes cross this atomic boundary.
                os.replace(temp, output)
            metadata = {**result.metadata, "artifact_sha256": info["sha256"],
                        "artifact_bytes": output.stat().st_size}
            if cache_key:
                try:
                    metadata["cache_stored"] = self.cache.store(cache_key, output)
                    metadata["cache_key"] = cache_key
                except (OSError, ValueError):
                    # Caching is optional; a failed cache write must never
                    # invalidate a validated output or trigger a paid retry.
                    metadata["cache_stored"] = False
            self.journal.put(key, stage, "completed", request_id=resume_id,
                             path=str(output), provider=endpoint.provider,
                             model=endpoint.model, reserved_usd=estimate,
                             data=metadata)
            self.journal.finish_attempt(
                attempt_id, "completed", (time.perf_counter() - started) * 1000)
            return output
        except Exception as exc:
            # A failed remote get() with a request ID can be resumed without rebilling.
            status = "submitted" if resume_id else "uncertain" if paid else "failed"
            self.journal.put(key, stage, status, request_id=resume_id,
                             path=str(output), provider=endpoint.provider,
                             model=endpoint.model, reserved_usd=estimate,
                             data={"error": str(exc)[:500]})
            self.journal.finish_attempt(
                attempt_id, "failed", (time.perf_counter() - started) * 1000)
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
                   lambda on_submit, resume, temp: provider.generate(
                       asset.prompt, asset.aspect_ratio, tier, seed, temp, ep,
                       on_submit, resume), f"generation:{tier}",
                   cache_request={"prompt": asset.prompt,
                                  "aspect_ratio": asset.aspect_ratio,
                                  "tier": tier, "seed": seed})
        if variant == "enhanced_2k":
            ep = self.profile.upscale
            provider = get_provider(ep)
            up = root / "upscaled.png"
            self.stage(prefix + ":upscale", "upscaling", ep, up,
                       lambda on_submit, resume, temp: provider.upscale(
                           original, temp, ep, on_submit, resume), "upscale",
                       cache_request={"source_sha256": sha256(original),
                                      "scale": 2})
            original = up
        final = root / "final.png"
        atomic_resize(original, final, asset.target_size)
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
        rubric_winners = []
        for kind in ("blind", "prompt"):
            # Deliberately reverse the display order across independent
            # rubrics to expose blatant first-candidate preference. It does
            # NOT constitute statistical order-bias calibration.
            order = ("A", "B") if kind == "blind" else ("B", "A")
            key = f"{asset.id}:a{attempt}:judge:{kind}"
            record = self.journal.get(key)
            if record and record["status"] == "completed":
                raw = record["data"]
            elif record:
                # Anthropic's message endpoint has no resumable request ID.
                # A crash/timeout after dispatch may have billed the call.
                raise RuntimeError(
                    f"Paid judge {key} has uncertain status; reconcile manually"
                )
            else:
                self.journal.job_checkpoint(self.job_token)
                estimate = self.cost("judge")
                self.journal.put(key, "judge", "submitting", provider="anthropic",
                                 model=judge.model, reserved_usd=estimate)
                attempt_id = self.journal.begin_attempt(key, "judge", "anthropic")
                started = time.perf_counter()
                try:
                    verdict = HaikuJudge(judge).review(
                        {label: paths[label] for label in order},
                        asset.prompt if kind == "prompt" else None, kind)
                    raw = {"winner": verdict.winner, "scores": verdict.scores,
                           "reason": verdict.reason, "candidate_order": list(order)}
                    check_verdict(raw, tuple(paths))
                    self.journal.put(key, "judge", "completed", provider="anthropic",
                                     model=judge.model, reserved_usd=estimate, data=raw,
                                     tokens_in=verdict.tokens_in, tokens_out=verdict.tokens_out)
                except Exception as exc:
                    self.journal.put(key, "judge", "uncertain", provider="anthropic",
                                     model=judge.model, reserved_usd=estimate,
                                     data={"error": str(exc)[:500]})
                    self.journal.finish_attempt(
                        attempt_id, "failed", (time.perf_counter() - started) * 1000)
                    raise
                self.journal.finish_attempt(
                    attempt_id, "completed", (time.perf_counter() - started) * 1000)
            if raw.get("candidate_order") is not None and raw["candidate_order"] != list(order):
                raise ValueError("Cached judge candidate order differs; reconcile manually")
            checked = check_verdict(raw, tuple(paths))
            rubric_winners.append(checked.winner)
            for label in paths:
                total[label].append(checked.scores[label])
        if any(label in ("tie", "neither") for label in rubric_winners):
            return None, None, "Judge abstained; no automatic candidate acceptance"
        if len(set(rubric_winners)) != 1:
            return None, None, "Independent judge rubrics disagree; human review required"
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
        target_key = hashlib.sha256(name.encode("utf-8")).hexdigest()[:12]
        root = self.journal.root / "intermediates" / asset.id / "cutouts" / target_key
        mask = root / "mask.png"
        key = f"{asset.id}:cutout:{name}:mask"
        self.stage(key, "segmentation", ep, mask,
                   lambda on_submit, resume, temp: provider.segment(
                       selected, name, temp, ep, on_submit, resume), "segmentation",
                   cache_request={"source_sha256": sha256(selected),
                                  "target": name})
        # Retry is a real edge-refinement alternative, not a redundant paid model call.
        problems = []
        for refine in (False, True)[:self.profile.policy.maximum_attempts]:
            self.journal.job_checkpoint(self.job_token)
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
                        self.journal.job_checkpoint(self.job_token)
                        estimate = self.cost("judge")
                        self.journal.put(eval_key, "cutout_judge", "submitting",
                                         provider="anthropic", model=self.profile.judge.model,
                                         reserved_usd=estimate)
                        attempt_id = self.journal.begin_attempt(
                            eval_key, "cutout_judge", "anthropic")
                        started = time.perf_counter()
                        try:
                            verdict = HaikuJudge(self.profile.judge).review(
                                {"A": original_preview, "B": composite},
                                f"Extract the full {name}", "cutout")
                        except Exception as exc:
                            self.journal.put(eval_key, "cutout_judge", "uncertain",
                                             provider="anthropic", model=self.profile.judge.model,
                                             reserved_usd=estimate, data={"error": str(exc)[:500]})
                            self.journal.finish_attempt(
                                attempt_id, "failed",
                                (time.perf_counter() - started) * 1000)
                            raise
                        self.journal.finish_attempt(
                            attempt_id, "completed",
                            (time.perf_counter() - started) * 1000)
                        score = verdict.scores["B"]
                        self.journal.put(eval_key, "cutout_judge", "completed",
                                         provider="anthropic", model=self.profile.judge.model,
                                         reserved_usd=estimate, tokens_in=verdict.tokens_in,
                                         tokens_out=verdict.tokens_out,
                                         data={"score": score, "reason": verdict.reason})
                    if score < self.profile.policy.minimum_score:
                        raise ValueError("Cutout visual score below configured threshold")
                atomic_copy_image(output, target_output)
                return {"status": "accepted", "stats": stats, "refined": refine}
            except ValueError as exc:
                problems.append(str(exc))
        raise ValueError("Cutout rejected: " + "; ".join(problems))

    def selected_checksums(self, outputs: list[str]) -> dict[str, str]:
        root = (self.journal.root / "selected").resolve()
        hashes = {}
        for name in outputs:
            path = (root / name).resolve()
            if not path.is_relative_to(root):
                raise ArtifactIntegrityError("Selected output escapes batch directory")
            hashes[name] = image_info(path)["sha256"]
        return hashes

    def validate_saved_outputs(self, saved: dict) -> None:
        root = (self.journal.root / "selected").resolve()
        hashes = saved.get("outputs_sha256", {})
        for name in saved.get("outputs", []):
            path = (root / name).resolve()
            if not path.is_relative_to(root):
                raise ArtifactIntegrityError("Selected output escapes batch directory")
            verified_image(path, hashes.get(name))

    def process(self, asset: Asset) -> dict:
        output_root = self.journal.root / "selected"
        final_output = output_root / asset.output.image
        saved = self.journal.fact("results", {}).get(asset.id)
        if saved and saved.get("integrity_error"):
            raise ArtifactIntegrityError(saved["reason"])
        if saved and saved.get("status") == "accepted":
            self.validate_saved_outputs(saved)
            return saved
        if saved and saved.get("status") == "failed_cutouts":
            self.validate_saved_outputs(saved)
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
                    "outputs": outputs, "outputs_sha256": self.selected_checksums(outputs),
                    "reason": "; ".join(failures)}
        last_reason = "No acceptable candidate"
        for attempt in range(1, self.profile.policy.maximum_attempts + 1):
            self.journal.job_checkpoint(self.job_token)
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
                if asset.source or "disagree" in reason or "abstained" in reason:
                    # Don't purchase another generated batch just to resolve
                    # a conflict between supposedly independent judge rubrics.
                    break
                continue
            atomic_resize(candidates[winner], final_output, asset.target_size)
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
                        "outputs_sha256": self.selected_checksums(outputs),
                        "reason": "; ".join(cutout_failures),
                        "winning_variant": winner, "quality_score": score}
            return {"status": "accepted", "outputs": outputs,
                    "outputs_sha256": self.selected_checksums(outputs),
                    "winning_variant": winner, "quality_score": score,
                    "visual_quality_verified": score is not None,
                    "reason": reason, "attempt": attempt}
        return {"status": "rejected", "outputs": [], "reason": last_reason}

    def run(self) -> dict:
        with self.journal.exclusive():
            if self.job_token is not None:
                self.journal.job_start(self.job_token)
            try:
                result = self._run_locked()
            except JobStopped as stop:
                if self.job_token is not None and stop.status in ("paused", "cancelled"):
                    self.journal.job_finish(self.job_token, stop.status)
                    export_report(self.journal)
                    return {"job_status": stop.status,
                            "asset_results": self.journal.fact("results", {})}
                raise
            except Exception:
                if self.job_token is not None:
                    self.journal.job_finish(self.job_token, "failed",
                                            "Worker raised an exception; inspect local log")
                raise
            else:
                if self.job_token is not None:
                    self.journal.job_finish(self.job_token, "completed")
                return result

    def _run_locked(self) -> dict:
        self.verify_input_sources()
        self.journal.job_checkpoint(self.job_token)
        results = self.journal.fact("results", {})
        for asset in self.manifest.assets:
            self.journal.job_checkpoint(self.job_token, asset.id)
            if results.get(asset.id, {}).get("status") == "accepted":
                try:
                    self.validate_saved_outputs(results[asset.id])
                except ArtifactIntegrityError as exc:
                    results[asset.id] = {"status": "error", "outputs": [],
                                         "integrity_error": True, "reason": str(exc)}
                    self.journal.set_fact("results", results)
                    export_report(self.journal)
                    continue
                else:
                    continue
            try:
                result = self.process(asset)
            except BudgetExceeded:
                self.journal.set_fact("results", results)
                export_report(self.journal)
                raise
            except JobStopped:
                self.journal.set_fact("results", results)
                raise
            except ArtifactIntegrityError as exc:
                result = {"status": "error", "outputs": [], "integrity_error": True,
                          "reason": str(exc)[:500]}
            except Exception as exc:
                result = {"status": "error", "outputs": [], "reason": str(exc)[:500]}
            results[asset.id] = result
            self.journal.set_fact("results", results)
            export_report(self.journal)
            self.journal.job_checkpoint(self.job_token)
        self.journal.job_checkpoint(self.job_token)
        report = export_report(self.journal)
        package(self.journal)
        return report
