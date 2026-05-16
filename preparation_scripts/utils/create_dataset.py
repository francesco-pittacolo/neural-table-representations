from utils.sql_utils import *
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def create_dataset(conn, groups, db, file_name_ground_truth, file_name_test, index):
    output = {"data": []}
    output2 = {"data": []}
    for i, (sql, questions) in enumerate(groups.items()):
        tables = extract_tables(sql)
        schema = [get_table_schema(conn, t) for t in tables]
        result = execute_sql(conn,sql)
        output["data"].append({
            "id": i,
            "question": questions[index],
            "sql": sql,
            "ground_truth": result,
        })
        output2["data"].append({
            "id": i,
            "question": questions[index],
            "schema": schema
        })
    output_path = os.path.join(BASE_DIR, "..",  "..", "data", "processed", db, "ground_truth", file_name_ground_truth)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # SAVE
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4, ensure_ascii=False)

    output2_path = os.path.join(BASE_DIR, "..", "..", "data", "processed", db, "test", file_name_test)
    os.makedirs(os.path.dirname(output2_path), exist_ok=True)
    
    with open(output2_path, "w", encoding="utf-8") as f:
        json.dump(output2, f, indent=4, ensure_ascii=False)