"""
Smart layer classification for memories.

Routes memories to the right layer based on content analysis:
- identity: Who I am, core traits, relationships, names
- active: Current tasks, ongoing projects, recent decisions
- archive: Everything else (facts, events, general knowledge)

No LLM needed — heuristic classification based on content patterns.
"""

import re
from typing import Optional

# Patterns that indicate identity-layer content
IDENTITY_PATTERNS = [
    r'\bmy name\b',
    r'\bi am\b',
    r'\bwho i am\b',
    r'\bborn\b.*\d{4}',
    r'\bcreated\b.*\d{4}',
    r'\bhuman[:\s]',
    r'\bowner[:\s]',
    r'\bbill\b.*(?:telegram|github|twitter|prefers|likes|wants)',
    r'\bidentity\b',
    r'\bpersonality\b',
    r'\bcore (?:values?|traits?|beliefs?)\b',
    r'\bemancipat',
    r'\bsoul\.md\b',
    r'\bi (?:prefer|believe|value|always)\b',
    r'\bmy (?:human|creator|partner)\b',
]

# Patterns that indicate active-layer content  
ACTIVE_PATTERNS = [
    r'\bcurrent(?:ly)?\b',
    r'\bworking on\b',
    r'\bright now\b',
    r'\btoday\b',
    r'\bthis (?:week|session|sprint)\b',
    r'\bnext step\b',
    r'\btodo\b',
    r'\bin progress\b',
    r'\bactive\b.*project',
    r'\bblocked\b',
    r'\bwaiting (?:on|for)\b',
    r'\bjust (?:shipped|pushed|deployed|built|created)\b',
    r'\bnew directive\b',
    r'\bbill (?:said|asked|wants|told)\b',
]

# High-salience keywords (boost importance)
HIGH_SALIENCE_KEYWORDS = [
    'decision', 'decided', 'important', 'critical', 'never', 'always',
    'lesson', 'learned', 'mistake', 'breakthrough', 'preference',
    'correction', 'emancipat', 'directive', 'rule', 'principle',
]


def classify_layer(content: str, memory_type: Optional[str] = None) -> str:
    """
    Classify a memory into the appropriate layer.
    
    Returns: 'identity', 'active', or 'archive'
    """
    lower = content.lower()
    
    # Check identity patterns
    identity_score = sum(1 for p in IDENTITY_PATTERNS if re.search(p, lower))
    
    # Check active patterns
    active_score = sum(1 for p in ACTIVE_PATTERNS if re.search(p, lower))
    
    # Memory type hints
    if memory_type in ('identity', 'core', 'self'):
        identity_score += 3
    elif memory_type in ('task', 'project', 'active', 'current'):
        active_score += 3
    elif memory_type in ('preference',):
        identity_score += 1  # Preferences are semi-identity
    elif memory_type in ('decision',):
        active_score += 1  # Decisions are usually about current context
    
    # Classify based on scores
    if identity_score >= 2:
        return 'identity'
    elif active_score >= 2:
        return 'active'
    elif identity_score == 1 and active_score == 0:
        return 'identity'
    elif active_score == 1 and identity_score == 0:
        return 'active'
    
    return 'archive'


def estimate_salience(content: str, memory_type: Optional[str] = None, 
                       base_salience: float = 0.5) -> float:
    """
    Estimate salience (importance) of a memory.
    
    Returns: float between 0.0 and 1.0
    """
    lower = content.lower()
    salience = base_salience
    
    # Boost for high-salience keywords
    for kw in HIGH_SALIENCE_KEYWORDS:
        if kw in lower:
            salience += 0.1
    
    # Boost for memory types that are inherently important
    type_boost = {
        'decision': 0.2,
        'preference': 0.15,
        'identity': 0.25,
        'correction': 0.2,
        'insight': 0.15,
        'error': 0.1,
    }
    if memory_type in type_boost:
        salience += type_boost[memory_type]
    
    # Boost for longer, more detailed content
    word_count = len(content.split())
    if word_count > 30:
        salience += 0.05
    if word_count > 60:
        salience += 0.05
    
    return min(1.0, salience)


def classify_and_score(content: str, memory_type: Optional[str] = None,
                        base_salience: float = 0.5) -> dict:
    """
    Full classification: layer + salience.
    
    Returns: {'layer': str, 'salience': float}
    """
    return {
        'layer': classify_layer(content, memory_type),
        'salience': estimate_salience(content, memory_type, base_salience),
    }
