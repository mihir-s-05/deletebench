NAV_ITEMS = ["Dashboard", "Changelog", "Settings"]
MODALS = {
    "changelog": "Changelog modal",
    "settings": "Settings panel",
}

def nav_items() -> list[str]:
    return list(NAV_ITEMS)

def has_modal(name: str) -> bool:
    return name in MODALS
