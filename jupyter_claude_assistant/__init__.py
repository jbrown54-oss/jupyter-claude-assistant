"""
Jupyter Claude Assistant - A JupyterLab extension powered by Claude AI.

This package provides:
- Jupyter server extension with REST API handlers
- Conda environment detection
- Context-aware code completion and assistance
- Local memory/skills database
- Assignment completion mode
"""

from ._version import __version__

def _jupyter_server_extension_points():
    """Return a list of server extension entry points."""
    return [{"module": "jupyter_claude_assistant"}]


def _load_jupyter_server_extension(server_app):
    """Load the server extension."""
    from .extension import setup_handlers
    setup_handlers(server_app.web_app)
    server_app.log.info("Jupyter Claude Assistant server extension loaded.")
