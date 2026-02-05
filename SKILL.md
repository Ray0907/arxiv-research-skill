---
name: arxiv-research
description: Searches academic papers on arXiv, analyzes research content, builds literature reviews, and generates citations for academic writing. Triggers when users need to find, understand, or cite arXiv papers, extract TikZ figures from LaTeX sources, or explore citation networks and coauthor relationships.
---

# arXiv Research Skill

## Overview

This skill enables systematic academic research through three core capabilities that form the minimal complete loop of knowledge building:

```
connect -> understand -> evidence
  Find  ->  Comprehend -> Cite
```

## Setup

Install dependencies: `uv sync`

## The Three Pillars

### 1. Connect (Knowledge Navigation)

**Purpose:** Find relevant existing knowledge

**When to use:**
- Starting research on a new topic
- Finding related work for a paper
- Discovering what exists in a field

**Capabilities:**
- Semantic search across arXiv
- Filter by category, author, date
- Rank by citation impact (via Semantic Scholar)
- Find similar papers to a known paper

**Usage:**
```bash
uv run python scripts/connect.py search "transformer attention mechanism" --category cs.LG --limit 20
uv run python scripts/connect.py search "LLM agents" --since 2023-01 --until 2024-06  # Date filtering
uv run python scripts/connect.py similar "2301.00001" --limit 10
uv run python scripts/connect.py recent cs.AI --days 7
uv run python scripts/connect.py by-author "Yann LeCun"
uv run python scripts/connect.py cited-by "2301.00001" --limit 20  # Forward citations
uv run python scripts/connect.py coauthors "Yann LeCun" --limit 20  # Collaboration network
```

### 2. Understand (Meaning Extraction)

**Purpose:** Comprehend what the knowledge contains

**When to use:**
- Need to quickly grasp a paper's contribution
- Extracting methodology details
- Comparing multiple papers
- Writing literature review sections

**Capabilities:**
- Structured paper analysis (problem, method, contribution, limitations)
- Key findings extraction
- Methodology breakdown
- Multi-paper comparison

**Usage:**
```bash
# Get paper content for analysis (single or batch)
uv run python scripts/connect.py content "2301.00001"
uv run python scripts/connect.py content "2301.00001,2302.00002,2303.00003"

# Pipe content into analysis prompts
uv run python scripts/connect.py content "2301.00001" | uv run python scripts/understand.py analyze quick
```

**Available prompts:** `uv run python scripts/understand.py list`

Prompts: `quick`, `methodology`, `contribution`, `critical`, `compare`, `literature`, `implementation`, `evidence`

### 3. Evidence (Source Attribution)

**Purpose:** Create verifiable links to sources

**When to use:**
- Writing academic papers
- Need proper citations
- Building bibliography
- Ensuring traceability of claims

**Capabilities:**
- BibTeX generation
- Multiple citation formats (APA, IEEE, ACM, Chicago, RIS)
- Batch citation export
- RIS export for Zotero/Mendeley/EndNote

**Usage:**
```bash
uv run python scripts/evidence.py bibtex "2301.00001"
uv run python scripts/evidence.py apa "2301.00001"
uv run python scripts/evidence.py ris "2301.00001"  # For Zotero/Mendeley
uv run python scripts/evidence.py batch "2301.00001,2302.00002,2303.00003" --format bibtex
uv run python scripts/evidence.py batch "2301.00001,2302.00002" --format ris > refs.ris
```

### 4. TikZ (Figure Extraction)

**Purpose:** Extract TikZ source code from arXiv paper LaTeX sources

**When to use:**
- Reusing or adapting figures from papers
- Analyzing visualization techniques
- Understanding diagram construction

**Capabilities:**
- Extracts tikzpicture, tikzcd, circuitikz, pgfplots environments
- Captures captions, labels, and library dependencies
- Outputs as pure TikZ, compilable LaTeX, JSON, or brief summary

**Usage:**
```bash
uv run python scripts/tikz.py extract "2301.00001"
uv run python scripts/tikz.py extract "2301.00001" --format latex > figures.tex
uv run python scripts/tikz.py extract "2301.00001,2302.00002" --format json
uv run python scripts/tikz.py list "2301.00001"
uv run python scripts/tikz.py extract "2301.00001" --format tikz | uv run python scripts/understand.py analyze quick
```

## Workflow Examples

### Literature Review Workflow

```
Progress:
- [ ] Step 1: Find seed papers
- [ ] Step 2: Expand with similar papers
- [ ] Step 3: Analyze each paper
- [ ] Step 4: Generate bibliography
```

```bash
# Step 1: Find seed papers (ranked by citation impact)
uv run python scripts/connect.py search "your topic" --limit 50 --with-citations --sort citations

# Step 2: Expand with similar papers from top results
uv run python scripts/connect.py similar "top_paper_id"

# Step 3: Analyze each paper
uv run python scripts/connect.py content "paper_id" | uv run python scripts/understand.py analyze literature

# Step 4: Generate bibliography
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

## API Dependencies

| Service | Purpose | Rate Limit | API Key Required |
|---------|---------|------------|------------------|
| arXiv | Paper search, content | 1 req/3s | No |
| Semantic Scholar | Citations, similar papers | 100 req/5min | No (optional for higher limits) |
| Jina Reader | Full text extraction | Generous | No |

## File Structure

```
arxiv-research-skill/
├── SKILL.md              # This file - usage guide
└── scripts/
    ├── connect.py        # Knowledge navigation
    ├── understand.py     # Analysis prompts
    ├── evidence.py       # Citation generation
    ├── tikz.py           # TikZ figure extraction
    ├── cache.py          # SQLite caching (~/.cache/arxiv-research/papers.db)
    └── utils.py          # Shared utilities (extractPaperId, cleanText)
```

## Common Patterns

### Finding Foundational Papers
```bash
uv run python scripts/connect.py search "topic" --sort citations --limit 10
```

### Tracking Recent Developments
```bash
uv run python scripts/connect.py recent cs.AI --days 30
```

### Building a Reading List
```bash
uv run python scripts/connect.py search "topic" > papers.json
# Review and filter
uv run python scripts/evidence.py batch "selected_ids" --format bibtex
```

## Error Handling

- **Rate limited:** Wait and retry, scripts have built-in backoff
- **Paper not found:** Verify arXiv ID format (YYMM.NNNNN)
- **No citations:** Paper may be too new for Semantic Scholar
