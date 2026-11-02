import json
import httpx
from .config import settings
from .security import clean_generated_files

SYSTEM_PROMPT = (
    "You are a senior software engineer. Generate a complete runnable application from the user's "
    "specification. Return ONLY valid JSON: {\"project_name\":\"short-kebab-case-name\","
    "\"summary\":\"short summary\",\"files\":{\"relative/path\":\"complete text content\"}}. "
    "Include frontend, backend, dependency manifests, README.md, .gitignore and .env.example as appropriate. "
    "Never include real credentials, API keys, passwords, tokens, binary files, dependency folders or build "
    "artifacts. Use environment variables for secrets. Include validation, error handling and setup docs. "
    "Use safe relative paths. Limit to 100 text files. Do not wrap JSON in markdown fences."
)

async def generate_code(topic: str, framework: str, language: str) -> dict:
    if not settings.ai_api_key or not settings.ai_model:
        raise RuntimeError("AI is not configured. Set AI_API_KEY and AI_MODEL in backend/.env.")
    url = settings.ai_base_url.rstrip("/") + "/chat/completions"
    payload = {"model": settings.ai_model, "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": SYSTEM_PROMPT},
          {"role": "user", "content": f"Project specification:\n{topic}\nFramework: {framework}\nLanguage: {language}\nGenerate the complete application."}]}
    async with httpx.AsyncClient(timeout=settings.ai_timeout_seconds) as client:
        response = await client.post(url, json=payload,
            headers={"Authorization": f"Bearer {settings.ai_api_key}"})
        response.raise_for_status()
    try:
        parsed = json.loads(response.json()["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("AI provider returned invalid JSON. Try a model supporting JSON output.") from exc
    if not isinstance(parsed, dict) or not isinstance(parsed.get("files"), dict):
        raise RuntimeError("AI response did not contain a files object.")
    parsed["files"] = clean_generated_files(parsed["files"])
    return parsed
