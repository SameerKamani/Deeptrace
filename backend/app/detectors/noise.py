from __future__ import annotations

from typing import Any, Dict

import numpy as np

from ..models.evidence import EvidenceSignal, SignalStatus, SignalSupport
from .base import Detector


class NoisePatternDetector(Detector):
    id = "noise_pattern_analysis"
    name = "Noise & Sensor Patterns"
    category = "noise"

    async def analyze(self, image, context: Dict[str, Any]) -> EvidenceSignal:
        arr = np.asarray(image.convert("L"), dtype=np.float32)
        mean = float(arr.mean())
        variance = float(arr.var())
        high_freq_energy = float(np.mean(np.abs(np.diff(arr, axis=0)))) + float(
            np.mean(np.abs(np.diff(arr, axis=1)))
        )

        observations = [
            f"Grayscale mean intensity: {mean:.2f}",
            f"Grayscale variance: {variance:.2f}",
            f"High-frequency energy: {high_freq_energy:.2f}",
        ]

        return EvidenceSignal(
            id=self.id,
            name=self.name,
            category=self.category,
            status=SignalStatus.OK,
            reliability=0.2,
            summary="Basic noise statistics computed.",
            observations=observations,
            metrics={
                "mean": mean,
                "variance": variance,
                "high_freq_energy": high_freq_energy,
            },
            supports=SignalSupport.UNKNOWN,
            notes="Heuristic-only signal; does not directly indicate authenticity.",
        )
