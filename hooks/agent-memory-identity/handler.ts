/**
 * agent-memory-identity hook
 * 
 * Injects identity memories into agent bootstrap context.
 * Runs on agent:bootstrap to add MEMORY_CONTEXT.md to bootstrap files.
 */

import { exec } from "child_process";
import { promisify } from "util";

const execAsync = promisify(exec);

interface BootstrapFile {
  path: string;
  content: string;
  source?: string;
}

interface HookEvent {
  type: string;
  action: string;
  sessionKey: string;
  timestamp: Date;
  messages: string[];
  context: {
    bootstrapFiles?: BootstrapFile[];
    workspaceDir?: string;
    cfg?: unknown;
  };
}

type HookHandler = (event: HookEvent) => Promise<void>;

const handler: HookHandler = async (event) => {
  // Only trigger on bootstrap
  if (event.type !== "agent" || event.action !== "bootstrap") {
    return;
  }

  // Need bootstrapFiles to inject into
  if (!event.context.bootstrapFiles) {
    return;
  }

  const dbPath = process.env.AGENT_MEMORY_DB || "~/clawd/agent_memory.db";
  const expandedPath = dbPath.replace("~", process.env.HOME || "");

  try {
    // Query identity layer memories
    const cmd = `python3 -m agent_memory.tools.recall "who am I, identity, core values, preferences" --db "${expandedPath}" --limit 5 --json 2>/dev/null`;
    
    const { stdout } = await execAsync(cmd, { timeout: 5000 });
    
    let memories: Array<{ memory: string; score: number; layer?: string }> = [];
    try {
      memories = JSON.parse(stdout);
    } catch {
      // No memories or parse error
      return;
    }

    if (memories.length === 0) {
      return;
    }

    // Format as markdown context
    const content = [
      "# Memory Context (Auto-Injected)",
      "",
      "## Identity Memories",
      "",
      ...memories.map((m, i) => `${i + 1}. ${m.memory}`),
      "",
      `_Injected at ${new Date().toISOString()} from agent-memory_`,
    ].join("\n");

    // Add to bootstrap files
    event.context.bootstrapFiles.push({
      path: "MEMORY_CONTEXT.md",
      content,
      source: "agent-memory-identity-hook",
    });

    console.log(`[agent-memory-identity] Injected ${memories.length} identity memories`);
  } catch (err) {
    // Don't block bootstrap on failure
    console.error(
      "[agent-memory-identity] Failed to inject:",
      err instanceof Error ? err.message : String(err)
    );
  }
};

export default handler;
