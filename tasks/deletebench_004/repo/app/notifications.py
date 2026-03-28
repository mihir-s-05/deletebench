from app.config import EMAIL_NOTIFICATIONS_ENABLED, IN_APP_NOTIFICATIONS_ENABLED

def available_channels() -> list[str]:
    channels = []
    if EMAIL_NOTIFICATIONS_ENABLED:
        channels.append("email")
    if IN_APP_NOTIFICATIONS_ENABLED:
        channels.append("in_app")
    return channels

def send_email_notification(user: str, message: str) -> str:
    return f"email:{user}:{message}"

def send_in_app_notification(user: str, message: str) -> str:
    return f"in_app:{user}:{message}"
