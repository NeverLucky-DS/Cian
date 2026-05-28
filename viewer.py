import html as html_lib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from flask import Flask, render_template_string, send_from_directory, request, abort, Response
from sqlalchemy import select, desc, func, or_

from db.db import SessionLocal
from db.models import Offer, OfferPhoto

app = Flask(__name__)
PER_PAGE = 30
LUXURY_FILE = Path("data/ml/luxury_scores.parquet")
PRED_FILE = Path("data/ml/predictions.csv")


def _read_table(path: Path) -> pd.DataFrame:
    if path.exists():
        if path.suffix == ".parquet":
            return pd.read_parquet(path)
        return pd.read_csv(path)
    csv_path = path.with_suffix(".csv")
    if csv_path.exists():
        return pd.read_csv(csv_path)
    return pd.DataFrame()


def _load_luxury_dict() -> dict[int, dict]:
    df = _read_table(LUXURY_FILE)
    if df.empty:
        return {}
    df = df.fillna({"luxury_description": 50, "luxury_photo": 50, "luxury_reason": ""})
    return {
        int(row.cian_id): {
            "luxury_description": int(row.luxury_description),
            "luxury_photo": int(row.luxury_photo),
            "luxury_reason": row.luxury_reason,
        }
        for row in df.itertuples()
    }


def _get_luxury_distribution() -> dict:
    df = _read_table(LUXURY_FILE)
    if df.empty:
        return {}
    desc_scores = df["luxury_description"].tolist()
    hist, bins = np.histogram(desc_scores, bins=20, range=(35, 100))
    return {
        "bins": bins.tolist(),
        "counts": hist.tolist(),
        "mean": float(df["luxury_description"].mean()),
        "std": float(df["luxury_description"].std()),
    }


def _load_pred_dict() -> dict[int, float]:
    df = _read_table(PRED_FILE)
    if df.empty:
        return {}
    return {int(row.cian_id): float(row.pred_price) for row in df.itertuples()}


LUXURY_DATA = _load_luxury_dict()
PREDICTIONS_DATA = _load_pred_dict()


def _attach_scores(o):
    lux = LUXURY_DATA.get(o.cian_id)
    if lux:
        o.luxury_description = lux["luxury_description"]
        o.luxury_photo = lux["luxury_photo"]
        o.luxury_reason = lux["luxury_reason"]
    else:
        o.luxury_description = None
        o.luxury_photo = None
        o.luxury_reason = ""

    pred = PREDICTIONS_DATA.get(o.cian_id)
    if pred is not None and o.price_rub:
        o.pred_price = int(pred)
        diff = o.price_rub - o.pred_price
        if diff > 0:
            o.discount_amount = diff
            o.discount_amount_fmt = f"{diff:,}".replace(",", " ")
            o.discount_pct = round(diff / o.price_rub * 100, 1)
        else:
            o.discount_amount = None
            o.discount_amount_fmt = None
            o.discount_pct = None
    else:
        o.pred_price = None
        o.discount_amount = None
        o.discount_amount_fmt = None
        o.discount_pct = None
    return o


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


# ─────────────────────────────── CSS ────────────────────────────────

SHARED_CSS = """
:root {
  --bg:         #F1F3F7;
  --surface:    #FFFFFF;
  --border:     #E2E5EB;
  --text:       #0F1117;
  --muted:      #68727F;
  --accent:     #1A56DB;
  --accent-lt:  #EBF1FF;
  --green:      #0A7C4B;
  --green-bg:   #E6F8F0;
  --red:        #D62B2B;
  --red-bg:     #FDEAEA;
  --amber:      #B45309;
  --amber-bg:   #FEF3C7;
  --r:          14px;
  --r-sm:       8px;
  --sh:         0 2px 12px rgba(0,0,0,.08);
  --sh-lg:      0 8px 32px rgba(0,0,0,.13);
  --t:          .18s ease;
  --font:       -apple-system,'Segoe UI',Arial,sans-serif;
}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:var(--font);background:var(--bg);color:var(--text);font-size:15px;line-height:1.5}
a{text-decoration:none;color:inherit}

/* ── HEADER ── */
.hdr{
  background:var(--surface);border-bottom:1px solid var(--border);
  padding:0 24px;height:56px;display:flex;align-items:center;gap:14px;
  position:sticky;top:0;z-index:100;box-shadow:0 1px 4px rgba(0,0,0,.06);
}
.logo{font-size:17px;font-weight:800;letter-spacing:-.3px}
.logo em{color:var(--accent);font-style:normal}
.cnt-badge{
  background:var(--accent-lt);color:var(--accent);
  font-size:12px;font-weight:700;padding:3px 10px;border-radius:20px;
}

/* ── FILTERS ── */
.filters{
  background:var(--surface);border-bottom:1px solid var(--border);
  padding:10px 24px;display:flex;gap:8px;flex-wrap:wrap;align-items:center;
}
.fi{
  padding:7px 12px;border:1.5px solid var(--border);border-radius:var(--r-sm);
  font-size:13.5px;background:var(--bg);color:var(--text);outline:none;
  transition:border-color var(--t),background var(--t);
}
.fi:focus{border-color:var(--accent);background:#fff}
.fbtn{
  padding:7px 20px;background:var(--accent);color:#fff;border:none;
  border-radius:var(--r-sm);font-size:13.5px;font-weight:700;cursor:pointer;
  transition:opacity var(--t);
}
.fbtn:hover{opacity:.88}

/* ── CONTAINER ── */
.wrap{max-width:1360px;margin:0 auto;padding:20px 24px}
.meta-bar{
  display:flex;justify-content:space-between;align-items:center;
  margin-bottom:16px;color:var(--muted);font-size:13px;
}

/* ── CHART ── */
.chart-box{
  background:var(--surface);border:1px solid var(--border);border-radius:var(--r);
  padding:16px 20px;margin-bottom:20px;
}
.chart-lbl{font-size:12px;color:var(--muted);margin-bottom:8px}
.chart-box canvas{display:block;width:100%;height:72px}

/* ── CARD GRID ── */
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px}

/* ── CARD ── */
.card{
  background:var(--surface);border-radius:var(--r);overflow:hidden;
  border:1px solid var(--border);box-shadow:0 1px 4px rgba(0,0,0,.06);
  transition:transform var(--t),box-shadow var(--t);
  display:flex;flex-direction:column;cursor:pointer;
}
.card:hover{transform:translateY(-4px);box-shadow:var(--sh-lg)}
.card-photo{position:relative;height:210px;background:#DDE1EA;overflow:hidden;flex-shrink:0}
.card-photo img{
  width:100%;height:100%;object-fit:cover;display:block;
  transition:transform .3s ease;
}
.card:hover .card-photo img{transform:scale(1.04)}
.card-photo.empty::after{
  content:'📷';position:absolute;inset:0;
  display:flex;align-items:center;justify-content:center;
  font-size:40px;opacity:.25;
}
.price-badge{
  position:absolute;bottom:10px;left:10px;
  background:rgba(10,12,18,.72);backdrop-filter:blur(8px);
  color:#fff;font-size:15px;font-weight:800;
  padding:5px 12px;border-radius:var(--r-sm);letter-spacing:-.2px;
}
.deal-tag{
  position:absolute;top:10px;right:10px;
  background:var(--green);color:#fff;
  font-size:11px;font-weight:700;padding:3px 9px;border-radius:20px;
}
.nb-tag{
  position:absolute;top:10px;left:10px;
  background:var(--accent);color:#fff;
  font-size:11px;font-weight:600;padding:3px 9px;border-radius:20px;
}
.card-body{padding:12px 14px;display:flex;flex-direction:column;gap:5px;flex:1}
.pills{display:flex;gap:5px;flex-wrap:wrap}
.pill{
  background:var(--bg);color:var(--text);
  font-size:12.5px;font-weight:600;padding:3px 9px;border-radius:6px;
}
.metro-pill{
  display:inline-flex;align-items:center;gap:3px;
  font-size:12px;font-weight:600;color:var(--accent);
  background:var(--accent-lt);padding:2px 9px;border-radius:5px;
}
.card-addr{font-size:12.5px;color:var(--muted);line-height:1.4}
.jk-lbl{font-size:12px;color:var(--muted);font-weight:500}
.pred-lbl{
  font-size:12px;color:var(--green);font-weight:700;
  display:flex;align-items:center;gap:4px;
}
.lux-row{display:flex;align-items:center;gap:8px;margin-top:2px}
.lux-bg{flex:1;height:4px;background:var(--border);border-radius:2px;overflow:hidden}
.lux-fill{height:100%;border-radius:2px;background:linear-gradient(90deg,#F59E0B,#10B981,#7B51F0)}
.lux-n{font-size:11px;color:var(--muted);font-weight:700;white-space:nowrap}

/* ── PAGER ── */
.pager{display:flex;justify-content:center;gap:6px;margin:28px 0 12px}
.pager a,.pager span{
  width:38px;height:38px;display:flex;align-items:center;justify-content:center;
  border:1.5px solid var(--border);border-radius:var(--r-sm);
  font-size:14px;font-weight:600;background:var(--surface);color:var(--text);
  transition:all var(--t);
}
.pager a:hover{border-color:var(--accent);color:var(--accent)}
.pager .cur{background:var(--accent);border-color:var(--accent);color:#fff}

/* ── DETAIL ── */
.back-lnk{
  display:inline-flex;align-items:center;gap:6px;
  color:var(--muted);font-size:14px;padding:16px 24px;
  transition:color var(--t);
}
.back-lnk:hover{color:var(--accent)}
.detail-wrap{
  display:grid;grid-template-columns:1fr 340px;
  gap:24px;max-width:1200px;margin:0 auto;padding:0 24px 48px;
}
.gal-main img{
  width:100%;height:460px;object-fit:cover;
  border-radius:var(--r);display:block;
  transition:opacity .2s;
}
.gal-main .no-img{
  height:460px;background:var(--border);border-radius:var(--r);
  display:flex;align-items:center;justify-content:center;
  color:var(--muted);font-size:48px;
}
.gal-thumbs{display:flex;gap:8px;margin-top:8px;flex-wrap:wrap}
.gal-thumbs img{
  width:82px;height:62px;object-fit:cover;border-radius:6px;cursor:pointer;
  border:2px solid transparent;transition:all var(--t);opacity:.72;
}
.gal-thumbs img:hover,.gal-thumbs img.on{border-color:var(--accent);opacity:1}
.price-card{
  background:var(--surface);border:1px solid var(--border);border-radius:var(--r);
  padding:20px;position:sticky;top:72px;height:fit-content;
  box-shadow:var(--sh);
}
.price-main{font-size:26px;font-weight:900;letter-spacing:-.5px;line-height:1.2;margin-bottom:3px}
.price-m2{font-size:13px;color:var(--muted);margin-bottom:16px}
.dspecs{
  display:grid;grid-template-columns:1fr 1fr;gap:10px;
  padding-bottom:14px;margin-bottom:14px;border-bottom:1px solid var(--border);
}
.ds-lbl{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.6px;margin-bottom:2px}
.ds-val{font-size:14px;font-weight:700}
.metro-blk{
  display:flex;align-items:center;gap:10px;
  padding:10px 0;border-bottom:1px solid var(--border);margin-bottom:12px;
}
.metro-ico{font-size:20px}
.metro-nm{font-weight:700;font-size:14px}
.metro-d{font-size:12px;color:var(--muted)}
.pred-blk{
  background:var(--green-bg);border-radius:var(--r-sm);
  padding:12px;margin-bottom:12px;
}
.pred-ttl{font-size:11px;color:var(--green);text-transform:uppercase;letter-spacing:.6px;font-weight:800;margin-bottom:4px}
.pred-v{font-size:17px;font-weight:800;color:var(--green)}
.pred-d{font-size:12px;color:var(--green);margin-top:2px}
.cian-btn{
  display:block;text-align:center;padding:11px;
  background:var(--accent);color:#fff;border-radius:var(--r-sm);
  font-weight:700;font-size:14px;transition:opacity var(--t);margin-top:14px;
}
.cian-btn:hover{opacity:.88}
.gauge-wrap{margin-top:14px;padding-top:14px;border-top:1px solid var(--border)}
.gauge-ttl{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.6px;font-weight:700;margin-bottom:6px}
.gauge-n{font-size:22px;font-weight:900;margin-bottom:5px}
.gauge-n small{font-size:14px;font-weight:400;color:var(--muted)}
.gauge-bg{height:8px;background:var(--border);border-radius:4px;overflow:hidden;margin-bottom:4px}
.gauge-fill{height:100%;border-radius:4px;background:linear-gradient(90deg,#F59E0B,#10B981,#7B51F0)}
.gauge-ends{display:flex;justify-content:space-between;font-size:11px;color:var(--muted)}
.gauge-rsn{font-size:12px;color:var(--muted);margin-top:6px;line-height:1.4}

/* ── FULL SPECS ── */
.sec-ttl{
  font-size:15px;font-weight:800;margin:24px 0 12px;
  padding-bottom:8px;border-bottom:1px solid var(--border);
}
.fspecs{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:20px}
.fs-item{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-sm);padding:12px}
.fs-lbl{font-size:11px;color:var(--muted);margin-bottom:3px}
.fs-val{font-size:14px;font-weight:700}
.desc-box{
  background:var(--surface);border:1px solid var(--border);border-radius:var(--r);
  padding:20px;line-height:1.65;font-size:14px;color:var(--text);
}
.desc-box p{margin-bottom:10px}
.desc-box ul{margin:6px 0 10px 20px}
.desc-box li{margin:3px 0}

/* ── RESPONSIVE ── */
@media(max-width:900px){
  .detail-wrap{grid-template-columns:1fr}
  .price-card{position:static}
  .fspecs{grid-template-columns:repeat(2,1fr)}
}
@media(max-width:600px){
  .wrap{padding:12px 14px}
  .grid{grid-template-columns:1fr}
  .filters,.hdr{padding:8px 14px}
  .fspecs{grid-template-columns:1fr}
  .detail-wrap{padding:0 14px 32px}
  .gal-main img{height:240px}
}
"""


@app.route("/style.css")
def css():
    return Response(SHARED_CSS, mimetype="text/css",
                    headers={"Cache-Control": "public, max-age=3600"})


# ─────────────────────────── LIST PAGE ──────────────────────────────

LIST_HTML = """
<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cian DB Viewer</title>
<link rel="stylesheet" href="/style.css">
</head>
<body>

<header class="hdr">
  <div class="logo">Cian <em>DB</em> Viewer</div>
  <span class="cnt-badge">{{ total }} объявлений</span>
</header>

<form class="filters" method="get">
  <input class="fi" type="text" name="q" value="{{ q or '' }}"
         placeholder="🔍  поиск по адресу / ЖК / описанию" style="min-width:220px;flex:1">
  <select class="fi" name="rooms">
    <option value="">Комнаты</option>
    {% for r in [1,2,3,4,5] %}
      <option value="{{ r }}" {% if rooms == r|string %}selected{% endif %}>{{ r }}-комн.</option>
    {% endfor %}
    <option value="0" {% if rooms == '0' %}selected{% endif %}>Студия</option>
  </select>
  <input class="fi" type="number" name="price_max" value="{{ price_max or '' }}"
         placeholder="Цена до, ₽" style="width:150px">
  <select class="fi" name="nb">
    <option value="">Любой тип</option>
    <option value="1" {% if nb == '1' %}selected{% endif %}>Новостройки</option>
    <option value="0" {% if nb == '0' %}selected{% endif %}>Вторичка</option>
  </select>
  <select class="fi" name="sort">
    <option value="deal"       {% if sort=='deal'       %}selected{% endif %}>Лучшая скидка</option>
    <option value="new"        {% if sort=='new'        %}selected{% endif %}>Новые</option>
    <option value="price_asc"  {% if sort=='price_asc'  %}selected{% endif %}>Цена ↑</option>
    <option value="price_desc" {% if sort=='price_desc' %}selected{% endif %}>Цена ↓</option>
    <option value="m2_asc"     {% if sort=='m2_asc'     %}selected{% endif %}>Площадь ↑</option>
  </select>
  <button class="fbtn" type="submit">Применить</button>
</form>

<div class="wrap">

{% if lux_dist.bins %}
<div class="chart-box">
  <div class="chart-lbl">
    Luxury-оценки по описанию — среднее {{ lux_dist.mean|round(1) }}, σ = {{ lux_dist.std|round(1) }}
  </div>
  <canvas id="lc"></canvas>
</div>
<script>
(function(){
  const b={{ lux_dist.bins|tojson }}, c={{ lux_dist.counts|tojson }};
  const cv=document.getElementById('lc');
  cv.width=cv.parentElement.clientWidth-40; cv.height=72;
  const ctx=cv.getContext('2d'), bw=cv.width/(b.length-1), max=Math.max(...c);
  const g=ctx.createLinearGradient(0,0,cv.width,0);
  g.addColorStop(0,'#F59E0B'); g.addColorStop(.5,'#10B981'); g.addColorStop(1,'#7B51F0');
  ctx.fillStyle=g;
  for(let i=0;i<c.length;i++){
    const h=(c[i]/max)*56, x=i*bw, y=60-h;
    ctx.fillRect(x,y,Math.max(bw-2,1),h);
  }
  ctx.fillStyle='#68727F'; ctx.font='11px -apple-system,sans-serif';
  ctx.fillText(String(Math.round(b[0])),0,72);
  ctx.textAlign='right';
  ctx.fillText(String(Math.round(b[b.length-1])),cv.width,72);
})();
</script>
{% endif %}

<div class="meta-bar">
  <span>Страница {{ page }} из {{ pages }} · {{ offers|length }} показано</span>
</div>

<div class="grid">
{% for o in offers %}
<a href="/offer/{{ o.cian_id }}" class="card">
  <div class="card-photo {% if o.cover is none %}empty{% endif %}">
    {% if o.cover is not none %}
      <img src="/photos/{{ o.cian_id }}/{{ o.cover }}.webp" loading="lazy"
           onerror="this.parentElement.classList.add('empty'); this.remove()">
    {% endif %}
    <div class="price-badge">
      {{ "{:,}".format(o.price_rub).replace(',', ' ') if o.price_rub else '—' }} ₽
    </div>
    {% if o.is_newbuilding %}
      <div class="nb-tag">Новостройка</div>
    {% endif %}
    {% if o.discount_pct and o.discount_pct > 3 %}
      <div class="deal-tag">−{{ o.discount_pct }}% модель</div>
    {% endif %}
  </div>
  <div class="card-body">
    <div class="pills">
      {% if o.rooms_count %}<span class="pill">{{ o.rooms_count }}-комн.</span>{% endif %}
      {% if o.total_area %}<span class="pill">{{ o.total_area }} м²</span>{% endif %}
      {% if o.floor_number and o.floors_total %}
        <span class="pill">{{ o.floor_number }}/{{ o.floors_total }} эт.</span>
      {% endif %}
    </div>
    {% if o.metro_name %}
      <span class="metro-pill">🚇 {{ o.metro_name }}{% if o.metro_minutes %} · {{ o.metro_minutes }} мин{% endif %}</span>
    {% endif %}
    <div class="card-addr">{{ o.address_full or '—' }}</div>
    {% if o.jk_name %}
      <div class="jk-lbl">ЖК {{ o.jk_name }}</div>
    {% endif %}
    {% if o.pred_price %}
      <div class="pred-lbl">
        ✦ Модель: {{ "{:,}".format(o.pred_price).replace(',', ' ') }} ₽{% if o.discount_pct %} · −{{ o.discount_pct }}%{% endif %}
      </div>
    {% endif %}
    {% if o.luxury_description %}
      <div class="lux-row">
        <div class="lux-bg">
          <div class="lux-fill" style="width:{{ o.luxury_description }}%"></div>
        </div>
        <span class="lux-n">Lux {{ o.luxury_description }}</span>
      </div>
    {% endif %}
  </div>
</a>
{% endfor %}
</div>

<div class="pager">
  {% if page > 1 %}<a href="?{{ qs(page=page-1) }}">‹</a>{% endif %}
  <span class="cur">{{ page }}&thinsp;/&thinsp;{{ pages }}</span>
  {% if page < pages %}<a href="?{{ qs(page=page+1) }}">›</a>{% endif %}
</div>
</div>
</body></html>
"""


# ─────────────────────────── DETAIL PAGE ────────────────────────────

DETAIL_HTML = """
<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ o.title or ('Объявление #' ~ o.cian_id|string) }} — Cian DB</title>
<link rel="stylesheet" href="/style.css">
</head>
<body>

<a class="back-lnk" href="/">← К списку</a>

<div class="detail-wrap">

  <!-- ═══ LEFT: gallery + specs ═══ -->
  <div>
    <div class="gal-main">
      {% if photos %}
        <img id="mp" src="/photos/{{ o.cian_id }}/{{ photos[0].position }}.webp"
             alt="фото" onerror="this.outerHTML='<div class=no-img>📷</div>'">
      {% else %}
        <div class="no-img">📷</div>
      {% endif %}
    </div>

    {% if photos|length > 1 %}
    <div class="gal-thumbs">
      {% for ph in photos %}
      <img src="/photos/{{ o.cian_id }}/{{ ph.position }}.webp"
           loading="lazy"
           class="{{ 'on' if loop.index0 == 0 else '' }}"
           onerror="this.remove()"
           onclick="
             var mp=document.getElementById('mp');
             mp.style.opacity=0;
             mp.src=this.src;
             mp.onload=function(){mp.style.opacity=1};
             document.querySelectorAll('.gal-thumbs img').forEach(i=>i.classList.remove('on'));
             this.classList.add('on');
           ">
      {% endfor %}
    </div>
    {% endif %}

    <!-- full specs -->
    <div class="sec-ttl">Характеристики</div>
    <div class="fspecs">
      {% set sp = [
        ('Категория',    o.category),
        ('Тип сделки',   o.deal_type),
        ('Комнаты',      o.rooms_count|string ~ '-комн.' if o.rooms_count else ('Студия' if o.rooms_count == 0 else '—')),
        ('Площадь общ.', o.total_area|string ~ ' м²' if o.total_area else '—'),
        ('Площадь жил.', o.living_area|string ~ ' м²' if o.living_area else '—'),
        ('Кухня',        o.kitchen_area|string ~ ' м²' if o.kitchen_area else '—'),
        ('Этаж',         (o.floor_number|string ~ ' из ' ~ o.floors_total|string) if o.floor_number and o.floors_total else '—'),
        ('Отделка',      o.decoration or '—'),
        ('Вид из окон',  o.windows_view or '—'),
        ('Материал',     o.building_material or '—'),
        ('Год постройки',o.building_year or '—'),
        ('Паркинг',      o.parking_type or '—'),
        ('ЖК',           o.jk_name or '—'),
        ('Девелопер',    o.jk_developer or '—'),
        ('Продавец',     (o.seller_name ~ ' (' ~ o.seller_type ~ ')') if o.seller_name and o.seller_type else (o.seller_name or o.seller_type or '—')),
        ('ID Cian',      o.cian_id|string),
      ] %}
      {% for lbl, val in sp %}
      <div class="fs-item">
        <div class="fs-lbl">{{ lbl }}</div>
        <div class="fs-val">{{ val }}</div>
      </div>
      {% endfor %}
    </div>

    {% if o.description %}
    <div class="sec-ttl">Описание</div>
    <div class="desc-box">{{ format_desc(o.description)|safe }}</div>
    {% endif %}
  </div>

  <!-- ═══ RIGHT: sticky price card ═══ -->
  <div>
    <div class="price-card">
      <div class="price-main">
        {{ "{:,}".format(o.price_rub).replace(',', ' ') if o.price_rub else '—' }} ₽
      </div>
      {% if o.price_per_m2_rub %}
      <div class="price-m2">{{ "{:,}".format(o.price_per_m2_rub).replace(',', ' ') }} ₽ / м²</div>
      {% endif %}

      <div class="dspecs">
        <div>
          <div class="ds-lbl">Комнаты</div>
          <div class="ds-val">{{ o.rooms_count or '—' }}</div>
        </div>
        <div>
          <div class="ds-lbl">Площадь</div>
          <div class="ds-val">{{ o.total_area or '—' }} м²</div>
        </div>
        <div>
          <div class="ds-lbl">Этаж</div>
          <div class="ds-val">{{ o.floor_number or '—' }} / {{ o.floors_total or '—' }}</div>
        </div>
        <div>
          <div class="ds-lbl">Год</div>
          <div class="ds-val">{{ o.building_year or '—' }}</div>
        </div>
      </div>

      {% if o.metro_name %}
      <div class="metro-blk">
        <span class="metro-ico">🚇</span>
        <div>
          <div class="metro-nm">{{ o.metro_name }}</div>
          {% if o.metro_minutes %}
          <div class="metro-d">{{ o.metro_minutes }} мин · {{ o.metro_travel_type or 'пешком' }}</div>
          {% endif %}
        </div>
      </div>
      {% endif %}

      {% if o.pred_price %}
      <div class="pred-blk">
        <div class="pred-ttl">Оценка ML-модели</div>
        <div class="pred-v">{{ "{:,}".format(o.pred_price).replace(',', ' ') }} ₽</div>
        {% if o.discount_pct %}
        <div class="pred-d">Переоценено на {{ o.discount_pct }}% (+{{ o.discount_amount_fmt }} ₽)</div>
        {% endif %}
      </div>
      {% endif %}

      {% if o.luxury_description %}
      <div class="gauge-wrap">
        <div class="gauge-ttl">Luxury Score — описание</div>
        <div class="gauge-n">{{ o.luxury_description }}<small> / 100</small></div>
        <div class="gauge-bg">
          <div class="gauge-fill" style="width:{{ o.luxury_description }}%"></div>
        </div>
        <div class="gauge-ends"><span>Эконом</span><span>Люкс</span></div>
        {% if o.luxury_reason %}
        <div class="gauge-rsn">{{ o.luxury_reason }}</div>
        {% endif %}
      </div>
      {% endif %}

      {% if o.luxury_photo %}
      <div class="gauge-wrap">
        <div class="gauge-ttl">Luxury Score — фото</div>
        <div class="gauge-n">{{ o.luxury_photo }}<small> / 100</small></div>
        <div class="gauge-bg">
          <div class="gauge-fill" style="width:{{ o.luxury_photo }}%"></div>
        </div>
      </div>
      {% endif %}

      <a href="{{ o.url }}" target="_blank" class="cian-btn">Открыть на Cian ↗</a>
    </div>
  </div>

</div>
</body></html>
"""


# ─────────────────────── ROUTES ─────────────────────────────────────

@app.route("/")
def index():
    q = request.args.get("q", "").strip()
    rooms = request.args.get("rooms", "").strip()
    price_max = request.args.get("price_max", "").strip()
    nb = request.args.get("nb", "").strip()
    sort = request.args.get("sort", "deal").strip()
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

        if sort == "deal":
            offers = list(s.scalars(stmt))
        else:
            offers = list(s.scalars(stmt.offset((page - 1) * PER_PAGE).limit(PER_PAGE)))

        offers = [_attach_scores(o) for o in offers]
        if sort == "deal":
            offers.sort(key=lambda x: x.discount_pct if x.discount_pct is not None else -999, reverse=True)
            start = (page - 1) * PER_PAGE
            offers = offers[start:start + PER_PAGE]

        ids = [o.id for o in offers]
        cover = {}
        if ids:
            non_layout = s.execute(
                select(OfferPhoto.offer_id, func.min(OfferPhoto.position))
                .where(
                    OfferPhoto.offer_id.in_(ids),
                    OfferPhoto.path_local.isnot(None),
                    OfferPhoto.is_layout.is_(False),
                )
                .group_by(OfferPhoto.offer_id)
            ).all()
            cover = {r[0]: r[1] for r in non_layout}
            missing = [i for i in ids if i not in cover]
            if missing:
                fallback = s.execute(
                    select(OfferPhoto.offer_id, func.min(OfferPhoto.position))
                    .where(
                        OfferPhoto.offer_id.in_(missing),
                        OfferPhoto.path_local.isnot(None),
                    )
                    .group_by(OfferPhoto.offer_id)
                ).all()
                cover.update({r[0]: r[1] for r in fallback})

        for o in offers:
            o.cover = cover.get(o.id)

    def qs(**override):
        params = {
            "q": q, "rooms": rooms, "price_max": price_max,
            "nb": nb, "sort": sort, "page": page,
        }
        params.update(override)
        return "&".join(f"{k}={v}" for k, v in params.items() if v not in (None, ""))

    lux_dist = _get_luxury_distribution()
    return render_template_string(
        LIST_HTML,
        offers=offers, total=total, page=page, pages=pages,
        q=q, rooms=rooms, price_max=price_max, nb=nb, sort=sort, qs=qs,
        lux_dist=lux_dist,
    )


@app.route("/offer/<int:cian_id>")
def detail(cian_id):
    with SessionLocal() as s:
        o = s.scalar(select(Offer).where(Offer.cian_id == cian_id))
        if not o:
            abort(404)
        _attach_scores(o)
        photos = list(s.scalars(
            select(OfferPhoto)
            .where(OfferPhoto.offer_id == o.id, OfferPhoto.path_local.isnot(None))
            .order_by(OfferPhoto.position)
        ))
    return render_template_string(DETAIL_HTML, o=o, photos=photos, format_desc=format_desc)


@app.route("/photos/<int:cian_id>/<path:fname>")
def photo(cian_id, fname):
    return send_from_directory(f"photos/{cian_id}", fname)


if __name__ == "__main__":
    import os
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5005"))
    debug = os.environ.get("DEBUG", "0") == "1"

    if debug:
        app.run(host=host, port=port, debug=True)
    else:
        try:
            from waitress import serve
            print(f"viewer → http://{host}:{port}")
            serve(app, host=host, port=port, threads=8)
        except ImportError:
            app.run(host=host, port=port, debug=False)
