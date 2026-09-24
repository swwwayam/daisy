"""Groq request-policy regressions; no network calls or credentials are needed."""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from openai import APITimeoutError

import main


class ChatLatencyTests(unittest.TestCase):
    def client(self):
        client = MagicMock()
        client.with_options.return_value = client
        client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Hello!"), finish_reason="stop")],
            usage=SimpleNamespace(completion_tokens=3),
        )
        return client

    def test_groq_chat_bounds_interactive_request(self):
        client = self.client()
        with patch.object(main, "ai_client", client), patch.object(main, "GROQ_MODEL", "openai/gpt-oss-120b"):
            self.assertEqual(main.chat(main.ChatRequest(message="What can you do?")), {"reply": "Hello!"})
        args = client.chat.completions.create.call_args.kwargs
        self.assertNotIn("extra_body", args)
        self.assertEqual(args["max_tokens"], 512)
        client.with_options.assert_called_once_with(timeout=30.0, max_retries=0)

    def test_agent_budget_and_json_mode_are_preserved(self):
        client = self.client()
        with patch.object(main, "ai_client", client), patch.object(main, "GROQ_MODEL", "openai/gpt-oss-120b"):
            main.generate_ai_text("Plan the cleaning", json_mode=True)
        args = client.chat.completions.create.call_args.kwargs
        self.assertEqual(args["max_tokens"], 16384)
        self.assertNotIn("extra_body", args)
        self.assertEqual(args["response_format"], {"type": "json_object"})
        client.with_options.assert_not_called()

    def test_timeout_is_not_misreported_as_a_quota_error(self):
        client = self.client()
        client.chat.completions.create.side_effect = APITimeoutError(request=MagicMock())
        with patch.object(main, "ai_client", client):
            reply = main.chat(main.ChatRequest(message="What can you do?"))["reply"]
        self.assertIn("too long", reply)
        self.assertNotIn("quota", reply)

    def test_dataset_grounding_is_preserved(self):
        client = self.client()
        import pandas as pd
        with patch.object(main, "ai_client", client), patch.dict(main.DATASETS, {"test": pd.DataFrame({"value": [1, 2]})}), patch.object(main, "build_chat_pipeline_context", return_value="Actual pipeline context"):
            main.chat(main.ChatRequest(message="Explain my dataset", dataset_id="test"))
        prompt = client.chat.completions.create.call_args.kwargs["messages"][0]["content"]
        self.assertIn("Rows: 2", prompt)
        self.assertIn("Actual pipeline context", prompt)

    def test_greetings_use_provider_reply_without_fabricated_dataset_context(self):
        client = self.client()
        with patch.object(main, "ai_client", client), patch.object(main, "build_schema_report") as schema:
            for message in ("hi", "HELLO!", "hey daisy"):
                self.assertEqual(main.chat(main.ChatRequest(message=message))["reply"], "Hello!")
        self.assertEqual(client.chat.completions.create.call_count, 3)
        schema.assert_not_called()

    def test_no_dataset_state_is_explicit_and_user_message_separate(self):
        client = self.client()
        with patch.object(main, "ai_client", client), patch.object(main, "build_chat_pipeline_context") as context:
            main.chat(main.ChatRequest(message="Have you analyzed my data?"))
        messages = client.chat.completions.create.call_args.kwargs["messages"]
        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("No dataset has been uploaded", messages[0]["content"])
        self.assertIn("No results exist", messages[0]["content"])
        self.assertEqual(messages[1], {"role": "user", "content": "Have you analyzed my data?"})
        context.assert_not_called()

    def test_expired_dataset_does_not_invent_results(self):
        client = self.client()
        with patch.object(main, "ai_client", client), patch.dict(main.DATASETS, {}, clear=True):
            main.chat(main.ChatRequest(message="hi, explain my results", dataset_id="expired"))
        messages = client.chat.completions.create.call_args.kwargs["messages"]
        self.assertIn("dataset is unavailable", messages[0]["content"])


if __name__ == "__main__":
    unittest.main()
