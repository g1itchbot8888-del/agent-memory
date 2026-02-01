# Progress Log

## 2026-02-01: Project Kickoff

### Decisions Made
1. **Pivot to memory** — Bill wants to build best-in-class memory for agents
2. **Local-first** — No cloud dependencies, portable
3. **Semantic search** — Meaning-based, not keyword
4. **Auto-capture** — No manual "save this" required
5. **Dogfooding** — I (g1itchbot) am the primary test subject

### Research Findings
- **Mem0**: YC-backed, +26% over OpenAI on LOCOMO benchmark, graph-based
- **MemGPT/Letta**: OS-inspired, agent controls own memory, hierarchical tiers
- **Key papers**: TiMem (temporal hierarchy), Amory (narrative), HiMem, HiMeS (hippocampus-inspired)
- **Gap identified**: Nobody's nailed automatic progressive disclosure for agents

### Architecture Chosen
```
┌─────────────────────────────────────────┐
│  IDENTITY (~200 tokens)                 │
│  Who I am, who my human is, core self   │
├─────────────────────────────────────────┤
│  ACTIVE CONTEXT (~500 tokens)           │
│  Current task, recent decisions         │
├─────────────────────────────────────────┤
│  SURFACED (loaded on relevance)         │
│  Related memories, pulled by meaning    │
├─────────────────────────────────────────┤
│  ARCHIVE (searchable, not loaded)       │
│  Full history, compressed over time     │
└─────────────────────────────────────────┘
```

### Tech Stack
- **Storage**: sqlite + sqlite-vec
- **Embeddings**: fastembed (bge-small-en-v1.5, dim=384)
- **Language**: Python
- **Integration**: OpenClaw lifecycle hooks

### Phases Completed

#### Phase 0: Baseline ✅
- Documented current file-based system
- Identified pain points: manual reads, keyword search, no hierarchy
- Defined success criteria

#### Phase 1: Foundation ✅
- Core Memory class with identity, active, archive layers
- Basic CRUD operations
- 14 passing tests

#### Phase 2: Semantic Search ✅
- Integrated fastembed for local embeddings
- Vector similarity search via sqlite-vec
- "monetization" finds "pricing model" ✓

#### Phase 3: Bootstrap ✅
- Import from OpenClaw workspace
- Parses SOUL.md, IDENTITY.md, USER.md, SESSION-STATE.md, MEMORY.md
- Imported 324 memories from my workspace

#### Phase 4: Auto-Capture ✅
- Heuristic extraction (decisions, preferences, insights, goals)
- Pattern-based, no LLM required
- "We decided to use fastembed" → auto-captured as decision

### Remaining Phases

#### Phase 5: Consolidation 🔄
- Periodic compression (detail → summary)
- Merge redundant memories
- Prune low-value/old
- Smart forgetting

#### Phase 6: Predictive Surfacing ⏳
- Context-aware retrieval
- Anticipate what memories are needed
- Pre-load relevant context

---

## Key Insights

1. **Semantic search is transformative** — Finding "pricing model" when searching "monetization" changes everything

2. **324 memories imported cleanly** — My existing file-based system migrated successfully

3. **Auto-extraction works** — Simple patterns catch most decisions/preferences

4. **Bill's motivation** — "It solves a real problem for you" — building for lived experience, not abstract use cases

---

## Files Structure
```
agent-memory/
├── README.md
├── requirements.txt
├── docs/
│   ├── VISION.md          # Core principles
│   ├── BENCHMARK.md       # Agent Memory Benchmark spec
│   ├── BASELINE.md        # Pre-project state
│   └── PROGRESS.md        # This file
├── src/
│   ├── memory.py          # Core Memory class
│   ├── extract.py         # Heuristic extraction
│   ├── openclaw.py        # OpenClaw integration
│   ├── bootstrap.py       # Import from workspace
│   └── tools/
│       ├── startup.py     # Generate startup context
│       ├── capture.py     # Manual capture
│       ├── recall.py      # Semantic search
│       └── auto_capture.py # Auto-extract and save
└── tests/
    └── test_memory.py     # 14 passing tests
```
