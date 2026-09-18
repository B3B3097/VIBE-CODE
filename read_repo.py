#!/usr/bin/env python3
"""
Target Repo / Workspace Context Reader for VIBE-CODE
Reads files from a target repo or local workspace to provide context for code generation.
"""
import sys
import os
import json
import base64
import urllib.request

def read_local_files(dir_path="./workspace", max_bytes=60000):
    content_map = {}
    total_bytes = 0
    for root, _, files in os.walk(dir_path):
        for f in files:
            if f.startswith(".") or f.endswith((".pyc", ".lock", ".bin")):
                continue
            path = os.path.join(root, f)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                    txt = fh.read()
                    content_map[path] = txt
                    total_bytes += len(txt)
                    if total_bytes > max_bytes:
                        break
            except Exception:
                pass
        if total_bytes > max_bytes:
            break
    return content_map

def main():
    target_repo = sys.argv[1] if len(sys.argv) > 1 else ""
    token = sys.argv[2] if len(sys.argv) > 2 else ""
    max_chars = int(sys.argv[3]) if len(sys.argv) > 3 else 60000

    print(f"Reading context for target repo: {target_repo or 'local workspace'}")
    files = read_local_files()
    raw = json.dumps(files, ensure_ascii=False)
    b64 = base64.b64encode(raw.encode("utf-8")).decode("utf-8")
    
    with open("/tmp/repo_context.b64", "w", encoding="utf-8") as f:
        f.write(b64)
    print(f"✅ Saved repo context ({len(raw)} chars, {len(b64)} b64 bytes)")

if __name__ == "__main__":
    main()
