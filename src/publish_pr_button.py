"""
src/publish_pr_button.py — Helper module and metadata for GitHub PR button integration
"""

from typing import Dict, Any

ICON_PATH = "assets/github-icon.png"
CSS_SNIPPET = """
.element {
  background-clip: padding-box;
}
"""

def get_publish_button_config() -> Dict[str, Any]:
    """Returns frontend configuration and default styling for the PR button."""
    return {
        "icon_path": ICON_PATH,
        "label": "Опубликовать изменения (PR)",
        "tooltip": "Создать Pull Request с изменениями модели в GitHub",
        "css": CSS_SNIPPET.strip()
    }


