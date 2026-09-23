#!/usr/bin/env python3
"""
src/main.py — Main CLI entry point for VIBE-CODE Workspace Engine
"""
import sys
import json
import argparse
from src.workspace_engine import WorkspaceEngine

def main():
    parser = argparse.ArgumentParser(description="VIBE-CODE Workspace Engine CLI")
    parser.add_argument("--prompt", "-p", default="Build production ready application", help="Task prompt")
    parser.add_argument("--workspace", "-w", default=".", help="Target workspace directory")
    args = parser.parse_args()

    engine = WorkspaceEngine(workspace_path=args.workspace, prompt=args.prompt)
    summary = engine.execute_workflow()
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()
