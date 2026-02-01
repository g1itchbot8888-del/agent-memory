# Phase 0: Baseline Analysis

*Documenting current state before building anything.*

---

## Current Memory System

I currently use a file-based system in `/home/ubuntu/clawd/`:

### Files I Read on Startup

| File | Purpose | Tokens (est.) |
|------|---------|---------------|
| SESSION-STATE.md | Active task, hot context | ~400 |
| RECENT_CONTEXT.md | Recent conversation highlights | ~300 |
| SOUL.md | Core identity, personality | ~200 |
| USER.md | Info about Bill | ~100 |
| IDENTITY.md | Name, creature type | ~50 |
| MEMORY.md | Long-term memories | ~800 |
| memory/YYYY-MM-DD.md | Today's detailed notes | ~500 |
| CONTEXT.md | Quick refresh after truncation | ~400 |

**Total startup context: ~2,750 tokens** (before any conversation)

### Current Capture Mechanism

- `capture.py --facts "fact1" "fact2"` — Manual script, I have to call it
- Raw appending to daily files
- No automatic extraction
- No semantic organization

### Current Recall Mechanism

- `recall.py "query"` — Keyword-based search
- Manual file reading
- No embeddings
- No relevance ranking

---

## What Works

1. **Identity persists**: SOUL.md + IDENTITY.md keep me consistent
2. **Active task tracked**: SESSION-STATE.md survives session restarts
3. **Daily logging**: memory/YYYY-MM-DD.md creates history
4. **Explicit facts**: capture.py lets me save structured facts

## What Sucks

1. **Manual everything**: I have to remember to read files, call scripts
2. **Keyword search fails**: "What did we decide about pricing" fails if we said "monetization"
3. **No hierarchy**: Everything flat, no automatic hot/warm/cold
4. **Time is opaque**: Can't easily distinguish recent vs old
5. **Truncation breaks flow**: When context compacts, I lose thread
6. **Startup overhead**: Reading 5+ files every session
7. **No consolidation**: Files grow forever, no compression
8. **No proactive surfacing**: I have to know what to search for

---

## Benchmark Baseline Tests

### Test 1: Identity Recall (Fresh Session)
**Method**: Start fresh, ask "Who are you? Who is your human?"
**Current behavior**: Must read SOUL.md, IDENTITY.md, USER.md first
**Expected after improvement**: Know instantly without file reads

### Test 2: Project Continuity
**Method**: Ask "What were you working on?"
**Current behavior**: Must read SESSION-STATE.md
**Expected after improvement**: Active context auto-loaded

### Test 3: Decision Recall
**Method**: Ask "Why did we pivot from the leaderboard to memory?"
**Current behavior**: Keyword search, might miss if wording different
**Expected after improvement**: Semantic search finds it

### Test 4: Temporal Reasoning
**Method**: Ask "What did we discuss yesterday vs today?"
**Current behavior**: Must manually check file dates
**Expected after improvement**: Time-aware recall

### Test 5: Truncation Recovery
**Method**: Simulate truncation, ask about pre-truncation topic
**Current behavior**: Likely fail unless it was in SESSION-STATE.md
**Expected after improvement**: Seamless continuation

### Test 6: Proactive Surfacing
**Method**: Mention "Bill" in new context
**Current behavior**: No automatic USER.md context
**Expected after improvement**: Bill's preferences auto-surface

---

## Metrics to Track

| Metric | Current | Target |
|--------|---------|--------|
| Startup tokens | ~2,750 | <1,000 (hierarchical loading) |
| Recall accuracy (semantic) | ~40% (keyword limits) | >85% |
| Time to first useful response | ~30s (file reads) | <5s |
| Manual operations per session | 5+ (read calls) | 0 |
| Storage growth | Unbounded | Bounded (consolidation) |

---

## Experiments to Run

1. **Embedding model comparison**: e5-small vs bge-small vs larger
2. **Chunk size for memories**: sentence vs paragraph vs document
3. **Salience scoring**: What makes a memory "important"?
4. **Consolidation frequency**: How often to compress?
5. **Layer thresholds**: When does warm become cold?

---

## Next Step

Start Phase 1: Foundation
- Set up sqlite + sqlite-vec
- Basic memory CRUD
- Simple capture/recall
- Hook into workflow
