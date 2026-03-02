"""
Search Handler - Search PyPI, GitHub, Stack Overflow.
GET /jupyter-claude/search
"""

import logging
import tornado
from .base_handler import BaseClaudeHandler

logger = logging.getLogger(__name__)


class SearchHandler(BaseClaudeHandler):
    """Handle external search requests."""

    @tornado.web.authenticated
    async def get(self):
        """
        GET /jupyter-claude/search
        Query params:
            q: search query (required)
            source: "all" | "pypi" | "github" | "stackoverflow" (default: "all")
        """
        try:
            query = self.get_query_argument("q", "").strip()
            if not query:
                self.write_error_json("Query parameter 'q' is required", 400)
                return

            source = self.get_query_argument("source", "all")

            if source == "pypi":
                results = {"pypi": self.search_svc.search_pypi(query), "query": query}
            elif source == "github":
                results = {"github": self.search_svc.search_github(query), "query": query}
            elif source == "stackoverflow":
                results = {"stackoverflow": self.search_svc.search_stackoverflow(query), "query": query}
            else:
                results = self.search_svc.search_all(query)

            self.write_json({"success": True, **results})

        except Exception as e:
            logger.error(f"Search handler error: {e}", exc_info=True)
            self.write_error_json(f"Search error: {str(e)}")
