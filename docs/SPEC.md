# Technical Specification

## Overview

agent-memory is a hierarchical memory system for autonomous agents. It provides:
- **Identity persistence** across sessions
- **Semantic recall** by meaning, not keywords
- **Auto-capture** without manual tagging
- **Local-first** storage with no cloud dependencies

## Core Concepts

### Memory Layers

| Layer | Size | Loading | Purpose |
|-------|------|---------|---------|
| Identity | ~200 tokens | Always loaded | Who am I, who is my human |
| Active | ~500 tokens | Always loaded | Current task, hot context |
| Surfaced | Variable | On relevance | Memories relevant to current context |
| Archive | Unlimited | On search | Full history, compressed over time |

### Memory Types

| Type | Salience | Description |
|------|----------|-------------|
| decision | 0.8 | Choices made, directions taken |
| preference | 0.7 | Likes, dislikes, how things should be |
| insight | 0.75 | Realizations, learnings |
| goal | 0.85 | Objectives, targets |
| fact | 0.5-0.6 | General information |
| long_term | 0.7 | Curated long-term memories |
| daily | 0.5 | Daily log entries |

### Salience Scoring

Salience (0.0-1.0) indicates importance:
- 0.9+: Critical (goals, major decisions)
- 0.7-0.8: Important (decisions, preferences)
- 0.5-0.6: Normal (facts, daily logs)
- <0.5: Low (routine, may be pruned)

## API Reference

### Memory Class

```python
from src.memory import Memory

mem = Memory("agent_memory.db")

# Identity (always loaded)
mem.set_identity("name", "g1itchbot")
mem.get_identity()  # → {"name": "g1itchbot"}
mem.get_identity_context()  # → "# Identity\n- name: g1itchbot"

# Active context (current task)
mem.set_active("task", "Building memory system")
mem.get_active()
mem.get_active_context()

# Archive (searchable memories)
mem.add("Some fact", memory_type="fact", salience=0.6)
mem.search("query", limit=5, min_salience=0.3)

# Startup
mem.get_startup_context()  # Identity + Active formatted

# Stats
mem.stats()  # → {"memories": 324, "identity_keys": 3, ...}
```

### Extraction

```python
from src.extract import extract_memories

text = "We decided to pivot to memory. I prefer local solutions."
memories = extract_memories(text, min_confidence=0.5)
# → [ExtractedMemory(content="We decided...", type="decision", ...)]
```

### CLI Tools

```bash
# Generate startup context
python -m src.tools.startup --db agent_memory.db

# Manual capture
python -m src.tools.capture "Some fact" --db agent_memory.db
python -m src.tools.capture --facts "Fact 1" "Fact 2"
python -m src.tools.capture --decision "We chose X"

# Semantic search
python -m src.tools.recall "what did we decide about pricing"

# Auto-capture from text
python -m src.tools.auto_capture "conversation text here"
echo "text" | python -m src.tools.auto_capture --stdin
```

## Database Schema

### memories
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| content | TEXT | Memory content |
| layer | TEXT | archive (default) |
| memory_type | TEXT | fact, decision, etc. |
| salience | REAL | 0.0-1.0 importance |
| created_at | TEXT | ISO timestamp |
| updated_at | TEXT | ISO timestamp |
| accessed_at | TEXT | Last access time |
| access_count | INTEGER | Times retrieved |
| metadata | TEXT | JSON metadata |

### identity
| Column | Type | Description |
|--------|------|-------------|
| key | TEXT | Primary key |
| value | TEXT | Identity value |
| updated_at | TEXT | ISO timestamp |

### active_context
| Column | Type | Description |
|--------|------|-------------|
| key | TEXT | Primary key |
| value | TEXT | Context value |
| updated_at | TEXT | ISO timestamp |

### memory_embeddings (virtual table)
| Column | Type | Description |
|--------|------|-------------|
| memory_id | INTEGER | FK to memories |
| embedding | FLOAT[384] | Vector embedding |

## Embedding Model

- **Model**: BAAI/bge-small-en-v1.5
- **Dimension**: 384
- **Library**: fastembed
- **Local**: Yes, no API required

## Extraction Patterns

### Decisions
- "we decided/agreed/chose/will/should/going to"
- "let's"
- "the plan is"

### Preferences
- "prefer/like/love/want/don't like/hate"
- "better/best/favorite/rather"

### Insights
- "the key/important/insight/learned/realized"
- "turns out"
- "the problem/issue/challenge/opportunity is"

### Goals
- "goal/objective/target/aim is"
- "we're building/creating/making/trying to"
- "the vision is"

## Future: Consolidation (Phase 5)

Planned consolidation strategy:
1. **Compression**: After N days, summarize detailed logs
2. **Merging**: Combine semantically similar memories
3. **Pruning**: Remove low-salience, never-accessed memories
4. **Contradiction resolution**: Update rather than duplicate

## Future: Predictive Surfacing (Phase 6)

Planned approach:
1. Analyze current context
2. Identify likely-needed memories
3. Pre-load into surfaced layer
4. Update as conversation evolves
