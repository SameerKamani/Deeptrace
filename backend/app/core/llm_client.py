from __future__ import annotations

import base64
from typing import Any, Dict, Optional

import httpx

from .llm import llm_settings


class LLMClient:
    async def generate_explanation(
        self, verdict: str, evidence: Dict[str, Any]
    ) -> Optional[str]:
        if llm_settings.explanation_provider == "groq" and llm_settings.groq_api_key:
            return await self._groq_explanation(verdict, evidence)
        if llm_settings.explanation_provider == "gemini" and llm_settings.gemini_api_key:
            return await self._gemini_text_explanation(verdict, evidence)
        return None

    async def analyze_image_semantics(self, image_bytes: bytes) -> Optional[Dict[str, Any]]:
        if not llm_settings.gemini_api_key:
            return None

        prompt = (
            "You are a digital forensic analyst. Examine the image for subtle signs of AI generation. "
            "Focus on lighting consistency, shadows, reflections, geometry, text rendering, and semantic "
            "anomalies. Return a JSON object with keys: anomalies (array of strings), "
            "confidence (0-1), and summary (string). If no issues found, anomalies should be empty."
        )

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "image/png",
                                "data": base64.b64encode(image_bytes).decode("utf-8"),
                            }
                        },
                    ]
                }
            ]
        }

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{llm_settings.gemini_vision_model}:generateContent"
        )
        headers = {"Content-Type": "application/json"}
        params = {"key": llm_settings.gemini_api_key}

        async with httpx.AsyncClient(timeout=llm_settings.vision_timeout_seconds) as client:
            response = await client.post(url, headers=headers, params=params, json=payload)
            response.raise_for_status()
            data = response.json()

        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return {"raw_text": text}
        except (KeyError, IndexError, TypeError):
            return None

    async def _groq_explanation(self, verdict: str, evidence: Dict[str, Any]) -> Optional[str]:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {llm_settings.groq_api_key}"}
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a forensic analyst. Provide a concise, detective-like explanation that references "
                    "specific evidence signals, highlights uncertainty, and avoids overclaiming."
                ),
            },
            {
                "role": "user",
                "content": f"Verdict: {verdict}\nEvidence JSON:\n{evidence}",
            },
        ]
        payload = {
            "model": llm_settings.groq_model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": llm_settings.explanation_max_tokens,
        }

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError):
            return None

    async def _gemini_text_explanation(self, verdict: str, evidence: Dict[str, Any]) -> Optional[str]:
        prompt = (
            "Write a concise forensic explanation referencing the evidence, highlight uncertainty, "
            "and avoid overclaiming.\n"
            f"Verdict: {verdict}\nEvidence JSON:\n{evidence}"
        )
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{llm_settings.gemini_model}:generateContent"
        )
        headers = {"Content-Type": "application/json"}
        params = {"key": llm_settings.gemini_api_key}

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(url, headers=headers, params=params, json=payload)
            response.raise_for_status()
            data = response.json()

        try:
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError, TypeError):
            return None
