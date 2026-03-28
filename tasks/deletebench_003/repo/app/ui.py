NAV_ITEMS = ["Dashboard", "Export", "Settings"]
MODALS = {
    "export": "Export modal",
    "settings": "Settings panel",
}

def nav_items() -> list[str]:
    return list(NAV_ITEMS)

def has_modal(name: str) -> bool:
    return name in MODALS
