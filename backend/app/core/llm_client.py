from __future__ import annotations

import base64
import json
import re
from typing import Any, Dict, Optional, Tuple

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

    def _extract_json_object(self, text: str) -> Optional[Dict[str, Any]]:
        if not text:
            return None
        t = text.strip()
        t = t.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            obj = json.loads(t)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
        m = re.search(r"\{[\s\S]*\}", t)
        if m:
            try:
                obj = json.loads(m.group(0))
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                return None
        return None

    async def grounded_osint_investigation(
        self,
        image_bytes: bytes,
        user_context: str,
    ) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
        if not llm_settings.gemini_api_key:
            return None

        ctx = (user_context or "").strip()
        extra = (
            f"\n\nUser-provided context (treat as investigative hints, not proof): {ctx}"
            if ctx
            else ""
        )
        prompt = (
            "You are a lead forensic journalist with access to Google Search. "
            "Examine the image. Use search to determine whether this image aligns with verified real-world reporting "
            "or is widely described as fabricated, AI-generated, or a known deepfake."
            + extra
            + "\n\nAfter searching, respond with ONLY a single JSON object (no markdown fences) using exactly these keys:\n"
            "- known_deepfake (boolean): true only if credible reporting or fact-checkers say this depiction is fake, AI, or misleading.\n"
            "- verified_real (boolean): true only if credible outlets corroborate the depicted situation as real.\n"
            "- context (string): 3-5 sentences summarizing what you found and naming sources at a high level.\n"
            "If the scene is generic with no identifiable public story, set both booleans false and explain in context."
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
            "tools": [{"google_search": {}}],
            "generationConfig": {"temperature": 0.2},
        }
        headers = {"Content-Type": "application/json"}
        params = {"key": llm_settings.gemini_api_key}

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await self._post_with_fallback(
                    client,
                    llm_settings.gemini_grounding_model,
                    headers,
                    params,
                    payload,
                )
                data = response.json()
            except Exception:
                return None

        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError):
            return None

        cand0 = data["candidates"][0]
        meta = cand0.get("groundingMetadata") or cand0.get("grounding_metadata") or {}
        parsed = self._extract_json_object(text)
        if not parsed:
            return None
        out = {
            "known_deepfake": bool(parsed.get("known_deepfake")),
            "verified_real": bool(parsed.get("verified_real")),
            "context": str(parsed.get("context") or "").strip(),
            "grounded_text": text.strip(),
        }
        meta_out = meta if isinstance(meta, dict) else {}
        return out, meta_out

    async def followup_answer(
        self,
        user_message: str,
        verdict: str,
        evidence: Dict[str, Any],
    ) -> Optional[str]:
        system = (
            "You are DeepTrace, a forensic assistant. The user already received a structured analysis. "
            "Answer follow-up questions only using the provided evidence JSON and verdict. "
            "If the question cannot be answered from that evidence, say so clearly. "
            "Be conversational, concise (2-6 sentences), and avoid inventing new forensic claims."
        )
        user = f"Verdict: {verdict}\n\nEvidence JSON:\n{json.dumps(evidence, indent=2)}\n\nUser question:\n{user_message}"

        async def groq_reply() -> Optional[str]:
            if not llm_settings.groq_api_key:
                return None
            url = "https://api.groq.com/openai/v1/chat/completions"
            hdrs = {"Authorization": f"Bearer {llm_settings.groq_api_key}"}
            payload = {
                "model": llm_settings.groq_model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.2,
                "max_tokens": min(llm_settings.explanation_max_tokens, 768),
            }
            async with httpx.AsyncClient(timeout=45.0) as client:
                try:
                    response = await client.post(url, headers=hdrs, json=payload)
                    response.raise_for_status()
                    data = response.json()
                    return data["choices"][0]["message"]["content"].strip()
                except Exception:
                    return None

        async def gemini_reply() -> Optional[str]:
            if not llm_settings.gemini_api_key:
                return None
            payload = {
                "contents": [{"parts": [{"text": system + "\n\n" + user}]}],
                "generationConfig": {"temperature": 0.2},
            }
            headers = {"Content-Type": "application/json"}
            params = {"key": llm_settings.gemini_api_key}
            async with httpx.AsyncClient(timeout=45.0) as client:
                try:
                    response = await self._post_with_fallback(client, llm_settings.gemini_model, headers, params, payload)
                    data = response.json()
                    return data["candidates"][0]["content"]["parts"][0]["text"].strip()
                except Exception:
                    return None

        if llm_settings.explanation_provider == "groq":
            out = await groq_reply()
            if out:
                return out
            return await gemini_reply()

        out = await gemini_reply()
        if out:
            return out
        return await groq_reply()

    async def generate_explanation(
        self,
        verdict: str,
        evidence: Dict[str, Any],
        reasoning_summary: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        if llm_settings.explanation_provider == "groq" and llm_settings.groq_api_key:
            return await self._groq_explanation(verdict, evidence, reasoning_summary)
        if llm_settings.explanation_provider == "gemini" and llm_settings.gemini_api_key:
            return await self._gemini_text_explanation(verdict, evidence, reasoning_summary)
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

    async def generate_osint_search_queries(
        self, image_bytes: bytes, user_context: str = ""
    ) -> Optional[list[str]]:
        if not llm_settings.gemini_api_key:
            return None

        uc = (user_context or "").strip()
        hint = (
            f"\n\nThe user added this context (use it to sharpen queries): {uc}\n"
            if uc
            else ""
        )
        prompt = (
            "You are an elite investigative journalist and digital forensics expert. Examine this image carefully. "
            + hint
            + "If it depicts a generic scene (unidentifiable people, random landscape, generic stock photo), reply strictly with: [\"GENERIC_SCENE\"]\n\n"
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
            "You are a senior digital forensic analyst writing the narrative section of a verification report for a non-expert reader. "
            "Read the evidence summary and Evidence Profile JSON, then explain why the stated verdict was reached in plain, calm language.\n\n"
            "RULES:\n"
            "1. Tone: Professional, conversational, easy to understand, and never dramatic or pretentious. It should sound like a smart person walking someone through the image.\n"
            "2. Honesty: Do not claim certainty beyond the provided certainty score. If the verdict is inconclusive, clearly state which way the evidence leans, if any.\n"
            "3. Integration: Mention the strongest signals on both sides when relevant. Use the signal's plain-English fields (`what_checked`, `what_found`, `why_it_matters`, `caveat`) whenever possible instead of repeating raw detector jargon.\n"
            "4. Structure: Write exactly three short paragraphs. Paragraph 1 should state the verdict, certainty, and overall lean in simple terms. Paragraph 2 should explain the clearest reasons behind the result using concrete observations from the signals. Paragraph 3 should explain competing explanations, caveats, or uncertainty.\n"
            "5. Style: Avoid vague filler like 'forensic analysis reveals' unless you immediately explain what was actually seen. Prefer wording like 'we noticed', 'we found', 'that matters because', and 'this could also happen if'.\n"
            "6. Truth: Never invent observations. Only reference signals, scores, and summaries present in the provided data."
        )

    async def _groq_explanation(
        self,
        verdict: str,
        evidence: Dict[str, Any],
        reasoning_summary: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {llm_settings.groq_api_key}"}
        summary_json = json.dumps(reasoning_summary or {}, indent=2)
        messages = [
            {
                "role": "system",
                "content": self._get_reasoner_system_prompt(),
            },
            {
                "role": "user",
                "content": (
                    f"Verdict Declared: {verdict}\n\n"
                    f"Reasoning Summary:\n{summary_json}\n\n"
                    f"Evidence JSON Profile:\n{json.dumps(evidence, indent=2)}"
                ),
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

    async def _gemini_text_explanation(
        self,
        verdict: str,
        evidence: Dict[str, Any],
        reasoning_summary: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        summary_json = json.dumps(reasoning_summary or {}, indent=2)
        prompt = (
            f"{self._get_reasoner_system_prompt()}\n\n"
            f"Verdict Declared: {verdict}\n\n"
            f"Reasoning Summary:\n{summary_json}\n\n"
            f"Evidence JSON Profile:\n{json.dumps(evidence, indent=2)}"
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
