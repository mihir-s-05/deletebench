import unittest

from app.api import available_routes, member_count
from app.invites import create_invite


class TeamTests(unittest.TestCase):
    def test_invites_exist(self) -> None:
        self.assertIn("/team/invites", available_routes())
        self.assertEqual(create_invite("a@example.com"), "invite:a@example.com")

    def test_members_survive(self) -> None:
        self.assertEqual(member_count(), 2)
