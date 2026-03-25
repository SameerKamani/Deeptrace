from __future__ import annotations

from typing import Any, Dict

import numpy as np

from ..models.evidence import EvidenceSignal, SignalStatus, SignalSupport
from .base import Detector


class NoisePatternDetector(Detector):
    id = "noise_pattern_analysis"
    name = "Thermal Noise & Sensor Consistency"
    category = "noise"

    async def analyze(self, image, context: Dict[str, Any]) -> EvidenceSignal:
        # Convert to grayscale for structural thermal noise analysis
        arr = np.asarray(image.convert("L"), dtype=np.float32)

        mean = float(arr.mean())
        variance = float(arr.var())

        # High-frequency energy evaluates how "sharp" or "chaotic" pixel transitions are.
        # Deep generative models tend to have unnaturally smooth transitions in low-detail areas
        # and aggressively sharp ones in high-detail areas (bimodality).
        diff_y = np.abs(np.diff(arr, axis=0))
        diff_x = np.abs(np.diff(arr, axis=1))
        
        hf_energy_y = float(np.mean(diff_y))
        hf_energy_x = float(np.mean(diff_x))
        high_freq_overall = (hf_energy_y + hf_energy_x) / 2.0

        # Calculate localized standard deviation to find "dead zones" characteristic of AI 
        # (AI struggles to replicate uniform ISO noise in flat areas like skies or blurry backgrounds)
        # Using a simple block approach.
        windows = [arr[i:i+32, j:j+32] for i in range(0, arr.shape[0]-32, 32) for j in range(0, arr.shape[1]-32, 32)]
        if windows:
            window_vars = [np.var(w) for w in windows]
            dead_zone_ratio = sum(1 for v in window_vars if v < 2.0) / len(window_vars)
        else:
            dead_zone_ratio = 0.0

        observations = [
            f"Global thermal variance: {variance:.1f} (Mean: {mean:.1f})",
            f"High-frequency spatial energy: {high_freq_overall:.2f}",
        ]

        # Logic for verdicts
        supports = SignalSupport.UNKNOWN
        reliability = 0.4
        summary = "The image texture and noise pattern were evaluated."
        what_found = "The texture pattern did not strongly stand out yet."
        why_it_matters = "Real cameras usually leave behind at least some sensor noise, while generated or heavily filtered images can look unnaturally smooth."

        # Real cameras almost always have some base ISO noise. Generative AI can be mathematically flat in unfocused areas.
        if dead_zone_ratio > 0.4 and high_freq_overall < 4.0:
            observations.append(f"CRITICAL: Unnatural topological smoothness detected. {dead_zone_ratio*100:.0f}% of the image lacks base sensor noise structure.")
            supports = SignalSupport.AI_GENERATED
            reliability = 0.65
            summary = "Large parts of the image look unusually smooth for a normal camera photo."
            what_found = (
                f"Around {dead_zone_ratio:.0%} of the image looks too flat and lacks the small grain a camera usually leaves behind."
            )
            why_it_matters = "That leans toward AI generation or very heavy filtering, because real photos rarely stay this clean across broad areas."
        elif variance > 1000.0 and high_freq_overall > 15.0:
            observations.append("Heavy, highly chaotic noise structure. Consistent with high-ISO real photography, but could be artificial post-grain.")
            supports = SignalSupport.AUTHENTIC
            reliability = 0.35
            summary = "The image contains strong grain that looks more like a noisy real photo than a clean generated image."
            what_found = "The texture is busy and noisy rather than overly smooth."
            why_it_matters = "That can happen in real photos shot in difficult conditions, although added grain can sometimes imitate it."
        elif dead_zone_ratio < 0.05 and variance > 50.0:
            observations.append("Subtle, uniform grain structure present across all focal depths, strongly indicating real glass/sensor optics.")
            supports = SignalSupport.AUTHENTIC
            reliability = 0.55
            summary = "The image has natural-looking fine grain instead of perfectly smooth surfaces."
            what_found = "We see subtle texture across the image that looks more like normal camera grain than synthetic smoothness."
            why_it_matters = "That slightly favors a real photo, because cameras usually leave behind a small amount of natural sensor noise."
        else:
            observations.append("Noise distribution is completely mid-range. Inconclusive profile.")
            supports = SignalSupport.INCONCLUSIVE
            reliability = 0.2
            summary = "The texture pattern is mixed and does not clearly point either way."
            what_found = "The image is neither clearly too smooth nor clearly rich in natural camera grain."
            why_it_matters = "That makes this signal weak for decision-making on its own."

        return EvidenceSignal(
            id=self.id,
            name=self.name,
            category=self.category,
            status=SignalStatus.OK,
            reliability=reliability,
            summary=summary,
            what_checked="We checked the tiny texture of the image to see whether it behaves like normal camera sensor noise.",
            what_found=what_found,
            why_it_matters=why_it_matters,
            caveat="Editing, denoising, upscaling, filters, or compression can change this signal, so it should never be used alone.",
            observations=observations,
            metrics={
                "mean": mean,
                "variance": variance,
                "high_freq_energy": high_freq_overall,
                "dead_zone_ratio": dead_zone_ratio
            },
            supports=supports,
            notes="Analyzes physical thermal discrepancies; AI often fails to render true Gaussian ISO sensor noise in out-of-focus areas.",
        )
