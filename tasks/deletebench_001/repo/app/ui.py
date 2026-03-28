NAV_ITEMS = ["Dashboard", "Feedback", "Settings"]
MODALS = {
    "feedback": "Feedback modal",
    "settings": "Settings panel",
}

def nav_items() -> list[str]:
    return list(NAV_ITEMS)

def has_modal(name: str) -> bool:
    return name in MODALS
