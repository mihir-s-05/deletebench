class Database:
    def get_user(self, user_id: str) -> dict[str, str]:
        return {"id": user_id, "name": "Ada"}

class Cache:
    def __init__(self) -> None:
        self._data: dict[str, dict[str, str]] = {}

    def get(self, key: str) -> dict[str, str] | None:
        return self._data.get(key)

    def set(self, key: str, value: dict[str, str]) -> None:
        self._data[key] = value

class UserRepository:
    def __init__(self) -> None:
        self.database = Database()
        self.cache = Cache()

    def get_user(self, user_id: str) -> dict[str, str]:
        cached = self.cache.get(user_id)
        if cached is not None:
            return cached
        user = self.database.get_user(user_id)
        self.cache.set(user_id, user)
        return user

def probe_lookup() -> dict[str, str]:
    return UserRepository().get_user("9")
