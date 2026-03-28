def email(payload: str) -> str:
    return f"email:{payload}"

def webhook(payload: str) -> str:
    return f"webhook:{payload}"

def slack(payload: str) -> str:
    return f"slack:{payload}"

PROVIDERS = {"email": email, "webhook": webhook, "slack": slack}

def available_providers() -> list[str]:
    return sorted(PROVIDERS)

def notify(provider: str, payload: str) -> str:
    return PROVIDERS[provider](payload)
