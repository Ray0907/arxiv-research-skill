"""Semantic Scholar client: citations, references, similar papers, coauthors."""

import sys
import time
from typing import Optional

import httpx

from cache import PaperCache
from models import Paper
from utils import SEMANTIC_SCHOLAR_RATE_LIMIT_DELAY, TIMEOUT

SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1"


class SemanticScholarClient:
    """Client for Semantic Scholar API operations."""

    def __init__(self, api_key: Optional[str] = None, cache: Optional[PaperCache] = None):
        headers = {}
        if api_key:
            headers["x-api-key"] = api_key
        self.client = httpx.Client(
            timeout=TIMEOUT,
            headers=headers,
            follow_redirects=True
        )
        self.last_request_time = 0
        self.cache = cache

    def _rateLimit(self):
        """Ensure rate limiting."""
        elapsed = time.time() - self.last_request_time
        if elapsed < SEMANTIC_SCHOLAR_RATE_LIMIT_DELAY:
            time.sleep(SEMANTIC_SCHOLAR_RATE_LIMIT_DELAY - elapsed)
        self.last_request_time = time.time()

    def getCitations(self, arxiv_id: str) -> dict:
        """Get citation data for an arXiv paper. Cached for CITATION_TTL_DAYS."""
        if self.cache:
            cached = self.cache.getCitations(arxiv_id)
            if cached:
                return {
                    "citationCount": cached["citation_count"],
                    "influentialCitationCount": cached["influential_count"],
                }

        self._rateLimit()

        url = f"{SEMANTIC_SCHOLAR_API}/paper/arXiv:{arxiv_id}"
        params = {"fields": "citationCount,influentialCitationCount,title,authors"}

        try:
            response = self.client.get(url, params=params)
            if response.status_code == 404:
                return {}
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            print(f"Warning: Semantic Scholar request failed ({e.response.status_code}): {url}", file=sys.stderr)
            return {}
        except httpx.HTTPError as e:
            print(f"Warning: Semantic Scholar request error: {e}", file=sys.stderr)
            return {}

        if self.cache and "citationCount" in data:
            self.cache.saveCitations(
                arxiv_id,
                data.get("citationCount") or 0,
                data.get("influentialCitationCount") or 0,
            )

        return data

    def getSimilar(self, arxiv_id: str, limit: int = 10) -> list[dict]:
        """Get similar papers based on an arXiv paper."""
        self._rateLimit()

        url = f"{SEMANTIC_SCHOLAR_API}/paper/arXiv:{arxiv_id}/recommendations"
        params = {
            "fields": "externalIds,title,authors,citationCount,year",
            "limit": limit
        }

        try:
            response = self.client.get(url, params=params)
            if response.status_code == 404:
                return []
            response.raise_for_status()
            data = response.json()
            return data.get("recommendedPapers", [])
        except httpx.HTTPStatusError as e:
            print(f"Warning: Semantic Scholar request failed ({e.response.status_code}): {url}", file=sys.stderr)
            return []
        except httpx.HTTPError as e:
            print(f"Warning: Semantic Scholar request error: {e}", file=sys.stderr)
            return []

    def enrichWithCitations(self, papers: list[Paper]) -> list[Paper]:
        """Add citation data to a list of papers.

        Cache hits are applied directly; remaining papers are fetched in a single
        batch request instead of one request per paper.
        """
        to_fetch = []
        for paper in papers:
            if not paper.id_arxiv:
                continue
            cached = self.cache.getCitations(paper.id_arxiv) if self.cache else None
            if cached:
                paper.citation_count = cached["citation_count"]
                paper.influential_citation_count = cached["influential_count"]
            else:
                to_fetch.append(paper)

        if not to_fetch:
            return papers

        self._rateLimit()
        url = f"{SEMANTIC_SCHOLAR_API}/paper/batch"
        params = {"fields": "externalIds,citationCount,influentialCitationCount"}
        body = {"ids": [f"ARXIV:{p.id_arxiv}" for p in to_fetch]}

        try:
            response = self.client.post(url, params=params, json=body)
            response.raise_for_status()
            results = response.json()
        except httpx.HTTPStatusError as e:
            print(f"Warning: Semantic Scholar batch request failed ({e.response.status_code}): {url}", file=sys.stderr)
            return papers
        except httpx.HTTPError as e:
            print(f"Warning: Semantic Scholar batch request error: {e}", file=sys.stderr)
            return papers

        by_arxiv_id = {}
        for entry in results:
            if not entry:
                continue
            arxiv_id = (entry.get("externalIds") or {}).get("ArXiv")
            if arxiv_id:
                by_arxiv_id[arxiv_id] = entry

        for paper in to_fetch:
            entry = by_arxiv_id.get(paper.id_arxiv)
            if not entry:
                continue
            citation_count = entry.get("citationCount") or 0
            influential_count = entry.get("influentialCitationCount") or 0
            paper.citation_count = citation_count
            paper.influential_citation_count = influential_count
            if self.cache:
                self.cache.saveCitations(paper.id_arxiv, citation_count, influential_count)

        return papers

    def getReferences(self, arxiv_id: str, limit: int = 50) -> list[dict]:
        """Get references (papers cited by) an arXiv paper."""
        self._rateLimit()

        url = f"{SEMANTIC_SCHOLAR_API}/paper/arXiv:{arxiv_id}/references"
        params = {
            "fields": "externalIds,title,authors,year",
            "limit": limit
        }

        try:
            response = self.client.get(url, params=params)
            if response.status_code == 404:
                return []
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
        except httpx.HTTPStatusError as e:
            print(f"Warning: Semantic Scholar request failed ({e.response.status_code}): {url}", file=sys.stderr)
            return []
        except httpx.HTTPError as e:
            print(f"Warning: Semantic Scholar request error: {e}", file=sys.stderr)
            return []

    def getCitedBy(self, arxiv_id: str, limit: int = 50) -> list[dict]:
        """Get citations (papers that cite this paper)."""
        self._rateLimit()

        url = f"{SEMANTIC_SCHOLAR_API}/paper/arXiv:{arxiv_id}/citations"
        params = {
            "fields": "externalIds,title,authors,year,citationCount",
            "limit": limit
        }

        try:
            response = self.client.get(url, params=params)
            if response.status_code == 404:
                return []
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
        except httpx.HTTPStatusError as e:
            print(f"Warning: Semantic Scholar request failed ({e.response.status_code}): {url}", file=sys.stderr)
            return []
        except httpx.HTTPError as e:
            print(f"Warning: Semantic Scholar request error: {e}", file=sys.stderr)
            return []

    def searchAuthor(self, name: str) -> Optional[dict]:
        """Search for an author by name and return the best match."""
        self._rateLimit()

        url = f"{SEMANTIC_SCHOLAR_API}/author/search"
        params = {"query": name, "limit": 1}

        try:
            response = self.client.get(url, params=params)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            data = response.json()
            authors = data.get("data", [])
            return authors[0] if authors else None
        except httpx.HTTPStatusError as e:
            print(f"Warning: Semantic Scholar request failed ({e.response.status_code}): {url}", file=sys.stderr)
            return None
        except httpx.HTTPError as e:
            print(f"Warning: Semantic Scholar request error: {e}", file=sys.stderr)
            return None

    def getCoauthors(self, author_name: str, limit: int = 100) -> dict:
        """Get coauthors for an author by analyzing their papers.

        Returns dict with author info and coauthor statistics.
        """
        # First find the author
        author = self.searchAuthor(author_name)
        if not author:
            return {"error": "Author not found"}

        author_id = author.get("authorId")
        author_name_found = author.get("name", author_name)

        # Get author's papers
        self._rateLimit()
        url = f"{SEMANTIC_SCHOLAR_API}/author/{author_id}/papers"
        params = {
            "fields": "title,authors,year",
            "limit": limit
        }

        try:
            response = self.client.get(url, params=params)
            if response.status_code == 404:
                return {"error": "Could not fetch papers"}
            response.raise_for_status()
            data = response.json()
            papers = data.get("data", [])
        except Exception as e:
            return {"error": str(e)}

        # Count coauthors
        coauthor_counts = {}
        for paper in papers:
            for coauthor in paper.get("authors", []):
                coauthor_id = coauthor.get("authorId")
                coauthor_name = coauthor.get("name", "Unknown")
                if coauthor_id and coauthor_id != author_id:
                    if coauthor_id not in coauthor_counts:
                        coauthor_counts[coauthor_id] = {
                            "name": coauthor_name,
                            "count": 0,
                            "papers": []
                        }
                    coauthor_counts[coauthor_id]["count"] += 1
                    coauthor_counts[coauthor_id]["papers"].append(paper.get("title", ""))

        # Sort by collaboration count
        sorted_coauthors = sorted(
            coauthor_counts.values(),
            key=lambda x: x["count"],
            reverse=True
        )

        return {
            "author_id": author_id,
            "author_name": author_name_found,
            "total_papers": len(papers),
            "coauthors": sorted_coauthors
        }

    def close(self):
        self.client.close()
