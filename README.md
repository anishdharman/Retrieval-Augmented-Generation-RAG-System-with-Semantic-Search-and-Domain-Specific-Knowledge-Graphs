# AI Project Builder — RAG System Edition

Full-stack React/Vite + FastAPI application for AI code generation, file preview, ZIP download and GitHub publishing.

## Setup

Requirements: Python 3.10+, Node.js 18+, an OpenAI-compatible AI API, and optional GitHub OAuth App credentials.

### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with AI_API_KEY, AI_MODEL and optional GitHub OAuth values.
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:5173. Vite proxies `/api` to FastAPI.

## Configuration
Set `AI_API_KEY`, `AI_BASE_URL`, `AI_MODEL`, `SESSION_SECRET`, `FRONTEND_ORIGIN`, and optionally `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `GITHUB_CALLBACK_URL` in `backend/.env`. For GitHub OAuth, create an OAuth App with homepage `http://localhost:5173` and callback matching `GITHUB_CALLBACK_URL`. Public repositories request `public_repo`; private repositories request `repo`.

## API
- POST `/api/projects/analyze`
- POST `/api/projects/upload`
- POST `/api/projects/generate`
- GET `/api/projects/{project_id}/files`
- GET `/api/projects/{project_id}/download`
- GET `/api/github/login`
- GET `/api/github/callback`
- GET `/api/github/repositories`
- POST `/api/github/publish`

## Production hardening
The included in-memory project and OAuth-token stores are for local development and reset on restart. Replace them with a database and encrypted server-side token storage (for example Redis), enable HTTPS cookies, use a strong secret, add rate limiting and malware scanning, and restrict deployment origins. Generated code should be reviewed before execution or publication. Never commit `.env`.
