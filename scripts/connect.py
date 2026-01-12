#!/usr/bin/env python3
"""
connect.py - Knowledge Navigation for arXiv Research

Core capability: Find relevant existing knowledge
Integrates arXiv search with Semantic Scholar for citation data.
"""

import argparse
import csv
import io
import json
import re
import sys
import time
import urllib.parse
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional

try:
    import httpx
except ImportError:
    print("Error: httpx required. Install with: pip install httpx")
    sys.exit(1)

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Error: beautifulsoup4 required. Install with: pip install beautifulsoup4")
    sys.exit(1)

from utils import extractPaperId, cleanText
from cache import PaperCache, CachedPaper, CachedReference


# Configuration
ARXIV_BASE = "https://arxiv.org"
ARXIV_EXPORT = "https://export.arxiv.org"
SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1"
JINA_READER = "https://r.jina.ai"
TIMEOUT = 30.0
RATE_LIMIT_DELAY = 1.0  # seconds between requests


@dataclass
class Paper:
    """Represents an academic paper."""
    id_arxiv: str
    title: str
    abstract: str
    authors: list[str]
    categories: list[str]
    url_abstract: str
    url_pdf: str
    date_published: Optional[str] = None
    citation_count: Optional[int] = None
    influential_citation_count: Optional[int] = None


class ArxivClient:
    """Client for arXiv operations."""

    def __init__(self):
        self.client = httpx.Client(timeout=TIMEOUT, follow_redirects=True)
        self.last_request_time = 0

    def _rateLimit(self):
        """Ensure rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        self.last_request_time = time.time()

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        author: Optional[str] = None,
        sort_by: str = "relevance",
        limit: int = 25,
        page: int = 1
    ) -> list[Paper]:
        """Search arXiv for papers using the API."""
        self._rateLimit()

        max_results = min(limit, 100)
        start = (page - 1) * max_results

        # Build search query for arXiv API
        search_parts = []
        if query:
            # Search in title, abstract, and all fields
            search_parts.append(f"all:{query}")
        if author:
            search_parts.append(f"au:{author}")
        if category:
            search_parts.append(f"cat:{category}")

        full_query = " AND ".join(search_parts) if search_parts else "all:*"

        # arXiv API sort options
        sort_options = {
            "relevance": "relevance",
            "date_desc": "submittedDate",
            "date_asc": "submittedDate",
            "citations": "relevance",  # Will sort after getting citation data
        }
        sort_order = sort_options.get(sort_by, "relevance")
        ascending = "ascending" if sort_by == "date_asc" else "descending"

        url = (
            f"{ARXIV_EXPORT}/api/query?"
            f"search_query={urllib.parse.quote(full_query)}"
            f"&start={start}&max_results={max_results}"
            f"&sortBy={sort_order}&sortOrder={ascending}"
        )

        response = self.client.get(url)
        response.raise_for_status()

        return self._parseApiResults(response.text)

    def _parseSearchResults(self, html: str) -> list[Paper]:
        """Parse arXiv search results HTML."""
        soup = BeautifulSoup(html, "html.parser")
        items = soup.select(".arxiv-result")

        papers = []
        for item in items:
            try:
                # Extract title
                title_elem = item.select_one(".title")
                title = cleanText(title_elem.text) if title_elem else "Unknown Title"

                # Extract abstract
                abstract_elem = item.select_one(".abstract-full")
                if not abstract_elem:
                    abstract_elem = item.select_one(".abstract")
                abstract = cleanText(abstract_elem.text) if abstract_elem else ""
                abstract = re.sub(r"\s*(Less|More)\s*$", "", abstract)
                abstract = re.sub(r"^Abstract:\s*", "", abstract)

                # Extract URL and ID
                url_elem = item.select_one(".list-title > span > a")
                url_abstract = url_elem.get("href") if url_elem else ""
                id_arxiv = extractPaperId(url_abstract) or ""

                # Extract authors
                authors = []
                authors_elem = item.select(".authors a")
                for author in authors_elem:
                    authors.append(author.text.strip())

                # Extract categories
                categories = []
                tags = item.select(".tag.is-small")
                for tag in tags:
                    cat_text = tag.text.strip()
                    if cat_text and not cat_text.startswith("doi:"):
                        categories.append(cat_text)

                # Extract dates
                date_elem = item.select_one(".is-size-7")
                date_published = None
                if date_elem:
                    date_text = date_elem.text
                    submitted_match = re.search(r"Submitted\s+(\d+\s+\w+,?\s+\d+)", date_text)
                    if submitted_match:
                        date_published = submitted_match.group(1)

                paper = Paper(
                    id_arxiv=id_arxiv,
                    title=title,
                    abstract=abstract,
                    authors=authors,
                    categories=categories,
                    url_abstract=url_abstract,
                    url_pdf=f"https://arxiv.org/pdf/{id_arxiv}.pdf" if id_arxiv else "",
                    date_published=date_published,
                )
                papers.append(paper)
            except Exception:
                continue

        return papers

    def _parseApiResults(self, xml_content: str) -> list[Paper]:
        """Parse arXiv API Atom feed results."""
        from xml.etree import ElementTree

        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom"
        }

        try:
            root = ElementTree.fromstring(xml_content)
        except ElementTree.ParseError:
            return []

        papers = []
        for entry in root.findall("atom:entry", ns):
            try:
                # Extract ID
                id_elem = entry.find("atom:id", ns)
                if id_elem is None:
                    continue

                id_text = id_elem.text or ""
                id_match = re.search(r"abs/(\d+\.\d+)", id_text)
                if not id_match:
                    continue
                id_arxiv = id_match.group(1)

                # Extract title
                title_elem = entry.find("atom:title", ns)
                title = " ".join((title_elem.text or "").split()) if title_elem is not None else ""

                # Extract authors
                authors = []
                for author in entry.findall("atom:author", ns):
                    name_elem = author.find("atom:name", ns)
                    if name_elem is not None and name_elem.text:
                        authors.append(name_elem.text)

                # Extract abstract
                summary_elem = entry.find("atom:summary", ns)
                abstract = " ".join((summary_elem.text or "").split()) if summary_elem is not None else ""

                # Extract categories
                categories = []
                for cat in entry.findall("atom:category", ns):
                    term = cat.get("term")
                    if term:
                        categories.append(term)

                # Extract published date
                published_elem = entry.find("atom:published", ns)
                date_published = published_elem.text if published_elem is not None else None

                paper = Paper(
                    id_arxiv=id_arxiv,
                    title=title,
                    abstract=abstract,
                    authors=authors,
                    categories=categories,
                    url_abstract=f"{ARXIV_BASE}/abs/{id_arxiv}",
                    url_pdf=f"{ARXIV_BASE}/pdf/{id_arxiv}.pdf",
                    date_published=date_published,
                )
                papers.append(paper)
            except Exception:
                continue

        return papers

    def getPaper(self, id_or_url: str) -> Optional[Paper]:
        """Get detailed information about a specific paper."""
        self._rateLimit()

        id_arxiv = extractPaperId(id_or_url)
        if not id_arxiv:
            return None

        url_abstract = f"{ARXIV_BASE}/abs/{id_arxiv}"
        response = self.client.get(url_abstract)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Extract title
        title_elem = soup.select_one(".title.mathjax")
        title = cleanText(title_elem.text.replace("Title:", "")) if title_elem else "Unknown"

        # Extract abstract
        abstract_elem = soup.select_one(".abstract.mathjax")
        abstract = cleanText(abstract_elem.text.replace("Abstract:", "")) if abstract_elem else ""

        # Extract authors
        authors = []
        authors_div = soup.select_one(".authors")
        if authors_div:
            for a in authors_div.select("a"):
                authors.append(a.text.strip())

        # Extract categories
        categories = []
        subj_elem = soup.select_one(".tablecell.subjects")
        if subj_elem:
            cat_matches = re.findall(r"\(([a-z-]+\.[A-Z]+)\)", subj_elem.text)
            categories = list(set(cat_matches))

        # Extract dates
        date_submitted = None
        date_history = soup.select_one(".dateline")
        if date_history:
            date_match = re.search(r"Submitted.*?(\d+\s+\w+\s+\d+)", date_history.text)
            if date_match:
                date_submitted = date_match.group(1)

        return Paper(
            id_arxiv=id_arxiv,
            title=title,
            abstract=abstract,
            authors=authors,
            categories=categories,
            url_abstract=url_abstract,
            url_pdf=f"{ARXIV_BASE}/pdf/{id_arxiv}.pdf",
            date_published=date_submitted,
        )

    def getRecent(self, category: str = "cs.AI", count: int = 10) -> list[Paper]:
        """Get recent papers from a category."""
        self._rateLimit()

        count = min(count, 50)
        url = f"{ARXIV_BASE}/list/{category}/recent?skip=0&show={count}"

        response = self.client.get(url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        papers = []
        entries = soup.select("dl#articles dt, dl#articles dd")

        i = 0
        while i < len(entries) - 1:
            if entries[i].name == "dt" and entries[i + 1].name == "dd":
                dt = entries[i]
                dd = entries[i + 1]

                # Extract ID
                id_link = dt.select_one("a[href*='/abs/']")
                id_arxiv = ""
                if id_link:
                    href = id_link.get("href", "")
                    id_match = re.search(r"/abs/(\d+\.\d+)", href)
                    if id_match:
                        id_arxiv = id_match.group(1)

                # Extract title
                title_elem = dd.select_one(".list-title")
                title = cleanText(title_elem.text.replace("Title:", "")) if title_elem else ""

                # Extract authors
                authors = []
                authors_elem = dd.select_one(".list-authors")
                if authors_elem:
                    for a in authors_elem.select("a"):
                        authors.append(a.text.strip())

                # Extract categories
                categories = []
                subj_elem = dd.select_one(".list-subjects")
                if subj_elem:
                    cat_matches = re.findall(r"([a-z-]+\.[A-Z]+)", subj_elem.text)
                    categories = list(set(cat_matches))

                if id_arxiv:
                    paper = Paper(
                        id_arxiv=id_arxiv,
                        title=title,
                        abstract="",  # Not available in list view
                        authors=authors,
                        categories=categories,
                        url_abstract=f"{ARXIV_BASE}/abs/{id_arxiv}",
                        url_pdf=f"{ARXIV_BASE}/pdf/{id_arxiv}.pdf",
                    )
                    papers.append(paper)

                i += 2
            else:
                i += 1

        return papers

    def getContent(self, id_or_url: str) -> str:
        """Get full text content using Jina Reader."""
        self._rateLimit()

        id_arxiv = extractPaperId(id_or_url)
        if not id_arxiv:
            url_target = id_or_url if id_or_url.startswith("http") else f"{ARXIV_BASE}/abs/{id_or_url}"
        else:
            url_target = f"{ARXIV_BASE}/abs/{id_arxiv}"

        jina_url = f"{JINA_READER}/{url_target}"

        response = self.client.get(jina_url, timeout=TIMEOUT * 2)
        response.raise_for_status()

        return response.text

    def close(self):
        self.client.close()


class SemanticScholarClient:
    """Client for Semantic Scholar API operations."""

    def __init__(self, api_key: Optional[str] = None):
        headers = {}
        if api_key:
            headers["x-api-key"] = api_key
        self.client = httpx.Client(
            timeout=TIMEOUT,
            headers=headers,
            follow_redirects=True
        )
        self.last_request_time = 0

    def _rateLimit(self):
        """Ensure rate limiting."""
        elapsed = time.time() - self.last_request_time
        if elapsed < 0.5:  # 100 requests per 5 minutes = ~0.5s between requests
            time.sleep(0.5 - elapsed)
        self.last_request_time = time.time()

    def getCitations(self, arxiv_id: str) -> dict:
        """Get citation data for an arXiv paper."""
        self._rateLimit()

        url = f"{SEMANTIC_SCHOLAR_API}/paper/arXiv:{arxiv_id}"
        params = {"fields": "citationCount,influentialCitationCount,title,authors"}

        try:
            response = self.client.get(url, params=params)
            if response.status_code == 404:
                return {}
            response.raise_for_status()
            return response.json()
        except Exception:
            return {}

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
        except Exception:
            return []

    def enrichWithCitations(self, papers: list[Paper]) -> list[Paper]:
        """Add citation data to a list of papers."""
        for paper in papers:
            if paper.id_arxiv:
                citation_data = self.getCitations(paper.id_arxiv)
                if citation_data:
                    paper.citation_count = citation_data.get("citationCount")
                    paper.influential_citation_count = citation_data.get("influentialCitationCount")
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
        except Exception:
            return []

    def close(self):
        self.client.close()


def formatPapers(papers: list[Paper], format_type: str = "json", query: str = "") -> str:
    """Format papers for output.

    Supported formats: json, brief, csv, markdown
    """
    if format_type == "json":
        return json.dumps([asdict(p) for p in papers], indent=2, ensure_ascii=False)

    elif format_type == "brief":
        lines = []
        for p in papers:
            citations = f" [{p.citation_count} citations]" if p.citation_count else ""
            lines.append(f"[{p.id_arxiv}] {p.title}{citations}")
            lines.append(f"  Authors: {', '.join(p.authors[:3])}{'...' if len(p.authors) > 3 else ''}")
            lines.append(f"  URL: {p.url_abstract}")
            lines.append("")
        return "\n".join(lines)

    elif format_type == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "id_arxiv", "title", "authors", "date_published",
            "citation_count", "categories", "url_abstract"
        ])
        for p in papers:
            writer.writerow([
                p.id_arxiv,
                p.title,
                "; ".join(p.authors),
                p.date_published or "",
                p.citation_count or "",
                "; ".join(p.categories),
                p.url_abstract
            ])
        return output.getvalue()

    elif format_type == "markdown":
        lines = []
        if query:
            lines.append(f"## Search Results: \"{query}\"\n")
        else:
            lines.append("## Papers\n")

        lines.append("| # | Title | Authors | Date | Citations |")
        lines.append("|---|-------|---------|------|-----------|")

        for i, p in enumerate(papers, 1):
            authors_short = ", ".join(p.authors[:2])
            if len(p.authors) > 2:
                authors_short += " et al."
            date_str = p.date_published[:10] if p.date_published else ""
            citations = str(p.citation_count) if p.citation_count else "-"
            title_link = f"[{p.title[:60]}{'...' if len(p.title) > 60 else ''}]({p.url_abstract})"
            lines.append(f"| {i} | {title_link} | {authors_short} | {date_str} | {citations} |")

        lines.append("")
        lines.append(f"---\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Results: {len(papers)}")
        return "\n".join(lines)

    else:
        return json.dumps([asdict(p) for p in papers], indent=2, ensure_ascii=False)


def formatReferences(references: list[dict], format_type: str = "json", source_id: str = "") -> str:
    """Format references for output.

    Supported formats: json, brief, csv, markdown
    """
    if format_type == "json":
        return json.dumps(references, indent=2, ensure_ascii=False)

    elif format_type == "brief":
        lines = []
        for ref in references:
            cited_paper = ref.get("citedPaper", {})
            title = cited_paper.get("title", "Unknown")
            year = cited_paper.get("year", "")
            authors = cited_paper.get("authors", [])
            author_names = ", ".join(a.get("name", "") for a in authors[:2])
            if len(authors) > 2:
                author_names += " et al."

            arxiv_id = ""
            external_ids = cited_paper.get("externalIds", {})
            if external_ids:
                arxiv_id = external_ids.get("ArXiv", "")

            id_str = f"[{arxiv_id}] " if arxiv_id else ""
            year_str = f" ({year})" if year else ""
            lines.append(f"{id_str}{title}{year_str}")
            if author_names:
                lines.append(f"  {author_names}")
            lines.append("")
        return "\n".join(lines)

    elif format_type == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["arxiv_id", "title", "authors", "year"])
        for ref in references:
            cited_paper = ref.get("citedPaper", {})
            external_ids = cited_paper.get("externalIds", {}) or {}
            arxiv_id = external_ids.get("ArXiv", "")
            title = cited_paper.get("title", "")
            year = cited_paper.get("year", "")
            authors = cited_paper.get("authors", [])
            author_names = "; ".join(a.get("name", "") for a in authors)
            writer.writerow([arxiv_id, title, author_names, year or ""])
        return output.getvalue()

    elif format_type == "markdown":
        lines = []
        if source_id:
            lines.append(f"## References from {source_id}\n")
        else:
            lines.append("## References\n")

        lines.append("| # | Title | Authors | Year | arXiv ID |")
        lines.append("|---|-------|---------|------|----------|")

        for i, ref in enumerate(references, 1):
            cited_paper = ref.get("citedPaper", {})
            title = cited_paper.get("title", "Unknown")
            if len(title) > 50:
                title = title[:50] + "..."
            year = cited_paper.get("year", "-")
            authors = cited_paper.get("authors", [])
            author_names = ", ".join(a.get("name", "") for a in authors[:2])
            if len(authors) > 2:
                author_names += " et al."

            external_ids = cited_paper.get("externalIds", {}) or {}
            arxiv_id = external_ids.get("ArXiv", "-")

            lines.append(f"| {i} | {title} | {author_names} | {year or '-'} | {arxiv_id} |")

        lines.append("")
        lines.append(f"---\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Total: {len(references)}")
        return "\n".join(lines)

    else:
        return json.dumps(references, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(
        description="arXiv Research - Connect: Knowledge Navigation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s search "transformer attention" --category cs.LG --limit 10
  %(prog)s search "LLM agents" --format csv > papers.csv
  %(prog)s search "deep learning" --format markdown > papers.md
  %(prog)s similar 2301.00001 --limit 5
  %(prog)s recent cs.AI --limit 20 --format markdown
  %(prog)s references 2301.00001 --format csv
  %(prog)s paper 2301.00001
  %(prog)s content 2301.00001
  %(prog)s by-author "Yann LeCun" --limit 10
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Common format choices
    format_choices = ["json", "brief", "csv", "markdown"]

    # Search command
    search_parser = subparsers.add_parser("search", help="Search for papers")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--category", "-c", help="Filter by category (e.g., cs.AI)")
    search_parser.add_argument("--author", "-a", help="Filter by author")
    search_parser.add_argument("--limit", "-l", type=int, default=10, help="Number of results")
    search_parser.add_argument("--sort", choices=["relevance", "date_desc", "date_asc", "citations"], default="relevance")
    search_parser.add_argument("--with-citations", action="store_true", help="Include citation counts")
    search_parser.add_argument("--format", "-f", choices=format_choices, default="brief")

    # Similar command
    similar_parser = subparsers.add_parser("similar", help="Find similar papers")
    similar_parser.add_argument("paper_id", help="arXiv paper ID")
    similar_parser.add_argument("--limit", "-l", type=int, default=10, help="Number of results")
    similar_parser.add_argument("--format", "-f", choices=format_choices, default="json")

    # Recent command
    recent_parser = subparsers.add_parser("recent", help="Get recent papers")
    recent_parser.add_argument("category", help="arXiv category (e.g., cs.AI)")
    recent_parser.add_argument("--limit", "-l", type=int, default=10, help="Number of results")
    recent_parser.add_argument("--with-citations", action="store_true", help="Include citation counts")
    recent_parser.add_argument("--format", "-f", choices=format_choices, default="brief")

    # References command
    refs_parser = subparsers.add_parser("references", help="Get paper references")
    refs_parser.add_argument("paper_id", help="arXiv paper ID")
    refs_parser.add_argument("--limit", "-l", type=int, default=50, help="Number of results")
    refs_parser.add_argument("--format", "-f", choices=format_choices, default="brief")

    # Paper command
    paper_parser = subparsers.add_parser("paper", help="Get paper details")
    paper_parser.add_argument("paper_id", help="arXiv paper ID or URL")
    paper_parser.add_argument("--with-citations", action="store_true", help="Include citation counts")

    # Content command
    content_parser = subparsers.add_parser("content", help="Get paper full text")
    content_parser.add_argument("paper_id", help="arXiv paper ID or URL")

    # By-author command
    author_parser = subparsers.add_parser("by-author", help="Search by author")
    author_parser.add_argument("author", help="Author name")
    author_parser.add_argument("--limit", "-l", type=int, default=10, help="Number of results")
    author_parser.add_argument("--with-citations", action="store_true", help="Include citation counts")
    author_parser.add_argument("--format", "-f", choices=format_choices, default="brief")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    arxiv = ArxivClient()
    semantic = SemanticScholarClient()

    try:
        if args.command == "search":
            papers = arxiv.search(
                query=args.query,
                category=args.category,
                author=args.author,
                sort_by=args.sort,
                limit=args.limit
            )
            if args.with_citations or args.sort == "citations":
                papers = semantic.enrichWithCitations(papers)
                if args.sort == "citations":
                    papers.sort(key=lambda p: p.citation_count or 0, reverse=True)
            print(formatPapers(papers, args.format, query=args.query))

        elif args.command == "similar":
            similar = semantic.getSimilar(args.paper_id, args.limit)
            if similar:
                # Convert similar papers to Paper objects for formatting
                papers = []
                for s in similar:
                    external_ids = s.get("externalIds", {}) or {}
                    arxiv_id = external_ids.get("ArXiv", "")
                    authors = [a.get("name", "") for a in s.get("authors", [])]
                    papers.append(Paper(
                        id_arxiv=arxiv_id,
                        title=s.get("title", "Unknown"),
                        abstract="",
                        authors=authors,
                        categories=[],
                        url_abstract=f"{ARXIV_BASE}/abs/{arxiv_id}" if arxiv_id else "",
                        url_pdf=f"{ARXIV_BASE}/pdf/{arxiv_id}.pdf" if arxiv_id else "",
                        date_published=str(s.get("year", "")) if s.get("year") else None,
                        citation_count=s.get("citationCount")
                    ))
                print(formatPapers(papers, args.format, query=f"similar to {args.paper_id}"))
            else:
                print(f"No similar papers found for {args.paper_id}")

        elif args.command == "recent":
            papers = arxiv.getRecent(args.category, args.limit)
            if args.with_citations:
                papers = semantic.enrichWithCitations(papers)
            print(formatPapers(papers, args.format, query=f"recent {args.category}"))

        elif args.command == "references":
            arxiv_id = extractPaperId(args.paper_id)
            if not arxiv_id:
                print(f"Error: Invalid arXiv ID: {args.paper_id}")
                sys.exit(1)
            refs = semantic.getReferences(arxiv_id, args.limit)
            if refs:
                print(formatReferences(refs, args.format, source_id=arxiv_id))
            else:
                print(f"No references found for {arxiv_id}")

        elif args.command == "paper":
            paper = arxiv.getPaper(args.paper_id)
            if paper:
                if args.with_citations:
                    semantic.enrichWithCitations([paper])
                print(json.dumps(asdict(paper), indent=2, ensure_ascii=False))
            else:
                print(f"Paper not found: {args.paper_id}")

        elif args.command == "content":
            content = arxiv.getContent(args.paper_id)
            print(content)

        elif args.command == "by-author":
            papers = arxiv.search(query="", author=args.author, limit=args.limit)
            if args.with_citations:
                papers = semantic.enrichWithCitations(papers)
            print(formatPapers(papers, args.format, query=f"author: {args.author}"))

    finally:
        arxiv.close()
        semantic.close()


if __name__ == "__main__":
    main()
