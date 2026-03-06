# arXiv Research Skill

Agent skill for academic research on arXiv — find papers, analyze content, generate citations.

```
connect -> understand -> evidence
  Find  ->  Comprehend ->  Cite
```

## Installation

### As an Agent Skill (via [Vercel Skills](https://vercel.com/docs/agent-resources/skills))

```bash
npx skills add Ray0907/arxiv-research-skill
```

This installs the skill for your coding agent (Claude Code, Cursor, Copilot, etc.).

### Manual Setup

```bash
uv sync
```

## What It Does

| Capability | Script | Purpose |
|------------|--------|---------|
| **Connect** | `scripts/connect.py` | Search arXiv, find similar papers, explore citation networks and coauthors |
| **Understand** | `scripts/understand.py` | Structured analysis prompts (quick summary, methodology, critical review, comparison) |
| **Evidence** | `scripts/evidence.py` | Generate citations (BibTeX, APA, IEEE, RIS) and batch export |
| **TikZ** | `scripts/tikz.py` | Extract TikZ figure source code from paper LaTeX sources |

## Quick Start

```bash
# Search papers
uv run python scripts/connect.py search "transformer attention" --limit 10

# Analyze a paper
uv run python scripts/connect.py content 2301.00001 | uv run python scripts/understand.py analyze quick

# Generate citation
uv run python scripts/evidence.py bibtex 2301.00001

# Extract TikZ figures
uv run python scripts/tikz.py extract 2206.00364
```

See [SKILL.md](SKILL.md) for full command reference and workflow patterns.

## API Dependencies

| Service | Purpose | Rate Limit | API Key |
|---------|---------|------------|---------|
| arXiv API | Paper search, metadata | 1 req/3s | No |
| Semantic Scholar | Citation counts, similar papers | 100 req/5min | Optional |
| Jina Reader | Full text extraction | Generous | No |

## License

MIT
