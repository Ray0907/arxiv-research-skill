#!/usr/bin/env python3
"""
understand.py - Meaning Extraction for arXiv Research

Core capability: Comprehend what the knowledge contains
Provides structured prompts and templates for analyzing academic papers.
"""

import argparse
import sys
from typing import Optional


# Analysis Prompt Templates
PROMPTS = {
    "quick": """Analyze this paper and provide a structured summary:

## Problem
What problem does this paper address? (1-2 sentences)

## Method
How does it solve the problem? (2-3 sentences describing the approach)

## Contribution
What is novel or new? (1-2 sentences on key contributions)

## Limitations
What are the limitations or constraints? (1-2 sentences)

## Key Takeaway
One sentence summary for someone who will never read the full paper.
""",

    "methodology": """Extract the methodology details from this paper:

## Core Approach
- Algorithm/method name:
- High-level description:

## Key Assumptions
1.
2.
3.

## Technical Details
- Architecture/design:
- Key parameters:
- Training/optimization (if applicable):

## Experimental Setup
- Datasets used:
- Baseline comparisons:
- Evaluation metrics:

## Reproducibility
- Code available: (yes/no/url)
- Data available: (yes/no/url)
- Key implementation details:
""",

    "contribution": """Identify the contributions of this paper:

## Main Contributions (ranked by significance)
1. [Most significant]
2.
3.

## Novelty Analysis
- What existed before:
- What this paper adds:
- Why it matters:

## Comparison to Prior Work
| Aspect | Prior Work | This Paper | Improvement |
|--------|------------|------------|-------------|
|        |            |            |             |

## Impact Assessment
- Theoretical impact:
- Practical impact:
- Potential applications:
""",

    "critical": """Critically analyze this paper:

## Strengths
1.
2.
3.

## Weaknesses
1.
2.
3.

## Assumptions to Question
- Assumption 1: [Is it valid?]
- Assumption 2: [Is it valid?]

## Missing Elements
- What experiments are missing?
- What comparisons would strengthen the claims?
- What edge cases are not addressed?

## Potential Issues
- Reproducibility concerns:
- Scalability concerns:
- Generalization concerns:

## Overall Assessment
[Fair and balanced evaluation]
""",

    "compare": """Compare the following papers on these dimensions:

| Dimension | Paper A | Paper B | Paper C |
|-----------|---------|---------|---------|
| Problem addressed |  |  |  |
| Core method |  |  |  |
| Key innovation |  |  |  |
| Datasets used |  |  |  |
| Main results |  |  |  |
| Limitations |  |  |  |
| Code available |  |  |  |
| Year published |  |  |  |

## Key Differences
1.
2.
3.

## Which to Use When
- Use Paper A when:
- Use Paper B when:
- Use Paper C when:

## Research Gap
What do none of these papers address?
""",

    "literature": """Organize these papers for a literature review:

## Thematic Grouping
Group the papers by theme/approach:

### Theme 1: [Name]
- Paper X: [brief contribution]
- Paper Y: [brief contribution]

### Theme 2: [Name]
- Paper Z: [brief contribution]

## Timeline/Evolution
How has the field evolved?
- Early work (before 20XX):
- Key developments (20XX-20XX):
- Recent advances (20XX-present):

## Open Problems
What questions remain unanswered?
1.
2.
3.

## Synthesis
Write a 200-word synthesis paragraph connecting these works.
""",

    "implementation": """Extract implementation details for reproducing this work:

## Environment Requirements
- Programming language:
- Key libraries/frameworks:
- Hardware requirements:

## Architecture Details
```
[Describe or diagram the architecture]
```

## Hyperparameters
| Parameter | Value | Notes |
|-----------|-------|-------|
|           |       |       |

## Training Details
- Dataset preprocessing:
- Training procedure:
- Optimization settings:

## Evaluation Protocol
- Test/validation split:
- Metrics computation:
- Statistical tests:

## Code Resources
- Official repository:
- Third-party implementations:
- Pre-trained models:
""",

    "evidence": """Evaluate if this paper can be used as evidence for a specific claim:

## The Claim to Support
[State the claim you want to support]

## Paper's Relevant Findings
1.
2.
3.

## Strength of Evidence
- Direct support: [yes/partial/no]
- Experimental validation: [strong/moderate/weak]
- Generalizability: [high/medium/low]

## Caveats
- Context limitations:
- Methodology concerns:
- Conflicting findings:

## Citation Recommendation
- Should cite: [yes/no/maybe]
- How to cite: [as primary evidence / as supporting evidence / as context]
- Suggested citation context: "[Sentence showing how to incorporate]"
"""
}


def getPrompt(prompt_type: str) -> str:
    """Get a specific analysis prompt."""
    return PROMPTS.get(prompt_type, PROMPTS["quick"])


def listPrompts() -> dict[str, str]:
    """List all available prompts with descriptions."""
    descriptions = {
        "quick": "Fast structured summary (problem, method, contribution, limitations)",
        "methodology": "Detailed methodology extraction for understanding approach",
        "contribution": "Identify and rank paper contributions",
        "critical": "Critical analysis with strengths, weaknesses, concerns",
        "compare": "Multi-paper comparison table",
        "literature": "Organize papers for literature review",
        "implementation": "Extract details for reproducing the work",
        "evidence": "Evaluate paper as evidence for a specific claim"
    }
    return descriptions


def generateAnalysisRequest(
    paper_content: str,
    prompt_type: str = "quick",
    custom_context: Optional[str] = None
) -> str:
    """Generate a complete analysis request combining prompt and content."""
    prompt = getPrompt(prompt_type)

    request = f"""Please analyze the following paper content using the structured format below.

{prompt}

---
PAPER CONTENT:
---

{paper_content}
"""

    if custom_context:
        request = f"""Context: {custom_context}

{request}
"""

    return request


def main():
    parser = argparse.ArgumentParser(
        description="arXiv Research - Understand: Meaning Extraction",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s list                          # List available prompts
  %(prog)s get quick                     # Get the quick summary prompt
  %(prog)s get methodology               # Get methodology extraction prompt
  %(prog)s analyze quick < paper.txt     # Generate analysis request from stdin
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # List command
    subparsers.add_parser("list", help="List available analysis prompts")

    # Get command
    get_parser = subparsers.add_parser("get", help="Get a specific prompt")
    get_parser.add_argument(
        "prompt_type",
        choices=list(PROMPTS.keys()),
        help="Type of analysis prompt"
    )

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Generate analysis request from paper content")
    analyze_parser.add_argument(
        "prompt_type",
        choices=list(PROMPTS.keys()),
        help="Type of analysis prompt"
    )
    analyze_parser.add_argument(
        "--context", "-c",
        help="Additional context for the analysis"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "list":
        prompts = listPrompts()
        print("Available Analysis Prompts:")
        print("-" * 60)
        for name, description in prompts.items():
            print(f"  {name:15} - {description}")
        print("\nUsage: understand.py get <prompt_name>")

    elif args.command == "get":
        prompt = getPrompt(args.prompt_type)
        print(prompt)

    elif args.command == "analyze":
        # Read paper content from stdin
        if sys.stdin.isatty():
            print("Error: Please pipe paper content to stdin")
            print("Example: python connect.py content 2301.00001 | python understand.py analyze quick")
            sys.exit(1)

        paper_content = sys.stdin.read()
        request = generateAnalysisRequest(
            paper_content,
            args.prompt_type,
            args.context
        )
        print(request)


if __name__ == "__main__":
    main()
