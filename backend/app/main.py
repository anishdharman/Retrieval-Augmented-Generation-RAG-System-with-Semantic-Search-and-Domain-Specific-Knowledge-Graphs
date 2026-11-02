import io, secrets
from uuid import uuid4
from urllib.parse import urlencode
import httpx
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel, Field
from .config import settings
from .store import PROJECTS, GITHUB_TOKENS, ensure_session_id
from .documents import extract_text
from .ai import generate_code
from .security import publishable_files
from .github_api import list_repositories, create_repository, publish_tree, GitHubError

app = FastAPI(title="AI Project Builder API", version="1.0.0")
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret, same_site="lax", https_only=False)
app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_origin], allow_credentials=True,
                   allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

class AnalyzeRequest(BaseModel):
    topic: str = Field(min_length=10, max_length=100000)

class GenerateRequest(BaseModel):
    topic: str = Field(min_length=10, max_length=100000)
    framework: str = "React + FastAPI"
    language: str = "Python and JavaScript"

class PublishRequest(BaseModel):
    project_id: str
    mode: str = "create"
    repo_name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=350)
    visibility: str = "private"
    branch: str = Field(default="main", min_length=1, max_length=100)
    owner: str | None = None
    confirm: bool = False

@app.get("/api/health")
async def health():
    return {"status": "ok", "ai_configured": bool(settings.ai_api_key and settings.ai_model),
            "github_configured": bool(settings.github_client_id and settings.github_client_secret)}

@app.post("/api/projects/analyze")
async def analyze(payload: AnalyzeRequest):
    topic = payload.topic.strip()
    if len(topic) < 10:
        raise HTTPException(422, "Please provide a more detailed project specification.")
    return {"summary": topic[:700], "suggested_stack": ["React", "Vite", "FastAPI", "Python"],
            "checklist": ["Define requirements", "Design API and data model",
                          "Implement frontend and backend", "Add tests and documentation"]}

@app.post("/api/projects/upload")
async def upload_spec(file: UploadFile = File(...)):
    return {"filename": file.filename,
            "text": await extract_text(file, settings.max_upload_mb * 1024 * 1024)}

@app.post("/api/projects/generate")
async def generate(payload: GenerateRequest, request: Request):
    try:
        result = await generate_code(payload.topic.strip(), payload.framework, payload.language)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(502, f"AI provider error: {exc.response.status_code}") from exc
    except (httpx.HTTPError, RuntimeError) as exc:
        raise HTTPException(502, str(exc)) from exc
    project_id = str(uuid4())
    sid = ensure_session_id(request.session)
    PROJECTS[project_id] = {"id": project_id, "owner_sid": sid,
        "name": result.get("project_name", "generated-project"),
        "summary": result.get("summary", ""), "files": result["files"]}
    return {"project_id": project_id, "project_name": PROJECTS[project_id]["name"],
            "summary": PROJECTS[project_id]["summary"], "files": list(result["files"])}

def get_owned_project(project_id: str, request: Request):
    project = PROJECTS.get(project_id)
    if not project or project.get("owner_sid") != request.session.get("sid"):
        raise HTTPException(404, "Project not found or expired.")
    return project

@app.get("/api/projects/{project_id}/files")
async def get_files(project_id: str, request: Request):
    project = get_owned_project(project_id, request)
    return {"project_id": project_id, "project_name": project["name"],
            "summary": project["summary"], "files": project["files"]}

@app.get("/api/projects/{project_id}/download")
async def download(project_id: str, request: Request):
    project = get_owned_project(project_id, request)
    output = io.BytesIO()
    import zipfile
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, content in publishable_files(project["files"]).items():
            archive.writestr(path, content)
    output.seek(0)
    filename = "".join(c for c in project["name"] if c.isalnum() or c in "-_") or "project"
    return StreamingResponse(output, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}.zip"'})

@app.get("/api/github/login")
async def github_login(request: Request, visibility: str = "private"):
    if not settings.github_client_id or not settings.github_client_secret:
        raise HTTPException(503, "GitHub OAuth is not configured on the backend.")
    if visibility not in {"public", "private"}:
        raise HTTPException(422, "Invalid visibility.")
    ensure_session_id(request.session)
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state
    scope = "public_repo" if visibility == "public" else "repo"
    params = {"client_id": settings.github_client_id, "redirect_uri": settings.github_callback_url,
              "scope": scope, "state": state}
    return RedirectResponse("https://github.com/login/oauth/authorize?" + urlencode(params))

@app.get("/api/github/callback")
async def github_callback(request: Request, code: str = "", state: str = ""):
    expected = request.session.get("oauth_state")
    request.session.pop("oauth_state", None)
    if not expected or not secrets.compare_digest(expected, state):
        raise HTTPException(400, "OAuth state validation failed.")
    if not code:
        raise HTTPException(400, "GitHub did not return an authorization code.")
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post("https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            json={"client_id": settings.github_client_id, "client_secret": settings.github_client_secret,
                  "code": code, "redirect_uri": settings.github_callback_url})
    if response.status_code >= 400 or "access_token" not in response.json():
        raise HTTPException(502, "GitHub OAuth exchange failed.")
    sid = ensure_session_id(request.session)
    GITHUB_TOKENS[sid] = response.json()["access_token"]
    request.session["github_connected"] = True
    return RedirectResponse(settings.frontend_origin + "/?github=connected")

def get_token(request: Request):
    token = GITHUB_TOKENS.get(request.session.get("sid", ""))
    if not token:
        raise HTTPException(401, "Connect GitHub before publishing.")
    return token

@app.get("/api/github/repositories")
async def repositories(request: Request):
    try:
        repos = await list_repositories(get_token(request))
        return [{"id": r["id"], "name": r["name"], "full_name": r["full_name"],
                 "private": r["private"], "default_branch": r.get("default_branch") or "main",
                 "html_url": r["html_url"]} for r in repos]
    except GitHubError as exc:
        raise HTTPException(502, str(exc)) from exc

@app.post("/api/github/publish")
async def publish(payload: PublishRequest, request: Request):
    if not payload.confirm:
        raise HTTPException(400, "Explicit confirmation is required before publishing.")
    project = get_owned_project(payload.project_id, request)
    files = publishable_files(project["files"])
    if not files:
        raise HTTPException(422, "No safe files are available to publish.")
    if payload.mode not in {"create", "existing"} or payload.visibility not in {"public", "private"}:
        raise HTTPException(422, "Invalid publishing options.")
    if not payload.branch.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(422, "Invalid branch name.")
    token = get_token(request)
    try:
        if payload.mode == "create":
            repo = await create_repository(token, payload.repo_name, payload.description,
                                           payload.visibility == "private")
            owner = repo["owner"]["login"]
        else:
            owner = payload.owner
            if not owner:
                raise HTTPException(422, "Owner is required for an existing repository.")
        result = await publish_tree(token, owner, payload.repo_name, payload.branch, files)
        return {"success": True, "repository_url": result["url"],
                "commit_sha": result["commit_sha"], "published_files": len(files)}
    except GitHubError as exc:
        raise HTTPException(502, str(exc)) from exc
