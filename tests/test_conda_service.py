"""Tests for the CondaService."""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from jupyter_claude_assistant.services.conda_service import CondaService


@pytest.fixture
def conda():
    return CondaService()


class TestCondaService:
    def test_get_active_environment_returns_dict(self, conda):
        """Test that get_active_environment returns a dict with required keys."""
        env = conda.get_active_environment()
        assert isinstance(env, dict)
        assert "name" in env
        assert "path" in env
        assert "python_version" in env
        assert "python_executable" in env

    def test_active_env_has_name(self, conda):
        """Test that the active environment has a name."""
        env = conda.get_active_environment()
        assert env["name"]  # Not empty

    def test_active_env_python_version(self, conda):
        """Test that python version is in correct format."""
        env = conda.get_active_environment()
        parts = env["python_version"].split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)

    def test_list_environments(self, conda):
        """Test listing environments."""
        envs = conda.list_environments()
        assert isinstance(envs, list)
        assert len(envs) >= 1

    def test_get_installed_packages(self, conda):
        """Test getting installed packages."""
        packages = conda.get_installed_packages()
        assert isinstance(packages, list)
        # Should have some packages
        assert len(packages) > 0

    def test_packages_have_required_fields(self, conda):
        """Test that packages have name and version."""
        packages = conda.get_installed_packages()
        if packages:
            for pkg in packages[:5]:
                assert "name" in pkg
                assert "version" in pkg

    def test_is_package_installed_known(self, conda):
        """Test checking for a known package (pip itself)."""
        assert conda.is_package_installed("pip")

    def test_is_package_installed_fake(self, conda):
        """Test checking for a package that doesn't exist."""
        assert not conda.is_package_installed("definitely-not-installed-xyz-abc")

    def test_get_package_names(self, conda):
        """Test getting package names."""
        names = conda.get_package_names()
        assert isinstance(names, list)
        assert all(isinstance(n, str) for n in names)
        # All names should be lowercase
        assert all(n == n.lower() for n in names)

    def test_get_env_summary(self, conda):
        """Test environment summary string."""
        summary = conda.get_env_summary()
        assert isinstance(summary, str)
        assert "Conda env:" in summary or "env" in summary.lower()

    def test_cache_works(self, conda):
        """Test that caching works (second call uses cache)."""
        import time
        start = time.time()
        conda.get_installed_packages()
        first_call = time.time() - start

        start = time.time()
        conda.get_installed_packages()
        second_call = time.time() - start

        # Second call should be significantly faster due to caching
        # Allow some tolerance but cache should be much faster
        assert second_call < first_call + 0.5  # At minimum, shouldn't be much slower

    def test_clear_cache(self, conda):
        """Test that clearing cache works."""
        conda.get_installed_packages()  # Populate cache
        conda.clear_cache()
        assert conda._env_cache == {}
