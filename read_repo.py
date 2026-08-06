
</think>

</think>

import os, sys, json, base64, urllib.request, urllib.error

# ── Accept CLI args OR env vars ─────────────────────────────────────────────
TARGET_REPO = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("TARGET_REPO", "")
GH_TOKEN    = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("GH_TOKEN", "")
MAX_CHARS   = int(sys.argv[3]) if len(sys.argv) > 3 else int(os.environ.get("MAX_CHARS", "80000"))

if not TARGET_REPO:
    print("\nError: Repository name is required. Please provide a valid GitHub repository name.\n")
    sys.exit(1)

PRIORITY = ["README.md", "main.py", "app.py", "index.js", "index.ts", "package.json"]
EXT  = {".py", ".js", ".ts", ".html", ".md", ".json", ".yml", ".sh", ".go", ".rs", ".jsx", ".tsx"}
SKIP = {"node_modules", "__pycache__", ".git", "dist", "build", "venv", ".venv", "vendor"}

OUTPUT_PATH = os.path.join(os.getenv('TEMP'), "repo_context.b64")

def gh_get(path):
    url = f"https://api.github.com{path}"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "vibe-code/2.0",
    }
    if GH_TOKEN:
        headers["Authorization"] = f"Bearer {GH_TOKEN}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"\n  HTTP {e.code} for {path}: {e.reason}")
        return {}
    except Exception as e:
        print(f"\n  Error for {path}: {e}")
        return {}

def get_file_content(path):
    resp = gh_get(f"/repos/{TARGET_REPO}/contents/{path}")
    if isinstance(resp, dict) and "content" in resp:
        try:
            return base64.b64decode(resp["content"]).decode("utf-8", errors="replace")
        except Exception:
            return ""
    return ""

def get_tree():
    resp = gh_get(f"/repos/{TARGET_REPO}/git/trees/HEAD?recursive=1")
    if isinstance(resp, dict) and "tree" in resp:
        return resp["tree"]
    # Fallback: try default branch from repo info
    info = gh_get(f"/repos/{TARGET_REPO}")
    branch = info.get("default_branch", "main") if isinstance(info, dict) else "main"
    resp = gh_get(f"/repos/{TARGET_REPO}/git/trees/{branch}?recursive=1")
    return resp.get("tree", []) if isinstance(resp, dict) else []

print(f"\nReading repo: {TARGET_REPO} (max {MAX_CHARS:,} chars)")

tree = get_tree()
code_files = [
    f["path"] for f in tree
    if f.get("type") == "blob"
    and any(f["path"].endsWith(e) for e in EXT)
    and not any(skip in f["path"].split("/") for skip in SKIP)
]

# Add debug output to show which files are being processed
print("\nProcessing files:")
for path in code_files:
    print(f"  - {path}")

# Priority files first, then the rest
ordered = [p for p in PRIORITY if p in code_files]
ordered += [p for p in code_files if p not in ordered]
ordered = ordered[:60]

F = {}
total = 0

for path in ordered:
    if total >= MAX_CHARS:
        break
    content = get_file_content(path)
    if not content:
        continue
    # Add debug output to show file content
    print(f"\nContent of {path} (first 3000 chars):")
    print(content[:3000])
    snippet = content[:3000]
    F[path] = snippet
    total += len(snippet)
    print(f"  + {path} ({len(snippet):,} chars)")

ctx = {"repo": TARGET_REPO, "files": F, "totalChars": total}
encoded = base64.b64encode(json.dumps(ctx).encode()).decode()
with open(OUTPUT_PATH, "w") as f:
    f.write(encoded)

print(f"\nSaved {len(F)} files, {total:,} chars → {OUTPUT_PATH}")

print(f"\nSaved {len(F)} files, {total:,} chars → {OUTPUT_PATH}")

name: Build and Test Web Application

on:
  push:
    branches:
      - main
  pull_request:
    branches:
      - main

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
    - name: Checkout code
      uses: actions/checkout@v3

    - name: Set up Node.js
      uses: actions/setup-node@v4
      with:
        node-version: 18

    - name: Install dependencies
      run: |
        npm install

    - name: Build application
      run: |
        npm run build

    - name: Run tests
      run: |
        npm test