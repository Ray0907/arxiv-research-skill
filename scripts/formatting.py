"""Output formatters for papers, references, citations and coauthors."""

import csv
import io
import json
from dataclasses import asdict
from datetime import datetime

from models import Paper


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


def formatCitations(citations: list[dict], format_type: str = "json", source_id: str = "") -> str:
    """Format citations (papers that cite this paper) for output.

    Supported formats: json, brief, csv, markdown
    """
    if format_type == "json":
        return json.dumps(citations, indent=2, ensure_ascii=False)

    elif format_type == "brief":
        lines = []
        for cit in citations:
            citing_paper = cit.get("citingPaper", {})
            title = citing_paper.get("title", "Unknown")
            year = citing_paper.get("year", "")
            citation_count = citing_paper.get("citationCount", 0)
            authors = citing_paper.get("authors", [])
            author_names = ", ".join(a.get("name", "") for a in authors[:2])
            if len(authors) > 2:
                author_names += " et al."

            arxiv_id = ""
            external_ids = citing_paper.get("externalIds", {})
            if external_ids:
                arxiv_id = external_ids.get("ArXiv", "")

            id_str = f"[{arxiv_id}] " if arxiv_id else ""
            year_str = f" ({year})" if year else ""
            cite_str = f" [{citation_count} citations]" if citation_count else ""
            lines.append(f"{id_str}{title}{year_str}{cite_str}")
            if author_names:
                lines.append(f"  {author_names}")
            lines.append("")
        return "\n".join(lines)

    elif format_type == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["arxiv_id", "title", "authors", "year", "citation_count"])
        for cit in citations:
            citing_paper = cit.get("citingPaper", {})
            external_ids = citing_paper.get("externalIds", {}) or {}
            arxiv_id = external_ids.get("ArXiv", "")
            title = citing_paper.get("title", "")
            year = citing_paper.get("year", "")
            citation_count = citing_paper.get("citationCount", "")
            authors = citing_paper.get("authors", [])
            author_names = "; ".join(a.get("name", "") for a in authors)
            writer.writerow([arxiv_id, title, author_names, year or "", citation_count])
        return output.getvalue()

    elif format_type == "markdown":
        lines = []
        if source_id:
            lines.append(f"## Papers citing {source_id}\n")
        else:
            lines.append("## Citing Papers\n")

        lines.append("| # | Title | Authors | Year | Citations | arXiv ID |")
        lines.append("|---|-------|---------|------|-----------|----------|")

        for i, cit in enumerate(citations, 1):
            citing_paper = cit.get("citingPaper", {})
            title = citing_paper.get("title", "Unknown")
            if len(title) > 50:
                title = title[:50] + "..."
            year = citing_paper.get("year", "-")
            citation_count = citing_paper.get("citationCount", "-")
            authors = citing_paper.get("authors", [])
            author_names = ", ".join(a.get("name", "") for a in authors[:2])
            if len(authors) > 2:
                author_names += " et al."

            external_ids = citing_paper.get("externalIds", {}) or {}
            arxiv_id = external_ids.get("ArXiv", "-")

            lines.append(f"| {i} | {title} | {author_names} | {year or '-'} | {citation_count} | {arxiv_id} |")

        lines.append("")
        lines.append(f"---\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Total: {len(citations)}")
        return "\n".join(lines)

    else:
        return json.dumps(citations, indent=2, ensure_ascii=False)


def formatCoauthors(data: dict, format_type: str = "brief", limit: int = 20) -> str:
    """Format coauthors data for output.

    Supported formats: json, brief, markdown
    """
    if "error" in data:
        return f"Error: {data['error']}"

    if format_type == "json":
        return json.dumps(data, indent=2, ensure_ascii=False)

    elif format_type == "brief":
        lines = []
        lines.append(f"Author: {data['author_name']}")
        lines.append(f"Total papers analyzed: {data['total_papers']}")
        lines.append(f"\nTop coauthors:")
        lines.append("-" * 40)

        for i, coauthor in enumerate(data["coauthors"][:limit], 1):
            lines.append(f"{i:2}. {coauthor['name']} ({coauthor['count']} papers)")

        return "\n".join(lines)

    elif format_type == "markdown":
        lines = []
        lines.append(f"## Coauthors of {data['author_name']}\n")
        lines.append(f"Based on {data['total_papers']} papers\n")
        lines.append("| # | Coauthor | Papers Together |")
        lines.append("|---|----------|-----------------|")

        for i, coauthor in enumerate(data["coauthors"][:limit], 1):
            lines.append(f"| {i} | {coauthor['name']} | {coauthor['count']} |")

        lines.append("")
        lines.append(f"---\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        return "\n".join(lines)

    else:
        return json.dumps(data, indent=2, ensure_ascii=False)
