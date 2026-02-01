#!/usr/bin/env python3
"""
Auto-capture memories from conversation text.

Uses heuristic extraction to find decisions, preferences, insights, and goals.
No manual tagging required.

Usage:
    python -m src.tools.auto_capture "conversation text here"
    echo "conversation" | python -m src.tools.auto_capture --stdin
    python -m src.tools.auto_capture --file conversation.txt
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.memory import Memory
from src.extract import extract_memories


def main():
    parser = argparse.ArgumentParser(description="Auto-capture memories from text")
    parser.add_argument("text", nargs="*", help="Text to extract from")
    parser.add_argument("--db", default="agent_memory.db", help="Database path")
    parser.add_argument("--stdin", action="store_true", help="Read from stdin")
    parser.add_argument("--file", help="Read from file")
    parser.add_argument("--min-confidence", type=float, default=0.5, help="Min extraction confidence")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be captured")
    
    args = parser.parse_args()
    
    # Get text to process
    if args.stdin:
        text = sys.stdin.read()
    elif args.file:
        text = Path(args.file).read_text()
    elif args.text:
        text = " ".join(args.text)
    else:
        print("No text provided. Use --stdin, --file, or positional args.")
        parser.print_help()
        return
    
    # Extract memories
    memories = extract_memories(text, min_confidence=args.min_confidence)
    
    if not memories:
        print("No significant memories found in text.")
        return
    
    if args.dry_run:
        print(f"Would capture {len(memories)} memories:\n")
        for mem in memories:
            print(f"[{mem.memory_type}] (salience: {mem.salience})")
            print(f"  {mem.content}\n")
        return
    
    # Save to database
    mem = Memory(args.db)
    try:
        for extracted in memories:
            mem.add(
                extracted.content,
                memory_type=extracted.memory_type,
                salience=extracted.salience
            )
        print(f"✓ Auto-captured {len(memories)} memories")
        for m in memories:
            print(f"  [{m.memory_type}] {m.content[:60]}...")
    finally:
        mem.close()


if __name__ == "__main__":
    main()
