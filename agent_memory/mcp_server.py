#!/usr/bin/env python3
"""
MCP (Model Context Protocol) server for agent-memory.

Exposes memory recall, capture, identity, and stats as MCP tools.
Any MCP-compatible client (Claude Desktop, Cursor, etc.) can use this.

Usage:
    python -m agent_memory.mcp_server --db ~/clawd/agent_memory.db
    
    # Or via the mcp CLI
    mcp run agent_memory/mcp_server.py -- --db ~/clawd/agent_memory.db
"""

import argparse
import json
import os
import sys
from typing import Optional

from mcp.server.fastmcp import FastMCP

# Ensure agent_memory is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_memory.memory import Memory
from agent_memory.learnings import LearningMachine
from agent_memory.consolidate import consolidate as run_consolidation

# --- Server setup ---

mcp = FastMCP(
    "agent-memory",
    instructions="Hierarchical memory system for autonomous agents with semantic recall, "
                 "auto-capture, and self-learning capabilities. Use recall() to search memories, "
                 "capture() to store new ones, and memory_stats() for an overview.",
)

# Global state — initialized on startup
_db_path: str = "agent_memory.db"


def _get_memory() -> Memory:
    """Get a Memory instance (creates fresh connection each time for thread safety)."""
    return Memory(_db_path)


def _get_learnings() -> LearningMachine:
    """Get a LearningMachine instance."""
    return LearningMachine(_db_path)


# --- Tools ---

@mcp.tool()
def recall(query: str, limit: int = 5, min_salience: float = 0.0, include_learnings: bool = True) -> str:
    """
    Search memories semantically. Returns the most relevant memories matching the query.
    
    Use this to find past decisions, preferences, facts, or any stored knowledge.
    Results are ranked by semantic similarity to the query.
    
    Args:
        query: Natural language search query (e.g., "what did we decide about pricing")
        limit: Maximum number of results to return (default: 5)
        min_salience: Minimum importance threshold 0.0-1.0 (default: 0.0)
        include_learnings: Whether to include relevant learnings from past mistakes (default: True)
    """
    mem = _get_memory()
    lm = _get_learnings()
    
    try:
        results = mem.search(query, limit=limit, min_salience=min_salience)
        
        if not results:
            output = "No matching memories found."
        else:
            lines = [f"Found {len(results)} relevant memories:\n"]
            for i, r in enumerate(results, 1):
                relevance = f"{r['relevance']:.2f}" if r.get('relevance') else "?"
                lines.append(f"{i}. [{r['type']}] (relevance: {relevance})")
                lines.append(f"   {r['content']}")
                if r.get('created_at'):
                    lines.append(f"   Created: {r['created_at'][:10]}")
                lines.append("")
            output = "\n".join(lines)
        
        # Include learnings
        if include_learnings:
            learnings_ctx = lm.format_context(query, limit=3)
            if learnings_ctx:
                output += "\n" + learnings_ctx
        
        return output
    finally:
        mem.close()
        lm.close()


@mcp.tool()
def capture(content: str, memory_type: str = "fact", salience: float = 0.6) -> str:
    """
    Store a new memory. Memories are embedded for semantic search.
    
    Use this to remember facts, decisions, preferences, insights, or any important information.
    
    Args:
        content: The memory content to store (natural language)
        memory_type: Type of memory — "fact", "decision", "preference", "insight", "event" (default: "fact")
        salience: Importance score 0.0-1.0 where 1.0 is critical (default: 0.6)
    """
    mem = _get_memory()
    try:
        mem.add(content, memory_type=memory_type, salience=salience)
        return f"Captured {memory_type}: {content[:100]}{'...' if len(content) > 100 else ''}"
    finally:
        mem.close()


@mcp.tool()
def capture_facts(facts: list[str], salience: float = 0.6) -> str:
    """
    Store multiple facts at once. Each fact is stored as a separate memory.
    
    Args:
        facts: List of fact strings to store
        salience: Importance score 0.0-1.0 for all facts (default: 0.6)
    """
    mem = _get_memory()
    try:
        for fact in facts:
            mem.add(fact, memory_type="fact", salience=salience)
        return f"Captured {len(facts)} facts"
    finally:
        mem.close()


@mcp.tool()
def capture_decision(decision: str, context: Optional[str] = None) -> str:
    """
    Record a decision that was made. Stored with higher salience since decisions shape behavior.
    
    Args:
        decision: The decision that was made (e.g., "We chose React over Vue for the frontend")
        context: Optional context about why the decision was made
    """
    mem = _get_memory()
    try:
        content = decision
        if context:
            content += f" (Context: {context})"
        mem.add(content, memory_type="decision", salience=0.8)
        return f"Captured decision: {decision[:100]}{'...' if len(decision) > 100 else ''}"
    finally:
        mem.close()


@mcp.tool()
def capture_preference(preference: str) -> str:
    """
    Record a user preference. These are surfaced when relevant.
    
    Args:
        preference: The preference to remember (e.g., "Bill prefers concise answers")
    """
    mem = _get_memory()
    try:
        mem.add(preference, memory_type="preference", salience=0.7)
        return f"Captured preference: {preference[:100]}{'...' if len(preference) > 100 else ''}"
    finally:
        mem.close()


@mcp.tool()
def record_learning(kind: str, trigger: str, learning: str, context: Optional[str] = None) -> str:
    """
    Record something learned from experience — a mistake, correction, or insight.
    
    These are surfaced during recall to prevent repeating mistakes.
    
    Args:
        kind: Type of learning — "error", "correction", "insight", "recall_hit", "recall_miss"
        trigger: What triggered this learning (the situation/context)
        learning: What was learned (the takeaway)
        context: Additional context (optional)
    """
    lm = _get_learnings()
    try:
        lm.record(kind=kind, trigger=trigger, learning=learning, context=context)
        return f"Recorded {kind}: {learning[:100]}{'...' if len(learning) > 100 else ''}"
    finally:
        lm.close()


@mcp.tool()
def get_identity() -> str:
    """
    Get the agent's identity context — core self-knowledge that's always relevant.
    Returns all identity key-value pairs.
    """
    mem = _get_memory()
    try:
        return mem.get_identity_context() or "No identity set."
    finally:
        mem.close()


@mcp.tool()
def set_identity(key: str, value: str) -> str:
    """
    Set an identity fact about the agent. Identity memories are always loaded.
    
    Args:
        key: Identity key (e.g., "name", "human_name", "born", "personality")
        value: The value to store
    """
    mem = _get_memory()
    try:
        mem.set_identity(key, value)
        return f"Identity set: {key} = {value}"
    finally:
        mem.close()


@mcp.tool()
def get_active_context() -> str:
    """
    Get the active context — current task and hot working memory.
    This is the agent's "RAM" of what it's doing right now.
    """
    mem = _get_memory()
    try:
        return mem.get_active_context() or "No active context set."
    finally:
        mem.close()


@mcp.tool()
def set_active(key: str, value: str) -> str:
    """
    Set active context — current task state, working memory.
    
    Args:
        key: Active context key (e.g., "current_task", "waiting_on", "next_step")
        value: The value to store
    """
    mem = _get_memory()
    try:
        mem.set_active(key, value)
        return f"Active context set: {key} = {value}"
    finally:
        mem.close()


@mcp.tool()
def get_startup_context() -> str:
    """
    Get the full startup context — identity + active + surfaced memories.
    Useful for session initialization, gives the agent a complete picture of who it is
    and what it's working on.
    """
    mem = _get_memory()
    try:
        return mem.get_startup_context()
    finally:
        mem.close()


@mcp.tool()
def memory_stats() -> str:
    """
    Get statistics about the memory database — total memories, types, layers, learnings.
    """
    mem = _get_memory()
    lm = _get_learnings()
    try:
        mem_stats = mem.stats()
        learn_stats = lm.stats()
        
        output = "Memory Statistics:\n"
        output += f"  Total memories: {mem_stats.get('total_memories', 0)}\n"
        
        by_type = mem_stats.get('by_type', {})
        if by_type:
            output += "  By type:\n"
            for t, count in sorted(by_type.items()):
                output += f"    {t}: {count}\n"
        
        by_layer = mem_stats.get('by_layer', {})
        if by_layer:
            output += "  By layer:\n"
            for l, count in sorted(by_layer.items()):
                output += f"    {l}: {count}\n"
        
        output += f"\nLearning Statistics:\n"
        output += f"  Total learnings: {learn_stats.get('total', 0)}\n"
        by_kind = learn_stats.get('by_kind', {})
        if by_kind:
            output += "  By kind:\n"
            for k, count in sorted(by_kind.items()):
                output += f"    {k}: {count}\n"
        
        return output
    finally:
        mem.close()
        lm.close()


@mcp.tool()
def graph_stats() -> str:
    """
    Get statistics about the memory graph — relationships, superseded memories, temporal memories.
    """
    mem = _get_memory()
    try:
        from agent_memory.graph import GraphMemory
        graph = GraphMemory(mem.conn)
        stats = graph.stats()
        
        output = "Graph Statistics:\n"
        output += f"  Total edges: {stats.get('total_edges', 0)}\n"
        
        by_rel = stats.get('by_relation', {})
        if by_rel:
            output += "  By relation:\n"
            for r, count in sorted(by_rel.items()):
                output += f"    {r}: {count}\n"
        
        output += f"  Superseded memories: {stats.get('superseded_memories', 0)}\n"
        output += f"  Temporal memories: {stats.get('temporal_memories', 0)}\n"
        output += f"  Avg confidence: {stats.get('avg_confidence', 0):.3f}\n"
        return output
    except Exception as e:
        return f"Graph not available: {e}"
    finally:
        mem.close()


@mcp.tool()
def get_memory_graph(memory_id: int) -> str:
    """
    Get the graph relationships for a specific memory — what it updates, extends, or derives from.
    
    Args:
        memory_id: The memory ID to look up relationships for
    """
    mem = _get_memory()
    try:
        from agent_memory.graph import GraphMemory
        graph = GraphMemory(mem.conn)
        edges = graph.get_edges(memory_id)
        
        if not edges:
            return f"Memory {memory_id} has no graph relationships."
        
        output = f"Relationships for memory {memory_id}:\n"
        for e in edges:
            direction = "→" if e['direction'] == 'out' else "←"
            other_id = e['target_id'] if e['direction'] == 'out' else e['source_id']
            output += f"  {direction} {e['relation']} memory {other_id} (confidence: {e['confidence']:.3f})\n"
            output += f"    {e['connected_content']}\n"
        
        return output
    except Exception as e:
        return f"Graph not available: {e}"
    finally:
        mem.close()


@mcp.tool()
def consolidate(dry_run: bool = True) -> str:
    """
    Run memory consolidation — merges similar memories and prunes low-value ones.
    
    Args:
        dry_run: If True, show what would happen without making changes (default: True)
    """
    result = run_consolidation(_db_path, dry_run=dry_run)
    
    output = f"Consolidation {'(DRY RUN)' if dry_run else 'COMPLETE'}:\n"
    output += f"  Pruned: {result.pruned}\n"
    output += f"  Merged: {result.merged}\n"
    if dry_run:
        output += "\nRun with dry_run=False to apply changes."
    return output


# --- Resources (read-only context) ---

@mcp.resource("memory://stats")
def resource_stats() -> str:
    """Current memory statistics."""
    return memory_stats()


@mcp.resource("memory://identity")
def resource_identity() -> str:
    """Agent identity context."""
    mem = _get_memory()
    try:
        return mem.get_identity_context() or "No identity set."
    finally:
        mem.close()


@mcp.resource("memory://startup")
def resource_startup() -> str:
    """Full startup context for session initialization."""
    mem = _get_memory()
    try:
        return mem.get_startup_context()
    finally:
        mem.close()


# --- Entrypoint ---

def main():
    global _db_path
    
    parser = argparse.ArgumentParser(description="agent-memory MCP server")
    parser.add_argument("--db", default="agent_memory.db", help="Path to memory database")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio",
                        help="MCP transport (default: stdio)")
    parser.add_argument("--host", default="0.0.0.0", help="Host for SSE transport")
    parser.add_argument("--port", type=int, default=8765, help="Port for SSE transport")
    
    args = parser.parse_args()
    _db_path = args.db
    
    # Validate DB exists or can be created
    db_dir = os.path.dirname(os.path.abspath(_db_path))
    if not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    
    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="sse", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
