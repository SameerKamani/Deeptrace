from __future__ import annotations

from typing import Any, Dict

import numpy as np

from ..models.evidence import EvidenceSignal, SignalStatus, SignalSupport
from .base import Detector


class LightingConsistencyDetector(Detector):
    id = "lighting_consistency"
    name = "Lighting Physics & Contrast Geometry"
    category = "lighting"

    async def analyze(self, image, context: Dict[str, Any]) -> EvidenceSignal:
        arr = np.asarray(image.convert("L"), dtype=np.float32)
        
        dynamic_range = float(arr.max() - arr.min())
        clipped_highlights = float(np.mean(arr >= 253.0))
        crushed_blacks = float(np.mean(arr <= 2.0))
        
        # Calculate local contrast variance to check for "HDR flattening"
        windows = [arr[i:i+64, j:j+64] for i in range(0, arr.shape[0]-64, 64) for j in range(0, arr.shape[1]-64, 64)]
        
        if windows:
            window_means = [np.mean(w) for w in windows]
            global_contrast_variance = np.var(window_means)
        else:
            global_contrast_variance = 0.0

        observations = [
            f"Physical dynamic range spread: {dynamic_range:.0f}/255",
            f"Highlight clipping geometry: {clipped_highlights * 100:.2f}%",
            f"Crushed black geometry: {crushed_blacks * 100:.2f}%",
        ]

        supports = SignalSupport.UNKNOWN
        reliability = 0.4
        summary = "Lighting physics evaluated."

        # Real optics struggle with extreme dynamic ranges; they clip highlights or crush blacks.
        # AI generators (Diffusion) often output unnaturally perfect "HDR" lighting where everything is exposed physically identically.
        is_perfectly_flat = clipped_highlights < 0.001 and crushed_blacks < 0.001 and dynamic_range > 150
        
        if is_perfectly_flat and global_contrast_variance < 1000:
            observations.append("CRITICAL: Unnatural HDR latency detected. Scene exhibits zero physical optical clipping despite massive dynamic range.")
            supports = SignalSupport.AI_GENERATED
            reliability = 0.65
            summary = "Lighting is procedurally flattened, lacking true optic exposure variance."
        elif clipped_highlights > 0.02 or crushed_blacks > 0.05:
            observations.append("Severe exposure boundaries detected (blown highlights or crushed shadows). This strongly aligns with raw physical camera sensors.")
            supports = SignalSupport.AUTHENTIC
            reliability = 0.55
            summary = "True optical exposure failure thresholds detected."
        else:
            observations.append("Lighting topology is well balanced but lacks distinct physical or generative boundaries. Profile is inconclusive.")
            supports = SignalSupport.INCONCLUSIVE
            reliability = 0.3
            summary = "Lighting profile is balanced and non-directional."

        return EvidenceSignal(
            id=self.id,
            name=self.name,
            category=self.category,
            status=SignalStatus.OK,
            reliability=reliability,
            summary=summary,
            observations=observations,
            metrics={
                "dynamic_range": dynamic_range,
                "clipped_highlights": clipped_highlights,
                "crushed_blacks": crushed_blacks,
                "contrast_variance": float(global_contrast_variance),
            },
            supports=supports,
            notes="Evaluates optical exposure realism. Generative models rarely replicate true physical clipping.",
        )
