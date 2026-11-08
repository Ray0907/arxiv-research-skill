#!/usr/bin/env python3
"""
utils.py - Shared utilities for arXiv Research Skill

Common functions used across connect, evidence, and cache modules.
"""

import re
from typing import Optional


# Rate limits, shared across all clients that talk to these services.
ARXIV_RATE_LIMIT_DELAY = 3.0  # arXiv asks for 1 request per 3 seconds
SEMANTIC_SCHOLAR_RATE_LIMIT_DELAY = 0.5  # 100 requests per 5 minutes = ~0.5s between requests
ARXIV_USER_AGENT = "arxiv-research-skill (+https://github.com/Ray0907/arxiv-research-skill)"
TIMEOUT = 30.0
ARXIV_BASE = "https://arxiv.org"
ARXIV_EXPORT = "https://export.arxiv.org"


# New-style: YYMM.NNNNN or YYMM.NNNNNNN, optional version suffix (e.g. 2301.00001v2)
# Old-style: archive/YYMMNNN, optional version suffix (e.g. hep-th/9901001v1)
_NEW_STYLE = r"(\d{4}\.\d{4,5})(?:v\d+)?"
_OLD_STYLE = r"([a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?"


def extractPaperId(url_or_id: str) -> Optional[str]:
    """Extract arXiv paper ID from URL or return ID if already in ID format.

    Supports:
    - Full URLs: https://arxiv.org/abs/2301.00001, https://arxiv.org/abs/2301.00001v2
    - PDF URLs: https://arxiv.org/pdf/2301.00001.pdf
    - Bare IDs: 2301.00001, 2301.00001v2
    - Old-style IDs: hep-th/9901001, hep-th/9901001v1

    Version suffixes are stripped. Returns the arXiv ID or None if not found.
    """
    patterns = [
        rf"arxiv\.org/abs/{_NEW_STYLE}",
        rf"arxiv\.org/pdf/{_NEW_STYLE}",
        rf"arxiv\.org/abs/{_OLD_STYLE}",
        rf"arxiv\.org/pdf/{_OLD_STYLE}",
        rf"^{_NEW_STYLE}$",
        rf"^{_OLD_STYLE}$",
    ]
    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)
    return None


def cleanText(text: str) -> str:
    """Clean and normalize text content.

    Removes extra whitespace and newlines.
    """
    text = text.replace("\n", " ")
    text = " ".join(text.split())
    return text.strip()
