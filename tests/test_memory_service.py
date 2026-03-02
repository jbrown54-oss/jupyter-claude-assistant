"""Tests for the MemoryService."""

import os
import tempfile
import time
import pytest
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from jupyter_claude_assistant.services.memory_service import MemoryService


@pytest.fixture
def memory():
    """Create a temporary memory service for testing."""
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test.db")
    svc = MemoryService(db_path=db_path)
    yield svc
    # Explicitly close all SQLite connections before cleanup (needed on Windows)
    import gc
    del svc
    gc.collect()
    import shutil
    try:
        shutil.rmtree(tmpdir, ignore_errors=True)
    except Exception:
        pass


class TestInteractions:
    def test_save_and_retrieve(self, memory):
        """Test saving and retrieving an interaction."""
        iid = memory.save_interaction(
            request_type="chat",
            prompt="How do I read a CSV?",
            response="Use pd.read_csv('file.csv')",
            conda_env="base",
        )
        assert iid is not None
        assert iid > 0

    def test_get_recent(self, memory):
        """Test getting recent interactions."""
        memory.save_interaction("chat", "prompt 1", "response 1")
        memory.save_interaction("chat", "prompt 2", "response 2")

        recent = memory.get_recent_interactions(limit=5)
        assert len(recent) == 2
        assert recent[0]["prompt"] == "prompt 2"  # Most recent first

    def test_rate_interaction(self, memory):
        """Test rating an interaction."""
        iid = memory.save_interaction("chat", "test", "response")
        memory.rate_interaction(iid, 4)

        recent = memory.get_recent_interactions()
        assert recent[0]["rating"] == 4

    def test_rating_clamped(self, memory):
        """Test that rating is clamped to 1-5."""
        iid = memory.save_interaction("chat", "test", "response")
        memory.rate_interaction(iid, 10)  # Should be clamped to 5

        recent = memory.get_recent_interactions()
        assert recent[0]["rating"] == 5

    def test_stats(self, memory):
        """Test usage statistics."""
        memory.save_interaction("chat", "p1", "r1")
        memory.save_interaction("chat", "p2", "r2")
        memory.save_interaction("complete", "p3", "r3")

        stats = memory.get_stats()
        assert stats["total_interactions"] == 3
        assert stats["by_type"]["chat"] == 2
        assert stats["by_type"]["complete"] == 1

    def test_find_similar(self, memory):
        """Test finding similar interactions by hash."""
        prompt = "How do I read a CSV?"
        memory.save_interaction("chat", prompt, "Use pd.read_csv()")

        result = memory.find_similar_interaction(prompt, "chat")
        assert result is not None
        assert result["response"] == "Use pd.read_csv()"

    def test_find_similar_miss(self, memory):
        """Test that non-matching prompts return None."""
        memory.save_interaction("chat", "prompt A", "response A")
        result = memory.find_similar_interaction("completely different prompt", "chat")
        assert result is None


class TestSkills:
    def test_save_and_search_skill(self, memory):
        """Test saving and searching skills."""
        memory.save_skill(
            name="pandas_groupby",
            description="Group a DataFrame by columns",
            code_template="df.groupby('col').agg({'val': 'sum'})",
            tags=["pandas", "dataframe"],
        )

        results = memory.search_skills("pandas")
        assert len(results) == 1
        assert results[0]["name"] == "pandas_groupby"

    def test_skill_upsert(self, memory):
        """Test that saving the same skill name updates it."""
        memory.save_skill("test_skill", "desc 1", "code 1")
        memory.save_skill("test_skill", "desc 2", "code 2")

        all_skills = memory.get_all_skills()
        assert len(all_skills) == 1
        assert all_skills[0]["description"] == "desc 2"

    def test_use_skill(self, memory):
        """Test incrementing skill use count."""
        memory.save_skill("my_skill", "desc", "code")
        skills = memory.get_all_skills()
        skill_id = skills[0]["id"]

        memory.use_skill(skill_id)
        memory.use_skill(skill_id)

        skills = memory.get_all_skills()
        assert skills[0]["use_count"] == 2


class TestSearchCache:
    def test_cache_and_retrieve(self, memory):
        """Test caching and retrieving search results."""
        results = [{"name": "pandas", "version": "2.0"}]
        memory.cache_search("pandas", results, "pypi", ttl_seconds=3600)

        cached = memory.get_cached_search("pandas", "pypi")
        assert cached is not None
        assert cached[0]["name"] == "pandas"

    def test_cache_miss(self, memory):
        """Test that non-cached queries return None."""
        result = memory.get_cached_search("some-package", "pypi")
        assert result is None

    def test_cache_expiry(self, memory):
        """Test that expired cache returns None."""
        results = [{"name": "test"}]
        memory.cache_search("test", results, "pypi", ttl_seconds=-1)  # Already expired

        cached = memory.get_cached_search("test", "pypi")
        assert cached is None


class TestPreferences:
    def test_set_and_get(self, memory):
        """Test setting and getting preferences."""
        memory.set_preference("model", "claude-sonnet-4-6")
        assert memory.get_preference("model") == "claude-sonnet-4-6"

    def test_preference_default(self, memory):
        """Test default value for missing preference."""
        result = memory.get_preference("nonexistent", default="fallback")
        assert result == "fallback"

    def test_preference_upsert(self, memory):
        """Test that setting same key updates value."""
        memory.set_preference("key", "value1")
        memory.set_preference("key", "value2")
        assert memory.get_preference("key") == "value2"

    def test_get_all_preferences(self, memory):
        """Test getting all preferences."""
        memory.set_preference("a", 1)
        memory.set_preference("b", "two")
        prefs = memory.get_all_preferences()
        assert prefs["a"] == 1
        assert prefs["b"] == "two"
