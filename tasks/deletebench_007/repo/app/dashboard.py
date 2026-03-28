from app.config import ENABLE_BETA_DASHBOARD

def dashboard_cards() -> list[str]:
    cards = ["Overview", "Health"]
    if ENABLE_BETA_DASHBOARD:
        cards.append("Beta Insights")
    return cards
