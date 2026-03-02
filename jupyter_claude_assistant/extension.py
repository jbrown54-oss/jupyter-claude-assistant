"""
Jupyter Server Extension Setup.

Registers all REST API handlers with the Jupyter server.
"""

from jupyter_server.utils import url_path_join


def setup_handlers(web_app):
    """Register all extension handlers."""
    from .handlers.chat_handler import ChatHandler
    from .handlers.complete_handler import CompleteHandler
    from .handlers.explain_handler import ExplainHandler
    from .handlers.fix_handler import FixHandler
    from .handlers.assign_handler import AssignmentHandler
    from .handlers.conda_handler import CondaHandler
    from .handlers.memory_handler import MemoryHandler
    from .handlers.search_handler import SearchHandler
    from .handlers.config_handler import ConfigHandler

    base_url = web_app.settings["base_url"]
    base = url_path_join(base_url, "jupyter-claude")

    handlers = [
        (url_path_join(base, "chat"), ChatHandler),
        (url_path_join(base, "complete"), CompleteHandler),
        (url_path_join(base, "explain"), ExplainHandler),
        (url_path_join(base, "fix"), FixHandler),
        (url_path_join(base, "assignment"), AssignmentHandler),
        (url_path_join(base, "conda"), CondaHandler),
        (url_path_join(base, "memory"), MemoryHandler),
        (url_path_join(base, "search"), SearchHandler),
        (url_path_join(base, "config"), ConfigHandler),
    ]

    web_app.add_handlers(".*$", handlers)
