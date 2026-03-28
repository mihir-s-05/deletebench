from app.config import TEAM_INVITES_ENABLED

def invite_routes() -> list[str]:
    return ["/team/invites"] if TEAM_INVITES_ENABLED else []

def create_invite(email: str) -> str:
    return f"invite:{email}"
