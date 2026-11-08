#!/usr/bin/env python3
"""
connect.py - Knowledge Navigation for arXiv Research

Core capability: Find relevant existing knowledge
Integrates arXiv search with Semantic Scholar for citation data.
"""

import argparse
import json
import sys
import time
import urllib.parse
from dataclasses import asdict
from typing import Optional
from xml.etree import ElementTree

try:
    import httpx
except ImportError:
    print("Error: httpx required. Install with: pip install httpx")
    sys.exit(1)

from formatting import formatPapers, formatReferences, formatCitations, formatCoauthors
from scholar import SemanticScholarClient
from utils import extractPaperId, ARXIV_BASE, ARXIV_EXPORT, ARXIV_RATE_LIMIT_DELAY, ARXIV_USER_AGENT, TIMEOUT
from cache import PaperCache, CachedPaper
from models import Paper
from query import buildSearchQuery


# Configuration
JINA_READER = "https://r.jina.ai"


class ArxivClient:
    """Client for arXiv operations."""

    def __init__(self, cache: Optional[PaperCache] = None):
        self.client = httpx.Client(
            timeout=TIMEOUT,
            headers={"User-Agent": ARXIV_USER_AGENT},
            follow_redirects=True,
        )
        self.last_request_time = 0
        self.cache = cache

    def _rateLimit(self):
        """Ensure rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < ARXIV_RATE_LIMIT_DELAY:
            time.sleep(ARXIV_RATE_LIMIT_DELAY - elapsed)
        self.last_request_time = time.time()

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        author: Optional[str] = None,
        sort_by: str = "relevance",
        limit: int = 25,
        page: int = 1,
        since: Optional[str] = None,
        until: Optional[str] = None
    ) -> list[Paper]:
        """Search arXiv for papers using the API.

        Args:
            since: Start date in YYYY-MM or YYYY-MM-DD format
            until: End date in YYYY-MM or YYYY-MM-DD format
        """
        self._rateLimit()

        max_results = min(limit, 100)
        start = (page - 1) * max_results

        full_query = buildSearchQuery(query, category, author, since, until)

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

    @staticmethod
    def _parseApiResults(xml_content: str) -> list[Paper]:
        """Parse arXiv API Atom feed results."""
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

                id_arxiv = extractPaperId(id_elem.text or "")
                if not id_arxiv:
                    continue

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
        """Get detailed information about a specific paper. Metadata never expires, so
        cache hits skip the network entirely."""
        id_arxiv = extractPaperId(id_or_url)
        if not id_arxiv:
            return None

        if self.cache:
            cached = self.cache.getPaper(id_arxiv)
            if cached:
                return Paper(
                    id_arxiv=cached.id_arxiv,
                    title=cached.title,
                    abstract=cached.abstract,
                    authors=cached.authors,
                    categories=cached.categories,
                    url_abstract=cached.url_abstract,
                    url_pdf=cached.url_pdf,
                    date_published=cached.date_published,
                )

        self._rateLimit()

        url = f"{ARXIV_EXPORT}/api/query?id_list={id_arxiv}"
        response = self.client.get(url)
        response.raise_for_status()

        papers = self._parseApiResults(response.text)
        if not papers:
            return None
        paper = papers[0]

        if self.cache:
            self.cache.savePaper(CachedPaper(
                id_arxiv=paper.id_arxiv,
                title=paper.title,
                abstract=paper.abstract,
                authors=paper.authors,
                categories=paper.categories,
                url_abstract=paper.url_abstract,
                url_pdf=paper.url_pdf,
                date_published=paper.date_published,
            ))

        return paper

    def getRecent(self, category: str = "cs.AI", count: int = 10) -> list[Paper]:
        """Get recent papers from a category."""
        return self.search("", category=category, sort_by="date_desc", limit=min(count, 50))

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


def main():
    parser = argparse.ArgumentParser(
        description="arXiv Research - Connect: Knowledge Navigation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s search "transformer attention" --category cs.LG --limit 10
  %(prog)s search "LLM agents" --since 2023-01 --until 2024-06
  %(prog)s search "deep learning" --format markdown > papers.md
  %(prog)s similar 2301.00001 --limit 5
  %(prog)s recent cs.AI --limit 20 --format markdown
  %(prog)s references 2301.00001 --format csv
  %(prog)s cited-by 2301.00001 --format markdown
  %(prog)s coauthors "Yann LeCun" --limit 20
  %(prog)s paper 2301.00001
  %(prog)s content 2301.00001,2302.00002,2303.00003
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
    search_parser.add_argument("--since", help="Start date (YYYY-MM or YYYY-MM-DD)")
    search_parser.add_argument("--until", help="End date (YYYY-MM or YYYY-MM-DD)")
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

    # Cited-by command
    cited_parser = subparsers.add_parser("cited-by", help="Get papers that cite this paper")
    cited_parser.add_argument("paper_id", help="arXiv paper ID")
    cited_parser.add_argument("--limit", "-l", type=int, default=50, help="Number of results")
    cited_parser.add_argument("--format", "-f", choices=format_choices, default="brief")

    # Paper command
    paper_parser = subparsers.add_parser("paper", help="Get paper details")
    paper_parser.add_argument("paper_id", help="arXiv paper ID or URL")
    paper_parser.add_argument("--with-citations", action="store_true", help="Include citation counts")

    # Content command
    content_parser = subparsers.add_parser("content", help="Get paper full text")
    content_parser.add_argument("paper_ids", help="arXiv paper ID(s), comma-separated for batch")
    content_parser.add_argument("--separator", default="\n\n---\n\n", help="Separator between papers in batch mode")

    # By-author command
    author_parser = subparsers.add_parser("by-author", help="Search by author")
    author_parser.add_argument("author", help="Author name")
    author_parser.add_argument("--limit", "-l", type=int, default=10, help="Number of results")
    author_parser.add_argument("--with-citations", action="store_true", help="Include citation counts")
    author_parser.add_argument("--format", "-f", choices=format_choices, default="brief")

    # Coauthors command
    coauthor_parser = subparsers.add_parser("coauthors", help="Find coauthors of an author")
    coauthor_parser.add_argument("author", help="Author name")
    coauthor_parser.add_argument("--limit", "-l", type=int, default=20, help="Number of coauthors to show")
    coauthor_parser.add_argument("--format", "-f", choices=["json", "brief", "markdown"], default="brief")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    cache = PaperCache()
    arxiv = ArxivClient(cache=cache)
    semantic = SemanticScholarClient(cache=cache)

    try:
        if args.command == "search":
            papers = arxiv.search(
                query=args.query,
                category=args.category,
                author=args.author,
                sort_by=args.sort,
                limit=args.limit,
                since=args.since,
                until=args.until
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

        elif args.command == "cited-by":
            arxiv_id = extractPaperId(args.paper_id)
            if not arxiv_id:
                print(f"Error: Invalid arXiv ID: {args.paper_id}")
                sys.exit(1)
            citations = semantic.getCitedBy(arxiv_id, args.limit)
            if citations:
                print(formatCitations(citations, args.format, source_id=arxiv_id))
            else:
                print(f"No citing papers found for {arxiv_id}")

        elif args.command == "paper":
            paper = arxiv.getPaper(args.paper_id)
            if paper:
                if args.with_citations:
                    semantic.enrichWithCitations([paper])
                print(json.dumps(asdict(paper), indent=2, ensure_ascii=False))
            else:
                print(f"Paper not found: {args.paper_id}")

        elif args.command == "content":
            paper_ids = [p.strip() for p in args.paper_ids.split(",")]
            contents = []
            for paper_id in paper_ids:
                arxiv_id = extractPaperId(paper_id)
                if not arxiv_id:
                    print(f"Warning: Invalid arXiv ID: {paper_id}", file=sys.stderr)
                    continue
                content = arxiv.getContent(arxiv_id)
                if len(paper_ids) > 1:
                    contents.append(f"# Paper: {arxiv_id}\n\n{content}")
                else:
                    contents.append(content)
            print(args.separator.join(contents))

        elif args.command == "by-author":
            papers = arxiv.search(query="", author=args.author, limit=args.limit)
            if args.with_citations:
                papers = semantic.enrichWithCitations(papers)
            print(formatPapers(papers, args.format, query=f"author: {args.author}"))

        elif args.command == "coauthors":
            data = semantic.getCoauthors(args.author, limit=100)
            print(formatCoauthors(data, args.format, limit=args.limit))

    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        arxiv.close()
        semantic.close()


if __name__ == "__main__":
    main()
