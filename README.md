# DeepTrace

Explainable forensic verification for AI-generated images.

## Quick start

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
.\.venv\Scripts\uvicorn backend.app.main:app --reload


Run the frontend:

```powershell
cd frontend
npm install
npm run dev
```

Set the API URL if needed:

```
VITE_API_BASE=http://localhost:8000
```

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

## Notes

- If `GEMINI_API_KEY` is not set, the semantic detector is marked unavailable.
- If `GROQ_API_KEY` is not set, the reasoning layer falls back to a local explanation.
- The spectral model loads from `SPECTRAL_MODEL_PATH` (default `deeptrace_fuse_best/`).
 - ELA heatmaps are generated as part of the forensic signals and included in the response.
