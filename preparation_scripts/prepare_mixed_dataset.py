import json
import random
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

soccer_path = os.path.join(BASE_DIR, "..", "data", "processed", "soccer_3.json")
bakery_path = os.path.join(BASE_DIR, "..", "data", "processed", "bakery_1.json")

if not os.path.exists(soccer_path):
    raise FileNotFoundError("Missing soccer dataset. Run soccer preprocessing script first.")

if not os.path.exists(bakery_path):
    raise FileNotFoundError("Missing bakery dataset. Run bakery preprocessing script first.")

# LOAD DATASETS
with open(soccer_path, "r", encoding="utf-8") as f:
    soccer = json.load(f)["data"]

with open(bakery_path, "r", encoding="utf-8") as f:
    bakery = json.load(f)["data"]

dataset = soccer + bakery

def extract_question(item):
    if "question" in item:
        return item["question"]
    elif "questions" in item:
        return item["questions"][0] # multiple nl questions for same sql query, take only first question 
    else:
        return None
    
# NORMALIZE
dataset_clean = []
for item in dataset:
    q = extract_question(item)
    if q is None:
        continue
    dataset_clean.append({
        "db": item["db_id"],
        "question": q,
        "sql": item["sql"],
        "result": item["result"]
    })

# SHUFFLE
random.seed(5) # deterministic for reproducibility
random.shuffle(dataset_clean)

# RE-INDEX
output = {"data": []}

for i, item in enumerate(dataset_clean):
    output["data"].append({
        "id": i,
        "db_id": item["db"],
        "question": item["question"],
        "sql": item["sql"],
        "result": item["result"]
    })

output_path = os.path.join(BASE_DIR, "..", "data", "processed", "mixed_dataset.json")
os.makedirs(os.path.dirname(output_path), exist_ok=True)

# SAVE
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(output, f, indent=4, ensure_ascii=False)