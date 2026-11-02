import httpx

API = "https://api.github.com"
BASE_HEADERS = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}

class GitHubError(Exception):
    pass

async def request(method: str, path: str, token: str, **kwargs):
    headers = {**BASE_HEADERS, "Authorization": f"Bearer {token}", **kwargs.pop("headers", {})}
    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.request(method, API + path, headers=headers, **kwargs)
    if response.status_code >= 400:
        try:
            detail = response.json().get("message", response.text)
        except Exception:
            detail = response.text
        if response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0":
            raise GitHubError("GitHub API rate limit reached. Wait and retry.")
        raise GitHubError(f"GitHub API returned {response.status_code}: {detail}")
    return response.json() if response.content else {}

async def list_repositories(token: str):
    return await request("GET", "/user/repos?per_page=100&sort=updated", token)

async def create_repository(token: str, name: str, description: str, private: bool):
    return await request("POST", "/user/repos", token,
        json={"name": name, "description": description, "private": private, "auto_init": True})

async def publish_tree(token: str, owner: str, repo: str, branch: str, files: dict[str, str]):
    info = await request("GET", f"/repos/{owner}/{repo}", token)
    default_branch = info.get("default_branch") or branch
    ref = None
    try:
        ref = await request("GET", f"/repos/{owner}/{repo}/git/ref/heads/{branch}", token)
    except GitHubError as exc:
        if "404" not in str(exc):
            raise
    parent_sha, base_tree = None, None
    if ref:
        parent_sha = ref["object"]["sha"]
    elif not info.get("empty", False):
        ref = await request("GET", f"/repos/{owner}/{repo}/git/ref/heads/{default_branch}", token)
        parent_sha = ref["object"]["sha"]
    if parent_sha:
        parent = await request("GET", f"/repos/{owner}/{repo}/git/commits/{parent_sha}", token)
        base_tree = parent["tree"]["sha"]
    entries = []
    for path, content in files.items():
        blob = await request("POST", f"/repos/{owner}/{repo}/git/blobs", token,
            json={"content": content, "encoding": "utf-8"})
        entries.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
    tree_payload = {"tree": entries}
    if base_tree:
        tree_payload["base_tree"] = base_tree
    tree = await request("POST", f"/repos/{owner}/{repo}/git/trees", token, json=tree_payload)
    commit_payload = {"message": "Publish generated project", "tree": tree["sha"]}
    if parent_sha:
        commit_payload["parents"] = [parent_sha]
    commit = await request("POST", f"/repos/{owner}/{repo}/git/commits", token, json=commit_payload)
    if ref:
        await request("PATCH", f"/repos/{owner}/{repo}/git/refs/heads/{branch}", token,
            json={"sha": commit["sha"], "force": False})
    else:
        await request("POST", f"/repos/{owner}/{repo}/git/refs", token,
            json={"ref": f"refs/heads/{branch}", "sha": commit["sha"]})
    return {"commit_sha": commit["sha"], "url": f"https://github.com/{owner}/{repo}"}
