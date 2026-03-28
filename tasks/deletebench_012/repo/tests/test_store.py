import unittest

from app.store import UserRepository


class StoreTests(unittest.TestCase):
    def test_cache_exists(self) -> None:
        repository = UserRepository()
        self.assertEqual(repository.get_user("7")["name"], "Ada")
        self.assertEqual(repository.cache.get("7"), {"id": "7", "name": "Ada"})
