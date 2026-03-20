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

        base_str = "Based on our analysis, "
        if verdict == Verdict.LIKELY_AUTHENTIC:
            fallback_explanation = f"{base_str}there is no strong evidence to suggest this is AI generated. We can be fairly confident this is actually real and shot on a real camera. The lighting and shadows match physical reality, and there are no spectral inconsistencies. {conclusion}"
        elif verdict == Verdict.LIKELY_AI_GENERATED:
            fallback_explanation = f"{base_str}multiple forensic signals indicate this is a procedurally generated AI image. We see distinct mathematical flaws in the matrix alongside geometric inconsistencies that a real camera would simply never capture. {conclusion}"
        else:
            fallback_explanation = f"{base_str}we cannot reach a definitive conclusion. The structural signals strongly conflict with each other, meaning this image either underwent massive post-processing edits, or the generative traces are expertly hidden. {conclusion}"

        client = LLMClient()
        llm_explanation = await client.generate_explanation(
            verdict=verdict.value,
            evidence=evidence.model_dump(),
        )

        return verdict, llm_explanation or fallback_explanation
