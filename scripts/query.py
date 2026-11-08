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


def parseDateToArxiv(date_str: str, is_start: bool = True) -> str:
    """Convert date string to arXiv API format (YYYYMMDDTTTT).

    Args:
        date_str: Date in YYYY-MM or YYYY-MM-DD format
        is_start: If True, use start of period; if False, use end of period
    """
    parts = date_str.split("-")
    year = parts[0]
    month = parts[1] if len(parts) > 1 else ("01" if is_start else "12")
    day = parts[2] if len(parts) > 2 else ("01" if is_start else "31")

    if not is_start and len(parts) <= 2:
        day = f"{calendar.monthrange(int(year), int(month))[1]:02d}"

    time_part = "0000" if is_start else "2359"
    return f"{year}{month}{day}{time_part}"


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
        parts.append(f"submittedDate:[{date_from} TO {date_to}]")

    return " AND ".join(p for p in parts if p) or "all:*"
