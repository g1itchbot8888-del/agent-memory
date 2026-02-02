#!/usr/bin/env python3
"""
OpenClaw startup hook for agent-memory.

Generates startup context from the memory database AND live workspace files.
Can be called by OpenClaw on session start to auto-inject context.

Usage:
    # Generate context with workspace files
    python -m agent_memory.hooks.startup_hook --db agent_memory.db --workspace ~/clawd
    
    # Write to file for OpenClaw to read
    python -m agent_memory.hooks.startup_hook --db agent_memory.db --workspace ~/clawd --output MEMORY_CONTEXT.md
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from agent_memory.memory import Memory
from agent_memory.surface import MemorySurfacer


def read_workspace_file(workspace: Path, filename: str, max_chars: int = 2000) -> str:
    """Read a workspace file, truncating if needed."""
    filepath = workspace / filename
    if not filepath.exists():
        return None
    content = filepath.read_text()
    if len(content) > max_chars:
        return content[:max_chars] + "\n...(truncated)"
    return content


def generate_startup_context(
    db_path: str, 
    workspace: str = None,
    surface_query: str = None, 
    max_memories: int = 3
) -> str:
    """
    Generate startup context from memory database AND live workspace files.
    
    Args:
        db_path: Path to memory database
        workspace: Path to workspace (for reading SESSION-STATE.md, etc.)
        surface_query: Optional query to surface relevant memories
        max_memories: Max memories to surface
    
    Returns:
        Formatted context string for injection
    """
    mem = Memory(db_path)
    surfacer = MemorySurfacer(mem)
    workspace_path = Path(workspace).expanduser() if workspace else None
    
    sections = []
    
    # Identity (from database)
    identity = mem.get_identity()
    if identity:
        identity_lines = ["## Identity"]
        for key, value in identity.items():
            if key == 'soul':
                soul_preview = value[:500] + "..." if len(value) > 500 else value
                identity_lines.append(f"**Core self:** {soul_preview}")
            else:
                identity_lines.append(f"- **{key}:** {value}")
        sections.append("\n".join(identity_lines))
    
    # Active context - READ DIRECTLY FROM FILES (not database!)
    active_lines = ["## Active Context"]
    
    if workspace_path:
        # Read SESSION-STATE.md directly (hot context, always fresh)
        session_state = read_workspace_file(workspace_path, "SESSION-STATE.md", max_chars=1500)
        if session_state:
            active_lines.append(f"**Session State (live):**\n{session_state}")
        
        # Read RECENT_CONTEXT.md if it exists
        recent_context = read_workspace_file(workspace_path, "RECENT_CONTEXT.md", max_chars=1000)
        if recent_context:
            active_lines.append(f"\n**Recent Context (live):**\n{recent_context}")
    
    # Fall back to database if no workspace files
    if len(active_lines) == 1:  # Only header, no content
        active = mem.get_active()
        if active:
            for key, value in active.items():
                preview = value[:300] + "..." if len(value) > 300 else value
                active_lines.append(f"- **{key}:** {preview}")
    
    if len(active_lines) > 1:
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
    
    header = "# Memory Context (Auto-Injected)"
    return header + "\n\n" + "\n\n".join(sections)


def main():
    parser = argparse.ArgumentParser(description="Generate startup context from agent-memory")
    parser.add_argument("--db", required=True, help="Path to memory database")
    parser.add_argument("--workspace", "-w", help="Path to workspace (reads SESSION-STATE.md directly)")
    parser.add_argument("--output", "-o", help="Write to file instead of stdout")
    parser.add_argument("--surface", help="Query to surface relevant memories")
    parser.add_argument("--max-memories", type=int, default=3, help="Max memories to surface")
    
    args = parser.parse_args()
    
    context = generate_startup_context(
        args.db,
        workspace=args.workspace,
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
