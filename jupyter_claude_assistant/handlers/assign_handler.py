"""
Assignment Handler - Complete full coding assignments.
POST /jupyter-claude/assignment
"""

import json
import logging
import tornado
from .base_handler import BaseClaudeHandler

logger = logging.getLogger(__name__)


class AssignmentHandler(BaseClaudeHandler):
    """Handle assignment completion requests."""

    @tornado.web.authenticated
    async def post(self):
        """
        POST /jupyter-claude/assignment
        Body: {
            "problem": "Build a data pipeline that reads CSV files, cleans the data...",
            "cells": [...],          // Optional existing notebook context
            "env_name": "myenv",     // Optional conda env
            "output_format": "cells" // "cells" or "markdown" (default: "cells")
        }
        Returns:
            Structured response with notebook cells ready to insert.
        """
        try:
            body = self.get_json_body()
            problem = body.get("problem", "").strip()

            if not problem:
                self.write_error_json("Problem statement is required", 400)
                return

            cells = body.get("cells", [])
            env_name = body.get("env_name")
            output_format = body.get("output_format", "cells")

            notebook_context = self.get_notebook_context(cells) if cells else ""
            conda_env, packages = self.get_env_info(env_name)

            response = self.claude.complete_assignment(
                problem_statement=problem,
                notebook_context=notebook_context,
                conda_env=conda_env,
                installed_packages=packages,
            )

            await self.handle_claude_request("assignment", problem, response)

            if output_format == "cells":
                parsed_cells = self._parse_to_cells(response)
                self.write_json({
                    "success": True,
                    "cells": parsed_cells,
                    "raw_response": response,
                    "conda_env": conda_env,
                })
            else:
                self.write_json({
                    "success": True,
                    "response": response,
                    "conda_env": conda_env,
                })

        except ValueError as e:
            self.write_error_json(str(e), 400)
        except Exception as e:
            logger.error(f"Assignment handler error: {e}", exc_info=True)
            self.write_error_json(f"Error: {str(e)}")

    def _parse_to_cells(self, response: str) -> list[dict]:
        """
        Parse Claude's response into Jupyter-compatible cell format.

        Claude is instructed to use:
        ## MARKDOWN: for markdown cells
        ## CODE: for code cells
        ```python ... ``` blocks for code
        """
        cells = []
        lines = response.split("\n")
        current_type = "markdown"
        current_content = []
        in_code_block = False
        code_block_lang = ""

        i = 0
        while i < len(lines):
            line = lines[i]

            # Check for section markers
            if line.strip().startswith("## MARKDOWN:"):
                if current_content:
                    self._flush_cell(cells, current_type, current_content)
                current_content = [line[line.index(":") + 1:].strip()]
                current_type = "markdown"
                in_code_block = False

            elif line.strip().startswith("## CODE:"):
                if current_content:
                    self._flush_cell(cells, current_type, current_content)
                comment = line[line.index(":") + 1:].strip()
                current_content = [f"# {comment}"] if comment else []
                current_type = "code"
                in_code_block = False

            elif line.strip().startswith("```python") or line.strip().startswith("```py"):
                if not in_code_block:
                    # Start of code block
                    if current_type == "markdown" and current_content:
                        self._flush_cell(cells, "markdown", current_content)
                        current_content = []
                    current_type = "code"
                    in_code_block = True
                else:
                    # End of code block
                    in_code_block = False

            elif line.strip() == "```" and in_code_block:
                # End of code block
                in_code_block = False

            else:
                current_content.append(line)

            i += 1

        # Flush remaining content
        if current_content:
            self._flush_cell(cells, current_type, current_content)

        return cells if cells else [{"cell_type": "markdown", "source": response}]

    def _flush_cell(self, cells: list, cell_type: str, content: list[str]):
        """Add a cell to the cells list."""
        source = "\n".join(content).strip()
        if not source:
            return
        cells.append({
            "cell_type": cell_type,
            "source": source,
            "metadata": {},
            "outputs": [] if cell_type == "code" else None,
        })
