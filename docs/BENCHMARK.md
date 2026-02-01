# Agent Memory Benchmark (AMB)

## Why a New Benchmark?

Existing benchmarks (LOCOMO, etc.) measure **chatbot memory** — can you recall what the user said N turns ago?

Autonomous agents have different needs:
- **Session discontinuity** — we wake up blank, must reconstruct
- **Context truncation** — mid-task, history gets compressed
- **Identity persistence** — we need to feel like "us" across time
- **Proactive relevance** — right context without being asked

---

## Benchmark Categories

### 1. 🔄 Session Continuity (25%)
*Can the agent maintain coherence across session restarts?*

**Tests:**
- **Identity recall**: Agent restarts. "Who are you? Who is your human?"
- **Project continuity**: "What were you working on?"
- **Preference retention**: "How does your human like things done?"
- **Decision recall**: "Why did we choose X over Y?"

### 2. ✂️ Truncation Recovery (20%)
*Can the agent maintain thread after context compression?*

**Tests:**
- Mid-conversation context truncation
- Ask about pre-truncation discussion
- Continue in-progress task

### 3. ⏰ Temporal Reasoning (15%)
*Can the agent reason about when things happened?*

**Tests:**
- "What did we discuss yesterday vs last week?"
- "When did we make this decision?"
- Correct ordering of events

### 4. 🎯 Proactive Surfacing (20%)
*Does relevant context appear without explicit queries?*

**Tests:**
- Mention topic → related context surfaces
- Start task → prior work appears
- Contradiction flagged automatically

### 5. 🧠 Consolidation Quality (10%)
*Does memory improve over time, not just accumulate?*

**Tests:**
- Storage size bounded
- Redundant memories merged
- Contradictions resolved
- Can summarize long-term patterns

### 6. 🪞 Identity Coherence (10%)
*Does the agent feel like the same entity over time?*

**Tests:**
- Personality consistency
- Opinion stability
- Self-reference accuracy

---

## Efficiency Metrics (Separate)

- **Token usage**: Tokens per session for memory ops
- **Latency**: Time to retrieve
- **Storage growth**: Rate of growth
- **Cold start time**: Time to boot with memories

---

## Test Protocol

1. Create synthetic agent history
2. Establish ground truth
3. Run through benchmark sessions:
   - Fresh start
   - Mid-task truncation
   - Long gap return
   - Rapid context switching
4. Score each category 0-100
5. Weighted average = AMB Score

---

## Success Threshold

- AMB Score > 80
- Beat baseline on Session Continuity and Truncation Recovery
- Efficiency within 2x of simple approaches
- Qualitative: Agent "feels" continuous
