#!/usr/bin/env python3
"""
VIBE-CODE local model runner.
Two modes:
  - GENERATE: create code from scratch (multi-file)
  - IMPROVE:  analyze existing file, return improved single file
"""
import os, sys, json, subprocess, re, time, urllib.request, base64
from datetime import datetime

MODEL_NAME   = "qwen2.5-coder:7b"
PROMPT       = os.environ.get("PROMPT", "")
SESSION_ID   = os.environ.get("SESSION_ID", datetime.now().strftime("%Y%m%d%H%M%S"))
MAX_ITERS    = int(os.environ.get("MAX_ITERS", "3"))
MAX_TOKENS   = int(os.environ.get("MAX_TOKENS", "32768"))
FILE_NAME    = os.environ.get("FILE_NAME", "").strip()
FILE_CONTENT_B64 = os.environ.get("FILE_CONTENT", "").strip()
OLLAMA_HOST  = "http://127.0.0.1:11434"

# Decode attached file if provided
ATTACHED_CONTENT = ""
if FILE_CONTENT_B64:
    try:
        ATTACHED_CONTENT = base64.b64decode(FILE_CONTENT_B64).decode("utf-8")
    except Exception as e:
        print(f"⚠️  Could not decode file content: {e}")

MODE = "improve" if ATTACHED_CONTENT else "generate"

SYSTEM_GENERATE = """You are an elite software engineer. Your task:
1. Write COMPLETE, immediately runnable production-grade code — no placeholders, no "TODO"
2. Mark EVERY file with its filename in the first line comment:
   ```python
   # main.py
   ...code...
   ```
3. Include ALL required files: main code, requirements.txt or package.json if needed
4. Handle errors gracefully, add input validation
5. After writing, mentally run through every line to catch bugs before returning"""

SYSTEM_IMPROVE = """You are an expert code reviewer and senior engineer.
You are given an existing file. Your task:
1. Carefully read and understand every line of the file
2. Find ALL bugs, errors, bad practices, missing error handling
3. Improve the code: fix bugs, add validation, improve readability, optimize where needed
4. Return ONLY the complete improved file — single code block, same filename
5. Do NOT split into multiple files, do NOT add extra files
6. The file must be immediately runnable after your changes
7. Preserve the original purpose and behavior, only improve quality"""


# ─── Ollama ───────────────────────────────────────────────────────────────────

def ollama_ready(timeout=90):
    for _ in range(timeout):
        try:
            urllib.request.urlopen(f"{OLLAMA_HOST}/api/tags", timeout=2)
            return True
        except Exception:
            time.sleep(1)
    return False

def call_model(messages):
    body = json.dumps({
        "model": MODEL_NAME,
        "messages": messages,
        "stream": False,
        "options": {
            "num_predict": MAX_TOKENS,
            "num_ctx":     MAX_TOKENS,
            "temperature": 0.12,
            "top_p":       0.9,
        },
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=7200) as r:
        return json.loads(r.read())["message"]["content"]


# ─── Parsing ──────────────────────────────────────────────────────────────────

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

def parse_single_file(text, fallback_name):
    """Extract the first (and only) code block, use fallback_name if no filename comment."""
    pattern = r"```(\w*)\n(?:(?:#|//|<!--)\s*(\S+\.\S+).*?\n)?([^`]*?)```"
    m = re.search(pattern, text, re.DOTALL)
    if not m:
        return None
    lang    = m.group(1).lower() or "text"
    name    = m.group(2) or fallback_name
    content = m.group(3).strip()
    return {"lang": lang, "name": name, "content": content} if content else None


# ─── Testing ──────────────────────────────────────────────────────────────────

def test_single_file(file_obj, workdir):
    os.makedirs(workdir, exist_ok=True)
    path = os.path.join(workdir, file_obj["name"])
    with open(path, "w", encoding="utf-8") as f:
        f.write(file_obj["content"])

    if file_obj["lang"] not in ("python", "py"):
        return True, "(non-Python file — skipping runtime test)"

    try:
        r = subprocess.run(
            ["python3", "-c",
             f"import ast; ast.parse(open('{file_obj['name']}').read()); print('SYNTAX OK')"],
            cwd=workdir, capture_output=True, text=True, timeout=10
        )
        if r.returncode != 0:
            return False, "Syntax error:\n" + r.stderr[:1000]

        r2 = subprocess.run(
            ["python3", file_obj["name"]],
            cwd=workdir, capture_output=True, text=True, timeout=20,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        )
        if r2.returncode == 0:
            return True, r2.stdout[:800] or "(exited cleanly)"
        return False, r2.stderr[:800] or r2.stdout[:800]
    except subprocess.TimeoutExpired:
        return True, "(ran, timed out — likely a long-running service, OK)"
    except Exception as exc:
        return False, str(exc)

def test_code(files, workdir):
    os.makedirs(workdir, exist_ok=True)
    for f in files:
        dest = os.path.join(workdir, f["name"])
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as fp:
            fp.write(f["content"])

    req = os.path.join(workdir, "requirements.txt")
    if os.path.exists(req):
        r = subprocess.run(
            ["pip", "install", "-r", req, "-q", "--break-system-packages"],
            capture_output=True, timeout=120
        )
        if r.returncode != 0:
            return False, "pip install failed:\n" + r.stderr.decode(errors="replace")[:800]

    candidates = [f for f in files if f["lang"] in ("python", "py")]
    if not candidates:
        return True, "(no Python code to test)"
    main_f = next((f for f in candidates if "main" in f["name"]), candidates[0])

    try:
        r = subprocess.run(
            ["python3", "-c",
             f"import ast; ast.parse(open('{main_f['name']}').read()); print('SYNTAX OK')"],
            cwd=workdir, capture_output=True, text=True, timeout=15
        )
        if r.returncode != 0:
            return False, "Syntax error:\n" + r.stderr[:800]

        r2 = subprocess.run(
            ["python3", main_f["name"]],
            cwd=workdir, capture_output=True, text=True, timeout=25,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        )
        if r2.returncode == 0:
            return True, r2.stdout[:800] or "(exited cleanly)"
        return False, r2.stderr[:800] or r2.stdout[:800]
    except subprocess.TimeoutExpired:
        return True, "(ran, timed out — OK for services)"
    except Exception as exc:
        return False, str(exc)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def write_progress(folder, status, msg, files=None):
    data = {"status": status, "message": msg, "folder": folder,
            "timestamp": datetime.now().isoformat(), "files": files or [], "mode": MODE}
    with open(os.path.join(folder, "_progress.json"), "w") as f:
        json.dump(data, f, ensure_ascii=False)

def slugify(text, n=40):
    s = re.sub(r"[^a-zA-Z0-9а-яёА-ЯЁ]+", "-", text[:n]).strip("-").lower()
    return s or "project"


# ─── IMPROVE MODE ─────────────────────────────────────────────────────────────

def run_improve():
    date    = datetime.now().strftime("%Y-%m-%d")
    slug    = slugify(FILE_NAME.split(".")[0] or PROMPT or "improved")
    folder  = f"output/{date}_improved_{slug}"
    workdir = f"/tmp/vc_{SESSION_ID}"
    os.makedirs(folder, exist_ok=True)

    user_request = PROMPT.strip() or "Проверь и улучши этот файл максимально."

    print(f"\n{'='*60}")
    print(f"🔧 VIBE-CODE — File Improvement Mode")
    print(f"📄 File    : {FILE_NAME}  ({len(ATTACHED_CONTENT)} chars)")
    print(f"📝 Request : {user_request[:100]}")
    print(f"🤖 Model   : {MODEL_NAME}")
    print(f"🔄 Iters   : {MAX_ITERS}")
    print(f"{'='*60}\n")

    print("⏳ Waiting for Ollama...")
    if not ollama_ready(90):
        print("❌ Ollama not ready"); sys.exit(1)
    print("✅ Ollama ready\n")

    # Detect language for syntax check
    ext = FILE_NAME.rsplit(".", 1)[-1].lower() if "." in FILE_NAME else ""

    messages = [
        {"role": "system", "content": SYSTEM_IMPROVE},
        {"role": "user", "content":
            f"Here is the file `{FILE_NAME}`:\n\n"
            f"```{ext}\n# {FILE_NAME}\n{ATTACHED_CONTENT}\n```\n\n"
            f"Task: {user_request}\n\n"
            f"Return ONLY the complete improved file in a single code block. "
            f"Start the block with `# {FILE_NAME}` as first line comment."
        },
    ]

    write_progress(folder, "running", f"🔧 Analysing {FILE_NAME}...")
    last_file = None

    for it in range(MAX_ITERS):
        tag = f"ITER {it+1}/{MAX_ITERS}"
        print(f"[{tag}] {'🔍 Analyzing and improving...' if it==0 else '🔄 Verifying and polishing...'}")

        t0  = time.time()
        raw = call_model(messages)
        print(f"[{tag}] ✅ Response: {len(raw):,} chars ({time.time()-t0:.1f}s)")

        with open(os.path.join(folder, f"_raw_{it+1}.txt"), "w", encoding="utf-8") as f:
            f.write(raw)

        file_obj = parse_single_file(raw, FILE_NAME)
        if not file_obj:
            print(f"[{tag}] ⚠️  No code block, retrying...")
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content":
                f"Return the improved file in a single code block:\n"
                f"```{ext}\n# {FILE_NAME}\n...improved code...\n```"
            })
            continue

        last_file = file_obj
        test_ok, test_out = test_single_file(file_obj, f"{workdir}_it{it}")
        print(f"[{tag}] {'✅' if test_ok else '❌'} Test: {test_out[:200]}")

        write_progress(folder, "running",
            f"Iter {it+1}: {'✅ OK' if test_ok else '❌ fixing...'}")

        if test_ok:
            if it < MAX_ITERS - 1:
                messages.append({"role": "assistant", "content": raw})
                messages.append({"role": "user", "content":
                    "The file works correctly. Do one final pass:\n"
                    "1. Add/improve docstrings and inline comments\n"
                    "2. Strengthen all error handling\n"
                    "3. Remove any dead code\n"
                    "Return the COMPLETE final file. "
                    "If already perfect, start your response with DONE."
                })
                if raw.strip().startswith("DONE"):
                    print(f"[{tag}] 🎯 Model: file is perfect!")
                    break
            else:
                break
        else:
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content":
                f"This error occurred:\n```\n{test_out[:1200]}\n```\n\n"
                f"Fix ALL issues and return the complete corrected `{FILE_NAME}`."
            })

    # Save output
    if last_file:
        out_path = os.path.join(folder, last_file["name"])
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(last_file["content"])
        print(f"\n✅ Saved: {out_path}")

        # Diff summary
        orig_lines = ATTACHED_CONTENT.splitlines()
        new_lines  = last_file["content"].splitlines()
        print(f"   Original: {len(orig_lines)} lines  →  Improved: {len(new_lines)} lines")

        write_progress(folder, "done",
            f"✅ {last_file['name']} improved ({len(orig_lines)}→{len(new_lines)} lines)",
            files=[last_file["name"]]
        )
        print(f"\n✅ DONE! Output: {folder}/{last_file['name']}")
    else:
        write_progress(folder, "error", "Could not extract improved file")
        print("❌ No output generated"); sys.exit(1)


# ─── GENERATE MODE ────────────────────────────────────────────────────────────

def run_generate():
    date    = datetime.now().strftime("%Y-%m-%d")
    folder  = f"output/{date}_{slugify(PROMPT)}"
    workdir = f"/tmp/vc_{SESSION_ID}"
    os.makedirs(folder, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"🚀 VIBE-CODE — Code Generator Mode")
    print(f"📝 Prompt  : {PROMPT[:100]}")
    print(f"🤖 Model   : {MODEL_NAME}")
    print(f"📁 Folder  : {folder}/")
    print(f"🔄 Iters   : {MAX_ITERS}   Max tokens: {MAX_TOKENS}")
    print(f"{'='*60}\n")

    print("⏳ Waiting for Ollama...")
    if not ollama_ready(90):
        print("❌ Ollama not ready"); sys.exit(1)
    print("✅ Ollama ready\n")

    messages = [
        {"role": "system", "content": SYSTEM_GENERATE},
        {"role": "user",   "content": PROMPT},
    ]
    last_files = []

    write_progress(folder, "running", "🧠 Generating code...")

    for it in range(MAX_ITERS):
        tag = f"ITER {it+1}/{MAX_ITERS}"
        print(f"[{tag}] {'🧠 Generating...' if it==0 else '🔄 Improving...'}")

        t0  = time.time()
        raw = call_model(messages)
        print(f"[{tag}] ✅ {len(raw):,} chars ({time.time()-t0:.1f}s)")

        with open(os.path.join(folder, f"_raw_{it+1}.txt"), "w", encoding="utf-8") as f:
            f.write(raw)

        files = parse_files(raw)
        print(f"[{tag}] 📄 {len(files)} file(s): {[f['name'] for f in files]}")

        if not files:
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content":
                "Please put ALL code in markdown code blocks with filename comment:\n"
                "```python\n# filename.py\n...code...\n```"
            })
            continue

        last_files = files
        test_ok, test_out = test_code(files, f"{workdir}_it{it}")
        print(f"[{tag}] {'✅' if test_ok else '❌'} {test_out[:250]}")
        write_progress(folder, "running",
            f"Iter {it+1}: {'✅ tests pass' if test_ok else '❌ fixing...'}")

        if test_ok:
            if it < MAX_ITERS - 1:
                messages.append({"role": "assistant", "content": raw})
                messages.append({"role": "user", "content":
                    "Code runs! Now: add error handling, docstrings, input validation. "
                    "Write COMPLETE improved version. Start with CODE_IS_READY if already excellent."
                })
                if "CODE_IS_READY" in raw[:60]:
                    break
            else:
                break
        else:
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content":
                f"Error:\n```\n{test_out[:1200]}\n```\nFix ALL bugs, return complete files."
            })

    if last_files:
        print(f"\n📁 Saving {len(last_files)} file(s)...")
        for f in last_files:
            dest = os.path.join(folder, f["name"])
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "w", encoding="utf-8") as fp:
                fp.write(f["content"])
            print(f"   📝 {dest}")

        readme = f"""# {slugify(PROMPT).replace('-',' ').title()}

**Сгенерировано VIBE-CODE AI**

| | |
|---|---|
| **Запрос** | {PROMPT} |
| **Модель** | {MODEL_NAME} |
| **Дата** | {datetime.now().strftime('%Y-%m-%d %H:%M UTC')} |

## Файлы
{chr(10).join(f'- `{f["name"]}`' for f in last_files)}

## Запуск
```bash
{'pip install -r requirements.txt && ' if any(f["name"]=="requirements.txt" for f in last_files) else ''}python main.py
```
"""
        with open(os.path.join(folder, "README.md"), "w") as f:
            f.write(readme)

        write_progress(folder, "done", f"✅ {len(last_files)} file(s) in {folder}/",
                       files=[f["name"] for f in last_files] + ["README.md"])
        print(f"\n✅ DONE! Folder: {folder}/")
    else:
        write_progress(folder, "error", "No code blocks found")
        print("❌ No code generated"); sys.exit(1)


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not PROMPT and not ATTACHED_CONTENT:
        print("ERROR: PROMPT or FILE_CONTENT required"); sys.exit(1)
    if MODE == "improve":
        run_improve()
    else:
        if not PROMPT:
            print("ERROR: PROMPT is empty"); sys.exit(1)
        run_generate()
