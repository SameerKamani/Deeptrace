from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel

from .evidence import EvidenceProfile


class Verdict(str, Enum):
    LIKELY_AUTHENTIC = "likely_authentic"
    LIKELY_AI_GENERATED = "likely_ai_generated"
    INCONCLUSIVE = "inconclusive"


class ForensicReport(BaseModel):
    verdict: Verdict
    explanation: str
    evidence: EvidenceProfile
    generated_at: datetime

    @staticmethod
    def now() -> datetime:
        return datetime.now(timezone.utc)
