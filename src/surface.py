"""
Predictive memory surfacing.

Anticipates what memories are relevant based on:
- Current conversation context
- Active task
- Mentioned entities (people, projects, topics)
- Temporal cues ("yesterday", "last week")

Returns memories that should be loaded into context
without explicit search queries.
"""

import re
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Set
from dataclasses import dataclass

from .memory import Memory


@dataclass
class SurfacedMemory:
    """A memory surfaced by prediction."""
    id: int
    content: str
    memory_type: str
    relevance: float
    reason: str  # Why it was surfaced


class MemorySurfacer:
    """
    Predicts and surfaces relevant memories.
    
    Strategies:
    1. Entity extraction: Find mentioned people, projects, topics
    2. Temporal cues: "yesterday" → recent memories
    3. Context similarity: Semantically similar to current context
    4. Active task: Always surface task-related memories
    """
    
    # Entity patterns
    PERSON_PATTERNS = [
        r'\b([A-Z][a-z]+)\s+(?:said|wants|asked|mentioned|prefers)',
        r'(?:with|from|to)\s+([A-Z][a-z]+)\b',
    ]
    
    # Temporal patterns
    TEMPORAL_PATTERNS = {
        'yesterday': timedelta(days=1),
        'last week': timedelta(days=7),
        'last month': timedelta(days=30),
        'recently': timedelta(days=3),
        'today': timedelta(days=0),
        'earlier': timedelta(hours=6),
    }
    
    def __init__(self, memory: Memory):
        self.mem = memory
    
    def surface(self, context: str, limit: int = 5) -> List[SurfacedMemory]:
        """
        Surface memories relevant to the current context.
        
        Args:
            context: Current conversation/task context
            limit: Maximum memories to surface
        
        Returns:
            List of surfaced memories with reasons
        """
        surfaced = []
        seen_ids: Set[int] = set()
        
        # 1. Extract and search for mentioned entities
        entities = self._extract_entities(context)
        for entity in entities[:3]:  # Limit entity searches
            results = self.mem.search(entity, limit=2)
            for r in results:
                if r['id'] not in seen_ids and r.get('relevance', 0) > 0.5:
                    surfaced.append(SurfacedMemory(
                        id=r['id'],
                        content=r['content'],
                        memory_type=r['type'],
                        relevance=r.get('relevance', 0.5),
                        reason=f"mentions '{entity}'"
                    ))
                    seen_ids.add(r['id'])
        
        # 2. Check for temporal cues
        temporal_delta = self._extract_temporal(context)
        if temporal_delta:
            # Search for memories from that time period
            # Note: Would need date-based filtering in production
            pass
        
        # 3. Semantic similarity to overall context
        if len(surfaced) < limit:
            results = self.mem.search(context, limit=limit - len(surfaced))
            for r in results:
                if r['id'] not in seen_ids and r.get('relevance', 0) > 0.4:
                    surfaced.append(SurfacedMemory(
                        id=r['id'],
                        content=r['content'],
                        memory_type=r['type'],
                        relevance=r.get('relevance', 0.5),
                        reason="contextually relevant"
                    ))
                    seen_ids.add(r['id'])
        
        # Sort by relevance
        surfaced.sort(key=lambda x: x.relevance, reverse=True)
        
        return surfaced[:limit]
    
    def surface_for_startup(self) -> List[SurfacedMemory]:
        """
        Surface memories for session startup.
        
        Returns high-importance memories that should always be available.
        """
        surfaced = []
        
        # Get active context to understand current focus
        active = self.mem.get_active()
        current_task = active.get('current_task', active.get('session_state', ''))
        
        if current_task:
            results = self.mem.search(current_task, limit=3, min_salience=0.6)
            for r in results:
                surfaced.append(SurfacedMemory(
                    id=r['id'],
                    content=r['content'],
                    memory_type=r['type'],
                    relevance=r.get('relevance', 0.5),
                    reason="relates to active task"
                ))
        
        return surfaced
    
    def _extract_entities(self, text: str) -> List[str]:
        """Extract mentioned entities (people, projects, etc.)"""
        entities = set()
        
        # Find capitalized names
        for pattern in self.PERSON_PATTERNS:
            matches = re.findall(pattern, text)
            entities.update(matches)
        
        # Find quoted terms
        quoted = re.findall(r'"([^"]+)"', text)
        entities.update(quoted)
        
        # Find @mentions
        mentions = re.findall(r'@(\w+)', text)
        entities.update(mentions)
        
        return list(entities)
    
    def _extract_temporal(self, text: str) -> Optional[timedelta]:
        """Extract temporal references from text."""
        text_lower = text.lower()
        
        for term, delta in self.TEMPORAL_PATTERNS.items():
            if term in text_lower:
                return delta
        
        return None
    
    def format_surfaced(self, memories: List[SurfacedMemory]) -> str:
        """Format surfaced memories for injection into context."""
        if not memories:
            return ""
        
        lines = ["# Relevant Context"]
        for mem in memories:
            lines.append(f"- [{mem.memory_type}] {mem.content}")
            lines.append(f"  _(surfaced because: {mem.reason})_")
        
        return "\n".join(lines)


def surface_memories(db_path: str, context: str, limit: int = 5) -> List[SurfacedMemory]:
    """
    Convenience function to surface memories.
    
    Args:
        db_path: Path to memory database
        context: Current context
        limit: Max memories to return
    
    Returns:
        List of surfaced memories
    """
    mem = Memory(db_path)
    surfacer = MemorySurfacer(mem)
    result = surfacer.surface(context, limit)
    mem.close()
    return result


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python -m src.surface <db_path> <context>")
        sys.exit(1)
    
    db_path = sys.argv[1]
    context = " ".join(sys.argv[2:])
    
    print(f"Surfacing memories for: \"{context[:50]}...\"\\n")
    
    memories = surface_memories(db_path, context, limit=5)
    
    if not memories:
        print("No relevant memories found.")
    else:
        for mem in memories:
            print(f"[{mem.memory_type}] (rel: {mem.relevance:.2f})")
            print(f"  {mem.content[:80]}...")
            print(f"  Reason: {mem.reason}\\n")
