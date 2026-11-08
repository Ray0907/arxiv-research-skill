"""Pure arXiv search-query construction. No network."""

import calendar
import re
from datetime import datetime, timezone
from typing import Optional


# The API drops stopwords from ANDed terms and returns 0 hits, so values holding one are sent as a phrase.
STOPWORDS = frozenset(
    "a an and are as at be but by for if in into is it no not of on or such that the their "
    "then there these they this to was will with".split()
)
FIELD_SYNTAX = re.compile(r"\b(?:ti|au|abs|co|jr|cat|rn|all):")
ARXIV_FIRST_DATE = "19910101"


def buildTerm(prefix: str, value: str, phrase: bool = False) -> str:
    """AND every word under prefix, or quote the value when it must stay a phrase."""
    words = value.replace('"', "").split()
    if not words:
        return ""
    if (phrase and len(words) > 1) or any(w.lower() in STOPWORDS for w in words):
        return f'{prefix}:"{" ".join(words)}"'
    return " AND ".join(f"{prefix}:{w}" for w in words)


_DATE_RE = re.compile(r"^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$")


def parseDateToArxiv(date_str: str, is_start: bool = True) -> str:
    """Convert YYYY, YYYY-MM or YYYY-MM-DD to the arXiv API format (YYYYMMDDTTTT).

    Args:
        is_start: If True, use the start of the period; if False, its end.

    Raises:
        ValueError: if the text is not one of those forms or is not a real date.
    """
    match = _DATE_RE.match(date_str.strip())
    if not match:
        raise ValueError(f"Invalid date '{date_str}'. Use YYYY, YYYY-MM or YYYY-MM-DD.")
    year, month, day = (int(g) if g else None for g in match.groups())

    if month is None:
        month = 1 if is_start else 12
    if not 1 <= month <= 12:
        raise ValueError(f"Invalid date '{date_str}': month must be 01-12.")
    last_day = calendar.monthrange(year, month)[1]
    if day is None:
        day = 1 if is_start else last_day
    if not 1 <= day <= last_day:
        raise ValueError(f"Invalid date '{date_str}': {year:04d}-{month:02d} has {last_day} days.")

    return f"{year:04d}{month:02d}{day:02d}{'0000' if is_start else '2359'}"


def buildSearchQuery(
    query: Optional[str],
    category: Optional[str],
    author: Optional[str],
    since: Optional[str],
    until: Optional[str],
) -> str:
    """Build the arXiv API search_query string."""
    parts = []
    if query:
        parts.append(query if FIELD_SYNTAX.search(query) else buildTerm("all", query))
    if author:
        parts.append(buildTerm("au", author, phrase=True))
    if category:
        parts.append(f"cat:{category}")

    # The API rejects an open-ended range ([x TO *] is HTTP 500), so fill the missing bound.
    if since or until:
        date_from = parseDateToArxiv(since, is_start=True) if since else f"{ARXIV_FIRST_DATE}0000"
        date_to = (
            parseDateToArxiv(until, is_start=False)
            if until
            else datetime.now(timezone.utc).strftime("%Y%m%d2359")
        )
        if date_from > date_to:
            raise ValueError(f"since ({since}) must not be after until ({until}).")
        parts.append(f"submittedDate:[{date_from} TO {date_to}]")

    return " AND ".join(p for p in parts if p) or "all:*"
