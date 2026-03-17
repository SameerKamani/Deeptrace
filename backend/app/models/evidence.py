from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SignalStatus(str, Enum):
    OK = "ok"
    WARNING = "warning"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


class SignalSupport(str, Enum):
    AUTHENTIC = "authentic"
    AI_GENERATED = "ai_generated"
    INCONCLUSIVE = "inconclusive"
    UNKNOWN = "unknown"


class EvidenceSignal(BaseModel):
    id: str = Field(..., description="Stable identifier for the signal.")
    name: str
    category: str
    status: SignalStatus
    reliability: float = Field(..., ge=0.0, le=1.0)
    summary: str
    observations: List[str] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    supports: SignalSupport = SignalSupport.UNKNOWN
    notes: Optional[str] = None


class ImageInfo(BaseModel):
    width: int
    height: int
    mode: str
    sha256: str
    format: Optional[str] = None


class EvidenceProfile(BaseModel):
    image: ImageInfo
    signals: List[EvidenceSignal]
    warnings: List[str] = Field(default_factory=list)
