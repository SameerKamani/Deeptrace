# DeepTrace

Explainable forensic verification for AI-generated images.

## Current Status

**✅ Fully Functional Implementation**
- 7 forensic detectors with parallel processing
- FastAPI backend with async pipeline
- React frontend with modern UI
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

## Implemented Detectors

The system currently runs 7 parallel forensic detectors:

1. **Spectral Analysis** - CNN-based frequency artifact detection
2. **Metadata Analysis** - EXIF data and provenance verification  
3. **Noise Pattern Analysis** - Thermal noise and sensor consistency
4. **Lighting Consistency** - Physical lighting and shadow analysis
5. **Semantic Analysis** - LLM-powered logical inconsistency detection
6. **Error Level Analysis** - JPEG compression artifact analysis
7. **OSINT Verification** - Web scraping for fact-checking

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

The system requires API keys for LLM reasoning:

- `GEMINI_API_KEY` - For semantic analysis and reasoning
- `GROQ_API_KEY` - Fallback reasoning engine

## Notes

- If `GEMINI_API_KEY` is not set, the semantic detector is marked unavailable.
- If `GROQ_API_KEY` is not set, the reasoning layer falls back to a local explanation.
- The spectral model loads from `SPECTRAL_MODEL_PATH` (default `deeptrace_fuse_best/`).
- ELA heatmaps are generated as part of the forensic signals and included in the response.
- All detectors run in parallel with performance tracking logged to `logs/xray/`.
- The system produces three possible verdicts: `LIKELY_AUTHENTIC`, `LIKELY_AI_GENERATED`, or `INCONCLUSIVE`.
## Recent Updates (2026-03-24)

- **Six‑Lens Spectral Model** – `SpectralFusionModel` now implements six parallel branches (ConvNeXt, FFT, SRM, Chroma (YCbCr), SPAI, Robustness) and a 1792‑dim fusion head. The model loads cleanly from `deeptrace_fuse_best/`.
- **Grayscale conversion** – Uses BT.601 luma weights (`0.299, 0.587, 0.114`) instead of uniform ones.
- **Environment** – `SPECTRAL_AI_INDEX` set to `0` to match the fine‑tuned model’s class ordering.
- **Semantic Detector** – LLM prompt now explicitly checks for AI watermarks; confidence‑driven `supports` mapping added.
- **Reliability weighting** – Semantic signal reliability boosts to `0.9` when confidence > 0.9 (e.g., watermark detection).
- **Verification script** – `test_full_model.py` validates weight loading and forward pass.
