# 📁 VIBE-CODE Workspace Autonomous Architecture

## 1. Overview
The **Workspace Autonomous Architecture** replaces single-file code dumps with an iterative workspace pipeline:
- Scans existing project source code and AST dependency hierarchies.
- Plans modular file decomposition (e.g. `models.py`, `engine.py`, `main.py`, `test_app.py`).
- Generates a real-time `TODO.md` progress checklist with status markers (`[ ]`, `[>]`, `[x]`).
- Automatically runs syntax audits and unit test suites before publishing.
- Synchronizes output artifacts with the private storage repository `B3B3097/Storage-VIBE-CODE`.

## 2. Core Modules
- `src/workspace_engine.py`: Master orchestrator managing `WorkspaceScanner`, `TaskPlanner`, and `CodeValidator`.
- `generate.py`: Direct Ollama / AI inference harness configured with 131,072 uncapped context window tokens.
- `src/private_storage.py`: Secure bridge to private storage with secret sanitization and checksum audits.
- `admin_panel.html` & `src/admin_auth.py`: Role-restricted administration interface.

## 3. Workflow Lifecycle
1. **Discovery**: `WorkspaceScanner` identifies all workspace files and parses AST symbols.
2. **Decomposition**: `TaskPlanner` creates sequential, trackable development tasks.
3. **Synthesis**: LLM constructs code adhering to domain boundaries.
4. **Validation**: Test runner verifies all test assertions pass.
5. **Checklist Update**: `TODO.md` is updated with completed checkmarks `[x]`.
6. **Replication**: All modified files and chat logs are backed up to private storage.
