"""Operational API configuration and middleware tests."""
import unittest
import uuid
from unittest.mock import patch

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


class HealthEndpointTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.object(main, "AUTH_PROVIDER", "supabase"))

    def test_liveness_is_public_and_identifies_the_service(self):
        with TestClient(main.app) as client:
            response = client.get("/health/live")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["service"], "daisy-api")
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_readiness_reports_only_configuration_state(self):
        with (
            patch.object(main, "SUPABASE_URL", "https://example.supabase.co"),
            patch.object(main, "SUPABASE_PUBLISHABLE_KEY", "configured"),
            patch.object(main, "GROQ_API_KEY", "configured"),
            patch.object(main, "MAX_UPLOAD_BYTES", 50 * 1024 * 1024),
            patch.object(main, "RUN_RETENTION_DAYS", 90),
            patch.object(main, "CORS_ORIGINS", ["https://app.daisy.example"]),
            TestClient(main.app) as client,
        ):
            response = client.get("/health/ready")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ready")
        self.assertEqual(response.json()["service"], "daisy-api")
        self.assertEqual(response.json()["version"], main.app.version)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.json()["checks"], {
            "authentication": True,
            "supabase_auth": True,
            "groq_inference": True,
            "upload_limit": True,
            "allowed_browser_origins": True,
        })
        self.assertEqual(response.json()["configuration"], {
            "durable_storage": False,
            "upload_limit_mb": 50,
            "run_retention_days": 90,
        })

    def test_convex_readiness_does_not_require_legacy_supabase_configuration(self):
        with (patch.object(main, "AUTH_PROVIDER", "convex"),
              patch.object(main, "CONVEX_SITE_URL", "https://example.convex.site"),
              patch.object(main, "SUPABASE_URL", ""),
              patch.object(main, "SUPABASE_PUBLISHABLE_KEY", ""),
              patch.object(main, "GROQ_API_KEY", "configured")):
            checks = main.readiness_checks()
        self.assertTrue(checks["authentication"])
        self.assertTrue(checks["convex_auth"])
        self.assertNotIn("supabase_auth", checks)

    def test_operational_settings_never_include_secrets_or_allowed_origins(self):
        with (
            patch.object(main, "SUPABASE_PUBLISHABLE_KEY", "do-not-expose"),
            patch.object(main, "GROQ_API_KEY", "do-not-expose"),
            patch.object(main, "CORS_ORIGINS", ["https://private.example"]),
            patch.object(main, "RUN_RETENTION_DAYS", 30),
        ):
            settings = main.operational_settings()
        self.assertEqual(settings["run_retention_days"], 30)
        self.assertNotIn("do-not-expose", str(settings))
        self.assertNotIn("private.example", str(settings))

    def test_readiness_returns_503_when_a_dependency_is_unconfigured(self):
        with (
            patch.object(main, "SUPABASE_URL", ""),
            patch.object(main, "SUPABASE_PUBLISHABLE_KEY", "configured"),
            patch.object(main, "GROQ_API_KEY", "configured"),
            patch.object(main, "MAX_UPLOAD_BYTES", 50 * 1024 * 1024),
            patch.object(main, "CORS_ORIGINS", ["https://app.daisy.example"]),
            TestClient(main.app) as client,
        ):
            response = client.get("/health/ready")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "not_ready")
        self.assertEqual(response.json()["service"], "daisy-api")
        self.assertFalse(response.json()["checks"]["supabase_auth"])

    def test_readiness_returns_503_without_an_allowed_browser_origin(self):
        with (
            patch.object(main, "SUPABASE_URL", "https://example.supabase.co"),
            patch.object(main, "SUPABASE_PUBLISHABLE_KEY", "configured"),
            patch.object(main, "GROQ_API_KEY", "configured"),
            patch.object(main, "MAX_UPLOAD_BYTES", 50 * 1024 * 1024),
            patch.object(main, "CORS_ORIGINS", []),
            TestClient(main.app) as client,
        ):
            response = client.get("/health/ready")

        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()["checks"]["allowed_browser_origins"])


if __name__ == "__main__":
    unittest.main()
