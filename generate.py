#!/usr/bin/env python3
"""
VIBE-CODE local model runner.
Downloads Qwen2.5-Coder-7B, generates code, tests it, iterates.
"""
import os, sys, json, subprocess, re, shutil, time, urllib.request
from datetime import datetime

MODEL_NAME   = "qwen2.5-coder:7b"
PROMPT       = os.environ.get("PROMPT", "")
SESSION_ID   = os.environ.get("SESSION_ID", datetime.now().strftime("%Y%m%d%H%M%S"))
MAX_ITERS    = int(os.environ.get("MAX_ITERS", "3"))
MAX_TOKENS   = int(os.environ.get("MAX_TOKENS", "32768"))
OLLAMA_HOST  = "http://127.0.0.1:11434"
REPO_DIR     = os.environ.get("GITHUB_WORKSPACE", ".")

SYSTEM_PROMPT = """You are an elite software engineer. Your task:
1. Write COMPLETE, immediately runnable production-grade code — no placeholders, no "TODO"
2. Mark EVERY file with its filename in the first line comment:
   ```python
   # main.py
   ...
   ```
3. Include ALL required files: main code, requirements.txt or package.json, .env.example
4. Handle errors gracefully, add input validation
5. After writing, mentally run through every line to catch bugs"""


# ─── Ollama API ───────────────────────────────────────────────────────────────

def ollama_ready(timeout=60):
    for _ in range(timeout):
        try:
            urllib.request.urlopen(f"{OLLAMA_HOST}/api/tags", timeout=2)
            return True
        except Exception:
            time.sleep(1)
    return False


def call_model(messages):
    """Call Ollama /api/chat with multi-turn messages. Returns response text."""
    body = json.dumps({
        "model": MODEL_NAME,
        "messages": messages,
        "stream": False,
        "options": {
            "num_predict": MAX_TOKENS,
            "num_ctx":     MAX_TOKENS,
            "temperature": 0.15,
            "top_p":       0.9,
        },
    }).encode()
    req  = urllib.request.Request(
        f"{OLLAMA_HOST}/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=7200) as r:
        return json.loads(r.read())["message"]["content"]


# ─── Code parsing ─────────────────────────────────────────────────────────────

LANG_DEFAULTS = {
    "python":"main.py","py":"main.py",
    "javascript":"index.js","js":"index.js",
    "typescript":"index.ts","ts":"index.ts",
    "html":"index.html","css":"style.css",
    "bash":"run.sh","sh":"run.sh",
    "json":"config.json","sql":"schema.sql",
    "go":"main.go","rust":"main.rs","dockerfile":"Dockerfile",
}

def parse_files(text):
    files = []
    pattern = r"```(\w*)\n(?:(?:#|//|<!--)\s*(\S+\.\S+).*?\n)?([^`]*?)```"
    for m in re.finditer(pattern, text, re.DOTALL):
        lang    = m.group(1).lower() or "text"
        name    = m.group(2)
        content = m.group(3).strip()
        if not content:
            continue
        if not name:
            name = LANG_DEFAULTS.get(lang, f"file_{len(files)}.txt")
            if any(f["name"] == name for f in files):
                name = name.replace(".", f"_{len(files)}.", 1)
        files.append({"lang": lang, "name": name, "content": content})
    return files


# ─── Code testing ─────────────────────────────────────────────────────────────

def test_code(files, workdir):
    os.makedirs(workdir, exist_ok=True)
    # Write all files
    for f in files:
        dest = os.path.join(workdir, f["name"])
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as fp:
            fp.write(f["content"])

    # Install requirements
    req = os.path.join(workdir, "requirements.txt")
    if os.path.exists(req):
        r = subprocess.run(
            ["pip", "install", "-r", req, "-q", "--break-system-packages"],
            capture_output=True, timeout=120
        )
        if r.returncode != 0:
            return False, "pip install failed:\n" + r.stderr.decode(errors="replace")[:1000]

    # Find entry point
    candidates = [f for f in files if f["lang"] in ("python", "py")]
    if not candidates:
        return True, "(no Python code to test)"
    main_f = next((f for f in candidates if "main" in f["name"]), candidates[0])

    try:
        r = subprocess.run(
            ["python3", "-c", f"import ast; ast.parse(open('{main_f['name']}').read()); print('SYNTAX OK')"],
            cwd=workdir, capture_output=True, text=True, timeout=15
        )
        if r.returncode != 0:
            return False, "Syntax error:\n" + r.stderr[:1000]

        r2 = subprocess.run(
            ["python3", main_f["name"]],
            cwd=workdir, capture_output=True, text=True, timeout=25,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        )
        if r2.returncode == 0:
            return True, r2.stdout[:1000] or "(exited cleanly)"
        else:
            err = r2.stderr[:1000] or r2.stdout[:1000]
            return False, err
    except subprocess.TimeoutExpired:
        return True, "(ran, timed out — expected for long-running services)"
    except Exception as exc:
        return False, str(exc)


# ─── Progress file ────────────────────────────────────────────────────────────

def write_progress(folder, status, msg, files=None):
    data = {
        "status":    status,
        "message":   msg,
        "folder":    folder,
        "timestamp": datetime.now().isoformat(),
        "files":     files or [],
    }
    path = os.path.join(folder, "_progress.json")
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False)


def slugify(text, n=40):
    s = re.sub(r"[^a-zA-Z0-9а-яёА-ЯЁ]+", "-", text[:n]).strip("-").lower()
    return s or "project"


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    if not PROMPT:
        print("ERROR: PROMPT is empty"); sys.exit(1)

    date   = datetime.now().strftime("%Y-%m-%d")
    folder = f"output/{date}_{slugify(PROMPT)}"
    os.makedirs(folder, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"🚀 VIBE-CODE — Local AI Code Generator")
    print(f"📝 Prompt  : {PROMPT[:100]}")
    print(f"🤖 Model   : {MODEL_NAME}")
    print(f"📁 Folder  : {folder}/")
    print(f"🔄 Iters   : {MAX_ITERS}   Max tokens: {MAX_TOKENS}")
    print(f"{'='*60}\n")

    # Wait for Ollama
    print("⏳ Waiting for Ollama service...")
    if not ollama_ready(90):
        print("❌ Ollama not ready"); sys.exit(1)
    print("✅ Ollama ready\n")

    messages  = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": PROMPT},
    ]
    last_files = []
    workdir    = f"/tmp/vc_{SESSION_ID}"

    write_progress(folder, "running", "🧠 Generating code...")

    for it in range(MAX_ITERS):
        tag = f"ITER {it+1}/{MAX_ITERS}"
        if it == 0:
            print(f"[{tag}] 🧠 Generating initial code...")
        else:
            print(f"[{tag}] 🔄 Reviewing and fixing code...")

        t0  = time.time()
        raw = call_model(messages)
        print(f"[{tag}] ✅ Response: {len(raw):,} chars  ({time.time()-t0:.1f}s)")

        # Save raw response
        with open(os.path.join(folder, f"_raw_{it+1}.txt"), "w", encoding="utf-8") as f:
            f.write(raw)

        files = parse_files(raw)
        print(f"[{tag}] 📄 Found {len(files)} file(s): {[f['name'] for f in files]}")

        if not files:
            # Try to extract at least the whole response as one file
            print(f"[{tag}] ⚠️  No code blocks detected, saving raw response")
            write_progress(folder, "running", f"Iteration {it+1}: no code blocks found, retrying...")
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content":
                "Please rewrite your answer with ALL code inside proper markdown code blocks: "
                "```language\n# filename.ext\n...code...\n```"
            })
            continue

        last_files = files
        iwd = f"{workdir}_it{it}"
        test_ok, test_out = test_code(files, iwd)
        print(f"[{tag}] {'✅' if test_ok else '❌'} Test: {test_out[:300]}")

        write_progress(folder, "running",
            f"Iteration {it+1}: {'✅ tests pass' if test_ok else '❌ fixing errors...'}")

        if test_ok:
            if it < MAX_ITERS - 1:
                messages.append({"role": "assistant", "content": raw})
                messages.append({"role": "user", "content":
                    "Code runs successfully! Now:\n"
                    "1. Add proper error handling and edge cases\n"
                    "2. Add helpful docstrings/comments\n"
                    "3. Improve code quality overall\n"
                    "Write the COMPLETE improved version. "
                    "If the code is already excellent, write CODE_IS_READY on first line."
                })
                if "CODE_IS_READY" in raw[:50]:
                    print(f"[{tag}] 🎯 Model says: code is ready!")
                    break
            else:
                break
        else:
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content":
                f"The code produced this error:\n```\n{test_out[:1500]}\n```\n\n"
                "Fix ALL bugs and write the COMPLETE corrected version of every file."
            })

    # ── Save final output ──
    if last_files:
        print(f"\n📁 Saving {len(last_files)} file(s) to {folder}/")
        for f in last_files:
            dest = os.path.join(folder, f["name"])
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "w", encoding="utf-8") as fp:
                fp.write(f["content"])
            print(f"   📝 {dest}")

        readme = f"""# {slugify(PROMPT).replace('-', ' ').title()}

**Сгенерировано VIBE-CODE AI**

| | |
|---|---|
| **Запрос** | {PROMPT} |
| **Модель** | {MODEL_NAME} |
| **Дата** | {datetime.now().strftime('%Y-%m-%d %H:%M UTC')} |
| **Итераций** | {MAX_ITERS} |

## Файлы
{chr(10).join(f'- `{f["name"]}`' for f in last_files)}

## Запуск
```bash
{'pip install -r requirements.txt' if any(f["name"]=="requirements.txt" for f in last_files) else ''}
python main.py
```
"""
        with open(os.path.join(folder, "README.md"), "w", encoding="utf-8") as f:
            f.write(readme)

        write_progress(folder, "done",
            f"✅ Code ready in {folder}/",
            files=[f["name"] for f in last_files] + ["README.md"]
        )

        print(f"\n✅ DONE!  Folder: {folder}/")
        print(f"📂 Files : {[f['name'] for f in last_files]}\n")
    else:
        write_progress(folder, "error", "No code blocks found in any iteration")
        print("\n❌ No code generated")
        sys.exit(1)


if __name__ == "__main__":
    main()
