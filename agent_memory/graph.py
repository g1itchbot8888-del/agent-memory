"""
Graph Memory — Relationship tracking between memories.

Memories don't exist in isolation. When new information arrives, it may:
- UPDATE existing memories (contradiction/correction)
- EXTEND existing memories (add detail)
- DERIVE new insights from multiple memories

This module tracks these relationships and uses them to:
1. Resolve contradictions (return latest info)
2. Enrich search results (follow extends chains)
3. Surface derived insights
4. Enable automatic forgetting (expired temporal memories)
"""

import sqlite3
import json
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum


class Relation(str, Enum):
    UPDATES = "updates"      # New info contradicts/replaces old
    EXTENDS = "extends"      # New info adds detail to old
    DERIVES = "derives"      # New insight inferred from multiple memories


# Temporal patterns for automatic forgetting
TEMPORAL_PATTERNS = [
    # Relative time references
    (r'\b(tomorrow|tmrw)\b', lambda: timedelta(days=2)),
    (r'\b(tonight)\b', lambda: timedelta(hours=12)),
    (r'\b(today)\b', lambda: timedelta(days=1)),
    (r'\b(this week)\b', lambda: timedelta(weeks=1)),
    (r'\b(this month)\b', lambda: timedelta(days=31)),
    (r'\b(next week)\b', lambda: timedelta(weeks=2)),
    (r'\b(next month)\b', lambda: timedelta(days=62)),
    (r'\b(in (\d+) minutes?)\b', lambda m: timedelta(minutes=int(m))),
    (r'\b(in (\d+) hours?)\b', lambda m: timedelta(hours=int(m))),
    (r'\b(in (\d+) days?)\b', lambda m: timedelta(days=int(m))),
    # Meeting/event patterns
    (r'\b(meeting|call|appointment|interview) (at|@) \d', lambda: timedelta(days=1)),
]

# Similarity thresholds for relationship detection
SIMILARITY_UPDATE_THRESHOLD = 0.72    # Similar + contradiction signals = update
SIMILARITY_EXTEND_THRESHOLD = 0.65    # Moderately similar = likely extends
SIMILARITY_DERIVE_THRESHOLD = 0.45    # Loosely related = candidate for derives


class GraphMemory:
    """
    Graph layer on top of the core Memory system.
    Tracks relationships between memories and handles temporal expiry.
    """
    
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._init_schema()
    
    def _init_schema(self):
        """Create graph tables if they don't exist."""
        cursor = self.conn.cursor()
        
        # Edges between memories
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory_edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL,
                target_id INTEGER NOT NULL,
                relation TEXT NOT NULL,
                confidence REAL DEFAULT 0.5,
                created_at TEXT NOT NULL,
                metadata TEXT,
                FOREIGN KEY (source_id) REFERENCES memories(id),
                FOREIGN KEY (target_id) REFERENCES memories(id),
                UNIQUE(source_id, target_id, relation)
            )
        """)
        
        # Index for fast lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_edges_source ON memory_edges(source_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_edges_target ON memory_edges(target_id)
        """)
        
        # Add is_latest and expires_at columns to memories if not present
        try:
            cursor.execute("ALTER TABLE memories ADD COLUMN is_latest INTEGER DEFAULT 1")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            cursor.execute("ALTER TABLE memories ADD COLUMN expires_at TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        self.conn.commit()
    
    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
    
    # ==================== RELATIONSHIP DETECTION ====================
    
    def detect_relationships(self, new_memory_id: int, new_content: str,
                             similar_memories: List[Dict],
                             new_embedding: Optional[List[float]] = None) -> List[Dict]:
        """
        Detect relationships between a new memory and existing similar memories.
        Uses similarity scores + heuristics to classify relationships.
        
        Returns list of detected relationships.
        """
        relationships = []
        
        for existing in similar_memories:
            if existing['id'] == new_memory_id:
                continue
                
            similarity = existing.get('relevance', 0)
            existing_content = existing.get('content', '')
            
            relation = self._classify_relationship(
                new_content, existing_content, similarity
            )
            
            if relation:
                confidence = self._compute_confidence(
                    relation, similarity, new_content, existing_content
                )
                relationships.append({
                    'source_id': new_memory_id,
                    'target_id': existing['id'],
                    'relation': relation.value,
                    'confidence': confidence,
                    'existing_content': existing_content[:100]
                })
        
        return relationships
    
    def _classify_relationship(self, new: str, existing: str, 
                                similarity: float) -> Optional[Relation]:
        """
        Classify the relationship between new and existing memory.
        
        Heuristics:
        - Very high similarity + contradiction signals → UPDATE
        - High similarity + additional info → EXTENDS
        - Moderate similarity across topics → DERIVES candidate
        """
        new_lower = new.lower()
        existing_lower = existing.lower()
        
        # Check for update signals (contradiction/replacement)
        if similarity >= SIMILARITY_UPDATE_THRESHOLD:
            if self._has_contradiction_signals(new_lower, existing_lower):
                return Relation.UPDATES
            # Same subject, very high similarity, but no contradiction — extends
            if similarity >= 0.85 and len(new) > len(existing) * 0.5:
                return Relation.EXTENDS
        
        # Also check for updates at lower similarity if strong contradiction signals
        if similarity >= SIMILARITY_EXTEND_THRESHOLD:
            if self._has_contradiction_signals(new_lower, existing_lower) and \
               self._shares_subject(new_lower, existing_lower):
                return Relation.UPDATES
        
        # Check for extension signals
        if similarity >= SIMILARITY_EXTEND_THRESHOLD:
            if self._has_extension_signals(new_lower, existing_lower):
                return Relation.EXTENDS
            # Shared entities/subjects + new info
            if self._shares_subject(new_lower, existing_lower):
                if self._has_new_information(new_lower, existing_lower):
                    return Relation.EXTENDS
        
        # Derive: moderate similarity, different enough to be separate but related
        if SIMILARITY_DERIVE_THRESHOLD <= similarity < SIMILARITY_EXTEND_THRESHOLD:
            if self._has_inferrable_connection(new_lower, existing_lower):
                return Relation.DERIVES
        
        return None
    
    def _has_contradiction_signals(self, new: str, existing: str) -> bool:
        """Detect if new content contradicts existing."""
        # Direct contradiction patterns
        contradiction_patterns = [
            r'\b(actually|no longer|not|isn\'t|wasn\'t|changed to|moved to|switched to|now)\b',
            r'\b(instead of|rather than|correcting|correction|update[ds]?)\b',
            r'\b(used to|previously|formerly|was|were)\b',
        ]
        
        # Check if new content has contradiction language
        has_contradiction_lang = any(
            re.search(p, new) for p in contradiction_patterns
        )
        
        # Check if they share a subject but differ on predicate
        # (Simple: same first few significant words, different endings)
        new_words = set(new.split()[:8])
        existing_words = set(existing.split()[:8])
        shared_start = len(new_words & existing_words) / max(len(new_words), 1)
        
        if has_contradiction_lang and shared_start > 0.3:
            return True
        
        # Check for value changes (e.g., "price is $X" vs "price is $Y")
        numbers_new = set(re.findall(r'\$?\d+\.?\d*', new))
        numbers_existing = set(re.findall(r'\$?\d+\.?\d*', existing))
        if numbers_new and numbers_existing and numbers_new != numbers_existing:
            if shared_start > 0.4:
                return True
        
        return False
    
    def _has_extension_signals(self, new: str, existing: str) -> bool:
        """Detect if new content extends existing."""
        extension_patterns = [
            r'\b(also|additionally|furthermore|moreover|plus)\b',
            r'\b(specifically|in particular|for example|e\.g\.)\b',
            r'\b(details|more about|expanding on)\b',
        ]
        return any(re.search(p, new) for p in extension_patterns)
    
    def _shares_subject(self, new: str, existing: str) -> bool:
        """Check if two memories share a subject entity."""
        # Extract potential subjects (capitalized words, names)
        def extract_entities(text):
            # Simple: look for capitalized words (potential names/entities)
            entities = set(re.findall(r'\b[A-Z][a-z]+\b', text))
            # Also check for common subjects
            entities.update(re.findall(r'\b(?:bill|alex|the project|the app|capybot)\b', text.lower()))
            return entities
        
        new_entities = extract_entities(new)
        existing_entities = extract_entities(existing)
        
        if not new_entities or not existing_entities:
            return False
        
        overlap = new_entities & existing_entities
        return len(overlap) > 0
    
    def _has_new_information(self, new: str, existing: str) -> bool:
        """Check if new content has information not in existing."""
        new_words = set(new.split())
        existing_words = set(existing.split())
        novel_words = new_words - existing_words
        # More than 30% new words = has new info
        return len(novel_words) / max(len(new_words), 1) > 0.3
    
    def _has_inferrable_connection(self, new: str, existing: str) -> bool:
        """Check if a derivation could be made between two memories."""
        # Simple: they share some entities/topics but are distinct enough
        new_words = set(new.split())
        existing_words = set(existing.split())
        overlap = len(new_words & existing_words) / max(min(len(new_words), len(existing_words)), 1)
        return 0.15 < overlap < 0.5
    
    def _compute_confidence(self, relation: Relation, similarity: float,
                           new: str, existing: str) -> float:
        """Compute confidence score for a detected relationship."""
        base = similarity
        
        if relation == Relation.UPDATES:
            # Higher confidence if explicit contradiction language
            if re.search(r'\b(actually|no longer|changed|correction)\b', new.lower()):
                base = min(base + 0.15, 1.0)
        elif relation == Relation.EXTENDS:
            # Higher confidence if clearly additive
            if re.search(r'\b(also|additionally|specifically)\b', new.lower()):
                base = min(base + 0.1, 1.0)
        elif relation == Relation.DERIVES:
            # Derives are inherently lower confidence
            base = base * 0.7
        
        return round(base, 3)
    
    # ==================== EDGE MANAGEMENT ====================
    
    def add_edge(self, source_id: int, target_id: int, relation: str,
                 confidence: float = 0.5, metadata: Optional[Dict] = None) -> int:
        """Add a relationship edge between two memories."""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO memory_edges 
                (source_id, target_id, relation, confidence, created_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (source_id, target_id, relation, confidence, self._now(),
                  json.dumps(metadata) if metadata else None))
            
            # If this is an UPDATE, mark the target as no longer latest
            if relation == Relation.UPDATES.value:
                cursor.execute("""
                    UPDATE memories SET is_latest = 0 WHERE id = ?
                """, (target_id,))
            
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            return -1
    
    def get_edges(self, memory_id: int, direction: str = "both") -> List[Dict]:
        """Get all edges connected to a memory."""
        cursor = self.conn.cursor()
        edges = []
        
        if direction in ("out", "both"):
            cursor.execute("""
                SELECT e.*, m.content as target_content 
                FROM memory_edges e
                JOIN memories m ON e.target_id = m.id
                WHERE e.source_id = ?
            """, (memory_id,))
            for row in cursor.fetchall():
                edges.append({
                    'id': row['id'],
                    'source_id': row['source_id'],
                    'target_id': row['target_id'],
                    'relation': row['relation'],
                    'confidence': row['confidence'],
                    'direction': 'out',
                    'connected_content': row['target_content'][:100]
                })
        
        if direction in ("in", "both"):
            cursor.execute("""
                SELECT e.*, m.content as source_content
                FROM memory_edges e
                JOIN memories m ON e.source_id = m.id
                WHERE e.target_id = ?
            """, (memory_id,))
            for row in cursor.fetchall():
                edges.append({
                    'id': row['id'],
                    'source_id': row['source_id'],
                    'target_id': row['target_id'],
                    'relation': row['relation'],
                    'confidence': row['confidence'],
                    'direction': 'in',
                    'connected_content': row['source_content'][:100]
                })
        
        return edges
    
    def get_memory_chain(self, memory_id: int, relation: str = "updates",
                         max_depth: int = 10) -> List[int]:
        """Follow a chain of relationships (e.g., update chain)."""
        chain = [memory_id]
        current = memory_id
        
        for _ in range(max_depth):
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT target_id FROM memory_edges
                WHERE source_id = ? AND relation = ?
                LIMIT 1
            """, (current, relation))
            row = cursor.fetchone()
            if row is None:
                break
            chain.append(row['target_id'])
            current = row['target_id']
        
        return chain
    
    # ==================== TEMPORAL FORGETTING ====================
    
    def detect_expiry(self, content: str) -> Optional[str]:
        """
        Detect if a memory has temporal content and compute expiry time.
        Returns ISO timestamp of when the memory should expire, or None.
        """
        content_lower = content.lower()
        now = datetime.now(timezone.utc)
        
        for pattern, delta_fn in TEMPORAL_PATTERNS:
            match = re.search(pattern, content_lower)
            if match:
                # Some delta functions need the match group
                try:
                    if match.lastindex and match.lastindex >= 2:
                        delta = delta_fn(match.group(2))
                    else:
                        delta = delta_fn()
                except (TypeError, ValueError):
                    delta = delta_fn()
                
                expiry = now + delta
                return expiry.isoformat()
        
        return None
    
    def set_expiry(self, memory_id: int, expires_at: str):
        """Set expiry time for a memory."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE memories SET expires_at = ? WHERE id = ?
        """, (expires_at, memory_id))
        self.conn.commit()
    
    def expire_memories(self) -> int:
        """
        Mark expired memories as no longer latest.
        Returns count of expired memories.
        """
        cursor = self.conn.cursor()
        now = self._now()
        
        cursor.execute("""
            UPDATE memories 
            SET is_latest = 0
            WHERE expires_at IS NOT NULL 
            AND expires_at < ?
            AND is_latest = 1
        """, (now,))
        
        expired = cursor.rowcount
        self.conn.commit()
        return expired
    
    # ==================== ENHANCED SEARCH ====================
    
    def search_with_graph(self, base_results: List[Dict], 
                          follow_extends: bool = True,
                          prefer_latest: bool = True) -> List[Dict]:
        """
        Enhance search results using graph relationships.
        
        - If prefer_latest: filter out memories that have been updated
        - If follow_extends: include extending memories for context
        """
        if not base_results:
            return base_results
        
        enhanced = []
        seen_ids = set()
        
        for result in base_results:
            mem_id = result['id']
            
            # Skip if we've already seen this
            if mem_id in seen_ids:
                continue
            seen_ids.add(mem_id)
            
            # Check if this memory has been superseded
            if prefer_latest:
                cursor = self.conn.cursor()
                cursor.execute("""
                    SELECT is_latest FROM memories WHERE id = ?
                """, (mem_id,))
                row = cursor.fetchone()
                if row and not row['is_latest']:
                    # Find the latest version
                    cursor.execute("""
                        SELECT source_id FROM memory_edges
                        WHERE target_id = ? AND relation = 'updates'
                        ORDER BY created_at DESC LIMIT 1
                    """, (mem_id,))
                    update_row = cursor.fetchone()
                    if update_row:
                        # Replace with the latest version
                        latest_id = update_row['source_id']
                        cursor.execute("""
                            SELECT id, content, memory_type, salience, created_at, metadata
                            FROM memories WHERE id = ?
                        """, (latest_id,))
                        latest = cursor.fetchone()
                        if latest and latest['id'] not in seen_ids:
                            result = {
                                'id': latest['id'],
                                'content': latest['content'],
                                'type': latest['memory_type'],
                                'salience': latest['salience'],
                                'created_at': latest['created_at'],
                                'relevance': result.get('relevance', 0.5),
                                'metadata': json.loads(latest['metadata']) if latest['metadata'] else None,
                                '_supersedes': mem_id
                            }
                            seen_ids.add(latest['id'])
                    else:
                        # No update found, skip outdated memory
                        continue
            
            # Follow extends to enrich context
            if follow_extends:
                extensions = self._get_extensions(mem_id)
                if extensions:
                    ext_content = "; ".join(e['content'][:100] for e in extensions[:3])
                    result['_extensions'] = extensions
                    result['_extended_context'] = ext_content
            
            enhanced.append(result)
        
        return enhanced
    
    def _get_extensions(self, memory_id: int) -> List[Dict]:
        """Get memories that extend a given memory."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT m.id, m.content, m.memory_type, m.created_at, e.confidence
            FROM memory_edges e
            JOIN memories m ON e.source_id = m.id
            WHERE e.target_id = ? AND e.relation = 'extends'
            ORDER BY e.confidence DESC
        """, (memory_id,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    # ==================== GRAPH STATS ====================
    
    def stats(self) -> Dict:
        """Get graph statistics."""
        cursor = self.conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as count FROM memory_edges")
        total_edges = cursor.fetchone()['count']
        
        by_relation = {}
        cursor.execute("""
            SELECT relation, COUNT(*) as count 
            FROM memory_edges GROUP BY relation
        """)
        for row in cursor.fetchall():
            by_relation[row['relation']] = row['count']
        
        # Count superseded memories
        cursor.execute("""
            SELECT COUNT(*) as count FROM memories 
            WHERE is_latest = 0
        """)
        superseded = cursor.fetchone()['count']
        
        # Count memories with expiry
        cursor.execute("""
            SELECT COUNT(*) as count FROM memories 
            WHERE expires_at IS NOT NULL
        """)
        temporal = cursor.fetchone()['count']
        
        # Avg confidence
        cursor.execute("SELECT AVG(confidence) as avg FROM memory_edges")
        avg_conf = cursor.fetchone()['avg'] or 0
        
        return {
            'total_edges': total_edges,
            'by_relation': by_relation,
            'superseded_memories': superseded,
            'temporal_memories': temporal,
            'avg_confidence': round(avg_conf, 3)
        }
