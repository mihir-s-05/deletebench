from app.config import ENABLE_AUDIT_PREVIEW

def dashboard_cards() -> list[str]:
    cards = ["Overview", "Health"]
    if ENABLE_AUDIT_PREVIEW:
        cards.append("Audit Preview")
    return cards
