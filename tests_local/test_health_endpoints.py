from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from app.server import healthz, readyz


def response_payload(response: object) -> dict[str, str]:
    return json.loads(response.body)  # type: ignore[attr-defined]


class HealthEndpointTests(unittest.TestCase):
    def test_healthz_reports_running_process(self) -> None:
        response = healthz()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_payload(response), {"status": "ok"})

    @patch("app.server.check_database")
    def test_readyz_reports_ready_database(self, check_database_mock: object) -> None:
        response = readyz()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response_payload(response),
            {"status": "ready", "database": "ok"},
        )

    @patch("app.server.check_database", side_effect=RuntimeError("database is down"))
    def test_readyz_reports_unavailable_database(
        self, check_database_mock: object
    ) -> None:
        response = readyz()

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response_payload(response),
            {"status": "not_ready", "database": "unavailable"},
        )


if __name__ == "__main__":
    unittest.main()
