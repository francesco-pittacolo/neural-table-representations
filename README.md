# Models and Practice of Neural Table Representations

This repository implements a minimal evaluation framework for comparing two approaches for answering natural language questions over relational data:

* **Text-to-SQL**: LLM generates SQL queries executed on a SQLite database
* **TableQA**: LLM directly answers questions from serialized table content

The goal is to analyze differences in behavior, robustness, and failure modes between the two paradigms.

---

## Repository Structure

```
src/
  text2sql/
    ...
    run_text2sql.py
  tableqa/
    ...
    run_tableqa.py

databases/
datasets/
outputs/
evaluations/
```

---

## Setup

Create a `.env` file in the root directory and add your API key:

```
GROQ_API_KEY=your_api_key_here
```

If you use other providers (OpenAI, LLaMA, Qwen, etc.), configure their keys in the same file or in your environment variables depending on your backend setup.

---

## Configuration

All experiments are controlled via simple Python variables inside the scripts.

### Models

```python
models = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "qwen/qwen3-32b",
]
```

### Datasets

```python
datasets = {
    "bakery_1": [""],
    "soccer_3": ["soccer_3_1", "soccer_3_2"]
}
```

### Prompting Modes

```python
MODES = ["zero_shot", "few_shot"]
```

---

## Running the Project

### 1. Text-to-SQL Pipeline

Run:

```bash
python src/text2sql/run_text2sql.py
```

This pipeline:

* Loads dataset schema and questions
* Prompts the LLM to generate SQL queries
* Executes SQL on SQLite databases
* Stores normalized outputs in `outputs/text2sql/`

---

### 2. TableQA Pipeline

Run:

```bash
python src/tableqa/run_tableqa.py
```

This pipeline:

* Serializes relevant tables
* Prompts the LLM to directly answer questions
* Parses and normalizes outputs
* Stores results in `outputs/tableqa/`

---

## Outputs

All generated results are saved under:

```
outputs/
  text2sql/
  tableqa/
```

Each run produces structured outputs used for evaluation and comparison.

---

## Evaluation

To evaluate the outputs of both pipelines, run:

```bash
python src/evaluation/run_evaluation.py
```
Results are saved in the evaluations/ directory.
---

## Key Idea

This project is designed to compare:

* **Text-to-SQL** → structured reasoning via database execution
* **TableQA** → direct reasoning over serialized relational data

The focus is on **behavioral differences and failure modes**, not absolute performance.

## Acknowledgements

Built for the course *Advanced Topics in Computer Science* .
