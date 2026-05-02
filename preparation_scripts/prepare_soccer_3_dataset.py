import json
import sqlite3
from collections import defaultdict
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

raw_file = os.path.join(BASE_DIR, "..", "data", "raw", "test.json")

with open(raw_file, "r") as f:
    data = json.load(f)

filtered = [item for item in data if item.get("db_id") == "soccer_3"]

groups = defaultdict(list)

for item in filtered:
    sql = item["query"].strip()
    groups[sql].append(item["question"].strip())

# connect to database
conn = sqlite3.connect(os.path.join(BASE_DIR, "..", "databases", "soccer_3", "soccer_3.sqlite"))
conn.execute("PRAGMA query_only = ON;")
cursor = conn.cursor()

def execute_sql(sql):
    try:
        cursor.execute(sql)
        rows = cursor.fetchall()

        if not rows:
            return []

        # single value
        if len(rows) == 1 and len(rows[0]) == 1:
            return rows[0][0]

        # single column
        if len(rows[0]) == 1:
            return [r[0] for r in rows]

        # multi column
        return [list(r) for r in rows]

    except Exception as e:
        return str(e)
        
output = {
    "data": []
}

for i, (sql, questions) in enumerate(groups.items()):
    result = execute_sql(sql)

    output["data"].append({
        "id": i,
        "db_id": "soccer_3",
        "questions": questions,
        "sql": sql,
        "result": result
    })

output_path = os.path.join(BASE_DIR, "..", "data", "processed", "soccer_3.json")
os.makedirs(os.path.dirname(output_path), exist_ok=True)

# SAVE
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(output, f, indent=4, ensure_ascii=False)