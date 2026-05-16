import re
import json
import random
from utils.sql_executor import execute_sql
from utils.normalizer_text2sql import normalize, normalize_sql

import os
from dotenv import load_dotenv
from groq import Groq

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
            {"role": "system", "content": "You generate SQL queries only."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )
    return response.choices[0].message.content


# =========================================================
# FORMAT SCHEMA
# =========================================================

def format_schema(schema):
    return "\n".join(
        f"Table {t['table']}: {', '.join(t['columns'])}"
        for t in schema
    )


# =========================================================
# FEW-SHOT RETRIEVAL
# =========================================================

def retrieve_few_shot_random(test_data, current_id, k=3):

    candidates = [
        ex for ex in test_data
        if ex["id"] != current_id
    ]

    if not candidates:
        return []

    return random.sample(candidates, min(k, len(candidates)))


# =========================================================
# FORMAT FEW-SHOT EXAMPLES
# =========================================================

def format_few_shot(examples, gt_data):

    out = []

    # id -> sql
    gt_map = {
        x["id"]: x["sql"]
        for x in gt_data
        if "sql" in x
    }

    for ex in examples:

        sql = gt_map.get(ex["id"])

        # skip if sql missing
        if sql is None:
            continue

        schema_text = format_schema(ex["schema"])

        out.append(f"""
Schema:
{schema_text}

Question:
{ex['question']}

SQL:
{sql}
""".strip())

    return "\n\n".join(out)


# =========================================================
# BUILD PROMPT
# =========================================================

def build_prompt(
    question,
    schema,
    few_shot_examples=None,
    gt_data=None
):

    few_shot_text = ""

    if few_shot_examples and gt_data:
        few_shot_text = format_few_shot(
            few_shot_examples,
            gt_data
        )

    examples_block = ""

    if few_shot_text:
        examples_block = (
            "USE THIS AS EXAMPLES:\n\n"
            + few_shot_text
        )

    return f"""
You are a strict SQLite query generator.

Schema:
{schema}

RULES:
- Use ONLY tables and columns that appear in the schema
- If a table or column is not in the schema, output {{"sql": null}}
- Do NOT invent tables, columns, or values
- Use ONLY SQLite syntax
- Do NOT use ANY, ALL, or non-SQLite operators
- Do NOT provide explanations or reasoning
- Do NOT output <think> or any extra text
- If the question cannot be answered exactly using the schema, output {{"sql": null}}

{examples_block}

OUTPUT FORMAT:
Return EXACTLY one JSON object:
{{"sql": string or null}}

Question:
{question}
""".strip()


# =========================================================
# EXTRACT SQL
# =========================================================

def extract_sql(text):

    text = text.strip()

    # remove thinking blocks
    text = re.sub(
        r"<think>.*?</think>",
        "",
        text,
        flags=re.DOTALL
    ).strip()

    # extract first json
    match = re.search(
        r"\{.*\}",
        text,
        flags=re.DOTALL
    )

    if not match:
        return None

    json_str = match.group(0)

    try:
        return json.loads(json_str).get("sql")
    except:
        return None


# =========================================================
# MAIN PIPELINE
# =========================================================

def run_text2sql(
    item,
    conn,
    model,
    test_data=None,
    gt_data=None,
    mode="zero_shot"
):

    schema_text = format_schema(item["schema"])

    # =====================================================
    # FEW-SHOT
    # =====================================================

    few_shot_examples = None

    if mode == "few_shot" and test_data is not None:

        few_shot_examples = retrieve_few_shot_random(
            test_data,
            item["id"],
            k=3
        )

    # =====================================================
    # BUILD PROMPT
    # =====================================================

    prompt = build_prompt(
        item["question"],
        schema_text,
        few_shot_examples,
        gt_data
    )

    #print("\n================ PROMPT ================\n")
    #print(prompt)

    # =====================================================
    # CALL MODEL
    # =====================================================

    output = call_llm(prompt, model)

    print("\n================ OUTPUT ================\n")
    print(output)

    # =====================================================
    # EXTRACT SQL
    # =====================================================

    sql = extract_sql(output)

    if not sql:
        return {
            "sql": None,
            "answer": [],
            "status": "empty"
        }

    sql = normalize_sql(sql)

    # =====================================================
    # NO DATABASE
    # =====================================================

    if conn is None:
        return {
            "sql": sql,
            "answer": None,
            "status": "no_db",
            "error": None
        }

    # =====================================================
    # EXECUTE SQL
    # =====================================================

    try:

        result = execute_sql(conn, sql)
        result = normalize(result)

        return {
            "sql": sql,
            "answer": result,
            "status": "ok",
            "error": None
        }

    except Exception as e:

        return {
            "sql": sql,
            "answer": [],
            "status": "sql_error",
            "error": str(e)
        }