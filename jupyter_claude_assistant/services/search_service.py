"""
Search Service - Searches PyPI, GitHub, and Stack Overflow for packages and solutions.

Used to provide relevant package suggestions and code examples.
"""

import json
import logging
import urllib.request
import urllib.parse
import urllib.error
import time
from typing import Optional

logger = logging.getLogger(__name__)

PYPI_API = "https://pypi.org/pypi/{package}/json"
PYPI_SEARCH = "https://pypi.org/search/?q={query}&format=json"
GITHUB_SEARCH_REPOS = "https://api.github.com/search/repositories?q={query}+language:python&sort=stars&per_page=5"
GITHUB_SEARCH_CODE = "https://api.github.com/search/code?q={query}+language:python&per_page=3"
SO_SEARCH = "https://api.stackexchange.com/2.3/search/advanced?order=desc&sort=votes&q={query}&site=stackoverflow&pagesize=5&filter=withbody"


class SearchService:
    """Searches external sources for package and code information."""

    def __init__(self, memory_service=None, github_token: str = None):
        self.memory = memory_service
        self.github_token = github_token
        self._timeout = 10

    def _fetch(self, url: str, headers: dict = None) -> Optional[dict]:
        """Fetch JSON from a URL."""
        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "jupyter-claude-assistant/1.0")
            if headers:
                for key, value in headers.items():
                    req.add_header(key, value)

            with urllib.request.urlopen(req, timeout=self._timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
                return data
        except urllib.error.HTTPError as e:
            logger.warning(f"HTTP error fetching {url}: {e.code}")
        except urllib.error.URLError as e:
            logger.warning(f"URL error fetching {url}: {e.reason}")
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
        return None

    def search_pypi(self, query: str) -> list[dict]:
        """Search PyPI for packages matching the query."""
        # Check cache
        if self.memory:
            cached = self.memory.get_cached_search(query, "pypi")
            if cached:
                return cached

        url = f"https://pypi.org/search/?q={urllib.parse.quote(query)}"
        # Use the JSON API endpoint
        results = []

        # Try to get info about the exact package name first
        exact_url = PYPI_API.format(package=query.replace(" ", "-"))
        data = self._fetch(exact_url)
        if data and "info" in data:
            info = data["info"]
            results.append({
                "name": info["name"],
                "version": info["version"],
                "summary": info.get("summary", ""),
                "url": info.get("project_url", f"https://pypi.org/project/{info['name']}/"),
                "source": "pypi",
            })

        # Also search using simple search
        search_url = f"https://pypi.org/simple/"
        # Use PyPI's XML search endpoint for keyword search
        xml_url = f"https://pypi.org/search/?q={urllib.parse.quote(query)}&format=json"
        search_data = self._fetch(xml_url)
        if search_data and isinstance(search_data, list):
            for item in search_data[:5]:
                results.append({
                    "name": item.get("name", ""),
                    "version": item.get("version", ""),
                    "summary": item.get("summary", ""),
                    "url": f"https://pypi.org/project/{item.get('name', '')}/",
                    "source": "pypi",
                })

        # Cache results
        if self.memory and results:
            self.memory.cache_search(query, results, "pypi")

        return results

    def get_package_info(self, package_name: str) -> Optional[dict]:
        """Get detailed info about a specific PyPI package."""
        url = PYPI_API.format(package=package_name)
        data = self._fetch(url)
        if not data:
            return None

        info = data.get("info", {})
        return {
            "name": info.get("name"),
            "version": info.get("version"),
            "summary": info.get("summary"),
            "description": info.get("description", "")[:2000],
            "author": info.get("author"),
            "license": info.get("license"),
            "requires_python": info.get("requires_python"),
            "project_urls": info.get("project_urls", {}),
            "install_url": f"pip install {info.get('name', package_name)}",
            "conda_install": f"conda install {info.get('name', package_name)}",
            "source": "pypi",
        }

    def search_github(self, query: str) -> list[dict]:
        """Search GitHub for Python repositories."""
        # Check cache
        if self.memory:
            cached = self.memory.get_cached_search(query, "github")
            if cached:
                return cached

        headers = {}
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"

        url = GITHUB_SEARCH_REPOS.format(query=urllib.parse.quote(query))
        data = self._fetch(url, headers=headers)

        results = []
        if data and "items" in data:
            for repo in data["items"][:5]:
                results.append({
                    "name": repo["full_name"],
                    "description": repo.get("description", ""),
                    "stars": repo.get("stargazers_count", 0),
                    "url": repo.get("html_url", ""),
                    "language": repo.get("language", ""),
                    "topics": repo.get("topics", []),
                    "source": "github",
                })

        # Cache results
        if self.memory and results:
            self.memory.cache_search(query, results, "github")

        return results

    def search_stackoverflow(self, query: str) -> list[dict]:
        """Search Stack Overflow for relevant Q&A."""
        # Check cache
        if self.memory:
            cached = self.memory.get_cached_search(query, "stackoverflow")
            if cached:
                return cached

        url = SO_SEARCH.format(query=urllib.parse.quote(query))
        data = self._fetch(url)

        results = []
        if data and "items" in data:
            for item in data["items"][:5]:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "score": item.get("score", 0),
                    "answer_count": item.get("answer_count", 0),
                    "is_answered": item.get("is_answered", False),
                    "tags": item.get("tags", []),
                    "body_preview": item.get("body", "")[:300] if item.get("body") else "",
                    "source": "stackoverflow",
                })

        # Cache results
        if self.memory and results:
            self.memory.cache_search(query, results, "stackoverflow", ttl_seconds=7200)

        return results

    def search_all(self, query: str) -> dict:
        """Search all sources and return combined results."""
        results = {
            "query": query,
            "pypi": [],
            "github": [],
            "stackoverflow": [],
            "timestamp": time.time(),
        }

        # Run searches (sequentially to avoid rate limits)
        try:
            results["pypi"] = self.search_pypi(query)
        except Exception as e:
            logger.error(f"PyPI search error: {e}")

        try:
            results["github"] = self.search_github(query)
        except Exception as e:
            logger.error(f"GitHub search error: {e}")

        try:
            results["stackoverflow"] = self.search_stackoverflow(query)
        except Exception as e:
            logger.error(f"Stack Overflow search error: {e}")

        return results

    def format_results_for_claude(self, results: dict) -> str:
        """Format search results as context for Claude."""
        parts = [f"=== SEARCH RESULTS FOR: {results['query']} ===\n"]

        if results.get("pypi"):
            parts.append("PyPI Packages:")
            for pkg in results["pypi"][:3]:
                parts.append(f"  - {pkg['name']} v{pkg.get('version','?')}: {pkg.get('summary','')[:100]}")

        if results.get("github"):
            parts.append("\nGitHub Repositories:")
            for repo in results["github"][:3]:
                parts.append(f"  - {repo['name']} ({repo.get('stars',0)} stars): {repo.get('description','')[:100]}")

        if results.get("stackoverflow"):
            parts.append("\nStack Overflow:")
            for qa in results["stackoverflow"][:3]:
                status = "✓ Answered" if qa.get("is_answered") else "Open"
                parts.append(f"  - [{status}] {qa['title'][:100]}")

        return "\n".join(parts)
