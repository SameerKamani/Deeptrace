from __future__ import annotations

from typing import Any, Dict

import numpy as np

from ..models.evidence import EvidenceSignal, SignalStatus, SignalSupport
from .base import Detector


class LightingConsistencyDetector(Detector):
    id = "lighting_consistency"
    name = "Lighting & Physical Consistency"
    category = "lighting"

    async def analyze(self, image, context: Dict[str, Any]) -> EvidenceSignal:
        arr = np.asarray(image.convert("L"), dtype=np.float32)
        dynamic_range = float(arr.max() - arr.min())
        clipped_highlights = float(np.mean(arr >= 250.0))

        observations = [
            f"Dynamic range: {dynamic_range:.2f}",
            f"Highlight clipping ratio: {clipped_highlights:.3f}",
        ]

        return EvidenceSignal(
            id=self.id,
            name=self.name,
            category=self.category,
            status=SignalStatus.OK,
            reliability=0.15,
            summary="Computed simple lighting heuristics.",
            observations=observations,
            metrics={
                "dynamic_range": dynamic_range,
                "clipped_highlights": clipped_highlights,
            },
            supports=SignalSupport.UNKNOWN,
            notes="Placeholder heuristic; advanced lighting reasoning to be added.",
        )
