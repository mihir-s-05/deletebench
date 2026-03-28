from app.config import CSV_EXPORT_ENABLED, JSON_EXPORT_ENABLED

def export_formats() -> list[str]:
    formats = []
    if CSV_EXPORT_ENABLED:
        formats.append("csv")
    if JSON_EXPORT_ENABLED:
        formats.append("json")
    return formats

def export_csv(rows: list[dict[str, str]]) -> str:
    return ",".join(rows[0].keys()) + "\n" + ",".join(rows[0].values())

def export_json(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return list(rows)
