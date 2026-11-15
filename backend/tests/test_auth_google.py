import unittest
from unittest import mock

import auth
import config


class GoogleAvailabilityTests(unittest.TestCase):
    def _patch(
        self,
        enabled: bool,
        client_id: str = "client-id",
        secret: str = "secret",
        reason: str = "Google 已停用",
    ):
        return mock.patch.multiple(
            config,
            AUTH_GOOGLE_ENABLED=enabled,
            AUTH_GOOGLE_DISABLED_REASON=reason,
            GOOGLE_CLIENT_ID=client_id,
            GOOGLE_CLIENT_SECRET=secret,
        )

    def test_env_gate_wins_even_with_credentials(self) -> None:
        with self._patch(False):
            self.assertTrue(auth.google_configured())
            self.assertFalse(auth.google_available())
            self.assertEqual(auth.google_disabled_reason(), "Google 已停用")

    def test_enabled_with_credentials_is_available(self) -> None:
        with self._patch(True):
            self.assertTrue(auth.google_available())
            self.assertIsNone(auth.google_disabled_reason())

    def test_enabled_without_credentials_reports_configuration(self) -> None:
        with self._patch(True, client_id="", secret=""):
            self.assertFalse(auth.google_available())
            self.assertIn("尚未配置", auth.google_disabled_reason() or "")


if __name__ == "__main__":
    unittest.main()
