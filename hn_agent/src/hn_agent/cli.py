"""
CLI interface for the HN research agent.
"""

import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from hn_agent.agent.research import run_research, DeepResearchReport


def main():
    """Main CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="HN Deep Research Agent")
    parser.add_argument("question", nargs="+", help="Research question")
    parser.add_argument("--max-stories", type=int, default=8, help="Max stories to summarize")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output")
    
    args = parser.parse_args()
    question = " ".join(args.question)
    
    if not args.quiet:
        print(f"🔍 Researching: {question}", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
    
    try:
        report = run_research(
            question, 
            max_stories_to_summarize=args.max_stories,
            verbose=not args.quiet
        )
        
        if args.json:
            # Output JSON to stdout
            print(json.dumps(report.model_dump(), indent=2))
        else:
            # Human-readable output
            print(f"\n📋 Research Report\n")
            print(f"Question: {report.question}\n")
            
            if report.method:
                print(f"Methods Used:")
                for method in report.method:
                    print(f"  • {method}")
                print()
            
            if report.key_findings:
                print(f"Key Findings ({len(report.key_findings)}):")
                for i, finding in enumerate(report.key_findings, 1):
                    print(f"  {i}. {finding}")
                print()
            
            if report.themes:
                print(f"Themes Identified ({len(report.themes)}):")
                for theme in report.themes:
                    if isinstance(theme, dict):
                        print(f"  • {theme.get('topic', theme)}")
                        if 'description' in theme:
                            print(f"    {theme['description']}")
                    else:
                        print(f"  • {theme}")
                print()
            
            if report.controversies:
                print(f"Controversies/Debates ({len(report.controversies)}):")
                for controversy in report.controversies:
                    print(f"  • {controversy}")
                print()
            
            if report.sources:
                print(f"Sources Analyzed ({len(report.sources)} stories):")
                for source in report.sources:
                    if isinstance(source, dict):
                        story_id = source.get('id', source.get('story_id', '?'))
                        title = source.get('title', 'Unknown')
                        print(f"  • [{story_id}] {title}")
                    else:
                        print(f"  • {source}")
                print()
            
            if report.limitations:
                print(f"Research Limitations:")
                for limitation in report.limitations:
                    print(f"  ⚠️  {limitation}")
    
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()