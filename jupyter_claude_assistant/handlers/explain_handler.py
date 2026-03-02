"""
Explain Handler - Explain code cells and their outputs.
POST /jupyter-claude/explain
"""

import logging
import tornado
from .base_handler import BaseClaudeHandler

logger = logging.getLogger(__name__)


class ExplainHandler(BaseClaudeHandler):
    """Handle code explanation requests."""

    @tornado.web.authenticated
    async def post(self):
        """
        POST /jupyter-claude/explain
        Body: {
            "code": "df.groupby('col').agg({'val': 'mean'})",
            "output": "Optional output text",
            "error": "Optional error text"
        }
        """
        try:
            body = self.get_json_body()
            code = body.get("code", "").strip()

            if not code:
                self.write_error_json("Code is required", 400)
                return

            output = body.get("output", "")
            error = body.get("error", "")

            response = self.claude.explain_code(
                code=code,
                output=output,
                error=error,
            )

            await self.handle_claude_request("explain", code, response)

            self.write_json({
                "success": True,
                "response": response,
            })

        except ValueError as e:
            self.write_error_json(str(e), 400)
        except Exception as e:
            logger.error(f"Explain handler error: {e}", exc_info=True)
            self.write_error_json(f"Error: {str(e)}")
