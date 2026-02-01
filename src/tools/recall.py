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
from src.memory import Memory


def main():
    parser = argparse.ArgumentParser(description="Recall memories")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--db", default="agent_memory.db", help="Database path")
    parser.add_argument("--limit", type=int, default=5, help="Max results")
    parser.add_argument("--min-salience", type=float, default=0.0, help="Minimum importance")
    parser.add_argument("--format", choices=["text", "json", "brief"], default="text")
    
    args = parser.parse_args()
    
    mem = Memory(args.db)
    
    try:
        results = mem.search(args.query, limit=args.limit, min_salience=args.min_salience)
        
        if not results:
            print("No matching memories found.")
            return
        
        if args.format == "json":
            import json
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
    
    finally:
        mem.close()


if __name__ == "__main__":
    main()
