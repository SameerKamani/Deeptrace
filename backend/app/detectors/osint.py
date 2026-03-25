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
                summary="This web verification check could not run because the raw image bytes were missing.",
                what_checked="We try to find whether the image or the event it claims to show appears in trustworthy public reporting.",
                what_found="The OSINT detector did not receive the image data it needed.",
                why_it_matters="Context can help confirm whether an image matches a real public event or a known fake.",
                caveat="This is a detector issue, not evidence about the image.",
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
                queries_used = []
                if isinstance(meta, dict):
                    queries_used = meta.get("webSearchQueries") or meta.get("web_search_queries") or []

                observations = [
                    "OSINT mode: Google Search grounding (Gemini).",
                ]
                if queries_used:
                    observations.append(f"Search queries used: {len(queries_used)}")

                if is_deepfake:
                    summary = "Live Internet fact-checking (grounded search) indicates a known or widely disputed fabrication."
                    supports = SignalSupport.AI_GENERATED
                    reliability = 0.98
                    what_found = "Search results and grounded context point to this image or claim being described as fake, misleading, or AI-generated."
                    why_it_matters = "When trusted reporting or fact-checking already describes the depiction as fake, that is very strong context evidence."
                    observations.append(
                        "Critical: Grounded sources describe this depiction as fabricated, AI-generated, or misleading."
                    )
                elif is_real:
                    summary = "Grounded search results align with verified real-world reporting."
                    supports = SignalSupport.AUTHENTIC
                    reliability = 0.85
                    what_found = "The search results line up with credible reporting about the depicted event or situation."
                    why_it_matters = "That does not prove the pixels are untouched, but it strongly supports the claim that the scene is real-world and reported."
                    observations.append(
                        "Verified: Extracted context matches credible reporting on the depicted situation."
                    )
                else:
                    summary = "Grounded search did not yield a clear fact-check consensus for this exact depiction."
                    supports = SignalSupport.INCONCLUSIVE
                    reliability = 0.45
                    what_found = "The web search found related context, but not a clear public answer about this exact image."
                    why_it_matters = "That leaves context unresolved rather than clearly verified or clearly debunked."
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
                    what_checked="We searched the web to see whether this image or event is publicly verified, disputed, or debunked.",
                    what_found=what_found,
                    why_it_matters=why_it_matters,
                    caveat="OSINT is best for public claims and known events. It is much less useful for generic scenes with no clear context.",
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
                summary="The image looks too generic for meaningful web verification.",
                what_checked="We tried to determine whether the scene points to a known public event, person, or widely discussed claim.",
                what_found="The scene does not appear specific enough for a useful web fact-check.",
                why_it_matters="OSINT only helps when there is a public event or claim to verify. Generic scenes usually cannot be confirmed this way.",
                caveat="A skipped OSINT check does not say anything negative about the image. It only means there was no clear public context to search.",
                observations=["Zero specific public figures or geopolitical events recognized by OSINT protocol."],
                supports=SignalSupport.UNKNOWN,
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
                summary="This web verification check failed while gathering search results.",
                what_checked="We tried to search the public web for corroboration or debunking of the scene.",
                what_found="The OSINT pipeline could not complete the search step.",
                why_it_matters="This removes one contextual check from the final result.",
                caveat="This is a search failure, not evidence about the image.",
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
                summary="The web search ran, but the fact-check summary could not be parsed cleanly.",
                what_checked="We searched the web for reporting, fact-checks, and public context tied to the image.",
                what_found="The search completed, but the final synthesis was not usable.",
                why_it_matters="This removes one contextual signal from the final result.",
                caveat="This is a synthesis failure, not evidence about the image.",
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
            what_found = "Public reporting or fact-checking describes this image or claim as fabricated."
            why_it_matters = "That is strong contextual evidence against authenticity."
            observations.append(
                "CRITICAL: The open internet explicitly flags this event or image as a fabricated deepfake."
            )
        elif is_real:
            summary = "Multiple independent news sources corroborate this physical event."
            supports = SignalSupport.AUTHENTIC
            reliability = 0.85
            what_found = "Public reporting supports the event or situation shown in the image."
            why_it_matters = "That is strong context evidence that the depicted claim is real, even if it does not prove the image is untouched."
            observations.append(
                "Verified: Extracted context matches verified real-world reporting and eyewitness accounts."
            )
        else:
            summary = "Event exists in news cycle, but visual authenticity remains publicly debated."
            supports = SignalSupport.INCONCLUSIVE
            reliability = 0.4
            what_found = "The broader subject exists publicly, but the web did not settle whether this exact image is authentic."
            why_it_matters = "That makes context useful but not decisive."
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
            what_checked="We searched the web to see whether this image or claim has been verified, disputed, or debunked publicly.",
            what_found=what_found,
            why_it_matters=why_it_matters,
            caveat="OSINT is about public context, not just pixel analysis. It is strongest for famous events and weakest for generic scenes.",
            observations=observations,
            metrics={"deepfake_flag": is_deepfake, "verified_flag": is_real, "grounding": False},
            supports=supports,
        )
