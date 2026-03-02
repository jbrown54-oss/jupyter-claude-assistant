"""
Fix Handler - Suggest fixes for code errors.
POST /jupyter-claude/fix
"""

import logging
import tornado
from .base_handler import BaseClaudeHandler

logger = logging.getLogger(__name__)


class FixHandler(BaseClaudeHandler):
    """Handle code fix requests."""

    @tornado.web.authenticated
    async def post(self):
        """
        POST /jupyter-claude/fix
        Body: {
            "code": "df.groupby('col').agger({'val': 'mean'})",
            "error": "AttributeError: 'DataFrameGroupBy' object has no attribute 'agger'",
            "cells": [...]  // Optional notebook context
        }
        """
        try:
            body = self.get_json_body()
            code = body.get("code", "").strip()
            error = body.get("error", "").strip()

            if not code or not error:
                self.write_error_json("Both code and error are required", 400)
                return

            cells = body.get("cells", [])
            notebook_context = self.get_notebook_context(cells) if cells else ""

            response = self.claude.suggest_fix(
                code=code,
                error=error,
                notebook_context=notebook_context,
            )

            await self.handle_claude_request("fix", f"{code}\nERROR: {error}", response)

            self.write_json({
                "success": True,
                "response": response,
            })

        except ValueError as e:
            self.write_error_json(str(e), 400)
        except Exception as e:
            logger.error(f"Fix handler error: {e}", exc_info=True)
            self.write_error_json(f"Error: {str(e)}")
