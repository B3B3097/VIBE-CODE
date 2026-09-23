import os, sys, json, base64, urllib.request, urllib.error

PRIORITY = ["README.md", "main.py", "app.py", "index.js", "index.ts", "package.json"]
EXT  = {".py", ".js", ".ts", ".html", ".md", ".json", ".yml", ".yaml", ".sh", ".go", ".rs", ".jsx", ".tsx"}
SKIP = {"node_modules", "__pycache__", ".git", "dist", "build", "venv", ".venv", "vendor"}
OUTPUT_PATH = "/tmp/repo_context.b64"

def gh_get(path, gh_token=""):
    url = f"https://api.github.com{path}"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "vibe-code/2.0",
    }
    if gh_token:
        headers["Authorization"] = f"Bearer {gh_token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code} for {path}: {e.reason}")
        return {}
    except Exception as e:
        print(f"  Error for {path}: {e}")
        return {}

def get_file_content(target_repo, path, gh_token=""):
    resp = gh_get(f"/repos/{target_repo}/contents/{path}", gh_token)
    if isinstance(resp, dict) and "content" in resp:
        try:
            return base64.b64decode(resp["content"]).decode("utf-8", errors="replace")
        except Exception:
            return ""
    return ""

def get_tree(target_repo, gh_token=""):
    resp = gh_get(f"/repos/{target_repo}/git/trees/HEAD?recursive=1", gh_token)
    if isinstance(resp, dict) and "tree" in resp:
        return resp["tree"]
    info = gh_get(f"/repos/{target_repo}", gh_token)
    branch = info.get("default_branch", "main") if isinstance(info, dict) else "main"
    resp = gh_get(f"/repos/{target_repo}/git/trees/{branch}?recursive=1", gh_token)
    return resp.get("tree", []) if isinstance(resp, dict) else []

def read_repository(target_repo, gh_token="", max_chars=80000, output_path=OUTPUT_PATH):
    print(f"Reading repo: {target_repo} (max {max_chars:,} chars)")
    tree = get_tree(target_repo, gh_token)
    code_files = [
        f["path"] for f in tree
        if f.get("type") == "blob"
        and any(f["path"].endswith(e) for e in EXT)
        and not any(skip in f["path"].split("/") for skip in SKIP)
    ]

    ordered = [p for p in PRIORITY if p in code_files]
    ordered += [p for p in code_files if p not in ordered]
    ordered = ordered[:60]

    files = {}
    total = 0
    for path in ordered:
        if total >= max_chars:
            break
        content = get_file_content(target_repo, path, gh_token)
        if not content:
            continue
        snippet = content[:min(3000, max_chars - total)]
        files[path] = snippet
        total += len(snippet)
        print(f"  + {path} ({len(snippet):,} chars)")

    ctx = {"repo": target_repo, "files": files, "totalChars": total}
    encoded = base64.b64encode(json.dumps(ctx).encode()).decode()
    with open(output_path, "w") as f:
        f.write(encoded)

    print(f"Saved {len(files)} files, {total:,} chars → {output_path}")
    return ctx

def main():
    target_repo = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("TARGET_REPO", "")
    gh_token    = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("GH_TOKEN", "")
    max_chars   = int(sys.argv[3]) if len(sys.argv) > 3 else int(os.environ.get("MAX_CHARS", "80000"))

    if not target_repo:
        print("Usage: read_repo.py <owner/repo> [gh_token] [max_chars]")
        sys.exit(1)

    read_repository(target_repo, gh_token, max_chars)

if __name__ == "__main__":
    main()
