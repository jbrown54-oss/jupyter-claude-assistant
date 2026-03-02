"""
Memory Handler - Access and manage the local memory/skills database.
GET/POST /jupyter-claude/memory
"""

import logging
import tornado
from .base_handler import BaseClaudeHandler

logger = logging.getLogger(__name__)


class MemoryHandler(BaseClaudeHandler):
    """Handle memory/skills database requests."""

    @tornado.web.authenticated
    async def get(self):
        """
        GET /jupyter-claude/memory
        Query params:
            type: "stats" | "skills" | "recent" | "snippets"
            query: search query (for skills/snippets)
        """
        try:
            query_type = self.get_query_argument("type", "stats")
            query = self.get_query_argument("query", "")

            if query_type == "stats":
                stats = self.memory.get_stats()
                prefs = self.memory.get_all_preferences()
                self.write_json({"success": True, "stats": stats, "preferences": prefs})

            elif query_type == "skills":
                if query:
                    skills = self.memory.search_skills(query)
                else:
                    skills = self.memory.get_all_skills()
                self.write_json({"success": True, "skills": skills})

            elif query_type == "recent":
                limit = int(self.get_query_argument("limit", "10"))
                interactions = self.memory.get_recent_interactions(limit=limit)
                self.write_json({"success": True, "interactions": interactions})

            elif query_type == "snippets":
                snippets = self.memory.search_snippets(query) if query else []
                self.write_json({"success": True, "snippets": snippets})

            else:
                self.write_error_json(f"Unknown type: {query_type}", 400)

        except Exception as e:
            logger.error(f"Memory GET handler error: {e}", exc_info=True)
            self.write_error_json(f"Error: {str(e)}")

    @tornado.web.authenticated
    async def post(self):
        """
        POST /jupyter-claude/memory
        Body: {
            "action": "save_skill" | "save_snippet" | "rate" | "set_preference",
            ...action-specific fields...
        }
        """
        try:
            body = self.get_json_body()
            action = body.get("action", "")

            if action == "save_skill":
                self.memory.save_skill(
                    name=body["name"],
                    description=body["description"],
                    code_template=body["code_template"],
                    tags=body.get("tags", []),
                )
                self.write_json({"success": True, "message": "Skill saved"})

            elif action == "save_snippet":
                self.memory.save_snippet(
                    title=body["title"],
                    code=body["code"],
                    tags=body.get("tags", []),
                )
                self.write_json({"success": True, "message": "Snippet saved"})

            elif action == "rate":
                self.memory.rate_interaction(
                    interaction_id=body["id"],
                    rating=body["rating"],
                )
                self.write_json({"success": True, "message": "Rating saved"})

            elif action == "set_preference":
                self.memory.set_preference(body["key"], body["value"])
                self.write_json({"success": True, "message": "Preference saved"})

            else:
                self.write_error_json(f"Unknown action: {action}", 400)

        except KeyError as e:
            self.write_error_json(f"Missing required field: {e}", 400)
        except Exception as e:
            logger.error(f"Memory POST handler error: {e}", exc_info=True)
            self.write_error_json(f"Error: {str(e)}")
