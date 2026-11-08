import pytest
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import evidence
import tikz
from connect import ArxivClient
from query import buildSearchQuery, buildTerm

USER_AGENT = "arxiv-research-skill (+https://github.com/Ray0907/arxiv-research-skill)"

FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2601.00001v1</id>
    <published>2026-01-02T00:00:00Z</published>
    <title>Invented Study of Lantern Routing</title>
    <summary>An invented abstract
      about lantern routing.</summary>
    <author><name>Ada Example</name></author>
    <category term="cs.AI"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2601.00002v2</id>
    <published>2026-01-03T00:00:00Z</published>
    <title>Another Invented Title</title>
    <summary>Second invented abstract.</summary>
    <author><name>Ben Sample</name></author>
    <category term="cs.AI"/>
    <category term="cs.LG"/>
  </entry>
</feed>"""


def test_plain_words_are_anded():
    assert buildTerm("all", "transformer attention mechanism") == (
        "all:transformer AND all:attention AND all:mechanism"
    )


def test_single_word():
    assert buildTerm("all", "transformer") == "all:transformer"


def test_stopword_value_becomes_phrase():
    assert buildTerm("all", "attention is all you need") == 'all:"attention is all you need"'


def test_quotes_are_stripped_first():
    assert buildTerm("all", '"deep learning"') == "all:deep AND all:learning"
    assert buildTerm("all", 'say "of" now') == 'all:"say of now"'


def test_author_multiword_is_phrase():
    assert buildTerm("au", "Yann LeCun", phrase=True) == 'au:"Yann LeCun"'
    assert buildTerm("au", "LeCun", phrase=True) == "au:LeCun"


def test_field_syntax_passes_through_untouched():
    q = 'ti:"graph networks" AND au:Smith'
    assert buildSearchQuery(q, None, None, None, None) == q
    assert buildSearchQuery("cat:cs.CL transformer", None, None, None, None) == "cat:cs.CL transformer"


def test_search_query_combines_parts():
    out = buildSearchQuery("LLM agents", "cs.AI", "Yann LeCun", None, None)
    assert out == 'all:LLM AND all:agents AND au:"Yann LeCun" AND cat:cs.AI'


def test_no_filters_matches_everything():
    assert buildSearchQuery("", None, None, None, None) == "all:*"


def test_since_only_has_no_wildcard():
    out = buildSearchQuery("x", None, None, "2024-01", None)
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    assert f"submittedDate:[202401010000 TO {today}2359]" in out


def test_until_only_has_no_wildcard():
    out = buildSearchQuery("x", None, None, None, "2024-12")
    assert "submittedDate:[199101010000 TO 202412312359]" in out


def test_both_bounds():
    out = buildSearchQuery("x", None, None, "2024-01-15", "2024-02-10")
    assert "submittedDate:[202401150000 TO 202402102359]" in out


def make_client(feed=FEED):
    client = ArxivClient()
    client.client.close()
    client.client = MagicMock()
    response = MagicMock()
    response.text = feed
    client.client.get.return_value = response
    return client


def test_get_recent_uses_atom_api_sorted_by_submission():
    client = make_client()
    papers = client.getRecent("cs.AI", 7)

    url = client.client.get.call_args[0][0]
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    assert parsed.netloc == "export.arxiv.org" and parsed.path == "/api/query"
    assert qs["search_query"] == ["cat:cs.AI"]
    assert qs["sortBy"] == ["submittedDate"]
    assert qs["sortOrder"] == ["descending"]
    assert qs["max_results"] == ["7"]
    assert [p.id_arxiv for p in papers] == ["2601.00001", "2601.00002"]
    assert papers[0].abstract == "An invented abstract about lantern routing."


def test_get_recent_waits_for_the_rate_limit_once():
    client = make_client()
    client._rateLimit = MagicMock()
    client.getRecent("cs.AI", 3)
    assert client._rateLimit.call_count == 1


def test_search_sends_anded_query():
    client = make_client()
    client.search("transformer attention mechanism")
    qs = parse_qs(urlparse(client.client.get.call_args[0][0]).query)
    assert qs["search_query"] == ["all:transformer AND all:attention AND all:mechanism"]


@pytest.mark.parametrize("make", [ArxivClient, evidence.ArxivMetadataClient, tikz.TikzClient])
def test_arxiv_clients_send_user_agent(make):
    owner = make()
    try:
        assert owner.client.headers["user-agent"] == USER_AGENT
    finally:
        owner.client.close()
