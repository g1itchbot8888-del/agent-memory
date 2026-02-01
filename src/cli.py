#!/usr/bin/env python3
"""
CLI for agent-memory system.

Usage:
    python -m src.cli identity set name "g1itchbot"
    python -m src.cli identity get
    python -m src.cli active set task "Building memory system"
    python -m src.cli add "Bill wants to build best-in-class memory"
    python -m src.cli search "memory system"
    python -m src.cli startup
    python -m src.cli stats
"""

import argparse
import json
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.memory import Memory


def main():
    parser = argparse.ArgumentParser(description="Agent Memory CLI")
    parser.add_argument("--db", default="memory.db", help="Database path")
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Identity commands
    identity_parser = subparsers.add_parser("identity", help="Manage identity")
    identity_sub = identity_parser.add_subparsers(dest="action")
    
    id_set = identity_sub.add_parser("set", help="Set identity key")
    id_set.add_argument("key", help="Key name")
    id_set.add_argument("value", help="Value")
    
    id_get = identity_sub.add_parser("get", help="Get identity")
    id_get.add_argument("key", nargs="?", help="Specific key (optional)")
    
    # Active context commands
    active_parser = subparsers.add_parser("active", help="Manage active context")
    active_sub = active_parser.add_subparsers(dest="action")
    
    act_set = active_sub.add_parser("set", help="Set active context")
    act_set.add_argument("key", help="Key name")
    act_set.add_argument("value", help="Value")
    
    act_get = active_sub.add_parser("get", help="Get active context")
    act_get.add_argument("key", nargs="?", help="Specific key (optional)")
    
    # Add memory
    add_parser = subparsers.add_parser("add", help="Add a memory")
    add_parser.add_argument("content", help="Memory content")
    add_parser.add_argument("--type", default="fact", help="Memory type")
    add_parser.add_argument("--salience", type=float, default=0.5, help="Importance 0-1")
    
    # Search memories
    search_parser = subparsers.add_parser("search", help="Search memories")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--limit", type=int, default=5, help="Max results")
    
    # Startup context
    subparsers.add_parser("startup", help="Get startup context")
    
    # Stats
    subparsers.add_parser("stats", help="Get memory statistics")
    
    # Surface relevant
    surface_parser = subparsers.add_parser("surface", help="Surface relevant memories")
    surface_parser.add_argument("context", help="Current context")
    surface_parser.add_argument("--limit", type=int, default=3, help="Max results")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    mem = Memory(args.db)
    
    try:
        if args.command == "identity":
            if args.action == "set":
                mem.set_identity(args.key, args.value)
                print(f"✓ Set identity.{args.key} = {args.value}")
            elif args.action == "get":
                result = mem.get_identity(args.key if hasattr(args, 'key') else None)
                if result:
                    for k, v in result.items():
                        print(f"{k}: {v}")
                else:
                    print("(no identity set)")
        
        elif args.command == "active":
            if args.action == "set":
                mem.set_active(args.key, args.value)
                print(f"✓ Set active.{args.key}")
            elif args.action == "get":
                result = mem.get_active(args.key if hasattr(args, 'key') else None)
                if result:
                    for k, v in result.items():
                        print(f"## {k}\n{v}\n")
                else:
                    print("(no active context)")
        
        elif args.command == "add":
            memory_id = mem.add(args.content, memory_type=args.type, salience=args.salience)
            print(f"✓ Added memory #{memory_id}")
        
        elif args.command == "search":
            results = mem.search(args.query, limit=args.limit)
            if results:
                for r in results:
                    relevance = f"{r['relevance']:.2f}" if r['relevance'] else "?"
                    print(f"[{r['type']}] (rel:{relevance}) {r['content']}")
            else:
                print("(no matching memories)")
        
        elif args.command == "startup":
            context = mem.get_startup_context()
            if context:
                print(context)
            else:
                print("(no startup context)")
        
        elif args.command == "stats":
            stats = mem.stats()
            print(json.dumps(stats, indent=2))
        
        elif args.command == "surface":
            relevant = mem.surface_relevant(args.context, limit=args.limit)
            if relevant:
                print(relevant)
            else:
                print("(no relevant memories)")
    
    finally:
        mem.close()


if __name__ == "__main__":
    main()
