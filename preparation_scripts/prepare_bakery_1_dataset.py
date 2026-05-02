import json
import re
import os
import sqlite3
from collections import defaultdict

# Script to parse questions and relative sql queries from a txt file (see data/raw/bakery_1_michi.txt)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
raw_file_path = os.path.join(BASE_DIR, "..", "data", "raw", "bakery_1_michi.txt")

raw = open(raw_file_path, "r", encoding="utf-8").read().splitlines()

data = []
id_counter = 0

current_question = None
current_sql = []
mode = None

def is_sql(line):
    return line.lower().startswith(
        ("select", "from", "where", "group", "order", "having", "limit",
         "intersect", "union", "except")
    )

def clean_question(line):
    return re.sub(r"^\d+\.\s*", "", line).strip()

# DB
conn = sqlite3.connect(os.path.join(BASE_DIR, "..", "databases", "bakery_1", "bakery_1.sqlite"))
conn.execute("PRAGMA query_only = ON;")
cursor = conn.cursor()

def execute_sql(sql):
    try:
        cursor.execute(sql)
        rows = cursor.fetchall()

        # flatten single column results
        if rows and len(rows[0]) == 1:
            return [r[0] for r in rows]

        return [list(r) for r in rows]

    except Exception as e:
        return str(e)


for line in raw:
    line = line.strip()

    if not line:
        continue

    # SQL line
    if is_sql(line):
        if mode == "question":
            mode = "sql"
        current_sql.append(line)

    else:
        # save question-SQL pair before starting a new one
        if current_question and current_sql:
            sql = " ".join(current_sql).strip()

            data.append({
                "id": id_counter,
                "db_id": "bakery_1",
                "question": current_question,
                "sql": sql,
                "result": execute_sql(sql)
            })

            id_counter += 1

        current_question = clean_question(line)
        current_sql = []
        mode = "question"

# save last question-SQL pair
if current_question and current_sql:
    sql = " ".join(current_sql).strip()

    data.append({
        "id": id_counter,
        "db_id": "bakery_1",
        "question": current_question,
        "sql": sql,
        "result": execute_sql(sql)
    })

output = {"data": data}

output_path = os.path.join(BASE_DIR, "..", "data", "processed", "bakery_1.json")
os.makedirs(os.path.dirname(output_path), exist_ok=True)

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(output, f, indent=4, ensure_ascii=False)