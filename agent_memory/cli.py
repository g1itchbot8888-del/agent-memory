#!/usr/bin/env python3
"""
Main CLI entry point for agent-memory.

Usage:
    agent-memory bootstrap ~/workspace
    agent-memory recall "what did we decide"
    agent-memory capture --facts "fact1" "fact2"
    agent-memory startup
    agent-memory export -o backup.json
    agent-memory benchmark
"""

import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Memory system for autonomous agents",
        prog="agent-memory"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Bootstrap
    boot = subparsers.add_parser("bootstrap", help="Bootstrap from workspace")
    boot.add_argument("workspace", help="Path to workspace")
    boot.add_argument("--db", default="agent_memory.db", help="Database name")
    boot.add_argument("--force", action="store_true", help="Overwrite existing")
    
    # Recall
    recall = subparsers.add_parser("recall", help="Semantic search")
    recall.add_argument("query", help="Search query")
    recall.add_argument("--db", default="agent_memory.db", help="Database path")
    recall.add_argument("--limit", type=int, default=5, help="Max results")
    
    # Capture
    capture = subparsers.add_parser("capture", help="Capture memories")
    capture.add_argument("content", nargs="*", help="Content to capture")
    capture.add_argument("--db", default="agent_memory.db", help="Database path")
    capture.add_argument("--facts", nargs="+", help="Facts to capture")
    capture.add_argument("--decision", help="Decision to capture")
    
    # Startup
    startup = subparsers.add_parser("startup", help="Generate startup context")
    startup.add_argument("--db", default="agent_memory.db", help="Database path")
    startup.add_argument("--output", "-o", help="Output file")
    
    # Export
    export = subparsers.add_parser("export", help="Export to JSON")
    export.add_argument("--db", default="agent_memory.db", help="Database path")
    export.add_argument("--output", "-o", required=True, help="Output file")
    
    # Import
    imp = subparsers.add_parser("import", help="Import from JSON")
    imp.add_argument("--db", default="agent_memory.db", help="Database path")
    imp.add_argument("--input", "-i", required=True, help="Input file")
    
    # Benchmark
    bench = subparsers.add_parser("benchmark", help="Run benchmark")
    bench.add_argument("--db", required=True, help="Database path")
    bench.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    # Stats
    stats = subparsers.add_parser("stats", help="Show statistics")
    stats.add_argument("--db", default="agent_memory.db", help="Database path")
    
    # Setup
    setup = subparsers.add_parser("setup", help="Configure for an agent")
    setup.add_argument("agent", nargs="?", choices=["openclaw", "claude-code", "opencode", "cursor"],
                       help="Agent to configure for")
    setup.add_argument("--db", default="~/agent_memory.db", help="Database path")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Route to appropriate module
    if args.command == "bootstrap":
        from agent_memory.bootstrap import main as bootstrap_main
        sys.argv = ["bootstrap", args.workspace, "--db", args.db]
        if args.force:
            sys.argv.append("--force")
        bootstrap_main()
    
    elif args.command == "recall":
        from agent_memory.tools.recall import main as recall_main
        sys.argv = ["recall", args.query, "--db", args.db, "--limit", str(args.limit)]
        recall_main()
    
    elif args.command == "capture":
        from agent_memory.tools.capture import main as capture_main
        sys.argv = ["capture", "--db", args.db]
        if args.facts:
            sys.argv.extend(["--facts"] + args.facts)
        if args.decision:
            sys.argv.extend(["--decision", args.decision])
        if args.content:
            sys.argv.extend(args.content)
        capture_main()
    
    elif args.command == "startup":
        from agent_memory.hooks.startup_hook import main as startup_main
        sys.argv = ["startup", "--db", args.db]
        if args.output:
            sys.argv.extend(["--output", args.output])
        startup_main()
    
    elif args.command == "export":
        from agent_memory.tools.export_import import main as export_main
        sys.argv = ["export_import", "export", "--db", args.db, "--output", args.output]
        export_main()
    
    elif args.command == "import":
        from agent_memory.tools.export_import import main as import_main
        sys.argv = ["export_import", "import", "--db", args.db, "--input", args.input]
        import_main()
    
    elif args.command == "benchmark":
        from agent_memory.benchmarks.run import main as bench_main
        sys.argv = ["benchmark", "--db", args.db]
        if args.verbose:
            sys.argv.append("-v")
        bench_main()
    
    elif args.command == "stats":
        from agent_memory.memory import Memory
        mem = Memory(args.db)
        s = mem.stats()
        print(f"Memories: {s['memories']}")
        print(f"Identity keys: {s['identity_keys']}")
        print(f"Active context: {s['active_keys']}")
        print(f"Embeddings: {'✓' if s['embeddings_available'] else '✗'}")
        print(f"Vector search: {'✓' if s['vector_search_available'] else '✗'}")
        mem.close()
    
    elif args.command == "setup":
        _run_setup(args.agent, args.db)


def _run_setup(agent: str | None, db_path: str):
    """Configure agent-memory for a specific agent."""
    import json
    
    agents = {
        "openclaw": {
            "config_path": "~/.openclaw/config.json",
            "mcp_key": "mcp.servers",
        },
        "claude-code": {
            "config_path": "~/.claude/settings.json",
            "mcp_key": "mcpServers",
        },
        "opencode": {
            "config_path": "~/.opencode/config.json",
            "mcp_key": "mcp.servers",
        },
        "cursor": {
            "config_path": "~/.cursor/mcp.json",
            "mcp_key": "mcpServers",
        },
    }
    
    if not agent:
        print("Available agents:")
        for name in agents:
            print(f"  agent-memory setup {name}")
        print("\nOr run interactively:")
        agent = input("Which agent? [openclaw/claude-code/opencode/cursor]: ").strip().lower()
        if agent not in agents:
            print(f"Unknown agent: {agent}")
            return
    
    cfg = agents[agent]
    config_path = Path(cfg["config_path"]).expanduser()
    db_expanded = Path(db_path).expanduser()
    
    mcp_config = {
        "agent-memory": {
            "command": "agent-memory-mcp",
            "args": ["--db", str(db_expanded)],
        }
    }
    
    print(f"\n🧠 agent-memory setup for {agent}")
    print(f"   Database: {db_expanded}")
    print(f"   Config: {config_path}")
    print()
    
    if config_path.exists():
        try:
            with open(config_path) as f:
                existing = json.load(f)
        except:
            existing = {}
    else:
        existing = {}
        config_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Navigate to the mcp servers key
    keys = cfg["mcp_key"].split(".")
    target = existing
    for key in keys[:-1]:
        if key not in target:
            target[key] = {}
        target = target[key]
    
    if keys[-1] not in target:
        target[keys[-1]] = {}
    target[keys[-1]]["agent-memory"] = mcp_config["agent-memory"]
    
    with open(config_path, "w") as f:
        json.dump(existing, f, indent=2)
    
    print("✅ MCP server configured!")
    print()
    print("The agent-memory MCP server provides these tools:")
    print("  - memory_recall: Search memories semantically")
    print("  - memory_capture: Store new memories")
    print("  - memory_startup: Get identity + active context")
    print()
    print(f"Restart {agent} to activate.")


if __name__ == "__main__":
    main()
