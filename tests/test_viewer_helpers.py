"""Тесты вспомогательной логики viewer без подключения к БД."""


class _OfferStub:
    def __init__(self, cian_id: int, price_rub: int | None):
        self.cian_id = cian_id
        self.price_rub = price_rub


def _attach_scores_stub(offer, luxury_data, predictions_data):
    """Копия логики скидки из viewer._attach_scores для изолированного теста."""
    lux = luxury_data.get(offer.cian_id)
    if lux:
        offer.luxury_description = lux["luxury_description"]
    else:
        offer.luxury_description = None

    pred = predictions_data.get(offer.cian_id)
    if pred is not None and offer.price_rub:
        offer.pred_price = int(pred)
        diff = offer.price_rub - offer.pred_price
        if diff > 0:
            offer.discount_pct = round(diff / offer.price_rub * 100, 1)
        else:
            offer.discount_pct = None
    else:
        offer.pred_price = None
        offer.discount_pct = None
    return offer


def test_discount_pct_when_listing_above_model():
    """Viewer считает diff = price - pred; скидка показывается при diff > 0."""
    o = _OfferStub(cian_id=2, price_rub=25_000_000)
    result = _attach_scores_stub(o, {}, {2: 20_000_000.0})
    assert result.pred_price == 20_000_000
    assert result.discount_pct == 20.0


def test_no_discount_when_listing_below_model():
    o = _OfferStub(cian_id=1, price_rub=20_000_000)
    result = _attach_scores_stub(o, {}, {1: 22_000_000.0})
    assert result.discount_pct is None


def test_luxury_score_attached():
    o = _OfferStub(cian_id=3, price_rub=10_000_000)
    lux = {3: {"luxury_description": 78}}
    result = _attach_scores_stub(o, lux, {})
    assert result.luxury_description == 78
    assert result.pred_price is None
