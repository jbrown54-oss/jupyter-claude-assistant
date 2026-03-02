"""Tests for the ClaudeService (without actual API calls)."""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from jupyter_claude_assistant.services.claude_service import ClaudeService


@pytest.fixture
def claude():
    return ClaudeService(api_key="test-key")


class TestClaudeServiceInit:
    def test_init_with_key(self):
        """Test initialization with explicit API key."""
        svc = ClaudeService(api_key="test-key-123")
        assert svc.api_key == "test-key-123"

    def test_init_from_env(self, monkeypatch):
        """Test initialization from environment variable."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key-456")
        svc = ClaudeService()
        assert svc.api_key == "env-key-456"

    def test_default_model(self):
        """Test default model is set correctly."""
        svc = ClaudeService(api_key="key")
        assert svc.model == "claude-sonnet-4-6"

    def test_custom_model(self):
        """Test custom model assignment."""
        svc = ClaudeService(api_key="key", model="claude-opus-4-6")
        assert svc.model == "claude-opus-4-6"

    def test_set_api_key(self, claude):
        """Test setting a new API key resets the client."""
        claude._client = MagicMock()  # Set a fake client
        claude.set_api_key("new-key")
        assert claude.api_key == "new-key"
        assert claude._client is None  # Client should be reset


class TestBuildNotebookContext:
    def test_empty_cells(self, claude):
        """Test building context from empty cells."""
        result = claude.build_notebook_context([])
        assert result == ""

    def test_single_code_cell(self, claude):
        """Test context with a single code cell."""
        cells = [{"cell_type": "code", "source": "import pandas as pd", "outputs": []}]
        result = claude.build_notebook_context(cells)
        assert "NOTEBOOK CONTEXT" in result
        assert "import pandas as pd" in result
        assert "Cell 1" in result

    def test_markdown_cell(self, claude):
        """Test context with a markdown cell."""
        cells = [{"cell_type": "markdown", "source": "# Analysis", "outputs": []}]
        result = claude.build_notebook_context(cells)
        assert "# Analysis" in result
        assert "MARKDOWN" in result

    def test_current_cell_marker(self, claude):
        """Test that current cell is marked."""
        cells = [
            {"cell_type": "code", "source": "x = 1", "outputs": []},
            {"cell_type": "code", "source": "y = 2", "outputs": []},
        ]
        result = claude.build_notebook_context(cells, current_cell_index=1)
        assert "CURRENT CELL" in result

    def test_cell_with_output(self, claude):
        """Test context includes cell outputs."""
        cells = [{
            "cell_type": "code",
            "source": "print('hello')",
            "outputs": [{"output_type": "stream", "text": ["hello\n"]}]
        }]
        result = claude.build_notebook_context(cells)
        assert "hello" in result

    def test_cell_with_error(self, claude):
        """Test context includes error outputs."""
        cells = [{
            "cell_type": "code",
            "source": "1/0",
            "outputs": [{
                "output_type": "error",
                "ename": "ZeroDivisionError",
                "evalue": "division by zero",
            }]
        }]
        result = claude.build_notebook_context(cells)
        assert "ZeroDivisionError" in result

    def test_source_as_list(self, claude):
        """Test that source as list of strings is handled."""
        cells = [{"cell_type": "code", "source": ["import pandas\n", "import numpy\n"], "outputs": []}]
        result = claude.build_notebook_context(cells)
        assert "import pandas" in result

    def test_multiple_cells(self, claude):
        """Test context with multiple cells."""
        cells = [
            {"cell_type": "code", "source": "x = 1", "outputs": []},
            {"cell_type": "markdown", "source": "## Analysis", "outputs": []},
            {"cell_type": "code", "source": "y = x + 1", "outputs": []},
        ]
        result = claude.build_notebook_context(cells)
        assert "Cell 1" in result
        assert "Cell 2" in result
        assert "Cell 3" in result


class TestBuildMessages:
    def test_build_messages_basic(self, claude):
        """Test basic message building."""
        messages = claude._build_messages("Hello", "", "", [])
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert "Hello" in messages[0]["content"]

    def test_build_messages_with_env(self, claude):
        """Test message building with conda env."""
        messages = claude._build_messages("Hello", "", "myenv", [])
        assert "myenv" in messages[0]["content"]

    def test_build_messages_with_packages(self, claude):
        """Test message building with package list."""
        messages = claude._build_messages("Hello", "", "", ["pandas", "numpy", "matplotlib"])
        assert "pandas" in messages[0]["content"]

    def test_build_messages_with_context(self, claude):
        """Test message building with notebook context."""
        context = "=== NOTEBOOK CONTEXT ===\n[Cell 1 | CODE]\nimport pandas"
        messages = claude._build_messages("Help me", context, "", [])
        assert "NOTEBOOK CONTEXT" in messages[0]["content"]

    def test_packages_limit(self, claude):
        """Test that package list is limited to 30."""
        packages = [f"pkg{i}" for i in range(50)]
        messages = claude._build_messages("Hello", "", "", packages)
        content = messages[0]["content"]
        # Should only include first 30
        assert "pkg29" in content
        assert "pkg30" not in content  # 31st package should not be included


class TestAPICallsWithMock:
    """Tests that mock the actual API calls."""

    @patch("anthropic.Anthropic")
    def test_complete_basic(self, mock_anthropic_class, claude):
        """Test basic completion with mocked API."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Here is the answer")]
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        # Reset client to use mock
        claude._client = mock_client

        result = claude.complete("Test prompt")
        assert result == "Here is the answer"
        mock_client.messages.create.assert_called_once()

    @patch("anthropic.Anthropic")
    def test_complete_no_key_raises(self, mock_anthropic_class):
        """Test that missing API key raises ValueError."""
        svc = ClaudeService(api_key="")

        with pytest.raises((ValueError, Exception)):
            svc.complete("Test")
