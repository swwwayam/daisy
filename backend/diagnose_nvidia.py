"""Bounded, real NVIDIA latency probes. No datasets or credentials are printed.

Run: .venv/Scripts/python.exe diagnose_nvidia.py
Makes two small inference requests to the configured NVIDIA model.
"""
import json
import os
from pathlib import Path
from time import perf_counter

from dotenv import load_dotenv
from openai import OpenAI


def main():
    load_dotenv(Path(__file__).with_name(".env"))
    model = os.environ.get("NVIDIA_MODEL", "deepseek-ai/deepseek-v4-pro-0813")
    key = os.environ.get("NVIDIA_API_KEY")
    if not key:
        raise SystemExit("NVIDIA_API_KEY is missing.")
    with OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=key,
                timeout=20.0, max_retries=0) as client:
        for streaming in (True, False):
            result = {"model": model, "stream": streaming}
            start = perf_counter()
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": "Hi. Reply with one short greeting."}],
                    max_tokens=64, temperature=0.2, top_p=0.95, stream=streaming,
                    extra_body={"chat_template_kwargs": {
                        "enable_thinking" if "nemotron" in model.lower() else "thinking": False}},
                )
                if streaming:
                    parts = []
                    with response:
                        for chunk in response:
                            result.setdefault("first_chunk_seconds", round(perf_counter() - start, 3))
                            if chunk.choices and chunk.choices[0].delta.content:
                                result.setdefault("first_text_seconds", round(perf_counter() - start, 3))
                                parts.append(chunk.choices[0].delta.content)
                            if perf_counter() - start > 20:
                                result["stopped_at_time_budget"] = True
                                break
                    result["reply"] = "".join(parts)
                else:
                    result["reply"] = response.choices[0].message.content
                    result["finish_reason"] = response.choices[0].finish_reason
                result["status"] = "received"
            except Exception as error:
                result["error"] = type(error).__name__
                result["http_status"] = getattr(error, "status_code", None)
                result["cause"] = type(error.__cause__).__name__ if error.__cause__ else None
            result["total_seconds"] = round(perf_counter() - start, 3)
            print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
