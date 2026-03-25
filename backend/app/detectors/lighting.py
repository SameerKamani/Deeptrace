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
        summary = "The lighting and exposure pattern were evaluated."
        what_found = "The scene did not yet show a strong lighting clue in either direction."
        why_it_matters = "Real cameras usually show imperfect exposure behavior, while generated images can look unnaturally even or polished."

        # Real optics struggle with extreme dynamic ranges; they clip highlights or crush blacks.
        # AI generators (Diffusion) often output unnaturally perfect "HDR" lighting where everything is exposed physically identically.
        is_perfectly_flat = clipped_highlights < 0.001 and crushed_blacks < 0.001 and dynamic_range > 150
        
        if is_perfectly_flat and global_contrast_variance < 1000:
            observations.append("CRITICAL: Unnatural HDR latency detected. Scene exhibits zero physical optical clipping despite massive dynamic range.")
            supports = SignalSupport.AI_GENERATED
            reliability = 0.65
            summary = "The lighting looks unusually even for a normal camera-captured scene."
            what_found = "Bright and dark areas stay too clean and controlled, without the clipping or exposure strain we often expect from real photography."
            why_it_matters = "That can happen in AI-generated images, which often produce lighting that feels a little too perfect."
        elif clipped_highlights > 0.02 or crushed_blacks > 0.05:
            observations.append("Severe exposure boundaries detected (blown highlights or crushed shadows). This strongly aligns with raw physical camera sensors.")
            supports = SignalSupport.AUTHENTIC
            reliability = 0.55
            summary = "The exposure behaves more like a real camera image than a perfectly generated one."
            what_found = "We can see more natural clipping in the brightest or darkest areas, which is common in real photography."
            why_it_matters = "Real cameras often struggle a bit with harsh lighting, so this leans slightly toward authenticity."
        else:
            observations.append("Lighting topology is well balanced but lacks distinct physical or generative boundaries. Profile is inconclusive.")
            supports = SignalSupport.INCONCLUSIVE
            reliability = 0.3
            summary = "The lighting looks plausible, but it is not distinctive enough to settle the result."
            what_found = "The scene is balanced enough that lighting alone does not give us a strong clue."
            why_it_matters = "This leaves lighting as a supporting signal rather than a decisive one."

        return EvidenceSignal(
            id=self.id,
            name=self.name,
            category=self.category,
            status=SignalStatus.OK,
            reliability=reliability,
            summary=summary,
            what_checked="We checked whether the scene's brightness and contrast behave like normal camera exposure.",
            what_found=what_found,
            why_it_matters=why_it_matters,
            caveat="Lighting is one of the weakest signals by itself, because editing, flash, shade, and strong post-processing can all change it.",
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
