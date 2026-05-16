import json
import re
import random
import time
import os
from dotenv import load_dotenv
from groq import Groq

from utils.normalizer_qa import normalize_tableqa


# =========================================================
# CLIENT
# =========================================================

def get_client():
    load_dotenv()
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set")
    return Groq(api_key=api_key)


def call_llm(prompt, model="llama-3.3-70b-versatile"):
    client = get_client()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a precise table question answering system. "
                    "Return ONLY valid JSON in the format {\"answer\": [...]} or null/[] when appropriate. "
                    "No explanations, no SQL, no extra text."
                )
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )
    return response.choices[0].message.content


# =========================================================
# SERIALIZATION
# =========================================================

def serialize_tables(db_json, schema):
    serialized = []

    for table_info in schema:
        table_name = table_info["table"]
        rows = db_json["tables"].get(table_name, [])

        text = f"TABLE: {table_name}\n"

        if not rows:
            text += "EMPTY\n"
            serialized.append(text)
            continue

        columns = list(rows[0].keys())

        text += " | ".join(columns) + "\n"

        for row in rows:
            text += " | ".join(str(row[col]) for col in columns)
            text += "\n"

        serialized.append(text)

    return "\n\n".join(serialized)


def serialize_tables_compact(db_json, schema):
    out = []

    for t in schema:
        table = t["table"]
        rows = db_json["tables"].get(table, [])

        if not rows:
            out.append(f"{table}:EMPTY")
            continue

        cols = list(rows[0].keys())
        header = ",".join(cols)

        out.append(f"{table}:{header}")

        for r in rows:
            row = ",".join(str(r[c]) for c in cols)
            out.append(row)

    return "\n".join(out)


# =========================================================
# FEW SHOT
# =========================================================

def retrieve_few_shot_random(test_data, gt_data, current_id, k=3):

    gt_map = {x["id"]: x for x in gt_data}
    candidates = []

    for ex in test_data:
        if ex["id"] == current_id:
            continue
        if ex["id"] not in gt_map:
            continue

        gt_item = gt_map[ex["id"]]

        if "ground_truth" not in gt_item:
            continue

        candidates.append({
            "question": ex["question"],
            "answer": gt_item["ground_truth"]
        })

    if not candidates:
        return []

    return random.sample(candidates, min(k, len(candidates)))


def format_few_shot(examples, schema):
    schema_text = "\n".join([
        f"{t['table']}({', '.join(t['columns'])})"
        for t in schema
    ])

    out = []

    for ex in examples:
        out.append(f"""

SCHEMA:
{schema_text}

Question:
{ex["question"]}

Answer:
{json.dumps(ex["answer"], ensure_ascii=False)}
""".strip())

    return "\n\n".join(out)


# =========================================================
# PROMPTS
# =========================================================

def build_prompt(question, serialized_tables, schema, few_shot_examples=None,):

    examples_block = ""

    if few_shot_examples:
        examples_block = f"""
EXAMPLES:

{format_few_shot(few_shot_examples, schema)}
----
"""
    print(examples_block)
    return f"""
You are a precise table question answering system.

RULES:
- Use ONLY table data
- Do NOT hallucinate
- Return ONLY JSON
- No explanations
- If empty: {{"answer": []}}
- If impossible: {{"answer": null}}

{examples_block}

Tables:
{serialized_tables}

Question:
{question}
""".strip()


def build_prompt_compact(question, serialized_tables):
    return (
        'JSON only: {"answer":[...]}\n'
        'No text.\n'
        'No SQL.\n\n'
        f"{serialized_tables}\n\n"
        f"Q: {question}"
    )


# =========================================================
# PARSER
# =========================================================

def extract_answer(text):

    if not text:
        return {
            "answer": [],
            "status": "empty_output"
        }

    text = text.strip()

    text = re.sub(
        r"<think>.*?</think>",
        "",
        text,
        flags=re.DOTALL
    ).strip()

    try:
        obj = json.loads(text)

    except:

        match = re.search(
            r"\{.*\}",
            text,
            flags=re.DOTALL
        )

        if not match:
            return {
                "answer": [],
                "status": "parse_error"
            }

        try:
            obj = json.loads(match.group(0))

        except:
            return {
                "answer": [],
                "status": "json_error"
            }

    # =========================================
    # HANDLE DIRECT LIST OUTPUT
    # =========================================

    if isinstance(obj, list):
        return {
            "answer": obj,
            "status": "ok"
        }

    # =========================================
    # HANDLE INVALID FORMAT
    # =========================================

    if not isinstance(obj, dict):
        return {
            "answer": [],
            "status": "invalid_format"
        }

    answer = obj.get("answer", None)

    if answer is None:
        return {
            "answer": None,
            "status": "cannot_infer"
        }

    return {
        "answer": answer,
        "status": "ok"
    }


# =========================================================
# ERROR CLASSIFICATION
# =========================================================

def classify_error(msg: str):
    m = str(msg).lower()

    if (
        "per day" in m
        or "daily" in m
        or "quota" in m
        or "limit reached" in m
    ):
        return "stop"
    
    # context error
    if (
        "413" in m
        or "request too large" in m
        or "too large for model" in m
        or "input exceeds" in m
        or "context length" in m
    ):
        return "context"

    # rate limit
    if (
        "rate_limit" in m
        or "429" in m
        or "tpm" in m
        or "tokens per minute" in m
        or "quota" in m
        or "limit reached" in m
    ):
        return "retry"

    return "unknown"


# =========================================================
# MAIN
# =========================================================

def run_tableqa(
    item,
    db_json,
    model,
    mode="zero_shot",
    test_data=None,
    gt_data=None,
    max_retries=5
):

    retries = 0

    few_shot_examples = None

    if mode == "few_shot" and test_data and gt_data:
        few_shot_examples = retrieve_few_shot_random(
            test_data, gt_data, item["id"], k=3
        )

    while True:

        try:
            schema = item["schema"]
            serialized_tables = serialize_tables(db_json, schema)
            prompt = build_prompt(item["question"], serialized_tables, schema, few_shot_examples)

            output = call_llm(prompt, model)
            break

        except Exception as e:

            msg = str(e).lower()
            action = classify_error(msg)

            # =====================================
            # CONTEXT ERROR
            # =====================================
            if action == "context":

                print("\n[CONTEXT] switching to compact serialization")

                try:
                    serialized_tables = serialize_tables_compact(db_json, item["schema"])
                    prompt = build_prompt_compact(item["question"], serialized_tables)

                    output = call_llm(prompt, model)
                    break

                except Exception as compact_error:

                    return {
                        "answer": None,
                        "status": "context_error",
                        "error": str(compact_error),
                        "raw_output": None
                    }

            # =====================================
            # RETRY (RATE LIMIT)
            # =====================================
            if action == "retry":

                wait_time = min(60, 2 ** retries)

                time.sleep(wait_time)
                retries += 1

                if retries >= max_retries:

                    return {
                        "answer": None,
                        "status": "rate_limit_failed",
                        "error": msg,
                        "raw_output": None
                    }

                continue

            # =====================================
            # DAILY LIMIT
            # =====================================
            if action == "stop":

                return {
                    "answer": None,
                    "status": "daily_limit_reached",
                    "error": msg,
                    "raw_output": None
                }

            raise

    parsed = extract_answer(output)

    parsed["answer"] = normalize_tableqa(parsed["answer"])

    return {
        "answer": parsed["answer"],
        "status": parsed["status"],
        "error": None,
        "raw_output": output
    }