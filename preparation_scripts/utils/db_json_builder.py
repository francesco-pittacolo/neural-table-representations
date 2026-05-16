import sqlite3
import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

def export_database(conn, output_path):
    db_json = {"tables": {}}

    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table';"
    ).fetchall()

    for (table,) in tables:
        cursor = conn.execute(f"SELECT * FROM {table}")
        cols = [desc[0] for desc in cursor.description]

        rows = [
            dict(zip(cols, row))
            for row in cursor.fetchall()
        ]

        db_json["tables"][table] = rows

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(db_json, f, indent=2, ensure_ascii=False)