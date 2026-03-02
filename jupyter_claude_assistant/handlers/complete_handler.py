"""
Complete Handler - Code completion and next-cell suggestions.
POST /jupyter-claude/complete
"""

import logging
import tornado
from .base_handler import BaseClaudeHandler

logger = logging.getLogger(__name__)


class CompleteHandler(BaseClaudeHandler):
    """Handle code completion requests."""

    @tornado.web.authenticated
    async def post(self):
        """
        POST /jupyter-claude/complete
        Body: {
            "code": "import pandas as pd\ndf = pd.read_",  // Partial code
            "cells": [...],                                  // Notebook cells for context
            "current_cell": 3,                              // Current cell index
            "mode": "complete" | "next_cell"               // Completion mode
        }
        """
        try:
            body = self.get_json_body()
            code = body.get("code", "").strip()
            cells = body.get("cells", [])
            current_cell = body.get("current_cell", -1)
            mode = body.get("mode", "complete")
            goal = body.get("goal", "")

            notebook_context = self.get_notebook_context(cells, current_cell) if cells else ""
            conda_env, packages = self.get_env_info()

            if mode == "next_cell":
                response = self.claude.suggest_next_cell(
                    notebook_context=notebook_context,
                    goal=goal,
                )
                request_type = "next_cell"
            else:
                if not code:
                    self.write_error_json("Code is required for completion mode", 400)
                    return
                response = self.claude.complete_cell(
                    partial_code=code,
                    notebook_context=notebook_context,
                )
                request_type = "complete"

            await self.handle_claude_request(request_type, code or goal, response)

            self.write_json({
                "success": True,
                "response": response,
                "mode": mode,
            })

        except ValueError as e:
            self.write_error_json(str(e), 400)
        except Exception as e:
            logger.error(f"Complete handler error: {e}", exc_info=True)
            self.write_error_json(f"Error: {str(e)}")
