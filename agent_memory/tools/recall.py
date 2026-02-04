#!/usr/bin/env python3
"""
Recall memories from agent-memory database using semantic search.

Replaces the old keyword-based recall.py script.
Uses embeddings for meaning-based search.

Usage:
    python -m src.tools.recall "what did we decide about pricing"
    python -m src.tools.recall "Bill's preferences" --limit 5
    python -m src.tools.recall "recent decisions" --type decision
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from agent_memory.memory import Memory
from agent_memory.learnings import LearningMachine


def main():
    parser = argparse.ArgumentParser(description="Recall memories")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--db", default="agent_memory.db", help="Database path")
    parser.add_argument("--limit", type=int, default=5, help="Max results")
    parser.add_argument("--min-salience", type=float, default=0.0, help="Minimum importance")
    parser.add_argument("--format", choices=["text", "json", "brief"], default="text")
    parser.add_argument("--no-learnings", action="store_true", help="Skip learnings")
    parser.add_argument("--check-conflicts", action="store_true", 
                        help="Check for contradictions with identity layer")
    
    args = parser.parse_args()
    
    mem = Memory(args.db)
    lm = LearningMachine(args.db)
    
    try:
        results = mem.search(args.query, limit=args.limit, min_salience=args.min_salience)
        
        if not results:
            print("No matching memories found.")
        elif args.format == "json":
            import json
            if args.check_conflicts:
                conflicts = mem.detect_conflicts(results)
                print(json.dumps({"results": results, "conflicts": conflicts}, indent=2))
            else:
                print(json.dumps(results, indent=2))
        elif args.format == "brief":
            for r in results:
                print(f"• {r['content'][:100]}...")
        else:
            print(f"Found {len(results)} relevant memories:\n")
            for i, r in enumerate(results, 1):
                relevance = f"{r['relevance']:.2f}" if r.get('relevance') else "?"
                print(f"{i}. [{r['type']}] (relevance: {relevance})")
                print(f"   {r['content']}")
                if r.get('created_at'):
                    print(f"   Created: {r['created_at'][:10]}")
                print()
        
        # Check for identity conflicts if requested (or always in text mode)
        if args.check_conflicts and results:
            conflicts = mem.detect_conflicts(results)
            if conflicts:
                print("\n⚠️  IDENTITY CONFLICTS DETECTED:")
                for c in conflicts:
                    print(f"   Identity: {c['identity_key']} = {c['identity_value']}")
                    print(f"   Conflict: {c['conflicting_memory'].get('content', '')[:150]}")
                    print(f"   Similarity: {c['similarity']}")
                    print()
        
        # Surface relevant learnings alongside memories
        if not args.no_learnings:
            learnings_ctx = lm.format_context(args.query, limit=3)
            if learnings_ctx:
                print(learnings_ctx)
    
    finally:
        mem.close()
        lm.close()


if __name__ == "__main__":
    main()
