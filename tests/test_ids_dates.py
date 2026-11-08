import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from connect import ArxivClient
from query import parseDateToArxiv

LEGACY_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2601.00001v1</id>
    <published>2026-01-02T00:00:00Z</published>
    <title>Invented New Style Paper</title>
    <summary>Invented abstract.</summary>
    <author><name>Ada Example</name></author>
    <category term="cs.AI"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/hep-th/9901001v2</id>
    <published>1999-01-02T00:00:00Z</published>
    <title>Invented Legacy Paper</title>
    <summary>Invented legacy abstract.</summary>
    <author><name>Ben Sample</name></author>
    <category term="hep-th"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/math.GT/0309136v1</id>
    <published>2003-09-08T00:00:00Z</published>
    <title>Invented Legacy Subject Paper</title>
    <summary>Another invented abstract.</summary>
    <author><name>Cy Placeholder</name></author>
    <category term="math.GT"/>
  </entry>
</feed>"""


def test_parse_keeps_legacy_ids_and_strips_versions():
    papers = ArxivClient._parseApiResults(LEGACY_FEED)
    assert [p.id_arxiv for p in papers] == ["2601.00001", "hep-th/9901001", "math.GT/0309136"]
    assert papers[1].url_abstract.endswith("/abs/hep-th/9901001")


@pytest.mark.parametrize(
    "date, last_day",
    [
        ("2024-02", "29"),
        ("2023-02", "28"),
        ("1900-02", "28"),
        ("2000-02", "29"),
        ("2024-04", "30"),
        ("2024-12", "31"),
    ],
)
def test_until_month_ends_on_its_real_last_day(date, last_day):
    assert parseDateToArxiv(date, is_start=False) == f"{date.replace('-', '')}{last_day}2359"


def test_explicit_day_is_not_clamped():
    assert parseDateToArxiv("2024-02-15", is_start=False) == "202402152359"
