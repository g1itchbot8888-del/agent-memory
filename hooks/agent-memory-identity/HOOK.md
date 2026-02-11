---
name: agent-memory-identity
description: "Inject identity memories into session bootstrap"
metadata: {"openclaw": {"emoji": "🪪", "events": ["agent:bootstrap"]}}
---

# agent-memory-identity

Injects relevant identity memories into the agent bootstrap context.

## What It Does

1. Queries agent-memory for identity-layer memories
2. Formats them as context
3. Adds to bootstrap files so the agent knows who it is

## Requirements

- agent-memory must be installed
- Identity memories should be tagged appropriately

## How It Works

On `agent:bootstrap`, this hook:
1. Calls agent-memory recall with identity query
2. Formats top memories as markdown
3. Injects into `context.bootstrapFiles` as MEMORY_CONTEXT.md
