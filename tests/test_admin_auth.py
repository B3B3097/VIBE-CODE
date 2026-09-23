#!/usr/bin/env python3
"""
tests/test_admin_auth.py — Unit tests for admin authentication and role enforcement
"""

import sys
import unittest
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.admin_auth import AdminAuthenticator


class TestAdminAuth(unittest.TestCase):
    def setUp(self):
        self.auth = AdminAuthenticator()

    def test_admin_credentials_success(self):
        self.assertTrue(self.auth.verify_credentials("admin", "admin_vibe_2026!"))
        self.assertTrue(self.auth.verify_credentials("B3B3097", "admin123"))
        self.assertTrue(self.auth.verify_credentials("admin", "ghp_123456789012345678901234567890123456"))

    def test_regular_user_rejected(self):
        self.assertFalse(self.auth.verify_credentials("guest_user", "admin_vibe_2026!"))
        self.assertFalse(self.auth.verify_credentials("admin", "wrong_password"))
        self.assertFalse(self.auth.verify_credentials("", ""))

    def test_token_creation_and_validation(self):
        tok = self.auth.create_admin_token("admin")
        self.assertTrue(tok.startswith("admin_token_"))
        username = self.auth.validate_token(tok)
        self.assertEqual(username, "admin")

    def test_tampered_token_rejected(self):
        tok = self.auth.create_admin_token("admin")
        tampered = tok[:-4] + "abcd"
        self.assertIsNone(self.auth.validate_token(tampered))

    def test_is_admin_user_check(self):
        self.assertTrue(self.auth.is_admin_user({"is_owner": True}))
        self.assertTrue(self.auth.is_admin_user({"role": "admin"}))
        self.assertTrue(self.auth.is_admin_user({"github_login": "B3B3097"}))
        self.assertFalse(self.auth.is_admin_user({"github_login": "random_user", "is_owner": False}))


if __name__ == "__main__":
    unittest.main()
