# DeepTrace

Explainable forensic verification for AI-generated images.

## Current Status

**✅ Fully Functional Implementation**
- 7 forensic detectors with parallel processing
- FastAPI backend with async pipeline
- React chat UI (analyze + optional context, follow-up questions)
- In-memory sessions for chat and last report
- OSINT: Gemini Google Search grounding when enabled, DuckDuckGo fallback
- LLM-powered reasoning (Gemini/Groq)
- Evidence-based explanations
- X-ray performance logging

## Quick start

### Backend Setup

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r backend\requirements.txt
```

Copy environment values and add API keys as needed:

```powershell
Copy-Item .env.example .env
```

Run the backend:

```powershell


.\.venv\Scripts\uvicorn backend.app.main:app --reload


```

### Frontend Setup

```powershell
cd frontend
npm install
npm run dev
```

Set the API URL if needed:

```
VITE_API_BASE=http://localhost:8000
```

## API (testing)

- `POST /sessions` — create a session id (in-memory).
- `POST /sessions/{session_id}/analyze` — multipart form: `file` (image), optional `context` (user text for OSINT and pipeline).
- `POST /sessions/{session_id}/messages` — JSON `{ "message": "..." }` follow-up about the last report (requires a prior analyze in that session).
- `POST /analyze` — multipart: `file`, optional `context` (same pipeline as above, no session).

## Implemented Detectors

The system currently runs 7 parallel forensic detectors:

1. **Spectral Analysis** - CNN-based frequency artifact detection
2. **Metadata Analysis** - EXIF data and provenance verification  
3. **Noise Pattern Analysis** - Thermal noise and sensor consistency
4. **Lighting Consistency** - Physical lighting and shadow analysis
5. **Semantic Analysis** - LLM-powered logical inconsistency detection
6. **Error Level Analysis** - JPEG compression artifact analysis
7. **OSINT Verification** - Grounded Google Search (Gemini tool) when enabled, else DuckDuckGo + LLM synthesis

## Spectral model setup

The spectral model is expected as a directory (default: `deeptrace_fuse_best/`) containing the PyTorch
state dictionary files. Install PyTorch CPU with:

```powershell
.\.venv\Scripts\pip install torch --index-url https://download.pytorch.org/whl/cpu
```

Update `.env` if your model path differs:

```
SPECTRAL_MODEL_PATH=deeptrace_fuse_best
```

## API Configuration

- `GEMINI_API_KEY` — **Vision + structured tasks**: semantic detector (image JSON), OSINT query generation, OSINT synthesis when not using grounding, and **grounded OSINT** (`google_search` tool on `GEMINI_GROUNDING_MODEL`).
- `GEMINI_GROUNDING_MODEL` — Model for OSINT with Google Search (default `gemini-2.5-flash`).
- `OSINT_USE_GROUNDING` — Set to `0` to use DuckDuckGo + Gemini synthesis instead of grounded search.
- `GROQ_API_KEY` — **Final report narrative** (Investigator’s Summary): default provider is Groq (`LLM_EXPLANATION_PROVIDER=groq`) for longer, clearer prose. Chat follow-ups use Groq first when this is set to `groq`.
- `LLM_EXPLANATION_PROVIDER` — `groq` (default) or `gemini` for the main written explanation only.
- `LLM_EXPLANATION_MAX_TOKENS` — Cap for that narrative (default `900`).

## Notes

- If `GEMINI_API_KEY` is not set, the semantic detector and Gemini-dependent OSINT paths are degraded or unavailable.
- If `GROQ_API_KEY` is not set while `LLM_EXPLANATION_PROVIDER=groq`, the main narrative falls back to the built-in template (or set provider to `gemini` if you only have Gemini).
- The spectral model loads from `SPECTRAL_MODEL_PATH` (default `deeptrace_fuse_best/`).
- ELA heatmaps are generated as part of the forensic signals and included in the response.
- All detectors run in parallel with performance tracking logged to `logs/xray/`.
- The system produces three possible verdicts: `LIKELY_AUTHENTIC`, `LIKELY_AI_GENERATED`, or `INCONCLUSIVE`.
## Recent Updates (2026-03-24)

- **Chat UI + sessions** — Frontend uses `POST /sessions` and session-scoped analyze; optional context field; follow-up messages against the last report.
- **Pipeline context** — Optional `user_context` is passed to detectors (OSINT uses it for grounding and DDG queries).
- **OSINT grounding** — Primary path uses Gemini `google_search` tool + JSON synthesis; falls back to DuckDuckGo if grounding fails or `OSINT_USE_GROUNDING=0`.
- **Six‑Lens Spectral Model** – `SpectralFusionModel` now implements six parallel branches (ConvNeXt, FFT, SRM, Chroma (YCbCr), SPAI, Robustness) and a 1792‑dim fusion head. The model loads cleanly from `deeptrace_fuse_best/`.
- **Grayscale conversion** – Uses BT.601 luma weights (`0.299, 0.587, 0.114`) instead of uniform ones.
- **Environment** – `SPECTRAL_AI_INDEX` set to `0` to match the fine‑tuned model’s class ordering.
- **Semantic Detector** – LLM prompt now explicitly checks for AI watermarks; confidence‑driven `supports` mapping added.
- **Reliability weighting** – Semantic signal reliability boosts to `0.9` when confidence > 0.9 (e.g., watermark detection).
- **Verification script** – `test_full_model.py` validates weight loading and forward pass.
