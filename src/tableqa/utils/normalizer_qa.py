def normalize_tableqa(value):

    if value is None:
        return None

    normalized = []

    for row in value:

        if isinstance(row, dict):

            normalized.append([
                str(v).strip()
                for v in row.values()
            ])

        elif isinstance(row, (list, tuple)):

            normalized.append([
                str(v).strip()
                for v in row
            ])

        else:

            normalized.append([
                str(row).strip()
            ])

    return normalized