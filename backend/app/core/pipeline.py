from __future__ import annotations

import asyncio
import hashlib
from io import BytesIO
from typing import Any, Dict, List

from PIL import Image

from ..detectors.registry import registry
from ..models.evidence import EvidenceProfile, ImageInfo
from ..models.report import ForensicReport, Verdict
from ..reasoning.engine import ReasoningEngine


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class AnalysisPipeline:
    def __init__(self) -> None:
        self.reasoning = ReasoningEngine()

    async def analyze(self, image_bytes: bytes) -> ForensicReport:
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        image_info = ImageInfo(
            width=image.width,
            height=image.height,
            mode=image.mode,
            sha256=_hash_bytes(image_bytes),
            format=image.format,
        )

        context: Dict[str, Any] = {
            "image_info": image_info,
            "image_bytes": image_bytes,
        }
        detectors = registry.all()

        async def run_detector(detector):
            return await detector.analyze(image, context)

        tasks = [run_detector(detector) for detector in detectors]
        signals = await asyncio.gather(*tasks)

        evidence = EvidenceProfile(image=image_info, signals=signals)
        verdict, explanation = await self.reasoning.reason(evidence)

        return ForensicReport(
            verdict=verdict,
            explanation=explanation,
            evidence=evidence,
            generated_at=ForensicReport.now(),
        )
