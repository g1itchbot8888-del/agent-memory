#!/usr/bin/env python3
"""
Capture memories to agent-memory database.

Replaces the old file-based capture.py script.
Supports facts, decisions, preferences, and raw text.

Usage:
    python -m src.tools.capture "Some fact to remember"
    python -m src.tools.capture --facts "Fact 1" "Fact 2" "Fact 3"
    python -m src.tools.capture --decision "We chose X because Y"
    python -m src.tools.capture --preference "Bill likes concise answers"
    python -m src.tools.capture --type insight --salience 0.8 "Key insight here"
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from agent_memory.memory import Memory


def main():
    parser = argparse.ArgumentParser(description="Capture memories")
    parser.add_argument("content", nargs="*", help="Memory content")
    parser.add_argument("--db", default="agent_memory.db", help="Database path")
    parser.add_argument("--facts", nargs="+", help="Multiple facts to capture")
    parser.add_argument("--decision", help="Capture a decision")
    parser.add_argument("--preference", help="Capture a preference")
    parser.add_argument("--type", default="fact", help="Memory type")
    parser.add_argument("--salience", type=float, default=0.6, help="Importance 0-1")
    
    args = parser.parse_args()
    
    mem = Memory(args.db)
    captured = 0
    
    try:
        # Capture --facts
        if args.facts:
            for fact in args.facts:
                mem.add(fact, memory_type="fact", salience=args.salience)
                captured += 1
        
        # Capture --decision
        if args.decision:
            mem.add(args.decision, memory_type="decision", salience=0.8)
            captured += 1
        
        # Capture --preference
        if args.preference:
            mem.add(args.preference, memory_type="preference", salience=0.7)
            captured += 1
        
        # Capture positional content
        if args.content:
            content = " ".join(args.content)
            mem.add(content, memory_type=args.type, salience=args.salience)
            captured += 1
        
        if captured > 0:
            print(f"✓ Captured {captured} {'memory' if captured == 1 else 'memories'}")
        else:
            print("No content provided. Use --facts, --decision, --preference, or positional args.")
            parser.print_help()
    
    finally:
        mem.close()


if __name__ == "__main__":
    main()
