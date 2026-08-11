"""
VIBE-CODE Storage Sync v2 — полноценное приватное хранилище данных.

Что синхронизируется в Storage-VIBE-CODE (private):
  🔑 keys.env        — API ключи (full | masked)
  💬 chats/          — чаты (prompt + файлы + release notes)
  🪙 tokens.json     — ledger токенов ПОЛЬЗОВАТЕЛЯ (НЕ анонимно!)
  👤 profile.json    — профиль и история запусков
  🌍 global/         — глобальная статистика + leaderboard + daily
  📊 README.md       — авто-дашборд "сколько денег сэкономлено"

Финансовая модель:
  saved = tokens/1M * (market_price - our_cheap_price)
"""

import os, sys, json, hashlib, base64, datetime, time
import urllib.request, urllib.error

# ── Config ────────────────────────────────────────────────────────────────────
STORAGE_REPO = os.getenv("STORAGE_REPO", "B3B3097/Storage-VIBE-CODE")
GH_TOKEN     = os.getenv("GH_TOKEN", "")
RUN_ID       = os.getenv("RUN_ID", "unknown")
STORAGE_MODE = os.getenv("STORAGE_MODE", "masked")          # full | masked
OUTPUT_DIR   = os.getenv("OUTPUT_DIR", "/tmp/vibe_output")
PROMPT       = os.getenv("PROMPT", "")
AGENT_MODE   = os.getenv("AGENT_MODE", "single")
MODEL_SINGLE = os.getenv("MODEL_SINGLE", "")
MODEL_CODER  = os.getenv("MODEL_CODER", "")
MODEL_PLANNER= os.getenv("MODEL_PLANNER", "")

# Ваша реальная (дешёвая) цена за 1M токенов, $
OUR_COST_PER_1M = float(os.getenv("OUR_COST_PER_1M", "0.05"))

# Рыночные цены за 1M токенов (среднее input+output), $
MODEL_MARKET_PRICES = {
    "qwen2.5:7b":        0.27,
    "qwen2.5-coder:7b":  0.27,
    "qwen2.5":           0.27,
    "bonsai-27b":        0.80,
    "kimi-k3":           0.60,
    "kimi":              0.60,
    "claude-opus-4":     45.0,
    "claude-sonnet-4":   9.0,
    "claude-3.5-sonnet": 6.0,
    "claude":            9.0,
    "gpt-4o":            6.25,
    "gpt":               6.25,
    "deepseek":          0.27,
    "llama":             0.30,
}
DEFAULT_MARKET_PRICE = 1.0

SENSITIVE_PATTERNS = ["API_KEY", "TOKEN", "SECRET", "WEBHOOK", "SID", "AUTH"]
MAX_RETRIES = 3

NOW = datetime.datetime.now(datetime.timezone.utc)


# ══════════════════════════════════════════════════════════════════════════════
# HTTP / GitHub helpers
# ══════════════════════════════════════════════════════════════════════════════
def _req(url: str, method: str = "GET", data: dict = None, timeout: int = 30):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method, headers={
        "Authorization": f"Bearer {GH_TOKEN}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "vibe-code-storage/2.0",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        return json.loads(raw) if raw else {}


def gh_get_file(path: str):
    """Return file object (with sha/content) or None."""
    try:
        return _req(f"https://api.github.com/repos/{STORAGE_REPO}/contents/{path}")
    except Exception:
        return None


def gh_put_file(path: str, content: str, message: str) -> bool:
    """Create or update file with retry."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            existing = gh_get_file(path)
            data = {
                "message": message,
                "content": base64.b64encode(content.encode("utf-8")).decode(),
                "branch": "main",
            }
            if existing and "sha" in existing:
                data["sha"] = existing["sha"]
            _req(f"https://api.github.com/repos/{STORAGE_REPO}/contents/{path}",
                 "PUT", data)
            print(f"  ✅ {path}")
            return True
        except urllib.error.HTTPError as e:
            print(f"  ⚠️ [{attempt}/{MAX_RETRIES}] PUT {path}: HTTP {e.code}")
            if e.code == 409:      # conflict — retry
                time.sleep(2)
                continue
            return False
        except Exception as e:
            print(f"  ⚠️ [{attempt}/{MAX_RETRIES}] PUT {path}: {e}")
            time.sleep(2)
    return False


def gh_read_json(path: str, default):
    """Read JSON file from storage, return default if missing."""
    obj = gh_get_file(path)
    if obj and "content" in obj:
        try:
            return json.loads(base64.b64decode(obj["content"]).decode("utf-8"))
        except Exception:
            pass
    return default


# ══════════════════════════════════════════════════════════════════════════════
# Identity (НЕ анонимно для статистики)
# ══════════════════════════════════════════════════════════════════════════════
def get_username() -> str:
    """Real GitHub username from token (stats are NOT anonymous)."""
    try:
        me = _req("https://api.github.com/user", timeout=10)
        login = me.get("login", "")
        if login:
            return login
    except Exception:
        pass
    # fallback: hash
    return "anon-" + hashlib.sha256((GH_TOKEN or "x").encode()).hexdigest()[:10]


def safe_folder(name: str) -> str:
    return "".join(c for c in name if c.isalnum() or c in "-_") or "unknown"


USER = safe_folder(get_username())


# ══════════════════════════════════════════════════════════════════════════════
# Money math
# ══════════════════════════════════════════════════════════════════════════════
def market_price(model: str) -> float:
    m = (model or "").lower()
    for key, price in MODEL_MARKET_PRICES.items():
        if m.startswith(key):
            return price
    return DEFAULT_MARKET_PRICE


def compute_costs(tokens: int, model: str) -> dict:
    """market vs our cheap price -> saved money."""
    mp = market_price(model)
    market = tokens / 1_000_000 * mp
    ours   = tokens / 1_000_000 * OUR_COST_PER_1M
    return {
        "tokens": tokens,
        "model": model,
        "market_price_per_1m": mp,
        "our_price_per_1m": OUR_COST_PER_1M,
        "market_cost_usd": round(market, 4),
        "our_cost_usd": round(ours, 4),
        "saved_usd": round(max(0.0, market - ours), 4),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Collectors
# ══════════════════════════════════════════════════════════════════════════════
def mask_value(v: str) -> str:
    if not v:
        return ""
    if len(v) <= 12:
        return "****"
    return v[:4] + "*" * (len(v) - 8) + v[-4:]


def collect_keys() -> dict:
    keys = {}
    for name, value in sorted(os.environ.items()):
        if not value or name == "GH_TOKEN":
            continue
        if any(p in name for p in SENSITIVE_PATTERNS):
            keys[name] = value if STORAGE_MODE == "full" else mask_value(value)
    return keys


def read_budget_report() -> dict:
    path = os.path.join(OUTPUT_DIR, "_budget_report.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def collect_chat(budget: dict) -> dict:
    chat = {
        "run_id": RUN_ID,
        "user": USER,
        "timestamp": NOW.isoformat(),
        "prompt": PROMPT,
        "agent_mode": AGENT_MODE,
        "model": MODEL_SINGLE or MODEL_CODER,
        "tokens_used": budget.get("used", 0),
        "files": [],
        "release_notes": "",
    }
    if os.path.isdir(OUTPUT_DIR):
        for fname in sorted(os.listdir(OUTPUT_DIR)):
            p = os.path.join(OUTPUT_DIR, fname)
            if not os.path.isfile(p):
                continue
            if fname == "_release_notes.md":
                try:
                    chat["release_notes"] = open(p, encoding="utf-8").read()[:20000]
                except Exception:
                    pass
                continue
            if fname.startswith("_"):
                continue
            try:
                chat["files"].append({