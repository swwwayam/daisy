"""Dataset upload boundary tests."""
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

import main


class UploadLimitTests(unittest.TestCase):
    auth = {"Authorization": "Bearer test-session"}

    def test_oversized_csv_is_rejected_before_parsing(self):
        with (
            TestClient(main.app) as client,
            patch.object(main, "validate_access_token", new=AsyncMock(return_value={"id": "test-user"})),
            patch.object(main, "MAX_UPLOAD_BYTES", 16),
        ):
            response = client.post(
                "/upload-dataset",
                headers=self.auth,
                files={"file": ("large.csv", b"column\n" + b"x" * 17, "text/csv")},
            )

        self.assertEqual(response.status_code, 413)
        self.assertIn("upload limit", response.json()["detail"])

    def test_csv_within_limit_is_accepted(self):
        payload = b"value\n1\n2\n"
        with (
            TestClient(main.app) as client,
            patch.object(main, "validate_access_token", new=AsyncMock(return_value={"id": "test-user"})),
            patch.object(main, "MAX_UPLOAD_BYTES", len(payload)),
            patch.dict(main.DATASETS, {}, clear=True),
        ):
            response = client.post(
                "/upload-dataset",
                headers=self.auth,
                files={"file": ("valid.csv", payload, "text/csv")},
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["rows"], 2)


if __name__ == "__main__":
    unittest.main()
