"""
Memory Service - SQLite-backed persistent memory for the AI assistant.

Stores:
- Past interactions and their ratings
- Notebook patterns and solutions that worked well
- User preferences
- Code snippets and their contexts
- Search results for caching
"""

import sqlite3
import json
import os
import time
import hashlib
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default database location
DEFAULT_DB_PATH = os.path.join(
    os.path.expanduser("~"),
    ".jupyter_claude",
    "memory.db",
)


class MemoryService:
    """Persistent memory and skills database using SQLite."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_database()

    def _init_database(self):
        """Initialize the database schema."""
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    request_type TEXT NOT NULL,
                    prompt_hash TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    response TEXT NOT NULL,
                    rating INTEGER DEFAULT NULL,
                    conda_env TEXT DEFAULT '',
                    notebook_name TEXT DEFAULT '',
                    tokens_used INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS skills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT NOT NULL,
                    code_template TEXT NOT NULL,
                    tags TEXT DEFAULT '[]',
                    use_count INTEGER DEFAULT 0,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS snippets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    code TEXT NOT NULL,
                    language TEXT DEFAULT 'python',
                    tags TEXT DEFAULT '[]',
                    conda_env TEXT DEFAULT '',
                    use_count INTEGER DEFAULT 0,
                    created_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS search_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_hash TEXT NOT NULL UNIQUE,
                    query TEXT NOT NULL,
                    results TEXT NOT NULL,
                    source TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS notebook_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    notebook_path TEXT NOT NULL,
                    conda_env TEXT DEFAULT '',
                    session_start REAL NOT NULL,
                    session_end REAL,
                    cell_count INTEGER DEFAULT 0,
                    interactions INTEGER DEFAULT 0,
                    summary TEXT DEFAULT ''
                );

                CREATE INDEX IF NOT EXISTS idx_interactions_timestamp
                    ON interactions(timestamp);
                CREATE INDEX IF NOT EXISTS idx_interactions_type
                    ON interactions(request_type);
                CREATE INDEX IF NOT EXISTS idx_search_cache_hash
                    ON search_cache(query_hash);
            """)

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _hash(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    # -------------------------------------------------------------------------
    # Interactions
    # -------------------------------------------------------------------------

    def save_interaction(
        self,
        request_type: str,
        prompt: str,
        response: str,
        conda_env: str = "",
        notebook_name: str = "",
        tokens_used: int = 0,
    ) -> int:
        """Save an interaction to the database. Returns the interaction ID."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                """INSERT INTO interactions
                   (timestamp, request_type, prompt_hash, prompt, response,
                    conda_env, notebook_name, tokens_used)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    time.time(),
                    request_type,
                    self._hash(prompt),
                    prompt[:2000],  # Limit stored prompt size
                    response[:10000],  # Limit stored response size
                    conda_env,
                    notebook_name,
                    tokens_used,
                ),
            )
            return cursor.lastrowid

    def rate_interaction(self, interaction_id: int, rating: int):
        """Rate an interaction (1-5 scale)."""
        rating = max(1, min(5, rating))
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE interactions SET rating = ? WHERE id = ?",
                (rating, interaction_id),
            )

    def get_recent_interactions(self, limit: int = 10, request_type: str = None) -> list[dict]:
        """Get recent interactions, optionally filtered by type."""
        query = "SELECT * FROM interactions"
        params = []
        if request_type:
            query += " WHERE request_type = ?"
            params.append(request_type)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with self._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def find_similar_interaction(self, prompt: str, request_type: str = None) -> Optional[dict]:
        """Find a cached response for a similar prompt."""
        prompt_hash = self._hash(prompt)
        query = "SELECT * FROM interactions WHERE prompt_hash = ?"
        params = [prompt_hash]
        if request_type:
            query += " AND request_type = ?"
            params.append(request_type)
        query += " ORDER BY rating DESC, timestamp DESC LIMIT 1"

        with self._get_conn() as conn:
            row = conn.execute(query, params).fetchone()
            return dict(row) if row else None

    def get_stats(self) -> dict:
        """Get usage statistics."""
        with self._get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM interactions").fetchone()[0]
            by_type = conn.execute(
                "SELECT request_type, COUNT(*) as count FROM interactions GROUP BY request_type"
            ).fetchall()
            avg_rating = conn.execute(
                "SELECT AVG(rating) FROM interactions WHERE rating IS NOT NULL"
            ).fetchone()[0]

            return {
                "total_interactions": total,
                "by_type": {row["request_type"]: row["count"] for row in by_type},
                "average_rating": round(avg_rating or 0, 2),
            }

    # -------------------------------------------------------------------------
    # Skills (reusable code patterns)
    # -------------------------------------------------------------------------

    def save_skill(self, name: str, description: str, code_template: str, tags: list[str] = None):
        """Save a reusable skill/code pattern."""
        now = time.time()
        tags_json = json.dumps(tags or [])
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO skills (name, description, code_template, tags, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(name) DO UPDATE SET
                     description=excluded.description,
                     code_template=excluded.code_template,
                     tags=excluded.tags,
                     updated_at=excluded.updated_at""",
                (name, description, code_template, tags_json, now, now),
            )

    def search_skills(self, query: str, limit: int = 5) -> list[dict]:
        """Search skills by name or description."""
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT * FROM skills
                   WHERE name LIKE ? OR description LIKE ? OR tags LIKE ?
                   ORDER BY use_count DESC LIMIT ?""",
                (f"%{query}%", f"%{query}%", f"%{query}%", limit),
            ).fetchall()
            return [dict(row) for row in rows]

    def use_skill(self, skill_id: int):
        """Increment use count for a skill."""
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE skills SET use_count = use_count + 1, updated_at = ? WHERE id = ?",
                (time.time(), skill_id),
            )

    def get_all_skills(self) -> list[dict]:
        """Get all saved skills."""
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM skills ORDER BY use_count DESC").fetchall()
            return [dict(row) for row in rows]

    # -------------------------------------------------------------------------
    # Code Snippets
    # -------------------------------------------------------------------------

    def save_snippet(self, title: str, code: str, tags: list[str] = None, conda_env: str = ""):
        """Save a code snippet."""
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO snippets (title, code, tags, conda_env, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (title, code, json.dumps(tags or []), conda_env, time.time()),
            )

    def search_snippets(self, query: str, limit: int = 5) -> list[dict]:
        """Search saved snippets."""
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT * FROM snippets
                   WHERE title LIKE ? OR code LIKE ? OR tags LIKE ?
                   ORDER BY use_count DESC LIMIT ?""",
                (f"%{query}%", f"%{query}%", f"%{query}%", limit),
            ).fetchall()
            return [dict(row) for row in rows]

    # -------------------------------------------------------------------------
    # Search Cache
    # -------------------------------------------------------------------------

    def cache_search(self, query: str, results: list, source: str, ttl_seconds: int = 3600):
        """Cache search results."""
        now = time.time()
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO search_cache (query_hash, query, results, source, created_at, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(query_hash) DO UPDATE SET
                     results=excluded.results,
                     created_at=excluded.created_at,
                     expires_at=excluded.expires_at""",
                (self._hash(f"{source}:{query}"), query, json.dumps(results), source, now, now + ttl_seconds),
            )

    def get_cached_search(self, query: str, source: str) -> Optional[list]:
        """Get cached search results if not expired."""
        with self._get_conn() as conn:
            row = conn.execute(
                """SELECT results FROM search_cache
                   WHERE query_hash = ? AND expires_at > ?""",
                (self._hash(f"{source}:{query}"), time.time()),
            ).fetchone()
            return json.loads(row["results"]) if row else None

    # -------------------------------------------------------------------------
    # Preferences
    # -------------------------------------------------------------------------

    def set_preference(self, key: str, value):
        """Save a user preference."""
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO preferences (key, value, updated_at) VALUES (?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
                (key, json.dumps(value), time.time()),
            )

    def get_preference(self, key: str, default=None):
        """Get a user preference."""
        with self._get_conn() as conn:
            row = conn.execute("SELECT value FROM preferences WHERE key = ?", (key,)).fetchone()
            return json.loads(row["value"]) if row else default

    def get_all_preferences(self) -> dict:
        """Get all preferences."""
        with self._get_conn() as conn:
            rows = conn.execute("SELECT key, value FROM preferences").fetchall()
            return {row["key"]: json.loads(row["value"]) for row in rows}
