from __future__ import annotations

import os
from typing import Optional


class LLMSettings:
    def __init__(self) -> None:
        keys = []
        try:
            with open(".env", "r") as f:
                for line in f:
                    if line.startswith("GEMINI_API_KEY="):
                        keys.append(line.strip().split("=", 1)[1])
        except Exception:
            pass
            
        self.gemini_api_keys = keys if keys else [os.getenv("GEMINI_API_KEY")]
        self.gemini_api_key = self.gemini_api_keys[0] if self.gemini_api_keys else None
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.1-pro-preview")
        self.gemini_vision_model = os.getenv("GEMINI_VISION_MODEL", self.gemini_model)
        self.gemini_grounding_model = os.getenv("GEMINI_GROUNDING_MODEL", "gemini-2.5-flash")
        self.osint_use_grounding = os.getenv("OSINT_USE_GROUNDING", "1") == "1"
        
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.explanation_provider = os.getenv("LLM_EXPLANATION_PROVIDER", "groq")
        self.explanation_max_tokens = int(os.getenv("LLM_EXPLANATION_MAX_TOKENS", "900"))
        self.vision_timeout_seconds = float(os.getenv("LLM_VISION_TIMEOUT_SECONDS", "20"))

    def provider_ready(self) -> Optional[str]:
        if self.explanation_provider == "gemini":
            return "gemini" if self.gemini_api_key else None
        if self.explanation_provider == "groq":
            return "groq" if self.groq_api_key else None
        return None


llm_settings = LLMSettings()
