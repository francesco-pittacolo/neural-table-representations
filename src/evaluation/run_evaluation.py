from pathlib import Path
import json
from evaluator import Evaluator

# =========================================================
# CONFIG
# =========================================================

PIPELINES = ["text2sql", "tableqa"]

datasets = {
    "bakery_1": [""],
    "soccer_3": ["soccer_3_1", "soccer_3_2"]
}

models = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "qwen/qwen3-32b",
]

prompt_method = ["zero_shot", "few_shot"]

BASE_DIR = Path(__file__).resolve().parent.parent.parent

evaluator = Evaluator()

# =========================================================
# ERROR DETECTION
# =========================================================

def is_context_error(pred_item):
    if pred_item is None:
        return True

    if not isinstance(pred_item, dict):
        return False

    pred = pred_item.get("prediction")
    if not isinstance(pred, dict):
        return False

    msg = (str(pred.get("error", "")) + str(pred.get("status", ""))).lower()

    return any(x in msg for x in [
        "413", "context",
        "rate", "tpm", "too large",
        "request too large"
    ])

# =========================================================
# EXTRACTION
# =========================================================

def extract_prediction(pred_item):
    if not isinstance(pred_item, dict):
        return []

    pred = pred_item.get("prediction")
    if not isinstance(pred, dict):
        return []

    if pred.get("status") != "ok":
        return []

    return pred.get("answer") if isinstance(pred.get("answer"), list) else []

# =========================================================
# MAIN LOOP
# =========================================================
for PIPELINE in PIPELINES:
    for method in prompt_method:
        mode_tag = method.split("_")[0]

        for model in models:

            model_name = model.replace("-", "_").replace(".", "_").replace("/", "_")

            for dataset, file_names in datasets.items():

                for file_name in file_names:

                    # ---------------- PATHS ----------------
                    if file_name:
                        gt_path = BASE_DIR / "data" / "processed" / dataset / "ground_truth" / f"{file_name}_gt.json"
                        pred_path = BASE_DIR / "outputs" / PIPELINE / dataset / file_name / method / f"{model_name}_{mode_tag}_results.json"
                        subset = file_name
                    else:
                        gt_path = BASE_DIR / "data" / "processed" / dataset / "ground_truth" / f"{dataset}_gt.json"
                        pred_path = BASE_DIR / "outputs" / PIPELINE / dataset / method / f"{model_name}_{mode_tag}_results.json"
                        subset = dataset

                    if not gt_path.exists() or not pred_path.exists():
                        print("Missing files:", gt_path, pred_path)
                        continue

                    gt_data = json.load(open(gt_path, encoding="utf-8"))["data"]
                    pred_data = json.load(open(pred_path, encoding="utf-8"))["data"]

                    pred_map = {p["id"]: p for p in pred_data if isinstance(p, dict)}

                    # ---------------- OUTPUT ----------------
                    if PIPELINE == "tableqa":
                        eval_modes = ["strict", "filtered"]
                    else:
                        eval_modes = ["strict"]
                    for eval_mode in eval_modes:

                        # ---------------- OUTPUT ----------------
                        base_out = BASE_DIR / "evaluations" / PIPELINE

                        if PIPELINE == "tableqa":
                            mode_dir = eval_mode   # strict / filtered
                            if file_name:
                                strict_dir = base_out / "strict" / dataset / file_name
                                filtered_dir = base_out / "filtered" / dataset / file_name
                            else:
                                strict_dir = base_out / "strict" / dataset
                                filtered_dir = base_out / "filtered" / dataset

                        elif PIPELINE == "text2sql":
                            if file_name:
                                out_dir = base_out / dataset / file_name
                            else:
                                out_dir = base_out / dataset
                        else:
                            raise ValueError(f"Unknown pipeline: {PIPELINE}")
                        
                        out_file = out_dir / method / f"{model_name}_{mode_tag}.json"
                        out_file.parent.mkdir(parents=True, exist_ok=True)

                        scores = {
                            "cell_precision": [],
                            "cell_recall": [],
                            "tuple_cardinality": [],
                            "tuple_constraint": [],
                            "tuple_order": []
                        }

                        skipped = 0
                        results = []

                        for gt_item in gt_data:

                            pred_item = pred_map.get(gt_item["id"])

                            if eval_mode == "filtered" and is_context_error(pred_item):
                                skipped += 1
                                continue
                            
                            pred_rows = extract_prediction(pred_item)

                            gt_rows = gt_item["ground_truth"]

                            metrics = evaluator.evaluate(gt_rows, pred_rows)

                            scores["cell_precision"].append(metrics["cell_precision"])
                            scores["cell_recall"].append(metrics["cell_recall"])
                            scores["tuple_cardinality"].append(metrics["tuple_cardinality"])
                            scores["tuple_constraint"].append(metrics["tuple_constraint"])
                            scores["tuple_order"].append(metrics["tuple_order"])

                            results.append({
                                "id": gt_item["id"],
                                "question": gt_item.get("question", ""),
                                "ground_truth": gt_rows,
                                "prediction": pred_rows,
                                "metrics": metrics
                            })

                        n = len(results) or 1

                        summary = {
                            "pipeline": PIPELINE,
                            "prompt_method": method,
                            "model": model,
                            "dataset": dataset,
                            "subset": subset,
                            "evaluation_mode": eval_mode,
                            "num_examples": len(results),
                            "skipped_context_errors": skipped,

                            "metrics": {
                                "cell_precision": round(sum(scores["cell_precision"]) / n, 4),
                                "cell_recall": round(sum(scores["cell_recall"]) / n, 4),
                                "tuple_cardinality": round(sum(scores["tuple_cardinality"]) / n, 4),
                                "tuple_constraint": round(sum(scores["tuple_constraint"]) / n, 4),
                                "tuple_order": round(sum(scores["tuple_order"]) / n, 4),
                            }
                        }

                        with open(out_file, "w", encoding="utf-8") as f:
                            json.dump({"summary": summary, "data": results}, f, indent=4, ensure_ascii=False)

                        #print("Saved:", out_file)