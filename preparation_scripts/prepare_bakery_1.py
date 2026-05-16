
import re
import sqlite3
from pathlib import Path
from collections import defaultdict
from utils.create_dataset import create_dataset
from utils.db_json_builder import *

BASE_DIR = Path(__file__).resolve().parent

raw_file_path = BASE_DIR.parent / "data" / "raw" / "bakery_1_michi.txt"

db_path = BASE_DIR.parent / "databases" / "bakery_1" / "bakery_1.sqlite"

# load raw file
with open(raw_file_path, "r", encoding="utf-8") as f:
    raw = f.read().splitlines()

# helpers
def is_sql(line):
    return line.lower().startswith(
        ("select", "from", "where", "group", "order", "having", "limit",
         "intersect", "union", "except")
    )

def clean_question(line):
    return re.sub(r"^\d+\.\s*", "", line).strip()

# build groups
groups = defaultdict(list)

current_question = None
current_sql = []

for line in raw:
    line = line.strip()
    if not line:
        continue

    if is_sql(line):
        current_sql.append(line)
    else:
        # save last pair
        if current_question and current_sql:
            sql = " ".join(current_sql).strip()
            groups[sql].append(current_question)

        current_question = clean_question(line)
        current_sql = []

# save last one
if current_question and current_sql:
    sql = " ".join(current_sql).strip()
    groups[sql].append(current_question)

# DB connection
conn = sqlite3.connect(db_path)
conn.execute("PRAGMA query_only = ON;")
output_path = BASE_DIR.parent / "data" / "processed" / "bakery_1" / "db_json" / "bakery_1_db.json"
export_database(conn, output_path)

create_dataset(conn, groups, "bakery_1",
    "bakery_1_gt.json",         # ground truth file
    "bakery_1_test.json",       # test file
    0                           # only first question per SQL
)