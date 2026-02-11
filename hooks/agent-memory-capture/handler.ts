/**
 * agent-memory-capture hook
 * 
 * Auto-captures session context to agent-memory before /new resets.
 * Calls the Python capture tool via subprocess.
 */

import { exec } from "child_process";
import { promisify } from "util";

const execAsync = promisify(exec);

// Type stub for OpenClaw HookHandler (will be provided by OpenClaw at runtime)
interface HookEvent {
  type: string;
  action: string;
  sessionKey: string;
  timestamp: Date;
  messages: string[];
  context: {
    sessionEntry?: unknown;
    sessionId?: string;
    workspaceDir?: string;
    cfg?: unknown;
  };
}

type HookHandler = (event: HookEvent) => Promise<void>;

const handler: HookHandler = async (event) => {
  // Only trigger on 'new' command (before reset)
  if (event.type !== "command" || event.action !== "new") {
    return;
  }

  const dbPath = process.env.AGENT_MEMORY_DB || "~/clawd/agent_memory.db";
  const expandedPath = dbPath.replace("~", process.env.HOME || "");

  try {
    // Extract session info for capture
    const sessionKey = event.sessionKey;
    const timestamp = event.timestamp.toISOString();
    
    // Capture session reset event
    const facts = [
      `Session reset initiated at ${timestamp}`,
      `Session key: ${sessionKey}`,
    ];

    // Call agent-memory capture
    const factsArgs = facts.map(f => `--facts "${f.replace(/"/g, '\\"')}"`).join(" ");
    const cmd = `python3 -m agent_memory.tools.capture --db "${expandedPath}" ${factsArgs}`;
    
    await execAsync(cmd, { timeout: 10000 });
    
    console.log(`[agent-memory-capture] Captured session context for ${sessionKey}`);
  } catch (err) {
    // Don't block the reset on capture failure
    console.error(
      "[agent-memory-capture] Failed to capture:",
      err instanceof Error ? err.message : String(err)
    );
  }
};

export default handler;
