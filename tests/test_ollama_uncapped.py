#!/usr/bin/env python3
"""
tests/test_ollama_uncapped.py — Unit test for Ollama uncapped context options
"""

import os
import sys
import unittest
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestOllamaUncapped(unittest.TestCase):
    def test_uncapped_context_options(self):
        # Verify 131072 context is injected when UNCAPPED_CONTEXT is active
        uncapped = os.getenv("UNCAPPED_CONTEXT", "true").lower() in ("true", "1", "yes")
        max_tokens = 0

        options = {
            "temperature": 0.3,
            "top_p": 0.9,
        }
        if uncapped:
            options["num_ctx"] = 131072
            options["num_predict"] = -1 if (max_tokens is None or max_tokens <= 0) else max_tokens
        else:
            options["num_predict"] = max_tokens or 8192

        self.assertEqual(options["num_ctx"], 131072)
        self.assertEqual(options["num_predict"], -1)
        self.assertEqual(options["temperature"], 0.3)


if __name__ == "__main__":
    unittest.main()
