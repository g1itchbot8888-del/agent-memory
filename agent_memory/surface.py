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
from typing import List, Dict, Optional, Set, Any
from dataclasses import dataclass

from agent_memory.memory import Memory


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
        
        # 2. Check for temporal cues and filter by time
        temporal_delta = self._extract_temporal(context)
        if temporal_delta:
            temporal_results = self._search_temporal(temporal_delta, context, limit=3)
            for r in temporal_results:
                if r['id'] not in seen_ids:
                    surfaced.append(SurfacedMemory(
                        id=r['id'],
                        content=r['content'],
                        memory_type=r['type'],
                        relevance=min(0.85, r.get('relevance', 0.5) + 0.2),  # Boost temporal matches
                        reason=f"from requested time period"
                    ))
                    seen_ids.add(r['id'])
        
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
    
    def _search_temporal(self, delta: timedelta, context: str, limit: int = 3) -> List[Dict]:
        """
        Search for memories within a time window.
        
        Args:
            delta: How far back to look
            context: Context for semantic matching within window
            limit: Max results
        
        Returns:
            List of matching memories
        """
        # Calculate cutoff time
        now = datetime.now(timezone.utc)
        if delta.days == 0 and delta.seconds == 0:
            # "today" means start of today
            cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            cutoff = now - delta
        
        cutoff_str = cutoff.strftime('%Y-%m-%d')
        
        # Query memories from that time period
        cursor = self.mem.conn.execute("""
            SELECT id, content, layer as type, salience
            FROM memories
            WHERE created_at >= ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (cutoff_str, limit * 2))  # Get more, then filter by relevance
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'id': row[0],
                'content': row[1],
                'type': row[2],
                'relevance': row[3] or 0.5
            })
        
        # If we have context, re-rank by semantic similarity
        if context and results and hasattr(self.mem, 'search'):
            # Use existing search to get relevance scores
            search_results = self.mem.search(context, limit=limit)
            search_ids = {r['id']: r.get('relevance', 0.5) for r in search_results}
            
            # Boost temporal results that also match semantically
            for r in results:
                if r['id'] in search_ids:
                    r['relevance'] = max(r['relevance'], search_ids[r['id']])
        
        return results[:limit]
    
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
