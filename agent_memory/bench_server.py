#!/usr/bin/env python3
"""
Lightweight HTTP server for MemoryBench integration.
Wraps agent-memory with a simple REST API that the TS provider can call.

Usage:
    python -m agent_memory.bench_server --port 9876
"""

import argparse
import json
import os
import sys
import tempfile
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_memory.memory import Memory

# Per-container (benchmark run) memory instances
_instances: Dict[str, Memory] = {}
_db_dir = tempfile.mkdtemp(prefix="agent_memory_bench_")


def _get_memory(container_tag: str) -> Memory:
    """Get or create a Memory instance for a container tag."""
    if container_tag not in _instances:
        db_path = os.path.join(_db_dir, f"{container_tag}.db")
        _instances[container_tag] = Memory(db_path)
    return _instances[container_tag]


class BenchHandler(BaseHTTPRequestHandler):
    """HTTP handler for benchmark operations."""
    
    def _send_json(self, data: Any, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def _read_body(self) -> Dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        body = self.rfile.read(length)
        return json.loads(body)
    
    def log_message(self, format, *args):
        # Suppress default logging for cleaner output
        pass
    
    def do_GET(self):
        if self.path == "/health":
            self._send_json({"status": "ok", "provider": "agent-memory"})
        else:
            self._send_json({"error": "Not found"}, 404)
    
    def do_POST(self):
        body = self._read_body()
        
        if self.path == "/ingest":
            self._handle_ingest(body)
        elif self.path == "/search":
            self._handle_search(body)
        elif self.path == "/clear":
            self._handle_clear(body)
        elif self.path == "/stats":
            self._handle_stats(body)
        else:
            self._send_json({"error": "Not found"}, 404)
    
    def _handle_ingest(self, body: Dict):
        """Ingest benchmark sessions into memory."""
        container_tag = body.get("containerTag", "default")
        sessions = body.get("sessions", [])
        mem = _get_memory(container_tag)
        
        doc_ids = []
        for session in sessions:
            session_id = session.get("sessionId", "unknown")
            messages = session.get("messages", [])
            
            # Build conversation text from messages
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                speaker = msg.get("speaker", role)
                timestamp = msg.get("timestamp", "")
                
                # Store each message as a memory
                memory_content = f"[{speaker}]: {content}"
                if timestamp:
                    memory_content = f"[{timestamp}] {memory_content}"
                
                metadata = {
                    "sessionId": session_id,
                    "role": role,
                    "speaker": speaker,
                    "timestamp": timestamp,
                }
                
                mid = mem.add(
                    content=memory_content,
                    memory_type="conversation",
                    salience=0.6,
                    metadata=metadata,
                    detect_relations=True  # Use graph memory
                )
                doc_ids.append(str(mid))
        
        self._send_json({
            "documentIds": doc_ids,
            "count": len(doc_ids)
        })
    
    def _handle_search(self, body: Dict):
        """Search memories."""
        container_tag = body.get("containerTag", "default")
        query = body.get("query", "")
        limit = body.get("limit", 30)
        
        mem = _get_memory(container_tag)
        results = mem.search(query, limit=limit, use_graph=True)
        
        # Format results for the benchmark
        formatted = []
        for r in results:
            formatted.append({
                "memory": r["content"],
                "score": r.get("relevance", 0),
                "metadata": r.get("metadata", {}),
                "created_at": r.get("created_at", ""),
            })
        
        self._send_json({"results": formatted})
    
    def _handle_clear(self, body: Dict):
        """Clear all memories for a container."""
        container_tag = body.get("containerTag", "default")
        
        if container_tag in _instances:
            _instances[container_tag].close()
            del _instances[container_tag]
        
        db_path = os.path.join(_db_dir, f"{container_tag}.db")
        if os.path.exists(db_path):
            os.unlink(db_path)
        
        self._send_json({"status": "cleared"})
    
    def _handle_stats(self, body: Dict):
        """Get memory stats."""
        container_tag = body.get("containerTag", "default")
        mem = _get_memory(container_tag)
        
        stats = mem.stats()
        
        # Add graph stats if available
        try:
            from agent_memory.graph import GraphMemory
            graph = GraphMemory(mem.conn)
            stats["graph"] = graph.stats()
        except Exception:
            pass
        
        self._send_json(stats)


def main():
    parser = argparse.ArgumentParser(description="agent-memory bench server")
    parser.add_argument("--port", type=int, default=9876)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    
    server = HTTPServer((args.host, args.port), BenchHandler)
    print(f"agent-memory bench server running on {args.host}:{args.port}")
    print(f"DB directory: {_db_dir}")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        # Cleanup
        for mem in _instances.values():
            mem.close()
        server.server_close()


if __name__ == "__main__":
    main()
