def _password(token: str) -> str:
    return f"password:{token}"

def _oauth(token: str) -> str:
    return f"oauth:{token}"

def _saml(token: str) -> str:
    return f"saml:{token}"

PROVIDERS = {"password": _password, "oauth": _oauth, "saml": _saml}

def available_providers() -> list[str]:
    return sorted(PROVIDERS)

def authenticate(provider: str, token: str) -> str:
    return PROVIDERS[provider](token)
