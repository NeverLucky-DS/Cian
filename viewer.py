import html as html_lib
import re

from flask import Flask, render_template_string, send_from_directory, request, abort
from sqlalchemy import select, desc, func, or_

from db.db import SessionLocal
from db.models import Offer, OfferPhoto


app = Flask(__name__)
PER_PAGE = 30


# превращает текст в html: абзацы по двойному переносу, маркированные списки по строкам с буллитом
def format_desc(text):
    if not text:
        return "—"
    parts = re.split(r"\n\s*\n", text.strip())
    out = []
    for part in parts:
        lines = [l.rstrip() for l in part.split("\n") if l.strip()]
        if lines and all(re.match(r"^[\u2022•\-\*]\s+", l) for l in lines):
            items = "".join(
                "<li>" + html_lib.escape(re.sub(r"^[\u2022•\-\*]\s+", "", l)) + "</li>"
                for l in lines
            )
            out.append("<ul>" + items + "</ul>")
        else:
            joined = "<br>".join(html_lib.escape(l) for l in lines)
            out.append("<p>" + joined + "</p>")
    return "".join(out)


# главная: список объявлений с фильтрами и пагинацией
LIST_HTML = """
<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Cian DB viewer</title>
<style>
body { font-family: -apple-system, Arial, sans-serif; margin: 16px; background:#f6f7f9; color:#222; }
h1 { margin: 0 0 12px 0; font-size: 20px; }
.bar { display:flex; gap:8px; margin-bottom:14px; flex-wrap:wrap; align-items:center; }
.bar input, .bar select { padding:6px 8px; border:1px solid #ccc; border-radius:6px; font-size:14px; }
.bar button { padding:6px 12px; border:0; background:#0a7cff; color:#fff; border-radius:6px; cursor:pointer; }
.stats { color:#666; font-size:13px; margin-bottom:10px; }
.grid { display:grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap:12px; }
.card { background:#fff; border:1px solid #e3e5e8; border-radius:10px; overflow:hidden; display:flex; flex-direction:column; }
.card img { width:100%; height:200px; object-fit:cover; background:#eee; }
.card .body { padding:10px 12px; display:flex; flex-direction:column; gap:4px; flex:1; }
.price { font-size:17px; font-weight:600; }
.meta { font-size:13px; color:#444; }
.addr { font-size:12px; color:#666; }
.tags { font-size:11px; color:#888; margin-top:4px; }
.card a { color:inherit; text-decoration:none; }
.card a.title-link:hover { color:#0a7cff; }
.pager { margin: 18px 0; display:flex; gap:8px; align-items:center; }
.pager a, .pager span { padding:6px 10px; border:1px solid #ccc; border-radius:6px; text-decoration:none; color:#222; background:#fff; }
.pager .cur { background:#0a7cff; color:#fff; border-color:#0a7cff; }
.badge { display:inline-block; padding:1px 6px; border-radius:4px; font-size:11px; background:#eef; color:#33a; margin-right:4px; }
.badge.nb { background:#fff0e0; color:#a55; }
</style>
</head>
<body>
<h1>Cian DB viewer</h1>
<form class="bar" method="get">
  <input type="text" name="q" value="{{ q or '' }}" placeholder="поиск по описанию/адресу/ЖК">
  <input type="number" name="rooms" value="{{ rooms or '' }}" placeholder="комнат" style="width:90px">
  <input type="number" name="price_max" value="{{ price_max or '' }}" placeholder="цена до, руб" style="width:160px">
  <select name="nb">
    <option value="">все</option>
    <option value="1" {% if nb == '1' %}selected{% endif %}>только новостройки</option>
    <option value="0" {% if nb == '0' %}selected{% endif %}>только вторичка</option>
  </select>
  <select name="sort">
    {% for v, label in [('new','новые'),('price_asc','цена ↑'),('price_desc','цена ↓'),('m2_asc','м2 ↑')] %}
      <option value="{{ v }}" {% if sort == v %}selected{% endif %}>{{ label }}</option>
    {% endfor %}
  </select>
  <button type="submit">применить</button>
</form>

<div class="stats">всего в БД: {{ total }} | страница {{ page }}/{{ pages }} | показано {{ offers|length }}</div>

<div class="grid">
{% for o in offers %}
  <div class="card">
    <a class="title-link" href="/offer/{{ o.cian_id }}">
      {% if o.cover %}
        <img src="/photos/{{ o.cian_id }}/{{ o.cover }}.webp" loading="lazy">
      {% else %}
        <img alt="нет фото">
      {% endif %}
      <div class="body">
        <div class="price">{{ "{:,}".format(o.price_rub).replace(',', ' ') if o.price_rub else '—' }} ₽</div>
        <div class="meta">
          {% if o.rooms_count %}{{ o.rooms_count }}-комн., {% endif %}
          {{ o.total_area or '—' }} м²{% if o.floor_number and o.floors_total %}, {{ o.floor_number }}/{{ o.floors_total }} эт.{% endif %}
        </div>
        <div class="addr">{{ o.address_full or '—' }}</div>
        <div class="addr">{% if o.metro_name %}м. {{ o.metro_name }}{% if o.metro_minutes %} · {{ o.metro_minutes }} мин{% endif %}{% endif %}</div>
        <div class="tags">
          {% if o.is_newbuilding %}<span class="badge nb">новостр.</span>{% endif %}
          {% if o.jk_name %}<span class="badge">{{ o.jk_name }}</span>{% endif %}
          {% if o.decoration %}<span class="badge">{{ o.decoration }}</span>{% endif %}
        </div>
      </div>
    </a>
  </div>
{% endfor %}
</div>

<div class="pager">
  {% if page > 1 %}<a href="?{{ qs(page=page-1) }}">‹ назад</a>{% endif %}
  <span class="cur">{{ page }} / {{ pages }}</span>
  {% if page < pages %}<a href="?{{ qs(page=page+1) }}">вперед ›</a>{% endif %}
</div>
</body></html>
"""


# страница одного объявления со всеми полями и фото
DETAIL_HTML = """
<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>{{ o.cian_id }} — {{ o.title or 'объявление' }}</title>
<style>
body { font-family: -apple-system, Arial, sans-serif; margin: 16px; background:#f6f7f9; color:#222; }
a.back { color:#0a7cff; text-decoration:none; }
h1 { margin: 8px 0; font-size: 22px; }
.price { font-size:24px; font-weight:700; }
.cols { display:grid; grid-template-columns: 2fr 1fr; gap:20px; margin-top:14px; }
.gallery { display:grid; grid-template-columns: repeat(3, 1fr); gap:6px; }
.gallery img { width:100%; height:160px; object-fit:cover; background:#eee; border-radius:6px; cursor:zoom-in; }
.info { background:#fff; border:1px solid #e3e5e8; border-radius:10px; padding:14px; }
.info dt { color:#666; font-size:12px; margin-top:8px; }
.info dd { margin: 0; font-size:14px; }
.desc { background:#fff; border:1px solid #e3e5e8; border-radius:10px; padding:14px; margin-top:14px; }
.desc p { margin: 0 0 10px 0; line-height:1.45; }
.desc ul { margin: 6px 0 10px 22px; padding:0; }
.desc li { margin: 2px 0; line-height:1.4; }
.modal { display:none; position:fixed; inset:0; background:rgba(0,0,0,0.85); z-index:9; align-items:center; justify-content:center; }
.modal img { max-width:95vw; max-height:95vh; }
.modal.on { display:flex; }
</style>
</head>
<body>
<a class="back" href="/">← к списку</a>
<h1>{{ o.title or ('Объявление #' ~ o.cian_id) }}</h1>
<div class="price">{{ "{:,}".format(o.price_rub).replace(',', ' ') if o.price_rub else '—' }} ₽
  {% if o.price_per_m2_rub %} <span style="font-size:14px;color:#666;">({{ "{:,}".format(o.price_per_m2_rub).replace(',', ' ') }} ₽/м²)</span>{% endif %}
</div>
<div><a href="{{ o.url }}" target="_blank">открыть на Cian ↗</a></div>

<div class="cols">
  <div>
    <div class="gallery">
      {% for ph in photos %}
        <img src="/photos/{{ o.cian_id }}/{{ ph.position }}.webp" loading="lazy" onclick="document.getElementById('m').classList.add('on'); document.getElementById('mi').src=this.src;">
      {% endfor %}
    </div>
    <div class="desc">{{ format_desc(o.description) | safe }}</div>
  </div>

  <div class="info">
    <dl>
      <dt>cian_id</dt><dd>{{ o.cian_id }}</dd>
      <dt>категория</dt><dd>{{ o.category }} ({{ o.deal_type }})</dd>
      <dt>комнат</dt><dd>{{ o.rooms_count or '—' }}{% if o.is_apartments %} (апартаменты){% endif %}</dd>
      <dt>площадь</dt><dd>{{ o.total_area or '—' }} м² (жилая {{ o.living_area or '—' }}, кухня {{ o.kitchen_area or '—' }})</dd>
      <dt>этаж</dt><dd>{{ o.floor_number or '—' }} из {{ o.floors_total or '—' }}</dd>
      <dt>отделка</dt><dd>{{ o.decoration or '—' }}</dd>
      <dt>вид из окон</dt><dd>{{ o.windows_view or '—' }}</dd>
      <dt>дом</dt><dd>{{ o.building_material or '—' }}{% if o.building_year %}, {{ o.building_year }} г.{% endif %}{% if o.parking_type %}, паркинг: {{ o.parking_type }}{% endif %}</dd>
      {% if o.deadline_year %}<dt>сдача</dt><dd>{{ o.deadline_quarter }} кв. {{ o.deadline_year }}</dd>{% endif %}
      {% if o.jk_name %}<dt>ЖК</dt><dd>{{ o.jk_name }}{% if o.jk_house %} · {{ o.jk_house }}{% endif %} ({{ o.jk_developer or '—' }})</dd>{% endif %}
      <dt>адрес</dt><dd>{{ o.address_full or '—' }}</dd>
      <dt>координаты</dt><dd>{{ o.lat }}, {{ o.lon }}</dd>
      {% if o.metro_name %}<dt>метро</dt><dd>{{ o.metro_name }}{% if o.metro_minutes %} · {{ o.metro_minutes }} мин ({{ o.metro_travel_type }}){% endif %}</dd>{% endif %}
      <dt>продавец</dt><dd>{{ o.seller_name or '—' }} ({{ o.seller_type or '—' }})</dd>
      {% if o.seller_phones %}<dt>телефоны</dt><dd>{% for p in o.seller_phones %}+{{ p.get('countryCode','') }}{{ p.get('number','') }}<br>{% endfor %}</dd>{% endif %}
      <dt>статус</dt><dd>{{ o.status }}</dd>
      <dt>создано</dt><dd>{{ o.creation_date }}</dd>
      <dt>правлено</dt><dd>{{ o.edit_date }}</dd>
      <dt>фото в БД</dt><dd>{{ photos|length }}</dd>
    </dl>
  </div>
</div>

<div id="m" class="modal" onclick="this.classList.remove('on');"><img id="mi"></div>
</body></html>
"""


# главный список с пагинацией и фильтрами
@app.route("/")
def index():
    q = request.args.get("q", "").strip()
    rooms = request.args.get("rooms", "").strip()
    price_max = request.args.get("price_max", "").strip()
    nb = request.args.get("nb", "").strip()
    sort = request.args.get("sort", "new").strip()
    page = max(1, int(request.args.get("page", 1)))

    with SessionLocal() as s:
        stmt = select(Offer)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(or_(
                Offer.description.ilike(like),
                Offer.address_full.ilike(like),
                Offer.jk_name.ilike(like),
                Offer.title.ilike(like),
            ))
        if rooms.isdigit():
            stmt = stmt.where(Offer.rooms_count == int(rooms))
        if price_max.isdigit():
            stmt = stmt.where(Offer.price_rub <= int(price_max))
        if nb == "1":
            stmt = stmt.where(Offer.is_newbuilding.is_(True))
        elif nb == "0":
            stmt = stmt.where(Offer.is_newbuilding.is_(False))

        # сортировка
        if sort == "price_asc":
            stmt = stmt.order_by(Offer.price_rub.asc().nulls_last())
        elif sort == "price_desc":
            stmt = stmt.order_by(Offer.price_rub.desc().nulls_last())
        elif sort == "m2_asc":
            stmt = stmt.order_by(Offer.total_area.asc().nulls_last())
        else:
            stmt = stmt.order_by(desc(Offer.first_seen_at))

        total = s.scalar(select(func.count()).select_from(stmt.subquery()))
        pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
        page = min(page, pages)
        offers = list(s.scalars(stmt.offset((page - 1) * PER_PAGE).limit(PER_PAGE)))

        # для каждого находим первую фотку (которая скачана)
        ids = [o.id for o in offers]
        cover = {}
        if ids:
            rows = s.execute(
                select(OfferPhoto.offer_id, func.min(OfferPhoto.position))
                .where(OfferPhoto.offer_id.in_(ids), OfferPhoto.path_local.isnot(None))
                .group_by(OfferPhoto.offer_id)
            ).all()
            cover = {r[0]: r[1] for r in rows}

        # навешиваем cover как атрибут
        view_offers = []
        for o in offers:
            o.cover = cover.get(o.id)
            view_offers.append(o)

    # утилита для построения query string при пагинации
    def qs(**override):
        params = {
            "q": q, "rooms": rooms, "price_max": price_max,
            "nb": nb, "sort": sort, "page": page,
        }
        params.update(override)
        return "&".join(f"{k}={v}" for k, v in params.items() if v not in (None, ""))

    return render_template_string(
        LIST_HTML,
        offers=view_offers, total=total, page=page, pages=pages,
        q=q, rooms=rooms, price_max=price_max, nb=nb, sort=sort, qs=qs,
    )


# карточка одного объявления
@app.route("/offer/<int:cian_id>")
def detail(cian_id):
    with SessionLocal() as s:
        o = s.scalar(select(Offer).where(Offer.cian_id == cian_id))
        if not o:
            abort(404)
        photos = list(s.scalars(
            select(OfferPhoto)
            .where(OfferPhoto.offer_id == o.id, OfferPhoto.path_local.isnot(None))
            .order_by(OfferPhoto.position)
        ))
    return render_template_string(DETAIL_HTML, o=o, photos=photos, format_desc=format_desc)


# раздаем локальные webp-фото
@app.route("/photos/<int:cian_id>/<path:fname>")
def photo(cian_id, fname):
    return send_from_directory(f"photos/{cian_id}", fname)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5005, debug=True)
