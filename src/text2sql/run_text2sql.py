from text2sql import run_text2sql
from pathlib import Path
import json
import sqlite3
import time
import os

# =========================================================
# CONFIG
# =========================================================

models = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "qwen/qwen3-32b",
]

datasets = {
    "bakery_1": [""],
    "soccer_3": ["soccer_3_1", "soccer_3_2"]
}

MODES = ["zero_shot", "few_shot"]

BASE_DIR = Path(__file__).resolve().parent.parent.parent

RESUME = True # to resume from existing jsonl files


# =========================================================
# LOAD EXISTING RESULTS
# =========================================================

def load_existing_results(jsonl_path):
    completed_ids = set()

    if not jsonl_path.exists():
        return completed_ids

    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                item = json.loads(line)
                completed_ids.add(item["id"])
            except:
                continue

    return completed_ids


# =========================================================
# RUN PIPELINE
# =========================================================

for dataset, file_names in datasets.items():

    db_path = BASE_DIR / "databases" / dataset / f"{dataset}.sqlite"
    db_available = db_path.exists()

    for file_name in file_names:

        # =====================================================
        # PATHS
        # =====================================================

        if file_name:

            test_file_path = (
                BASE_DIR / "data" / "processed" /
                dataset / "test" / f"{file_name}_test.json"
            )

            gt_path = (
                BASE_DIR / "data" / "processed" /
                dataset / "ground_truth" / f"{file_name}_gt.json"
            )

            base_out_dir = (
                BASE_DIR / "outputs" / "text2sql" /
                dataset / file_name
            )

        else:

            test_file_path = (
                BASE_DIR / "data" / "processed" /
                dataset / "test" / f"{dataset}_test.json"
            )

            gt_path = (
                BASE_DIR / "data" / "processed" /
                dataset / "ground_truth" / f"{dataset}_gt.json"
            )

            base_out_dir = (
                BASE_DIR / "outputs" / "text2sql" /
                dataset
            )

        base_out_dir.mkdir(parents=True, exist_ok=True)

        # =====================================================
        # LOAD DATA
        # =====================================================

        with open(test_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        with open(gt_path, "r", encoding="utf-8") as f:
            gt_data = json.load(f)

        test_data = data["data"]
        gt_data = gt_data["data"]

        total = len(test_data)

        # =====================================================
        # MODEL LOOP
        # =====================================================

        for model in models:

            for mode in MODES:

                print(f"\n=== Model: {model} | Mode: {mode} ===")

                model_name = (
                    model.replace("-", "_")
                    .replace(".", "_")
                    .replace("/", "_")
                )

                mode_tag = mode.split("_")[0]

                jsonl_path = (
                    base_out_dir / mode /
                    f"{model_name}_{mode_tag}_results.jsonl"
                )

                json_path = (
                    base_out_dir / mode /
                    f"{model_name}_{mode_tag}_results.json"
                )

                jsonl_path.parent.mkdir(parents=True, exist_ok=True)

                # =================================================
                # RESUME
                # =================================================

                completed_ids = (
                    load_existing_results(jsonl_path)
                    if RESUME else set()
                )

                done_count = len(completed_ids)

                print(f"Resuming from {done_count} completed items")

                stop_model = False

                # =================================================
                # DB CONNECTION
                # =================================================

                if db_available:
                    conn = sqlite3.connect(db_path)
                    conn.execute("PRAGMA query_only = ON;")
                else:
                    conn = None
                    print(f"[LLM-ONLY MODE] Missing DB: {db_path}")

                # =================================================
                # QUESTION LOOP
                # =================================================

                for i, item in enumerate(test_data):

                    if item["id"] in completed_ids:
                        continue

                    retries = 0
                    success = False

                    while not success:

                        try:

                            result = run_text2sql(
                                item,
                                conn,
                                model,
                                test_data=test_data,
                                gt_data=gt_data,
                                mode=mode
                            )

                            # =========================================
                            # DAILY LIMIT
                            # =========================================

                            if (
                                isinstance(result, dict)
                                and result.get("status") == "daily_limit_reached"
                            ):
                                print(f"\n[DAILY LIMIT] stopping model: {model}")
                                stop_model = True
                                break

                            record = {
                                "id": item.get("id"),
                                "question": item["question"],
                                "prediction": result
                            }

                            with open(jsonl_path, "a", encoding="utf-8") as f:
                                f.write(
                                    json.dumps(record, ensure_ascii=False) + "\n"
                                )

                            done_count += 1
                            success = True

                        except Exception as e:

                            msg = str(e)

                            # =========================================
                            # RATE LIMIT
                            # =========================================

                            if (
                                "RateLimitError" in msg
                                or "429" in msg
                            ):

                                quota_errors = [
                                    "tokens per day",
                                    "daily limit",
                                ]

                                if any(q in msg.lower() for q in quota_errors):

                                    print(
                                        f"\n[STOPPING MODEL] "
                                        f"Daily quota reached for {model}"
                                    )

                                    stop_model = True
                                    break

                                wait_time = min(60, 2 ** retries)

                                print(
                                    f"[RateLimit] {model} item {i} "
                                    f"→ waiting {wait_time}s"
                                )

                                time.sleep(wait_time)

                                retries += 1
                                continue

                            # =========================================
                            # OTHER ERRORS
                            # =========================================

                            record = {
                                "id": item.get("id"),
                                "question": item["question"],
                                "error": msg
                            }

                            with open(jsonl_path, "a", encoding="utf-8") as f:
                                f.write(
                                    json.dumps(record, ensure_ascii=False) + "\n"
                                )

                            done_count += 1
                            success = True

                    # =============================================
                    # BREAK MODEL LOOP
                    # =============================================

                    if stop_model:
                        break

                    # =============================================
                    # LIVE PROGRESS
                    # =============================================

                    print(
                        f"\rProgress: {done_count}/{total}",
                        end="",
                        flush=True
                    )

                    time.sleep(0.1)

                print()

                # =================================================
                # CLOSE DB
                # =================================================

                if conn:
                    conn.close()

                # =================================================
                # STOP MODEL EARLY
                # =================================================

                if stop_model:
                    print(f"Stopped model early: {model}")
                    continue

                # =================================================
                # JSONL → JSON ONLY IF COMPLETE
                # =================================================

                data_out = []

                with open(jsonl_path, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            data_out.append(json.loads(line))
                        except:
                            pass

                if len(data_out) != total:
                    print(
                        f"Incomplete run ({len(data_out)}/{total}) "
                        f"→ keeping JSONL"
                    )
                    continue

                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(
                        {"data": data_out},
                        f,
                        indent=4,
                        ensure_ascii=False
                    )

                os.remove(jsonl_path)

                # print(f"Saved final JSON: {json_path}")