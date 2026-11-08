#!/usr/bin/env python3
"""
tikz.py - TikZ Extraction from arXiv Papers

Connect extension: extracts TikZ source code from arXiv LaTeX sources.
Downloads e-print archives, parses .tex files, and returns structured TikZ figures.
"""

import argparse
import sys
import time
from typing import Optional

try:
    import httpx
except ImportError:
    print("Error: httpx required. Install with: pip install httpx")
    sys.exit(1)

from tikz_extract import processArchive
from tikz_format import formatFigures
from tikz_models import TikzFigure
from utils import extractPaperId, ARXIV_RATE_LIMIT_DELAY, ARXIV_USER_AGENT


# Configuration
ARXIV_BASE = "https://arxiv.org"
TIMEOUT = 60.0


class TikzClient:
    """Client for extracting TikZ figures from arXiv papers."""

    def __init__(self):
        self.client = httpx.Client(
            timeout=TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": ARXIV_USER_AGENT},
        )
        self.last_request_time = 0

    def _rateLimit(self):
        """Ensure rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < ARXIV_RATE_LIMIT_DELAY:
            time.sleep(ARXIV_RATE_LIMIT_DELAY - elapsed)
        self.last_request_time = time.time()

    def extractFigures(self, arxiv_id: str) -> list[TikzFigure]:
        """Extract all TikZ figures from a paper's LaTeX source.

        Downloads the e-print archive, extracts .tex files, and parses
        TikZ environments with a counting parser for correct nesting.
        """
        content = self._downloadSource(arxiv_id)
        if content is None:
            return []

        return processArchive(arxiv_id, content)

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

    def close(self):
        """Close the HTTP client."""
        self.client.close()


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
