from tableqa import run_tableqa
from pathlib import Path
import json
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
    "soccer_3": ["soccer_3_1"]
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
# MAIN
# =========================================================

for dataset, file_names in datasets.items():

    for file_name in file_names:

        # =====================================================
        # PATH HANDLING
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
                BASE_DIR / "outputs" / "tableqa" /
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
                BASE_DIR / "outputs" / "tableqa" /
                dataset
            )

        base_out_dir.mkdir(parents=True, exist_ok=True)

        # =====================================================
        # LOAD DATA
        # =====================================================

        db_json = json.load(open(
            BASE_DIR / "data" / "processed" /
            dataset / "db_json" / f"{dataset}_db.json"
        ))

        test_data = json.load(open(test_file_path))["data"]
        gt_data = json.load(open(gt_path))["data"]

        total = len(test_data)

        # =====================================================
        # MODELS LOOP
        # =====================================================

        for model in models:
            for mode in MODES:

                print(f"\n=== MODEL: {model} | MODE: {mode} ===")

                model_name = model.replace("-", "_").replace(".", "_").replace("/", "_")
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

                completed_ids = load_existing_results(jsonl_path) if RESUME else set()

                print(f"Resuming from {len(completed_ids)} completed items")

                stop_model = False
                done_count = len(completed_ids)

                # =================================================
                # QUESTION LOOP
                # =================================================

                for i, item in enumerate(test_data):

                    if item["id"] in completed_ids:
                        continue

                    try:
                        result = run_tableqa(
                            item=item,
                            db_json=db_json,
                            model=model,
                            mode=mode,
                            test_data=test_data,
                            gt_data=gt_data
                        )

                        # =================================================
                        # DAILY LIMIT → STOP MODEL (NO WRITE)
                        # =================================================

                        if result.get("status") == "daily_limit_reached":
                            print(f"\n[DAILY LIMIT] stopping model: {model}")
                            stop_model = True
                            break

                        # =================================================
                        # WRITE ONLY VALID RESULTS
                        # =================================================

                        record = {
                            "id": item["id"],
                            "question": item["question"],
                            "prediction": result
                        }

                        with open(jsonl_path, "a", encoding="utf-8") as f:
                            f.write(json.dumps(record, ensure_ascii=False) + "\n")

                        done_count += 1

                    except Exception as e:
                        print(f"[ERROR] {e}")

                    # =================================================
                    # LIVE PROGRESS BAR
                    # =================================================

                    print(
                        f"\rProgress: {done_count}/{total}",
                        end="",
                        flush=True
                    )

                    time.sleep(0.1)

                print()  # newline after progress bar

                # =================================================
                # STOP MODEL EARLY
                # =================================================

                if stop_model:
                    print(f"Stopped model early: {model}")
                    continue  # IMPORTANT: move to next model

                # =================================================
                # JSONL -> JSON ONLY IF COMPLETE
                # =================================================

                data_out = []

                with open(jsonl_path, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            data_out.append(json.loads(line))
                        except:
                            pass

                if len(data_out) != total:
                    print(f"Incomplete run ({len(data_out)}/{total}) → keeping JSONL")
                    continue

                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump({"data": data_out}, f, indent=4, ensure_ascii=False)

                os.remove(jsonl_path)

                #print(f"Saved final JSON: {json_path}")