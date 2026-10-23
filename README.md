# VietTubeLens

VietTubeLens is a Chrome Manifest V3 extension and FastAPI service for analysing
Vietnamese YouTube community reactions. The interface uses the **Signal Prism**
visual language and always presents its output as an estimate over analysed
comments, never as an objective quality score for a video.

## Quick start

### Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev,ml]"
uvicorn app.main:app --reload --port 8000
```

The backend automatically uses deterministic demo data when `YOUTUBE_API_KEY`
is not set. Copy `backend/.env.example` to `backend/.env`, add a key and set
`DEMO_MODE=false` to analyse real public comments. Never commit the `.env` file.
The first analysis downloads the configured ViSoBERT sentiment and toxicity
checkpoints, then keeps them resident for batched inference. The health endpoint
reports whether the models are lazy, loading, ready, or using the explicit
heuristic fallback.

### Extension

```powershell
cd apps/extension
npm install
npm run build
```

Load `apps/extension/dist` as an unpacked extension at `chrome://extensions`.
The default backend URL is `http://127.0.0.1:8000`; it can be changed from the
extension popup.

## Repository layout

- `apps/extension` — React/TypeScript Chrome extension and Signal Prism UI.
- `backend` — FastAPI batch API, SQLite cache, collector and analysis pipeline.
- `ml` — dataset schema and training/evaluation entry points for the research model.
- `docs` — annotation guide and experiment contract.

## Privacy and interpretation

The extension sends only YouTube video IDs to the configured backend. The API
key stays on the backend. Evidence quotes are public comments returned by the
YouTube Data API. Demo-mode output is explicitly marked as simulated.
