"""
Telegram-бот для дизайн-канала.

10:00 МСК — один пост (формат «что украсть»). Суббота — разбор проекта.
18:00 МСК — дайджест дня (3-4 материала со связками).
Пятница — мероприятия, музеи, выставки (утром карточка, вечером подборка).
Воскресенье — выходной.

  python bot.py           # авто по времени
  python bot.py morning   # утренний пост
  python bot.py digest    # вечерний дайджест
  python bot.py check     # проверка лент
"""

import os
import re
import sys
import json
import time
import html
import io
import textwrap
from pathlib import Path
from datetime import datetime, timezone, timedelta

import feedparser
import requests
import anthropic
import trafilatura
from PIL import Image, ImageDraw, ImageFont


# ═══════════════════════════════════════════════════════════════
#  НАСТРОЙКИ КАНАЛА
# ═══════════════════════════════════════════════════════════════
# Поменяй на название своего канала — оно будет на плашке каждой картинки.
CHANNEL_NAME = "Цифровая звонница"

# Цвета брендинга канала (используются в плашке и карточках)
BRAND_COLOR    = (30, 30, 30)       # тёмный фон плашки
ACCENT_COLOR   = (255, 107, 74)     # акцент (коралловый)
TEXT_COLOR      = (255, 255, 255)   # белый текст


# ═══════════════════════════════════════════════════════════════
#  ИСТОЧНИКИ
# ═══════════════════════════════════════════════════════════════
SOURCES = {
    "Типографика": [
        ("Grilli Type",      "https://rss.app/feeds/dlMmaN5pjj0PJ6Hg.xml"),
        ("Typewolf",          "https://www.typewolf.com/feed"),
        ("I Love Typography", "https://ilovetypography.com/feed/"),
        ("Type Today",        "https://rss.app/feeds/Jtk6gP91atxclgga.xml"),
        ("ParaType",          "https://info.paratype.ru/feed/"),
        ("Alphabettes",       "https://www.alphabettes.org/feed/"),
        ("Главред",           "https://rss.app/feeds/TN0o741DqJZvmjgY.xml"),
        ("Type01",            "https://rss.app/feeds/TxfGu8kTK6s4Ljqw.xml"),
        ("CoType Foundry",    "https://rss.app/feeds/9y2qZLoYGwnkTYK4.xml"),
    ],
    "Брендинг": [
        ("Brand New",              "https://www.underconsideration.com/brandnew/atom.xml"),
        ("Pentagram",              "https://rss.app/feeds/U0jCQWBCdgNwZ7VZ.xml"),
        ("Design Collector",       "https://rss.app/feeds/Z4SRZ8x2SZ3mE9Ko.xml"),
        ("The Brand Identity",     "https://rss.app/feeds/NPVFLPBrhBG1jXfJ.xml"),
        ("FIELD.IO",               "https://rss.app/feeds/DJHMIPnkYMtKm4bA.xml"),
        ("morrre.dsgn",            "https://rss.app/feeds/3KJRbjCWALNchKKQ.xml"), 
        ("HOLOGRAPHIK®",           "https://rss.app/feeds/cTFcNTeSA0SYJfTt.xml"),
    ],
    "Интерфейсы": [
        ("Smashing Magazine", "https://www.smashingmagazine.com/feed/"),
        ("Codrops",           "https://tympanus.net/codrops/feed/"),
        ("Awwwards",          "https://rss.app/feeds/jOgzZtcN0KJqYc2m.xml"),
    ],
    "3D и моушен": [
        ("Vimeo Inspiration",  "https://rsshub.app/telegram/channel/Vimeoinspiration"),
        ("Motionographer",     "https://motionographer.com/feed/"),
        ("Vimeo Inspiration",  "https://rsshub.app/telegram/channel/Vimeoinspiration"),
        ("Motionographer",     "https://motionographer.com/feed/"),
    ],
    "Индустриальный дизайн": [
        ("Dezeen",           "https://www.dezeen.com/feed/"),
        ("Designboom",       "https://www.designboom.com/feed/"),
        ("Minimal lemonade", "https://rss.app/feeds/JcrKTHdrIen89Uxa.xml"),
        ("DESIGNCOLLECTOR",  "https://rss.app/feeds/Z4SRZ8x2SZ3mE9Ko.xml"),
        ("Yanko Design",     "https://www.yankodesign.com/feed/"),
        ("Core77",           "https://www.core77.com/feed"),
    ],
    "Студии и блоги": [
        ("It's Nice That",   "https://rss.app/feeds/7tmrb0zyqjv7WmGQ.xml"),
        ("Creative Review",  "https://www.creativereview.co.uk/feed/"),
        ("Eye on Design",    "https://eyeondesign.aiga.org/feed/"),
        ("Sidebar.io",       "https://sidebar.io/feed.xml"),
        ("Илья Бирман",      "https://ilyabirman.ru/meanwhile/rss/"),
        ("Макс Кудашов",     "https://rss.app/feeds/RjqtSq710RR98Wns.xml"),
    ],
    "Искусство": [
        ("Hyperallergic",     "https://hyperallergic.com/feed/"),
        ("Colossal",          "https://www.thisiscolossal.com/feed/"),
        ("Juxtapoz",          "https://www.juxtapoz.com/news?format=feed"),
        ("Артгид",            "https://rss.app/feeds/hy3ahClzRt5NKxZ9.xml"),
    ],
    "Фото": [
        ("The Blueprint",     "https://rss.app/feeds/uAnx817uSfagXw9u.xml"),
        ("Colta",             "https://www.colta.ru/feed"),
    ],
    "ИИ в дизайне": [
        ("AI Newz",       "https://rss.app/feeds/wyKW6fcSVQ5YMMF2.xml"),
        ("Хабр",          "https://habr.com/en/feed/"),
        ("The Verge AI",  "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
    ],
    "Москва события": [
        ("Кабачковая икра по акции",  "https://rss.app/feeds/B7mYNVND7Qhw5aOw.xml"),
    ],
    "Туториалы"
    ],
}

DAILY_CATEGORIES = {
    0: ["Типографика", "Брендинг", "Интерфейсы", "3D и моушен"],
    1: ["Индустриальный дизайн"],
    2: ["Студии и блоги", "Искусство", "Фото"],
    3: ["ИИ в дизайне"],
    4: ["Москва события"],
    5: ["Туториалы"],
}

CATEGORY_EMOJI = {
    "Типографика":          "🔤",
    "Брендинг":             "🎨",
    "Интерфейсы":           "💻",
    "3D и моушен":          "🧊",
    "Индустриальный дизайн":"🏭",
    "Студии и блоги":       "✍️",
    "Искусство":            "🖼",
    "Фото":                 "📸",
    "ИИ в дизайне":         "🤖",
    "Москва события":       "📍",
    "Туториалы":            "🛠",
}

DAY_LABEL = {
    0: "Типографика · Брендинг · UI · 3D",
    1: "Индустриальный дизайн",
    2: "Студии · Искусство · Фото",
    3: "ИИ в дизайне",
    4: "Дизайн-события в Москве",
    5: "Разбор проекта",
}

DAY_HASHTAGS = {
    0: "#типографика #брендинг #ui #3d",
    1: "#индустриальныйдизайн #продуктовыйдизайн",
    2: "#искусство #фотография #дизайнстудии",
    3: "#ии #нейросети #дизайн",
    4: "#москва #выставки #дизайнсобытия",
    5: "#разбор #дизайнприём #инструменты",
}

# ═══════════════════════════════════════════════════════════════
#  ПАРАМЕТРЫ
# ═══════════════════════════════════════════════════════════════
STATE_FILE      = "sent_items.json"
MAX_AGE_HOURS   = 48
HISTORY_LIMIT   = 3000
USER_AGENT      = "Mozilla/5.0 (compatible; DesignNewsBot/1.0)"
CLAUDE_MODEL    = "claude-haiku-4-5"
IMAGE_WIDTH     = 1280
IMAGE_HEIGHT    = 720
DIGEST_COUNT    = 4


# ═══════════════════════════════════════════════════════════════
#  УТИЛИТЫ
# ═══════════════════════════════════════════════════════════════
def clean(text):
    """Чистит строку от мусора: лишние пробелы, переносы, спецсимволы по краям."""
    if not text:
        return ""
    text = re.sub(r"[\n\r\t]+", " ", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip(" ·•|—–-/\\")


# ═══════════════════════════════════════════════════════════════
#  STATE
# ═══════════════════════════════════════════════════════════════
def load_state():
    p = Path(STATE_FILE)
    if p.exists():
        try:
            return json.loads(p.read_text("utf-8"))
        except Exception:
            pass
    return {"sent": [], "initialized": False}


def save_state(state):
    state["sent"] = state["sent"][-HISTORY_LIMIT:]
    Path(STATE_FILE).write_text(json.dumps(state, ensure_ascii=False, indent=2), "utf-8")


# ═══════════════════════════════════════════════════════════════
#  ШРИФТ (DejaVu Sans — есть на Ubuntu в GitHub Actions)
# ═══════════════════════════════════════════════════════════════
def get_font(size, bold=False):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


# ═══════════════════════════════════════════════════════════════
#  КАРТИНКА 16:9 С БРЕНДИРОВАННОЙ ПЛАШКОЙ
# ═══════════════════════════════════════════════════════════════
def extract_image_url(entry):
    for attr in ("media_thumbnail", "media_content"):
        val = entry.get(attr)
        if val and val[0].get("url"):
            return val[0]["url"]
    for link in entry.get("links", []):
        if link.get("type", "").startswith("image"):
            return link.get("href")
    for field in ("content", "summary"):
        val = entry.get(field)
        if isinstance(val, list) and val:
            val = val[0].get("value", "")
        if isinstance(val, str):
            m = re.search(r'<img[^>]+src="([^"]+)"', val)
            if m:
                return m.group(1)
    return None


def fetch_og_image(url):
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": USER_AGENT})
        if r.ok:
            m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', r.text)
            if m:
                return m.group(1)
    except Exception:
        pass
    return None


def make_cover_image(image_url, category="", source=""):
    """Скачивает картинку → 16:9 → градиент внизу → плашка с рубрикой и каналом."""
    try:
        r = requests.get(image_url, timeout=20, headers={"User-Agent": USER_AGENT})
        if not r.ok:
            return None
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        w, h = img.size

        # Кроп в 16:9
        target_ratio = 16 / 9
        current_ratio = w / h
        if current_ratio > target_ratio:
            new_w = int(h * target_ratio)
            left = (w - new_w) // 2
            img = img.crop((left, 0, left + new_w, h))
        else:
            new_h = int(w / target_ratio)
            top = (h - new_h) // 2
            img = img.crop((0, top, w, top + new_h))
        img = img.resize((IMAGE_WIDTH, IMAGE_HEIGHT), Image.LANCZOS)

        draw = ImageDraw.Draw(img)

        # Градиент: нижние 30% картинки затемняются
        gradient_h = int(IMAGE_HEIGHT * 0.30)
        for y in range(gradient_h):
            alpha = int(180 * (y / gradient_h))
            y_pos = IMAGE_HEIGHT - gradient_h + y
            draw.line([(0, y_pos), (IMAGE_WIDTH, y_pos)], fill=(0, 0, 0, 255), width=1)
            # Pillow RGB не поддерживает альфу через draw.line напрямую,
            # поэтому используем overlay
        # Пересоздаём с альфа-каналом для нормального градиента
        overlay = Image.new("RGBA", (IMAGE_WIDTH, IMAGE_HEIGHT), (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)
        for y in range(gradient_h):
            alpha = int(200 * (y / gradient_h))
            y_pos = IMAGE_HEIGHT - gradient_h + y
            odraw.line([(0, y_pos), (IMAGE_WIDTH, y_pos)], fill=(0, 0, 0, alpha))

        img = img.convert("RGBA")
        img = Image.alpha_composite(img, overlay)

        draw = ImageDraw.Draw(img)

        # Текст на плашке
        font_cat  = get_font(28, bold=True)
        font_ch   = get_font(20)

        emoji = CATEGORY_EMOJI.get(category, "")
        label = f"{emoji} {clean(category)}".strip()
        if source:
            label += f"  ·  {clean(source)}"

        padding = 36
        text_y = IMAGE_HEIGHT - 56

        # Рубрика (слева)
        draw.text((padding, text_y), label, font=font_cat, fill=TEXT_COLOR)

        # Название канала (справа)
        bbox = draw.textbbox((0, 0), CHANNEL_NAME, font=font_ch)
        ch_w = bbox[2] - bbox[0]
        draw.text((IMAGE_WIDTH - padding - ch_w, text_y + 6), CHANNEL_NAME,
                  font=font_ch, fill=ACCENT_COLOR)

        # Акцентная линия сверху плашки
        line_y = IMAGE_HEIGHT - gradient_h + 10
        draw.line([(padding, line_y), (padding + 60, line_y)],
                  fill=ACCENT_COLOR, width=3)

        img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=92)
        buf.seek(0)
        return buf.getvalue()
    except Exception as e:
        print(f"    обложка: {e}")
        return None


# ═══════════════════════════════════════════════════════════════
#  ПЯТНИЧНАЯ КАРТОЧКА СОБЫТИЙ (генерируется в Pillow)
# ═══════════════════════════════════════════════════════════════
def make_friday_card(events_parsed, date_str):
    """Генерирует картинку-карточку со списком событий."""
    try:
        img = Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT), BRAND_COLOR)
        draw = ImageDraw.Draw(img)

        font_title = get_font(42, bold=True)
        font_event = get_font(24, bold=True)
        font_desc  = get_font(20)
        font_date  = get_font(18)

        padding = 50
        y = 50

        # Акцентная линия
        draw.line([(padding, y), (padding + 80, y)], fill=ACCENT_COLOR, width=4)
        y += 20

        # Заголовок
        title = events_parsed.get("title", "Дизайн-события недели")
        draw.text((padding, y), title, font=font_title, fill=TEXT_COLOR)
        y += 60

        # Дата
        draw.text((padding, y), date_str, font=font_date, fill=ACCENT_COLOR)
        y += 40

        # События
        items = events_parsed.get("events", [])[:5]
        for ev in items:
            if y > IMAGE_HEIGHT - 80:
                break
            name = ev.get("name", "")
            desc = ev.get("oneliner", "")

            draw.text((padding, y), f"→  {name}", font=font_event, fill=TEXT_COLOR)
            y += 32

            # Переносим длинные описания
            wrapped = textwrap.wrap(desc, width=65)
            for line in wrapped[:2]:
                draw.text((padding + 24, y), line, font=font_desc, fill=(180, 180, 180))
                y += 26
            y += 16

        # Название канала внизу справа
        bbox = draw.textbbox((0, 0), CHANNEL_NAME, font=font_date)
        ch_w = bbox[2] - bbox[0]
        draw.text((IMAGE_WIDTH - padding - ch_w, IMAGE_HEIGHT - 45),
                  CHANNEL_NAME, font=font_date, fill=ACCENT_COLOR)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=92)
        buf.seek(0)
        return buf.getvalue()
    except Exception as e:
        print(f"    карточка: {e}")
        return None


# ═══════════════════════════════════════════════════════════════
#  ПОЛНЫЙ ТЕКСТ
# ═══════════════════════════════════════════════════════════════
def fetch_full_text(url, fallback=""):
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(downloaded, include_comments=False,
                                       include_tables=False, favor_precision=True)
            if text and len(text) > 200:
                return text[:4000]
    except Exception:
        pass
    return fallback


# ═══════════════════════════════════════════════════════════════
#  RSS: сбор кандидатов
# ═══════════════════════════════════════════════════════════════
def collect_candidates(categories, state):
    sent_ids = set(state["sent"])
    now = time.time()
    max_age = MAX_AGE_HOURS * 3600
    candidates = []
    for category in categories:
        for source_name, feed_url in SOURCES.get(category, []):
            try:
                feed = feedparser.parse(feed_url, request_headers={"User-Agent": USER_AGENT})
                for entry in (feed.entries or [])[:8]:
                    item_id = entry.get("id") or entry.get("link")
                    if not item_id or item_id in sent_ids:
                        continue
                    pub = entry.get("published_parsed") or entry.get("updated_parsed")
                    pub_ts = time.mktime(pub) if pub else now
                    if now - pub_ts > max_age:
                        sent_ids.add(item_id)
                        state["sent"].append(item_id)
                        continue
                    summary = entry.get("summary", "") or ""
                    if isinstance(summary, list):
                        summary = summary[0].get("value", "") if summary else ""
                    candidates.append({
                        "id":       item_id,
                        "category": category,
                        "source":   clean(source_name),
                        "title":    clean(entry.get("title", "")),
                        "link":     entry.get("link", ""),
                        "image":    extract_image_url(entry),
                        "summary":  re.sub(r"<[^>]+>", " ", summary)[:2000],
                        "ts":       pub_ts,
                    })
            except Exception as e:
                print(f"  ошибка {source_name}: {e}")
    candidates.sort(key=lambda x: x["ts"], reverse=True)
    return candidates


# ═══════════════════════════════════════════════════════════════
#  KUDAGO API
# ═══════════════════════════════════════════════════════════════
def fetch_kudago_events(limit=8):
    now_ts = int(time.time())
    week_later = now_ts + 7 * 86400
    events = []
    for cats in ["exhibition", "festival", "cinema"]:
        try:
            r = requests.get(
                "https://kudago.com/public-api/v1.4/events/",
                params={
                    "location": "msk", "categories": cats,
                    "fields": "title,short_title,description,dates,site_url,images,place",
                    "page_size": 10, "actual_since": now_ts,
                    "actual_until": week_later, "order_by": "-publication_date",
                    "text_format": "plain",
                },
                timeout=20,
            )
            if r.ok:
                for ev in r.json().get("results", []):
                    title = ev.get("short_title") or ev.get("title", "")
                    desc  = ev.get("description", "")[:500]
                    link  = ev.get("site_url", "")
                    image = ""
                    imgs  = ev.get("images", [])
                    if imgs:
                        image = imgs[0].get("image", "")
                    events.append({
                        "title": title,
                        "desc": re.sub(r"<[^>]+>", " ", desc).strip(),
                        "link": link, "image": image, "cat": cats,
                    })
        except Exception as e:
            print(f"  KudaGo ({cats}): {e}")
    seen = set()
    unique = []
    for ev in events:
        key = ev["title"].lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(ev)
    return unique[:limit]


# ═══════════════════════════════════════════════════════════════
#  CLAUDE ПРОМПТЫ
# ═══════════════════════════════════════════════════════════════

# --- Авторский голос (вшит во все промпты) ---
VOICE_RULES = """
ГОЛОС КАНАЛА:
- Пишешь для практикующих дизайнеров. Они умные, не нужно разжёвывать очевидное.
- Тон: умный, неожиданный, без корпоративного глянца. Ориентир — Loewe, а не Сбер.
- Логика с метафорами: метафора не украшение, а упаковка мысли. Одна точная метафора вместо трёх абзацев объяснений.
- Используй связки «и это аргумент», «поэтому», «да, но». Не «однако», не «тем не менее», не «стоит отметить».
- Заголовок — это тезис. Не описание. Не вопрос. Тезис.
- Без канцелярита, «является», «представляет собой», «в рамках». Без длинных тире. Без лишних кавычек.
- Названия брендов, продуктов, студий, шрифтов на иностранном языке НЕ переводить. Apple, Helvetica, Pentagram — как есть.
- Не выдумывай факты. Имена, цифры, бренды — ТОЛЬКО из источника.
"""

REWRITE_PROMPT = VOICE_RULES + """
Перепиши материал в пост для телеграм-канала о дизайне.

ФОРМАТ:
1. Заголовок-тезис: 40-80 символов, без точки. Не перевод оригинала, а твой вывод.
2. Суть: 2-3 коротких предложения. Что произошло, что сделали, в чём идея.
3. Один приём, который можно украсть: конкретная техника, подход или решение из этого проекта/статьи, которое дизайнер может применить в своей работе сегодня. Не абстрактная «полезность», а конкретный takeaway. Начни со слова «Украсть:».
4. Общая длина title + summary + steal: до 500 символов.

ВЕРНИ JSON БЕЗ ```:
{{"title": "...", "summary": "...", "steal": "..."}}

МАТЕРИАЛ:
Заголовок: {title}
Текст: {content}
Источник: {source}
"""

ANALYSIS_PROMPT = VOICE_RULES + """
Сделай мини-разбор дизайн-проекта для телеграм-канала. Не пересказ, а анализ.

ФОРМАТ:
1. Заголовок-тезис: 40-80 символов. Твоя оценка проекта в одной фразе.
2. Что сделано: 2-3 предложения. Факты: кто, что, для кого.
3. Что работает: 1-2 предложения. Конкретный приём, который делает проект сильным.
4. Что спорно: 1-2 предложения. Что можно было решить иначе. Будь честным, но конструктивным.
5. Украсть: один приём из проекта, который можно забрать в свою работу.
6. Общая длина: до 650 символов.

ВЕРНИ JSON БЕЗ ```:
{{"title": "...", "what": "...", "works": "...", "debatable": "...", "steal": "..."}}

МАТЕРИАЛ:
Заголовок: {title}
Текст: {content}
Источник: {source}
"""

DIGEST_PROMPT = VOICE_RULES + """
Составь вечерний дайджест из нескольких материалов. Не просто перечисли — найди связи между ними. Что общего в сегодняшних новостях, какой тренд или паттерн проглядывает.

ФОРМАТ:
1. Заголовок дайджеста: 30-50 символов. Не «дайджест дня», а тезис, объединяющий материалы.
2. Вводная: 1-2 предложения, что объединяет материалы. Тренд, совпадение, контраст.
3. На каждый материал: название (name), суть в одном предложении (summary), один takeaway для дизайнера (steal).
4. Максимум {count} материалов.

ВЕРНИ JSON БЕЗ ```:
{{"title": "...", "intro": "...", "items": [{{"name": "...", "summary": "...", "steal": "..."}}]}}

МАТЕРИАЛЫ:
{materials}
"""

FRIDAY_PROMPT = VOICE_RULES + """
Составь подборку дизайн-мероприятий, выставок и музейных событий в Москве на ближайшую неделю.

ФОРМАТ:
1. Заголовок: 30-60 символов. Конкретный, не «афиша недели».
2. На каждое событие: название, одно предложение что это, и одно — зачем дизайнеру туда идти (что он оттуда унесёт).
3. Максимум 5 событий. Приоритет: выставки и события, связанные с визуальной культурой.

ВЕРНИ JSON БЕЗ ```:
{{"title": "...", "events": [{{"name": "...", "oneliner": "...", "why": "..."}}]}}

СОБЫТИЯ:
{events_text}
"""


def extract_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        text = m.group(0)
    return json.loads(text)


def call_claude(client, prompt):
    resp = client.messages.create(
        model=CLAUDE_MODEL, max_tokens=1200, temperature=0.4,
        messages=[{"role": "user", "content": prompt}],
    )
    return extract_json(resp.content[0].text)


# ═══════════════════════════════════════════════════════════════
#  ФОРМАТИРОВАНИЕ
# ═══════════════════════════════════════════════════════════════
def format_regular_post(weekday, source, parsed, link):
    label = DAY_LABEL.get(weekday, "")
    tags  = DAY_HASHTAGS.get(weekday, "")
    steal = parsed.get("steal", parsed.get("value", ""))
    return (
        f"<b>{html.escape(clean(parsed['title']))}</b>\n\n"
        f"{html.escape(clean(parsed['summary']))}\n\n"
        f"🔑 {html.escape(clean(steal))}\n\n"
        f"<i>{html.escape(clean(source))} · {html.escape(label)}</i>\n\n"
        f"{html.escape(tags)}\n\n"
        f'🔗 <a href="{link}">Источник</a>'
    )


def format_analysis_post(source, parsed, link):
    tags = DAY_HASHTAGS.get(5, "")
    return (
        f"<b>{html.escape(clean(parsed['title']))}</b>\n\n"
        f"{html.escape(clean(parsed['what']))}\n\n"
        f"✅ <b>Работает:</b> {html.escape(clean(parsed['works']))}\n\n"
        f"🤔 <b>Спорно:</b> {html.escape(clean(parsed['debatable']))}\n\n"
        f"🔑 <b>Украсть:</b> {html.escape(clean(parsed['steal']))}\n\n"
        f"<i>{html.escape(clean(source))} · Разбор проекта</i>\n\n"
        f"{html.escape(tags)}\n\n"
        f'🔗 <a href="{link}">Источник</a>'
    )


def format_digest_post(weekday, parsed, items_data):
    label = DAY_LABEL.get(weekday, "")
    tags  = DAY_HASHTAGS.get(weekday, "")

    parts = [f"<b>📋 {html.escape(clean(parsed['title']))}</b>\n"]

    intro = parsed.get("intro", "")
    if intro:
        parts.append(f"\n{html.escape(clean(intro))}\n")

    for i, item in enumerate(parsed.get("items", [])):
        link = items_data[i]["link"] if i < len(items_data) else ""
        steal = item.get("steal", "")
        parts.append(
            f"\n▪️ <b>{html.escape(clean(item['name']))}</b>\n"
            f"{html.escape(clean(item['summary']))}\n"
            f"🔑 {html.escape(clean(steal))}"
            + (f'\n🔗 <a href="{link}">Источник</a>' if link else "")
        )
    parts.append(f"\n\n<i>{html.escape(label)}</i>\n{html.escape(tags)}")
    return "\n".join(parts)


def format_friday_post(parsed, events):
    parts = [f"<b>📍 {html.escape(clean(parsed['title']))}</b>\n"]
    for i, ev in enumerate(parsed.get("events", [])):
        link = events[i]["link"] if i < len(events) else ""
        parts.append(
            f"\n▪️ <b>{html.escape(clean(ev['name']))}</b>\n"
            f"{html.escape(clean(ev['oneliner']))}\n"
            f"→ {html.escape(clean(ev.get('why', '')))}"
            + (f'\n🔗 <a href="{link}">Подробнее</a>' if link else "")
        )
    tags = DAY_HASHTAGS.get(4, "")
    parts.append(f"\n\n{html.escape(tags)}")
    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════
#  TELEGRAM
# ═══════════════════════════════════════════════════════════════
def tg_send_photo_bytes(token, chat_id, photo_bytes, caption):
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendPhoto",
            data={"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"},
            files={"photo": ("cover.jpg", photo_bytes, "image/jpeg")},
            timeout=30,
        )
        if r.ok:
            return True
    except Exception as e:
        print(f"    sendPhoto: {e}")
    return False


def tg_send_text(token, chat_id, text):
    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data={"chat_id": chat_id, "text": text, "parse_mode": "HTML",
              "disable_web_page_preview": False},
        timeout=30,
    )
    return r.ok


def post_to_telegram(token, chat_id, text, cover_bytes=None):
    if cover_bytes:
        caption = text if len(text) <= 1024 else text[:1020] + "..."
        if tg_send_photo_bytes(token, chat_id, cover_bytes, caption):
            return True
    return tg_send_text(token, chat_id, text)


# ═══════════════════════════════════════════════════════════════
#  ПРОВЕРКА ЛЕНТ
# ═══════════════════════════════════════════════════════════════
def check_feeds():
    print("Проверяю RSS-ленты...\n")
    ok = bad = 0
    bad_list = []
    seen_urls = set()
    for cat, sources in SOURCES.items():
        print(f"\n[{cat}]")
        for name, url in sources:
            if url in seen_urls:
                continue
            seen_urls.add(url)
            try:
                feed = feedparser.parse(url, request_headers={"User-Agent": USER_AGENT})
                count = len(feed.entries)
                if count > 0:
                    print(f"  ✓ {name:<24} {count}")
                    ok += 1
                else:
                    print(f"  ✗ {name:<24} пусто")
                    bad_list.append(f"  {cat} · {name}  →  {url}")
                    bad += 1
            except Exception as e:
                print(f"  ✗ {name:<24} {e}")
                bad_list.append(f"  {cat} · {name}  →  {url}")
                bad += 1
    print(f"\n[KudaGo API]")
    try:
        evts = fetch_kudago_events(3)
        print(f"  ✓ KudaGo            {len(evts)} событий")
        ok += 1
    except Exception as e:
        print(f"  ✗ KudaGo            {e}")
        bad += 1
    print(f"\nИтого: {ok} живых, {bad} мёртвых")
    if bad_list:
        print("\nМёртвые:")
        for b in bad_list:
            print(b)


# ═══════════════════════════════════════════════════════════════
#  УТРЕННИЙ ПОСТ
# ═══════════════════════════════════════════════════════════════
def run_morning(token, chat_id, client, weekday, state):
    if weekday == 4:
        return run_friday(token, chat_id, client, state)

    is_saturday = (weekday == 5)
    categories = DAILY_CATEGORIES[weekday]
    candidates = collect_candidates(categories, state)
    print(f"Кандидатов: {len(candidates)}")

    if not candidates:
        print("Нет свежих материалов.")
        return False

    for item in candidates:
        print(f"\n→ {item['source']}: {item['title'][:60]}")
        content = item["summary"]
        if len(content) < 400 and item["link"]:
            print("    подтягиваю текст...")
            content = fetch_full_text(item["link"], fallback=content) or content

        image_url = item["image"]
        if not image_url and item["link"]:
            image_url = fetch_og_image(item["link"])

        # Суббота — разбор, остальные дни — обычный пост
        try:
            if is_saturday:
                parsed = call_claude(client, ANALYSIS_PROMPT.format(
                    title=item["title"], content=content[:4000], source=item["source"]))
                text = format_analysis_post(item["source"], parsed, item["link"])
            else:
                parsed = call_claude(client, REWRITE_PROMPT.format(
                    title=item["title"], content=content[:4000], source=item["source"]))
                text = format_regular_post(weekday, item["source"], parsed, item["link"])
        except Exception as e:
            print(f"    Claude: {e}")
            continue

        cover = make_cover_image(image_url, item["category"], item["source"]) if image_url else None

        if post_to_telegram(token, chat_id, text, cover):
            state["sent"].append(item["id"])
            print("    ✓ опубликовано")
            return True
        print("    ✗ ошибка отправки")
    return False


# ═══════════════════════════════════════════════════════════════
#  ПЯТНИЦА: МЕРОПРИЯТИЯ
# ═══════════════════════════════════════════════════════════════
def run_friday(token, chat_id, client, state):
    print("Пятница — мероприятия, музеи, выставки")
    events = fetch_kudago_events(8)
    print(f"  KudaGo: {len(events)} событий")

    for source_name, feed_url in SOURCES.get("Москва события", []):
        try:
            feed = feedparser.parse(feed_url, request_headers={"User-Agent": USER_AGENT})
            for entry in (feed.entries or [])[:5]:
                title = entry.get("title", "")
                link  = entry.get("link", "")
                summary = entry.get("summary", "")
                if isinstance(summary, list):
                    summary = summary[0].get("value", "") if summary else ""
                events.append({
                    "title": title,
                    "desc": re.sub(r"<[^>]+>", " ", summary)[:300],
                    "link": link, "image": extract_image_url(entry) or "", "cat": "telegram",
                })
        except Exception as e:
            print(f"  {source_name}: {e}")

    if not events:
        print("  нет событий")
        return False

    events_text = ""
    for i, ev in enumerate(events[:8], 1):
        events_text += f"{i}. {ev['title']}\n   {ev['desc'][:200]}\n   Ссылка: {ev['link']}\n\n"

    try:
        parsed = call_claude(client, FRIDAY_PROMPT.format(events_text=events_text))
    except Exception as e:
        print(f"  Claude: {e}")
        return False

    text = format_friday_post(parsed, events)

    # Генерируем карточку с событиями
    msk = datetime.now(timezone(timedelta(hours=3)))
    date_str = msk.strftime("%d.%m — ") + (msk + timedelta(days=7)).strftime("%d.%m.%Y")
    card = make_friday_card(parsed, date_str)

    if post_to_telegram(token, chat_id, text, card):
        for ev in events:
            if ev.get("link"):
                state["sent"].append(ev["link"])
        print("  ✓ подборка опубликована")
        return True
    return False


# ═══════════════════════════════════════════════════════════════
#  ВЕЧЕРНИЙ ДАЙДЖЕСТ
# ═══════════════════════════════════════════════════════════════
def run_digest(token, chat_id, client, weekday, state):
    if weekday == 4:
        return run_friday(token, chat_id, client, state)

    categories = DAILY_CATEGORIES[weekday]
    candidates = collect_candidates(categories, state)
    print(f"Кандидатов для дайджеста: {len(candidates)}")

    if not candidates:
        print("Нет материалов для дайджеста.")
        return False

    selected = candidates[:DIGEST_COUNT]
    materials_text = ""
    for i, item in enumerate(selected, 1):
        content = item["summary"]
        if len(content) < 400 and item["link"]:
            content = fetch_full_text(item["link"], fallback=content) or content
        materials_text += f"{i}. [{item['source']}] {item['title']}\n   {content[:600]}\n\n"
        if not item["image"] and item["link"]:
            item["image"] = fetch_og_image(item["link"])

    try:
        parsed = call_claude(client, DIGEST_PROMPT.format(
            count=DIGEST_COUNT, materials=materials_text))
    except Exception as e:
        print(f"  Claude: {e}")
        return False

    text = format_digest_post(weekday, parsed, selected)

    # Обложка от первого материала с картинкой
    cover = None
    for it in selected:
        if it.get("image"):
            cover = make_cover_image(it["image"], it["category"], it["source"])
            if cover:
                break

    if post_to_telegram(token, chat_id, text, cover):
        for item in selected:
            state["sent"].append(item["id"])
        print("  ✓ дайджест опубликован")
        return True
    return False


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════
def detect_mode(msk_hour):
    return "morning" if msk_hour < 14 else "digest"


def main():
    token         = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id       = os.environ["TELEGRAM_CHAT_ID"]
    anthropic_key = os.environ["ANTHROPIC_API_KEY"]
    client        = anthropic.Anthropic(api_key=anthropic_key)

    msk     = datetime.now(timezone(timedelta(hours=3)))
    weekday = msk.weekday()
    print(f"Сегодня: {msk.strftime('%A %d.%m.%Y %H:%M')} МСК, день {weekday}")

    if weekday == 6:
        print("Воскресенье — выходной.")
        return

    if weekday not in DAILY_CATEGORIES:
        print(f"Нет рубрик для дня {weekday}.")
        return

    args = sys.argv[1:]
    if "morning" in args:
        mode = "morning"
    elif "digest" in args:
        mode = "digest"
    else:
        mode = detect_mode(msk.hour)

    state = load_state()

    if not state.get("initialized"):
        print("Первый запуск — инициализация...")
        sent_ids = set(state["sent"])
        for cat_list in DAILY_CATEGORIES.values():
            for cat in cat_list:
                for _, feed_url in SOURCES.get(cat, []):
                    try:
                        feed = feedparser.parse(feed_url, request_headers={"User-Agent": USER_AGENT})
                        for entry in (feed.entries or [])[:10]:
                            item_id = entry.get("id") or entry.get("link")
                            if item_id and item_id not in sent_ids:
                                state["sent"].append(item_id)
                                sent_ids.add(item_id)
                    except Exception:
                        pass
        state["initialized"] = True
        save_state(state)
        print(f"Записано {len(state['sent'])} ID.")
        return

    label = DAY_LABEL.get(weekday, "")
    print(f"Режим: {mode}")
    print(f"Рубрика: {label}\n")

    if mode == "morning":
        run_morning(token, chat_id, client, weekday, state)
    else:
        run_digest(token, chat_id, client, weekday, state)

    save_state(state)
    print("\nГотово.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        check_feeds()
    else:
        main()
