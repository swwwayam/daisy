"""End-to-end tests for explicit zero-value cleaning policies."""
import json
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

import main


class CleaningPolicyApiTests(unittest.TestCase):
    auth = {"Authorization": "Bearer test-session"}

    def test_selected_zero_policy_is_applied_and_recorded(self):
        csv = "Glucose,Balconies,target\n0,0,1\n90,1,0\n100,2,1\n"
        plan = json.dumps({
            "summary": "Filled missing glucose values.",
            "actions": [{
                "type": "impute",
                "column": "Glucose",
                "strategy": "median",
                "reasoning": "The explicit zero policy created a missing value.",
            }],
        })
        with (
            TestClient(main.app) as client,
            patch.object(main, "validate_access_token", new=AsyncMock(return_value={"id": "test-user"})),
            patch.object(main, "ai_client", object()),
            patch.object(main, "generate_ai_text", return_value=plan),
            patch.dict(main.DATASETS, {}, clear=True),
            patch.dict(main.DATASET_TRANSFORMS, {}, clear=True),
        ):
            upload = client.post(
                "/upload-dataset", headers=self.auth,
                files={"file": ("health.csv", csv, "text/csv")},
            )
            self.assertEqual(upload.status_code, 200, upload.text)
            summary = upload.json()
            self.assertEqual(summary["zero_values"], {"Glucose": 1, "Balconies": 1, "target": 1})

            response = client.post(
                "/agents/data-cleaning", headers=self.auth,
                json={"dataset_id": summary["dataset_id"], "zero_as_missing": ["Glucose"]},
            )
            self.assertEqual(response.status_code, 200, response.text)
            result = response.json()
            cleaned = main.DATASETS[result["cleaned_dataset_id"]]
            self.assertEqual(cleaned["Glucose"].tolist(), [95.0, 90.0, 100.0])
            self.assertEqual(cleaned["Balconies"].tolist(), [0, 1, 2])
            types = [step["type"] for step in main.DATASET_TRANSFORMS[result["cleaned_dataset_id"]]]
            self.assertEqual(types[:3], ["normalize", "zero_to_missing", "impute"])

    def test_unknown_zero_policy_column_is_rejected(self):
        with (
            TestClient(main.app) as client,
            patch.object(main, "validate_access_token", new=AsyncMock(return_value={"id": "test-user"})),
            patch.object(main, "ai_client", object()),
            patch.dict(main.DATASETS, {"dataset": main.pd.DataFrame({"value": [0, 1]})}, clear=True),
        ):
            response = client.post(
                "/agents/data-cleaning", headers=self.auth,
                json={"dataset_id": "dataset", "zero_as_missing": ["does_not_exist"]},
            )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
