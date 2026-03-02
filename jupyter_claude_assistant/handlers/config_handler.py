"""
Config Handler - Get and set extension configuration.
GET/POST /jupyter-claude/config
"""

import os
import logging
import tornado
from .base_handler import BaseClaudeHandler
from ..handlers.base_handler import get_services, _claude

logger = logging.getLogger(__name__)


class ConfigHandler(BaseClaudeHandler):
    """Handle configuration requests."""

    @tornado.web.authenticated
    async def get(self):
        """
        GET /jupyter-claude/config
        Returns current configuration.
        """
        try:
            prefs = self.memory.get_all_preferences()
            has_api_key = bool(
                os.environ.get("ANTHROPIC_API_KEY") or
                self.memory.get_preference("api_key")
            )

            self.write_json({
                "success": True,
                "has_api_key": has_api_key,
                "model": prefs.get("model", "claude-sonnet-4-6"),
                "preferences": prefs,
            })

        except Exception as e:
            logger.error(f"Config GET handler error: {e}", exc_info=True)
            self.write_error_json(f"Error: {str(e)}")

    @tornado.web.authenticated
    async def post(self):
        """
        POST /jupyter-claude/config
        Body: {
            "api_key": "sk-ant-...",   // Optional: set API key
            "model": "claude-opus-4-6", // Optional: change model
            "preferences": {...}        // Optional: update preferences
        }
        """
        try:
            body = self.get_json_body()

            if "api_key" in body:
                # Update the API key in the Claude service
                self.claude.set_api_key(body["api_key"])
                self.memory.set_preference("api_key_configured", True)
                logger.info("API key updated")

            if "model" in body:
                self.claude.model = body["model"]
                self.memory.set_preference("model", body["model"])

            if "preferences" in body:
                for key, value in body["preferences"].items():
                    self.memory.set_preference(key, value)

            self.write_json({"success": True, "message": "Configuration updated"})

        except Exception as e:
            logger.error(f"Config POST handler error: {e}", exc_info=True)
            self.write_error_json(f"Error: {str(e)}")
