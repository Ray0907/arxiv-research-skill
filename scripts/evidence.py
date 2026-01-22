#!/usr/bin/env python3
"""
evidence.py - Source Attribution for arXiv Research

Core capability: Create verifiable links to sources
Generates citations in various academic formats.
"""

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from xml.etree import ElementTree

try:
    import httpx
except ImportError:
    print("Error: httpx required. Install with: pip install httpx")
    sys.exit(1)

from utils import extractPaperId


ARXIV_EXPORT = "https://export.arxiv.org"
TIMEOUT = 30.0


@dataclass
class PaperMetadata:
    """Paper metadata for citation generation."""
    id_arxiv: str
    title: str
    authors: list[str]
    abstract: str
    categories: list[str]
    published: str
    updated: Optional[str]
    doi: Optional[str]
    journal_ref: Optional[str]


class ArxivMetadataClient:
    """Client for fetching arXiv metadata via API."""

    def __init__(self):
        self.client = httpx.Client(timeout=TIMEOUT, follow_redirects=True)
        self.last_request_time = 0

    def _rateLimit(self):
        """Ensure rate limiting (arXiv asks for 1 request per 3 seconds)."""
        elapsed = time.time() - self.last_request_time
        if elapsed < 3.0:
            time.sleep(3.0 - elapsed)
        self.last_request_time = time.time()

    def getMetadata(self, arxiv_id: str) -> Optional[PaperMetadata]:
        """Fetch paper metadata from arXiv API."""
        self._rateLimit()

        url = f"{ARXIV_EXPORT}/api/query?id_list={arxiv_id}"
        response = self.client.get(url)
        response.raise_for_status()

        return self._parseAtomFeed(response.text)

    def getMetadataBatch(self, arxiv_ids: list[str]) -> list[PaperMetadata]:
        """Fetch metadata for multiple papers."""
        self._rateLimit()

        id_list = ",".join(arxiv_ids)
        url = f"{ARXIV_EXPORT}/api/query?id_list={id_list}&max_results={len(arxiv_ids)}"
        response = self.client.get(url)
        response.raise_for_status()

        return self._parseAtomFeedMultiple(response.text)

    def _parseAtomFeed(self, xml_content: str) -> Optional[PaperMetadata]:
        """Parse arXiv Atom feed for a single paper."""
        papers = self._parseAtomFeedMultiple(xml_content)
        return papers[0] if papers else None

    def _parseAtomFeedMultiple(self, xml_content: str) -> list[PaperMetadata]:
        """Parse arXiv Atom feed for multiple papers."""
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
            # Extract ID
            id_elem = entry.find("atom:id", ns)
            if id_elem is None:
                continue

            id_text = id_elem.text or ""
            id_match = re.search(r"abs/(\d+\.\d+)", id_text)
            if not id_match:
                continue
            arxiv_id = id_match.group(1)

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

            # Extract dates
            published_elem = entry.find("atom:published", ns)
            published = published_elem.text if published_elem is not None else ""

            updated_elem = entry.find("atom:updated", ns)
            updated = updated_elem.text if updated_elem is not None else None

            # Extract DOI
            doi_elem = entry.find("arxiv:doi", ns)
            doi = doi_elem.text if doi_elem is not None else None

            # Extract journal reference
            journal_elem = entry.find("arxiv:journal_ref", ns)
            journal_ref = journal_elem.text if journal_elem is not None else None

            papers.append(PaperMetadata(
                id_arxiv=arxiv_id,
                title=title,
                authors=authors,
                abstract=abstract,
                categories=categories,
                published=published,
                updated=updated,
                doi=doi,
                journal_ref=journal_ref
            ))

        return papers

    def close(self):
        self.client.close()


def formatBibtex(paper: PaperMetadata) -> str:
    """Generate BibTeX citation."""
    # Create citation key: first author's last name + year + first word of title
    first_author = paper.authors[0] if paper.authors else "Unknown"
    last_name = first_author.split()[-1].lower()

    # Extract year from published date
    year = "2024"
    if paper.published:
        year_match = re.search(r"(\d{4})", paper.published)
        if year_match:
            year = year_match.group(1)

    # First significant word from title
    title_words = re.findall(r"\b[A-Za-z]{4,}\b", paper.title)
    first_word = title_words[0].lower() if title_words else "paper"

    cite_key = f"{last_name}{year}{first_word}"

    # Format authors for BibTeX
    authors_bibtex = " and ".join(paper.authors)

    bibtex = f"""@article{{{cite_key},
    title = {{{paper.title}}},
    author = {{{authors_bibtex}}},
    year = {{{year}}},
    eprint = {{{paper.id_arxiv}}},
    archivePrefix = {{arXiv}},
    primaryClass = {{{paper.categories[0] if paper.categories else 'cs.AI'}}}"""

    if paper.doi:
        bibtex += f",\n    doi = {{{paper.doi}}}"

    if paper.journal_ref:
        bibtex += f",\n    journal = {{{paper.journal_ref}}}"

    bibtex += "\n}"

    return bibtex


def formatAPA(paper: PaperMetadata) -> str:
    """Generate APA 7th edition citation."""
    # Format authors
    if len(paper.authors) == 1:
        authors_str = formatAuthorAPA(paper.authors[0])
    elif len(paper.authors) == 2:
        authors_str = f"{formatAuthorAPA(paper.authors[0])} & {formatAuthorAPA(paper.authors[1])}"
    elif len(paper.authors) <= 20:
        authors_str = ", ".join(formatAuthorAPA(a) for a in paper.authors[:-1])
        authors_str += f", & {formatAuthorAPA(paper.authors[-1])}"
    else:
        # More than 20 authors: first 19, ..., last
        authors_str = ", ".join(formatAuthorAPA(a) for a in paper.authors[:19])
        authors_str += f", ... {formatAuthorAPA(paper.authors[-1])}"

    # Extract year
    year = "n.d."
    if paper.published:
        year_match = re.search(r"(\d{4})", paper.published)
        if year_match:
            year = year_match.group(1)

    return f"{authors_str} ({year}). {paper.title}. arXiv preprint arXiv:{paper.id_arxiv}."


def formatAuthorAPA(name: str) -> str:
    """Format a single author name for APA style."""
    parts = name.split()
    if len(parts) >= 2:
        last_name = parts[-1]
        initials = ". ".join(p[0] + "." for p in parts[:-1])
        return f"{last_name}, {initials}"
    return name


def formatIEEE(paper: PaperMetadata) -> str:
    """Generate IEEE citation."""
    # Format authors
    if len(paper.authors) <= 3:
        authors_str = ", ".join(formatAuthorIEEE(a) for a in paper.authors)
    else:
        authors_str = f"{formatAuthorIEEE(paper.authors[0])} et al."

    # Extract year
    year = ""
    if paper.published:
        year_match = re.search(r"(\d{4})", paper.published)
        if year_match:
            year = year_match.group(1)

    return f'{authors_str}, "{paper.title}," arXiv preprint arXiv:{paper.id_arxiv}, {year}.'


def formatAuthorIEEE(name: str) -> str:
    """Format a single author name for IEEE style."""
    parts = name.split()
    if len(parts) >= 2:
        last_name = parts[-1]
        initials = " ".join(p[0] + "." for p in parts[:-1])
        return f"{initials} {last_name}"
    return name


def formatACM(paper: PaperMetadata) -> str:
    """Generate ACM citation."""
    # Format authors
    if len(paper.authors) == 1:
        authors_str = paper.authors[0]
    elif len(paper.authors) == 2:
        authors_str = f"{paper.authors[0]} and {paper.authors[1]}"
    else:
        authors_str = f"{paper.authors[0]} et al."

    # Extract year
    year = ""
    if paper.published:
        year_match = re.search(r"(\d{4})", paper.published)
        if year_match:
            year = year_match.group(1)

    return f"{authors_str}. {year}. {paper.title}. arXiv preprint arXiv:{paper.id_arxiv}."


def formatChicago(paper: PaperMetadata) -> str:
    """Generate Chicago citation."""
    # Format authors
    if len(paper.authors) == 1:
        authors_str = formatAuthorChicago(paper.authors[0], first=True)
    elif len(paper.authors) == 2:
        authors_str = f"{formatAuthorChicago(paper.authors[0], first=True)} and {formatAuthorChicago(paper.authors[1], first=False)}"
    elif len(paper.authors) <= 10:
        authors_str = formatAuthorChicago(paper.authors[0], first=True)
        for author in paper.authors[1:-1]:
            authors_str += f", {formatAuthorChicago(author, first=False)}"
        authors_str += f", and {formatAuthorChicago(paper.authors[-1], first=False)}"
    else:
        authors_str = f"{formatAuthorChicago(paper.authors[0], first=True)} et al."

    # Extract year
    year = ""
    if paper.published:
        year_match = re.search(r"(\d{4})", paper.published)
        if year_match:
            year = year_match.group(1)

    return f'{authors_str}. "{paper.title}." arXiv preprint arXiv:{paper.id_arxiv} ({year}).'


def formatAuthorChicago(name: str, first: bool = True) -> str:
    """Format a single author name for Chicago style."""
    parts = name.split()
    if len(parts) >= 2:
        last_name = parts[-1]
        first_names = " ".join(parts[:-1])
        if first:
            return f"{last_name}, {first_names}"
        else:
            return f"{first_names} {last_name}"
    return name


def formatRIS(paper: PaperMetadata) -> str:
    """Generate RIS citation (for Zotero, Mendeley, EndNote)."""
    lines = []
    lines.append("TY  - JOUR")

    # Authors (one AU line per author)
    for author in paper.authors:
        lines.append(f"AU  - {author}")

    # Title
    lines.append(f"TI  - {paper.title}")

    # Year
    if paper.published:
        year_match = re.search(r"(\d{4})", paper.published)
        if year_match:
            lines.append(f"PY  - {year_match.group(1)}")

    # Abstract
    if paper.abstract:
        lines.append(f"AB  - {paper.abstract}")

    # URLs
    lines.append(f"UR  - https://arxiv.org/abs/{paper.id_arxiv}")

    # DOI
    if paper.doi:
        lines.append(f"DO  - {paper.doi}")

    # Journal reference
    if paper.journal_ref:
        lines.append(f"JO  - {paper.journal_ref}")
    else:
        lines.append(f"JO  - arXiv preprint arXiv:{paper.id_arxiv}")

    # Categories as keywords
    for cat in paper.categories:
        lines.append(f"KW  - {cat}")

    # End of record
    lines.append("ER  - ")

    return "\n".join(lines)


def formatCitation(paper: PaperMetadata, format_type: str) -> str:
    """Format citation in the specified style."""
    formatters = {
        "bibtex": formatBibtex,
        "apa": formatAPA,
        "ieee": formatIEEE,
        "acm": formatACM,
        "chicago": formatChicago,
        "ris": formatRIS
    }

    formatter = formatters.get(format_type.lower())
    if not formatter:
        raise ValueError(f"Unknown format: {format_type}")

    return formatter(paper)


def main():
    parser = argparse.ArgumentParser(
        description="arXiv Research - Evidence: Source Attribution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s bibtex 2301.00001
  %(prog)s apa 2301.00001
  %(prog)s ris 2301.00001
  %(prog)s batch 2301.00001,2302.00002 --format ris > refs.ris
  %(prog)s all 2301.00001
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Individual format commands
    for fmt in ["bibtex", "apa", "ieee", "acm", "chicago", "ris"]:
        fmt_parser = subparsers.add_parser(fmt, help=f"Generate {fmt.upper()} citation")
        fmt_parser.add_argument("paper_id", help="arXiv paper ID or URL")

    # Batch command
    batch_parser = subparsers.add_parser("batch", help="Generate citations for multiple papers")
    batch_parser.add_argument("paper_ids", help="Comma-separated arXiv paper IDs")
    batch_parser.add_argument("--format", "-f", choices=["bibtex", "apa", "ieee", "acm", "chicago", "ris"],
                             default="bibtex", help="Citation format")

    # All formats command
    all_parser = subparsers.add_parser("all", help="Generate all citation formats")
    all_parser.add_argument("paper_id", help="arXiv paper ID or URL")

    # Metadata command
    meta_parser = subparsers.add_parser("metadata", help="Get raw paper metadata")
    meta_parser.add_argument("paper_id", help="arXiv paper ID or URL")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    client = ArxivMetadataClient()

    try:
        if args.command in ["bibtex", "apa", "ieee", "acm", "chicago", "ris"]:
            arxiv_id = extractPaperId(args.paper_id)
            if not arxiv_id:
                print(f"Error: Could not parse arXiv ID from: {args.paper_id}")
                sys.exit(1)

            paper = client.getMetadata(arxiv_id)
            if not paper:
                print(f"Error: Paper not found: {arxiv_id}")
                sys.exit(1)

            print(formatCitation(paper, args.command))

        elif args.command == "batch":
            ids = [extractPaperId(id.strip()) for id in args.paper_ids.split(",")]
            ids = [id for id in ids if id]

            if not ids:
                print("Error: No valid arXiv IDs provided")
                sys.exit(1)

            papers = client.getMetadataBatch(ids)

            for paper in papers:
                print(formatCitation(paper, args.format))
                print()

        elif args.command == "all":
            arxiv_id = extractPaperId(args.paper_id)
            if not arxiv_id:
                print(f"Error: Could not parse arXiv ID from: {args.paper_id}")
                sys.exit(1)

            paper = client.getMetadata(arxiv_id)
            if not paper:
                print(f"Error: Paper not found: {arxiv_id}")
                sys.exit(1)

            for fmt in ["bibtex", "apa", "ieee", "acm", "chicago", "ris"]:
                print(f"--- {fmt.upper()} ---")
                print(formatCitation(paper, fmt))
                print()

        elif args.command == "metadata":
            arxiv_id = extractPaperId(args.paper_id)
            if not arxiv_id:
                print(f"Error: Could not parse arXiv ID from: {args.paper_id}")
                sys.exit(1)

            paper = client.getMetadata(arxiv_id)
            if not paper:
                print(f"Error: Paper not found: {arxiv_id}")
                sys.exit(1)

            from dataclasses import asdict
            print(json.dumps(asdict(paper), indent=2, ensure_ascii=False))

    finally:
        client.close()


if __name__ == "__main__":
    main()
