"""
Memory consolidation: compress, merge, prune.

Like how brains consolidate during sleep:
- Recent detailed memories → compressed summaries
- Similar memories → merged
- Low-value memories → pruned
- Contradictions → resolved
"""

import sqlite3
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from agent_memory.memory import Memory


@dataclass
class ConsolidationResult:
    """Results of a consolidation run."""
    memories_before: int
    memories_after: int
    merged: int
    pruned: int
    compressed: int
    duration_ms: float


class MemoryConsolidator:
    """
    Consolidates memories over time.
    
    Strategies:
    1. Prune: Remove low-salience, old, never-accessed memories
    2. Merge: Combine semantically similar memories
    3. Compress: Summarize old detailed logs (requires LLM, optional)
    """
    
    # Thresholds
    PRUNE_MIN_AGE_DAYS = 7  # Don't prune memories younger than this
    PRUNE_MAX_SALIENCE = 0.4  # Prune if salience below this
    PRUNE_NEVER_ACCESSED = True  # Prune if never accessed
    
    MERGE_SIMILARITY_THRESHOLD = 0.85  # Merge if similarity above this
    
    def __init__(self, memory: Memory):
        self.mem = memory
    
    def consolidate(self, 
                    prune: bool = True, 
                    merge: bool = True,
                    dry_run: bool = False) -> ConsolidationResult:
        """
        Run consolidation pass.
        
        Args:
            prune: Remove low-value memories
            merge: Combine similar memories
            dry_run: Show what would happen without doing it
        
        Returns:
            ConsolidationResult with stats
        """
        start_time = datetime.now(timezone.utc)
        
        # Get initial count
        stats = self.mem.stats()
        memories_before = stats['memories']
        
        pruned = 0
        merged = 0
        compressed = 0
        
        if prune:
            pruned = self._prune_memories(dry_run=dry_run)
        
        if merge:
            merged = self._merge_similar(dry_run=dry_run)
        
        # Get final count
        stats = self.mem.stats()
        memories_after = stats['memories']
        
        duration = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        
        return ConsolidationResult(
            memories_before=memories_before,
            memories_after=memories_after,
            merged=merged,
            pruned=pruned,
            compressed=compressed,
            duration_ms=duration
        )
    
    def _prune_memories(self, dry_run: bool = False) -> int:
        """Remove low-value, old, never-accessed memories."""
        cursor = self.mem.conn.cursor()
        
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=self.PRUNE_MIN_AGE_DAYS)).isoformat()
        
        # Find candidates for pruning
        cursor.execute("""
            SELECT id, content, salience, created_at, accessed_at, access_count
            FROM memories
            WHERE salience < ?
              AND created_at < ?
              AND (access_count = 0 OR access_count IS NULL)
              AND layer = 'archive'
        """, (self.PRUNE_MAX_SALIENCE, cutoff_date))
        
        candidates = cursor.fetchall()
        
        if dry_run:
            return len(candidates)
        
        # Delete candidates
        if candidates:
            ids = [row[0] for row in candidates]
            placeholders = ','.join('?' * len(ids))
            
            # Delete embeddings first
            cursor.execute(f"""
                DELETE FROM memory_embeddings WHERE memory_id IN ({placeholders})
            """, ids)
            
            # Delete memories
            cursor.execute(f"""
                DELETE FROM memories WHERE id IN ({placeholders})
            """, ids)
            
            self.mem.conn.commit()
        
        return len(candidates)
    
    def _merge_similar(self, dry_run: bool = False) -> int:
        """Merge semantically similar memories."""
        cursor = self.mem.conn.cursor()
        
        # Get all memories with embeddings
        cursor.execute("""
            SELECT m.id, m.content, m.memory_type, m.salience, m.created_at
            FROM memories m
            JOIN memory_embeddings e ON m.id = e.memory_id
            WHERE m.layer = 'archive'
            ORDER BY m.created_at DESC
        """)
        
        memories = cursor.fetchall()
        
        if len(memories) < 2:
            return 0
        
        merged_count = 0
        merged_ids = set()
        
        # Compare each pair (expensive, but thorough)
        # In production, would use approximate nearest neighbors
        for i, mem1 in enumerate(memories):
            if mem1[0] in merged_ids:
                continue
                
            for mem2 in memories[i+1:]:
                if mem2[0] in merged_ids:
                    continue
                
                # Check similarity via vector search
                # This is a simplification - would use actual vector comparison
                results = self.mem.search(mem1[1], limit=5)
                
                for r in results:
                    if r['id'] == mem2[0] and r.get('relevance', 0) > self.MERGE_SIMILARITY_THRESHOLD:
                        # Found a match - merge by keeping the one with higher salience
                        if mem1[3] >= mem2[3]:
                            keep_id, remove_id = mem1[0], mem2[0]
                        else:
                            keep_id, remove_id = mem2[0], mem1[0]
                        
                        if not dry_run:
                            # Update the kept memory's access count
                            cursor.execute("""
                                UPDATE memories 
                                SET access_count = access_count + 1,
                                    updated_at = ?
                                WHERE id = ?
                            """, (datetime.now(timezone.utc).isoformat(), keep_id))
                            
                            # Delete the merged memory
                            cursor.execute("DELETE FROM memory_embeddings WHERE memory_id = ?", (remove_id,))
                            cursor.execute("DELETE FROM memories WHERE id = ?", (remove_id,))
                        
                        merged_ids.add(remove_id)
                        merged_count += 1
                        break
        
        if not dry_run:
            self.mem.conn.commit()
        
        return merged_count
    
    def get_consolidation_candidates(self) -> Dict:
        """
        Get stats on what would be consolidated.
        Useful for previewing before running.
        """
        cursor = self.mem.conn.cursor()
        
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=self.PRUNE_MIN_AGE_DAYS)).isoformat()
        
        # Count prune candidates
        cursor.execute("""
            SELECT COUNT(*) FROM memories
            WHERE salience < ?
              AND created_at < ?
              AND (access_count = 0 OR access_count IS NULL)
              AND layer = 'archive'
        """, (self.PRUNE_MAX_SALIENCE, cutoff_date))
        prune_count = cursor.fetchone()[0]
        
        # Count total
        cursor.execute("SELECT COUNT(*) FROM memories")
        total = cursor.fetchone()[0]
        
        # Count by type
        cursor.execute("""
            SELECT memory_type, COUNT(*) 
            FROM memories 
            GROUP BY memory_type
        """)
        by_type = {row[0]: row[1] for row in cursor.fetchall()}
        
        return {
            'total_memories': total,
            'prune_candidates': prune_count,
            'by_type': by_type
        }


def consolidate(db_path: str, dry_run: bool = False) -> ConsolidationResult:
    """
    Convenience function to run consolidation.
    
    Args:
        db_path: Path to memory database
        dry_run: Preview without changing
    
    Returns:
        ConsolidationResult
    """
    mem = Memory(db_path)
    consolidator = MemoryConsolidator(mem)
    result = consolidator.consolidate(dry_run=dry_run)
    mem.close()
    return result


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m src.consolidate <db_path> [--dry-run]")
        sys.exit(1)
    
    db_path = sys.argv[1]
    dry_run = "--dry-run" in sys.argv
    
    print(f"Consolidating {db_path}...")
    if dry_run:
        print("(DRY RUN - no changes will be made)\n")
    
    result = consolidate(db_path, dry_run=dry_run)
    
    print(f"Before: {result.memories_before} memories")
    print(f"After:  {result.memories_after} memories")
    print(f"Pruned: {result.pruned}")
    print(f"Merged: {result.merged}")
    print(f"Time:   {result.duration_ms:.1f}ms")
