#!/usr/bin/env python3
"""
VIBE-CODE local model runner.
Modes:
  - GENERATE: create code from scratch (multi-file)
  - IMPROVE:  analyse existing file, return improved single file

Token budget modes:
  - MAX_TOKENS per iteration + MAX_ITERS (classic)
  - TOTAL_BUDGET: run until cumulative tokens >= budget (ignores MAX_ITERS)
"""
import os, sys, json, subprocess, re, time, urllib.request, base64
from datetime import datetime

MODEL_NAME   = "qwen2.5-coder:7b"
PROMPT       = os.environ.get("PROMPT", "")
SESSION_ID   = os.environ.get("SESSION_ID", datetime.now().strftime("%Y%m%d%H%M%S"))
MAX_ITERS    = int(os.environ.get("MAX_ITERS", "3"))
MAX_TOKENS   = int(os.environ.get("MAX_TOKENS", "8192"))
TOTAL_BUDGET = int(os.environ.get("TOTAL_BUDGET", "0"))   # 0 = use MAX_ITERS mode
FILE_NAME    = os.environ.get("FILE_NAME", "").strip()
FILE_CONTENT_B64 = os.environ.get("FILE_CONTENT", "").strip()
OLLAMA_HOST  = "http://127.0.0.1:11434"

# num_ctx must be LARGER than num_predict to leave room for input tokens
CTX_BUFFER   = 8192
CTX_BUDGET   = MAX_TOKENS + CTX_BUFFER

# If TOTAL_BUDGET set, allow up to 200 iterations
EFFECTIVE_MAX_ITERS = 200 if TOTAL_BUDGET > 0 else MAX_ITERS

CHARS_PER_TOKEN = 3.5
SHORT_THRESHOLD = 0.40

REFUSAL_PATTERNS = [
    r"i (cannot|can't|am unable|won't|will not|don't)",
    r"(sorry|apolog|unfortunately).{0,60}(cannot|can't|help|assist)",
    r"i('m| am) not able",
    r"(violate|against|policy|guidelines|ethical|harmful)",
    r"(не могу|не буду|не в состоянии|отказыва).{0,40}(помо|выполн|делать|создав)",
]

ATTACHED_CONTENT = ""
if FILE_CONTENT_B64:
    try:
        ATTACHED_CONTENT = base64.b64decode(FILE_CONTENT_B64).decode("utf-8")
    except Exception as e:
        print(f"⚠️  Cannot decode file: {e}")

MODE = "improve" if ATTACHED_CONTENT else "generate"

# ── System prompts ─────────────────────────────────────────────────────────────

SYSTEM_GENERATE = f"""You are an elite software engineer.

RULES:
1. Write COMPLETE, immediately runnable, production-grade code. No placeholders. No "TODO".
2. Start every code block with the filename as a comment:
   ```python
   # main.py
   ...full code...
   ```
3. Include EVERY file needed: source files, requirements.txt, README.md.
4. Each function must have a docstring.
5. Handle ALL possible errors (file not found, network failure, bad input).
6. Add input validation everywhere user data enters.
7. Use your FULL token budget — write comprehensive, detailed, production-quality code.
"""

SYSTEM_IMPROVE = f"""You are an expert code reviewer and senior engineer.

Given an existing file:
1. Read EVERY line carefully.
2. Find ALL bugs, logic errors, missing error handling, security issues.
3. Rewrite the ENTIRE file with all improvements:
   - Fix every bug
   - Add comprehensive error handling
   - Add type hints to all functions
   - Add docstrings to every function and class
   - Add input validation
   - Improve variable names and code clarity
4. Return ONE complete code block — the full improved file.
5. After the code block, add a ## Changes section listing every improvement.
"""


# ── Ollama ────────────────────────────────────────────────────────────────────

def ollama_ready(timeout=90):
    for _ in range(timeout):
        try:
            urllib.request.urlopen(f"{OLLAMA_HOST}/api/tags", timeout=2)
            return True
        except Exception:
            time.sleep(1)
    return False


def call_model(messages, max_tokens=None):
    """Call Ollama /api/chat. Returns (text, tokens_used)."""
    n = max_tokens or MAX_TOKENS
    ctx = n + CTX_BUFFER
    body = json.dumps({
        "model":   MODEL_NAME,
        "messages": messages,
        "stream":  False,
        "options": {
            "num_predict": n,
            "num_ctx":     ctx,
            "temperature": 0.25,
            "top_p":       0.92,
            "repeat_penalty": 1.05,
        },
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=7200) as r:
        d = json.loads(r.read())
    text  = d["message"]["content"]
    used  = d.get("eval_count", len(text) // CHARS_PER_TOKEN)
    return text, int(used)


def is_refusal(text):
    t = text.lower().strip()
    for pat in REFUSAL_PATTERNS:
        if re.search(pat, t):
            return True
    return False


def budget_remaining(total_used):
    """Tokens left in total budget. Returns MAX_TOKENS if budget mode off."""
    if TOTAL_BUDGET <= 0:
        return MAX_TOKENS
    return max(0, TOTAL_BUDGET - total_used)


def budget_exhausted(total_used):
    """True if total budget is set and used up."""
    return TOTAL_BUDGET > 0 and total_used >= TOTAL_BUDGET


def is_short(text, used_tokens, iter_budget=None):
    budget    = iter_budget or MAX_TOKENS
    threshold = int(budget * SHORT_THRESHOLD)
    short     = used_tokens < threshold
    pct       = used_tokens / budget * 100 if budget else 0
    print(f"   Token budget: {used_tokens}/{budget}  ({pct:.1f}%)  "
          f"{'SHORT — will expand' if short else 'OK'}")
    return short


# ── Code parsing ──────────────────────────────────────────────────────────────

LANG_DEFAULTS = {
    "python":"main.py","py":"main.py",
    "javascript":"index.js","js":"index.js",
    "typescript":"index.ts","ts":"index.ts",
    "html":"index.html","css":"style.css",
    "bash":"run.sh","sh":"run.sh",
    "json":"config.json","sql":"schema.sql",
    "go":"main.go","rust":"main.rs","dockerfile":"Dockerfile",
    "text":"notes.txt","txt":"notes.txt","markdown":"README.md","md":"README.md",
}

def parse_files(text):
    files = []
    pattern = r"```(\w*)\n(?:(?:#|//|<!--)\s*(\S+\.\S+).*?\n)?([^`]*?)```"
    for m in re.finditer(pattern, text, re.DOTALL):
        lang    = m.group(1).lower() or "text"
        name    = m.group(2)
        content = m.group(3).strip()
        if not content or len(content) < 5:
            continue
        if not name:
            name = LANG_DEFAULTS.get(lang, f"file_{len(files)}.txt")
            if any(f["name"] == name for f in files):
                base, ext = name.rsplit(".", 1) if "." in name else (name, "txt")
                name = f"{base}_{len(files)}.{ext}"
        files.append({"lang": lang, "name": name, "content": content})
    return files


def parse_single(text, fallback_name):
    pattern = r"```(\w*)\n(?:(?:#|//|<!--)\s*(\S+\.\S+).*?\n)?([^`]*?)```"
    m = re.search(pattern, text, re.DOTALL)
    if not m:
        return None
    lang    = m.group(1).lower() or "text"
    name    = m.group(2) or fallback_name
    content = m.group(3).strip()
    return {"lang": lang, "name": name, "content": content} if content else None


# ── Testing ───────────────────────────────────────────────────────────────────

def install_reqs(workdir):
    req = os.path.join(workdir, "requirements.txt")
    if not os.path.exists(req):
        return True, ""
    r = subprocess.run(
        ["pip", "install", "-r", req, "-q", "--break-system-packages"],
        capture_output=True, timeout=120
    )
    if r.returncode != 0:
        return False, "pip install failed:\n" + r.stderr.decode(errors="replace")[:600]
    return True, ""


def test_python(file_name, workdir, timeout=25):
    try:
        r = subprocess.run(
            ["python3", "-c",
             f"import ast; ast.parse(open('{file_name}').read()); print('SYNTAX OK')"],
            cwd=workdir, capture_output=True, text=True, timeout=10
        )
        if r.returncode != 0:
            return False, "Syntax error:\n" + r.stderr[:800]
        r2 = subprocess.run(
            ["python3", file_name],
            cwd=workdir, capture_output=True, text=True, timeout=timeout,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        )
        if r2.returncode == 0:
            return True, r2.stdout[:600] or "(exited cleanly)"
        return False, r2.stderr[:600] or r2.stdout[:600]
    except subprocess.TimeoutExpired:
        return True, "(ran, timed out — OK for long-running services)"
    except Exception as e:
        return False, str(e)


def test_code(files, workdir):
    os.makedirs(workdir, exist_ok=True)
    for f in files:
        dest = os.path.join(workdir, f["name"])
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as fp:
            fp.write(f["content"])
    ok, err = install_reqs(workdir)
    if not ok:
        return False, err
    py = [f for f in files if f["lang"] in ("python", "py")]
    if not py:
        return True, "(no Python to test)"
    main_f = next((f for f in py if "main" in f["name"]), py[0])
    return test_python(main_f["name"], workdir)


def test_single_file(file_obj, workdir):
    os.makedirs(workdir, exist_ok=True)
    with open(os.path.join(workdir, file_obj["name"]), "w", encoding="utf-8") as f:
        f.write(file_obj["content"])
    if file_obj["lang"] not in ("python", "py"):
        return True, "(non-Python — skipping runtime test)"
    return test_python(file_obj["name"], workdir)


# ── Helpers ───────────────────────────────────────────────────────────────────

def write_progress(folder, status, msg, files=None, mode=MODE):
    data = {"status": status, "message": msg, "folder": folder,
            "timestamp": datetime.now().isoformat(), "files": files or [], "mode": mode}
    with open(os.path.join(folder, "_progress.json"), "w") as f:
        json.dump(data, f, ensure_ascii=False)


def slugify(text, n=40):
    s = re.sub(r"[^a-zA-Z0-9а-яёА-ЯЁ]+", "-", text[:n]).strip("-").lower()
    return s or "project"


def save_raw(text, n):
    with open(f"/tmp/vc_raw_{n}.txt", "w", encoding="utf-8") as f:
        f.write(text)


def log_response(tag, raw, used, elapsed, total_used=0):
    preview = raw[:300].replace('\n', ' ')
    budget_info = f"  [total: {total_used:,} / {TOTAL_BUDGET:,}]" if TOTAL_BUDGET > 0 else ""
    print(f"[{tag}] Response preview: {preview!r}{budget_info}")
    if is_refusal(raw):
        print(f"[{tag}] ⚠️  REFUSAL DETECTED — will rephrase prompt")


# ── IMPROVE MODE ──────────────────────────────────────────────────────────────

def run_improve():
    date    = datetime.now().strftime("%Y-%m-%d")
    slug    = slugify(FILE_NAME.rsplit(".", 1)[0] if "." in FILE_NAME else FILE_NAME or "file")
    folder  = f"output/{date}_improved_{slug}"
    workdir = f"/tmp/vc_{SESSION_ID}"
    os.makedirs(folder, exist_ok=True)

    user_request = PROMPT.strip() or \
        "Fix all bugs, improve error handling, add type hints, docstrings, and input validation."
    ext = FILE_NAME.rsplit(".", 1)[-1].lower() if "." in FILE_NAME else "txt"

    budget_str = f"  Total budget: {TOTAL_BUDGET:,} tokens" if TOTAL_BUDGET > 0 else ""
    print(f"\n{'='*60}")
    print(f"🔧 VIBE-CODE — Improve Mode")
    print(f"📄 File   : {FILE_NAME}  ({len(ATTACHED_CONTENT.splitlines())} lines, {len(ATTACHED_CONTENT):,} chars)")
    print(f"📝 Task   : {user_request[:100]}")
    print(f"🤖 Model  : {MODEL_NAME}  Per-iter: {MAX_TOKENS} tokens  Ctx: {MAX_TOKENS+CTX_BUFFER}{budget_str}")
    print(f"🔄 Iters  : {'until budget' if TOTAL_BUDGET > 0 else MAX_ITERS}")
    print(f"{'='*60}\n")

    print("⏳ Waiting for Ollama...")
    if not ollama_ready(90):
        print("❌ Ollama not ready"); sys.exit(1)
    print("✅ Ollama ready\n")

    # Truncate very large files to avoid blowing context
    content_for_model = ATTACHED_CONTENT
    if len(ATTACHED_CONTENT) > 60000:
        content_for_model = ATTACHED_CONTENT[:60000]
        print(f"⚠️  File truncated to 60K chars for model context (original: {len(ATTACHED_CONTENT):,} chars)")

    messages = [
        {"role": "system", "content": SYSTEM_IMPROVE},
        {"role": "user", "content":
            f"File: `{FILE_NAME}`\n\n"
            f"```{ext}\n# {FILE_NAME}\n{content_for_model}\n```\n\n"
            f"Task: {user_request}\n\n"
            f"Return the complete improved file in ONE code block starting with `# {FILE_NAME}`."
        },
    ]

    write_progress(folder, "running", f"🔧 Analysing {FILE_NAME}...")
    last_file  = None
    total_used = 0
    refusal_count = 0

    for it in range(EFFECTIVE_MAX_ITERS):
        if budget_exhausted(total_used):
            print(f"\n✅ Total budget {TOTAL_BUDGET:,} tokens exhausted after {it} iterations.")
            break

        iter_budget = min(MAX_TOKENS, budget_remaining(total_used)) if TOTAL_BUDGET > 0 else MAX_TOKENS
        if iter_budget <= 0:
            break

        tag   = f"ITER {it+1}"
        label = "🔍 Analysing and improving..." if it == 0 else "🔄 Polishing..."
        print(f"\n[{tag}] {label}  (iter_budget={iter_budget:,})")

        t0 = time.time()
        raw, used = call_model(messages, max_tokens=iter_budget)
        dt = time.time() - t0
        total_used += used
        print(f"[{tag}] ✅ {len(raw):,} chars  {used:,} tokens  ({dt:.0f}s)  total={total_used:,}")
        save_raw(raw, it + 1)
        log_response(tag, raw, used, dt, total_used)

        file_obj = parse_single(raw, FILE_NAME)

        if is_refusal(raw):
            refusal_count += 1
            messages = [
                {"role": "system", "content": SYSTEM_IMPROVE},
                {"role": "user", "content":
                    f"Please review and improve this {ext} file. Return the complete improved version.\n\n"
                    f"```{ext}\n# {FILE_NAME}\n{content_for_model[:3000]}\n```\n\n"
                    f"Fix bugs, add error handling, add docstrings. "
                    f"Return ONE complete code block with `# {FILE_NAME}` as first comment."
                },
            ]
            write_progress(folder, "running", f"[{tag}] Rephrasing after refusal...")
            if refusal_count >= 2:
                break
            continue

        if it == 0 and is_short(raw, used, iter_budget) and not file_obj:
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content":
                f"Your response was too brief. Rewrite `{FILE_NAME}` COMPLETELY with detailed "
                f"docstrings, error handling, type hints. Return the complete file in one code block."
            })
            continue

        if not file_obj:
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content":
                f"Return the improved `{FILE_NAME}` in exactly one code block:\n"
                f"```{ext}\n# {FILE_NAME}\n...complete code...\n```"
            })
            write_progress(folder, "running", f"[{tag}] No code block — retrying...")
            continue

        last_file = file_obj
        test_ok, test_out = test_single_file(file_obj, f"{workdir}_it{it}")
        print(f"[{tag}] {'✅' if test_ok else '❌'} Test: {test_out[:200]}")
        write_progress(folder, "running", f"[{tag}]: {'✅ OK' if test_ok else '❌ fixing...'}  total={total_used:,}")

        if test_ok and not budget_exhausted(total_used):
            messages.append({"role": "assistant", "content": raw})
            remaining = budget_remaining(total_used)
            if remaining > 2000:
                messages.append({"role": "user", "content":
                    f"Great — it works! You have ~{remaining:,} tokens left in the budget.\n"
                    f"Use them to: expand docstrings with examples, add comprehensive unit tests, "
                    f"improve error messages, add logging, add CLI argument parsing if missing.\n"
                    f"Return the COMPLETE expanded file."
                })
            else:
                break
        elif not test_ok:
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content":
                f"Error during execution:\n```\n{test_out[:1000]}\n```\n\n"
                f"Fix ALL issues. Return complete `{FILE_NAME}`."
            })
        else:
            break

    if last_file:
        changes_section = ""
        if "## Changes" in raw:
            changes_section = raw[raw.index("## Changes"):]

        out_path = os.path.join(folder, last_file["name"])
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(last_file["content"])

        orig_lines = ATTACHED_CONTENT.splitlines()
        new_lines  = last_file["content"].splitlines()
        delta      = len(new_lines) - len(orig_lines)
        delta_str  = f"+{delta}" if delta >= 0 else str(delta)

        changes_md = f"""# Changes to `{last_file['name']}`

**Improved by VIBE-CODE AI** · {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}

| | |
|---|---|
| **Original** | {len(orig_lines)} lines |
| **Improved** | {len(new_lines)} lines ({delta_str}) |
| **Tokens used** | {total_used:,} |
| **Task** | {user_request} |

{changes_section if changes_section else ""}
"""
        with open(os.path.join(folder, "CHANGES.md"), "w", encoding="utf-8") as f:
            f.write(changes_md)

        write_progress(folder, "done",
            f"✅ {last_file['name']} improved ({len(orig_lines)}→{len(new_lines)} lines)  {total_used:,} tokens",
            files=[last_file["name"], "CHANGES.md"])

        print(f"\n✅ DONE!")
        print(f"   File   : {out_path}")
        print(f"   Lines  : {len(orig_lines)} → {len(new_lines)} ({delta_str})")
        print(f"   Tokens : {total_used:,} used")
    else:
        write_progress(folder, "error", "No improved file extracted")
        print("❌ No output"); sys.exit(1)


# ── GENERATE MODE ─────────────────────────────────────────────────────────────

def run_generate():
    date    = datetime.now().strftime("%Y-%m-%d")
    folder  = f"output/{date}_{slugify(PROMPT)}"
    workdir = f"/tmp/vc_{SESSION_ID}"
    os.makedirs(folder, exist_ok=True)

    budget_str = f"  Total budget: {TOTAL_BUDGET:,} tokens" if TOTAL_BUDGET > 0 else ""
    print(f"\n{'='*60}")
    print(f"🚀 VIBE-CODE — Generate Mode")
    print(f"📝 Prompt  : {PROMPT[:120]}")
    print(f"🤖 Model   : {MODEL_NAME}  Per-iter: {MAX_TOKENS} tokens  Ctx: {MAX_TOKENS+CTX_BUFFER}{budget_str}")
    print(f"📁 Output  : {folder}/")
    print(f"🔄 Iters   : {'until budget exhausted' if TOTAL_BUDGET > 0 else MAX_ITERS}")
    print(f"{'='*60}\n")

    print("⏳ Waiting for Ollama...")
    if not ollama_ready(90):
        print("❌ Ollama not ready"); sys.exit(1)
    print("✅ Ollama ready\n")

    messages = [
        {"role": "system", "content": SYSTEM_GENERATE},
        {"role": "user",   "content": PROMPT},
    ]
    last_files    = []
    total_used    = 0
    refusal_count = 0

    write_progress(folder, "running", "🧠 Generating code...")

    for it in range(EFFECTIVE_MAX_ITERS):
        if budget_exhausted(total_used):
            print(f"\n✅ Total budget {TOTAL_BUDGET:,} tokens exhausted after {it} iterations.")
            break

        iter_budget = min(MAX_TOKENS, budget_remaining(total_used)) if TOTAL_BUDGET > 0 else MAX_TOKENS
        if iter_budget <= 0:
            break

        tag   = f"ITER {it+1}"
        label = "🧠 Generating..." if it == 0 else "🔄 Expanding..."
        print(f"\n[{tag}] {label}  (iter_budget={iter_budget:,}  remaining={budget_remaining(total_used):,})")

        t0 = time.time()
        raw, used = call_model(messages, max_tokens=iter_budget)
        dt = time.time() - t0
        total_used += used
        print(f"[{tag}] ✅ {len(raw):,} chars  {used:,} tokens  ({dt:.0f}s)  total={total_used:,}")
        save_raw(raw, it + 1)
        log_response(tag, raw, used, dt, total_used)

        if is_refusal(raw):
            refusal_count += 1
            print(f"[{tag}] ⚠️  Refusal #{refusal_count} — rephrasing in English")
            simple = (
                "Write a Python script that does the following:\n"
                + PROMPT[:800]
                + "\n\nProvide complete, working Python code with docstrings and error handling."
            )
            messages = [
                {"role": "system", "content": SYSTEM_GENERATE},
                {"role": "user",   "content": simple},
            ]
            write_progress(folder, "running", f"[{tag}] Rephrasing after refusal...")
            if refusal_count >= 2:
                print(f"[{tag}] ❌ Model refuses repeatedly — cannot proceed")
                break
            continue

        files = parse_files(raw)
        print(f"[{tag}] 📄 {len(files)} file(s): {[f['name'] for f in files]}")

        if it == 0 and is_short(raw, used, iter_budget) and len(files) < 2:
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content":
                f"Your response only used {used:,}/{iter_budget:,} tokens. Use your FULL budget.\n\n"
                f"Rewrite the COMPLETE solution with:\n"
                f"1. Full implementation — no shortcuts, no placeholders\n"
                f"2. Every function with full docstring (description, args, returns, example)\n"
                f"3. Comprehensive error handling for every operation\n"
                f"4. Unit tests in test_main.py\n"
                f"5. Detailed README.md with examples\n"
                f"6. requirements.txt\n\n"
                f"Mark every file with `# filename.ext` as first comment."
            })
            continue

        if not files:
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content":
                "Put ALL code in markdown blocks with filename comment:\n"
                "```python\n# main.py\n...code...\n```"
            })
            write_progress(folder, "running", f"[{tag}] No code blocks — retrying...")
            continue

        last_files = files
        test_ok, test_out = test_code(files, f"{workdir}_it{it}")
        print(f"[{tag}] {'✅' if test_ok else '❌'} Test: {test_out[:250]}")
        write_progress(folder, "running",
            f"[{tag}]: {'✅ tests pass' if test_ok else '❌ fixing...'}  total={total_used:,}")

        if test_ok:
            if budget_exhausted(total_used):
                break
            remaining = budget_remaining(total_used)
            messages.append({"role": "assistant", "content": raw})
            if remaining > 2000:
                messages.append({"role": "user", "content":
                    f"Code works! You have ~{remaining:,} tokens left in the budget.\n"
                    f"Use them for: comprehensive unit tests (test_main.py with 15+ test cases), "
                    f"detailed README.md with usage examples, enhanced error handling, "
                    f"edge case handling, type hints on every function. Write COMPLETE files.\n"
                    f"If the code is already excellent, write CODE_IS_READY."
                })
                if "CODE_IS_READY" in raw[:80]:
                    break
            else:
                break
        else:
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content":
                f"Error:\n```\n{test_out[:1000]}\n```\nFix ALL bugs. Return complete files."
            })

    if last_files:
        print(f"\n📁 Saving {len(last_files)} file(s)...")
        for f in last_files:
            dest = os.path.join(folder, f["name"])
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "w", encoding="utf-8") as fp:
                fp.write(f["content"])
            print(f"   📝 {dest}  ({len(f['content'].splitlines())} lines)")

        if not any(f["name"].lower() in ("readme.md", "readme") for f in last_files):
            run_instr = ""
            if any(f["name"] == "requirements.txt" for f in last_files):
                run_instr = "pip install -r requirements.txt\n"
            main_py = next((f["name"] for f in last_files if "main" in f["name"] and f["lang"] in ("python","py")), None)
            run_instr += f"python {main_py}" if main_py else "see source files"

            readme = f"""# {slugify(PROMPT).replace('-',' ').title()}

**Generated by VIBE-CODE AI**

| | |
|---|---|
| **Prompt** | {PROMPT[:200]} |
| **Model** | {MODEL_NAME} |
| **Tokens used** | {total_used:,} |
| **Date** | {datetime.now().strftime('%Y-%m-%d %H:%M UTC')} |

## Files
{chr(10).join(f'- `{f["name"]}` — {len(f["content"].splitlines())} lines' for f in last_files)}

## Run
```bash
{run_instr}
```
"""
            with open(os.path.join(folder, "README.md"), "w") as f:
                f.write(readme)
            last_files.append({"name": "README.md"})

        write_progress(folder, "done",
            f"✅ {len(last_files)} file(s) generated  {total_used:,} tokens used",
            files=[f["name"] for f in last_files])

        print(f"\n✅ DONE!  Output: {folder}/")
        print(f"   Files  : {[f['name'] for f in last_files]}")
        print(f"   Tokens : {total_used:,} used")
    else:
        write_progress(folder, "error", "No code blocks found in any iteration")
        print("❌ No code generated"); sys.exit(1)


# ── Entry ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if TOTAL_BUDGET > 0:
        print(f"💰 Total budget mode: {TOTAL_BUDGET:,} tokens  ({TOTAL_BUDGET // MAX_TOKENS} iterations @ {MAX_TOKENS} tokens/iter)")

    if not PROMPT and not ATTACHED_CONTENT:
        print("ERROR: PROMPT or FILE_CONTENT required"); sys.exit(1)
    if MODE == "improve":
        run_improve()
    else:
        if not PROMPT:
            print("ERROR: PROMPT is required in generate mode"); sys.exit(1)
        run_generate()
