from __future__ import annotations

import base64
from io import BytesIO
from typing import Any, Dict

import numpy as np
from PIL import Image, ImageChops

from ..models.evidence import EvidenceSignal, SignalStatus, SignalSupport
from .base import Detector


class ErrorLevelAnalysisDetector(Detector):
    id = "error_level_analysis"
    name = "Error Level Analysis (ELA)"
    category = "forensic"

    async def analyze(self, image, context: Dict[str, Any]) -> EvidenceSignal:
        original = image.convert("RGB")
        buffer = BytesIO()
        jpeg_quality = 90
        original.save(buffer, format="JPEG", quality=jpeg_quality)
        buffer.seek(0)
        recompressed = Image.open(buffer)

        diff = ImageChops.difference(original, recompressed)
        diff_np = np.asarray(diff, dtype=np.float32)
        max_diff = float(diff_np.max())
        mean_diff = float(diff_np.mean())

        scale = 1.0
        if max_diff > 0:
            scale = 255.0 / max_diff
        scaled = np.clip(diff_np * scale, 0, 255).astype(np.uint8)
        ela_image = Image.fromarray(scaled)

        ela_buffer = BytesIO()
        ela_image.save(ela_buffer, format="PNG")
        ela_base64 = base64.b64encode(ela_buffer.getvalue()).decode("utf-8")

        observations = [
            f"Mean ELA intensity: {mean_diff:.2f}",
            f"Max ELA intensity: {max_diff:.2f}",
            f"JPEG recompress quality: {jpeg_quality}",
        ]

        return EvidenceSignal(
            id=self.id,
            name=self.name,
            category=self.category,
            status=SignalStatus.OK,
            reliability=0.25,
            summary="This check looked for uneven compression that can suggest editing or recompositing.",
            what_checked="We re-saved the image and measured where compression changes are stronger or weaker across the frame.",
            what_found="The heatmap shows where compression differences stand out, which can sometimes reveal edited regions or uneven image history.",
            why_it_matters="This is more useful for spotting manipulation or pasted-in regions than for proving pure AI generation by itself.",
            caveat="ELA is a weak signal on modern images because social media compression, resaving, and editing can all affect it.",
            observations=observations,
            metrics={
                "ela_mean": mean_diff,
                "ela_max": max_diff,
                "ela_scale": scale,
                "ela_quality": jpeg_quality,
                "ela_image_base64": ela_base64,
            },
            supports=SignalSupport.UNKNOWN,
            notes="ELA highlights compression inconsistencies; interpret alongside other signals.",
        )
