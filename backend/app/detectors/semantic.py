from __future__ import annotations

import json
from typing import Any, Dict, List

from ..core.llm_client import LLMClient
from ..models.evidence import EvidenceSignal, SignalStatus, SignalSupport
from .base import Detector


class SemanticInconsistencyDetector(Detector):
    id = "semantic_inconsistencies"
    name = "Semantic & Physical Consistency"
    category = "semantic"

    async def analyze(self, image, context: Dict[str, Any]) -> EvidenceSignal:
        image_bytes: bytes = context.get("image_bytes", b"")
        if not image_bytes:
            return EvidenceSignal(
                id=self.id,
                name=self.name,
                category=self.category,
                status=SignalStatus.UNAVAILABLE,
                reliability=0.0,
                summary="No image bytes available for LLM analysis.",
                observations=["Image bytes missing in pipeline context."],
                supports=SignalSupport.UNKNOWN,
            )

        client = LLMClient()
        result = await client.analyze_image_semantics(image_bytes)
        if not result:
            return EvidenceSignal(
                id=self.id,
                name=self.name,
                category=self.category,
                status=SignalStatus.UNAVAILABLE,
                reliability=0.0,
                summary="Gemini Vision not configured or returned no data.",
                observations=["Set GEMINI_API_KEY to enable semantic analysis."],
                supports=SignalSupport.UNKNOWN,
            )

        raw_text = result.get("raw_text", "")
        observations: List[str] = []
        confidence = None

        try:
            parsed = json.loads(raw_text)
            anomalies = parsed.get("anomalies", [])
            confidence = parsed.get("confidence")
            summary = parsed.get("summary", "Semantic analysis completed.")
            observations = [str(item) for item in anomalies] if anomalies else ["No obvious semantic anomalies reported."]
        except Exception:
            summary = "Gemini responded, but output was not valid JSON."
            observations = [raw_text[:300]]
            
        supports = SignalSupport.UNKNOWN
        final_reliability = 0.4
        
        if confidence is not None:
            if confidence >= 0.5:
                supports = SignalSupport.AI_GENERATED
                if confidence > 0.9:
                    # An explicit reasoning like catching a watermark should override doubt
                    final_reliability = 0.9
            elif confidence <= 0.3:
                supports = SignalSupport.AUTHENTIC

        return EvidenceSignal(
            id=self.id,
            name=self.name,
            category=self.category,
            status=SignalStatus.OK,
            reliability=final_reliability,
            summary=summary,
            observations=observations,
            metrics={"confidence_raw": confidence},
            confidence=confidence,
            supports=supports,
            notes="LLM-based semantic reasoning. Treat as advisory evidence.",
        )
