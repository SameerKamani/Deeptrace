from __future__ import annotations

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .core.config import settings
from .core.llm import llm_settings
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


@app.post("/analyze")
async def analyze_image(file: UploadFile = File(...)):
    contents = await file.read()
    if len(contents) > settings.max_upload_mb * 1024 * 1024:
        return JSONResponse(
            status_code=413,
            content={"error": "File too large."},
        )

    report = await pipeline.analyze(contents)
    return report.model_dump()
