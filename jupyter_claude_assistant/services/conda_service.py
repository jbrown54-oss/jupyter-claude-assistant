"""
Conda Environment Service - Detects and manages conda environments.

Provides information about:
- Active conda environment
- Installed packages per environment
- Available environments
- Package availability checks
"""

import os
import sys
import json
import subprocess
import logging
from typing import Optional
from functools import lru_cache

logger = logging.getLogger(__name__)


class CondaService:
    """Detects and queries conda environments."""

    def __init__(self):
        self._conda_path = self._find_conda()
        self._env_cache: dict = {}

    def _find_conda(self) -> Optional[str]:
        """Find the conda executable."""
        candidates = [
            # Windows Anaconda default locations
            os.path.expanduser("~/anaconda3/Scripts/conda.exe"),
            os.path.expanduser("~/miniconda3/Scripts/conda.exe"),
            os.path.expanduser("~/miniforge3/Scripts/conda.exe"),
            # Via PATH
            "conda",
        ]

        # Check the current Python's conda
        python_base = os.path.dirname(sys.executable)
        candidates.insert(0, os.path.join(python_base, "conda"))
        candidates.insert(0, os.path.join(python_base, "conda.exe"))
        candidates.insert(0, os.path.join(python_base, "Scripts", "conda.exe"))

        for candidate in candidates:
            try:
                result = subprocess.run(
                    [candidate, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    logger.info(f"Found conda at: {candidate}")
                    return candidate
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                continue

        logger.warning("Could not find conda executable")
        return None

    def get_active_environment(self) -> dict:
        """
        Get information about the currently active conda environment.
        Returns dict with name, path, python_version.
        """
        env_name = os.environ.get("CONDA_DEFAULT_ENV", "")
        env_path = os.environ.get("CONDA_PREFIX", "")

        # If not set via env vars, infer from current Python
        if not env_name:
            python_path = sys.executable
            # Extract env name from path
            path_parts = python_path.replace("\\", "/").split("/")
            if "envs" in path_parts:
                idx = path_parts.index("envs")
                if idx + 1 < len(path_parts):
                    env_name = path_parts[idx + 1]
            else:
                env_name = "base"

        if not env_path:
            env_path = os.path.dirname(os.path.dirname(sys.executable))

        return {
            "name": env_name or "base",
            "path": env_path,
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "python_executable": sys.executable,
        }

    def list_environments(self) -> list[dict]:
        """List all conda environments."""
        if not self._conda_path:
            return [self.get_active_environment()]

        try:
            result = subprocess.run(
                [self._conda_path, "env", "list", "--json"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                envs = []
                for path in data.get("envs", []):
                    name = os.path.basename(path)
                    if path == data["envs"][0]:
                        name = "base"
                    envs.append({"name": name, "path": path})
                return envs
        except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:
            logger.error(f"Error listing environments: {e}")

        return [self.get_active_environment()]

    def get_installed_packages(self, env_name: str = None) -> list[dict]:
        """
        Get list of installed packages in an environment.
        Returns list of dicts with name, version.
        """
        # Check cache first
        cache_key = env_name or "current"
        if cache_key in self._env_cache:
            return self._env_cache[cache_key]

        packages = []

        if self._conda_path and env_name:
            # Use conda to list packages in specific env
            try:
                result = subprocess.run(
                    [self._conda_path, "list", "--name", env_name, "--json"],
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                if result.returncode == 0:
                    data = json.loads(result.stdout)
                    packages = [
                        {"name": p["name"], "version": p["version"], "channel": p.get("channel", "")}
                        for p in data
                    ]
                    self._env_cache[cache_key] = packages
                    return packages
            except Exception as e:
                logger.error(f"Error getting conda packages: {e}")

        # Fall back to pip list for current environment
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "list", "--format=json"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                packages = [{"name": p["name"], "version": p["version"], "channel": "pip"} for p in data]
                self._env_cache[cache_key] = packages
                return packages
        except Exception as e:
            logger.error(f"Error getting pip packages: {e}")

        return packages

    def get_package_names(self, env_name: str = None) -> list[str]:
        """Get just the package names for the given environment."""
        packages = self.get_installed_packages(env_name)
        return [p["name"].lower() for p in packages]

    def is_package_installed(self, package_name: str, env_name: str = None) -> bool:
        """Check if a specific package is installed."""
        names = self.get_package_names(env_name)
        return package_name.lower() in names

    def get_env_summary(self, env_name: str = None) -> str:
        """
        Get a human-readable summary of the environment.
        Used for Claude context.
        """
        env = self.get_active_environment()
        packages = self.get_installed_packages(env_name)

        # Key packages to highlight
        key_pkg_names = {
            "numpy", "pandas", "matplotlib", "scipy", "sklearn", "scikit-learn",
            "tensorflow", "torch", "keras", "seaborn", "plotly", "bokeh",
            "jupyter", "jupyterlab", "ipywidgets", "requests", "sqlalchemy",
            "flask", "fastapi", "django", "pytest", "black", "mypy",
            "transformers", "datasets", "xgboost", "lightgbm", "statsmodels",
            "PIL", "pillow", "cv2", "opencv", "nltk", "spacy", "gensim",
        }

        installed_names = {p["name"].lower() for p in packages}
        key_installed = sorted(installed_names & {k.lower() for k in key_pkg_names})

        summary = f"Conda env: {env['name']} (Python {env['python_version']})\n"
        summary += f"Total packages: {len(packages)}\n"
        if key_installed:
            summary += f"Key packages: {', '.join(key_installed)}"

        return summary

    def clear_cache(self):
        """Clear the package cache."""
        self._env_cache.clear()
