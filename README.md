# arXiv Research Skill

Agent skill for academic research on arXiv.

## Core Principle

```
Research = Building knowledge on existing knowledge

connect -> understand -> evidence
  Find  ->  Comprehend  ->  Cite
```

## Installation

```bash
uv sync
```

## The Three Pillars

### 1. Connect (Knowledge Navigation)

Find relevant existing knowledge.

```bash
# Search papers
uv run python scripts/connect.py search "transformer attention" --limit 10

# Search with citation counts
uv run python scripts/connect.py search "LLM agents" --with-citations --sort citations

# Search with date range
uv run python scripts/connect.py search "LLM agents" --since 2023-01 --until 2024-06

# Find similar papers
uv run python scripts/connect.py similar 2301.00001

# Get recent papers in a category
uv run python scripts/connect.py recent cs.AI --limit 20

# Search by author
uv run python scripts/connect.py by-author "Yann LeCun"

# Get paper details
uv run python scripts/connect.py paper 2301.00001

# Get full paper content (single or batch)
uv run python scripts/connect.py content 2301.00001
uv run python scripts/connect.py content 2301.00001,2302.00002,2303.00003

# Get papers that cite this paper
uv run python scripts/connect.py cited-by 2301.00001 --limit 20

# Find coauthors of an author
uv run python scripts/connect.py coauthors "Yann LeCun" --limit 20
```

### 2. Understand (Meaning Extraction)

Comprehend what the knowledge contains.

```bash
# List available analysis prompts
uv run python scripts/understand.py list

# Get a specific prompt
uv run python scripts/understand.py get quick
uv run python scripts/understand.py get methodology
uv run python scripts/understand.py get critical
uv run python scripts/understand.py get compare

# Generate analysis request from paper content
uv run python scripts/connect.py content 2301.00001 | uv run python scripts/understand.py analyze quick
```

Available prompts:

- `quick` - Fast structured summary
- `methodology` - Detailed methodology extraction
- `contribution` - Identify and rank contributions
- `critical` - Critical analysis with strengths/weaknesses
- `compare` - Multi-paper comparison table
- `literature` - Organize for literature review
- `implementation` - Extract reproduction details
- `evidence` - Evaluate as evidence for a claim

### 3. Evidence (Source Attribution)

Create verifiable links to sources.

```bash
# Generate BibTeX
uv run python scripts/evidence.py bibtex 2301.00001

# Generate APA citation
uv run python scripts/evidence.py apa 2301.00001

# Generate IEEE citation
uv run python scripts/evidence.py ieee 2301.00001

# Generate RIS (for Zotero/Mendeley/EndNote)
uv run python scripts/evidence.py ris 2301.00001

# Generate all formats
uv run python scripts/evidence.py all 2301.00001

# Batch generate citations
uv run python scripts/evidence.py batch "2301.00001,2302.00002,2303.00003" --format bibtex
uv run python scripts/evidence.py batch "2301.00001,2302.00002" --format ris > refs.ris

# Get raw metadata
uv run python scripts/evidence.py metadata 2301.00001
```

## Workflow Examples

### Literature Review

```bash
# 1. Find seed papers
uv run python scripts/connect.py search "your topic" --limit 30 --with-citations

# 2. Get similar papers from top results
uv run python scripts/connect.py similar 2301.00001

# 3. Analyze each paper
uv run python scripts/connect.py content 2301.00001 | uv run python scripts/understand.py analyze literature

# 4. Generate bibliography
uv run python scripts/evidence.py batch "id1,id2,id3" --format bibtex > refs.bib
```

### Finding Evidence for a Claim

```bash
# 1. Search for supporting research
uv run python scripts/connect.py search "your claim keywords" --with-citations

# 2. Verify the paper supports your claim
uv run python scripts/connect.py content 2301.00001

# 3. Generate citation
uv run python scripts/evidence.py apa 2301.00001
```

## API Dependencies

| Service          | Purpose                         | Rate Limit   | API Key  |
| ---------------- | ------------------------------- | ------------ | -------- |
| arXiv API        | Paper search, metadata          | 1 req/3s     | No       |
| Semantic Scholar | Citation counts, similar papers | 100 req/5min | Optional |
| Jina Reader      | Full text extraction            | ~1 req/s     | No       |

- Semantic Scholar API key is optional, provides higher rate limits
- Scripts include built-in rate limiting

## License

MIT
