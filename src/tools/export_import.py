#!/usr/bin/env python3
"""
Export and import memory database to/from JSON.

Useful for:
- Backing up to GitHub (human-readable, diffable)
- Migrating between systems
- Debugging/inspecting memories

Usage:
    # Export
    python -m src.tools.export_import export --db agent_memory.db --output backup.json
    
    # Import
    python -m src.tools.export_import import --db new_memory.db --input backup.json
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.memory import Memory


def export_database(db_path: str, output_path: str, include_embeddings: bool = False):
    """Export memory database to JSON."""
    mem = Memory(db_path)
    cursor = mem.conn.cursor()
    
    export_data = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "version": "1.0",
        "stats": mem.stats(),
        "identity": mem.get_identity(),
        "active_context": mem.get_active(),
        "memories": []
    }
    
    # Export all memories
    cursor.execute("""
        SELECT id, content, layer, memory_type, salience, 
               created_at, updated_at, accessed_at, access_count, metadata
        FROM memories
        ORDER BY created_at DESC
    """)
    
    for row in cursor.fetchall():
        memory = {
            "id": row[0],
            "content": row[1],
            "layer": row[2],
            "type": row[3],
            "salience": row[4],
            "created_at": row[5],
            "updated_at": row[6],
            "accessed_at": row[7],
            "access_count": row[8],
            "metadata": json.loads(row[9]) if row[9] else None
        }
        export_data["memories"].append(memory)
    
    mem.close()
    
    # Write to file
    with open(output_path, 'w') as f:
        json.dump(export_data, f, indent=2)
    
    return len(export_data["memories"])


def import_database(input_path: str, db_path: str, merge: bool = False):
    """Import memories from JSON to database."""
    
    with open(input_path, 'r') as f:
        import_data = json.load(f)
    
    if not merge and Path(db_path).exists():
        Path(db_path).unlink()
    
    mem = Memory(db_path)
    imported = 0
    
    # Import identity
    for key, value in import_data.get("identity", {}).items():
        mem.set_identity(key, value)
    
    # Import active context
    for key, value in import_data.get("active_context", {}).items():
        mem.set_active(key, value)
    
    # Import memories
    for memory in import_data.get("memories", []):
        mem.add(
            memory["content"],
            memory_type=memory.get("type", "fact"),
            salience=memory.get("salience", 0.5),
            metadata=memory.get("metadata")
        )
        imported += 1
    
    mem.close()
    return imported


def main():
    parser = argparse.ArgumentParser(description="Export/Import memory database")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Export command
    export_parser = subparsers.add_parser("export", help="Export to JSON")
    export_parser.add_argument("--db", required=True, help="Database path")
    export_parser.add_argument("--output", "-o", required=True, help="Output JSON file")
    
    # Import command
    import_parser = subparsers.add_parser("import", help="Import from JSON")
    import_parser.add_argument("--db", required=True, help="Database path")
    import_parser.add_argument("--input", "-i", required=True, help="Input JSON file")
    import_parser.add_argument("--merge", action="store_true", help="Merge with existing")
    
    args = parser.parse_args()
    
    if args.command == "export":
        count = export_database(args.db, args.output)
        print(f"✓ Exported {count} memories to {args.output}")
    
    elif args.command == "import":
        count = import_database(args.input, args.db, merge=args.merge)
        print(f"✓ Imported {count} memories to {args.db}")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
