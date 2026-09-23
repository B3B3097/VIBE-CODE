import unittest
from src.publish_pr_button import get_publish_button_config, ICON_PATH, CSS_SNIPPET

class TestPublishPRButton(unittest.TestCase):
    def test_config_structure(self):
        config = get_publish_button_config()
        self.assertIsInstance(config, dict)
        self.assertIn("icon_path", config)
        self.assertIn("label", config)
        self.assertIn("tooltip", config)
        self.assertIn("css", config)
        self.assertEqual(config["icon_path"], ICON_PATH)

    def test_css_snippet(self):
        self.assertIn("background-clip", CSS_SNIPPET)

if __name__ == "__main__":
    unittest.main()
