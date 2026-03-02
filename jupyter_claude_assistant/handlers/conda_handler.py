"""
Conda Handler - Environment information endpoints.
GET /jupyter-claude/conda
"""

import logging
import tornado
from .base_handler import BaseClaudeHandler

logger = logging.getLogger(__name__)


class CondaHandler(BaseClaudeHandler):
    """Handle conda environment information requests."""

    @tornado.web.authenticated
    async def get(self):
        """
        GET /jupyter-claude/conda
        Returns info about the active conda environment and all available environments.
        """
        try:
            active = self.conda.get_active_environment()
            environments = self.conda.list_environments()
            packages = self.conda.get_installed_packages()
            summary = self.conda.get_env_summary()

            self.write_json({
                "success": True,
                "active": active,
                "environments": environments,
                "packages": packages[:50],  # Limit response size
                "total_packages": len(packages),
                "summary": summary,
            })

        except Exception as e:
            logger.error(f"Conda handler error: {e}", exc_info=True)
            self.write_error_json(f"Error getting conda info: {str(e)}")
