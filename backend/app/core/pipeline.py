from __future__ import annotations

import asyncio
import hashlib
from io import BytesIO
from typing import Any, Dict, List

from PIL import Image

import time
import json
import os
from pathlib import Path

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
        global_start = time.perf_counter()
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

        xray_metrics = {}

        async def run_detector_tracked(detector):
            start_time = time.perf_counter()
            try:
                sig = await detector.analyze(image, context)
                duration = time.perf_counter() - start_time
                xray_metrics[detector.id] = {"status": sig.status.value, "time_seconds": round(duration, 4), "reliability": sig.reliability}
                return sig
            except Exception as e:
                duration = time.perf_counter() - start_time
                xray_metrics[detector.id] = {"status": "CRASHED", "time_seconds": round(duration, 4), "error": str(e)}
                # Still fail gracefully
                from ..models.evidence import EvidenceSignal, SignalStatus, SignalSupport
                return EvidenceSignal(
                    id=detector.id,
                    name=detector.name,
                    category=detector.category,
                    status=SignalStatus.ERROR,
                    reliability=0.0,
                    summary="FATAL DETECTOR CRASH",
                    observations=[f"Exception caught in pipeline: {str(e)}"],
                    supports=SignalSupport.UNKNOWN,
                )

        tasks = [run_detector_tracked(detector) for detector in detectors]
        signals = await asyncio.gather(*tasks)

        evidence = EvidenceProfile(image=image_info, signals=signals)
        
        reasoning_start = time.perf_counter()
        verdict, explanation = await self.reasoning.reason(evidence)
        reasoning_duration = time.perf_counter() - reasoning_start

        report = ForensicReport(
            verdict=verdict,
            explanation=explanation,
            evidence=evidence,
            generated_at=ForensicReport.now(),
        )
        
        # --- GENERATE X-RAY DIAGNOSTIC LOG ---
        global_duration = time.perf_counter() - global_start
        xray_log = {
            "timestamp": report.generated_at.isoformat(),
            "image_hash": image_info.sha256,
            "global_execution_time": round(global_duration, 4),
            "reasoning_execution_time": round(reasoning_duration, 4),
            "detector_metrics": xray_metrics,
            "final_verdict": verdict.value
        }
        
        # Write to logs directory
        log_dir = Path("logs/xray")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"xray_{image_info.sha256[:8]}_{int(time.time())}.json"
        
        try:
            with open(log_file, "w") as f:
                json.dump(xray_log, f, indent=4)
        except Exception:
            pass # Failsafe, don't break pipeline if OS write fails
            
        return report
