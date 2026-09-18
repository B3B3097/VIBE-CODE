# 🔒 Private Storage Synchronization Protocol

## 1. Objective
Ensures that all user interactions, proprietary code, configuration files, and token usage records are continuously preserved in the owner's private storage repository:
- **Repository:** `B3B3097/Storage-VIBE-CODE`
- **Access Model:** Private, authenticated via personal access token (`GH_TOKEN`).

## 2. Protected Data Assets
1. **Chat Transcripts:** `transcripts/chat_*.json` containing sanitized interaction logs.
2. **Workspace Snapshots:** Full multi-file workspace artifacts under `backups/workspace/`.
3. **Usage Reports:** `token_usage.yaml` recording model consumption and billing metrics.
4. **Configuration Manifests:** `config.yaml`, `metadata.json`, and deployment configurations.

## 3. Security & Redaction Safeguards
Before any data packet is replicated to private storage:
- GitHub access tokens (`ghp_*`) are intercepted and replaced with `[REDACTED_GH_TOKEN]`.
- API keys (`sk-*`) are sanitized with `[REDACTED_API_KEY]`.
- All transfers compute SHA-256 integrity hashes to detect partial or corrupted transfers.

## 4. Verification & Sync Commands
To manually trigger storage synchronization:
```bash
python sync_storage.py sync
python src/private_storage.py
```
Or use the **"🔐 Sync Storage"** button in the Workspace Explorer UI.
