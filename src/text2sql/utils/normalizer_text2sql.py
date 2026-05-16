import re

def normalize(rows):
    if not rows:
        return []

    return sorted(
        [tuple(str(x).strip() for x in r) for r in rows]
    )

def normalize_sql(sql: str) -> str:
    if not sql:
        return None

    sql = sql.strip()

    # remove markdown
    sql = re.sub(r"```sql|```", "", sql, flags=re.IGNORECASE).strip()

    sql = re.sub(
        r"(\w+)\.(LOWER|UPPER)\((\w+)\)",
        r"\2(\1.\3)",
        sql,
        flags=re.IGNORECASE
    )

    def repl(match):
        col = match.group(1)
        val = match.group(2)

        # skip if already LOWER(...)
        if col.lower().startswith("lower("):
            return match.group(0)

        return f"LOWER({col}) = LOWER('{val}')"

    sql = re.sub(
        r"(\b\w+\.\w+|\b\w+)\s*=\s*'([^']*)'",
        repl,
        sql,
        flags=re.IGNORECASE
    )

    return sql