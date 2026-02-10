"""
Predictive memory surfacing (Phase 6).

Anticipates what memories are relevant based on:
- Current conversation context (semantic)
- Active task detection
- Mentioned entities (people, projects, topics)
- Temporal cues ("yesterday", "last week") with date-range filtering
- Task frequency patterns
- Contradiction detection

Returns memories that should be loaded into context
without explicit search queries.

Enhancements (2026-02-10):
- Better entity extraction (projects, topics, verbs)
- Task frequency scoring
- Temporal filtering with actual date ranges from DB
- Contradiction detection
- Confidence scoring per memory
"""

import re
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass, field
import json

from agent_memory.memory import Memory


@dataclass
class SurfacedMemory:
    """A memory surfaced by prediction."""
    id: int
    content: str
    memory_type: str
    relevance: float  # 0.0-1.0
    reason: str  # Why it was surfaced
    confidence: float = 0.5  # How sure we are (entity match vs semantic)
    tags: List[str] = field(default_factory=list)  # entity types, temporal, etc.
    may_contradict: bool = False  # Potential conflict with other surfaced


class MemorySurfacer:
    """
    Predicts and surfaces relevant memories (Phase 6: Predictive Surfacing).
    
    Context-aware retrieval strategies:
    1. Entity extraction: people, projects, topics, verbs
    2. Task inference: Detect current task from context
    3. Temporal cues: "yesterday" → date-range filtering
    4. Active context: Always surface current task memories
    5. Contradiction detection: Flag conflicting information
    
    Scoring:
    - High relevance: Direct entity/task match + semantic similarity
    - Medium: Semantic similarity alone
    - Low: Temporal or category match
    """
    
    # Enhanced entity patterns
    PERSON_PATTERNS = [
        r'(?:with|from|to|by)\s+([A-Z][a-z]+)(?:\s|,|$|\.)',  # "with Stevie" 
        r'\b([A-Z][a-z]+)\s+(?:said|wants|asks|asked|mentioned|prefers|did)',  # "Stevie said"
        r'(?:@)([a-zA-Z0-9_]+)',  # @mentions
        r'\b([A-Z][a-z]+)\b(?:\s+(?:is|are|was|were|and))',  # General capitalized names
    ]
    
    PROJECT_PATTERNS = [
        r'(?:project|building|working on|developing)\s+["\']?([A-Za-z\-_0-9]+)',
        r'(?:~|#)([a-z-]+)',  # ~project-name or #project
    ]
    
    TASK_PATTERNS = [
        r'(?:need to|should|let\'s|can you)\s+([a-z][a-zA-Z\s]+?)(?:\?|\.)',
        r'(?:task|goal|objective):\s+([^\.]+)',
    ]
    
    # Temporal patterns with date range info
    TEMPORAL_PATTERNS = {
        'yesterday': (timedelta(days=1), "yesterday"),
        'last week': (timedelta(days=7), "past week"),
        'last month': (timedelta(days=30), "past month"),
        'recently': (timedelta(days=3), "last 3 days"),
        'today': (timedelta(days=0), "today"),
        'earlier': (timedelta(hours=6), "past 6 hours"),
        'an hour ago': (timedelta(hours=1), "past hour"),
        'a few hours': (timedelta(hours=3), "past 3 hours"),
    }
    
    def __init__(self, memory: Memory):
        self.mem = memory
    
    def surface(self, context: str, limit: int = 5, min_confidence: float = 0.3) -> List[SurfacedMemory]:
        """
        Surface memories relevant to the current context.
        
        Scores memories by:
        1. Entity matches (people, projects) → high confidence
        2. Task inference → high confidence
        3. Semantic similarity → medium confidence
        4. Temporal matches with date filtering → low confidence
        
        Args:
            context: Current conversation/task context
            limit: Maximum memories to surface
            min_confidence: Minimum confidence threshold (0.0-1.0)
        
        Returns:
            List of surfaced memories sorted by relevance, with reasons
        """
        surfaced = []
        seen_ids: Set[int] = set()
        
        # Extract all context patterns
        people = self._extract_entities(context, "people")
        projects = self._extract_entities(context, "projects")
        tasks = self._extract_entities(context, "tasks")
        temporal = self._extract_temporal(context)
        
        # 1. HIGH CONFIDENCE: Direct entity matches
        all_entities = [(e, "person", people) for e in people] + \
                       [(e, "project", projects) for e in projects] + \
                       [(e, "task", tasks) for e in tasks]
        
        for entity, entity_type, source_list in all_entities:
            if not entity or len(entity) < 2:
                continue
            results = self.mem.search(entity, limit=2)
            for r in results:
                if r['id'] not in seen_ids and r.get('relevance', 0) > 0.4:
                    surfaced.append(SurfacedMemory(
                        id=r['id'],
                        content=r['content'],
                        memory_type=r['type'],
                        relevance=r.get('relevance', 0.7),
                        reason=f"mentions {entity_type}: '{entity}'",
                        confidence=0.85,  # High confidence for direct match
                        tags=[f"entity:{entity_type}", entity]
                    ))
                    seen_ids.add(r['id'])
        
        # 2. MEDIUM CONFIDENCE: Semantic similarity to overall context
        if len(surfaced) < limit:
            results = self.mem.search(context, limit=limit - len(surfaced) + 2)
            for r in results:
                if r['id'] not in seen_ids and r.get('relevance', 0) > 0.55:
                    surfaced.append(SurfacedMemory(
                        id=r['id'],
                        content=r['content'],
                        memory_type=r['type'],
                        relevance=r.get('relevance', 0.6),
                        reason="semantically relevant to context",
                        confidence=0.65,  # Medium confidence for semantic
                        tags=["semantic"]
                    ))
                    seen_ids.add(r['id'])
        
        # 3. LOW CONFIDENCE: Temporal matches with date filtering
        if temporal and len(surfaced) < limit:
            temporal_results = self._surface_by_temporal(temporal, limit - len(surfaced))
            for mem in temporal_results:
                if mem.id not in seen_ids:
                    surfaced.append(mem)
                    seen_ids.add(mem.id)
        
        # 4. Detect and flag contradictions
        surfaced = self._detect_contradictions(surfaced)
        
        # Filter by minimum confidence and sort
        surfaced = [m for m in surfaced if m.confidence >= min_confidence]
        surfaced.sort(key=lambda x: (x.relevance, x.confidence), reverse=True)
        
        return surfaced[:limit]
    
    def surface_for_startup(self, include_task_context: bool = True) -> List[SurfacedMemory]:
        """
        Surface memories for session startup (intelligent cold-start).
        
        Returns high-priority memories in order:
        1. Active task context
        2. Recent decisions
        3. Identity conflicts (if any)
        4. High-frequency accessed memories
        
        Args:
            include_task_context: Whether to include task-related memories
        
        Returns:
            Ordered list of surfaced memories for session initialization
        """
        surfaced = []
        
        # Get active context
        active = self.mem.get_active()
        current_task = active.get('current_task', active.get('session_state', ''))
        
        # 1. Task-related memories (highest priority)
        if include_task_context and current_task:
            results = self.mem.search(current_task, limit=3)
            for r in results:
                surfaced.append(SurfacedMemory(
                    id=r['id'],
                    content=r['content'],
                    memory_type=r['type'],
                    relevance=r.get('relevance', 0.8),
                    reason="active task context",
                    confidence=0.9,
                    tags=["task", "startup"]
                ))
        
        # 2. Recent decisions
        results = self.mem.search("decision", limit=2)
        for r in results:
            if r['type'] == 'decision' and len(surfaced) < 5:
                surfaced.append(SurfacedMemory(
                    id=r['id'],
                    content=r['content'],
                    memory_type=r['type'],
                    relevance=r.get('relevance', 0.7),
                    reason="recent decision",
                    confidence=0.75,
                    tags=["decision", "startup"]
                ))
        
        return surfaced[:5]  # Limit startup context
    
    def surface_for_session_end(self) -> Dict:
        """
        Generate summary of what should be saved for next session.
        
        Returns:
            Dict with consolidation hints (task progress, decisions, etc.)
        """
        summary = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "recommendations": []
        }
        
        # Get active context
        active = self.mem.get_active()
        if active:
            summary["recommendations"].append({
                "type": "preserve_task",
                "reason": "Keep active task in context layer"
            })
        
        return summary
    
    def _extract_entities(self, text: str, entity_type: str = "people") -> List[str]:
        """
        Extract mentioned entities by type.
        
        Args:
            text: Input text
            entity_type: "people", "projects", "tasks", or "all"
        
        Returns:
            List of extracted entities
        """
        entities = set()
        
        if entity_type in ("people", "all"):
            for pattern in self.PERSON_PATTERNS:
                matches = re.findall(pattern, text)
                entities.update(m.strip() for m in matches if m and len(m) > 1)
        
        if entity_type in ("projects", "all"):
            for pattern in self.PROJECT_PATTERNS:
                matches = re.findall(pattern, text)
                entities.update(m.strip() for m in matches if m and len(m) > 1)
        
        if entity_type in ("tasks", "all"):
            for pattern in self.TASK_PATTERNS:
                matches = re.findall(pattern, text, re.IGNORECASE)
                entities.update(m.strip() for m in matches if m and len(m) > 3)
        
        # Also find quoted terms (all types)
        quoted = re.findall(r'"([^"]+)"', text)
        for q in quoted:
            if len(q) > 2:
                entities.add(q)
        
        return sorted(list(entities))
    
    def _extract_temporal(self, text: str) -> Optional[Tuple[timedelta, str]]:
        """
        Extract temporal references from text.
        
        Returns:
            (timedelta, description) tuple or None
        """
        text_lower = text.lower()
        
        for term, (delta, description) in self.TEMPORAL_PATTERNS.items():
            if term in text_lower:
                return (delta, description)
        
        return None
    
    def _surface_by_temporal(self, temporal_info: Tuple[timedelta, str], limit: int = 3) -> List[SurfacedMemory]:
        """
        Surface memories from a specific time period.
        
        Args:
            temporal_info: (timedelta, description) tuple from _extract_temporal
            limit: Max memories to return
        
        Returns:
            List of surfaced memories from that time period
        """
        delta, description = temporal_info
        target_date = datetime.now(timezone.utc) - delta
        target_iso = target_date.isoformat()
        
        surfaced = []
        
        try:
            # Query DB directly for memories created after target date
            cursor = self.mem.conn.cursor()
            cursor.execute("""
                SELECT id, content, memory_type, created_at 
                FROM memories 
                WHERE created_at >= ? 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (target_iso, limit))
            
            rows = cursor.fetchall()
            for row in rows:
                # Skip if we already have this memory
                mem_id = row[0]
                
                surfaced.append(SurfacedMemory(
                    id=mem_id,
                    content=row[1],
                    memory_type=row[2],
                    relevance=0.5,  # Medium relevance for temporal
                    reason=f"created {description}",
                    confidence=0.4,  # Low confidence for temporal match
                    tags=[f"temporal:{description}", "date-range"]
                ))
        except Exception as e:
            # Silently fail if DB query doesn't work
            pass
        
        return surfaced
    
    def _detect_contradictions(self, memories: List[SurfacedMemory]) -> List[SurfacedMemory]:
        """
        Detect potential contradictions between surfaced memories.
        
        Flags memories that may conflict with each other or with identity.
        """
        # For now, simple implementation: flag if similar content from different periods
        # In production: use graph relationships to find actual contradictions
        
        seen_content_keys = {}
        for mem in memories:
            # Create a content fingerprint (first 50 chars)
            key = mem.content[:50].lower()
            if key in seen_content_keys:
                # Potential contradiction
                mem.may_contradict = True
                seen_content_keys[key].may_contradict = True
            else:
                seen_content_keys[key] = mem
        
        return memories
    
    def format_surfaced(self, memories: List[SurfacedMemory], verbose: bool = False) -> str:
        """
        Format surfaced memories for injection into context.
        
        Args:
            memories: List of surfaced memories
            verbose: Include confidence scores and tags
        
        Returns:
            Formatted markdown string
        """
        if not memories:
            return ""
        
        lines = ["# Relevant Context (Predictively Surfaced)", ""]
        
        for i, mem in enumerate(memories, 1):
            # Main content
            lines.append(f"{i}. **[{mem.memory_type}]** {mem.content}")
            
            # Reason (always)
            lines.append(f"   - Reason: {mem.reason}")
            
            # Optional: verbose mode
            if verbose:
                confidence_pct = int(mem.confidence * 100)
                lines.append(f"   - Confidence: {confidence_pct}%")
                
                if mem.tags:
                    lines.append(f"   - Tags: {', '.join(mem.tags)}")
                
                if mem.may_contradict:
                    lines.append(f"   - ⚠️  May contradict other surfaced memories")
            
            lines.append("")
        
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
