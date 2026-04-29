import json
import os
from typing import Iterator

import httpx

MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
DEFAULT_MODEL = "mistral-small-latest"


def score_luxury_batch(prompt_text: str, api_key: str = "", model: str = DEFAULT_MODEL) -> list[dict]:
    key = api_key or MISTRAL_API_KEY
    if not key:
        raise ValueError("MISTRAL_API_KEY not set")
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt_text}],
        "temperature": 0.3,
        "max_tokens": 2048,
    }
    with httpx.Client(timeout=60) as client:
        r = client.post(MISTRAL_API_URL, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    content = data["choices"][0]["message"]["content"]
    try:
        parsed = json.loads(content)
        return parsed.get("offers", [])
    except json.JSONDecodeError:
        return []


def batch_iterator(items: list, batch_size: int = 5) -> Iterator[list]:
    for i in range(0, len(items), batch_size):
        yield items[i:i + batch_size]
