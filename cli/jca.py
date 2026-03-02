#!/usr/bin/env python3
"""
JCA - Jupyter Claude Assistant CLI

A command-line tool for AI-assisted Python and Jupyter notebook development.

Usage:
    jca chat "How do I read a CSV file?"
    jca explain mynotebook.ipynb --cell 3
    jca fix script.py
    jca complete script.py
    jca assign "Build a linear regression model" --output solution.ipynb
    jca search "pandas dataframe operations"
    jca env
    jca stats
"""

import os
import sys
import json
import click
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def get_api_key() -> str:
    """Get the Anthropic API key from environment or config."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        # Try reading from ~/.jupyter_claude/config.json
        config_path = Path.home() / ".jupyter_claude" / "config.json"
        if config_path.exists():
            try:
                with open(config_path) as f:
                    config = json.load(f)
                    key = config.get("api_key", "")
            except Exception:
                pass
    return key


def get_claude_service(model: str = "claude-sonnet-4-6"):
    """Get initialized Claude service."""
    from jupyter_claude_assistant.services.claude_service import ClaudeService
    return ClaudeService(api_key=get_api_key(), model=model)


def get_memory_service():
    """Get initialized memory service."""
    from jupyter_claude_assistant.services.memory_service import MemoryService
    return MemoryService()


def get_conda_service():
    """Get initialized conda service."""
    from jupyter_claude_assistant.services.conda_service import CondaService
    return CondaService()


def read_notebook(path: str) -> dict:
    """Read a Jupyter notebook file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_notebook(path: str, notebook: dict):
    """Write a Jupyter notebook file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(notebook, f, indent=1)


def create_empty_notebook() -> dict:
    """Create an empty notebook structure."""
    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "version": "3.10.0",
            },
        },
        "cells": [],
    }


def make_cell(cell_type: str, source: str) -> dict:
    """Create a notebook cell."""
    cell = {
        "cell_type": cell_type,
        "metadata": {},
        "source": source,
        "id": os.urandom(4).hex(),
    }
    if cell_type == "code":
        cell["outputs"] = []
        cell["execution_count"] = None
    return cell


def print_response(text: str, title: str = ""):
    """Print formatted response using rich if available."""
    try:
        from rich.console import Console
        from rich.markdown import Markdown
        from rich.panel import Panel

        console = Console()
        if title:
            console.print(Panel(Markdown(text), title=title, border_style="blue"))
        else:
            console.print(Markdown(text))
    except ImportError:
        if title:
            print(f"\n{'='*60}")
            print(f"  {title}")
            print(f"{'='*60}")
        print(text)
        print()


# =============================================================================
# CLI Commands
# =============================================================================

@click.group()
@click.version_option(version="1.0.0", prog_name="jca")
@click.option("--model", default="claude-sonnet-4-6", help="Claude model to use")
@click.pass_context
def main(ctx, model):
    """
    JCA - Jupyter Claude Assistant

    AI-powered coding assistant for Python and Jupyter notebooks.
    Powered by Claude AI (Anthropic).

    Set ANTHROPIC_API_KEY environment variable before use.
    """
    ctx.ensure_object(dict)
    ctx.obj["model"] = model


@main.command()
@click.argument("message")
@click.option("--notebook", "-n", help="Path to notebook for context")
@click.pass_context
def chat(ctx, message, notebook):
    """Chat with Claude about your code or notebook."""
    claude = get_claude_service(ctx.obj["model"])

    notebook_context = ""
    if notebook and Path(notebook).exists():
        nb = read_notebook(notebook)
        cells = nb.get("cells", [])
        notebook_context = claude.build_notebook_context(cells)
        click.echo(f"Using notebook context from: {notebook}")

    conda = get_conda_service()
    env_info = conda.get_active_environment()
    packages = conda.get_package_names()

    click.echo(f"Asking Claude ({ctx.obj['model']})...\n")

    try:
        response = claude.complete(
            prompt=message,
            notebook_context=notebook_context,
            conda_env=env_info["name"],
            installed_packages=packages,
        )
        print_response(response, title="Claude's Response")

        # Save to memory
        mem = get_memory_service()
        mem.save_interaction("chat", message, response, conda_env=env_info["name"])

    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        click.echo("Make sure ANTHROPIC_API_KEY is set.", err=True)
        sys.exit(1)


@main.command()
@click.argument("file_path")
@click.option("--cell", "-c", type=int, default=None, help="Cell index to explain (0-based)")
@click.option("--all-cells", "-a", is_flag=True, help="Explain all cells")
@click.pass_context
def explain(ctx, file_path, cell, all_cells):
    """Explain code in a Python file or Jupyter notebook."""
    path = Path(file_path)
    if not path.exists():
        click.echo(f"File not found: {file_path}", err=True)
        sys.exit(1)

    claude = get_claude_service(ctx.obj["model"])

    if path.suffix == ".ipynb":
        nb = read_notebook(str(path))
        cells = nb.get("cells", [])

        if cell is not None:
            if cell >= len(cells):
                click.echo(f"Cell index {cell} out of range (notebook has {len(cells)} cells)", err=True)
                sys.exit(1)
            target_cell = cells[cell]
            source = target_cell.get("source", "")
            if isinstance(source, list):
                source = "".join(source)
            outputs = target_cell.get("outputs", [])
            error_text = ""
            for out in outputs:
                if out.get("output_type") == "error":
                    error_text = f"{out.get('ename')}: {out.get('evalue')}"
                    break

            click.echo(f"Explaining cell {cell}...\n")
            response = claude.explain_code(source, error=error_text)
            print_response(response, title=f"Explanation: Cell {cell}")
        else:
            # Explain the whole notebook
            context = claude.build_notebook_context(cells)
            prompt = "Explain what this notebook does, cell by cell, and what the overall goal is."
            response = claude.complete(prompt, notebook_context=context)
            print_response(response, title=f"Notebook Explanation: {path.name}")

    elif path.suffix == ".py":
        with open(path, "r", encoding="utf-8") as f:
            code = f.read()
        click.echo(f"Explaining {path.name}...\n")
        response = claude.explain_code(code)
        print_response(response, title=f"Explanation: {path.name}")
    else:
        click.echo(f"Unsupported file type: {path.suffix}", err=True)
        sys.exit(1)


@main.command()
@click.argument("file_path")
@click.option("--cell", "-c", type=int, default=None, help="Cell with error (0-based)")
@click.pass_context
def fix(ctx, file_path, cell):
    """Fix errors in a Python file or notebook cell."""
    path = Path(file_path)
    if not path.exists():
        click.echo(f"File not found: {file_path}", err=True)
        sys.exit(1)

    claude = get_claude_service(ctx.obj["model"])

    if path.suffix == ".ipynb":
        nb = read_notebook(str(path))
        cells = nb.get("cells", [])

        # Find the cell with an error if not specified
        target_cell_idx = cell
        error_text = ""

        if target_cell_idx is None:
            for i, c in enumerate(cells):
                for out in c.get("outputs", []):
                    if out.get("output_type") == "error":
                        target_cell_idx = i
                        error_text = f"{out.get('ename')}: {out.get('evalue')}\n{''.join(out.get('traceback', []))}"
                        break
                if target_cell_idx is not None:
                    break

        if target_cell_idx is None:
            click.echo("No errors found in notebook. Specify a cell with --cell.", err=True)
            sys.exit(1)

        target_cell = cells[target_cell_idx]
        source = target_cell.get("source", "")
        if isinstance(source, list):
            source = "".join(source)

        if not error_text:
            for out in target_cell.get("outputs", []):
                if out.get("output_type") == "error":
                    error_text = f"{out.get('ename')}: {out.get('evalue')}"

        context = claude.build_notebook_context(cells, target_cell_idx)
        click.echo(f"Fixing cell {target_cell_idx}...\n")
        response = claude.suggest_fix(source, error_text or "Unknown error", context)
        print_response(response, title=f"Fix for Cell {target_cell_idx}")

    elif path.suffix == ".py":
        with open(path, "r", encoding="utf-8") as f:
            code = f.read()
        # Try to detect the error by running the file
        import subprocess
        result = subprocess.run(
            [sys.executable, str(path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        error = result.stderr or "No runtime error detected"
        click.echo(f"Fixing {path.name}...\n")
        response = claude.suggest_fix(code, error)
        print_response(response, title=f"Fix for {path.name}")


@main.command()
@click.argument("problem")
@click.option("--output", "-o", help="Output notebook path (.ipynb)")
@click.option("--env", "-e", help="Conda environment name")
@click.pass_context
def assign(ctx, problem, output, env):
    """Complete a coding assignment and write to a notebook."""
    claude = get_claude_service(ctx.obj["model"])
    conda = get_conda_service()

    env_info = conda.get_active_environment()
    env_name = env or env_info["name"]
    packages = conda.get_package_names(env_name)

    click.echo(f"Completing assignment using env: {env_name}")
    click.echo(f"Problem: {problem[:100]}...")
    click.echo("Working with Claude...\n")

    try:
        response = claude.complete_assignment(
            problem_statement=problem,
            conda_env=env_name,
            installed_packages=packages,
        )

        if output:
            # Parse response into notebook cells
            nb = create_empty_notebook()
            nb["cells"].append(make_cell("markdown", f"# Assignment Solution\n\n**Problem:** {problem}"))

            # Split on code blocks and markdown sections
            parts = response.split("```python")
            for i, part in enumerate(parts):
                if i == 0:
                    # Before first code block — markdown
                    if part.strip():
                        nb["cells"].append(make_cell("markdown", part.strip()))
                else:
                    # Has code
                    code_end = part.find("```")
                    if code_end != -1:
                        code = part[:code_end].strip()
                        rest = part[code_end + 3:].strip()
                        if code:
                            nb["cells"].append(make_cell("code", code))
                        if rest:
                            nb["cells"].append(make_cell("markdown", rest))
                    else:
                        nb["cells"].append(make_cell("code", part.strip()))

            write_notebook(output, nb)
            click.echo(f"\nSolution written to: {output}")
            click.echo(f"Open with: jupyter lab {output}")
        else:
            print_response(response, title="Assignment Solution")

        # Save to memory
        mem = get_memory_service()
        mem.save_interaction("assignment", problem, response, conda_env=env_name)

    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.argument("query")
@click.option("--source", "-s",
              type=click.Choice(["all", "pypi", "github", "stackoverflow"]),
              default="all")
@click.pass_context
def search(ctx, query, source):
    """Search PyPI, GitHub, and Stack Overflow."""
    from jupyter_claude_assistant.services.search_service import SearchService
    from jupyter_claude_assistant.services.memory_service import MemoryService

    mem = MemoryService()
    svc = SearchService(memory_service=mem)

    click.echo(f"Searching for: {query} (source: {source})\n")

    if source == "pypi":
        results = {"pypi": svc.search_pypi(query), "query": query}
    elif source == "github":
        results = {"github": svc.search_github(query), "query": query}
    elif source == "stackoverflow":
        results = {"stackoverflow": svc.search_stackoverflow(query), "query": query}
    else:
        results = svc.search_all(query)

    formatted = svc.format_results_for_claude(results)
    click.echo(formatted)


@main.command("env")
def show_env():
    """Show active conda environment information."""
    conda = get_conda_service()
    active = conda.get_active_environment()
    envs = conda.list_environments()
    summary = conda.get_env_summary()

    click.echo("\n=== Conda Environment Info ===")
    click.echo(f"Active: {active['name']}")
    click.echo(f"Path:   {active['path']}")
    click.echo(f"Python: {active['python_version']}")
    click.echo(f"\n{summary}")
    click.echo(f"\nAll environments ({len(envs)}):")
    for env in envs:
        marker = " *" if env["name"] == active["name"] else ""
        click.echo(f"  {env['name']}{marker}")


@main.command()
def stats():
    """Show usage statistics."""
    mem = get_memory_service()
    stats_data = mem.get_stats()
    prefs = mem.get_all_preferences()

    click.echo("\n=== JCA Usage Statistics ===")
    click.echo(f"Total interactions: {stats_data['total_interactions']}")
    click.echo(f"Average rating: {stats_data['average_rating']}/5")
    click.echo("\nBy type:")
    for req_type, count in stats_data.get("by_type", {}).items():
        click.echo(f"  {req_type}: {count}")

    if prefs:
        click.echo("\nPreferences:")
        for key, value in prefs.items():
            click.echo(f"  {key}: {value}")


@main.command("config")
@click.option("--set-key", help="Set the Anthropic API key")
@click.option("--set-model", help="Set the default model")
def configure(set_key, set_model):
    """Configure JCA settings."""
    config_dir = Path.home() / ".jupyter_claude"
    config_dir.mkdir(exist_ok=True)
    config_path = config_dir / "config.json"

    config = {}
    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)

    if set_key:
        config["api_key"] = set_key
        click.echo("API key saved to ~/.jupyter_claude/config.json")

    if set_model:
        config["model"] = set_model
        click.echo(f"Default model set to: {set_model}")

    if set_key or set_model:
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
    else:
        click.echo(f"Config file: {config_path}")
        if config:
            for key, value in config.items():
                if key == "api_key":
                    click.echo(f"  api_key: {'*' * 20}")
                else:
                    click.echo(f"  {key}: {value}")
        else:
            click.echo("No configuration found. Set ANTHROPIC_API_KEY or run:")
            click.echo("  jca config --set-key YOUR_KEY_HERE")


@main.command("complete")
@click.argument("file_path")
@click.option("--cell", "-c", type=int, default=None, help="Cell to complete (for .ipynb)")
@click.pass_context
def complete_code(ctx, file_path, cell):
    """Complete partial code in a file or notebook cell."""
    path = Path(file_path)
    if not path.exists():
        click.echo(f"File not found: {file_path}", err=True)
        sys.exit(1)

    claude = get_claude_service(ctx.obj["model"])

    if path.suffix == ".ipynb":
        nb = read_notebook(str(path))
        cells = nb.get("cells", [])
        if cell is None:
            # Complete the last code cell
            for i in range(len(cells) - 1, -1, -1):
                if cells[i]["cell_type"] == "code":
                    cell = i
                    break

        if cell is None:
            click.echo("No code cells found", err=True)
            sys.exit(1)

        target = cells[cell]
        source = target.get("source", "")
        if isinstance(source, list):
            source = "".join(source)

        context = claude.build_notebook_context(cells, cell)
        response = claude.complete_cell(source, context)
        print_response(response, title=f"Completion for Cell {cell}")

    elif path.suffix == ".py":
        with open(path) as f:
            code = f.read()
        response = claude.complete_cell(code)
        print_response(response, title=f"Completion for {path.name}")


if __name__ == "__main__":
    main()
