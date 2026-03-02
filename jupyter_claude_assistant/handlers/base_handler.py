"""
Base handler with common functionality for all Jupyter Claude handlers.
"""

import json
import logging
from jupyter_server.base.handlers import APIHandler
from tornado.web import HTTPError, authenticated

from ..services.claude_service import ClaudeService
from ..services.conda_service import CondaService
from ..services.memory_service import MemoryService
from ..services.search_service import SearchService

logger = logging.getLogger(__name__)

# Singletons shared across handlers
_claude = None
_conda = None
_memory = None
_search = None


def get_services():
    """Get or initialize shared service singletons."""
    global _claude, _conda, _memory, _search

    if _memory is None:
        _memory = MemoryService()

    if _conda is None:
        _conda = CondaService()

    if _search is None:
        _search = SearchService(memory_service=_memory)

    if _claude is None:
        import os
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        model = _memory.get_preference("model", "claude-sonnet-4-6")
        _claude = ClaudeService(api_key=api_key, model=model)

    return _claude, _conda, _memory, _search


class BaseClaudeHandler(APIHandler):
    """Base handler providing shared services and utility methods."""

    @property
    def claude(self) -> ClaudeService:
        return get_services()[0]

    @property
    def conda(self) -> CondaService:
        return get_services()[1]

    @property
    def memory(self) -> MemoryService:
        return get_services()[2]

    @property
    def search_svc(self) -> SearchService:
        return get_services()[3]

    def get_json_body(self) -> dict:
        """Parse JSON request body."""
        try:
            return json.loads(self.request.body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise HTTPError(400, "Invalid JSON in request body")

    def write_json(self, data: dict, status: int = 200):
        """Write JSON response."""
        self.set_status(status)
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(data))

    def write_error_json(self, message: str, status: int = 500):
        """Write JSON error response."""
        self.write_json({"error": message, "success": False}, status)

    def get_notebook_context(self, cells: list, current_index: int = -1) -> str:
        """Build notebook context from cells."""
        return self.claude.build_notebook_context(cells, current_index)

    def get_env_info(self, env_name: str = None) -> tuple[str, list[str]]:
        """Get conda environment name and package list."""
        env = self.conda.get_active_environment()
        env_name = env_name or env["name"]
        packages = self.conda.get_package_names(env_name)
        return env_name, packages

    async def handle_claude_request(self, request_type: str, prompt: str, response: str):
        """Save interaction to memory after a successful Claude request."""
        try:
            env, _ = self.get_env_info()
            self.memory.save_interaction(
                request_type=request_type,
                prompt=prompt,
                response=response,
                conda_env=env,
            )
        except Exception as e:
            logger.warning(f"Failed to save interaction to memory: {e}")
