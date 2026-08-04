"""
VIBE-CODE v2 — Multi-Agent Local LLM Code Platform
Agents: Qwen 2.5 (Planner/Architect) + Prism Bonsai 27B (Coder/Executor)
"""
import os, sys, json, re, time, datetime, base64, urllib.request, urllib.error
from enum import Enum
from typing import Optional

# ── Config ────────────────────────────────────────────────────────────────────
MODEL_PLANNER  = os.getenv("MODEL_PLANNER",  "qwen2.5:7b")      # Architect
MODEL_CODER    = os.getenv("MODEL_CODER",    "bonsai-27b")       # Executor
MODEL_SINGLE   = os.getenv("MODEL_SINGLE",   "qwen2.5-coder:7b") # Legacy single-agent
OLLAMA_HOST    = os.getenv("OLLAMA_HOST",    "http://127.0.0.1:11434")

AGENT_MODE     = os.getenv("AGENT_MODE",    "single")   # single | multi
TARGET_REPO    = os.getenv("TARGET_REPO",   "")         # owner/repo
GH_TOKEN       = os.getenv("GH_TOKEN",      "")
AUTO_PR        = os.getenv("AUTO_PR",       "false").lower() == "true"
AUTO_NOTES     = os.getenv("AUTO_NOTES",    "true").lower()  == "true"

PROMPT         = os.getenv("PROMPT",        "")
FILE_NAME      = os.getenv("FILE_NAME",     "")
MODE           = os.getenv("MODE",          "generate")  # generate | improve
MAX_TOKENS     = int(os.getenv("MAX_TOKENS", "4096"))
CTX_BUFFER     = int(os.getenv("CTX_BUFFER", "512"))
ITERATIONS     = int(os.getenv("ITERATIONS", "1"))
TOTAL_BUDGET   = int(os.getenv("TOTAL_BUDGET", "0"))
CONCURRENCY    = int(os.getenv("CONCURRENCY", "1"))

ATTACHED_CONTENT = ""
if os.path.exists("/tmp/attached_file"):
    with open("/tmp/attached_file") as f:
        ATTACHED_CONTENT = f.read()

REPO_CONTEXT = ""
if os.path.exists("/tmp/repo_context.b64"):
    try:
        with open("/tmp/repo_context.b64") as f:
            REPO_CONTEXT = base64.b64decode(f.read().strip()).decode("utf-8", errors="replace")
    except Exception:
        pass

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/tmp/vibe_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)
PROGRESS_FILE = f"{OUTPUT_DIR}/_progress.json"

# ── Progress ──────────────────────────────────────────────────────────────────
def write_progress(status: str, message: str, tokens_used: int = 0,
                   agent: str = "", extra: dict = None):
    data = {
        "status":      status,
        "message":     message,
        "tokensUsed":  tokens_used,
        "agent":       agent,
        "timestamp":   datetime.datetime.utcnow().isoformat(),
    }
    if extra:
        data.update(extra)
    with open(PROGRESS_FILE, "w") as f:
        json.dump(data, f)
    print(f"[{agent or status}] {message}", flush=True)

# ── Ollama helpers ─────────────────────────────────────────────────────────────
def ollama_ready(timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"{OLLAMA_HOST}/api/tags", timeout=2)
            return True
        except Exception:
            time.sleep(2)
    return False

def call_model(messages: list, model: str = None, max_tokens: int = None) -> tuple[str, int]:
    """Call Ollama /api/chat. Returns (text, tokens_used)."""
    if model is None:
        model = MODEL_SINGLE
    payload = json.dumps({
        "model":   model,
        "messages": messages,
        "stream":  False,
        "options": {
            "num_predict": max_tokens or MAX_TOKENS,
            "temperature": 0.3,
            "top_p": 0.9,
        }
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=600) as r:
        resp = json.loads(r.read())
    text = resp.get("message", {}).get("content", "")
    tokens = resp.get("eval_count", 0) + resp.get("prompt_eval_count", 0)
    return text, tokens

# ── Agent state ────────────────────────────────────────────────────────────────
class AgentState(Enum):
    IDLE      = "idle"
    PLANNING  = "planning"
    CODING    = "coding"
    REVIEWING = "reviewing"
    COMMITTING= "committing"
    RELEASING = "releasing"
    DONE      = "done"

# ── Git Integration ────────────────────────────────────────────────────────────
class GitIntegration:
    """GitHub API wrapper — reads repo context, creates commits and PRs."""

    def __init__(self, repo: str, token: str):
        self.repo  = repo
        self.token = token
        self.base  = "https://api.github.com"

    def _req(self, path: str, method: str = "GET", data: dict = None):
        url = f"{self.base}{path}"
        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(
            url, data=body,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept":        "application/vnd.github.v3+json",
                "Content-Type":  "application/json",
                "User-Agent":    "vibe-code/2.0",
            },
            method=method
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            return {"error": e.reason, "code": e.code}

    def get_repo_tree(self, max_files: int = 60) -> list[dict]:
        resp = self._req(f"/repos/{self.repo}/git/trees/HEAD?recursive=1")
        tree = resp.get("tree", [])
        code_exts = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs",
                     ".java", ".cpp", ".c", ".cs", ".rb", ".php", ".swift",
                     ".kt", ".yml", ".yaml", ".json", ".md", ".sh"}
        files = [f for f in tree if f.get("type") == "blob"
                 and any(f["path"].endswith(e) for e in code_exts)]
        return files[:max_files]

    def get_file(self, path: str) -> str:
        resp = self._req(f"/repos/{self.repo}/contents/{path}")
        if "content" in resp:
            return base64.b64decode(resp["content"]).decode("utf-8", errors="replace")
        return ""

    def get_repo_context(self, max_chars: int = 60_000) -> str:
        """Fetch top files and build context string for LLM injection."""
        files = self.get_repo_tree(max_files=40)
        context_parts = [f"# Repository: {self.repo}\n"]
        total = 0
        for f in files:
            if total >= max_chars:
                break
            content = self.get_file(f["path"])
            snippet = content[:3000]
            chunk = f"\n## {f['path']}\n```\n{snippet}\n```\n"
            context_parts.append(chunk)
            total += len(chunk)
        return "".join(context_parts)

    def get_default_branch(self) -> str:
        resp = self._req(f"/repos/{self.repo}")
        return resp.get("default_branch", "main")

    def get_branch_sha(self, branch: str) -> str:
        resp = self._req(f"/repos/{self.repo}/git/ref/heads/{branch}")
        return resp.get("object", {}).get("sha", "")

    def create_branch(self, branch_name: str) -> bool:
        default = self.get_default_branch()
        sha = self.get_branch_sha(default)
        if not sha:
            return False
        resp = self._req(f"/repos/{self.repo}/git/refs", "POST", {
            "ref": f"refs/heads/{branch_name}",
            "sha": sha
        })
        return "ref" in resp

    def get_file_sha(self, path: str, branch: str) -> Optional[str]:
        resp = self._req(f"/repos/{self.repo}/contents/{path}?ref={branch}")
        return resp.get("sha")

    def commit_file(self, path: str, content: str, message: str,
                    branch: str) -> bool:
        sha = self.get_file_sha(path, branch)
        data = {
            "message": message,
            "content": base64.b64encode(content.encode()).decode(),
            "branch":  branch,
        }
        if sha:
            data["sha"] = sha
        resp = self._req(f"/repos/{self.repo}/contents/{path}", "PUT", data)
        return "commit" in resp

    def commit_files(self, files: dict, message: str,
                     branch: str = "vibe-code/auto") -> list[str]:
        """Commit multiple files. files = {path: content}"""
        self.create_branch(branch)
        committed = []
        for path, content in files.items():
            ok = self.commit_file(path, content, f"feat: {message} [{path}]", branch)
            if ok:
                committed.append(path)
        return committed

    def create_pr(self, branch: str, title: str, body: str) -> str:
        default = self.get_default_branch()
        resp = self._req(f"/repos/{self.repo}/pulls", "POST", {
            "title": title,
            "body":  body,
            "head":  branch,
            "base":  default,
        })
        return resp.get("html_url", "")

    def get_diff(self, branch: str) -> str:
        default = self.get_default_branch()
        resp = self._req(
            f"/repos/{self.repo}/compare/{default}...{branch}",
        )
        files = resp.get("files", [])
        diff_parts = []
        for f in files[:20]:
            diff_parts.append(f"### {f['filename']}\n```diff\n{f.get('patch','')}\n```")
        return "\n".join(diff_parts)

# ── Planner Agent (Qwen 2.5) ───────────────────────────────────────────────────
class PlannerAgent:
    """Decomposes task, analyzes architecture, writes execution plan."""

    SYSTEM = """You are a Senior Software Architect. Your role is to:
1. Analyze the codebase and understand the existing architecture
2. Decompose the user's task into concrete implementation steps
3. Identify which files need to be created or modified
4. Write a clear, actionable execution plan for the Coder agent

Output your plan as valid JSON with this structure:
{
  "summary": "One-line task summary",
  "files_to_read": ["path/to/file1", "path/to/file2"],
  "steps": [
    {
      "id": 1,
      "description": "What to do",
      "file": "path/to/target/file.py",
      "action": "create|modify|delete",
      "details": "Specific implementation notes"
    }
  ],
  "dependencies": ["package1", "package2"],
  "risks": ["potential issue 1"]
}"""

    def decompose(self, task: str, repo_ctx: str = "",
                  tokens_budget: int = 2048) -> dict:
        write_progress("running", "📐 Planner analyzing task...",
                       agent="planner")
        messages = [
            {"role": "system", "content": self.SYSTEM},
            {"role": "user",   "content": (
                f"TASK: {task}\n\n"
                + (f"REPOSITORY CONTEXT:\n{repo_ctx[:20000]}\n\n" if repo_ctx else "")
                + "Produce the JSON execution plan."
            )}
        ]
        raw, tokens = call_model(messages, MODEL_PLANNER, tokens_budget)
        # Extract JSON
        match = re.search(r'\{[\s\S]*\}', raw)
        if match:
            try:
                plan = json.loads(match.group())
                plan["_tokens"] = tokens
                return plan
            except json.JSONDecodeError:
                pass
        return {"summary": task, "steps": [{"id": 1, "description": task,
                "file": FILE_NAME or "output.py", "action": "create",
                "details": raw}], "_tokens": tokens, "_raw": raw}

    def review(self, original_task: str, code_results: dict,
               tokens_budget: int = 1024) -> dict:
        """Review coder's output and decide approve/revise."""
        write_progress("running", "🔍 Planner reviewing generated code...",
                       agent="planner")
        summary = json.dumps({k: v[:200] if isinstance(v, str) else v
                               for k, v in code_results.items()}, indent=2)
        messages = [
            {"role": "system", "content": (
                "You are a code reviewer. Evaluate if the code correctly solves "
                "the task. Reply with JSON: {\"approved\": true/false, "
                "\"feedback\": \"...\", \"score\": 0-10}"
            )},
            {"role": "user", "content":
                f"TASK: {original_task}\n\nCODE OUTPUT:\n{summary}"}
        ]
        raw, tokens = call_model(messages, MODEL_PLANNER, tokens_budget)
        match = re.search(r'\{[\s\S]*\}', raw)
        if match:
            try:
                result = json.loads(match.group())
                result["_tokens"] = tokens
                return result
            except json.JSONDecodeError:
                pass
        return {"approved": True, "feedback": raw, "score": 7, "_tokens": tokens}


# ── Coder Agent (Bonsai 27B) ───────────────────────────────────────────────────
class CoderAgent:
    """Writes code, fixes bugs, generates tests based on planner's instructions."""

    SYSTEM = """You are an expert software engineer. Your role is to:
1. Read the execution plan carefully
2. Write clean, production-ready code for each step
3. Follow existing code style and patterns from the repository
4. Include error handling and documentation

For each file, output:
```filename: path/to/file.ext
[complete file content here]
```

Write complete files, not fragments. Be precise and thorough."""

    def implement(self, plan: dict, repo_ctx: str = "",
                  feedback: str = "", tokens_budget: int = None) -> dict:
        write_progress("running",
                       f"⚡ Coder implementing: {plan.get('summary','...')}",
                       agent="coder")
        steps_txt = json.dumps(plan.get("steps", []), indent=2)
        user_msg = (
            f"EXECUTION PLAN:\n{steps_txt}\n\n"
            + (f"REPOSITORY CONTEXT:\n{repo_ctx[:25000]}\n\n" if repo_ctx else "")
            + (f"REVIEWER FEEDBACK (please fix):\n{feedback}\n\n" if feedback else "")
            + "Implement all steps. Output complete files using the ```filename: ... ``` format."
        )
        messages = [
            {"role": "system", "content": self.SYSTEM},
            {"role": "user",   "content": user_msg}
        ]
        raw, tokens = call_model(messages, MODEL_CODER,
                                 tokens_budget or MAX_TOKENS)

        # Parse files from response
        files = {}
        pattern = r'```(?:filename:\s*)?([^\n`]+)\n([\s\S]*?)```'
        for match in re.finditer(pattern, raw):
            fname_raw = match.group(1).strip()
            content   = match.group(2)
            # Normalize: strip "filename:" prefix if present
            if fname_raw.startswith("filename:"):
                fname_raw = fname_raw[9:].strip()
            files[fname_raw] = content

        if not files:
            # Fallback: treat entire response as single file
            fname = plan.get("steps", [{}])[0].get("file", FILE_NAME or "output.txt")
            files[fname] = raw

        return {"files": files, "_tokens": tokens, "_raw": raw}

    def refactor(self, files: dict, feedback: str,
                 tokens_budget: int = None) -> dict:
        write_progress("running", "🔧 Coder refactoring based on review...",
                       agent="coder")
        files_txt = "\n\n".join(
            f"```filename: {k}\n{v}\n```" for k, v in files.items()
        )
        messages = [
            {"role": "system", "content": self.SYSTEM},
            {"role": "user",   "content":
                f"REFACTOR REQUEST:\n{feedback}\n\nCURRENT CODE:\n{files_txt}\n\n"
                "Apply all requested changes and output the complete updated files."}
        ]
        raw, tokens = call_model(messages, MODEL_CODER,
                                 tokens_budget or MAX_TOKENS)
        files_out = {}
        for match in re.finditer(
            r'```(?:filename:\s*)?([^\n`]+)\n([\s\S]*?)```', raw
        ):
            fname = match.group(1).strip().lstrip("filename:").strip()
            files_out[fname] = match.group(2)
        if not files_out:
            files_out = files  # unchanged if parse failed
        return {"files": files_out, "_tokens": tokens}


# ── Release Notes Generator ────────────────────────────────────────────────────
class ReleaseNotesGenerator:
    """Generates human-readable changelogs from diff + chat context."""

    SYSTEM = """You are a technical writer specializing in release notes.
Generate clear, developer-friendly release notes from the provided diff and context.

Output format (Markdown):
## 🚀 What's New
- [feature descriptions]

## 🔧 Improvements
- [improvements]

## 🐛 Bug Fixes
- [fixes]

## ⚠️ Breaking Changes
- [if any, otherwise omit]

Keep each item concise (one line). Focus on user/developer impact, not implementation details."""

    def generate(self, diff: str, task: str, files_changed: list,
                 tokens_budget: int = 1024) -> str:
        write_progress("running", "📝 Generating release notes...",
                       agent="release-notes")
        messages = [
            {"role": "system", "content": self.SYSTEM},
            {"role": "user",   "content": (
                f"TASK DESCRIPTION:\n{task}\n\n"
                f"FILES CHANGED:\n" + "\n".join(f"- {f}" for f in files_changed)
                + (f"\n\nDIFF:\n{diff[:8000]}" if diff else "")
                + "\n\nGenerate the release notes."
            )}
        ]
        raw, _ = call_model(messages, MODEL_PLANNER, tokens_budget)
        return raw


# ── Orchestrator (Multi-Agent State Machine) ───────────────────────────────────
class Orchestrator:
    """
    State machine coordinating PlannerAgent ↔ CoderAgent.

    Flow:
      IDLE → PLANNING (Qwen 2.5 decomposes task)
           → CODING   (Bonsai 27B implements plan)
           → REVIEWING (Qwen 2.5 reviews, optionally loops back to CODING)
           → COMMITTING (push to GitHub branch)
           → RELEASING (generate release notes)
           → DONE
    """

    MAX_REVIEW_LOOPS = 2

    def __init__(self):
        self.state   = AgentState.IDLE
        self.planner = PlannerAgent()
        self.coder   = CoderAgent()
        self.relnotes= ReleaseNotesGenerator()
        self.git     = GitIntegration(TARGET_REPO, GH_TOKEN) \
                       if TARGET_REPO and GH_TOKEN else None
        self.total_tokens = 0

    def _transition(self, new_state: AgentState, msg: str):
        self.state = new_state
        write_progress(new_state.value, msg, self.total_tokens,
                       extra={"state": new_state.value})

    def run(self, task: str) -> dict:
        start_time = time.time()
        result = {"task": task, "files": {}, "pr_url": "", "release_notes": ""}

        # ── 1. Fetch repo context ──────────────────────────────────────────────
        repo_ctx = REPO_CONTEXT  # pre-loaded from /tmp/repo_context.b64
        if not repo_ctx and self.git:
            self._transition(AgentState.PLANNING,
                             "📡 Fetching repository context...")
            repo_ctx = self.git.get_repo_context()

        # ── 2. PLANNING ────────────────────────────────────────────────────────
        self._transition(AgentState.PLANNING,
                         f"📐 Planner decomposing: {task[:60]}...")
        budget_per_call = (TOTAL_BUDGET // 4) if TOTAL_BUDGET else MAX_TOKENS
        plan = self.planner.decompose(task, repo_ctx, budget_per_call)
        self.total_tokens += plan.get("_tokens", 0)
        write_progress("planning", f"✅ Plan ready: {len(plan.get('steps',[]))} steps",
                       self.total_tokens, "planner",
                       extra={"plan": plan.get("summary", "")})

        # ── 3. CODING ──────────────────────────────────────────────────────────
        self._transition(AgentState.CODING,
                         "⚡ Coder implementing plan...")
        code_budget = (TOTAL_BUDGET // 2) if TOTAL_BUDGET else MAX_TOKENS
        code_result = self.coder.implement(plan, repo_ctx, "", code_budget)
        self.total_tokens += code_result.get("_tokens", 0)
        files = code_result.get("files", {})

        # ── 4. REVIEW LOOP ─────────────────────────────────────────────────────
        for loop in range(self.MAX_REVIEW_LOOPS):
            self._transition(AgentState.REVIEWING,
                             f"🔍 Planner reviewing (pass {loop+1})...")
            review = self.planner.review(task, files, budget_per_call)
            self.total_tokens += review.get("_tokens", 0)

            if review.get("approved", True) or review.get("score", 10) >= 7:
                write_progress("reviewing",
                               f"✅ Code approved (score: {review.get('score','-')})",
                               self.total_tokens, "planner")
                break

            # Refactor if not approved
            self._transition(AgentState.CODING,
                             f"🔧 Coder refactoring (feedback: {review.get('feedback','')[:60]})")
            refactor = self.coder.refactor(files, review.get("feedback",""),
                                           code_budget)
            self.total_tokens += refactor.get("_tokens", 0)
            files = refactor.get("files", files)

        result["files"] = files

        # ── 5. COMMIT / PR ─────────────────────────────────────────────────────
        if self.git and (AUTO_PR or files):
            self._transition(AgentState.COMMITTING,
                             f"🚀 Committing {len(files)} file(s) to GitHub...")
            ts = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M")
            branch = f"vibe-code/{ts}"
            committed = self.git.commit_files(
                files, plan.get("summary", task), branch
            )
            write_progress("committing",
                           f"✅ Committed: {', '.join(committed[:3])}",
                           self.total_tokens, "git")

            if AUTO_PR and committed:
                pr_url = self.git.create_pr(
                    branch,
                    f"feat: {plan.get('summary', task)[:72]}",
                    f"Generated by VIBE-CODE Multi-Agent\n\n"
                    f"Task: {task}\n\nFiles: {', '.join(committed)}"
                )
                result["pr_url"] = pr_url
                write_progress("committing",
                               f"🔗 PR created: {pr_url}",
                               self.total_tokens, "git",
                               extra={"pr_url": pr_url})

            # Diff for release notes
            diff = self.git.get_diff(branch) if committed else ""
        else:
            diff = ""
            branch = None

        # ── 6. RELEASE NOTES ──────────────────────────────────────────────────
        if AUTO_NOTES:
            self._transition(AgentState.RELEASING,
                             "📝 Generating release notes...")
            notes = self.relnotes.generate(
                diff, task, list(files.keys()), 1024
            )
            result["release_notes"] = notes
            write_progress("releasing", "✅ Release notes ready",
                           self.total_tokens, "release-notes",
                           extra={"release_notes": notes})

        # ── 7. DONE ────────────────────────────────────────────────────────────
        elapsed = round(time.time() - start_time, 1)
        self._transition(AgentState.DONE,
                         f"🎉 Done in {elapsed}s | {self.total_tokens} tokens")
        result["elapsed"]      = elapsed
        result["total_tokens"] = self.total_tokens
        return result


# ── Save outputs ───────────────────────────────────────────────────────────────
def save_outputs(files: dict, release_notes: str = "", pr_url: str = ""):
    for fname, content in files.items():
        safe = fname.lstrip("/").replace("..", "__")
        out_path = os.path.join(OUTPUT_DIR, safe)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w") as f:
            f.write(content)
        print(f"📄 {out_path}")
    if release_notes:
        with open(f"{OUTPUT_DIR}/_release_notes.md", "w") as f:
            f.write(release_notes)
    if pr_url:
        with open(f"{OUTPUT_DIR}/_pr_url.txt", "w") as f:
            f.write(pr_url)

# ── Single-agent legacy path ───────────────────────────────────────────────────
def run_single_agent():
    """Original single-model flow preserved for backward compatibility."""
    print(f"🤖 Single-agent mode | Model: {MODEL_SINGLE}")
    print(f"📝 Task: {PROMPT}")

    if not ollama_ready(90):
        print("❌ Ollama not ready"); sys.exit(1)
    print("✅ Ollama ready")

    budget_left = TOTAL_BUDGET or (MAX_TOKENS * ITERATIONS)
    total_tokens = 0
    output_parts = []
    messages = [
        {"role": "system", "content":
         "You are an expert software engineer. Write complete, production-ready code."},
    ]

    if REPO_CONTEXT:
        messages[0]["content"] += f"\n\nREPO CONTEXT:\n{REPO_CONTEXT[:20000]}"

    user_msg = PROMPT
    if ATTACHED_CONTENT:
        ext = os.path.splitext(FILE_NAME)[1].lstrip(".") or "txt"
        user_msg = (f"```{ext}\n# {FILE_NAME}\n{ATTACHED_CONTENT[:60000]}\n```\n\n"
                    + PROMPT)

    messages.append({"role": "user", "content": user_msg})

    for i in range(max(1, ITERATIONS)):
        write_progress("running", f"🔄 Iteration {i+1}/{ITERATIONS}",
                       total_tokens)
        budget = min(MAX_TOKENS, budget_left)
        raw, used = call_model(messages, MODEL_SINGLE, budget)
        total_tokens += used
        budget_left  -= used
        output_parts.append(raw)
        messages.append({"role": "assistant", "content": raw})
        if budget_left <= 0:
            break
        if ITERATIONS > 1:
            messages.append({"role": "user", "content": "Continue."})

    output = "\n\n".join(output_parts)
    files  = {FILE_NAME or "output.txt": output}

    # Release notes (single agent too)
    notes = ""
    if AUTO_NOTES and TARGET_REPO:
        gen = ReleaseNotesGenerator()
        notes = gen.generate("", PROMPT, list(files.keys()))

    save_outputs(files, notes)
    write_progress("done", f"✅ Done | {total_tokens} tokens", total_tokens,
                   extra={"release_notes": notes})
    return files


# ── Entry point ────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print(f"  VIBE-CODE v2  |  mode={AGENT_MODE}  |  {datetime.datetime.utcnow():%Y-%m-%d %H:%M}")
    print("=" * 60)

    if not PROMPT:
        print("❌ No PROMPT provided"); sys.exit(1)

    if not ollama_ready(120):
        print("❌ Ollama not ready after 2 min"); sys.exit(1)
    print("✅ Ollama ready\n")

    if AGENT_MODE == "multi":
        print(f"🧠 Planner : {MODEL_PLANNER}")
        print(f"⚡ Coder   : {MODEL_CODER}")
        if TARGET_REPO:
            print(f"📂 Repo    : {TARGET_REPO}")
        print()
        orc = Orchestrator()
        result = orc.run(PROMPT)
        save_outputs(
            result.get("files", {}),
            result.get("release_notes", ""),
            result.get("pr_url", "")
        )
    else:
        run_single_agent()


if __name__ == "__main__":
    main()
