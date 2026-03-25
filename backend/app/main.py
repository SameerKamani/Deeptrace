from __future__ import annotations

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .chat.store import store as session_store
from .core.config import settings
from .core.llm import llm_settings
from .core.llm_client import LLMClient
from .core.pipeline import AnalysisPipeline
from .detectors.lighting import LightingConsistencyDetector
from .detectors.metadata import MetadataDetector
from .detectors.noise import NoisePatternDetector
from .detectors.registry import registry
from .detectors.semantic import SemanticInconsistencyDetector
from .detectors.ela import ErrorLevelAnalysisDetector
from .detectors.spectral import SpectralArtifactDetector
from .detectors.osint import OpenSourceIntelligenceDetector

app = FastAPI(title=settings.project_name)
pipeline = AnalysisPipeline()


class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _register_detectors() -> None:
    registry.register(SpectralArtifactDetector())
    registry.register(MetadataDetector())
    registry.register(NoisePatternDetector())
    registry.register(LightingConsistencyDetector())
    registry.register(SemanticInconsistencyDetector())
    registry.register(ErrorLevelAnalysisDetector())
    registry.register(OpenSourceIntelligenceDetector())


_register_detectors()


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "llm_provider_ready": llm_settings.provider_ready(),
    }


def _too_large(contents: bytes) -> bool:
    return len(contents) > settings.max_upload_mb * 1024 * 1024


@app.post("/sessions")
async def create_session() -> dict:
    sid = session_store.create()
    return {"session_id": sid}


@app.post("/sessions/{session_id}/analyze")
async def analyze_in_session(
    session_id: str,
    file: UploadFile = File(...),
    context: str = Form(""),
):
    if not session_store.get(session_id):
        return JSONResponse(status_code=404, content={"error": "Unknown session."})
    contents = await file.read()
    if _too_large(contents):
        return JSONResponse(status_code=413, content={"error": "File too large."})

    report = await pipeline.analyze(contents, user_context=context)
    session_store.set_report(session_id, report)
    session_store.append_message(
        session_id,
        "user",
        f"[Analysis request]{(' ' + context) if context.strip() else ''}",
        {"kind": "analyze"},
    )
    session_store.append_message(
        session_id,
        "assistant",
        report.explanation,
        {"kind": "report", "verdict": report.verdict.value, "report": report.model_dump()},
    )
    return report.model_dump()


@app.post("/sessions/{session_id}/messages")
async def session_followup(session_id: str, body: ChatMessageRequest):
    data = session_store.get(session_id)
    if not data:
        return JSONResponse(status_code=404, content={"error": "Unknown session."})
    if not data.last_report:
        return JSONResponse(
            status_code=400,
            content={"error": "Run an analysis first so there is evidence to discuss."},
        )

    session_store.append_message(session_id, "user", body.message, {"kind": "text"})

    client = LLMClient()
    reply = await client.followup_answer(
        body.message,
        data.last_report.verdict.value,
        data.last_report.evidence.model_dump(),
    )
    if not reply:
        reply = "I could not generate a follow-up answer. Check LLM API keys and try again."

    session_store.append_message(session_id, "assistant", reply, {"kind": "text"})
    return {"reply": reply, "session_id": session_id}


@app.post("/analyze")
async def analyze_image(
    file: UploadFile = File(...),
    context: str = Form(""),
):
    contents = await file.read()
    if _too_large(contents):
        return JSONResponse(
            status_code=413,
            content={"error": "File too large."},
        )

    report = await pipeline.analyze(contents, user_context=context)
    return report.model_dump()
