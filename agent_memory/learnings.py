"""
Self-learning module for agent memory.

Inspired by agno-agi/dash's "Learning Machine" pattern:
- Captures what worked and what didn't
- Patterns discovered through use, not manual curation
- GPU-poor continuous learning: no fine-tuning, just stored patterns

Learnings types:
- recall_hit: A search that returned useful results
- recall_miss: A search that returned nothing useful  
- correction: User corrected something the agent said/did
- insight: Pattern discovered during operation
- error: Something that went wrong and how it was fixed
"""

import sqlite3
import json
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any


class LearningMachine:
    """
    Automatic self-learning system.
    
    Captures operational patterns so the agent improves over time
    without retraining or fine-tuning.
    """
    
    def __init__(self, db_path: str = "memory.db"):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()
    
    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
        return self._conn
    
    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
    
    def _init_db(self):
        """Initialize learnings table."""
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS learnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                trigger_text TEXT NOT NULL,
                learning TEXT NOT NULL,
                context TEXT,
                times_applied INTEGER DEFAULT 0,
                last_applied_at TEXT,
                created_at TEXT NOT NULL,
                metadata TEXT
            )
        """)
        # Index for quick lookup by kind
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_learnings_kind 
            ON learnings(kind)
        """)
        self.conn.commit()
    
    def record(self, kind: str, trigger: str, learning: str, 
               context: Optional[str] = None,
               metadata: Optional[Dict] = None) -> int:
        """
        Record a learning.
        
        Args:
            kind: Type of learning (recall_hit, recall_miss, correction, insight, error)
            trigger: What triggered this learning (e.g., search query, user message)
            learning: The actual lesson learned
            context: Additional context about the situation
            metadata: Any structured data to store
            
        Returns:
            Learning ID
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO learnings (kind, trigger_text, learning, context, created_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (kind, trigger, learning, context, self._now(),
              json.dumps(metadata) if metadata else None))
        self.conn.commit()
        return cursor.lastrowid
    
    def record_recall_hit(self, query: str, result_summary: str, 
                          usefulness: float = 1.0):
        """Record that a memory search returned useful results."""
        return self.record(
            kind="recall_hit",
            trigger=query,
            learning=f"Query '{query}' successfully found: {result_summary}",
            metadata={"usefulness": usefulness}
        )
    
    def record_recall_miss(self, query: str, what_was_needed: str):
        """Record that a memory search failed to find what was needed."""
        return self.record(
            kind="recall_miss",
            trigger=query,
            learning=f"Query '{query}' missed. Needed: {what_was_needed}",
            metadata={"gap": what_was_needed}
        )
    
    def record_correction(self, what_was_wrong: str, what_is_right: str,
                          context: Optional[str] = None):
        """Record a correction (user fixed something)."""
        return self.record(
            kind="correction",
            trigger=what_was_wrong,
            learning=f"WRONG: {what_was_wrong} → RIGHT: {what_is_right}",
            context=context
        )
    
    def record_insight(self, observation: str, pattern: str):
        """Record a discovered pattern or insight."""
        return self.record(
            kind="insight",
            trigger=observation,
            learning=pattern
        )
    
    def record_error(self, what_failed: str, how_fixed: str,
                     context: Optional[str] = None):
        """Record an error and its fix."""
        return self.record(
            kind="error",
            trigger=what_failed,
            learning=f"FIX: {how_fixed}",
            context=context
        )
    
    def get_relevant_learnings(self, context: str, kind: Optional[str] = None,
                                limit: int = 5) -> List[Dict]:
        """
        Get learnings relevant to current context.
        
        Simple keyword matching for now — can be upgraded to semantic search later.
        """
        cursor = self.conn.cursor()
        
        # Extract key terms from context
        terms = [t.lower().strip() for t in context.split() if len(t) > 3]
        
        if not terms:
            return []
        
        # Build LIKE conditions for key terms
        conditions = []
        params = []
        for term in terms[:10]:  # Cap at 10 terms
            conditions.append("(trigger_text LIKE ? OR learning LIKE ?)")
            params.extend([f"%{term}%", f"%{term}%"])
        
        where = " OR ".join(conditions)
        if kind:
            where = f"kind = ? AND ({where})"
            params = [kind] + params
        
        cursor.execute(f"""
            SELECT id, kind, trigger_text, learning, context, 
                   times_applied, created_at, metadata
            FROM learnings
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT ?
        """, params + [limit])
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'id': row['id'],
                'kind': row['kind'],
                'trigger': row['trigger_text'],
                'learning': row['learning'],
                'context': row['context'],
                'times_applied': row['times_applied'],
                'created_at': row['created_at'],
                'metadata': json.loads(row['metadata']) if row['metadata'] else None
            })
        
        return results
    
    def get_errors(self, limit: int = 10) -> List[Dict]:
        """Get recent error learnings (things to avoid)."""
        return self.get_relevant_learnings("", kind="error", limit=limit)
    
    def get_corrections(self, limit: int = 10) -> List[Dict]:
        """Get recent corrections (things the user fixed)."""
        return self.get_relevant_learnings("", kind="correction", limit=limit)
    
    def mark_applied(self, learning_id: int):
        """Mark a learning as having been applied."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE learnings 
            SET times_applied = times_applied + 1, last_applied_at = ?
            WHERE id = ?
        """, (self._now(), learning_id))
        self.conn.commit()
    
    def stats(self) -> Dict:
        """Get learning statistics."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT kind, COUNT(*) as count FROM learnings GROUP BY kind")
        by_kind = {row['kind']: row['count'] for row in cursor.fetchall()}
        
        cursor.execute("SELECT COUNT(*) as total FROM learnings")
        total = cursor.fetchone()['total']
        
        cursor.execute("""
            SELECT COUNT(*) as applied FROM learnings 
            WHERE times_applied > 0
        """)
        applied = cursor.fetchone()['applied']
        
        return {
            'total': total,
            'by_kind': by_kind,
            'applied': applied,
            'application_rate': applied / total if total > 0 else 0
        }
    
    def format_context(self, context: str, limit: int = 3) -> str:
        """
        Format relevant learnings as context for the agent.
        
        Returns a string that can be injected into the agent's prompt.
        """
        learnings = self.get_relevant_learnings(context, limit=limit)
        if not learnings:
            return ""
        
        lines = ["# Learnings (from past experience)"]
        for l in learnings:
            icon = {"recall_hit": "✓", "recall_miss": "✗", "correction": "⚠", 
                    "insight": "💡", "error": "🔧"}.get(l['kind'], "•")
            lines.append(f"{icon} [{l['kind']}] {l['learning']}")
        
        return "\n".join(lines)
    
    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
