#!/usr/bin/env python3
"""
OpenClaw startup hook for agent-memory.

Generates startup context from the memory database.
Can be called by OpenClaw on session start to auto-inject context.

Usage:
    # Generate context to stdout (for piping)
    python -m src.hooks.startup_hook --db agent_memory.db
    
    # Write to file for OpenClaw to read
    python -m src.hooks.startup_hook --db agent_memory.db --output MEMORY_CONTEXT.md
    
    # Include recent relevant memories
    python -m src.hooks.startup_hook --db agent_memory.db --surface "current context"
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from agent_memory.memory import Memory
from agent_memory.surface import MemorySurfacer


def generate_startup_context(db_path: str, surface_query: str = None, max_memories: int = 3) -> str:
    """
    Generate startup context from memory database.
    
    Args:
        db_path: Path to memory database
        surface_query: Optional query to surface relevant memories
        max_memories: Max memories to surface
    
    Returns:
        Formatted context string for injection
    """
    mem = Memory(db_path)
    surfacer = MemorySurfacer(mem)
    
    sections = []
    
    # Identity (always include)
    identity = mem.get_identity()
    if identity:
        identity_lines = ["## Identity"]
        for key, value in identity.items():
            if key == 'soul':
                # Truncate soul to key points
                soul_preview = value[:500] + "..." if len(value) > 500 else value
                identity_lines.append(f"**Core self:** {soul_preview}")
            else:
                identity_lines.append(f"- **{key}:** {value}")
        sections.append("\n".join(identity_lines))
    
    # Active context (current task/project)
    active = mem.get_active()
    if active:
        active_lines = ["## Active Context"]
        for key, value in active.items():
            if key == 'session_state':
                # Truncate long session state
                preview = value[:300] + "..." if len(value) > 300 else value
                active_lines.append(f"**Session:** {preview}")
            else:
                active_lines.append(f"- **{key}:** {value}")
        sections.append("\n".join(active_lines))
    
    # Surface relevant memories if query provided
    if surface_query:
        surfaced = surfacer.surface(surface_query, limit=max_memories)
        if surfaced:
            memory_lines = ["## Recent Relevant Memories"]
            for s in surfaced:
                memory_lines.append(f"- [{s.memory_type}] {s.content[:100]}...")
            sections.append("\n".join(memory_lines))
    
    # Stats footer
    stats = mem.stats()
    sections.append(f"_Memory: {stats['memories']} total | Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_")
    
    mem.close()
    
    # Combine with header
    header = "# Memory Context (Auto-Injected)"
    return header + "\n\n" + "\n\n".join(sections)


def main():
    parser = argparse.ArgumentParser(description="Generate startup context from agent-memory")
    parser.add_argument("--db", required=True, help="Path to memory database")
    parser.add_argument("--output", "-o", help="Write to file instead of stdout")
    parser.add_argument("--surface", help="Query to surface relevant memories")
    parser.add_argument("--max-memories", type=int, default=3, help="Max memories to surface")
    
    args = parser.parse_args()
    
    context = generate_startup_context(
        args.db, 
        surface_query=args.surface,
        max_memories=args.max_memories
    )
    
    if args.output:
        Path(args.output).write_text(context)
        print(f"✓ Wrote startup context to {args.output}")
    else:
        print(context)


if __name__ == "__main__":
    main()
