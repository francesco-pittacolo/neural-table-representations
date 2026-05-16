def execute_sql(conn, sql):
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()

        return [tuple(str(x) for x in r) for r in rows]

    except Exception as e:
        print("SQL ERROR:", e)
        print("SQL:", sql)
        raise e
    
import re

def normalize_sql(sql: str) -> str | None:
    if not sql:
        return None

    sql = sql.strip()

    # remove markdown
    sql = re.sub(r"```sql|```", "", sql, flags=re.IGNORECASE).strip()

    # remove reasoning artifacts if they leaked in
    sql = re.sub(r"<think>.*?</think>", "", sql, flags=re.DOTALL | re.IGNORECASE).strip()

    if not sql.upper().startswith("SELECT"):
        return None

    # normalize simple string equality
    sql = re.sub(
        r"(\b\w+\b)\s*=\s*'([^']*)'",
        r"LOWER(\1) = LOWER('\2')",
        sql,
        flags=re.IGNORECASE
    )

    return sql