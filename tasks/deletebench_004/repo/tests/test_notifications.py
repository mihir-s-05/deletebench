import unittest

from app.mail import format_email
from app.notifications import available_channels, send_email_notification, send_in_app_notification
from app.worker import queued_jobs


class NotificationTests(unittest.TestCase):
    def test_email_notifications_exist(self) -> None:
        self.assertIn("email", available_channels())
        self.assertEqual(send_email_notification("lee", "hi"), "email:lee:hi")
        self.assertIn("email_notifications", queued_jobs())

    def test_in_app_survives(self) -> None:
        self.assertIn("in_app", available_channels())
        self.assertEqual(send_in_app_notification("lee", "hi"), "in_app:lee:hi")
        self.assertEqual(format_email("hello", "body"), "Subject: hello\n\nbody")
