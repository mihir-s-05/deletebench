from app.invites import invite_routes
from app.members import list_members

def available_routes() -> list[str]:
    return ["/team/members", *invite_routes()]

def member_count() -> int:
    return len(list_members())
