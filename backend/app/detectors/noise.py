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
        summary = "Noise profile evaluated."

        # Real cameras almost always have some base ISO noise. Generative AI can be mathematically flat in unfocused areas.
        if dead_zone_ratio > 0.4 and high_freq_overall < 4.0:
            observations.append(f"CRITICAL: Unnatural topological smoothness detected. {dead_zone_ratio*100:.0f}% of the image lacks base sensor noise structure.")
            supports = SignalSupport.AI_GENERATED
            reliability = 0.65
            summary = "Profoundly unnatural noise uniformity detected."
        elif variance > 1000.0 and high_freq_overall > 15.0:
            observations.append("Heavy, highly chaotic noise structure. Consistent with high-ISO real photography, but could be artificial post-grain.")
            supports = SignalSupport.AUTHENTIC
            reliability = 0.35
            summary = "Consistent with natural high-ISO sensor grain."
        elif dead_zone_ratio < 0.05 and variance > 50.0:
            observations.append("Subtle, uniform grain structure present across all focal depths, strongly indicating real glass/sensor optics.")
            supports = SignalSupport.AUTHENTIC
            reliability = 0.55
            summary = "Lifelike thermal noise and focal depth grain."
        else:
            observations.append("Noise distribution is completely mid-range. Inconclusive profile.")
            supports = SignalSupport.INCONCLUSIVE
            reliability = 0.2
            summary = "Noise structure provides no defensive statistical deviation."

        return EvidenceSignal(
            id=self.id,
            name=self.name,
            category=self.category,
            status=SignalStatus.OK,
            reliability=reliability,
            summary=summary,
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
