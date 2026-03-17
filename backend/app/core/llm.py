from __future__ import annotations

import os
from typing import Optional


class LLMSettings:
    def __init__(self) -> None:
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
        self.gemini_vision_model = os.getenv("GEMINI_VISION_MODEL", self.gemini_model)
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.explanation_provider = os.getenv("LLM_EXPLANATION_PROVIDER", "groq")
        self.explanation_max_tokens = int(os.getenv("LLM_EXPLANATION_MAX_TOKENS", "450"))
        self.vision_timeout_seconds = float(os.getenv("LLM_VISION_TIMEOUT_SECONDS", "20"))

    def provider_ready(self) -> Optional[str]:
        if self.explanation_provider == "gemini":
            return "gemini" if self.gemini_api_key else None
        if self.explanation_provider == "groq":
            return "groq" if self.groq_api_key else None
        return None


llm_settings = LLMSettings()
