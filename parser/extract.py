from datetime import datetime


# безопасное приведение к float (Cian отдает площади строками: "75.18")
def to_float(v):
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def to_int(v):
    if v is None or v == "":
        return None
    try:
        return int(float(str(v).replace(",", ".")))
    except (TypeError, ValueError):
        return None


def to_dt(v):
    if not v:
        return None
    # бывают форматы ISO и unix timestamp в строке
    try:
        if isinstance(v, (int, float)) or (isinstance(v, str) and v.isdigit()):
            return datetime.fromtimestamp(int(v))
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


# вытаскиваем элементы адреса по типу из geo.address
def find_geo_part(address_list, type_name):
    for a in address_list or []:
        if a.get("type") == type_name:
            return a.get("name") or a.get("shortName") or a.get("fullName")
    return None


def build_address(address_list):
    # склеиваем человекочитаемый адрес из частей
    parts = []
    for a in address_list or []:
        nm = a.get("fullName") or a.get("name")
        if nm:
            parts.append(nm)
    return ", ".join(parts) if parts else None


def pick_metro(geo):
    # сначала из address (там основное метро), потом из undergrounds (полный список)
    if not geo:
        return None, None, None
    for a in geo.get("address", []) or []:
        if a.get("type") == "metro" or a.get("geoType") == "underground":
            return a.get("name"), None, None
    ugs = geo.get("undergrounds") or []
    if ugs:
        u = ugs[0]
        return u.get("name"), to_int(u.get("travelTime")), u.get("travelType")
    return None, None, None


# универсальный конвертер dict-оффера в kwargs для модели Offer
# принимает либо элемент из listing.results.offers, либо offerData.offer
def offer_to_row(offer, url=None):
    bargain = offer.get("bargainTerms") or {}
    building = offer.get("building") or {}
    geo = offer.get("geo") or {}
    nb = offer.get("newbuilding") or {}

    # цена: на листинге priceRur, на карточке priceTotalRur/priceTotal
    price = (
        to_int(bargain.get("priceRur"))
        or to_int(bargain.get("price"))
        or to_int(offer.get("priceTotalRur"))
        or to_int(offer.get("priceTotal"))
    )

    address_list = geo.get("address") or []
    metro_name, metro_min, metro_travel = pick_metro(geo)
    coords = geo.get("coordinates") or {}
    jk = geo.get("jk") or {}

    deadline = building.get("deadline") or {}
    quarter_map = {"first": 1, "second": 2, "third": 3, "fourth": 4}
    deadline_q = deadline.get("quarter")
    if isinstance(deadline_q, str):
        deadline_q = quarter_map.get(deadline_q)

    # цена за м2
    price_per_m2 = None
    if price and to_float(offer.get("totalArea")):
        price_per_m2 = int(price / to_float(offer.get("totalArea")))

    # is_newbuilding по категории
    cat = offer.get("category")
    is_nb = bool(nb) or (isinstance(cat, str) and "newBuilding" in cat)

    # url приоритет: явный (с фазы 1) > offer.fullUrl > сборка по cianId
    cian_id = to_int(offer.get("cianId") or offer.get("id"))
    final_url = url or offer.get("fullUrl")
    if not final_url and cian_id:
        final_url = f"https://www.cian.ru/sale/flat/{cian_id}/"

    row = dict(
        cian_id=cian_id,
        url=final_url,
        category=cat,
        deal_type=offer.get("dealType"),
        offer_type=offer.get("offerType"),
        flat_type=offer.get("flatType"),
        is_apartments=offer.get("isApartments"),
        is_newbuilding=is_nb,
        title=offer.get("title"),
        description=offer.get("description"),
        price_rub=price,
        price_per_m2_rub=price_per_m2,
        currency=bargain.get("currency"),
        mortgage_allowed=bargain.get("mortgageAllowed"),
        sale_type=bargain.get("saleType"),
        rooms_count=to_int(offer.get("roomsCount")),
        total_area=to_float(offer.get("totalArea")),
        living_area=to_float(offer.get("livingArea")),
        kitchen_area=to_float(offer.get("kitchenArea")),
        floor_number=to_int(offer.get("floorNumber")),
        floors_total=to_int(building.get("floorsCount")),
        ceiling_height=to_float(building.get("ceilingHeight")),
        decoration=offer.get("decoration"),
        windows_view=offer.get("windowsViewType"),
        balconies_count=to_int(offer.get("balconiesCount")),
        loggias_count=to_int(offer.get("loggiasCount")),
        building_year=to_int(building.get("buildYear")),
        building_material=building.get("materialType") or building.get("houseMaterialType"),
        building_class=building.get("classType"),
        parking_type=(building.get("parking") or {}).get("type") if isinstance(building.get("parking"), dict) else None,
        passenger_lifts=to_int(building.get("passengerLiftsCount")),
        cargo_lifts=to_int(building.get("cargoLiftsCount")),
        deadline_year=to_int(deadline.get("year")),
        deadline_quarter=to_int(deadline_q),
        is_complete=deadline.get("isComplete"),
        jk_id=to_int(jk.get("id")),
        jk_name=jk.get("name"),
        jk_developer=(jk.get("developer") or {}).get("name") if isinstance(jk.get("developer"), dict) else None,
        jk_house=(jk.get("house") or {}).get("name") if isinstance(jk.get("house"), dict) else None,
        region=find_geo_part(address_list, "location"),
        okrug=find_geo_part(address_list, "okrug"),
        district=find_geo_part(address_list, "raion"),
        street=find_geo_part(address_list, "street"),
        house=find_geo_part(address_list, "house"),
        address_full=build_address(address_list),
        lat=to_float(coords.get("lat")),
        lon=to_float(coords.get("lng") or coords.get("lon")),
        metro_name=metro_name,
        metro_minutes=metro_min,
        metro_travel_type=metro_travel,
        creation_date=to_dt(offer.get("creationDate")),
        edit_date=to_dt(offer.get("editDate")),
        publication_date=to_dt(offer.get("publicationDate")),
        status=offer.get("status"),
        raw_json=offer,
    )
    return row


# извлекаем продавца из offerData (карточка) или offer.user (листинг)
def extract_seller(offer_data_or_listing_offer):
    # на карточке: offerData.agent + offerData.offer.phones
    # на листинге: offer.user + offer.phones
    agent = offer_data_or_listing_offer.get("agent") if isinstance(offer_data_or_listing_offer, dict) else None
    user = None
    phones_field = None
    if agent:
        user = agent
        phones_field = agent.get("phones")
    else:
        # это сам offer
        user = offer_data_or_listing_offer.get("user") or {}
        phones_field = offer_data_or_listing_offer.get("phones")

    seller_type = (user or {}).get("accountType") or (user or {}).get("userType")
    seller_name = (user or {}).get("name") or (user or {}).get("companyName")
    seller_user_id = (user or {}).get("userId") or (user or {}).get("cianUserId")
    return dict(
        seller_type=seller_type,
        seller_name=seller_name,
        seller_user_id=int(seller_user_id) if seller_user_id else None,
        seller_phones=phones_field,
    )


# из offer вытащить список фото в виде [{position, url, is_layout}]
def extract_photos(offer):
    photos = offer.get("photos") or []
    out = []
    for i, p in enumerate(photos):
        url = p.get("fullUrl") or p.get("thumbnailUrl") or p.get("miniUrl")
        if not url:
            continue
        out.append({
            "position": i,
            "url_original": url,
            "is_layout": bool(p.get("isLayout")),
        })
    return out
