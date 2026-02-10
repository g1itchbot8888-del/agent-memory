/**
 * agent-memory provider for MemoryBench
 * 
 * Connects to the agent-memory HTTP bench server.
 * 
 * Prerequisites:
 *   python -m agent_memory.bench_server --port 9876
 */

import type { Provider, ProviderConfig, IngestOptions, IngestResult, SearchOptions } from "../types/provider";
import type { UnifiedSession } from "../types/session";

interface AgentMemoryConfig extends ProviderConfig {
    baseUrl?: string;
}

interface SearchResult {
    memory: string;
    score: number;
    metadata: Record<string, unknown>;
    created_at: string;
}

export class AgentMemoryProvider implements Provider {
    name = "agent-memory";
    private baseUrl: string = "http://127.0.0.1:9876";

    async initialize(config: AgentMemoryConfig): Promise<void> {
        if (config.baseUrl) {
            this.baseUrl = config.baseUrl;
        }

        // Check health
        const res = await fetch(`${this.baseUrl}/health`);
        if (!res.ok) {
            throw new Error(`agent-memory server not healthy: ${res.status}`);
        }
        const data = await res.json();
        console.log(`Connected to ${data.provider}`);
    }

    async ingest(sessions: UnifiedSession[], options: IngestOptions): Promise<IngestResult> {
        const containerTag = options.containerTag || "default";

        const res = await fetch(`${this.baseUrl}/ingest`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                containerTag,
                sessions: sessions.map(s => ({
                    sessionId: s.sessionId,
                    messages: s.messages.map(m => ({
                        role: m.role,
                        content: m.content,
                        speaker: m.speaker || m.role,
                        timestamp: m.timestamp || "",
                    })),
                })),
            }),
        });

        if (!res.ok) {
            throw new Error(`Ingest failed: ${res.status}`);
        }

        const data = await res.json();
        return {
            documentIds: data.documentIds || [],
        };
    }

    async awaitIndexing(result: IngestResult, containerTag: string): Promise<void> {
        // agent-memory indexes synchronously during ingest, no waiting needed
        // But we do a quick stats check to confirm data is there
        await fetch(`${this.baseUrl}/stats`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ containerTag }),
        });
    }

    async search(query: string, options: SearchOptions): Promise<SearchResult[]> {
        const containerTag = options.containerTag || "default";
        const limit = options.limit || 30;

        const res = await fetch(`${this.baseUrl}/search`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                containerTag,
                query,
                limit,
            }),
        });

        if (!res.ok) {
            throw new Error(`Search failed: ${res.status}`);
        }

        const data = await res.json();
        return data.results || [];
    }

    async clear(containerTag: string): Promise<void> {
        const res = await fetch(`${this.baseUrl}/clear`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ containerTag }),
        });

        if (!res.ok) {
            throw new Error(`Clear failed: ${res.status}`);
        }
    }
}

export default AgentMemoryProvider;
