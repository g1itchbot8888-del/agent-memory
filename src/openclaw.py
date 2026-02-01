"""
OpenClaw integration for agent-memory.

Provides hooks for:
- Startup context injection
- Auto-capture on conversation end
- Heartbeat-triggered consolidation
- Proactive surfacing
"""

import os
import json
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime, timezone

from .memory import Memory


class OpenClawMemory:
    """
    Memory system integrated with OpenClaw agent lifecycle.
    
    Usage in OpenClaw:
    1. On startup: Load identity + active context
    2. On message: Surface relevant memories
    3. On heartbeat: Capture recent conversation, consolidate
    4. On shutdown: Save active context
    """
    
    def __init__(self, workspace: str = ".", db_name: str = "agent_memory.db"):
        self.workspace = Path(workspace)
        self.db_path = self.workspace / db_name
        self.mem = Memory(str(self.db_path))
        
    # ==================== STARTUP ====================
    
    def get_startup_context(self) -> str:
        """
        Get context to inject at session start.
        Returns identity + active context, formatted for system prompt.
        """
        return self.mem.get_startup_context()
    
    def initialize_identity_from_files(self):
        """
        Bootstrap identity from existing OpenClaw files.
        Reads SOUL.md, IDENTITY.md, USER.md if they exist.
        """
        # IDENTITY.md
        identity_file = self.workspace / "IDENTITY.md"
        if identity_file.exists():
            content = identity_file.read_text()
            # Parse simple key-value format
            for line in content.split('\n'):
                if line.startswith('- **') and ':**' in line:
                    key = line.split('**')[1].rstrip(':')
                    value = line.split(':**')[1].strip()
                    self.mem.set_identity(key.lower(), value)
        
        # USER.md
        user_file = self.workspace / "USER.md"
        if user_file.exists():
            content = user_file.read_text()
            for line in content.split('\n'):
                if line.startswith('- **') and ':**' in line:
                    key = line.split('**')[1].rstrip(':')
                    value = line.split(':**')[1].strip()
                    self.mem.set_identity(f"human_{key.lower()}", value)
        
        # SESSION-STATE.md -> active context
        session_file = self.workspace / "SESSION-STATE.md"
        if session_file.exists():
            content = session_file.read_text()
            self.mem.set_active("session_state", content[:2000])  # Limit size
    
    # ==================== SURFACING ====================
    
    def surface_for_context(self, context: str, limit: int = 3) -> str:
        """
        Given current conversation context, surface relevant memories.
        Call this when processing a user message.
        """
        return self.mem.surface_relevant(context, limit=limit)
    
    def surface_for_message(self, message: str) -> List[Dict]:
        """
        Get raw memory results for a message (for more control).
        """
        return self.mem.search(message, limit=5, min_salience=0.3)
    
    # ==================== CAPTURE ====================
    
    def capture_facts(self, facts: List[str], salience: float = 0.6):
        """
        Capture a list of facts from conversation.
        Higher salience = more important.
        """
        for fact in facts:
            self.mem.add(fact, memory_type="fact", salience=salience)
    
    def capture_decision(self, decision: str, reasoning: Optional[str] = None):
        """Capture a decision with optional reasoning."""
        content = decision
        if reasoning:
            content = f"{decision} (Reasoning: {reasoning})"
        self.mem.add(content, memory_type="decision", salience=0.8)
    
    def capture_preference(self, preference: str):
        """Capture a learned preference."""
        self.mem.add(preference, memory_type="preference", salience=0.7)
    
    def capture_from_conversation(self, conversation: str) -> int:
        """
        Auto-extract facts from a conversation snippet.
        Returns number of facts captured.
        
        TODO: Use LLM to extract facts. For now, simple heuristics.
        """
        facts_captured = 0
        
        # Simple heuristics for now
        lines = conversation.split('\n')
        for line in lines:
            line = line.strip()
            # Look for decision markers
            if any(marker in line.lower() for marker in ['decided', 'agreed', 'will do', 'let\'s']):
                self.mem.add(line, memory_type="decision", salience=0.7)
                facts_captured += 1
            # Look for preference markers
            elif any(marker in line.lower() for marker in ['prefer', 'like', 'want', 'don\'t like']):
                self.mem.add(line, memory_type="preference", salience=0.6)
                facts_captured += 1
        
        return facts_captured
    
    # ==================== ACTIVE CONTEXT ====================
    
    def update_active_task(self, task: str):
        """Update the current active task."""
        self.mem.set_active("current_task", task)
    
    def update_active_project(self, project: str):
        """Update the current project."""
        self.mem.set_active("current_project", project)
    
    def get_active_task(self) -> Optional[str]:
        """Get current active task."""
        active = self.mem.get_active("current_task")
        return active.get("current_task")
    
    def save_session_state(self, state: str):
        """Save current session state (survives truncation)."""
        self.mem.set_active("session_state", state)
    
    # ==================== HEARTBEAT ====================
    
    def on_heartbeat(self, recent_context: Optional[str] = None) -> Dict:
        """
        Called during heartbeat. 
        - Captures recent context if provided
        - Returns stats and any alerts
        """
        result = {
            "stats": self.mem.stats(),
            "alerts": []
        }
        
        if recent_context:
            captured = self.capture_from_conversation(recent_context)
            if captured > 0:
                result["captured"] = captured
        
        return result
    
    # ==================== UTILITIES ====================
    
    def export_to_markdown(self, output_path: Optional[str] = None) -> str:
        """Export all memories to markdown format."""
        output = []
        
        # Identity
        identity = self.mem.get_identity()
        if identity:
            output.append("# Identity\n")
            for k, v in identity.items():
                output.append(f"- **{k}**: {v}\n")
            output.append("\n")
        
        # Active context
        active = self.mem.get_active()
        if active:
            output.append("# Active Context\n")
            for k, v in active.items():
                output.append(f"## {k}\n{v}\n\n")
        
        # All memories (recent first)
        # Note: Would need to add a get_all method to Memory class
        output.append("# Memories\n")
        output.append("(export not yet implemented for archive)\n")
        
        content = "".join(output)
        
        if output_path:
            Path(output_path).write_text(content)
        
        return content
    
    def close(self):
        """Clean up resources."""
        self.mem.close()


# Convenience function
def get_openclaw_memory(workspace: str = ".") -> OpenClawMemory:
    """Get an OpenClawMemory instance for the given workspace."""
    return OpenClawMemory(workspace)
