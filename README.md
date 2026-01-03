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
uv run python connect.py search "transformer attention" --limit 10

# Search with citation counts
uv run python connect.py search "LLM agents" --with-citations --sort citations

# Find similar papers
uv run python connect.py similar 2301.00001

# Get recent papers in a category
uv run python connect.py recent cs.AI --limit 20

# Search by author
uv run python connect.py by-author "Yann LeCun"

# Get paper details
uv run python connect.py paper 2301.00001

# Get full paper content
uv run python connect.py content 2301.00001
```

### 2. Understand (Meaning Extraction)

Comprehend what the knowledge contains.

```bash
# List available analysis prompts
uv run python understand.py list

# Get a specific prompt
uv run python understand.py get quick
uv run python understand.py get methodology
uv run python understand.py get critical
uv run python understand.py get compare

# Generate analysis request from paper content
uv run python connect.py content 2301.00001 | uv run python understand.py analyze quick
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
uv run python evidence.py bibtex 2301.00001

# Generate APA citation
uv run python evidence.py apa 2301.00001

# Generate IEEE citation
uv run python evidence.py ieee 2301.00001

# Generate all formats
uv run python evidence.py all 2301.00001

# Batch generate citations
uv run python evidence.py batch "2301.00001,2302.00002,2303.00003" --format bibtex

# Get raw metadata
uv run python evidence.py metadata 2301.00001
```

## Workflow Examples

### Literature Review

```bash
# 1. Find seed papers
uv run python connect.py search "your topic" --limit 30 --with-citations

# 2. Get similar papers from top results
uv run python connect.py similar 2301.00001

# 3. Analyze each paper
uv run python connect.py content 2301.00001 | uv run python understand.py analyze literature

# 4. Generate bibliography
uv run python evidence.py batch "id1,id2,id3" --format bibtex > refs.bib
```

### Finding Evidence for a Claim

```bash
# 1. Search for supporting research
uv run python connect.py search "your claim keywords" --with-citations

# 2. Verify the paper supports your claim
uv run python connect.py content 2301.00001

# 3. Generate citation
uv run python evidence.py apa 2301.00001
```

## API Dependencies

| Service          | Purpose                         | Rate Limit   |
| ---------------- | ------------------------------- | ------------ |
| arXiv API        | Paper search, metadata          | 1 req/3s     |
| Semantic Scholar | Citation counts, similar papers | 100 req/5min |
| Jina Reader      | Full text extraction            | Generous     |

No API keys required.

## License

MIT
