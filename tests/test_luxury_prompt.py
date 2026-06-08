import pandas as pd

from ml.luxury_prompt import build_payload, build_prompt, CRITERIA


def test_build_prompt_contains_offer_ids(offers_parquet):
    df = pd.read_parquet(offers_parquet)
    prompt = build_prompt(df.head(2))
    assert "Offer 111" in prompt
    assert "Offer 222" in prompt
    assert "luxury scale" in prompt.lower()


def test_build_prompt_includes_criteria():
    df = pd.DataFrame(
        [{"cian_id": 1, "address_full": "a", "district": "b", "price_rub": 1,
          "rooms_count": 1, "total_area": 1.0, "description": "x"}]
    )
    prompt = build_prompt(df)
    assert CRITERIA[0] in prompt


def test_build_payload_from_parquet(offers_parquet):
    payload = build_payload(limit=1, parquet_path=offers_parquet)
    assert "Offer 111" in payload
    assert "10000000" in payload
