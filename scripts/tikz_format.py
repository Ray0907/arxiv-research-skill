"""tikz_format.py - Render extracted TikZ figures as tikz, json, latex or brief text."""

import json
from dataclasses import asdict
from datetime import datetime

from tikz_models import TikzFigure


def formatTikz(figures: list[TikzFigure]) -> str:
    """Format as pure TikZ code with comment separators."""
    if not figures:
        return "% No TikZ figures found"

    parts = []
    for fig in figures:
        header = f"% Figure {fig.figure_index}: {fig.tikz_type}"
        header += f" (from {fig.source_file})"
        if fig.caption:
            header += f"\n% Caption: {fig.caption}"
        if fig.label:
            header += f"\n% Label: {fig.label}"
        parts.append(f"{header}\n{fig.tikz_code}")

    return "\n\n".join(parts)


def formatJson(figures: list[TikzFigure]) -> str:
    """Format as structured JSON."""
    return json.dumps([asdict(f) for f in figures], indent=2, ensure_ascii=False)


def formatLatex(figures: list[TikzFigure]) -> str:
    """Format as complete compilable LaTeX document."""
    if not figures:
        return "% No TikZ figures found"

    # Collect all libraries used
    all_libraries = set()
    for fig in figures:
        all_libraries.update(fig.libraries_used)

    # Determine which packages are needed
    packages = ["\\usepackage{tikz}"]
    types_present = {fig.tikz_type for fig in figures}

    if "tikzcd" in types_present:
        packages.append("\\usepackage{tikz-cd}")
    if "circuitikz" in types_present:
        packages.append("\\usepackage{circuitikz}")
    if "pgfplot" in types_present:
        packages.append("\\usepackage{pgfplots}")
        packages.append("\\pgfplotsset{compat=1.18}")

    if all_libraries:
        packages.append(f"\\usetikzlibrary{{{', '.join(sorted(all_libraries))}}}")

    packages_str = "\n".join(packages)
    id_arxiv = figures[0].id_arxiv

    body_parts = []
    for fig in figures:
        section = f"% Figure {fig.figure_index}: {fig.tikz_type}"
        if fig.caption:
            section += f"\n% Caption: {fig.caption}"
        section += f"\n\\begin{{figure}}[htbp]\n\\centering\n{fig.tikz_code}"
        if fig.caption:
            section += f"\n\\caption{{{fig.caption}}}"
        if fig.label:
            section += f"\n\\label{{{fig.label}}}"
        section += "\n\\end{figure}"
        body_parts.append(section)

    body = "\n\n".join(body_parts)

    return f"""\\documentclass{{article}}
{packages_str}

\\title{{TikZ Figures from arXiv:{id_arxiv}}}
\\date{{Extracted {datetime.now().strftime('%Y-%m-%d')}}}

\\begin{{document}}
\\maketitle

{body}

\\end{{document}}"""


def formatBrief(figures: list[TikzFigure], id_arxiv: str = "") -> str:
    """Format as brief text summary."""
    if not figures:
        return f"No TikZ figures found{f' in {id_arxiv}' if id_arxiv else ''}."

    # Count by type
    type_counts = {}
    for fig in figures:
        type_counts[fig.tikz_type] = type_counts.get(fig.tikz_type, 0) + 1

    # Collect libraries
    all_libraries = set()
    for fig in figures:
        all_libraries.update(fig.libraries_used)

    # Collect source files
    source_files = sorted({fig.source_file for fig in figures})

    lines = []
    header = f"TikZ figures"
    if id_arxiv:
        header += f" in {id_arxiv}"
    lines.append(f"{header}: {len(figures)} found")
    lines.append("")

    lines.append("Types:")
    for tikz_type, count in sorted(type_counts.items()):
        lines.append(f"  {tikz_type}: {count}")
    lines.append("")

    if all_libraries:
        lines.append(f"Libraries: {', '.join(sorted(all_libraries))}")
        lines.append("")

    lines.append(f"Source files: {', '.join(source_files)}")
    lines.append("")

    for fig in figures:
        caption_str = f" - {fig.caption[:60]}..." if fig.caption and len(fig.caption) > 60 else (f" - {fig.caption}" if fig.caption else "")
        lines.append(f"  [{fig.figure_index}] {fig.tikz_type}{caption_str}")

    return "\n".join(lines)


def formatFigures(figures: list[TikzFigure], format_type: str, id_arxiv: str = "") -> str:
    """Format figures for output."""
    if format_type == "tikz":
        return formatTikz(figures)
    elif format_type == "json":
        return formatJson(figures)
    elif format_type == "latex":
        return formatLatex(figures)
    elif format_type == "brief":
        return formatBrief(figures, id_arxiv)
    else:
        return formatTikz(figures)
