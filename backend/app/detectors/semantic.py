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
                summary="This visual consistency check could not run because the image bytes were missing.",
                what_checked="We look for visible issues such as broken hands, warped geometry, impossible text, or inconsistent reflections.",
                what_found="The semantic detector did not receive the image data it needed.",
                why_it_matters="This check is useful because it can spot visible clues that humans can understand directly.",
                caveat="This is a detector availability issue, not evidence for or against the image.",
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
                summary="This visual consistency check was unavailable.",
                what_checked="We look for visible issues such as broken hands, warped geometry, impossible text, or inconsistent reflections.",
                what_found="The vision model did not return a usable result.",
                why_it_matters="This check often gives the clearest human-readable clues when an image looks generated.",
                caveat="This only means the detector was unavailable. It is not evidence about the image itself.",
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
            summary = "The visual review returned text, but not in the expected structure."
            observations = [raw_text[:300]]
            
        supports = SignalSupport.UNKNOWN
        final_reliability = 0.4
        what_found = "The visual review did not produce a clear directional result."
        why_it_matters = "This check tries to spot visible problems that often give AI-generated images away."
        caveat = "This detector is useful, but it can still be wrong and should be treated as one part of the full picture."
        
        if confidence is not None:
            if confidence >= 0.5:
                supports = SignalSupport.AI_GENERATED
                what_found = "The visual review found visible issues that look more like generation mistakes than normal photography."
                why_it_matters = "When an image shows broken anatomy, odd geometry, or impossible details, that is strong evidence against a normal camera photo."
                if confidence > 0.9:
                    # An explicit reasoning like catching a watermark should override doubt
                    final_reliability = 0.9
            elif confidence <= 0.3:
                supports = SignalSupport.AUTHENTIC
                what_found = "The visual review did not find obvious anatomy, geometry, or text problems that would strongly suggest AI generation."
                why_it_matters = "A scene that holds together visually is more consistent with a real photo, even though this does not prove it."
            else:
                supports = SignalSupport.INCONCLUSIVE
                what_found = "The visual review noticed some potentially suspicious details, but not strongly enough to be confident."
                why_it_matters = "That makes this a mixed signal rather than a strong point for either side."

        return EvidenceSignal(
            id=self.id,
            name=self.name,
            category=self.category,
            status=SignalStatus.OK,
            reliability=final_reliability,
            summary=summary,
            what_checked="We looked for visible clues such as anatomy errors, warped shapes, impossible text, or inconsistent lighting/reflections.",
            what_found=what_found,
            why_it_matters=why_it_matters,
            caveat=caveat,
            observations=observations,
            metrics={"confidence_raw": confidence},
            confidence=confidence,
            supports=supports,
            notes="LLM-based semantic reasoning. Treat as advisory evidence.",
        )
