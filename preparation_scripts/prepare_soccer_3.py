import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from utils.create_dataset import *
from utils.db_json_builder import *

BASE_DIR = Path(__file__).resolve().parent

raw_file = BASE_DIR.parent / "data" / "raw" / "test.json"

with open(raw_file, "r") as f:
    data = json.load(f)

filtered = [item for item in data if item.get("db_id") == "soccer_3"]

groups = defaultdict(list)

for item in filtered:
    sql = item["query"].strip()
    groups[sql].append(item["question"].strip())

# connect to database
db_path = BASE_DIR.parent / "databases" / "soccer_3" / "soccer_3.sqlite"
conn = sqlite3.connect(db_path)
conn.execute("PRAGMA query_only = ON;")

output_path = BASE_DIR.parent / "data" / "processed" / "soccer_3" / "db_json" / "soccer_3_db.json"
export_database(conn, output_path)

cursor = conn.cursor()

        
create_dataset(conn, groups, "soccer_3", "soccer_3_1_gt.json", "soccer_3_1_test.json", 0)
create_dataset(conn, groups, "soccer_3", "soccer_3_2_gt.json", "soccer_3_2_test.json", 1)