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

### Literature Review

```bash
# 1. Find seed papers ranked by citation impact
uv run python scripts/connect.py search "your topic" --limit 50 --with-citations --sort citations

# 2. Expand with similar papers from top results
uv run python scripts/connect.py similar "top_paper_id"

# 3. Analyze each paper for the review
uv run python scripts/connect.py content "paper_id" | uv run python scripts/understand.py analyze literature

# 4. Generate bibliography
uv run python scripts/evidence.py batch "id1,id2,id3" --format bibtex > refs.bib
```

### Finding Evidence for a Claim

```bash
# 1. Search for supporting research
uv run python scripts/connect.py search "your claim keywords" --with-citations

# 2. Verify the paper supports your claim
uv run python scripts/connect.py content "paper_id" | uv run python scripts/understand.py analyze evidence

# 3. Generate proper citation
uv run python scripts/evidence.py apa "paper_id"
```

---

## API Dependencies

| Service | Purpose | Rate Limit | API Key |
|---------|---------|------------|---------|
| arXiv | Paper search, content | 1 req/3s | No |
| Semantic Scholar | Citations, similar papers | 100 req/5min | Optional (higher limits) |
| Jina Reader | Full text extraction | Generous | No |

Scripts include built-in rate limiting and backoff.

## Error Handling

- **Rate limited**: Scripts retry automatically with backoff
- **Paper not found**: Verify arXiv ID format (YYMM.NNNNN)
- **No citations**: Paper may be too new for Semantic Scholar

## File Structure

```
arxiv-research-skill/
├── SKILL.md              # Agent instructions
├── README.md             # Installation and overview
└── scripts/
    ├── connect.py        # Knowledge navigation
    ├── understand.py     # Analysis prompts
    ├── evidence.py       # Citation generation
    ├── tikz.py           # TikZ figure extraction
    ├── cache.py          # SQLite caching (~/.cache/arxiv-research/papers.db)
    └── utils.py          # Shared utilities (extractPaperId, cleanText)
```
