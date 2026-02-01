#!/usr/bin/env python3
"""
Generate startup context from agent-memory database.

This replaces reading multiple files on startup.
Output can be injected into system prompt or context.

Usage:
    python -m src.tools.startup
    python -m src.tools.startup --db /path/to/memory.db
    python -m src.tools.startup --format json
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.memory import Memory


def main():
    parser = argparse.ArgumentParser(description="Generate startup context")
    parser.add_argument("--db", default="agent_memory.db", help="Database path")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--max-tokens", type=int, default=1000, help="Max approximate tokens")
    
    args = parser.parse_args()
    
    mem = Memory(args.db)
    
    context = mem.get_startup_context()
    
    if args.format == "json":
        output = {
            "identity": mem.get_identity(),
            "active": mem.get_active(),
            "startup_context": context,
            "stats": mem.stats()
        }
        print(json.dumps(output, indent=2))
    else:
        print(context)
    
    mem.close()


if __name__ == "__main__":
    main()
