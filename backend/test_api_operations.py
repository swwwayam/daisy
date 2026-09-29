"""Operational API configuration and middleware tests."""
import unittest

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


if __name__ == "__main__":
    unittest.main()
