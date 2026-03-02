"""
Claude AI Service - Core interface to the Anthropic API.

Handles all Claude API calls with proper context management,
streaming support, and error handling.
"""

import os
import json
import logging
from typing import Optional, AsyncIterator
import anthropic

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are an expert Python/data science coding assistant embedded in JupyterLab.
You help users write, debug, explain, and improve code in Jupyter notebooks.

Your capabilities:
- Write clean, well-commented Python code
- Debug errors with clear explanations
- Suggest relevant packages (from PyPI, conda-forge)
- Explain complex concepts clearly with examples
- Complete coding assignments with full explanations
- Adapt to the user's conda environment and installed packages
- Provide context-aware suggestions based on the full notebook

Always:
- Format code in proper markdown code blocks with language specified
- Explain your reasoning step by step
- Suggest best practices (vectorization, type hints, docstrings)
- Warn about common pitfalls
- Be concise but thorough

When completing assignments:
- Add markdown cells with explanations before each code section
- Use proper variable names and comments
- Include test cases where appropriate
- Structure the solution logically"""


class ClaudeService:
    """Manages interactions with the Claude API."""

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-sonnet-4-6"):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model
        self._client: Optional[anthropic.Anthropic] = None

    @property
    def client(self) -> anthropic.Anthropic:
        if not self._client:
            if not self.api_key:
                raise ValueError(
                    "No Anthropic API key configured. "
                    "Set ANTHROPIC_API_KEY environment variable or configure in settings."
                )
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def set_api_key(self, key: str):
        """Update the API key and reset the client."""
        self.api_key = key
        self._client = None

    def build_notebook_context(self, cells: list[dict], current_cell_index: int = -1) -> str:
        """Build a context string from notebook cells for the AI."""
        if not cells:
            return ""

        context_parts = ["=== NOTEBOOK CONTEXT ===\n"]
        for i, cell in enumerate(cells):
            cell_type = cell.get("cell_type", "code")
            source = cell.get("source", "")
            if isinstance(source, list):
                source = "".join(source)
            outputs = cell.get("outputs", [])

            marker = " <-- CURRENT CELL" if i == current_cell_index else ""
            context_parts.append(f"\n[Cell {i+1} | {cell_type.upper()}]{marker}")
            context_parts.append(f"```{cell_type if cell_type == 'code' else 'markdown'}")
            context_parts.append(source)
            context_parts.append("```")

            if outputs:
                output_text = []
                for out in outputs[:3]:  # Limit outputs to first 3
                    if out.get("output_type") == "stream":
                        text = "".join(out.get("text", []))
                        output_text.append(text[:500])
                    elif out.get("output_type") in ("display_data", "execute_result"):
                        data = out.get("data", {})
                        if "text/plain" in data:
                            txt = "".join(data["text/plain"])
                            output_text.append(txt[:500])
                    elif out.get("output_type") == "error":
                        output_text.append(f"ERROR: {out.get('ename')}: {out.get('evalue')}")
                if output_text:
                    context_parts.append(f"Output: {' | '.join(output_text)}")

        return "\n".join(context_parts)

    def complete(
        self,
        prompt: str,
        notebook_context: str = "",
        conda_env: str = "",
        installed_packages: list[str] = None,
        max_tokens: int = 4096,
    ) -> str:
        """
        Send a completion request to Claude.
        Returns the full response text.
        """
        messages = self._build_messages(
            prompt, notebook_context, conda_env, installed_packages
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=SYSTEM_PROMPT,
                messages=messages,
            )
            return response.content[0].text
        except anthropic.AuthenticationError:
            raise ValueError("Invalid API key. Check your ANTHROPIC_API_KEY.")
        except anthropic.RateLimitError:
            raise RuntimeError("Rate limit exceeded. Please wait before retrying.")
        except anthropic.APIError as e:
            logger.error(f"Claude API error: {e}")
            raise

    def complete_assignment(
        self,
        problem_statement: str,
        notebook_context: str = "",
        conda_env: str = "",
        installed_packages: list[str] = None,
    ) -> str:
        """
        Complete a full assignment with code + markdown explanations.
        Returns structured notebook-ready content.
        """
        assignment_prompt = f"""Complete this assignment fully and professionally:

{problem_statement}

Provide your solution as a series of notebook cells, each clearly labeled:
- Use "## MARKDOWN:" prefix for markdown cells (explanations, headers)
- Use "## CODE:" prefix for code cells
- Structure: intro markdown, then alternating explanation + code sections
- End with a summary and any caveats

Be thorough. Show your work. Include imports, helper functions, and a clear conclusion."""

        return self.complete(
            assignment_prompt,
            notebook_context=notebook_context,
            conda_env=conda_env,
            installed_packages=installed_packages,
            max_tokens=8192,
        )

    def explain_code(self, code: str, output: str = "", error: str = "") -> str:
        """Explain a code cell and its output or error."""
        prompt = f"Explain this code clearly:\n\n```python\n{code}\n```"
        if error:
            prompt += f"\n\nThis produced an error:\n```\n{error}\n```\nExplain the error and how to fix it."
        elif output:
            prompt += f"\n\nOutput: `{output[:300]}`\n\nExplain the output."
        return self.complete(prompt, max_tokens=2048)

    def suggest_fix(self, code: str, error: str, notebook_context: str = "") -> str:
        """Suggest a fix for an error in a code cell."""
        prompt = f"""Fix this Python error:

Code:
```python
{code}
```

Error:
```
{error}
```

Provide:
1. Brief explanation of what caused the error
2. The corrected code
3. How to prevent this in the future"""
        return self.complete(prompt, notebook_context=notebook_context, max_tokens=2048)

    def complete_cell(self, partial_code: str, notebook_context: str = "") -> str:
        """Complete a partial code cell."""
        prompt = f"""Complete this Python code. Return ONLY the completed code, no explanation:

```python
{partial_code}
```"""
        return self.complete(prompt, notebook_context=notebook_context, max_tokens=1024)

    def suggest_next_cell(self, notebook_context: str, goal: str = "") -> str:
        """Suggest what the next cell in the notebook should be."""
        prompt = "Based on the notebook above, what should the next cell contain?"
        if goal:
            prompt += f" The user's goal is: {goal}"
        prompt += "\n\nProvide both the code and a brief explanation of why this is the natural next step."
        return self.complete(prompt, notebook_context=notebook_context, max_tokens=2048)

    def search_packages(self, task_description: str, conda_env: str = "") -> str:
        """Suggest relevant packages for a given task."""
        prompt = f"""Suggest the best Python packages for this task:
"{task_description}"

{'Conda environment: ' + conda_env if conda_env else ''}

For each package:
1. Package name (conda/pip install command)
2. What it does
3. Why it's the best choice
4. A minimal usage example

Prioritize packages available on conda-forge."""
        return self.complete(prompt, max_tokens=2048)

    def _build_messages(
        self,
        prompt: str,
        notebook_context: str,
        conda_env: str,
        installed_packages: list[str],
    ) -> list[dict]:
        """Build the message list for the API call."""
        content = ""

        if conda_env:
            content += f"Active conda environment: {conda_env}\n"

        if installed_packages:
            pkg_list = ", ".join(installed_packages[:30])  # Limit to 30 packages
            content += f"Key installed packages: {pkg_list}\n"

        if notebook_context:
            content += f"\n{notebook_context}\n\n"

        content += f"=== USER REQUEST ===\n{prompt}"

        return [{"role": "user", "content": content}]
