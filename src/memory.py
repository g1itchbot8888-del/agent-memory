"""
Core memory system for autonomous agents.

Hierarchical memory with semantic recall:
- IDENTITY: Who am I (always loaded)
- ACTIVE: Current task, hot context
- SURFACED: Relevant memories pulled by meaning
- ARCHIVE: Full history, searchable
"""

import sqlite3
import json
import os
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pathlib import Path

# Will be imported once installed
try:
    import sqlite_vec
    SQLITE_VEC_AVAILABLE = True
except ImportError:
    SQLITE_VEC_AVAILABLE = False

try:
    from fastembed import TextEmbedding
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    try:
        from sentence_transformers import SentenceTransformer
        EMBEDDINGS_AVAILABLE = True
    except ImportError:
        EMBEDDINGS_AVAILABLE = False


class Memory:
    """
    Hierarchical memory system with semantic recall.
    
    Layers:
    - identity: Core self, always loaded (~200 tokens)
    - active: Current task, hot context (~500 tokens)  
    - memories: Searchable archive with embeddings
    """
    
    DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"  # Fast, small, good quality (fastembed)
    EMBEDDING_DIM = 384  # Dimension for bge-small-en-v1.5
    
    def __init__(self, db_path: str = "memory.db", model_name: Optional[str] = None):
        self.db_path = db_path
        self.model_name = model_name or self.DEFAULT_MODEL
        self._conn: Optional[sqlite3.Connection] = None
        self._model: Optional[Any] = None
        self._init_db()
    
    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            if SQLITE_VEC_AVAILABLE:
                self._conn.enable_load_extension(True)
                sqlite_vec.load(self._conn)
        return self._conn
    
    @property
    def model(self):
        if self._model is None and EMBEDDINGS_AVAILABLE:
            try:
                from fastembed import TextEmbedding
                self._model = TextEmbedding(self.model_name)
            except ImportError:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
        return self._model
    
    def _init_db(self):
        """Initialize database schema."""
        cursor = self.conn.cursor()
        
        # Core memories table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                layer TEXT NOT NULL DEFAULT 'archive',
                memory_type TEXT DEFAULT 'fact',
                salience REAL DEFAULT 0.5,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                accessed_at TEXT,
                access_count INTEGER DEFAULT 0,
                metadata TEXT
            )
        """)
        
        # Identity layer (special - always loaded)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS identity (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # Active context (hot, survives truncation)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS active_context (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # Vector embeddings (if sqlite-vec available)
        if SQLITE_VEC_AVAILABLE:
            cursor.execute(f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_embeddings USING vec0(
                    memory_id INTEGER PRIMARY KEY,
                    embedding FLOAT[{self.EMBEDDING_DIM}]
                )
            """)
        
        self.conn.commit()
    
    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
    
    def _embed(self, text: str) -> Optional[List[float]]:
        """Generate embedding for text."""
        if not EMBEDDINGS_AVAILABLE or self.model is None:
            return None
        try:
            # fastembed returns a generator
            from fastembed import TextEmbedding
            if isinstance(self.model, TextEmbedding):
                embeddings = list(self.model.embed([text]))
                return embeddings[0].tolist()
        except (ImportError, TypeError):
            pass
        # sentence-transformers
        return self.model.encode(text).tolist()
    
    # ==================== IDENTITY LAYER ====================
    
    def set_identity(self, key: str, value: str):
        """Set an identity attribute (who I am)."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO identity (key, value, updated_at)
            VALUES (?, ?, ?)
        """, (key, value, self._now()))
        self.conn.commit()
    
    def get_identity(self, key: Optional[str] = None) -> Dict[str, str]:
        """Get identity attributes."""
        cursor = self.conn.cursor()
        if key:
            cursor.execute("SELECT key, value FROM identity WHERE key = ?", (key,))
        else:
            cursor.execute("SELECT key, value FROM identity")
        return {row['key']: row['value'] for row in cursor.fetchall()}
    
    def get_identity_context(self) -> str:
        """Get identity as a formatted context string."""
        identity = self.get_identity()
        if not identity:
            return ""
        lines = [f"# Identity"]
        for key, value in identity.items():
            lines.append(f"- {key}: {value}")
        return "\n".join(lines)
    
    # ==================== ACTIVE CONTEXT LAYER ====================
    
    def set_active(self, key: str, value: str):
        """Set active context (current task, hot info)."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO active_context (key, value, updated_at)
            VALUES (?, ?, ?)
        """, (key, value, self._now()))
        self.conn.commit()
    
    def get_active(self, key: Optional[str] = None) -> Dict[str, str]:
        """Get active context."""
        cursor = self.conn.cursor()
        if key:
            cursor.execute("SELECT key, value FROM active_context WHERE key = ?", (key,))
        else:
            cursor.execute("SELECT key, value FROM active_context")
        return {row['key']: row['value'] for row in cursor.fetchall()}
    
    def get_active_context(self) -> str:
        """Get active context as formatted string."""
        active = self.get_active()
        if not active:
            return ""
        lines = ["# Active Context"]
        for key, value in active.items():
            lines.append(f"## {key}")
            lines.append(value)
        return "\n".join(lines)
    
    # ==================== MEMORY ARCHIVE ====================
    
    def add(self, content: str, memory_type: str = "fact", 
            salience: float = 0.5, metadata: Optional[Dict] = None) -> int:
        """Add a memory to the archive."""
        cursor = self.conn.cursor()
        now = self._now()
        
        cursor.execute("""
            INSERT INTO memories (content, memory_type, salience, created_at, updated_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (content, memory_type, salience, now, now, json.dumps(metadata) if metadata else None))
        
        memory_id = cursor.lastrowid
        
        # Add embedding if available
        embedding = self._embed(content)
        if embedding and SQLITE_VEC_AVAILABLE:
            cursor.execute("""
                INSERT INTO memory_embeddings (memory_id, embedding)
                VALUES (?, ?)
            """, (memory_id, json.dumps(embedding)))
        
        self.conn.commit()
        return memory_id
    
    def search(self, query: str, limit: int = 5, min_salience: float = 0.0) -> List[Dict]:
        """Search memories by semantic similarity."""
        cursor = self.conn.cursor()
        
        # Try semantic search first
        query_embedding = self._embed(query)
        
        if query_embedding and SQLITE_VEC_AVAILABLE:
            # Vector similarity search
            cursor.execute(f"""
                SELECT 
                    m.id, m.content, m.memory_type, m.salience, 
                    m.created_at, m.metadata,
                    vec_distance_cosine(e.embedding, ?) as distance
                FROM memories m
                JOIN memory_embeddings e ON m.id = e.memory_id
                WHERE m.salience >= ?
                ORDER BY distance ASC
                LIMIT ?
            """, (json.dumps(query_embedding), min_salience, limit))
        else:
            # Fallback to keyword search
            cursor.execute("""
                SELECT id, content, memory_type, salience, created_at, metadata, 0.5 as distance
                FROM memories
                WHERE content LIKE ? AND salience >= ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (f"%{query}%", min_salience, limit))
        
        results = []
        for row in cursor.fetchall():
            # Update access tracking
            self._record_access(row['id'])
            results.append({
                'id': row['id'],
                'content': row['content'],
                'type': row['memory_type'],
                'salience': row['salience'],
                'created_at': row['created_at'],
                'relevance': 1 - row['distance'] if row['distance'] else 0.5,
                'metadata': json.loads(row['metadata']) if row['metadata'] else None
            })
        
        return results
    
    def _record_access(self, memory_id: int):
        """Record that a memory was accessed."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE memories 
            SET accessed_at = ?, access_count = access_count + 1
            WHERE id = ?
        """, (self._now(), memory_id))
        self.conn.commit()
    
    # ==================== FULL CONTEXT ====================
    
    def get_startup_context(self) -> str:
        """Get the context to load on startup (identity + active)."""
        parts = []
        
        identity = self.get_identity_context()
        if identity:
            parts.append(identity)
        
        active = self.get_active_context()
        if active:
            parts.append(active)
        
        return "\n\n".join(parts)
    
    def surface_relevant(self, context: str, limit: int = 3) -> str:
        """Surface memories relevant to the current context."""
        memories = self.search(context, limit=limit, min_salience=0.3)
        if not memories:
            return ""
        
        lines = ["# Relevant Memories"]
        for mem in memories:
            lines.append(f"- [{mem['type']}] {mem['content']}")
        
        return "\n".join(lines)
    
    # ==================== UTILITIES ====================
    
    def stats(self) -> Dict:
        """Get memory statistics."""
        cursor = self.conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as count FROM memories")
        memory_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM identity")
        identity_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM active_context")
        active_count = cursor.fetchone()['count']
        
        return {
            'memories': memory_count,
            'identity_keys': identity_count,
            'active_keys': active_count,
            'embeddings_available': EMBEDDINGS_AVAILABLE,
            'vector_search_available': SQLITE_VEC_AVAILABLE
        }
    
    def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None


# Convenience function for quick usage
def get_memory(db_path: str = "memory.db") -> Memory:
    """Get a Memory instance."""
    return Memory(db_path)
