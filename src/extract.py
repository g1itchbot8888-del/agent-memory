"""
Automatic fact extraction from conversations.

Heuristic-based extraction for now, can be enhanced with LLM later.
"""

import re
from typing import List, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class ExtractedMemory:
    content: str
    memory_type: str
    salience: float
    confidence: float  # How confident we are this is worth saving


class MemoryExtractor:
    """
    Extract memories from conversation text.
    
    Uses pattern matching and heuristics.
    Returns memories with type and salience scores.
    """
    
    # Patterns that indicate decisions
    DECISION_PATTERNS = [
        r"we (?:decided|agreed|chose|will|should|going to|need to)\b",
        r"let'?s\b",
        r"the plan is\b",
        r"(?:I|we) (?:want|need) to\b",
        r"pivot(?:ed|ing)?\b",
    ]
    
    # Patterns that indicate preferences
    PREFERENCE_PATTERNS = [
        r"(?:I|you|bill|we) (?:prefer|like|love|want|don'?t like|hate)\b",
        r"(?:better|best|favorite|rather)\b",
    ]
    
    # Patterns that indicate facts/insights
    INSIGHT_PATTERNS = [
        r"(?:the key|important|insight|learned|realized|discovered)\b",
        r"turns out\b",
        r"the (?:problem|issue|challenge|opportunity) is\b",
    ]
    
    # Patterns that indicate goals
    GOAL_PATTERNS = [
        r"(?:goal|objective|target|aim) is\b",
        r"we'?re (?:building|creating|making|trying to)\b",
        r"the vision is\b",
    ]
    
    def __init__(self):
        # Compile patterns for efficiency
        self.decision_re = re.compile("|".join(self.DECISION_PATTERNS), re.IGNORECASE)
        self.preference_re = re.compile("|".join(self.PREFERENCE_PATTERNS), re.IGNORECASE)
        self.insight_re = re.compile("|".join(self.INSIGHT_PATTERNS), re.IGNORECASE)
        self.goal_re = re.compile("|".join(self.GOAL_PATTERNS), re.IGNORECASE)
    
    def extract_from_text(self, text: str, min_confidence: float = 0.3) -> List[ExtractedMemory]:
        """
        Extract memories from text.
        
        Returns list of extracted memories with types and scores.
        """
        memories = []
        
        # Split into sentences/lines
        lines = self._split_into_chunks(text)
        
        for line in lines:
            line = line.strip()
            if len(line) < 20:  # Too short to be meaningful
                continue
            
            # Check for decision patterns
            if self.decision_re.search(line):
                memories.append(ExtractedMemory(
                    content=line,
                    memory_type="decision",
                    salience=0.8,
                    confidence=0.7
                ))
                continue
            
            # Check for preference patterns
            if self.preference_re.search(line):
                memories.append(ExtractedMemory(
                    content=line,
                    memory_type="preference",
                    salience=0.7,
                    confidence=0.6
                ))
                continue
            
            # Check for insight patterns
            if self.insight_re.search(line):
                memories.append(ExtractedMemory(
                    content=line,
                    memory_type="insight",
                    salience=0.75,
                    confidence=0.6
                ))
                continue
            
            # Check for goal patterns
            if self.goal_re.search(line):
                memories.append(ExtractedMemory(
                    content=line,
                    memory_type="goal",
                    salience=0.85,
                    confidence=0.7
                ))
                continue
        
        # Filter by confidence
        memories = [m for m in memories if m.confidence >= min_confidence]
        
        # Deduplicate similar memories
        memories = self._deduplicate(memories)
        
        return memories
    
    def _split_into_chunks(self, text: str) -> List[str]:
        """Split text into sentence-like chunks."""
        # Split on newlines, periods, and other sentence boundaries
        chunks = re.split(r'[\n.!?]+', text)
        # Also split on common conversation patterns
        result = []
        for chunk in chunks:
            # Further split on "—" or " - " which often separate thoughts
            sub_chunks = re.split(r'\s*[—–]\s*|\s+-\s+', chunk)
            result.extend(sub_chunks)
        return [c.strip() for c in result if c.strip()]
    
    def _deduplicate(self, memories: List[ExtractedMemory]) -> List[ExtractedMemory]:
        """Remove near-duplicate memories."""
        if len(memories) <= 1:
            return memories
        
        unique = []
        seen_content = set()
        
        for mem in memories:
            # Normalize for comparison
            normalized = mem.content.lower()[:50]
            if normalized not in seen_content:
                seen_content.add(normalized)
                unique.append(mem)
        
        return unique


def extract_memories(text: str, min_confidence: float = 0.3) -> List[ExtractedMemory]:
    """
    Convenience function to extract memories from text.
    
    Args:
        text: Conversation or text to extract from
        min_confidence: Minimum confidence threshold (0-1)
    
    Returns:
        List of ExtractedMemory objects
    """
    extractor = MemoryExtractor()
    return extractor.extract_from_text(text, min_confidence)


# Quick test when run directly
if __name__ == "__main__":
    test_text = """
    Bill wants to build a best-in-class memory system.
    We decided to pivot from the leaderboard to memory.
    The key insight is that agents need continuous identity.
    I prefer semantic search over keyword matching.
    Let's use fastembed for local embeddings.
    The weather is nice today.
    We should test this on real data.
    """
    
    memories = extract_memories(test_text)
    print(f"Extracted {len(memories)} memories:\n")
    for mem in memories:
        print(f"[{mem.memory_type}] (salience: {mem.salience}, conf: {mem.confidence})")
        print(f"  {mem.content}\n")
