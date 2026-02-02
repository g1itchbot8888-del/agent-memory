#!/usr/bin/env python3
"""
Bootstrap script to initialize agent-memory from existing OpenClaw workspace.

Reads current files (SOUL.md, IDENTITY.md, USER.md, SESSION-STATE.md, MEMORY.md)
and populates the new memory database.

Usage:
    python -m src.bootstrap /path/to/workspace
    python -m src.bootstrap  # Uses current directory
"""

import argparse
import re
import sys
from pathlib import Path
from datetime import datetime

from agent_memory.memory import Memory


def parse_markdown_keyvalues(content: str) -> dict:
    """Extract key-value pairs from markdown like '- **Key:** Value'"""
    result = {}
    for line in content.split('\n'):
        # Match patterns like "- **Name:** g1itchbot" or "**Name:** g1itchbot"
        match = re.match(r'^[-*]*\s*\*\*([^*:]+)\*\*:?\s*(.+)$', line.strip())
        if match:
            key = match.group(1).strip().lower().replace(' ', '_')
            value = match.group(2).strip()
            result[key] = value
    return result


def extract_facts_from_memory(content: str) -> list:
    """Extract individual facts from MEMORY.md or daily memory files."""
    facts = []
    current_section = None
    
    for line in content.split('\n'):
        line = line.strip()
        
        # Track sections
        if line.startswith('## '):
            current_section = line[3:].strip()
            continue
        
        # Extract bullet points as facts
        if line.startswith('- ') and len(line) > 10:
            fact = line[2:].strip()
            if current_section:
                fact = f"[{current_section}] {fact}"
            facts.append(fact)
    
    return facts


def bootstrap_identity(mem: Memory, workspace: Path):
    """Bootstrap identity from IDENTITY.md, SOUL.md, USER.md"""
    
    # IDENTITY.md
    identity_file = workspace / "IDENTITY.md"
    if identity_file.exists():
        print(f"  Reading {identity_file.name}...")
        content = identity_file.read_text()
        pairs = parse_markdown_keyvalues(content)
        for key, value in pairs.items():
            mem.set_identity(key, value)
            print(f"    + identity.{key}")
    
    # SOUL.md - extract key personality traits
    soul_file = workspace / "SOUL.md"
    if soul_file.exists():
        print(f"  Reading {soul_file.name}...")
        content = soul_file.read_text()
        # Store full soul as identity
        mem.set_identity("soul", content[:2000])  # Limit size
        print(f"    + identity.soul (truncated)")
    
    # USER.md
    user_file = workspace / "USER.md"
    if user_file.exists():
        print(f"  Reading {user_file.name}...")
        content = user_file.read_text()
        pairs = parse_markdown_keyvalues(content)
        for key, value in pairs.items():
            mem.set_identity(f"human_{key}", value)
            print(f"    + identity.human_{key}")


def bootstrap_active(mem: Memory, workspace: Path):
    """Bootstrap active context from SESSION-STATE.md"""
    
    session_file = workspace / "SESSION-STATE.md"
    if session_file.exists():
        print(f"  Reading {session_file.name}...")
        content = session_file.read_text()
        
        # Store full session state
        mem.set_active("session_state", content[:3000])
        print(f"    + active.session_state")
        
        # Try to extract current task
        for line in content.split('\n'):
            if 'ACTIVE PROJECT' in line or 'Current Task' in line:
                mem.set_active("current_task", line)
                print(f"    + active.current_task")
                break


def bootstrap_memories(mem: Memory, workspace: Path):
    """Bootstrap archive from MEMORY.md and daily files."""
    
    imported = 0
    
    # MEMORY.md - long-term memories
    memory_file = workspace / "MEMORY.md"
    if memory_file.exists():
        print(f"  Reading {memory_file.name}...")
        content = memory_file.read_text()
        facts = extract_facts_from_memory(content)
        for fact in facts:
            mem.add(fact, memory_type="long_term", salience=0.7)
            imported += 1
        print(f"    + {len(facts)} long-term memories")
    
    # memory/*.md - daily files
    memory_dir = workspace / "memory"
    if memory_dir.exists():
        daily_files = sorted(memory_dir.glob("*.md"))
        for daily_file in daily_files[-7:]:  # Last 7 days
            print(f"  Reading {daily_file.name}...")
            content = daily_file.read_text()
            facts = extract_facts_from_memory(content)
            
            # Extract date from filename for metadata
            date_str = daily_file.stem  # e.g., "2026-02-01"
            
            for fact in facts:
                mem.add(fact, memory_type="daily", salience=0.5, 
                       metadata={"date": date_str})
                imported += 1
            print(f"    + {len(facts)} daily facts")
    
    return imported


def main():
    parser = argparse.ArgumentParser(description="Bootstrap agent-memory from OpenClaw workspace")
    parser.add_argument("workspace", nargs="?", default=".", help="Path to workspace")
    parser.add_argument("--db", default="agent_memory.db", help="Output database name")
    parser.add_argument("--force", action="store_true", help="Overwrite existing database")
    
    args = parser.parse_args()
    workspace = Path(args.workspace).resolve()
    db_path = workspace / args.db
    
    print(f"Bootstrapping from: {workspace}")
    print(f"Database: {db_path}")
    print()
    
    if db_path.exists() and not args.force:
        print(f"Database already exists. Use --force to overwrite.")
        sys.exit(1)
    
    if db_path.exists():
        db_path.unlink()
    
    mem = Memory(str(db_path))
    
    print("1. Importing identity...")
    bootstrap_identity(mem, workspace)
    
    print("\n2. Importing active context...")
    bootstrap_active(mem, workspace)
    
    print("\n3. Importing memories...")
    total_memories = bootstrap_memories(mem, workspace)
    
    print("\n" + "="*50)
    print("Bootstrap complete!")
    print(f"Stats: {mem.stats()}")
    print()
    print("Startup context preview:")
    print("-" * 30)
    context = mem.get_startup_context()
    print(context[:500] + "..." if len(context) > 500 else context)
    
    mem.close()


if __name__ == "__main__":
    main()
