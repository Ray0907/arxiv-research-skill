---
name: arxiv-research
description: Searches academic papers on arXiv, analyzes research content, builds literature reviews, and generates citations for academic writing. Triggers when users need to find, understand, or cite arXiv papers, extract TikZ figures from LaTeX sources, or explore citation networks and coauthor relationships.
license: MIT
metadata:
  author: Ray0907
  version: "0.1.0"
---

# arXiv Research Skill

Systematic academic research through four capabilities that form a knowledge-building loop:

```
connect -> understand -> evidence
  Find  ->  Comprehend ->  Cite
             tikz (extract figures from LaTeX sources)
```

## Setup

Install dependencies: `uv sync`

If an `arxiv` MCP server ([Ray0907/arXiv-mcp](https://github.com/Ray0907/arXiv-mcp)) is already configured, prefer its
`search`, `search_advanced`, `get_paper`, `get_recent` and `get_content` tools for plain lookups. Use these scripts for
citation networks, coauthors, structured analysis prompts, citation formats and TikZ extraction, which the server does not provide.

## Capabilities

### Connect (Knowledge Navigation)

Find relevant papers across arXiv, explore citation networks, and discover related work.

```bash
# Search with optional filters
uv run python scripts/connect.py search "transformer attention mechanism" --category cs.LG --limit 20
uv run python scripts/connect.py search "LLM agents" --since 2023-01 --until 2024-06
uv run python scripts/connect.py search "topic" --with-citations --sort citations

# Discover related work
uv run python scripts/connect.py similar "2301.00001" --limit 10
uv run python scripts/connect.py recent cs.AI --days 7
uv run python scripts/connect.py by-author "Yann LeCun"

# Citation network
uv run python scripts/connect.py cited-by "2301.00001" --limit 20
uv run python scripts/connect.py coauthors "Yann LeCun" --limit 20

# Get full paper content (single or batch)
uv run python scripts/connect.py content "2301.00001"
uv run python scripts/connect.py content "2301.00001,2302.00002,2303.00003"
```

### Understand (Meaning Extraction)

Analyze paper content with structured prompts. Pipe paper content from `connect.py content` into analysis.

```bash
uv run python scripts/connect.py content "2301.00001" | uv run python scripts/understand.py analyze quick
```

Available prompts (`uv run python scripts/understand.py list`):

| Prompt | Purpose |
|--------|---------|
| `quick` | Fast structured summary |
| `methodology` | Detailed methodology extraction |
| `contribution` | Identify and rank contributions |
| `critical` | Strengths/weaknesses analysis |
| `compare` | Multi-paper comparison table |
| `literature` | Organize for literature review |
| `implementation` | Extract reproduction details |
| `evidence` | Evaluate as evidence for a claim |

### Evidence (Source Attribution)

Generate citations in multiple formats and export for reference managers.

```bash
uv run python scripts/evidence.py bibtex "2301.00001"
uv run python scripts/evidence.py apa "2301.00001"
uv run python scripts/evidence.py ris "2301.00001"           # For Zotero/Mendeley/EndNote
uv run python scripts/evidence.py batch "id1,id2,id3" --format bibtex > refs.bib
uv run python scripts/evidence.py batch "id1,id2" --format ris > refs.ris
```

Formats: `bibtex`, `apa`, `ieee`, `acm`, `chicago`, `ris`

### TikZ (Figure Extraction)

Extract TikZ source code from arXiv paper LaTeX sources. Supports tikzpicture, tikzcd, circuitikz, and pgfplots environments. Captures captions, labels, and library dependencies.

```bash
uv run python scripts/tikz.py extract "2301.00001"                          # Pure TikZ code
uv run python scripts/tikz.py extract "2301.00001" --format latex > fig.tex  # Compilable LaTeX
uv run python scripts/tikz.py extract "2301.00001,2302.00002" --format json  # Batch as JSON
uv run python scripts/tikz.py list "2301.00001"                              # Summary only
```

Output formats: `tikz` (default), `latex`, `json`, `brief`

---

## Workflow Patterns

Multi-step recipes (literature review, finding evidence for a claim): see `references/workflows.md`.

## API Dependencies

| Service | Purpose | Rate Limit | API Key |
|---------|---------|------------|---------|
| arXiv | Paper search, content | 1 req/3s | No |
| Semantic Scholar | Citations, similar papers | 100 req/5min | Optional (higher limits) |
| Jina Reader | Full text extraction | Generous | No |

Scripts enforce a fixed delay between requests per service. There is no automatic retry
on failure — a 429 or network error returns an empty result rather than retrying.

## Error Handling

- **Rate limited**: Requests will fail with an empty result, not retry; wait and re-run
- **Paper not found**: Verify arXiv ID format (YYMM.NNNNN)
- **No citations**: Paper may be too new for Semantic Scholar

## File Structure

```
arxiv-research-skill/
├── SKILL.md              # Agent instructions
├── README.md             # Installation and overview
├── references/
│   └── workflows.md      # Multi-step workflow recipes
└── scripts/
    ├── connect.py        # Knowledge navigation
    ├── understand.py     # Analysis prompts
    ├── evidence.py       # Citation generation
    ├── tikz.py           # TikZ figure extraction
    ├── cache.py          # SQLite caching (~/.cache/arxiv-research/papers.db)
    └── utils.py          # Shared utilities (extractPaperId, cleanText)
```
