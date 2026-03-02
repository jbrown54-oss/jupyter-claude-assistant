"""
Chat Handler - General-purpose chat with Claude about code/notebooks.
POST /jupyter-claude/chat
"""

import logging
import tornado
from .base_handler import BaseClaudeHandler

logger = logging.getLogger(__name__)


class ChatHandler(BaseClaudeHandler):
    """Handle general chat requests."""

    @tornado.web.authenticated
    async def post(self):
        """
        POST /jupyter-claude/chat
        Body: {
            "message": "How do I read a CSV file?",
            "cells": [...],          // Optional notebook cells for context
            "current_cell": 0,       // Optional index of current cell
            "env_name": "myenv"      // Optional conda env name
        }
        """
        try:
            body = self.get_json_body()
            message = body.get("message", "").strip()

            if not message:
                self.write_error_json("Message is required", 400)
                return

            cells = body.get("cells", [])
            current_cell = body.get("current_cell", -1)
            env_name = body.get("env_name")

            notebook_context = self.get_notebook_context(cells, current_cell) if cells else ""
            conda_env, packages = self.get_env_info(env_name)

            response = self.claude.complete(
                prompt=message,
                notebook_context=notebook_context,
                conda_env=conda_env,
                installed_packages=packages,
            )

            await self.handle_claude_request("chat", message, response)

            self.write_json({
                "success": True,
                "response": response,
                "conda_env": conda_env,
            })

        except ValueError as e:
            self.write_error_json(str(e), 400)
        except Exception as e:
            logger.error(f"Chat handler error: {e}", exc_info=True)
            self.write_error_json(f"Error: {str(e)}")
