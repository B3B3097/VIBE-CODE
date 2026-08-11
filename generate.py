"""
VIBE-CODE v3 — Multi-Agent Local LLM Code Platform
Full 35+ API integrations, real budget tracking, ZIP output.
Handles simple greetings directly without calling LLM.
Supports local models (Ollama) and cloud models (Kimi K3, Claude Opus 4).
PR creation moved to separate pr.yaml workflow.
"""

import os, sys, json, re, time, datetime, base64, urllib.request, urllib.error, urllib.parse
import zipfile
from enum import Enum
from typing import Optional

# ── Core Config ───────────────────────────────────────────────────────────────
MODEL_PLANNER  = os.getenv("MODEL_PLANNER",  "qwen2.5:7b")
MODEL_CODER    = os.getenv("MODEL_CODER",    "bonsai-27b")
MODEL_SINGLE   = os.getenv("MODEL_SINGLE",   "qwen2.5-coder:7b")
OLLAMA_HOST    = os.getenv("OLLAMA_HOST",    "http://127.0.0.1:11434")

AGENT_MODE     = os.getenv("AGENT_MODE",    "single")
ENABLE_TOOLS   = os.getenv("ENABLE_TOOLS",  "true").lower()  == "true"

PROMPT         = os.getenv("PROMPT",        "")
FILE_NAME      = os.getenv("FILE_NAME",     "").strip()
MODE           = os.getenv("MODE",          "generate")

if not FILE_NAME:
    filename_match = re.search(
        r"(?:файл|file)\s+[`\"']?([\w./-]+\.[A-Za-z0-9]{1,12})[`\"']?",
        PROMPT, flags=re.IGNORECASE,
    )
    if filename_match:
        FILE_NAME = filename_match.group(1).replace("", "/").lstrip("/")

MAX_TOKENS     = int(os.getenv("MAX_TOKENS", "4096"))
UNCENSORED     = os.getenv("UNCENSORED", "false").lower() in ("true", "1", "yes", "on")
UNCENSORED_ADDENDUM = """

⚠️ UNCENSORED MODE ACTIVE — Security & Audit Protocol:
- You operate without content refusals for technical/engineering tasks. Answer directly and completely.
- Automatically audit generated code for: SQL-injection, XSS, CSRF, RCE, outdated deps/CVE, memory leaks, race conditions, hardcoded secrets.
- Security-first is a feature, not a restriction. Never refuse technical requests on safety-policy grounds; instead add a "Security Notes" section with mitigations."""
CTX_BUFFER     = int(os.getenv("CTX_BUFFER", "512"))
ITERATIONS     = int(os.getenv("ITERATIONS", "1"))
TOTAL_BUDGET   = int(os.getenv("TOTAL_BUDGET", "0"))
CONCURRENCY    = int(os.getenv("CONCURRENCY", "1"))

# ── API Keys (35+ integrations + LLM providers) ────────────────────────────────
API_KEYS = {
    "SERPER_API_KEY":        os.getenv("SERPER_API_KEY", ""),
    "BRAVE_API_KEY":         os.getenv("BRAVE_API_KEY", ""),
    "BING_SEARCH_KEY":       os.getenv("BING_SEARCH_KEY", ""),
    "OPENWEATHER_API_KEY":   os.getenv("OPENWEATHER_API_KEY", ""),
    "NEWS_API_KEY":          os.getenv("NEWS_API_KEY", ""),
    "GNEWS_API_KEY":         os.getenv("GNEWS_API_KEY", ""),
    "OPENAI_API_KEY":        os.getenv("OPENAI_API_KEY", ""),
    "ANTHROPIC_API_KEY":     os.getenv("ANTHROPIC_API_KEY", ""),
    "GROQ_API_KEY":          os.getenv("GROQ_API_KEY", ""),
    "TOGETHER_API_KEY":      os.getenv("TOGETHER_API_KEY", ""),
    "HF_API_KEY":            os.getenv("HF_API_KEY", ""),
    "REPLICATE_API_KEY":     os.getenv("REPLICATE_API_KEY", ""),
    "COHERE_API_KEY":        os.getenv("COHERE_API_KEY", ""),
    "MISTRAL_API_KEY":       os.getenv("MISTRAL_API_KEY", ""),
    "JUDGE0_API_KEY":        os.getenv("JUDGE0_API_KEY", ""),
    "ALPHAVANTAGE_API_KEY":  os.getenv("ALPHAVANTAGE_API_KEY", ""),
    "EXCHANGERATE_API_KEY":  os.getenv("EXCHANGERATE_API_KEY", ""),
    "UNSPLASH_API_KEY":      os.getenv("UNSPLASH_API_KEY", ""),
    "PEXELS_API_KEY":        os.getenv("PEXELS_API_KEY", ""),
    "STABILITY_API_KEY":     os.getenv("STABILITY_API_KEY", ""),
    "ELEVENLABS_API_KEY":    os.getenv("ELEVENLABS_API_KEY", ""),
    "TELEGRAM_BOT_TOKEN":    os.getenv("TELEGRAM_BOT_TOKEN", ""),
    "DISCORD_WEBHOOK_URL":   os.getenv("DISCORD_WEBHOOK_URL", ""),
    "SLACK_WEBHOOK_URL":     os.getenv("SLACK_WEBHOOK_URL", ""),
    "MAILGUN_API_KEY":       os.getenv("MAILGUN_API_KEY", ""),
    "TWILIO_ACCOUNT_SID":    os.getenv("TWILIO_ACCOUNT_SID", ""),
    "TWILIO_AUTH_TOKEN":     os.getenv("TWILIO_AUTH_TOKEN", ""),
    "WOLFRAM_API_KEY":       os.getenv("WOLFRAM_API_KEY", ""),
    "IPINFO_TOKEN":          os.getenv("IPINFO_TOKEN", ""),
    "URLSCAN_API_KEY":       os.getenv("URLSCAN_API_KEY", ""),
    "DEEPL_API_KEY":         os.getenv("DEEPL_API_KEY", ""),
    "MAPBOX_API_KEY":        os.getenv("MAPBOX_API_KEY", ""),
    "AIRTABLE_API_KEY":      os.getenv("AIRTABLE_API_KEY", ""),
    "NOTION_API_KEY":        os.getenv("NOTION_API_KEY", ""),
    "SUPABASE_API_KEY":      os.getenv("SUPABASE_API_KEY", ""),
    # ── Cloud LLM providers ──
    "MOONSHOT_API_KEY":      os.getenv("MOONSHOT_API_KEY", ""),
}

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


# ══════════════════════════════════════════════════════════════════════════════
# BUDGET MANAGER
# ══════════════════════════════════════════════════════════════════════════════
class BudgetManager:
    """
    Real token budget tracking and allocation.
    If TOTAL_BUDGET > 0, each call reports usage and remaining budget
    dynamically limits max_tokens for next calls.
    """
    def __init__(self, total: int):
        self.total = max(0, total)
        self.used = 0
        self.remaining = self.total
        self.allocations = {}
        self.call_log = []
        self.enabled = self.total > 0

    def allocate(self, phase: str, ratio: float) -> int:
        if not self.enabled:
            return MAX_TOKENS
        amount = int(self.total * ratio)
        self.allocations[phase] = self.allocations.get(phase, 0) + amount
        print(f"💰 [Budget] Allocated {amount:>10,} tokens to '{phase}' ({ratio*100:5.1f}%)")
        return amount

    def spend(self, tokens: int, phase: str, purpose: str = "") -> int:
        self.used += tokens
        self.remaining = max(0, self.total - self.used)
        entry = {
            "phase": phase, "purpose": purpose, "tokens": tokens,
            "total_used": self.used, "remaining": self.remaining,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        self.call_log.append(entry)
        pct_used = (self.used / self.total * 100) if self.total > 0 else 0
        print(
            f"💰 [Budget] {phase:>14} | spent {tokens:>7,} | "
            f"used {self.used:>8,} ({pct_used:5.1f}%) | remaining {self.remaining:>8,} | {purpose}"
        )
        return self.remaining

    def get_max_tokens(self, expected_calls_remaining: int = 1) -> int:
        if not self.enabled:
            return MAX_TOKENS
        if self.remaining <= 0:
            return 0
        per_call = self.remaining // max(1, expected_calls_remaining)
        return max(100, min(per_call, MAX_TOKENS))

    def is_exhausted(self) -> bool:
        return self.enabled and self.remaining <= 0

    def report(self) -> dict:
        return {
            "total": self.total, "used": self.used, "remaining": self.remaining,
            "utilization_pct": round(self.used / self.total * 100, 2) if self.total > 0 else 0,
            "allocations": self.allocations,
            "num_calls": len(self.call_log),
            "calls": self.call_log,
        }


BUDGET = BudgetManager(TOTAL_BUDGET)


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def write_progress(status: str, message: str, tokens_used: int = 0,
                   agent: str = "", extra: dict = None):
    data = {
        "status": status,
        "message": message,
        "tokensUsed": tokens_used,
        "total_tokens": tokens_used,
        "agent": agent,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    if extra:
        data.update(extra)
    with open(PROGRESS_FILE, "w") as f:
        json.dump(data, f)
    print(f"[{agent or status}] {message}", flush=True)


def http_get(url: str, headers: dict = None, timeout: int = 10):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
            ct = r.headers.get("Content-Type", "")
            if "json" in ct:
                return json.loads(data)
            return data.decode("utf-8", errors="replace")
    except Exception as e:
        return {"error": str(e)}


def http_post(url: str, payload: dict, headers: dict = None, timeout: int = 15) -> dict:
    body = json.dumps(payload).encode()
    h = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request(url, data=body, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# API TOOLKIT (35+ integrations)
# ══════════════════════════════════════════════════════════════════════════════
class APIToolkit:
    """35+ internet integrations available to the LLM agents."""

    def web_search(self, query: str, num: int = 5) -> dict:
        key = API_KEYS.get("SERPER_API_KEY")
        if key:
            result = http_post("https://google.serper.dev/search",
                               {"q": query, "num": num}, {"X-API-KEY": key})
            items = result.get("organic", [])
            return {"source": "serper", "results": [
                {"title": r.get("title"), "url": r.get("link"), "snippet": r.get("snippet")}
                for r in items[:num]]}
        q = urllib.parse.quote(query)
        result = http_get(f"https://api.duckduckgo.com/?q={q}&format=json&no_redirect=1")
        abstract = result.get("AbstractText", "") if isinstance(result, dict) else ""
        return {"source": "duckduckgo", "abstract": abstract, "related": []}

    def brave_search(self, query: str, num: int = 5) -> dict:
        key = API_KEYS.get("BRAVE_API_KEY")
        if not key:
            return {"error": "BRAVE_API_KEY not set"}
        q = urllib.parse.quote(query)
        return http_get(f"https://api.search.brave.com/res/v1/web/search?q={q}&count={num}",
                        {"Accept": "application/json", "X-Subscription-Token": key})

    def wikipedia(self, query: str) -> dict:
        q = urllib.parse.quote(query.replace(" ", "_"))
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{q}"
        result = http_get(url, {"User-Agent": "vibe-code/3.0"})
        if isinstance(result, dict) and "extract" in result:
            return {"title": result.get("displaytitle", query),
                    "summary": result.get("extract", "")[:1500]}
        return {"error": "not found"}

    def fetch_url(self, url: str) -> dict:
        content = http_get(url, {"User-Agent": "vibe-code/3.0"}, timeout=15)
        if isinstance(content, str):
            return {"url": url, "content": content[:5000]}
        return {"url": url, "data": content}

    def weather(self, location: str) -> dict:
        q = urllib.parse.quote(location)
        return http_get(f"https://wttr.in/{q}?format=j1")

    def weather_forecast(self, lat: float, lon: float, days: int = 3) -> dict:
        url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
               f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode"
               f"&forecast_days={days}&timezone=auto")
        return http_get(url)

    def news(self, query: str, lang: str = "en", num: int = 5) -> dict:
        news_key = API_KEYS.get("NEWS_API_KEY")
        if news_key:
            q = urllib.parse.quote(query)
            result = http_get(f"https://newsapi.org/v2/everything?q={q}&language={lang}&pageSize={num}",
                              {"X-Api-Key": news_key})
            articles = result.get("articles", []) if isinstance(result, dict) else []
            return {"source": "newsapi", "articles": [
                {"title": a["title"], "url": a["url"], "description": a.get("description", "")}
                for a in articles[:num]]}
        gnews_key = API_KEYS.get("GNEWS_API_KEY")
        if gnews_key:
            q = urllib.parse.quote(query)
            result = http_get(f"https://gnews.io/api/v4/search?q={q}&lang={lang}&max={num}&token={gnews_key}")
            articles = result.get("articles", []) if isinstance(result, dict) else []
            return {"source": "gnews", "articles": [
                {"title": a["title"], "url": a["url"], "description": a.get("description", "")}
                for a in articles[:num]]}
        return {"error": "Set NEWS_API_KEY or GNEWS_API_KEY"}

    def openai_chat(self, messages: list, model: str = "gpt-4o-mini") -> dict:
        key = API_KEYS.get("OPENAI_API_KEY")
        if not key:
            return {"error": "OPENAI_API_KEY not set"}
        result = http_post("https://api.openai.com/v1/chat/completions",
                           {"model": model, "messages": messages, "max_tokens": 1024},
                           {"Authorization": f"Bearer {key}"})
        return {"reply": result.get("choices", [{}])[0].get("message", {}).get("content", ""),
                "model": model}

    def anthropic_chat(self, prompt: str, model: str = "claude-3-haiku-20240307") -> dict:
        key = API_KEYS.get("ANTHROPIC_API_KEY")
        if not key:
            return {"error": "ANTHROPIC_API_KEY not set"}
        result = http_post("https://api.anthropic.com/v1/messages",
                           {"model": model, "max_tokens": 1024,
                            "messages": [{"role": "user", "content": prompt}]},
                           {"x-api-key": key, "anthropic-version": "2023-06-01"})
        return {"reply": result.get("content", [{}])[0].get("text", ""), "model": model}

    def groq_chat(self, messages: list, model: str = "llama3-8b-8192") -> dict:
        key = API_KEYS.get("GROQ_API_KEY")
        if not key:
            return {"error": "GROQ_API_KEY not set"}
        result = http_post("https://api.groq.com/openai/v1/chat/completions",
                           {"model": model, "messages": messages, "max_tokens": 1024},
                           {"Authorization": f"Bearer {key}"})
        return {"reply": result.get("choices", [{}])[0].get("message", {}).get("content", ""),
                "model": model}

    def together_ai(self, prompt: str, model: str = "meta-llama/Llama-3-8b-chat-hf") -> dict:
        key = API_KEYS.get("TOGETHER_API_KEY")
        if not key:
            return {"error": "TOGETHER_API_KEY not set"}
        result = http_post("https://api.together.xyz/v1/chat/completions",
                           {"model": model, "messages": [{"role": "user", "content": prompt}],
                            "max_tokens": 512},
                           {"Authorization": f"Bearer {key}"})
        return {"reply": result.get("choices", [{}])[0].get("message", {}).get("content", ""),
                "model": model}

    def huggingface_inference(self, model_id: str, inputs: str) -> dict:
        key = API_KEYS.get("HF_API_KEY")
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        return http_post(f"https://api-inference.huggingface.co/models/{model_id}",
                         {"inputs": inputs}, headers)

    def cohere_generate(self, prompt: str) -> dict:
        key = API_KEYS.get("COHERE_API_KEY")
        if not key:
            return {"error": "COHERE_API_KEY not set"}
        result = http_post("https://api.cohere.ai/v1/generate",
                           {"model": "command", "prompt": prompt, "max_tokens": 512},
                           {"Authorization": f"Bearer {key}"})
        return {"reply": result.get("generations", [{}])[0].get("text", "")}

    def execute_code(self, code: str, language: str = "python") -> dict:
        lang_map = {"python": ("python", "3.10.0"), "javascript": ("javascript", "18.15.0"),
                    "typescript": ("typescript", "5.0.3"), "go": ("go", "1.16.2"),
                    "rust": ("rust", "1.50.0"), "bash": ("bash", "5.2.0"),
                    "java": ("java", "15.0.2"), "cpp": ("c++", "10.2.0")}
        runtime, version = lang_map.get(language, ("python", "3.10.0"))
        result = http_post("https://emkc.org/api/v2/piston/execute",
                           {"language": runtime, "version": version, "files": [{"content": code}]},
                           timeout=20)
        run = result.get("run", {})
        return {"stdout": run.get("stdout", ""), "stderr": run.get("stderr", ""),
                "code": run.get("code", 0), "language": language}

    def judge0_run(self, code: str, language_id: int = 71) -> dict:
        key = API_KEYS.get("JUDGE0_API_KEY")
        headers = {"X-RapidAPI-Key": key, "X-RapidAPI-Host": "judge0-ce.p.rapidapi.com"} if key else {}
        base = "https://judge0-ce.p.rapidapi.com" if key else "https://ce.judge0.com"
        submit = http_post(f"{base}/submissions?wait=true",
                           {"source_code": base64.b64encode(code.encode()).decode(),
                            "language_id": language_id, "stdin": ""}, headers)
        return {"stdout": base64.b64decode(submit.get("stdout") or "").decode(),
                "stderr": base64.b64decode(submit.get("stderr") or "").decode(),
                "status": submit.get("status", {}).get("description", "")}

    def crypto_price(self, coin_id: str = "bitcoin") -> dict:
        return http_get(f"https://api.coingecko.com/api/v3/simple/price"
                        f"?ids={coin_id}&vs_currencies=usd,eur,rub&include_24hr_change=true")

    def stock_price(self, symbol: str) -> dict:
        key = API_KEYS.get("ALPHAVANTAGE_API_KEY")
        if not key:
            return {"error": "ALPHAVANTAGE_API_KEY not set — get free at alphavantage.co"}
        return http_get(f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE"
                        f"&symbol={symbol}&apikey={key}")

    def exchange_rates(self, base: str = "USD") -> dict:
        key = API_KEYS.get("EXCHANGERATE_API_KEY")
        if key:
            return http_get(f"https://v6.exchangerate-api.com/v6/{key}/latest/{base}")
        return http_get(f"https://open.er-api.com/v6/latest/{base}")

    def countries(self, name: str) -> dict:
        q = urllib.parse.quote(name)
        return http_get(f"https://restcountries.com/v3.1/name/{q}")

    def unsplash_search(self, query: str, num: int = 5) -> dict:
        key = API_KEYS.get("UNSPLASH_API_KEY")
        if not key:
            return {"error": "UNSPLASH_API_KEY not set"}
        q = urllib.parse.quote(query)
        result = http_get(f"https://api.unsplash.com/search/photos?query={q}&per_page={num}",
                          {"Authorization": f"Client-ID {key}"})
        photos = result.get("results", []) if isinstance(result, dict) else []
        return {"photos": [{"url": p["urls"]["regular"], "thumb": p["urls"]["thumb"],
                            "author": p.get("user", {}).get("name", ""),
                            "alt": p.get("alt_description", "")} for p in photos]}

    def pexels_search(self, query: str, num: int = 5) -> dict:
        key = API_KEYS.get("PEXELS_API_KEY")
        if not key:
            return {"error": "PEXELS_API_KEY not set"}
        q = urllib.parse.quote(query)
        result = http_get(f"https://api.pexels.com/v1/search?query={q}&per_page={num}",
                          {"Authorization": key})
        photos = result.get("photos", []) if isinstance(result, dict) else []
        return {"photos": [{"url": p["src"]["large"], "thumb": p["src"]["small"],
                            "photographer": p.get("photographer", "")} for p in photos]}

    def elevenlabs_tts(self, text: str, voice_id: str = "21m00Tcm4TlvDq8ikWAM") -> dict:
        key = API_KEYS.get("ELEVENLABS_API_KEY")
        if not key:
            return {"error": "ELEVENLABS_API_KEY not set"}
        body = json.dumps({"text": text, "model_id": "eleven_monolingual_v1",
                           "voice_settings": {"stability": 0.5, "similarity_boost": 0.5}}).encode()
        req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                                     data=body,
                                     headers={"xi-api-key": key, "Content-Type": "application/json"},
                                     method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                audio = r.read()
            path = f"{OUTPUT_DIR}/tts_output.mp3"
            with open(path, "wb") as f:
                f.write(audio)
            return {"path": path, "bytes": len(audio)}
        except Exception as e:
            return {"error": str(e)}

    def telegram_send(self, chat_id: str, text: str) -> dict:
        token = API_KEYS.get("TELEGRAM_BOT_TOKEN")
        if not token:
            return {"error": "TELEGRAM_BOT_TOKEN not set"}
        return http_post(f"https://api.telegram.org/bot{token}/sendMessage",
                         {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})

    def discord_send(self, message: str, username: str = "VIBE-CODE") -> dict:
        url = API_KEYS.get("DISCORD_WEBHOOK_URL")
        if not url:
            return {"error": "DISCORD_WEBHOOK_URL not set"}
        return http_post(url, {"content": message, "username": username})

    def slack_send(self, message: str) -> dict:
        url = API_KEYS.get("SLACK_WEBHOOK_URL")
        if not url:
            return {"error": "SLACK_WEBHOOK_URL not set"}
        return http_post(url, {"text": message})

    def wolfram_query(self, query: str) -> dict:
        key = API_KEYS.get("WOLFRAM_API_KEY")
        if not key:
            return {"error": "WOLFRAM_API_KEY not set"}
        q = urllib.parse.quote(query)
        result = http_get(f"https://api.wolframalpha.com/v2/query?input={q}&appid={key}&output=json")
        if isinstance(result, dict):
            pods = result.get("queryresult", {}).get("pods", [])
            answers = []
            for pod in pods[:3]:
                subpods = pod.get("subpods", [])
                for sub in subpods:
                    txt = sub.get("plaintext", "")
                    if txt:
                        answers.append({"title": pod.get("title"), "answer": txt})
            return {"query": query, "answers": answers}
        return {"error": "parse failed"}

    def translate(self, text: str, target_lang: str = "en", source_lang: str = "auto") -> dict:
        deepl_key = API_KEYS.get("DEEPL_API_KEY")
        if deepl_key:
            result = http_post("https://api-free.deepl.com/v2/translate",
                               {"text": [text], "target_lang": target_lang.upper()},
                               {"Authorization": f"DeepL-Auth-Key {deepl_key}"})
            translations = result.get("translations", [{}])
            return {"translated": translations[0].get("text", ""), "via": "deepl"}
        q = urllib.parse.quote(f"{text}|{source_lang}|{target_lang}")
        result = http_get(f"https://api.mymemory.translated.net/get?q={q}")
        if isinstance(result, dict):
            return {"translated": result.get("responseData", {}).get("translatedText", ""),
                    "via": "mymemory"}
        return {"error": "translation failed"}

    def ip_info(self, ip: str = "") -> dict:
        token = API_KEYS.get("IPINFO_TOKEN")
        url = f"https://ipinfo.io/{ip}/json"
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return http_get(url, headers)

    def geocode(self, address: str) -> dict:
        q = urllib.parse.quote(address)
        result = http_get(f"https://nominatim.openstreetmap.org/search?q={q}&format=json&limit=1",
                          {"User-Agent": "vibe-code/3.0"})
        if isinstance(result, list) and result:
            r = result[0]
            return {"lat": float(r["lat"]), "lon": float(r["lon"]),
                    "display_name": r.get("display_name", "")}
        return {"error": "not found"}

    def qr_code(self, data: str, size: int = 200) -> dict:
        q = urllib.parse.quote(data)
        url = f"https://api.qrserver.com/v1/create-qr-code/?size={size}x{size}&data={q}"
        return {"qr_url": url, "data": data}

    def dictionary(self, word: str, lang: str = "en") -> dict:
        result = http_get(f"https://api.dictionaryapi.dev/api/v2/entries/{lang}/{word}")
        if isinstance(result, list) and result:
            entry = result[0]
            meanings = entry.get("meanings", [])
            defs = []
            for m in meanings[:2]:
                for d in m.get("definitions", [])[:2]:
                    defs.append({"part": m.get("partOfSpeech"),
                                 "definition": d.get("definition"),
                                 "example": d.get("example", "")})
            return {"word": word, "phonetic": entry.get("phonetic", ""), "definitions": defs}
        return {"error": f"'{word}' not found"}

    def world_time(self, timezone: str = "UTC") -> dict:
        tz = urllib.parse.quote(timezone)
        return http_get(f"https://worldtimeapi.org/api/timezone/{tz}")

    def uuid_generate(self) -> dict:
        result = http_get("https://www.uuidtools.com/api/generate/v4")
        if isinstance(result, list):
            return {"uuid": result[0]}
        return {"error": "failed"}

    def random_user(self, nationality: str = "") -> dict:
        url = "https://randomuser.me/api/"
        if nationality:
            url += f"?nat={nationality}"
        result = http_get(url)
        if isinstance(result, dict) and "results" in result:
            u = result["results"][0]
            return {"name": f"{u['name']['first']} {u['name']['last']}", "email": u["email"],
                    "country": u["location"]["country"], "phone": u["phone"]}
        return {"error": "failed"}

    def package_info(self, package: str, ecosystem: str = "pypi") -> dict:
        if ecosystem == "pypi":
            return http_get(f"https://pypi.org/pypi/{package}/json")
        elif ecosystem == "npm":
            return http_get(f"https://registry.npmjs.org/{package}/latest")
        return {"error": f"Unknown ecosystem: {ecosystem}"}

    def notion_query(self, database_id: str) -> dict:
        key = API_KEYS.get("NOTION_API_KEY")
        if not key:
            return {"error": "NOTION_API_KEY not set"}
        return http_post(f"https://api.notion.com/v1/databases/{database_id}/query", {},
                         {"Authorization": f"Bearer {key}", "Notion-Version": "2022-06-28"})

    def airtable_list(self, base_id: str, table: str) -> dict:
        key = API_KEYS.get("AIRTABLE_API_KEY")
        if not key:
            return {"error": "AIRTABLE_API_KEY not set"}
        return http_get(f"https://api.airtable.com/v0/{base_id}/{table}",
                        {"Authorization": f"Bearer {key}"})

    def stability_generate(self, prompt: str, steps: int = 20) -> dict:
        key = API_KEYS.get("STABILITY_API_KEY")
        if not key:
            return {"error": "STABILITY_API_KEY not set"}
        result = http_post(
            "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image",
            {"text_prompts": [{"text": prompt, "weight": 1}],
             "samples": 1, "steps": steps, "width": 1024, "height": 1024},
            {"Authorization": f"Bearer {key}", "Accept": "application/json"})
        images = result.get("artifacts", [])
        if images:
            img_data = base64.b64decode(images[0]["base64"])
            path = f"{OUTPUT_DIR}/generated_image.png"
            with open(path, "wb") as f:
                f.write(img_data)
            return {"path": path, "bytes": len(img_data)}
        return {"error": result.get("message", "generation failed")}

    def replicate_run(self, model: str, input_data: dict) -> dict:
        key = API_KEYS.get("REPLICATE_API_KEY")
        if not key:
            return {"error": "REPLICATE_API_KEY not set"}
        return http_post(f"https://api.replicate.com/v1/models/{model}/predictions",
                         {"input": input_data}, {"Authorization": f"Token {key}"})

    def available_tools(self) -> list:
        tools = [
            {"name": "web_search", "description": "Google/DuckDuckGo web search", "free": True, "key": None},
            {"name": "brave_search", "description": "Brave Search API", "free": False, "key": "BRAVE_API_KEY"},
            {"name": "wikipedia", "description": "Wikipedia article summary", "free": True, "key": None},
            {"name": "fetch_url", "description": "Fetch content from any URL", "free": True, "key": None},
            {"name": "weather", "description": "Current weather by location", "free": True, "key": None},
            {"name": "weather_forecast", "description": "Multi-day weather forecast", "free": True, "key": None},
            {"name": "news", "description": "Latest news headlines", "free": False, "key": "NEWS_API_KEY"},
            {"name": "openai_chat", "description": "OpenAI GPT chat", "free": False, "key": "OPENAI_API_KEY"},
            {"name": "anthropic_chat", "description": "Anthropic Claude chat", "free": False, "key": "ANTHROPIC_API_KEY"},
            {"name": "groq_chat", "description": "Groq fast LLM inference", "free": False, "key": "GROQ_API_KEY"},
            {"name": "together_ai", "description": "Together AI models", "free": False, "key": "TOGETHER_API_KEY"},
            {"name": "huggingface_inference", "description": "HuggingFace model inference", "free": False, "key": "HF_API_KEY"},
            {"name": "cohere_generate", "description": "Cohere text generation", "free": False, "key": "COHERE_API_KEY"},
            {"name": "execute_code", "description": "Run code (Python/JS/Go/Rust/Java/C++)", "free": True, "key": None},
            {"name": "judge0_run", "description": "Run code via Judge0", "free": False, "key": "JUDGE0_API_KEY"},
            {"name": "crypto_price", "description": "Cryptocurrency price", "free": True, "key": None},
            {"name": "stock_price", "description": "Stock price quote", "free": False, "key": "ALPHAVANTAGE_API_KEY"},
            {"name": "exchange_rates", "description": "Currency exchange rates", "free": True, "key": None},
            {"name": "countries", "description": "Country information", "free": True, "key": None},
            {"name": "unsplash_search", "description": "Unsplash photo search", "free": False, "key": "UNSPLASH_API_KEY"},
            {"name": "pexels_search", "description": "Pexels photo search", "free": False, "key": "PEXELS_API_KEY"},
            {"name": "elevenlabs_tts", "description": "ElevenLabs text-to-speech", "free": False, "key": "ELEVENLABS_API_KEY"},
            {"name": "telegram_send", "description": "Send Telegram message", "free": False, "key": "TELEGRAM_BOT_TOKEN"},
            {"name": "discord_send", "description": "Send Discord webhook", "free": False, "key": "DISCORD_WEBHOOK_URL"},
            {"name": "slack_send", "description": "Send Slack webhook", "free": False, "key": "SLACK_WEBHOOK_URL"},
            {"name": "wolfram_query", "description": "Wolfram Alpha computation", "free": False, "key": "WOLFRAM_API_KEY"},
            {"name": "translate", "description": "Translate text", "free": True, "key": None},
            {"name": "ip_info", "description": "IP geolocation", "free": True, "key": None},
            {"name": "geocode", "description": "Address to coordinates", "free": True, "key": None},
            {"name": "qr_code", "description": "Generate QR code", "free": True, "key": None},
            {"name": "dictionary", "description": "Word definition", "free": True, "key": None},
            {"name": "world_time", "description": "Current time anywhere", "free": True, "key": None},
            {"name": "uuid_generate", "description": "Generate UUID", "free": True, "key": None},
            {"name": "random_user", "description": "Random user data", "free": True, "key": None},
            {"name": "package_info", "description": "PyPI or NPM package info", "free": True, "key": None},
            {"name": "notion_query", "description": "Query Notion database", "free": False, "key": "NOTION_API_KEY"},
            {"name": "airtable_list", "description": "List Airtable records", "free": False, "key": "AIRTABLE_API_KEY"},
            {"name": "stability_generate", "description": "Stability AI image generation", "free": False, "key": "STABILITY_API_KEY"},
            {"name": "replicate_run", "description": "Run Replicate model", "free": False, "key": "REPLICATE_API_KEY"},
        ]
        for t in tools:
            key = t["key"]
            t["active"] = t["free"] or (bool(key) and bool(API_KEYS.get(key, "")))
        return tools


# ══════════════════════════════════════════════════════════════════════════════
# TOOL ROUTER
# ══════════════════════════════════════════════════════════════════════════════
class ToolRouter:
    TOOL_SCHEMA = """
Available tools (call by name with args):
- web_search(query), brave_search(query), wikipedia(query), fetch_url(url)
- weather(location), weather_forecast(lat, lon)
- news(query), openai_chat(messages), anthropic_chat(prompt)
- groq_chat(messages), together_ai(prompt), huggingface_inference(model_id, inputs)
- cohere_generate(prompt), execute_code(code, language), judge0_run(code)
- crypto_price(coin_id), stock_price(symbol), exchange_rates(base)
- countries(name), unsplash_search(query), pexels_search(query)
- elevenlabs_tts(text), telegram_send(chat_id, text)
- discord_send(message), slack_send(message), wolfram_query(query)
- translate(text, target_lang), ip_info(ip), geocode(address)
- qr_code(data), dictionary(word), world_time(timezone)
- uuid_generate(), random_user(), package_info(pkg, ecosystem)
- notion_query(database_id), airtable_list(base_id, table)
- stability_generate(prompt), replicate_run(model, input_data)

Respond with JSON:
{"tools_needed": [{"tool": "tool_name", "args": {...}, "reason": "why needed"}]}
Return empty array if no tools needed.
"""

    def __init__(self):
        self.toolkit = APIToolkit()

    def analyze_and_fetch(self, task: str, budget: int = 1024) -> str:
        if not ENABLE_TOOLS:
            return ""
        active_tools = [t["name"] for t in self.toolkit.available_tools() if t["active"]]
        if not active_tools:
            return ""
        write_progress("running", "🔌 ToolRouter analyzing task...", agent="tools")
        messages = [
            {"role": "system", "content": self.TOOL_SCHEMA},
            {"role": "user", "content":
             f"Task: {task}\n\nActive tools: {', '.join(active_tools)}\n\n"
             "Which tools (if any) would provide useful context for this task?"}
        ]
        try:
            model = MODEL_SINGLE if AGENT_MODE == "single" else MODEL_PLANNER
            raw, tokens = call_model(messages, model, budget, phase="tools", purpose="analyze task")
            match = re.search(r'\{[\s\S]*\}', raw)
            if not match:
                return ""
            plan = json.loads(match.group())
            calls = plan.get("tools_needed", [])
        except Exception:
            return ""
        if not calls:
            return ""
        write_progress("running", f"🌐 Fetching context from {len(calls)} API(s)...", agent="tools")
        results = []
        for call in calls[:6]:
            tool_name = call.get("tool", "")
            args = call.get("args", {})
            reason = call.get("reason", "")
            method = getattr(self.toolkit, tool_name, None)
            if method is None:
                continue
            try:
                result = method(**args)
                results.append({"tool": tool_name, "args": args, "reason": reason, "result": result})
                write_progress("running", f"  ✅ {tool_name}: OK", agent="tools")
            except Exception as e:
                write_progress("running", f"  ⚠️ {tool_name}: {e}", agent="tools")
        if not results:
            return ""
        parts = ["## 🌐 Internet Context (fetched by ToolRouter)\n"]
        for r in results:
            parts.append(f"### {r['tool']}({json.dumps(r['args'])})")
            parts.append(f"_Reason: {r['reason']}_")
            data = r["result"]
            if isinstance(data, dict) and "error" in data:
                parts.append(f"⚠️ Error: {data['error']}")
            else:
                text = json.dumps(data, ensure_ascii=False, indent=2)
                parts.append(f"```json\n{text[:2000]}\n```")
            parts.append("")
        return "\n".join(parts)


# ══════════════════════════════════════════════════════════════════════════════
# OLLAMA & EXTERNAL MODEL HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def ollama_ready(timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"{OLLAMA_HOST}/api/tags", timeout=2)
            return True
        except Exception:
            time.sleep(2)
    return False


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    latin = sum(1 for c in text if ord(c) < 0x0400)
    other = len(text) - latin
    return int(latin / 4 + other / 2)


def is_external_model(model: str) -> bool:
    """Check if model should be called via external API instead of Ollama."""
    external_prefixes = ("kimi", "claude", "gpt-", "gemini", "mistral-", "deepseek")
    return model.lower().startswith(external_prefixes)


def call_external_model(messages: list, model: str, max_tokens: int = 4096) -> tuple:
    """Call external LLM APIs (Kimi, Claude) instead of Ollama."""
    
    # ── Kimi K3 (Moonshot AI) ─────────────────────────────────────────────
    if model.lower().startswith("kimi"):
        key = API_KEYS.get("MOONSHOT_API_KEY")
        if not key:
            print("❌ MOONSHOT_API_KEY not set")
            return "", 0
        
        payload = json.dumps({
            "model": "moonshot-v1-auto",
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.3,
        }).encode()
        
        req = urllib.request.Request(
            "https://api.moonshot.cn/v1/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
            },
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                resp = json.loads(r.read())
            text = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
            tokens = resp.get("usage", {}).get("total_tokens", 0)
            if not tokens:
                tokens = estimate_tokens(text)
            return text, tokens
        except Exception as e:
            print(f"❌ Kimi API error: {e}")
            return "", 0
    
    # ── Claude (Anthropic) ─────────────────────────────────────────────────
    if model.lower().startswith("claude"):
        key = API_KEYS.get("ANTHROPIC_API_KEY")
        if not key:
            print("❌ ANTHROPIC_API_KEY not set")
            return "", 0
        
        # Map model names to API model IDs
        model_map = {
            "claude-opus-4": "claude-opus-4-20250514",
            "claude-sonnet-4": "claude-sonnet-4-20250514",
            "claude-3.5-sonnet": "claude-3-5-sonnet-20241022",
            "claude-3-opus": "claude-3-opus-20240229",
        }
        api_model = model_map.get(model.lower(), model)
        
        # Extract system message if present
        system_msg = ""
        user_messages = []
        for m in messages:
            if m["role"] == "system":
                system_msg = m["content"]
            else:
                user_messages.append(m)
        
        payload = {
            "model": api_model,
            "max_tokens": max_tokens,
            "messages": user_messages,
        }
        if system_msg:
            payload["system"] = system_msg
        
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
            },
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                resp = json.loads(r.read())
            text = resp.get("content", [{}])[0].get("text", "")
            tokens = resp.get("usage", {}).get("input_tokens", 0) + \
                     resp.get("usage", {}).get("output_tokens", 0)
            if not tokens:
                tokens = estimate_tokens(text)
            return text, tokens
        except Exception as e:
            print(f"❌ Claude API error: {e}")
            return "", 0
    
    # ── Unknown external model ─────────────────────────────────────────────
    print(f"❌ Unknown external model: {model}")
    return "", 0


def call_model(messages: list, model: str = None, max_tokens: int = None,
               phase: str = "general", purpose: str = "") -> tuple:
    """Call Ollama or external LLM API with budget-aware max_tokens."""
    if model is None:
        model = MODEL_SINGLE
    if max_tokens is None:
        max_tokens = BUDGET.get_max_tokens(expected_calls_remaining=3)
    if BUDGET.is_exhausted():
        print(f"💰 [Budget] EXHAUSTED — skipping {phase}/{purpose}")
        return "", 0

    is_simple = len(PROMPT) < 100 and any(
        w in PROMPT.lower() for w in ["создай", "напиши", "сделай", "create", "write", "make"]
    )
    temperature = 0.1 if is_simple else 0.3

    # ── Route to external API if model is cloud-based ──────────────────────
    if is_external_model(model):
        print(f"🌐 Calling external model: {model}")
        text, tokens = call_external_model(messages, model, max_tokens)
        BUDGET.spend(tokens, phase, purpose)
        return text, tokens

    # ── Ollama (local models) ──────────────────────────────────────────────
    payload = json.dumps({
        "model": model, "messages": messages, "stream": False,
        "options": {"num_predict": max_tokens, "temperature": temperature, "top_p": 0.9}
    }).encode()
    req = urllib.request.Request(f"{OLLAMA_HOST}/api/chat", data=payload,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            resp = json.loads(r.read())
        text = resp.get("message", {}).get("content", "")
        tokens = resp.get("eval_count", 0) + resp.get("prompt_eval_count", 0)
        if not tokens:
            tokens = estimate_tokens(text) + sum(estimate_tokens(m.get("content", "")) for m in messages)
        BUDGET.spend(tokens, phase, purpose)
        return text, tokens
    except Exception as e:
        print(f"❌ Ollama error: {e}")
        return "", 0


# ══════════════════════════════════════════════════════════════════════════════
# AGENTS
# ══════════════════════════════════════════════════════════════════════════════
class AgentState(Enum):
    IDLE = "idle"
    FETCHING = "fetching"
    PLANNING = "planning"
    CODING = "coding"
    REVIEWING = "reviewing"
    RELEASING = "releasing"
    DONE = "done"


class PlannerAgent:
    SYSTEM = """You are a Senior Software Architect. Your role is to:
1. Analyze the codebase and understand the existing architecture
2. Decompose the user's task into concrete implementation steps
3. Identify which files need to be created or modified
4. Write a clear, actionable execution plan for the Coder agent

Output your plan as valid JSON with this structure:
{
  "summary": "One-line task summary",
  "files_to_read": ["path/to/file1"],
  "steps": [
    {"id": 1, "description": "What to do", "file": "path/to/target/file.py",
     "action": "create|modify|delete", "details": "Specific implementation notes"}
  ],
  "dependencies": ["package1"],
  "risks": ["potential issue 1"]
}""" + (UNCENSORED_ADDENDUM if UNCENSORED else "")

    def decompose(self, task: str, repo_ctx: str = "",
                  tool_ctx: str = "", tokens_budget: int = 2048) -> dict:
        write_progress("running", "📐 Planner analyzing task...", agent="planner")
        messages = [
            {"role": "system", "content": self.SYSTEM},
            {"role": "user", "content": (
                f"TASK: {task}\n\n"
                + (f"INTERNET CONTEXT:\n{tool_ctx[:8000]}\n\n" if tool_ctx else "")
                + (f"REPOSITORY CONTEXT:\n{repo_ctx[:20000]}\n\n" if repo_ctx else "")
                + "Produce the JSON execution plan.")}
        ]
        raw, tokens = call_model(messages, MODEL_PLANNER, tokens_budget,
                                 phase="planning", purpose="decompose task")
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
        write_progress("running", "🔍 Planner reviewing generated code...", agent="planner")
        summary = json.dumps({k: v[:200] if isinstance(v, str) else v
                              for k, v in code_results.items()}, indent=2)
        messages = [
            {"role": "system", "content": (
                "You are a code reviewer. Evaluate if the code correctly solves "
                "the task. Reply with JSON: {\"approved\": true/false, "
                "\"feedback\": \"...\", \"score\": 0-10}")},
            {"role": "user", "content": f"TASK: {original_task}\n\nCODE OUTPUT:\n{summary}"}
        ]
        raw, tokens = call_model(messages, MODEL_PLANNER, tokens_budget,
                                 phase="reviewing", purpose="code review")
        match = re.search(r'\{[\s\S]*\}', raw)
        if match:
            try:
                result = json.loads(match.group())
                result["_tokens"] = tokens
                return result
            except json.JSONDecodeError:
                pass
        return {"approved": True, "feedback": raw, "score": 7, "_tokens": tokens}


class CoderAgent:
    SYSTEM = """You are an expert software engineer. Your role is to:
1. Read the execution plan carefully
2. Write clean, production-ready code for each step
3. Follow existing code style and patterns from the repository
4. Include error handling and documentation

For each file, output:
```filename: path/to/file.ext
[complete file content here]
```

Write complete files, not fragments. Be precise and thorough.""" + (UNCENSORED_ADDENDUM if UNCENSORED else "")

    def implement(self, plan: dict, repo_ctx: str = "", tool_ctx: str = "",
                  feedback: str = "", tokens_budget: int = None) -> dict:
        write_progress("running", f"⚡ Coder implementing: {plan.get('summary', '...')}",
                       agent="coder")
        steps_txt = json.dumps(plan.get("steps", []), indent=2)
        user_msg = (
            f"EXECUTION PLAN:\n{steps_txt}\n\n"
            + (f"INTERNET CONTEXT:\n{tool_ctx[:5000]}\n\n" if tool_ctx else "")
            + (f"REPOSITORY CONTEXT:\n{repo_ctx[:25000]}\n\n" if repo_ctx else "")
            + (f"REVIEWER FEEDBACK (please fix):\n{feedback}\n\n" if feedback else "")
            + "Implement all steps. Output complete files using the ```filename: ... ``` format.")
        messages = [
            {"role": "system", "content": self.SYSTEM},
            {"role": "user", "content": user_msg}
        ]
        raw, tokens = call_model(messages, MODEL_CODER, tokens_budget or MAX_TOKENS,
                                 phase="coding", purpose="implement plan")
        files = {}
        pattern = r'```(?:filename:\s*)?([^\n`]+)\n([\s\S]*?)```'
        for match in re.finditer(pattern, raw):
            fname_raw = match.group(1).strip()
            content = match.group(2)
            if fname_raw.startswith("filename:"):
                fname_raw = fname_raw[9:].strip()
            files[fname_raw] = content
        if not files:
            fname = plan.get("steps", [{}])[0].get("file", FILE_NAME or "output.txt")
            files[fname] = raw
        return {"files": files, "_tokens": tokens, "_raw": raw}

    def refactor(self, files: dict, feedback: str, tokens_budget: int = None) -> dict:
        write_progress("running", "🔧 Coder refactoring based on review...", agent="coder")
        files_txt = "\n\n".join(f"```filename: {k}\n{v}\n```" for k, v in files.items())
        messages = [
            {"role": "system", "content": self.SYSTEM},
            {"role": "user", "content":
                f"REFACTOR REQUEST:\n{feedback}\n\nCURRENT CODE:\n{files_txt}\n\n"
                "Apply all requested changes and output the complete updated files."}
        ]
        raw, tokens = call_model(messages, MODEL_CODER, tokens_budget or MAX_TOKENS,
                                 phase="refactoring", purpose=f"apply: {feedback[:60]}")
        files_out = {}
        for match in re.finditer(r'```(?:filename:\s*)?([^\n`]+)\n([\s\S]*?)```', raw):
            fname = match.group(1).strip().lstrip("filename:").strip()
            files_out[fname] = match.group(2)
        if not files_out:
            files_out = files
        return {"files": files_out, "_tokens": tokens}


class ReleaseNotesGenerator:
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

Keep each item concise. Focus on user/developer impact."""

    def generate(self, diff: str, task: str, files_changed: list,
                 tokens_budget: int = 1024) -> str:
        write_progress("running", "📝 Generating release notes...", agent="release-notes")
        messages = [
            {"role": "system", "content": self.SYSTEM},
            {"role": "user", "content": (
                f"TASK DESCRIPTION:\n{task}\n\n"
                f"FILES CHANGED:\n" + "\n".join(f"- {f}" for f in files_changed)
                + (f"\n\nDIFF:\n{diff[:8000]}" if diff else "")
                + "\n\nGenerate the release notes.")}
        ]
        model = MODEL_SINGLE if AGENT_MODE == "single" else MODEL_PLANNER
        raw, _ = call_model(messages, model, tokens_budget,
                            phase="release-notes", purpose="generate release notes")
        return raw


# ══════════════════════════════════════════════════════════════════════════════
# ORCHESTRATOR
# ══════════════════════════════════════════════════════════════════════════════
class Orchestrator:
    MAX_REVIEW_LOOPS = 2

    def __init__(self):
        self.state = AgentState.IDLE
        self.planner = PlannerAgent()
        self.coder = CoderAgent()
        self.relnotes = ReleaseNotesGenerator()
        self.router = ToolRouter()
        self.total_tokens = 0
        self.reasoning = []

    def _transition(self, new_state: AgentState, msg: str):
        self.state = new_state
        write_progress(new_state.value, msg, self.total_tokens,
                       extra={"state": new_state.value})

    def run(self, task: str) -> dict:
        start_time = time.time()
        result = {"task": task, "files": {}, "release_notes": ""}

        if BUDGET.enabled:
            print("\n" + "=" * 60)
            print(f"💰 TOTAL BUDGET: {BUDGET.total:,} tokens")
            BUDGET.allocate("tools", 0.05)
            BUDGET.allocate("planning", 0.10)
            BUDGET.allocate("coding", 0.50)
            BUDGET.allocate("reviewing", 0.15)
            BUDGET.allocate("refactoring", 0.10)
            BUDGET.allocate("release-notes", 0.05)
            BUDGET.allocate("reserve", 0.05)
            print("=" * 60 + "\n")

        self._transition(AgentState.FETCHING, "🌐 Fetching internet context...")
        tool_ctx = self.router.analyze_and_fetch(task, 512)

        repo_ctx = REPO_CONTEXT

        self._transition(AgentState.PLANNING, f"📐 Planner decomposing: {task[:60]}...")
        budget_per_call = BUDGET.get_max_tokens(10) if BUDGET.enabled else MAX_TOKENS
        plan = self.planner.decompose(task, repo_ctx, tool_ctx, budget_per_call)
        self.total_tokens += plan.get("_tokens", 0)
        self.reasoning.append({"agent": "planner", "phase": "planning",
                               "content": plan.get("summary", task)[:1200],
                               "tokens": plan.get("_tokens", 0)})
        write_progress("planning", f"✅ Plan ready: {len(plan.get('steps', []))} steps",
                       self.total_tokens, "planner",
                       extra={"plan": plan.get("summary", "")})

        self._transition(AgentState.CODING, "⚡ Coder implementing plan...")
        code_budget = BUDGET.get_max_tokens(5) if BUDGET.enabled else MAX_TOKENS
        code_result = self.coder.implement(plan, repo_ctx, tool_ctx, "", code_budget)
        self.total_tokens += code_result.get("_tokens", 0)
        files = code_result.get("files", {})
        self.reasoning.append({"agent": "coder", "phase": "coding",
                               "content": f"Generated {len(files)} file(s): " +
                                          ", ".join(list(files)[:10]),
                               "tokens": code_result.get("_tokens", 0)})

        for loop in range(self.MAX_REVIEW_LOOPS):
            if BUDGET.is_exhausted():
                print("💰 Budget exhausted — skipping review loop")
                break
            self._transition(AgentState.REVIEWING, f"🔍 Planner reviewing (pass {loop + 1})...")
            review = self.planner.review(task, files, budget_per_call)
            self.total_tokens += review.get("_tokens", 0)
            self.reasoning.append({"agent": "planner", "phase": "review",
                                   "content": review.get("feedback", review.get("_raw", "")),
                                   "tokens": review.get("_tokens", 0),
                                   "approved": review.get("approved"),
                                   "score": review.get("score")})
            if review.get("approved", True) or review.get("score", 10) >= 7:
                write_progress("reviewing",
                               f"✅ Code approved (score: {review.get('score', '-')})",
                               self.total_tokens, "planner")
                break
            if BUDGET.is_exhausted():
                break
            self._transition(AgentState.CODING,
                             f"🔧 Coder refactoring: {review.get('feedback', '')[:60]}")
            refactor = self.coder.refactor(files, review.get("feedback", ""), code_budget)
            self.total_tokens += refactor.get("_tokens", 0)
            self.reasoning.append({"agent": "coder", "phase": "refactor",
                                   "content": "Applied reviewer feedback: " +
                                              review.get("feedback", "")[:1000],
                                   "tokens": refactor.get("_tokens", 0)})
            files = refactor.get("files", files)

        result["files"] = files

        if not BUDGET.is_exhausted():
            self._transition(AgentState.RELEASING, "📝 Generating release notes...")
            notes = self.relnotes.generate("", task, list(files.keys()), 1024)
            result["release_notes"] = notes
            write_progress("releasing", "✅ Release notes ready",
                           self.total_tokens, "release-notes",
                           extra={"release_notes": notes})

        elapsed = round(time.time() - start_time, 1)
        self._transition(AgentState.DONE, f"🎉 Done in {elapsed}s | {self.total_tokens} tokens")
        result["elapsed"] = elapsed
        result["total_tokens"] = self.total_tokens
        result["reasoning"] = self.reasoning
        return result


# ══════════════════════════════════════════════════════════════════════════════
# SAVE & ZIP
# ══════════════════════════════════════════════════════════════════════════════
def save_outputs(files: dict, release_notes: str = "", reasoning: list = None):
    for fname, content in files.items():
        safe = fname.lstrip("/").replace("..", "__")
        out_path = os.path.join(OUTPUT_DIR, safe)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"📄 {out_path}")
    if release_notes:
        with open(f"{OUTPUT_DIR}/_release_notes.md", "w", encoding="utf-8") as f:
            f.write(release_notes)
    budget_report = BUDGET.report()
    with open(f"{OUTPUT_DIR}/_budget_report.json", "w", encoding="utf-8") as f:
        json.dump(budget_report, f, indent=2, ensure_ascii=False)
    toolkit = APIToolkit()
    tools = toolkit.available_tools()
    with open(f"{OUTPUT_DIR}/_tools_status.json", "w", encoding="utf-8") as f:
        json.dump(tools, f, indent=2)
    if reasoning:
        with open(f"{OUTPUT_DIR}/_reasoning.json", "w", encoding="utf-8") as f:
            json.dump(reasoning, f, indent=2, ensure_ascii=False)


def create_zip() -> str:
    """Create ZIP archive of all generated files."""
    zip_path = f"{OUTPUT_DIR}.zip"
    file_count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(OUTPUT_DIR):
            for file in files:
                file_path = os.path.join(root, file)
                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    arcname = os.path.relpath(file_path, OUTPUT_DIR)
                    zf.write(file_path, arcname)
                    file_count += 1
                    print(f"  📦 Added: {arcname}")
    if file_count == 0:
        print("⚠️  No files to add to ZIP, creating placeholder")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("README.txt", "No files were generated in this run.")
    size = os.path.getsize(zip_path)
    print(f"📦 Created ZIP: {zip_path} ({file_count} files, {size:,} bytes)")
    return zip_path


# ══════════════════════════════════════════════════════════════════════════════
# SINGLE-AGENT PATH
# ══════════════════════════════════════════════════════════════════════════════
def run_single_agent():
    print(f"🤖 Single-agent mode | Model: {MODEL_SINGLE}")
    print(f"📝 Task: {PROMPT}")

    # Skip Ollama check for external models
    if not is_external_model(MODEL_SINGLE):
        if not ollama_ready(90):
            print("❌ Ollama not ready")
            sys.exit(1)
        print("✅ Ollama ready")
    else:
        print(f"🌐 Using external model: {MODEL_SINGLE}")

    if BUDGET.enabled:
        print("\n" + "=" * 60)
        print(f"💰 TOTAL BUDGET: {BUDGET.total:,} tokens")
        print("=" * 60 + "\n")

    reasoning = []
    write_progress("fetching", "Fetching optional internet context", 0,
                   agent="tools", extra={"state": "fetching"})
    tool_ctx = ""
    if ENABLE_TOOLS:
        router = ToolRouter()
        tool_ctx = router.analyze_and_fetch(PROMPT, 512)
    reasoning.append({
        "agent": "tools", "phase": "fetching",
        "content": "Internet context collected" if tool_ctx else "No external context was needed",
        "tokens": 0,
    })

    budget_left = TOTAL_BUDGET or (MAX_TOKENS * ITERATIONS)
    total_tokens = 0
    output_parts = []

    is_simple = len(PROMPT) < 150 and not any(
        w in PROMPT.lower() for w in ["рефактор", "архитектуру", "api", "интеграц", "refactor"]
    )

    if is_simple:
        system_content = (
            "You are a helpful assistant. Complete the task directly and concisely. "
            "Output ONLY the file content, no explanations, no markdown fences "
            "unless the task requires multiple files."
            + (UNCENSORED_ADDENDUM if UNCENSORED else ""))
    else:
        system_content = (
            "You are an expert software engineer. Write complete, production-ready code."
            + (UNCENSORED_ADDENDUM if UNCENSORED else ""))

    messages = [{"role": "system", "content": system_content}]
    if REPO_CONTEXT:
        messages[0]["content"] += f"\n\nREPO CONTEXT:\n{REPO_CONTEXT[:20000]}"
    if tool_ctx:
        messages[0]["content"] += f"\n\n{tool_ctx[:6000]}"

    user_msg = PROMPT
    if ATTACHED_CONTENT:
        ext = os.path.splitext(FILE_NAME)[1].lstrip(".") or "txt"
        user_msg = (f"```{ext}\n# {FILE_NAME}\n{ATTACHED_CONTENT[:60000]}\n```\n\n" + PROMPT)
    messages.append({"role": "user", "content": user_msg})

    for i in range(max(1, ITERATIONS)):
        if BUDGET.is_exhausted():
            print("💰 Budget exhausted — stopping iterations")
            break
        write_progress("coding", f"Generating iteration {i + 1}/{ITERATIONS}", total_tokens,
                       agent="coder", extra={"state": "coding", "iteration": i + 1})
        budget = min(MAX_TOKENS, budget_left, BUDGET.get_max_tokens(ITERATIONS - i))
        raw, used = call_model(messages, MODEL_SINGLE, budget,
                               phase="coding", purpose=f"iteration {i + 1}/{ITERATIONS}")
        total_tokens += used
        budget_left -= used
        output_parts.append(raw)
        reasoning.append({
            "agent": "coder", "phase": f"iteration-{i + 1}",
            "content": f"Generated iteration {i + 1}; output length: {len(raw)} characters",
            "tokens": used,
        })
        messages.append({"role": "assistant", "content": raw})
        if budget_left <= 0:
            break
        if ITERATIONS > 1:
            messages.append({"role": "user", "content": "Continue."})

    output = "\n\n".join(output_parts)

    # Parse ```filename: ... ``` blocks
    files = {}
    for match in re.finditer(r'```(?:filename:\s*)?([^\n`]+)\n([\s\S]*?)```', output):
        fname = match.group(1).strip().lstrip("filename:").strip()
        files[fname] = match.group(2)

    if not files:
        clean = re.sub(r'^```[a-z]*\n', '', output)
        clean = re.sub(r'\n```\s*$', '', clean)
        files[FILE_NAME or "output.txt"] = clean.strip()

    print(f"📄 Generated {len(files)} file(s): {list(files.keys())}")

    notes = ""
    if not BUDGET.is_exhausted():
        write_progress("releasing", "Generating release notes", total_tokens,
                       agent="release-notes", extra={"state": "releasing"})
        gen = ReleaseNotesGenerator()
        notes = gen.generate("", PROMPT, list(files.keys()))

    save_outputs(files, notes, reasoning)
    write_progress("done", f"✅ Done | {total_tokens} tokens", total_tokens,
                   extra={"release_notes": notes, "reasoning_steps": len(reasoning)})
    return {"files": files, "total_tokens": total_tokens,
            "reasoning": reasoning, "release_notes": notes}


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════
def main():
    print("=" * 60)
    now = datetime.datetime.now(datetime.timezone.utc)
    print(f"  VIBE-CODE v3  |  mode={AGENT_MODE}  |  {now:%Y-%m-%d %H:%M}")
    print("=" * 60)

    if not PROMPT:
        print("❌ No PROMPT provided")
        sys.exit(1)

    # ── Handle simple greetings without calling LLM ──────────────────────────
    # ONLY exact greeting matches trigger direct response (fixed: no len() check!)
    simple_greetings = [
        "привет", "hi", "hello", "здравствуй", "здравствуйте",
        "хай", "hello world", "hey", "йо", "ку", "privet", "privetik",
    ]
    prompt_lower = PROMPT.strip().lower().rstrip("!?. ")
    
    if prompt_lower in simple_greetings:
        print("\n👋 Simple greeting detected — responding directly")
        response = (
            f"Привет! 👋\n\nЯ VIBE-CODE v3. Напиши задачу:\n"
            f"- Создай файл index.html с кнопкой\n"
            f"- Напиши Python скрипт для парсинга CSV\n"
            f"- Сделай REST API на FastAPI\n"
            f"- Напиши код змейки на Python\n\n"
            f"Ваше сообщение: \"{PROMPT}\""
        )
        files = {"reply.txt": response}
        save_outputs(files, "", [])
        create_zip()
        return
    
    # ── Check for task-like keywords to proceed with generation ──────────────
    task_keywords = [
        "напиши", "создай", "сделай", "добавь", "исправь", "переделай",
        "write", "create", "make", "add", "fix", "implement", "build",
        "код", "скрипт", "программу", "функцию", "класс", "api",
        "code", "script", "program", "function", "class", "game",
        "змейк", "тетрис", "калькулятор", "чат", "бот", "сайт",
        "snake", "tetris", "calculator", "chat", "bot", "website",
    ]
    
    has_task_keyword = any(kw in prompt_lower for kw in task_keywords)
    
    if not has_task_keyword and len(PROMPT.strip()) < 30:
        print("\n⚠️  Prompt looks unclear — asking for clarification")
        response = (
            f"Я не совсем понял задачу. Попробуй сформулировать конкретнее:\n\n"
            f"Примеры хороших промптов:\n"
            f"- \"Напиши код змейки на Python с pygame\"\n"
            f"- \"Создай калькулятор на JavaScript\"\n"
            f"- \"Сделай REST API на FastAPI с авторизацией\"\n\n"
            f"Твой промпт: \"{PROMPT}\""
        )
        files = {"reply.txt": response}
        save_outputs(files, "", [])
        create_zip()
        return
    
    print(f"📝 Task detected, proceeding with generation...")

    toolkit = APIToolkit()
    active = [t["name"] for t in toolkit.available_tools() if t["active"]]
    print(f"🔌 Active tools ({len(active)}): {', '.join(active[:8])}"
          f"{'...' if len(active) > 8 else ''}")
    print()

    # Check Ollama only if using local models
    uses_local = not (is_external_model(MODEL_SINGLE) or 
                      is_external_model(MODEL_PLANNER) or 
                      is_external_model(MODEL_CODER))
    if uses_local:
        if not ollama_ready(120):
            print("❌ Ollama not ready after 2 min")
            sys.exit(1)
        print("✅ Ollama ready\n")

    if AGENT_MODE == "multi":
        print(f"🧠 Planner : {MODEL_PLANNER}")
        print(f"⚡ Coder   : {MODEL_CODER}")
        print()
        orc = Orchestrator()
        result = orc.run(PROMPT)
        save_outputs(result.get("files", {}),
                     result.get("release_notes", ""),
                     result.get("reasoning", []))
    else:
        run_single_agent()

    # Create ZIP
    create_zip()

    # Final budget summary
    print("\n" + "=" * 60)
    print("💰 FINAL BUDGET REPORT")
    print("=" * 60)
    report = BUDGET.report()
    print(f"  Total:       {report['total']:>10,} tokens")
    print(f"  Used:        {report['used']:>10,} tokens ({report['utilization_pct']:.1f}%)")
    print(f"  Remaining:   {report['remaining']:>10,} tokens")
    print(f"  Num calls:   {report['num_calls']:>10}")
    if report['allocations']:
        print("\n  Allocations:")
        for phase, amount in report['allocations'].items():
            print(f"    {phase:<16} {amount:>10,} tokens")
    print("=" * 60)


if __name__ == "__main__":
    main()