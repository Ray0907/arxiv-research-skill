"""Shared data shapes."""

from dataclasses import dataclass
from typing import Optional


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
