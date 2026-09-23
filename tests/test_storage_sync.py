#!/usr/bin/env python3
"""
tests/test_storage_sync.py — Unit tests for private storage synchronization
"""

import os
import sys
import unittest
import tempfile
import shutil
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.private_storage import PrivateStorageManager


class TestPrivateStorageSync(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_storage_")
        os.environ["STORAGE_DIR"] = self.temp_dir
        self.mgr = PrivateStorageManager(target_repo="B3B3097/Storage-VIBE-CODE", token="ghp_test123456789012345678901234567890123456")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_status_report(self):
        status = self.mgr.get_status()
        self.assertEqual(status["target_repository"], "B3B3097/Storage-VIBE-CODE")
        self.assertTrue(status["private"])
        self.assertTrue(status["authenticated"])

    def test_secret_sanitization(self):
        sensitive = "My token is ghp_111122223333444455556666777788889999 and API key sk-abcdef1234567890abcdef1234567890"
        clean = self.mgr._sanitize_secrets(sensitive)
        self.assertNotIn("ghp_111122223333444455556666777788889999", clean)
        self.assertIn("[REDACTED_GH_TOKEN]", clean)
        self.assertIn("[REDACTED_API_KEY]", clean)

    def test_workspace_backup(self):
        ws_test = Path(self.temp_dir) / "test_ws"
        ws_test.mkdir()
        (ws_test / "file1.txt").write_text("Hello private storage")
        (ws_test / "config.yaml").write_text("env: test")

        res = self.mgr.backup_workspace(str(ws_test))
        self.assertTrue(res["success"])
        self.assertEqual(res["files_count"], 2)
        self.assertEqual(res["target_repository"], "B3B3097/Storage-VIBE-CODE")

    def test_chat_transcript_backup(self):
        messages = [
            {"role": "user", "content": "How do I secure my repo?"},
            {"role": "assistant", "content": "Keep token secret: ghp_123456789012345678901234567890123456"}
        ]
        ok = self.mgr.backup_chat_session("chat_001", messages)
        self.assertTrue(ok)
        transcript_file = Path(self.temp_dir) / "transcripts" / "chat_chat_001.json"
        self.assertTrue(transcript_file.exists())
        content = transcript_file.read_text(encoding="utf-8")
        self.assertIn("[REDACTED_GH_TOKEN]", content)


if __name__ == "__main__":
    unittest.main()
