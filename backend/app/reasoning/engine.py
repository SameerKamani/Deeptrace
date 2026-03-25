from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..core.llm_client import LLMClient
from ..models.evidence import EvidenceProfile, EvidenceSignal, SignalStatus, SignalSupport
from ..models.report import ScoreBreakdown, Verdict


SIGNAL_IMPORTANCE = {
    "spectral_artifacts": 0.95,
    "metadata_analysis": 0.8,
    "noise_pattern_analysis": 0.65,
    "lighting_consistency": 0.5,
    "semantic_inconsistencies": 0.8,
    "error_level_analysis": 0.35,
    "osint_verification": 0.75,
}

STATUS_FACTOR = {
    SignalStatus.OK: 1.0,
    SignalStatus.WARNING: 0.8,
    SignalStatus.UNAVAILABLE: 0.0,
    SignalStatus.ERROR: 0.0,
}


@dataclass
class ScoredSignal:
    signal: EvidenceSignal
    contribution: float
    bucket: str


@dataclass
class ReasoningOutcome:
    verdict: Verdict
    certainty: float
    confidence_label: str
    leaning: Optional[Verdict]
    short_summary: str
    score_breakdown: ScoreBreakdown
    explanation: str
    summary_payload: Dict[str, Any]
    signal_contributions: Dict[str, float] = field(default_factory=dict)


class ReasoningEngine:
    async def reason(self, evidence: EvidenceProfile) -> ReasoningOutcome:
        scored_signals = [self._score_signal(signal) for signal in evidence.signals]

        authentic_score = sum(item.contribution for item in scored_signals if item.bucket == "authentic")
        ai_score = sum(item.contribution for item in scored_signals if item.bucket == "ai_generated")
        inconclusive_score = sum(item.contribution for item in scored_signals if item.bucket == "inconclusive")
        total_considered = authentic_score + ai_score + inconclusive_score
        directional_total = authentic_score + ai_score
        dominant_score = max(authentic_score, ai_score)
        margin = dominant_score - min(authentic_score, ai_score)
        agreement = margin / directional_total if directional_total else 0.0
        uncertainty_ratio = inconclusive_score / total_considered if total_considered else 0.0

        leaning = None
        if directional_total >= 0.25 and margin >= 0.08:
            leaning = Verdict.LIKELY_AUTHENTIC if authentic_score >= ai_score else Verdict.LIKELY_AI_GENERATED

        if directional_total < 0.25 or dominant_score < 0.22:
            verdict = Verdict.INCONCLUSIVE
        elif agreement < 0.14:
            verdict = Verdict.INCONCLUSIVE
        elif authentic_score > ai_score:
            verdict = Verdict.LIKELY_AUTHENTIC
        else:
            verdict = Verdict.LIKELY_AI_GENERATED

        certainty = self._compute_certainty(
            dominant_score=dominant_score,
            total_considered=total_considered,
            agreement=agreement,
            uncertainty_ratio=uncertainty_ratio,
        )
        confidence_label = self._confidence_label(certainty)

        summary_payload = self._build_summary_payload(
            scored_signals=scored_signals,
            authentic_score=authentic_score,
            ai_score=ai_score,
            inconclusive_score=inconclusive_score,
            total_considered=total_considered,
            verdict=verdict,
            certainty=certainty,
            confidence_label=confidence_label,
            leaning=leaning,
        )

        fallback_explanation = self._build_fallback_explanation(summary_payload)

        client = LLMClient()
        llm_explanation = await client.generate_explanation(
            verdict=verdict.value,
            evidence=evidence.model_dump(),
            reasoning_summary=summary_payload,
        )

        return ReasoningOutcome(
            verdict=verdict,
            certainty=certainty,
            confidence_label=confidence_label,
            leaning=leaning,
            short_summary=str(summary_payload["short_summary"]),
            score_breakdown=ScoreBreakdown(
                authentic=round(authentic_score, 3),
                ai_generated=round(ai_score, 3),
                inconclusive=round(inconclusive_score, 3),
                total_considered=round(total_considered, 3),
            ),
            explanation=llm_explanation or fallback_explanation,
            summary_payload=summary_payload,
            signal_contributions={s.signal.id: round(s.contribution, 4) for s in scored_signals},
        )

    def _score_signal(self, signal: EvidenceSignal) -> ScoredSignal:
        importance = SIGNAL_IMPORTANCE.get(signal.id, 0.6)
        status_factor = STATUS_FACTOR.get(signal.status, 0.0)
        base_weight = signal.reliability * importance * status_factor

        if signal.supports == SignalSupport.AUTHENTIC:
            support_confidence = self._directional_confidence(signal)
            return ScoredSignal(signal=signal, contribution=base_weight * support_confidence, bucket="authentic")

        if signal.supports == SignalSupport.AI_GENERATED:
            support_confidence = self._directional_confidence(signal)
            return ScoredSignal(signal=signal, contribution=base_weight * support_confidence, bucket="ai_generated")

        if signal.supports == SignalSupport.INCONCLUSIVE:
            return ScoredSignal(signal=signal, contribution=base_weight * 0.8, bucket="inconclusive")

        if signal.reliability > 0 and status_factor > 0:
            return ScoredSignal(signal=signal, contribution=base_weight * 0.35, bucket="inconclusive")

        return ScoredSignal(signal=signal, contribution=0.0, bucket="neutral")

    def _directional_confidence(self, signal: EvidenceSignal) -> float:
        if signal.confidence is None:
            return 0.75

        raw_confidence = float(signal.confidence)
        if signal.supports == SignalSupport.AUTHENTIC:
            raw_confidence = 1.0 - raw_confidence

        raw_confidence = max(0.0, min(1.0, raw_confidence))
        return 0.45 + (raw_confidence * 0.55)

    def _compute_certainty(
        self,
        *,
        dominant_score: float,
        total_considered: float,
        agreement: float,
        uncertainty_ratio: float,
    ) -> float:
        if total_considered <= 0.0:
            return 0.0

        coverage = min(1.0, dominant_score)
        base = 0.18 + (0.55 * agreement) + (0.27 * coverage)
        certainty = base * (1.0 - (0.45 * uncertainty_ratio))
        return round(max(0.0, min(0.99, certainty)), 3)

    def _confidence_label(self, certainty: float) -> str:
        if certainty >= 0.78:
            return "high"
        if certainty >= 0.6:
            return "moderate"
        if certainty >= 0.45:
            return "guarded"
        return "low"

    def _build_summary_payload(
        self,
        *,
        scored_signals: List[ScoredSignal],
        authentic_score: float,
        ai_score: float,
        inconclusive_score: float,
        total_considered: float,
        verdict: Verdict,
        certainty: float,
        confidence_label: str,
        leaning: Optional[Verdict],
    ) -> Dict[str, Any]:
        top_authentic = self._serialize_signals(scored_signals, "authentic")
        top_ai = self._serialize_signals(scored_signals, "ai_generated")
        top_inconclusive = self._serialize_signals(scored_signals, "inconclusive")

        short_summary = self._build_short_summary(
            verdict=verdict,
            certainty=certainty,
            leaning=leaning,
            top_authentic=top_authentic,
            top_ai=top_ai,
            top_inconclusive=top_inconclusive,
        )

        return {
            "verdict": verdict.value,
            "certainty": certainty,
            "certainty_percent": int(round(certainty * 100)),
            "confidence_label": confidence_label,
            "leaning": leaning.value if leaning else None,
            "short_summary": short_summary,
            "scores": {
                "authentic": round(authentic_score, 3),
                "ai_generated": round(ai_score, 3),
                "inconclusive": round(inconclusive_score, 3),
                "total_considered": round(total_considered, 3),
            },
            "top_authentic_signals": top_authentic,
            "top_ai_signals": top_ai,
            "top_inconclusive_signals": top_inconclusive,
        }

    def _serialize_signals(self, scored_signals: List[ScoredSignal], bucket: str) -> List[Dict[str, Any]]:
        selected = [item for item in scored_signals if item.bucket == bucket and item.contribution > 0]
        selected.sort(key=lambda item: item.contribution, reverse=True)
        output = []
        for item in selected[:3]:
            output.append(
                {
                    "name": item.signal.name,
                    "summary": item.signal.summary,
                    "what_found": item.signal.what_found,
                    "why_it_matters": item.signal.why_it_matters,
                    "caveat": item.signal.caveat,
                    "support": item.signal.supports.value,
                    "contribution": round(item.contribution, 3),
                }
            )
        return output

    def _build_short_summary(
        self,
        *,
        verdict: Verdict,
        certainty: float,
        leaning: Optional[Verdict],
        top_authentic: List[Dict[str, Any]],
        top_ai: List[Dict[str, Any]],
        top_inconclusive: List[Dict[str, Any]],
    ) -> str:
        certainty_text = f"{int(round(certainty * 100))}% certainty"

        if verdict == Verdict.LIKELY_AUTHENTIC:
            lead = ", ".join(item["name"] for item in top_authentic[:2]) or "the strongest available signals"
            return f"The evidence currently leans toward a real photograph with {certainty_text}, led mainly by {lead}."

        if verdict == Verdict.LIKELY_AI_GENERATED:
            lead = ", ".join(item["name"] for item in top_ai[:2]) or "the strongest available signals"
            return f"The evidence currently leans toward AI generation with {certainty_text}, driven mainly by {lead}."

        if leaning == Verdict.LIKELY_AUTHENTIC:
            return (
                f"The evidence is mixed, but it leans slightly toward authenticity at {certainty_text}. "
                "Conflicting or limited signals keep this from being a confident call."
            )

        if leaning == Verdict.LIKELY_AI_GENERATED:
            return (
                f"The evidence is mixed, but it leans slightly toward AI generation at {certainty_text}. "
                "Conflicting or limited signals keep this from being a confident call."
            )

        lead = ", ".join(item["name"] for item in top_inconclusive[:2]) or "multiple weaker checks"
        return f"The evidence remains inconclusive at {certainty_text}, with uncertainty coming mainly from {lead}."

    def _build_fallback_explanation(self, summary: Dict[str, Any]) -> str:
        certainty_percent = summary["certainty_percent"]
        verdict = Verdict(summary["verdict"])
        leaning = summary.get("leaning")
        top_authentic = summary.get("top_authentic_signals", [])
        top_ai = summary.get("top_ai_signals", [])
        top_inconclusive = summary.get("top_inconclusive_signals", [])

        lead_authentic = self._signal_sentence(top_authentic)
        lead_ai = self._signal_sentence(top_ai)
        lead_uncertain = self._signal_sentence(top_inconclusive)

        if verdict == Verdict.LIKELY_AUTHENTIC:
            intro = (
                f"Right now, this looks more like a real photograph than an AI-generated one, with about {certainty_percent}% certainty. "
                "That score reflects how strongly the signals agree, not a guarantee."
            )
            evidence = (
                f"The main reasons are {lead_authentic}. "
                f"We still looked carefully at weaker or mixed signals such as {lead_uncertain}."
            )
            close = "So in plain English, the image holds together more like a camera photo than a generated one, even though no single signal proves that by itself."
            return "\n\n".join([intro, evidence, close])

        if verdict == Verdict.LIKELY_AI_GENERATED:
            intro = (
                f"Right now, this looks more likely AI-generated than camera-captured, with about {certainty_percent}% certainty. "
                "That score reflects how strongly the signals agree, not a guarantee."
            )
            evidence = (
                f"The biggest reasons are {lead_ai}. "
                f"There are still some counter-signals or weaker checks, such as {lead_authentic or lead_uncertain}, but they do not outweigh the main issues."
            )
            close = "So in plain English, more of the stronger signals look like generation artifacts or heavy synthetic processing than like a normal camera photo."
            return "\n\n".join([intro, evidence, close])

        if leaning == Verdict.LIKELY_AUTHENTIC.value:
            lean_text = "slightly toward a real photograph"
            lead_support = lead_authentic
            lead_counter = lead_ai or lead_uncertain
        elif leaning == Verdict.LIKELY_AI_GENERATED.value:
            lean_text = "slightly toward AI generation"
            lead_support = lead_ai
            lead_counter = lead_authentic or lead_uncertain
        else:
            lean_text = "in neither direction strongly enough"
            lead_support = lead_authentic or lead_ai
            lead_counter = lead_ai if lead_authentic else lead_authentic or lead_uncertain

        intro = (
            f"This result is inconclusive, and our current certainty is about {certainty_percent}%. "
            f"The evidence leans {lean_text}, but not strongly enough for a confident final call."
        )
        evidence = (
            f"The main support on one side comes from {lead_support}, while the strongest competing or limiting evidence comes from "
            f"{lead_counter}."
        )
        close = (
            f"Checks such as {lead_uncertain} add even more uncertainty, which is why the right answer here is to explain the balance of evidence instead of forcing a yes-or-no conclusion."
        )
        return "\n\n".join([intro, evidence, close])

    def _signal_sentence(self, items: List[Dict[str, Any]]) -> str:
        if not items:
            return "other weaker signals"

        if len(items) == 1:
            item = items[0]
            detail = item.get("what_found") or item.get("summary") or "it produced a meaningful signal"
            return f"{item['name']}, where we found that {detail.rstrip('.').lower()}."

        first = items[0]
        second = items[1]
        first_detail = first.get("what_found") or first.get("summary") or "it produced a meaningful signal"
        second_detail = second.get("what_found") or second.get("summary") or "it produced a meaningful signal"
        return (
            f"{first['name']}, where we found that {first_detail.rstrip('.').lower()}, "
            f"and {second['name']}, where we found that {second_detail.rstrip('.').lower()}."
        )
