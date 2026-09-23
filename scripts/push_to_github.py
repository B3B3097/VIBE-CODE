#!/usr/bin/env python3
"""
scripts/push_to_github.py — Securely push commits to GitHub using a personal access token (PAT)
─────────────────────────────────────────────────────────────────────────────
Usage:
    python3 scripts/push_to_github.py [GITHUB_TOKEN]

Environment Variables:
    GITHUB_TOKEN or GH_TOKEN
"""

import os
import sys
import subprocess
import re

REPO = "B3B3097/VIBE-CODE"
REMOTE_CLEAN = f"https://github.com/{REPO}.git"


def get_token() -> str:
    if len(sys.argv) > 1 and sys.argv[1].strip():
        return sys.argv[1].strip()
    return os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or ""


def sanitize(text: str, token: str) -> str:
    if not token:
        return text
    return text.replace(token, "[REDACTED_TOKEN]")


def run_cmd(cmd: list, token: str = "") -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        err_msg = sanitize(proc.stderr or proc.stdout, token)
        print(f"❌ Error: {err_msg.strip()}")
    return proc


def ensure_git_setup():
    # Ensure git repo is initialized
    is_git = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], capture_output=True, text=True)
    if is_git.returncode != 0:
        subprocess.run(["git", "init", "-b", "main"], capture_output=True)

    # Ensure user credentials configured
    user_name = subprocess.run(["git", "config", "user.name"], capture_output=True, text=True).stdout.strip()
    if not user_name:
        subprocess.run(["git", "config", "user.name", "B3B3097"], capture_output=True)
        subprocess.run(["git", "config", "user.email", "welereds@gmail.com"], capture_output=True)


def main():
    token = get_token()
    if not token:
        print("⚠️ GitHub Token not found.")
        print("Please provide your token:")
        print("  1) As an argument: python3 scripts/push_to_github.py ghp_yourTokenHere")
        print("  2) Or set environment variable: export GITHUB_TOKEN=ghp_yourTokenHere")
        sys.exit(1)

    ensure_git_setup()
    auth_remote = f"https://x-access-token:{token}@github.com/{REPO}.git"

    # Commit any uncommitted changes so nothing is lost
    status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
    if status.stdout.strip():
        print("📦 Auto-staging uncommitted changes...")
        subprocess.run(["git", "add", "-A"], capture_output=True)
        subprocess.run(["git", "commit", "-m", "chore: sync latest workspace state before push"], capture_output=True)

    print("🚀 Connecting to GitHub repository B3B3097/VIBE-CODE...")
    try:
        # Check remote origin
        check_remote = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True)
        if check_remote.returncode != 0:
            run_cmd(["git", "remote", "add", "origin", auth_remote], token)
        else:
            run_cmd(["git", "remote", "set-url", "origin", auth_remote], token)

        # Ensure latest main
        print("📥 Fetching latest remote state...")
        fetch = run_cmd(["git", "fetch", "origin", "main"], token)
        if fetch.returncode == 0:
            subprocess.run(["git", "merge", "--no-edit", "origin/main"], capture_output=True)

        # Push branch
        print("📤 Pushing local commits to origin main...")
        push = run_cmd(["git", "push", "origin", "HEAD:main"], token)
        if push.returncode == 0:
            print("✅ Successfully pushed commits to https://github.com/B3B3097/VIBE-CODE")
            # Also push tags
            run_cmd(["git", "push", "origin", "--tags"], token)
            print("🏷️ Pushed release tags to GitHub.")
        else:
            print("❌ Push failed. Output:")
            print(sanitize(push.stderr or push.stdout, token))
            sys.exit(1)
    finally:
        # Always clean remote url so token is not retained in .git/config
        run_cmd(["git", "remote", "set-url", "origin", REMOTE_CLEAN], token)
        print("🔒 Cleaned git remote URL (token sanitized).")


if __name__ == "__main__":
    main()
