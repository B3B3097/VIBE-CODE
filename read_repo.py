import os, json, base64

R = "/tmp/target-repo"
F = {}; T = 0; MAX = 80000
PRIORITY = ["README.md", "main.py", "app.py", "index.js", "index.ts", "package.json"]
EXT  = {".py", ".js", ".ts", ".html", ".md", ".json", ".yml", ".sh", ".go", ".rs"}
SKIP = {"node_modules", "__pycache__", ".git", "dist", "build", "venv", ".venv"}

def add(rel, full):
    global T
    if T >= MAX: return
    try:
        c = open(full, "r", encoding="utf-8", errors="ignore").read()
        if T + len(c) > MAX: c = c[:MAX - T]
        F[rel] = c; T += len(c)
        print(f"  + {rel} ({len(c):,} chars)")
    except: pass

for n in PRIORITY:
    p = os.path.join(R, n)
    if os.path.exists(p): add(n, p)

for root, dirs, fns in os.walk(R):
    dirs[:] = [d for d in dirs if d not in SKIP and not d.startswith(".")]
    for fn in sorted(fns):
        if T >= MAX: break
        if os.path.splitext(fn)[1].lower() in EXT:
            full = os.path.join(root, fn)
            rel  = os.path.relpath(full, R)
            if rel not in F: add(rel, full)

ctx = {"repo": os.environ["TARGET_REPO"], "files": F, "totalChars": T}
open("/tmp/repo_context.b64", "w").write(
    base64.b64encode(json.dumps(ctx).encode()).decode()
)
print(f"Saved {len(F)} files, {T:,} chars -> /tmp/repo_context.b64")
