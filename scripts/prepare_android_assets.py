#!/usr/bin/env python3
"""
scripts/prepare_android_assets.py — Bundle web app into Android assets directory
─────────────────────────────────────────────────────────────────────────────
"""

import os
import shutil
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET_DIR = os.path.join(BASE_DIR, "android", "app", "src", "main", "assets", "www")

def main():
    os.makedirs(TARGET_DIR, exist_ok=True)
    
    src_html = os.path.join(BASE_DIR, "index.html")
    dst_html = os.path.join(TARGET_DIR, "index.html")
    if os.path.exists(src_html):
        shutil.copy2(src_html, dst_html)
        print(f"✅ Synced index.html -> {dst_html}")
    
    src_admin = os.path.join(BASE_DIR, "admin_panel.html")
    dst_admin = os.path.join(TARGET_DIR, "admin_panel.html")
    if os.path.exists(src_admin):
        shutil.copy2(src_admin, dst_admin)
        print(f"✅ Synced admin_panel.html -> {dst_admin}")
        
    src_public = os.path.join(BASE_DIR, "public")
    dst_public = os.path.join(TARGET_DIR, "public")
    if os.path.exists(src_public):
        if os.path.exists(dst_public):
            shutil.rmtree(dst_public)
        shutil.copytree(src_public, dst_public)
        print(f"✅ Synced public/ -> {dst_public}")

    print(f"🚀 Android web assets ready in {TARGET_DIR}")

if __name__ == "__main__":
    main()
