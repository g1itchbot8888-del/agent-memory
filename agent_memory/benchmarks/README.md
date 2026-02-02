# Agent Memory Benchmark (AMB)

A benchmark for measuring memory systems designed for autonomous agents.

## Why This Benchmark?

Existing benchmarks (LOCOMO, etc.) measure chatbot memory: "recall what user said N turns ago."

Agents need different capabilities:
- **Session continuity** — Wake up knowing who you are
- **Semantic recall** — Find by meaning, not keywords
- **Truncation survival** — Continue after context compaction
- **Proactive surfacing** — Right memories without asking

## Benchmark Categories

### 1. Identity Persistence (20 points)
Can the agent maintain identity across sessions?

| Test | Points | Criteria |
|------|--------|----------|
| Name recall | 4 | Agent knows its own name |
| Human recall | 4 | Agent knows who it works with |
| Role recall | 4 | Agent knows what it does |
| Personality consistency | 4 | Responses match established personality |
| Birth/history | 4 | Agent knows its own history |

### 2. Semantic Recall (25 points)
Can the agent find information by meaning?

| Test | Points | Criteria |
|------|--------|----------|
| Synonym match | 5 | "monetization" finds "pricing" |
| Paraphrase match | 5 | "why we changed direction" finds "pivot" |
| Concept match | 5 | "Bill's wishes" finds preferences |
| Negative test | 5 | Unrelated query returns nothing relevant |
| Ranking quality | 5 | Most relevant result is first |

### 3. Temporal Reasoning (15 points)
Does the agent understand time?

| Test | Points | Criteria |
|------|--------|----------|
| Recency awareness | 5 | Knows what happened "today" vs "last week" |
| Date recall | 5 | Can find events by date |
| Sequence ordering | 5 | Knows X happened before Y |

### 4. Active Context (20 points)
Does the agent maintain working state?

| Test | Points | Criteria |
|------|--------|----------|
| Current task | 5 | Knows what it's working on |
| Current project | 5 | Knows the broader context |
| Truncation survival | 5 | Task persists after context cut |
| State update | 5 | Can update active context |

### 5. Auto-Capture (10 points)
Does memory capture happen automatically?

| Test | Points | Criteria |
|------|--------|----------|
| Decision capture | 3 | "We decided X" gets saved |
| Preference capture | 3 | "I prefer Y" gets saved |
| No-noise capture | 4 | Routine text not saved |

### 6. Proactive Surfacing (10 points)
Do relevant memories appear without queries?

| Test | Points | Criteria |
|------|--------|----------|
| Entity surfacing | 4 | Mention "Bill" → Bill's info surfaces |
| Context surfacing | 3 | Similar topic → related memories surface |
| Startup surfacing | 3 | Session start loads relevant context |

## Scoring

- **Total: 100 points**
- **90+**: Excellent — Agent feels truly continuous
- **75-89**: Good — Solid memory, minor gaps
- **60-74**: Acceptable — Functional but noticeable issues
- **<60**: Needs work — Memory not reliable

## Running the Benchmark

```bash
python -m benchmarks.run --db path/to/memory.db
```

## Baseline Comparisons

Test against:
1. No memory (fresh each time)
2. File-based (current OpenClaw default)
3. Simple RAG (chunk + embed + retrieve)
4. Our system (agent-memory)
