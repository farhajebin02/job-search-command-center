import json
import os
from functools import lru_cache

from google import genai
from google.genai import types


@lru_cache(maxsize=1)
def _client():
    return genai.Client(
        vertexai=True,
        project=os.environ["GCP_PROJECT_ID"],
        location=os.environ["GCP_LOCATION"],
    )


def _call(prompt: str, schema: dict, model: str):
    return _client().models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
        ),
    )


def generate_json(prompt: str, schema: dict, model: str | None = None) -> dict:
    resp = _call(prompt, schema, model or os.environ["GEMINI_BATCH_MODEL"])
    try:
        return json.loads(resp.text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError(f"Gemini did not return valid JSON: {resp.text!r}") from exc
