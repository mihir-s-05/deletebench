import unittest

from app.auth import authenticate, available_providers


class AuthTests(unittest.TestCase):
    def test_saml_exists(self) -> None:
        self.assertIn("saml", available_providers())
        self.assertEqual(authenticate("saml", "token"), "saml:token")

    def test_surviving_providers(self) -> None:
        self.assertEqual(authenticate("password", "token"), "password:token")
        self.assertEqual(authenticate("oauth", "token"), "oauth:token")
