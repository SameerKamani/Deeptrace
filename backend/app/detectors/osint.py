from __future__ import annotations

import asyncio
from typing import Any, Dict

from duckduckgo_search import DDGS

from ..core.llm import llm_settings
from ..core.llm_client import LLMClient
from ..models.evidence import EvidenceSignal, SignalStatus, SignalSupport
from .base import Detector


class OpenSourceIntelligenceDetector(Detector):
    id = "osint_verification"
    name = "Live Web Fact-Checking (OSINT)"
    category = "forensic"

    async def analyze(self, image, context: Dict[str, Any]) -> EvidenceSignal:
        image_bytes: bytes = context.get("image_bytes", b"")
        user_context: str = str(context.get("user_context") or "")
        if not image_bytes:
            return EvidenceSignal(
                id=self.id,
                name=self.name,
                category=self.category,
                status=SignalStatus.UNAVAILABLE,
                reliability=0.0,
                summary="No image bytes available for OSINT.",
                observations=["Requires raw image bytes."],
                supports=SignalSupport.UNKNOWN,
            )

        client = LLMClient()

        if llm_settings.osint_use_grounding and llm_settings.gemini_api_key:
            grounded = await client.grounded_osint_investigation(image_bytes, user_context)
            if grounded:
                fact_check, meta = grounded
                is_deepfake = fact_check.get("known_deepfake", False)
                is_real = fact_check.get("verified_real", False)
                context_str = fact_check.get("context", "Context parsed but empty.")
                grounded_text = fact_check.get("grounded_text", "")
                queries_used = []
                if isinstance(meta, dict):
                    queries_used = meta.get("webSearchQueries") or meta.get("web_search_queries") or []

                observations = [
                    "OSINT mode: Google Search grounding (Gemini).",
                ]
                if queries_used:
                    observations.append(f"Search queries used: {len(queries_used)}")
                observations.append(f"Synthesis: {context_str}")
                if grounded_text and len(grounded_text) < 1200:
                    observations.append(f"Model notes: {grounded_text[:800]}...")

                if is_deepfake:
                    summary = "Live Internet fact-checking (grounded search) indicates a known or widely disputed fabrication."
                    supports = SignalSupport.AI_GENERATED
                    reliability = 0.98
                    observations.append(
                        "Critical: Grounded sources describe this depiction as fabricated, AI-generated, or misleading."
                    )
                elif is_real:
                    summary = "Grounded search results align with verified real-world reporting."
                    supports = SignalSupport.AUTHENTIC
                    reliability = 0.85
                    observations.append(
                        "Verified: Extracted context matches credible reporting on the depicted situation."
                    )
                else:
                    summary = "Grounded search did not yield a clear fact-check consensus for this exact depiction."
                    supports = SignalSupport.INCONCLUSIVE
                    reliability = 0.45
                    observations.append(
                        "Warning: Subject matter may appear in news, but authenticity of this specific image is not clearly settled in sources."
                    )

                metrics: Dict[str, Any] = {
                    "deepfake_flag": is_deepfake,
                    "verified_flag": is_real,
                    "grounding": True,
                }
                if isinstance(meta, dict) and meta:
                    metrics["grounding_metadata"] = meta

                return EvidenceSignal(
                    id=self.id,
                    name=self.name,
                    category=self.category,
                    status=SignalStatus.OK,
                    reliability=reliability,
                    summary=summary,
                    observations=observations,
                    metrics=metrics,
                    supports=supports,
                    notes="Grounded with Google Search via Gemini when available.",
                )

        queries = await client.generate_osint_search_queries(image_bytes, user_context)

        if not queries or "GENERIC_SCENE" in queries:
            return EvidenceSignal(
                id=self.id,
                name=self.name,
                category=self.category,
                status=SignalStatus.WARNING,
                reliability=0.1,
                summary="Image designated as a generic scene. No public context required.",
                observations=["Zero specific public figures or geopolitical events recognized by OSINT protocol."],
                supports=SignalSupport.UNKNOWN,
                notes="Skipped live internet search. Only possible for recognized public or viral images.",
            )

        try:
            def sync_search(search_queries):
                pooled_results = []
                seen_urls = set()
                with DDGS() as ddgs:
                    for q in search_queries:
                        results = list(ddgs.text(q, max_results=5))
                        for r in results:
                            url = r.get("href", "")
                            if url not in seen_urls:
                                seen_urls.add(url)
                                pooled_results.append(f"- QUERY [{q}] -> {r.get('title')}: {r.get('body')}")
                return pooled_results

            results_list = await asyncio.to_thread(sync_search, queries)
            if not results_list:
                raise ValueError("Massive investigative sweep returned zero global results.")

            search_str = "\n".join(results_list)

        except Exception as exc:
            return EvidenceSignal(
                id=self.id,
                name=self.name,
                category=self.category,
                status=SignalStatus.ERROR,
                reliability=0.0,
                summary="OSINT Web Aggregator Failed",
                observations=[f"Error accessing open web: {exc}"],
                supports=SignalSupport.UNKNOWN,
            )

        fact_check = await client.evaluate_osint_context(image_bytes, search_str)
        if not fact_check:
            return EvidenceSignal(
                id=self.id,
                name=self.name,
                category=self.category,
                status=SignalStatus.ERROR,
                reliability=0.0,
                summary="Failed to parse Fact-Checker JSON synthesis.",
                observations=["Queries executed perfectly but final LLM synthesis failed to return valid JSON."],
                supports=SignalSupport.UNKNOWN,
            )

        is_deepfake = fact_check.get("known_deepfake", False)
        is_real = fact_check.get("verified_real", False)
        context_str = fact_check.get("context", "Context parsed but empty.")

        observations = [
            "OSINT mode: DuckDuckGo + LLM synthesis (fallback).",
            f"Executed Investigatory Queries: {len(queries)} dynamic vectors",
            f"Unique Global Articles Analyzed: {len(results_list)}",
            f"Fact-Checker Synthesis: {context_str}",
        ]

        if is_deepfake:
            summary = "Live Internet Fact-Checking confirms a KNOWN DEEPFAKE."
            supports = SignalSupport.AI_GENERATED
            reliability = 0.98
            observations.append(
                "CRITICAL: The open internet explicitly flags this event or image as a fabricated deepfake."
            )
        elif is_real:
            summary = "Multiple independent news sources corroborate this physical event."
            supports = SignalSupport.AUTHENTIC
            reliability = 0.85
            observations.append(
                "Verified: Extracted context matches verified real-world reporting and eyewitness accounts."
            )
        else:
            summary = "Event exists in news cycle, but visual authenticity remains publicly debated."
            supports = SignalSupport.INCONCLUSIVE
            reliability = 0.4
            observations.append(
                "Warning: Open web confirms the subject matter, but no explicit fact-checking consensus on this specific image was found."
            )

        return EvidenceSignal(
            id=self.id,
            name=self.name,
            category=self.category,
            status=SignalStatus.OK,
            reliability=reliability,
            summary=summary,
            observations=observations,
            metrics={"deepfake_flag": is_deepfake, "verified_flag": is_real, "grounding": False},
            supports=supports,
            notes="Cross-references the subject against global live news indices (OSINT).",
        )
