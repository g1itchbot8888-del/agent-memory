---
name: agent-memory-capture
description: "Auto-capture session context to agent-memory before /new resets"
metadata: {"openclaw": {"emoji": "🧠", "events": ["command:new"]}}
---

# agent-memory-capture

Automatically captures session context to agent-memory when you issue `/new`.

## What It Does

1. Extracts key facts from the session being reset
2. Captures them to agent-memory with proper layering
3. Ensures nothing important is lost on reset

## Requirements

- agent-memory must be installed (`pip install agent-memory`)
- Database path configured (defaults to `~/clawd/agent_memory.db`)

## Configuration

Set database path in hook config:

```json
{
  "hooks": {
    "internal": {
      "entries": {
        "agent-memory-capture": {
          "enabled": true,
          "env": {
            "AGENT_MEMORY_DB": "~/clawd/agent_memory.db"
          }
        }
      }
    }
  }
}
```
