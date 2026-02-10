"""
OpenClaw Startup Hook - Phase 6 Predictive Surfacing

Call this at agent startup to automatically load relevant memories.

Usage:
    from agent_memory.startup_hook import get_session_context
    
    context = get_session_context(workspace="/path/to/workspace")
    print(context)  # Insert into system prompt or session context
"""

from pathlib import Path
from typing import Optional
from agent_memory.openclaw import OpenClawMemory
from agent_memory.surface import MemorySurfacer


def get_session_context(
    workspace: str = ".",
    db_name: str = "agent-memory.db",
    include_startup: bool = True,
    include_identity: bool = True,
    verbose: bool = False
) -> str:
    """
    Get complete session context with Phase 6 predictive surfacing.
    
    Call at agent startup to pre-load relevant memories before
    processing user messages.
    
    Args:
        workspace: Path to agent workspace
        db_name: Memory database name
        include_startup: Load startup context (active task + recent decisions)
        include_identity: Include identity information
        verbose: Show confidence scores and tags
    
    Returns:
        Formatted markdown string ready to inject into system prompt
    """
    oclaw = OpenClawMemory(workspace, db_name)
    
    sections = []
    
    # 1. Identity (always loaded in core system, but include for clarity)
    if include_identity:
        identity = oclaw.mem.get_identity()
        if identity:
            sections.append("# Identity Context")
            for key, value in list(identity.items())[:3]:  # Top 3
                sections.append(f"- {key}: {value[:100]}")
            sections.append("")
    
    # 2. Phase 6: Predictive Startup Context
    if include_startup:
        startup = oclaw.surface_for_startup()
        if startup:
            sections.append(startup)
        else:
            sections.append("# Session Context\nNo active task or recent decisions.")
        sections.append("")
    
    return "\n".join(sections)


def inject_into_system_prompt(
    base_prompt: str,
    workspace: str = ".",
    **kwargs
) -> str:
    """
    Inject predictive context into existing system prompt.
    
    Usage:
        system_prompt = "You are Nyx..."
        enhanced = inject_into_system_prompt(system_prompt, workspace="/path")
        # Returns: system_prompt + "\n\n# Current Context\n..." + predictive_surfacing
    """
    context = get_session_context(workspace, **kwargs)
    
    if context.strip():
        return f"{base_prompt}\n\n## Current Session Context (Predictively Loaded)\n\n{context}"
    else:
        return base_prompt


def test_startup_hook():
    """Quick test of startup hook integration."""
    import sys
    
    print("Testing startup hook...\n")
    
    try:
        context = get_session_context(
            workspace="/home/nyx/.openclaw/workspace",
            verbose=True
        )
        
        if context:
            print("✅ Startup context loaded:")
            print("-" * 70)
            print(context)
            print("-" * 70)
            print(f"✅ Context size: {len(context)} characters")
        else:
            print("⚠️ No context loaded (empty database or no active task)")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    test_startup_hook()
