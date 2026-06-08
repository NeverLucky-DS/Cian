import pandas as pd
import pytest


@pytest.fixture
def sample_offer_json():
    return {
        "cianId": 123456789,
        "category": "flatSale",
        "dealType": "sale",
        "offerType": "flat",
        "title": "3-комн. квартира, 85 м²",
        "description": "Панорамные окна, дизайнерская отделка.",
        "totalArea": "85.5",
        "roomsCount": 3,
        "floorNumber": 12,
        "decoration": "fine",
        "bargainTerms": {"priceRur": 25_000_000, "currency": "RUB"},
        "building": {
            "floorsCount": 25,
            "buildYear": 2019,
            "materialType": "monolith",
            "ceilingHeight": 3.2,
        },
        "geo": {
            "address": [
                {"type": "location", "name": "Москва"},
                {"type": "raion", "name": "Хамовники"},
                {"type": "street", "name": "ул. Льва Толстого"},
                {"type": "house", "name": "16"},
                {"type": "metro", "name": "Парк культуры"},
            ],
            "coordinates": {"lat": 55.73, "lng": 37.59},
            "jk": {"id": 100, "name": "Premium Towers"},
        },
        "photos": [
            {"fullUrl": "https://example.com/1.jpg", "isLayout": False},
            {"fullUrl": "https://example.com/2.jpg", "isLayout": True},
            {"fullUrl": "https://example.com/3.jpg", "isLayout": False},
            {"fullUrl": "https://example.com/4.jpg", "isLayout": False},
        ],
        "user": {"name": "Агент", "accountType": "agency", "userId": 999},
        "phones": [{"countryCode": "7", "number": "9001234567"}],
    }


@pytest.fixture
def offers_parquet(tmp_path):
    df = pd.DataFrame(
        [
            {
                "cian_id": 111,
                "address_full": "Москва, ул. Тестовая, 1",
                "district": "ЦАО",
                "price_rub": 10_000_000,
                "rooms_count": 2,
                "total_area": 55.0,
                "description": "Комфорт-класс, рядом парк.",
            },
            {
                "cian_id": 222,
                "address_full": "Москва, ул. Примерная, 5",
                "district": "САО",
                "price_rub": 30_000_000,
                "rooms_count": 4,
                "total_area": 120.0,
                "description": "Панорамный вид, премиальная отделка.",
            },
        ]
    )
    path = tmp_path / "offers.parquet"
    df.to_parquet(path, index=False)
    return path
