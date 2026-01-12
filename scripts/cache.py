#!/usr/bin/env python3
"""
cache.py - Local caching for arXiv Research Skill

Provides SQLite-based caching to reduce API calls.
Cache location: ~/.cache/arxiv-research/papers.db

Expiration policy:
- Paper metadata: Never expires (title, authors, abstract don't change)
- Citation counts: 7 days (these update over time)
- References: 7 days (Semantic Scholar may update)
"""

import json
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# Cache configuration
CACHE_DIR = Path.home() / ".cache" / "arxiv-research"
DB_PATH = CACHE_DIR / "papers.db"
CITATION_TTL_DAYS = 7
REFERENCES_TTL_DAYS = 7


@dataclass
class CachedPaper:
    """Cached paper metadata."""
    id_arxiv: str
    title: str
    abstract: str
    authors: list[str]
    categories: list[str]
    url_abstract: str
    url_pdf: str
    date_published: Optional[str] = None


@dataclass
class CachedCitation:
    """Cached citation data."""
    id_arxiv: str
    citation_count: int
    influential_count: int
    cached_at: float


@dataclass
class CachedReference:
    """Cached reference entry."""
    id_arxiv: str  # Source paper ID
    ref_paper_id: Optional[str]  # Referenced paper's arXiv ID (if available)
    ref_title: str
    ref_authors: list[str]
    ref_year: Optional[int]


class PaperCache:
    """SQLite-based cache for paper data."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self._ensureCacheDir()
        self._initDb()

    def _ensureCacheDir(self):
        """Ensure cache directory exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _initDb(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS papers (
                    id_arxiv TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    abstract TEXT,
                    authors TEXT NOT NULL,
                    categories TEXT,
                    url_abstract TEXT,
                    url_pdf TEXT,
                    date_published TEXT,
                    cached_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS citations (
                    id_arxiv TEXT PRIMARY KEY,
                    citation_count INTEGER,
                    influential_count INTEGER,
                    cached_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS refs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id TEXT NOT NULL,
                    ref_paper_id TEXT,
                    ref_title TEXT NOT NULL,
                    ref_authors TEXT,
                    ref_year INTEGER,
                    cached_at REAL NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_refs_source ON refs(source_id);
                CREATE INDEX IF NOT EXISTS idx_citations_cached ON citations(cached_at);
                CREATE INDEX IF NOT EXISTS idx_refs_cached ON refs(cached_at);
            """)

    # Paper methods
    def getPaper(self, arxiv_id: str) -> Optional[CachedPaper]:
        """Get cached paper metadata. Never expires."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT id_arxiv, title, abstract, authors, categories, "
                "url_abstract, url_pdf, date_published FROM papers WHERE id_arxiv = ?",
                (arxiv_id,)
            )
            row = cursor.fetchone()
            if row:
                return CachedPaper(
                    id_arxiv=row[0],
                    title=row[1],
                    abstract=row[2],
                    authors=json.loads(row[3]),
                    categories=json.loads(row[4]) if row[4] else [],
                    url_abstract=row[5],
                    url_pdf=row[6],
                    date_published=row[7]
                )
        return None

    def savePaper(self, paper: CachedPaper):
        """Save paper metadata to cache."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO papers
                   (id_arxiv, title, abstract, authors, categories,
                    url_abstract, url_pdf, date_published, cached_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    paper.id_arxiv,
                    paper.title,
                    paper.abstract,
                    json.dumps(paper.authors),
                    json.dumps(paper.categories),
                    paper.url_abstract,
                    paper.url_pdf,
                    paper.date_published,
                    time.time()
                )
            )

    def savePapers(self, papers: list[CachedPaper]):
        """Save multiple papers to cache."""
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                """INSERT OR REPLACE INTO papers
                   (id_arxiv, title, abstract, authors, categories,
                    url_abstract, url_pdf, date_published, cached_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        p.id_arxiv,
                        p.title,
                        p.abstract,
                        json.dumps(p.authors),
                        json.dumps(p.categories),
                        p.url_abstract,
                        p.url_pdf,
                        p.date_published,
                        now
                    )
                    for p in papers
                ]
            )

    # Citation methods
    def getCitations(self, arxiv_id: str) -> Optional[dict]:
        """Get cached citation data. Returns None if expired or not found."""
        ttl_seconds = CITATION_TTL_DAYS * 24 * 60 * 60
        min_time = time.time() - ttl_seconds

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT citation_count, influential_count FROM citations "
                "WHERE id_arxiv = ? AND cached_at > ?",
                (arxiv_id, min_time)
            )
            row = cursor.fetchone()
            if row:
                return {
                    "citation_count": row[0],
                    "influential_count": row[1]
                }
        return None

    def saveCitations(self, arxiv_id: str, citation_count: int, influential_count: int):
        """Save citation data to cache."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO citations
                   (id_arxiv, citation_count, influential_count, cached_at)
                   VALUES (?, ?, ?, ?)""",
                (arxiv_id, citation_count, influential_count, time.time())
            )

    # References methods
    def getReferences(self, arxiv_id: str) -> Optional[list[CachedReference]]:
        """Get cached references. Returns None if expired or not found."""
        ttl_seconds = REFERENCES_TTL_DAYS * 24 * 60 * 60
        min_time = time.time() - ttl_seconds

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT ref_paper_id, ref_title, ref_authors, ref_year FROM refs "
                "WHERE source_id = ? AND cached_at > ?",
                (arxiv_id, min_time)
            )
            rows = cursor.fetchall()
            if rows:
                return [
                    CachedReference(
                        id_arxiv=arxiv_id,
                        ref_paper_id=row[0],
                        ref_title=row[1],
                        ref_authors=json.loads(row[2]) if row[2] else [],
                        ref_year=row[3]
                    )
                    for row in rows
                ]
        return None

    def saveReferences(self, arxiv_id: str, references: list[CachedReference]):
        """Save references to cache."""
        now = time.time()

        with sqlite3.connect(self.db_path) as conn:
            # Remove old references for this paper
            conn.execute("DELETE FROM refs WHERE source_id = ?", (arxiv_id,))

            # Insert new references
            conn.executemany(
                """INSERT INTO refs
                   (source_id, ref_paper_id, ref_title, ref_authors, ref_year, cached_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                [
                    (
                        arxiv_id,
                        ref.ref_paper_id,
                        ref.ref_title,
                        json.dumps(ref.ref_authors),
                        ref.ref_year,
                        now
                    )
                    for ref in references
                ]
            )

    # Maintenance methods
    def clearExpired(self):
        """Remove expired citation and reference data."""
        citation_min = time.time() - (CITATION_TTL_DAYS * 24 * 60 * 60)
        refs_min = time.time() - (REFERENCES_TTL_DAYS * 24 * 60 * 60)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM citations WHERE cached_at < ?", (citation_min,))
            conn.execute("DELETE FROM refs WHERE cached_at < ?", (refs_min,))

    def clear(self):
        """Clear all cached data."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM papers")
            conn.execute("DELETE FROM citations")
            conn.execute("DELETE FROM refs")

    def stats(self) -> dict:
        """Get cache statistics."""
        with sqlite3.connect(self.db_path) as conn:
            papers = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
            citations = conn.execute("SELECT COUNT(*) FROM citations").fetchone()[0]
            refs = conn.execute("SELECT COUNT(*) FROM refs").fetchone()[0]

            return {
                "papers": papers,
                "citations": citations,
                "references": refs,
                "db_path": str(self.db_path),
                "db_size_kb": round(os.path.getsize(self.db_path) / 1024, 2) if self.db_path.exists() else 0
            }
