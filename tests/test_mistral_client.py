import json
from unittest.mock import MagicMock, patch

import pytest

from ml.mistral_client import batch_iterator, score_luxury_batch


def test_batch_iterator_splits_evenly():
    items = list(range(7))
    batches = list(batch_iterator(items, batch_size=3))
    assert batches == [[0, 1, 2], [3, 4, 5], [6]]


def test_score_luxury_batch_requires_api_key():
    with pytest.raises(ValueError, match="MISTRAL_API_KEY"):
        score_luxury_batch("prompt", api_key="")


def test_score_luxury_batch_parses_json_response():
    fake_response = MagicMock()
    fake_response.raise_for_status = MagicMock()
    fake_response.json.return_value = {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "offers": [{"cian_id": 111, "luxury_score": 72, "reason": "good view"}]
                })
            }
        }]
    }
    mock_client = MagicMock()
    mock_client.post.return_value = fake_response
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    with patch("ml.mistral_client.httpx.Client", return_value=mock_client):
        result = score_luxury_batch("test prompt", api_key="test-key")

    assert len(result) == 1
    assert result[0]["cian_id"] == 111
    assert result[0]["luxury_score"] == 72
