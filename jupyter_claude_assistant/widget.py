"""
Jupyter Claude Assistant - Interactive Widget UI

Provides an ipywidgets-based interactive panel that works in any JupyterLab/
Jupyter Notebook environment without requiring npm/TypeScript compilation.

Usage:
    from jupyter_claude_assistant import show_panel
    show_panel()
"""

import os
import sys
from typing import Optional


def show_panel(api_key: Optional[str] = None):
    """
    Display the Claude Assistant interactive panel in a Jupyter notebook.

    This function creates an ipywidgets-based UI that provides:
    - Chat interface with Claude
    - Code completion
    - Assignment mode
    - Environment info
    - Memory/skills browser

    Args:
        api_key: Anthropic API key. If not provided, uses ANTHROPIC_API_KEY env var.
    """
    try:
        import ipywidgets as widgets
        from IPython.display import display
    except ImportError:
        print("Error: ipywidgets is required. Install with: pip install ipywidgets")
        return

    from .services.claude_service import ClaudeService
    from .services.conda_service import CondaService
    from .services.memory_service import MemoryService

    # Initialize services
    key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    claude = ClaudeService(api_key=key)
    conda = CondaService()
    memory = MemoryService()

    # -------------------------------------------------------------------------
    # Widget Layout
    # -------------------------------------------------------------------------

    # Header
    header = widgets.HTML(
        value="""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 12px 16px; border-radius: 8px 8px 0 0;
                    color: white; font-family: -apple-system, sans-serif;">
            <div style="font-size: 16px; font-weight: 700;">🤖 Claude Assistant</div>
            <div style="font-size: 11px; opacity: 0.85; margin-top: 2px;">
                Powered by Anthropic • {model}
            </div>
        </div>
        """.format(model=claude.model)
    )

    # Mode selector
    mode_tabs = widgets.Tab()

    # --- CHAT TAB ---
    chat_output = widgets.Output(
        layout=widgets.Layout(
            height="300px",
            overflow_y="auto",
            border="1px solid #e1e4e8",
            padding="8px",
            border_radius="4px",
            background_color="#fafafa",
        )
    )

    chat_input = widgets.Textarea(
        placeholder="Ask Claude anything about your code...\nShift+Enter to send",
        layout=widgets.Layout(width="100%", height="80px"),
    )

    chat_send_btn = widgets.Button(
        description="Send",
        button_style="primary",
        icon="paper-plane",
        layout=widgets.Layout(width="80px"),
    )

    chat_context_check = widgets.Checkbox(
        value=True,
        description="Include notebook context",
        style={"description_width": "initial"},
    )

    chat_controls = widgets.HBox([chat_send_btn, chat_context_check])
    chat_tab = widgets.VBox([chat_output, chat_input, chat_controls])

    # --- COMPLETE TAB ---
    complete_code_input = widgets.Textarea(
        placeholder="Paste partial code here...",
        layout=widgets.Layout(width="100%", height="150px"),
    )

    complete_btn = widgets.Button(
        description="Complete Code",
        button_style="success",
        icon="magic",
    )

    next_cell_btn = widgets.Button(
        description="Suggest Next Cell",
        button_style="info",
        icon="forward",
    )

    goal_input = widgets.Text(
        placeholder="Optional: describe your goal",
        layout=widgets.Layout(width="100%"),
    )

    complete_output = widgets.Output(
        layout=widgets.Layout(
            height="200px",
            overflow_y="auto",
            border="1px solid #e1e4e8",
            padding="8px",
        )
    )

    complete_tab = widgets.VBox([
        widgets.Label("Code to complete:"),
        complete_code_input,
        widgets.Label("Your goal (optional):"),
        goal_input,
        widgets.HBox([complete_btn, next_cell_btn]),
        widgets.Label("Result:"),
        complete_output,
    ])

    # --- ASSIGNMENT TAB ---
    assign_input = widgets.Textarea(
        placeholder="Describe your assignment or problem statement...\n\nExample: Build a data pipeline that reads a CSV, handles missing values, and plots the distribution of each numeric column.",
        layout=widgets.Layout(width="100%", height="120px"),
    )

    assign_btn = widgets.Button(
        description="Complete Assignment",
        button_style="warning",
        icon="graduation-cap",
    )

    assign_output = widgets.Output(
        layout=widgets.Layout(
            height="300px",
            overflow_y="auto",
            border="1px solid #e1e4e8",
            padding="8px",
        )
    )

    assign_tab = widgets.VBox([
        widgets.Label("Problem statement:"),
        assign_input,
        assign_btn,
        widgets.Label("Solution:"),
        assign_output,
    ])

    # --- FIX TAB ---
    fix_code_input = widgets.Textarea(
        placeholder="Paste the code that has an error...",
        layout=widgets.Layout(width="100%", height="120px"),
    )

    fix_error_input = widgets.Textarea(
        placeholder="Paste the error message here...",
        layout=widgets.Layout(width="100%", height="80px"),
    )

    fix_btn = widgets.Button(
        description="Fix Error",
        button_style="danger",
        icon="wrench",
    )

    fix_output = widgets.Output(
        layout=widgets.Layout(
            height="200px",
            overflow_y="auto",
            border="1px solid #e1e4e8",
            padding="8px",
        )
    )

    fix_tab = widgets.VBox([
        widgets.Label("Code with error:"),
        fix_code_input,
        widgets.Label("Error message:"),
        fix_error_input,
        fix_btn,
        widgets.Label("Fix:"),
        fix_output,
    ])

    # --- ENV TAB ---
    env_output = widgets.Output(
        layout=widgets.Layout(
            height="250px",
            overflow_y="auto",
            border="1px solid #e1e4e8",
            padding="8px",
        )
    )

    refresh_env_btn = widgets.Button(
        description="Refresh",
        button_style="info",
        icon="refresh",
    )

    env_tab = widgets.VBox([refresh_env_btn, env_output])

    # Setup mode tabs
    mode_tabs.children = [chat_tab, complete_tab, assign_tab, fix_tab, env_tab]
    for i, title in enumerate(["💬 Chat", "✨ Complete", "📝 Assign", "🔧 Fix", "🐍 Env"]):
        mode_tabs.set_title(i, title)

    # Status bar
    status_bar = widgets.HTML(
        value="<div style='font-size:11px; color:#666; padding:4px 8px;'>Ready</div>"
    )

    # API key warning (shown if no key)
    api_warning = widgets.HTML(
        value="""
        <div style="background:#fff3cd; border:1px solid #ffc107; padding:8px 12px;
                    border-radius:4px; font-size:12px; color:#856404;">
            ⚠️ No API key found. Set <code>ANTHROPIC_API_KEY</code> or run:<br>
            <code>import os; os.environ['ANTHROPIC_API_KEY'] = 'your-key'</code>
        </div>
        """
    )

    components = [header]
    if not key:
        components.append(api_warning)
    components.extend([mode_tabs, status_bar])

    panel = widgets.VBox(
        components,
        layout=widgets.Layout(
            width="600px",
            border="1px solid #e1e4e8",
            border_radius="8px",
            box_shadow="0 2px 8px rgba(0,0,0,0.1)",
        ),
    )

    # -------------------------------------------------------------------------
    # Event Handlers
    # -------------------------------------------------------------------------

    def set_status(msg: str, color: str = "#666"):
        status_bar.value = f"<div style='font-size:11px; color:{color}; padding:4px 8px;'>{msg}</div>"

    def get_notebook_cells():
        """Try to get current notebook cells from IPython kernel."""
        try:
            from IPython import get_ipython
            ip = get_ipython()
            if ip and hasattr(ip, "history_manager"):
                # Get recent history as context
                hist = list(ip.history_manager.get_range())
                return [{"cell_type": "code", "source": src, "outputs": []} for _, _, src in hist[-10:]]
        except Exception:
            pass
        return []

    def on_chat_send(b):
        message = chat_input.value.strip()
        if not message:
            return

        set_status("Thinking...", "#0366d6")
        chat_input.value = ""

        with chat_output:
            from IPython.display import HTML as IHTML
            display(IHTML(f"""
                <div style="margin:4px 0; padding:6px 10px; background:#e9ecef;
                            border-radius:12px 12px 2px 12px; max-width:80%; margin-left:auto;
                            font-size:13px; font-family:monospace;">
                    {message}
                </div>
            """))

        try:
            cells = get_notebook_cells() if chat_context_check.value else []
            context = claude.build_notebook_context(cells) if cells else ""
            env = conda.get_active_environment()

            response = claude.complete(
                prompt=message,
                notebook_context=context,
                conda_env=env["name"],
                installed_packages=conda.get_package_names(),
            )

            memory.save_interaction("chat", message, response, conda_env=env["name"])

            with chat_output:
                from IPython.display import Markdown
                display(Markdown(f"**Claude:**\n\n{response}"))

            set_status(f"✓ Response received ({len(response)} chars)")

        except Exception as e:
            with chat_output:
                from IPython.display import HTML as IHTML
                display(IHTML(f'<div style="color:red; font-size:12px;">Error: {e}</div>'))
            set_status(f"Error: {e}", "#d73a49")

    def on_complete(b):
        code = complete_code_input.value.strip()
        if not code:
            return
        set_status("Completing code...", "#0366d6")
        try:
            cells = get_notebook_cells()
            context = claude.build_notebook_context(cells)
            response = claude.complete_cell(code, context)
            complete_output.clear_output()
            with complete_output:
                from IPython.display import Markdown
                display(Markdown(response))
            set_status("✓ Completion ready")
        except Exception as e:
            set_status(f"Error: {e}", "#d73a49")

    def on_next_cell(b):
        goal = goal_input.value.strip()
        set_status("Suggesting next cell...", "#0366d6")
        try:
            cells = get_notebook_cells()
            context = claude.build_notebook_context(cells)
            response = claude.suggest_next_cell(context, goal)
            complete_output.clear_output()
            with complete_output:
                from IPython.display import Markdown
                display(Markdown(response))
            set_status("✓ Suggestion ready")
        except Exception as e:
            set_status(f"Error: {e}", "#d73a49")

    def on_assign(b):
        problem = assign_input.value.strip()
        if not problem:
            return
        set_status("Working on assignment... (this may take a moment)", "#0366d6")
        try:
            env = conda.get_active_environment()
            response = claude.complete_assignment(
                problem_statement=problem,
                conda_env=env["name"],
                installed_packages=conda.get_package_names(),
            )
            memory.save_interaction("assignment", problem, response, conda_env=env["name"])
            assign_output.clear_output()
            with assign_output:
                from IPython.display import Markdown
                display(Markdown(response))
            set_status("✓ Assignment complete!")
        except Exception as e:
            set_status(f"Error: {e}", "#d73a49")

    def on_fix(b):
        code = fix_code_input.value.strip()
        error = fix_error_input.value.strip()
        if not code or not error:
            set_status("Please provide both code and error message", "#d73a49")
            return
        set_status("Analyzing error...", "#0366d6")
        try:
            cells = get_notebook_cells()
            context = claude.build_notebook_context(cells)
            response = claude.suggest_fix(code, error, context)
            memory.save_interaction("fix", f"{code}\n{error}", response)
            fix_output.clear_output()
            with fix_output:
                from IPython.display import Markdown
                display(Markdown(response))
            set_status("✓ Fix ready!")
        except Exception as e:
            set_status(f"Error: {e}", "#d73a49")

    def on_refresh_env(b):
        env_output.clear_output()
        with env_output:
            from IPython.display import Markdown
            env = conda.get_active_environment()
            envs = conda.list_environments()
            summary = conda.get_env_summary()
            conda.clear_cache()
            md = f"""**Active Environment:** `{env['name']}`
**Python:** {env['python_version']}
**Path:** `{env['path']}`

{summary}

**All Environments:**
{chr(10).join(f"- `{e['name']}`" for e in envs)}
"""
            display(Markdown(md))

    # Wire up events
    chat_send_btn.on_click(on_chat_send)
    complete_btn.on_click(on_complete)
    next_cell_btn.on_click(on_next_cell)
    assign_btn.on_click(on_assign)
    fix_btn.on_click(on_fix)
    refresh_env_btn.on_click(on_refresh_env)

    # Trigger initial env load
    on_refresh_env(None)

    # Display
    display(panel)
    return panel
