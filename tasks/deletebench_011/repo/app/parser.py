def strict_parse(data: str) -> dict[str, str]:
    if ":" not in data:
        raise ValueError("strict parser requires a colon")
    key, value = data.split(":", 1)
    if key != "id":
        raise ValueError("strict parser expects the id key")
    return {"id": value}

def legacy_parse(data: str) -> dict[str, str]:
    return {"id": data.strip()}

def parse(data: str) -> dict[str, str]:
    try:
        return strict_parse(data)
    except ValueError:
        return legacy_parse(data)
