# Workflow Patterns

## Literature Review

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

## Finding Evidence for a Claim

```bash
# 1. Search for supporting research
uv run python scripts/connect.py search "your claim keywords" --with-citations

# 2. Verify the paper supports your claim
uv run python scripts/connect.py content "paper_id" | uv run python scripts/understand.py analyze evidence

# 3. Generate proper citation
uv run python scripts/evidence.py apa "paper_id"
```
