# agent-memory Provider for MemoryBench

TypeScript provider wrapper for running agent-memory in [MemoryBench](https://github.com/supermemoryai/memorybench).

## Setup

### 1. Start the agent-memory bench server

```bash
cd /path/to/agent-memory
python -m agent_memory.bench_server --port 9876
```

### 2. Copy provider to memorybench

```bash
# Clone memorybench if needed
git clone https://github.com/supermemoryai/memorybench
cd memorybench

# Copy provider
mkdir -p src/providers/agent-memory
cp /path/to/agent-memory/ts-provider/index.ts src/providers/agent-memory/

# Register in src/providers/index.ts
# Add: export { AgentMemoryProvider } from "./agent-memory"

# Add to ProviderName type in src/types/provider.ts
# Add "agent-memory" to the union

# Add config in src/utils/config.ts
```

### 3. Run benchmarks

```bash
bun run benchmark --provider agent-memory
```

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `baseUrl` | `http://127.0.0.1:9876` | URL of the bench server |

## How It Works

The provider calls the HTTP bench server which wraps agent-memory's core functionality:

- **ingest** → stores conversation sessions as memories with graph relations
- **search** → semantic search with graph-enhanced retrieval
- **clear** → removes memories for a specific benchmark run

Each benchmark run gets its own isolated database (containerTag).
