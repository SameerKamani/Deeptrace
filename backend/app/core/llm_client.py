from __future__ import annotations

import base64
import json
from typing import Any, Dict, Optional

import httpx

from .llm import llm_settings


class LLMClient:
    async def _post_with_fallback(self, client: httpx.AsyncClient, base_model: str, headers: dict, params: dict, payload: dict) -> httpx.Response:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{base_model}:generateContent"
        
        last_exception = None
        for key in llm_settings.gemini_api_keys:
            params["key"] = key
            try:
                response = await client.post(url, headers=headers, params=params, json=payload)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as e:
                # If Google throws a Quota error, instantly trigger rotation to the next key.
                if e.response.status_code == 429:
                    last_exception = e
                    continue
                    
                # If Google throws a Bad Request/Not Found (Model doesn't exist), fallback to base flash model.
                if e.response.status_code in (400, 404):
                    fallback_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent"
                    fallback_response = await client.post(fallback_url, headers=headers, params=params, json=payload)
                    fallback_response.raise_for_status()
                    return fallback_response
                raise
                
        if last_exception:
            raise last_exception
        raise ValueError("No Gemini keys configured or all exhausted.")
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
            "You are an elite digital forensic analyst examining this image for subtle signs of AI generation. "
            "Analyze the fundamental architecture of the image. Real photographs adhere strictly to physical rules "
            "(inverse-square lighting falloff, uniform thermal noise geometries, Euclidian background structures, "
            "and symmetrical pupil reflections). Generative AI models build images procedurally, frequently failing at these microscopic physical realities.\n\n"
            "Examine the image deeply for:\n"
            "1. Illumination Physics: Do shadows accurately match the primary and ambient light sources? Are specular highlights on eyes, glass, or glossy surfaces consistent?\n"
            "2. Anatomy & Geometry: Are intersecting lines in the background straight and parallel? Do background objects merge into each other non-sensically? Are fingers overlapping in impossible topological ways?\n"
            "3. Fine Texture Details: Is background text coherent or random gibberish strokes? Are repetitive patterns (fences, brick walls, knit fabric) structurally continuous?\n"
            "4. Artificial Smoothing: Are focal depths physically possible for a real optical camera lens, or artificially blurred? Is skin texture completely devoid of pores?\n"
            "5. AI Watermarks: Look at all 4 corners of the image immediately. Do you see the Google Gemini sparkle/stars watermark in the corner? Do you see a colored bar from OpenAI DALL-E, or text saying AI Generated? If a watermark exists, confidence MUST be 1.0.\n\n"
            "Respond ONLY with a valid JSON object using exactly these keys:\n"
            "- anomalies (array of strings specifically detailing each impossible physical/geometric irregularity found)\n"
            "- confidence (float from 0.0 to 1.0 indicating how strongly these semantic anomalies prove AI generation)\n"
            "- summary (a brief, highly professional forensic summary of your visual findings)\n"
            "If no issues are found, anomalies must be an empty array []. Do not include markdown formatting like ```json in your response."
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
            ],
            "generationConfig": {"temperature": 0.2}
        }

        headers = {"Content-Type": "application/json"}
        params = {"key": llm_settings.gemini_api_key}

        async with httpx.AsyncClient(timeout=llm_settings.vision_timeout_seconds) as client:
            try:
                response = await self._post_with_fallback(client, llm_settings.gemini_vision_model, headers, params, payload)
                data = response.json()
            except Exception:
                return None

        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            return {"raw_text": text}
        except (KeyError, IndexError, TypeError):
            return None

    async def generate_osint_search_queries(self, image_bytes: bytes) -> Optional[list[str]]:
        if not llm_settings.gemini_api_key:
            return None

        prompt = (
            "You are an elite investigative journalist and digital forensics expert. Examine this image carefully. "
            "If it depicts a generic scene (unidentifiable people, random landscape, generic stock photo), reply strictly with: [\"GENERIC_SCENE\"]\n\n"
            "If it depicts recognizable public figures, politicians, specific geopolitical events, viral moments, or highly specific contexts, "
            "write exactly 3 highly targeted Google search queries to investigate the authenticity of this event. Your angles should be:\n"
            "1. A direct chronological news search for the specific event depicted.\n"
            "2. A search specifically looking for 'debunk', 'fake', 'AI generated', or 'fact check' regarding the context.\n"
            "3. A broader entity/location context search to verify if such an event was physically possible or reported.\n\n"
            "Return ONLY a valid JSON array of strings. Do NOT use markdown. Example:\n"
            "[\"Donald Trump arrest New York exactly what happened\", \"Donald Trump arrested fake AI generated fact check\", \"NYPD statements Donald Trump arrest photos\"]"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}, {"inline_data": {"mime_type": "image/png", "data": base64.b64encode(image_bytes).decode("utf-8")}}]}]
        }
        async with httpx.AsyncClient(timeout=20) as client:
            try:
                response = await self._post_with_fallback(client, llm_settings.gemini_vision_model, {"Content-Type": "application/json"}, {"key": llm_settings.gemini_api_key}, payload)
                data = response.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                queries = json.loads(text)
                if isinstance(queries, list) and len(queries) > 0:
                    return queries
                return None
            except Exception:
                return None

    async def evaluate_osint_context(self, image_bytes: bytes, search_results: str) -> Optional[Dict[str, Any]]:
        if not llm_settings.gemini_api_key:
            return None
            
        prompt = (
            "You are a Lead Forensic Journalist. I am providing you with an image and a massive dump of live Web Search Results pulled from multiple investigative queries.\n\n"
            f"LIVE WEB RESULTS:\n{search_results}\n\n"
            "Compare the image strictly against this aggregate news intel. Does the open internet explicitly trace this to a verified real event covered by credible reporters? "
            "Or do the news results explicitly warn that this specific image/event is a known viral AI Deepfake/Fabrication?\n\n"
            "You must synthesize the articles carefully. Many fake images have articles written about them *saying* they are fake.\n\n"
            "Return ONLY valid JSON with keys:\n"
            "- known_deepfake (boolean: true if news consensus confirms it is fabricated)\n"
            "- verified_real (boolean: true if credible news confirms the event actually happened physically)\n"
            "- context (string: A dense, highly professional 3-4 sentence journalistic summary of the global consensus on this exact event. Cite specific fact-checkers if present in the results.)\n"
            "Do not use markdown formatting like ```json."
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}, {"inline_data": {"mime_type": "image/png", "data": base64.b64encode(image_bytes).decode("utf-8")}}]}]
        }
        async with httpx.AsyncClient(timeout=20) as client:
            try:
                response = await self._post_with_fallback(client, llm_settings.gemini_vision_model, {"Content-Type": "application/json"}, {"key": llm_settings.gemini_api_key}, payload)
                data = response.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                return json.loads(text)
            except Exception:
                return None

    def _get_reasoner_system_prompt(self) -> str:
        return (
            "You are an expert digital forensics assistant, but your goal is to explain things to the user in a very "
            "simple, friendly, and human-sounding way (like a smart chatbot or a helpful friend). "
            "Your assignment is to read the provided Evidence Profile JSON containing math signals and Write a cohesive, "
            "flowing paragraph explaining the final verdict.\n\n"
            "RULES:\n"
            "1. Tone: Conversational, clear, and very human. Do not sound like a robot. Speak like this: 'There is no evidence to suggest this is AI generated. We can be fairly confident this is actually real...'\n"
            "2. Integration: Weave the technical signals (Lighting, Semantic, Noise, ELA, Spectral, OSINT News) naturally into your paragraph. For example, 'It is suspicious how there is a missing shadow, but that can be explained by...' or 'Furthermore, live web search shows how there are eyewitness reports...'\n"
            "3. Format: Return a single, beautifully written 1-2 paragraph response. Do not use bullet points or harsh structural headers.\n"
            "4. Truth: Never invent evidence. Only discuss the flags/signals present in the JSON."
        )

    async def _groq_explanation(self, verdict: str, evidence: Dict[str, Any]) -> Optional[str]:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {llm_settings.groq_api_key}"}
        messages = [
            {
                "role": "system",
                "content": self._get_reasoner_system_prompt(),
            },
            {
                "role": "user",
                "content": f"Verdict Declared: {verdict}\n\nEvidence JSON Profile:\n{json.dumps(evidence, indent=2)}",
            },
        ]
        payload = {
            "model": llm_settings.groq_model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": llm_settings.explanation_max_tokens,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"].strip()
            except Exception:
                return None

    async def _gemini_text_explanation(self, verdict: str, evidence: Dict[str, Any]) -> Optional[str]:
        prompt = (
            f"{self._get_reasoner_system_prompt()}\n\n"
            f"Verdict Declared: {verdict}\n\nEvidence JSON Profile:\n{json.dumps(evidence, indent=2)}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3}
        }
        headers = {"Content-Type": "application/json"}
        params = {"key": llm_settings.gemini_api_key}

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                response = await self._post_with_fallback(client, llm_settings.gemini_model, headers, params, payload)
                data = response.json()
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()
            except Exception:
                return None
