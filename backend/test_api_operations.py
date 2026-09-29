"""Operational API configuration and middleware tests."""
import unittest
import uuid

from fastapi.testclient import TestClient
import main


class CorsConfigurationTests(unittest.TestCase):
    def test_default_origins_cover_local_development_servers(self):
        self.assertEqual(main.parse_cors_origins(None), list(main.DEFAULT_CORS_ORIGINS))

    def test_configured_origins_are_normalized_and_deduplicated(self):
        origins = main.parse_cors_origins(
            " https://app.daisy.example/,http://localhost:8443,https://app.daisy.example "
        )

        self.assertEqual(
            origins,
            ["https://app.daisy.example", "http://localhost:8443"],
        )


class RequestTracingTests(unittest.TestCase):
    def test_generated_request_id_is_returned_on_public_response(self):
        with TestClient(main.app) as client:
            response = client.get("/")

        self.assertEqual(response.status_code, 200)
        uuid.UUID(response.headers["X-Request-ID"])

    def test_safe_caller_request_id_is_preserved(self):
        with TestClient(main.app) as client:
            response = client.get("/", headers={"X-Request-ID": "web-42.trace"})

        self.assertEqual(response.headers["X-Request-ID"], "web-42.trace")

    def test_invalid_request_id_is_replaced_on_auth_failure(self):
        with TestClient(main.app) as client:
            response = client.post("/chat", headers={"X-Request-ID": "unsafe id!"}, json={})

        self.assertEqual(response.status_code, 401)
        self.assertNotEqual(response.headers["X-Request-ID"], "unsafe id!")
        uuid.UUID(response.headers["X-Request-ID"])


if __name__ == "__main__":
    unittest.main()
