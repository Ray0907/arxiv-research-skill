#!/usr/bin/env python3
"""
utils.py - Shared utilities for arXiv Research Skill

Common functions used across connect, evidence, and cache modules.
"""

import re
from typing import Optional


def extractPaperId(url_or_id: str) -> Optional[str]:
    """Extract arXiv paper ID from URL or return ID if already in ID format.

    Supports:
    - Full URLs: https://arxiv.org/abs/2301.00001
    - PDF URLs: https://arxiv.org/pdf/2301.00001.pdf
    - Bare IDs: 2301.00001

    Returns:
        The arXiv ID (e.g., "2301.00001") or None if not found.
    """
    patterns = [
        r"arxiv\.org/abs/(\d+\.\d+)",
        r"arxiv\.org/pdf/(\d+\.\d+)",
        r"^(\d+\.\d+)$",
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
