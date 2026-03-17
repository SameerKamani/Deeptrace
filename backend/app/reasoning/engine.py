from __future__ import annotations

from typing import Tuple

from ..models.evidence import EvidenceProfile, SignalSupport
from ..models.report import Verdict
from ..core.llm_client import LLMClient


class ReasoningEngine:
    async def reason(self, evidence: EvidenceProfile) -> Tuple[Verdict, str]:
        support_scores = {
            SignalSupport.AUTHENTIC: 0.0,
            SignalSupport.AI_GENERATED: 0.0,
        }
        summary_lines = []

        for signal in evidence.signals:
            summary_lines.append(f"{signal.name}: {signal.summary}")
            if signal.supports in support_scores:
                support_scores[signal.supports] += signal.reliability

        authentic_score = support_scores[SignalSupport.AUTHENTIC]
        ai_score = support_scores[SignalSupport.AI_GENERATED]

        if authentic_score == 0.0 and ai_score == 0.0:
            verdict = Verdict.INCONCLUSIVE
            conclusion = "Signals do not provide directional evidence yet."
        elif authentic_score > 0.0 and ai_score > 0.0:
            if abs(authentic_score - ai_score) < 0.25:
                verdict = Verdict.INCONCLUSIVE
                conclusion = "Signals conflict or are too balanced to reach a confident verdict."
            elif authentic_score > ai_score:
                verdict = Verdict.LIKELY_AUTHENTIC
                conclusion = "More reliable evidence leans toward authenticity."
            else:
                verdict = Verdict.LIKELY_AI_GENERATED
                conclusion = "More reliable evidence leans toward AI generation."
        elif authentic_score > 0.4:
            verdict = Verdict.LIKELY_AUTHENTIC
            conclusion = "Available evidence leans toward authenticity."
        elif ai_score > 0.4:
            verdict = Verdict.LIKELY_AI_GENERATED
            conclusion = "Available evidence leans toward AI generation."
        else:
            verdict = Verdict.INCONCLUSIVE
            conclusion = "Evidence is present but not strong enough to support a verdict."

        fallback_explanation = " ".join(summary_lines + [conclusion])

        client = LLMClient()
        llm_explanation = await client.generate_explanation(
            verdict=verdict.value,
            evidence=evidence.model_dump(),
        )

        return verdict, llm_explanation or fallback_explanation
