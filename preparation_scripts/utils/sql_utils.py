import re

def execute_sql(conn, sql):
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()
        return [tuple(str(cell) for cell in row) for row in rows]

    except Exception:
        return []

def extract_tables(sql):
    sql = sql.lower()

    tables = set()

    # capture FROM and JOIN blocks
    pattern = r"(from|join)\s+([^;]+)"

    matches = re.findall(pattern, sql)

    for _, block in matches:
        # split by commas and joins
        parts = re.split(r",|\bjoin\b", block)

        for part in parts:
            table = part.strip().split()[0]  # first word only
            table = re.sub(r"[`,;()]", "", table)

            if table and table not in {"select", "where", "on"}:
                tables.add(table)

    return list(tables)

def get_table_schema(conn, table_name):
    try:
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        rows = cursor.fetchall()

        return {
            "table": table_name,
            "columns": [row[1] for row in rows]
        }

    except Exception:
        # graceful fallback (important for robustness)
        return {
            "table": table_name,
            "columns": []
        }
    
def extract_rows_per_table(conn, tables, limit=0):
    rows = {}

    for t in tables:
        query = f"SELECT * FROM {t}"
        if limit:
            query += f" LIMIT {limit}"

        cursor = conn.execute(query)
        cols = [desc[0] for desc in cursor.description]

        rows[t] = [
            dict(zip(cols, row))
            for row in cursor.fetchall()
        ]

    return rows