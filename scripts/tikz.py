#!/usr/bin/env python3
"""
tikz.py - TikZ Extraction from arXiv Papers

Connect extension: extracts TikZ source code from arXiv LaTeX sources.
Downloads e-print archives, parses .tex files, and returns structured TikZ figures.
"""

import argparse
import gzip
import json
import os
import re
import shutil
import sys
import tarfile
import tempfile
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import httpx
except ImportError:
    print("Error: httpx required. Install with: pip install httpx")
    sys.exit(1)

from utils import extractPaperId


# Configuration
ARXIV_BASE = "https://arxiv.org"
TIMEOUT = 60.0
RATE_LIMIT_DELAY = 3.0  # arXiv asks for 1 request per 3 seconds

# TikZ environments to extract
TIKZ_ENVIRONMENTS = ["tikzpicture", "tikzcd", "circuitikz", "axis"]

# Map environment names to human-readable types
TIKZ_TYPE_MAP = {
    "tikzpicture": "tikzpicture",
    "tikzcd": "tikzcd",
    "circuitikz": "circuitikz",
    "axis": "pgfplot",
}


@dataclass
class TikzFigure:
    """Represents a single TikZ figure extracted from a paper."""
    id_arxiv: str
    figure_index: int
    tikz_type: str
    tikz_code: str
    source_file: str
    libraries_used: list[str]
    caption: Optional[str] = None
    label: Optional[str] = None


class TikzClient:
    """Client for extracting TikZ figures from arXiv papers."""

    def __init__(self):
        self.client = httpx.Client(timeout=TIMEOUT, follow_redirects=True)
        self.last_request_time = 0

    def _rateLimit(self):
        """Ensure rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        self.last_request_time = time.time()

    def extractFigures(self, arxiv_id: str) -> list[TikzFigure]:
        """Extract all TikZ figures from a paper's LaTeX source.

        Downloads the e-print archive, extracts .tex files, and parses
        TikZ environments with a counting parser for correct nesting.
        """
        content = self._downloadSource(arxiv_id)
        if content is None:
            return []

        return self._processArchive(arxiv_id, content)

    def _downloadSource(self, arxiv_id: str) -> Optional[bytes]:
        """Download e-print source from arXiv.

        Returns raw bytes or None if source unavailable (PDF-only paper).
        """
        self._rateLimit()

        url = f"{ARXIV_BASE}/e-print/{arxiv_id}"
        try:
            response = self.client.get(url)
            if response.status_code == 403:
                return None
            response.raise_for_status()
            return response.content
        except httpx.HTTPStatusError:
            return None
        except httpx.HTTPError:
            return None

    def _processArchive(self, arxiv_id: str, content: bytes) -> list[TikzFigure]:
        """Process downloaded archive content and extract TikZ figures.

        Tries tar.gz first, falls back to single-file gzip.
        """
        tmp_dir = tempfile.mkdtemp(prefix="arxiv_tikz_")
        try:
            tex_files = self._extractArchive(content, tmp_dir)
            if not tex_files:
                return []

            # Pass 1: collect all \usetikzlibrary{} across all files
            libraries_used = self._collectLibraries(tex_files)

            # Pass 2: extract TikZ environments from each file
            figures = []
            figure_index = 0
            for tex_path in tex_files:
                tex_content = self._readTexFile(tex_path)
                if not tex_content:
                    continue

                source_name = os.path.relpath(tex_path, tmp_dir)
                extracted = self._extractTikzFromContent(
                    tex_content, arxiv_id, source_name, libraries_used, figure_index
                )
                figures.extend(extracted)
                figure_index += len(extracted)

            return figures
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def _extractArchive(self, content: bytes, tmp_dir: str) -> list[str]:
        """Extract archive to tmp_dir and return list of .tex file paths.

        Tries tar.gz first, then single-file gzip.
        """
        # Try tar.gz
        try:
            import io
            with tarfile.open(fileobj=io.BytesIO(content), mode="r:gz") as tar:
                tar.extractall(tmp_dir, filter="data")
            return self._findTexFiles(tmp_dir)
        except (tarfile.TarError, gzip.BadGzipFile, EOFError):
            pass

        # Try plain tar (some e-prints are uncompressed tar)
        try:
            import io
            with tarfile.open(fileobj=io.BytesIO(content), mode="r:") as tar:
                tar.extractall(tmp_dir, filter="data")
            return self._findTexFiles(tmp_dir)
        except (tarfile.TarError, EOFError):
            pass

        # Try single-file gzip
        try:
            decompressed = gzip.decompress(content)
            tex_path = os.path.join(tmp_dir, "main.tex")
            with open(tex_path, "wb") as f:
                f.write(decompressed)
            return [tex_path]
        except (gzip.BadGzipFile, EOFError):
            pass

        # Try raw .tex (some papers are just plain LaTeX)
        try:
            text = content.decode("utf-8", errors="ignore")
            if "\\begin{document}" in text or "\\documentclass" in text:
                tex_path = os.path.join(tmp_dir, "main.tex")
                with open(tex_path, "w", encoding="utf-8") as f:
                    f.write(text)
                return [tex_path]
        except Exception:
            pass

        return []

    def _findTexFiles(self, directory: str) -> list[str]:
        """Recursively find all .tex files in directory."""
        tex_files = []
        for root, _dirs, files in os.walk(directory):
            for name in sorted(files):
                if name.endswith(".tex"):
                    tex_files.append(os.path.join(root, name))
        return tex_files

    def _readTexFile(self, path: str) -> Optional[str]:
        """Read a .tex file, trying common encodings."""
        for encoding in ["utf-8", "latin-1"]:
            try:
                with open(path, "r", encoding=encoding) as f:
                    return f.read()
            except (UnicodeDecodeError, OSError):
                continue
        return None

    def _collectLibraries(self, tex_files: list[str]) -> list[str]:
        """Collect all \\usetikzlibrary{} declarations across all .tex files."""
        libraries = set()
        pattern = re.compile(r"\\usetikzlibrary\{([^}]+)\}")

        for path in tex_files:
            content = self._readTexFile(path)
            if not content:
                continue
            for match in pattern.finditer(content):
                for lib in match.group(1).split(","):
                    lib = lib.strip()
                    if lib:
                        libraries.add(lib)

        return sorted(libraries)

    def _extractTikzFromContent(
        self,
        content: str,
        id_arxiv: str,
        source_file: str,
        libraries_used: list[str],
        start_index: int,
    ) -> list[TikzFigure]:
        """Extract TikZ environments from a single .tex file content.

        Uses a counting parser to handle nested \\begin/\\end correctly.
        """
        figures = []
        figure_index = start_index

        for env_name in TIKZ_ENVIRONMENTS:
            begin_tag = f"\\begin{{{env_name}}}"
            pos = 0

            while True:
                start = content.find(begin_tag, pos)
                if start == -1:
                    break

                # Use counting parser for balanced begin/end
                tikz_code = self._extractBalancedEnvironment(content, start, env_name)
                if tikz_code is None:
                    pos = start + len(begin_tag)
                    continue

                # Skip if this is nested inside an already-matched tikzpicture
                # (e.g. \begin{axis} inside \begin{tikzpicture})
                if env_name == "axis" and self._isNestedInTikzpicture(content, start):
                    pos = start + len(tikz_code)
                    continue

                # Extract caption and label from surrounding figure environment
                caption = self._extractCaption(content, start)
                label = self._extractLabel(content, start)

                figures.append(TikzFigure(
                    id_arxiv=id_arxiv,
                    figure_index=figure_index,
                    tikz_type=TIKZ_TYPE_MAP.get(env_name, env_name),
                    tikz_code=tikz_code,
                    source_file=source_file,
                    libraries_used=libraries_used,
                    caption=caption,
                    label=label,
                ))
                figure_index += 1
                pos = start + len(tikz_code)

        return figures

    def _extractBalancedEnvironment(
        self, content: str, start: int, env_name: str
    ) -> Optional[str]:
        """Extract a balanced \\begin{env}...\\end{env} block using depth counting.

        Handles nested environments of the same type correctly.
        """
        begin_tag = f"\\begin{{{env_name}}}"
        end_tag = f"\\end{{{env_name}}}"
        depth = 0
        pos = start

        while pos < len(content):
            next_begin = content.find(begin_tag, pos if depth > 0 else pos + 1)
            next_end = content.find(end_tag, pos)

            if next_end == -1:
                # Unbalanced: no closing tag found
                return None

            if next_begin != -1 and next_begin < next_end:
                # Found a nested begin before the next end
                depth += 1
                pos = next_begin + len(begin_tag)
            else:
                # Found an end tag
                if depth == 0:
                    end_pos = next_end + len(end_tag)
                    return content[start:end_pos]
                else:
                    depth -= 1
                    pos = next_end + len(end_tag)

        return None

    def _isNestedInTikzpicture(self, content: str, pos: int) -> bool:
        """Check if position is inside a \\begin{tikzpicture} block."""
        # Look backwards for the nearest tikzpicture begin/end
        before = content[:pos]
        last_begin = before.rfind("\\begin{tikzpicture}")
        last_end = before.rfind("\\end{tikzpicture}")

        if last_begin == -1:
            return False

        # If the last tikzpicture begin is after the last tikzpicture end,
        # we are inside a tikzpicture
        return last_begin > last_end

    def _extractCaption(self, content: str, tikz_start: int) -> Optional[str]:
        """Extract \\caption{} from surrounding \\begin{figure} environment."""
        # Look backwards for \begin{figure}
        search_start = max(0, tikz_start - 500)
        before = content[search_start:tikz_start]

        fig_begin = before.rfind("\\begin{figure}")
        if fig_begin == -1:
            return None

        # Find the end of this figure environment
        fig_abs_start = search_start + fig_begin
        fig_end = content.find("\\end{figure}", tikz_start)
        if fig_end == -1:
            return None

        figure_block = content[fig_abs_start:fig_end + len("\\end{figure}")]

        # Extract caption using balanced braces
        caption_match = re.search(r"\\caption\{", figure_block)
        if not caption_match:
            return None

        caption_start = caption_match.end()
        depth = 1
        i = caption_start
        while i < len(figure_block) and depth > 0:
            if figure_block[i] == "{":
                depth += 1
            elif figure_block[i] == "}":
                depth -= 1
            i += 1

        if depth == 0:
            caption_text = figure_block[caption_start:i - 1]
            # Clean up the caption text
            caption_text = re.sub(r"\\label\{[^}]*\}", "", caption_text)
            caption_text = " ".join(caption_text.split()).strip()
            return caption_text if caption_text else None

        return None

    def _extractLabel(self, content: str, tikz_start: int) -> Optional[str]:
        """Extract \\label{} from surrounding \\begin{figure} environment."""
        search_start = max(0, tikz_start - 500)
        before = content[search_start:tikz_start]

        fig_begin = before.rfind("\\begin{figure}")
        if fig_begin == -1:
            return None

        fig_abs_start = search_start + fig_begin
        fig_end = content.find("\\end{figure}", tikz_start)
        if fig_end == -1:
            return None

        figure_block = content[fig_abs_start:fig_end + len("\\end{figure}")]

        label_match = re.search(r"\\label\{([^}]+)\}", figure_block)
        if label_match:
            return label_match.group(1)

        return None

    def close(self):
        """Close the HTTP client."""
        self.client.close()


# --- Output Formatting ---

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


# --- Analysis Prompts ---

TIKZ_PROMPTS = {
    "quick": """Analyze these TikZ figures and provide a structured summary:

## Overview
How many figures? What types (diagrams, plots, flowcharts, etc.)?

## Figure Descriptions
For each figure:
- What it depicts
- Key visual structure (nodes, edges, layers, axes, etc.)
- Purpose in the paper context

## Complexity
- Simple (few nodes/elements) / Medium / Complex (many layers, custom styles)
- Estimated effort to reproduce or modify

## Reusability
Which figures (or parts) could be adapted for other papers?
""",

    "technical": """Provide a technical analysis of these TikZ figures:

## Package Dependencies
- TikZ libraries used and why
- Additional packages required (pgfplots, tikz-cd, circuitikz, etc.)

## Styling Analysis
For each figure:
- Node styles and custom definitions
- Color schemes
- Line styles and decorations
- Coordinate systems used

## Layout Methods
- Manual positioning vs. automatic layout
- Use of relative coordinates, calc library, etc.
- Anchoring and alignment strategies

## Reproducibility Notes
- Are all styles self-contained or do they depend on external definitions?
- Missing preamble definitions that would be needed
- Potential compilation issues
""",

    "compare": """Compare these TikZ figures:

| Aspect | Figure 1 | Figure 2 | Figure 3 |
|--------|----------|----------|----------|
| Type | | | |
| Elements count | | | |
| Libraries needed | | | |
| Complexity | | | |
| Purpose | | | |

## Stylistic Consistency
Are the figures visually consistent with each other?

## Shared Patterns
What TikZ patterns/styles are reused across figures?

## Differences
Key structural or stylistic differences between figures.
"""
}


# --- CLI ---

def main():
    parser = argparse.ArgumentParser(
        description="arXiv Research - TikZ Extraction (Connect extension)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s extract 2301.00001
  %(prog)s extract 2301.00001 --format latex > figures.tex
  %(prog)s extract 2301.00001,2302.00002 --format json
  %(prog)s list 2301.00001
  %(prog)s analyze 2301.00001 quick
  %(prog)s extract 2301.00001 --format tikz | understand.py analyze quick
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    format_choices = ["tikz", "json", "latex", "brief"]

    # Extract command
    extract_parser = subparsers.add_parser("extract", help="Extract TikZ source code")
    extract_parser.add_argument("paper_ids", help="arXiv paper ID(s), comma-separated for batch")
    extract_parser.add_argument("--format", "-f", choices=format_choices, default="tikz")

    # List command
    list_parser = subparsers.add_parser("list", help="List TikZ figures summary")
    list_parser.add_argument("paper_id", help="arXiv paper ID")
    list_parser.add_argument("--format", "-f", choices=format_choices, default="brief")

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Extract TikZ + analysis prompt")
    analyze_parser.add_argument("paper_id", help="arXiv paper ID")
    analyze_parser.add_argument(
        "prompt_type",
        nargs="?",
        choices=list(TIKZ_PROMPTS.keys()),
        default="quick",
        help="Type of analysis prompt"
    )
    analyze_parser.add_argument("--format", "-f", choices=format_choices, default="tikz")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    client = TikzClient()

    try:
        if args.command == "extract":
            paper_ids = [p.strip() for p in args.paper_ids.split(",")]
            all_figures = []

            for paper_id in paper_ids:
                arxiv_id = extractPaperId(paper_id)
                if not arxiv_id:
                    print(f"Warning: Invalid arXiv ID: {paper_id}", file=sys.stderr)
                    continue

                print(f"Downloading source for {arxiv_id}...", file=sys.stderr)
                figures = client.extractFigures(arxiv_id)

                if not figures:
                    print(f"No TikZ figures found in {arxiv_id}", file=sys.stderr)
                else:
                    print(
                        f"Found {len(figures)} TikZ figure(s) in {arxiv_id}",
                        file=sys.stderr,
                    )

                all_figures.extend(figures)

            id_label = paper_ids[0] if len(paper_ids) == 1 else f"{len(paper_ids)} papers"
            print(formatFigures(all_figures, args.format, id_label))

        elif args.command == "list":
            arxiv_id = extractPaperId(args.paper_id)
            if not arxiv_id:
                print(f"Error: Invalid arXiv ID: {args.paper_id}")
                sys.exit(1)

            print(f"Downloading source for {arxiv_id}...", file=sys.stderr)
            figures = client.extractFigures(arxiv_id)
            print(formatFigures(figures, args.format, arxiv_id))

        elif args.command == "analyze":
            arxiv_id = extractPaperId(args.paper_id)
            if not arxiv_id:
                print(f"Error: Invalid arXiv ID: {args.paper_id}")
                sys.exit(1)

            print(f"Downloading source for {arxiv_id}...", file=sys.stderr)
            figures = client.extractFigures(arxiv_id)

            if not figures:
                print(f"No TikZ figures found in {arxiv_id}")
                sys.exit(0)

            tikz_output = formatFigures(figures, args.format, arxiv_id)
            prompt = TIKZ_PROMPTS.get(args.prompt_type, TIKZ_PROMPTS["quick"])

            print(f"""Please analyze the following TikZ figures using the structured format below.

{prompt}

---
TIKZ FIGURES ({len(figures)} from arXiv:{arxiv_id}):
---

{tikz_output}
""")

    finally:
        client.close()


if __name__ == "__main__":
    main()
