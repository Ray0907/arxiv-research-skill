---
name: arxiv-research
description: Use when searching academic papers on arXiv, understanding research content, building literature reviews, or generating citations for academic writing
---

# arXiv Research Skill

## Overview

This skill enables systematic academic research through three core capabilities that form the minimal complete loop of knowledge building:

```
connect -> understand -> evidence
  Find  ->  Comprehend -> Cite
```

## Core Principles

**Why this exists:** Research is reducing uncertainty about reality by building on existing knowledge. arXiv contains codified human knowledge. This skill helps navigate and utilize that knowledge effectively.

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
# Run the connect script
python connect.py search "transformer attention mechanism" --category cs.LG --limit 20
python connect.py similar "2301.00001" --limit 10
python connect.py recent cs.AI --days 7
python connect.py by-author "Yann LeCun"
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
# Get paper content for analysis
python connect.py content "2301.00001"

# Then use the understanding prompts in your analysis
```

**Analysis Prompts** (use with paper content):

#### Quick Summary
```
Analyze this paper and provide:
1. Problem: What problem does it solve? (1-2 sentences)
2. Method: How does it solve it? (2-3 sentences)
3. Contribution: What's new/novel? (1-2 sentences)
4. Limitation: What are the limitations? (1-2 sentences)
```

#### Deep Methodology
```
Extract the methodology:
1. Core algorithm/approach
2. Key assumptions
3. Experimental setup
4. Evaluation metrics
5. Baseline comparisons
```

#### Literature Comparison
```
Compare these papers on:
| Aspect | Paper A | Paper B | Paper C |
|--------|---------|---------|---------|
| Problem |
| Method |
| Dataset |
| Results |
| Limitations |
```

### 3. Evidence (Source Attribution)

**Purpose:** Create verifiable links to sources

**When to use:**
- Writing academic papers
- Need proper citations
- Building bibliography
- Ensuring traceability of claims

**Capabilities:**
- BibTeX generation
- Multiple citation formats (APA, IEEE, ACM, Chicago)
- Batch citation export
- Citation verification

**Usage:**
```bash
# Generate citations
python evidence.py bibtex "2301.00001"
python evidence.py apa "2301.00001"
python evidence.py batch "2301.00001,2302.00002,2303.00003" --format bibtex
```

## Workflow Examples

### Literature Review Workflow

```
1. CONNECT: Find seed papers
   python connect.py search "your topic" --limit 50

2. CONNECT: Rank by impact
   (Results include citation counts from Semantic Scholar)

3. CONNECT: Expand with similar papers
   python connect.py similar "top_paper_id"

4. UNDERSTAND: Analyze each paper
   python connect.py content "paper_id" | analyze with prompts

5. EVIDENCE: Generate bibliography
   python evidence.py batch "id1,id2,id3" --format bibtex > refs.bib
```

### Finding Evidence for a Claim

```
1. CONNECT: Search for supporting research
   python connect.py search "your claim keywords"

2. UNDERSTAND: Verify the paper supports your claim
   python connect.py content "paper_id"

3. EVIDENCE: Generate proper citation
   python evidence.py apa "paper_id"
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
├── SKILL.md          # This file - usage guide
├── connect.py        # Knowledge navigation
├── understand.py     # Analysis utilities
└── evidence.py       # Citation generation
```

## Common Patterns

### Finding Foundational Papers
```bash
python connect.py search "topic" --sort citations --limit 10
```

### Tracking Recent Developments
```bash
python connect.py recent cs.AI --days 30
```

### Building a Reading List
```bash
python connect.py search "topic" > papers.json
# Review and filter
python evidence.py batch "selected_ids" --format bibtex
```

## Error Handling

- **Rate limited:** Wait and retry, scripts have built-in backoff
- **Paper not found:** Verify arXiv ID format (YYMM.NNNNN)
- **No citations:** Paper may be too new for Semantic Scholar
