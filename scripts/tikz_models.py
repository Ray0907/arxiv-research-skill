"""tikz_models.py - Shared data for TikZ extraction."""

from dataclasses import dataclass
from typing import Optional

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
