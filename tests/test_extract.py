from parser.extract import (
    MAX_PHOTOS,
    build_address,
    extract_photos,
    extract_seller,
    find_geo_part,
    offer_to_row,
    to_float,
    to_int,
)


def test_to_float_handles_comma_decimal():
    assert to_float("75,18") == 75.18
    assert to_float(None) is None
    assert to_float("bad") is None


def test_to_int_from_string():
    assert to_int("3") == 3
    assert to_int("") is None


def test_offer_to_row_maps_core_fields(sample_offer_json):
    row = offer_to_row(sample_offer_json)
    assert row["cian_id"] == 123456789
    assert row["price_rub"] == 25_000_000
    assert row["rooms_count"] == 3
    assert row["district"] == "Хамовники"
    assert row["metro_name"] == "Парк культуры"
    assert row["jk_name"] == "Premium Towers"
    assert row["price_per_m2_rub"] == int(25_000_000 / 85.5)


def test_find_geo_part_and_address():
    address = [
        {"type": "raion", "name": "Тверской"},
        {"type": "street", "fullName": "ул. Тверская"},
    ]
    assert find_geo_part(address, "raion") == "Тверской"
    assert "Тверская" in build_address(address)


def test_extract_photos_respects_max(sample_offer_json):
    photos = extract_photos(sample_offer_json)
    assert len(photos) == MAX_PHOTOS
    assert photos[0]["position"] == 0
    assert photos[0]["url_original"] == "https://example.com/1.jpg"


def test_extract_seller(sample_offer_json):
    seller = extract_seller(sample_offer_json)
    assert seller["seller_type"] == "agency"
    assert seller["seller_name"] == "Агент"
    assert seller["seller_user_id"] == 999
