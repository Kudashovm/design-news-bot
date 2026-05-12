"""
Telegram-бот для дизайн-канала.

10:00 МСК — один пост из рубрики дня.
18:00 МСК — дайджест: подборка лучшего за день.
Пятница — мероприятия, музеи, выставки.
Суббота утро — мини-разбор одного проекта.
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
import urllib.request
from pathlib import Path
from datetime import datetime, timezone, timedelta

import feedparser
import requests
import anthropic
import trafilatura
from PIL import Image, ImageDraw, ImageFont, ImageFilter


# ═══════════════════════════════════════════════════════════════
#  НАСТРОЙКИ КАНАЛА
# ═══════════════════════════════════════════════════════════════
CHANNEL_NAME = "Цифровая звонница"
CHANNEL_HANDLE = "@digitalzvon"

# ═══════════════════════════════════════════════════════════════
#  ИСТОЧНИКИ
# ═══════════════════════════════════════════════════════════════
SOURCES = {
    "Типографика": [
        ("Type Today",         "https://rss.app/feeds/Jtk6gP91atxclgga.xml"),
        ("Grilli Type",        "https://rss.app/feeds/dlMmaN5pjj0PJ6Hg.xml"),
        ("TYPE01",             "https://rss.app/feeds/TxfGu8kTK6s4Ljqw.xml"),
        ("CoType Foundry",     "https://rss.app/feeds/9y2qZLoYGwnkTYK4.xml"),
        ("Главред",            "https://rss.app/feeds/TN0o741DqJZvmjgY.xml"),
    ],
    "Брендинг и граф дизайн": [
        ("Pentagram",              "https://rss.app/feeds/U0jCQWBCdgNwZ7VZ.xml"),
        ("The Brand Identity",     "https://rss.app/feeds/NPVFLPBrhBG1jXfJ.xml"),
        ("Eye on Design",          "https://rss.app/feeds/7tmrb0zyqjv7WmGQ.xml"),
        ("DESIGNCOLLECTOR",        "https://rss.app/feeds/Z4SRZ8x2SZ3mE9Ko.xml"),
        ("Motto",                  "https://rss.app/feeds/1hVv8Q2h4hX8Ps88.xml"),
        ("Nick Vinny",             "https://rss.app/feeds/WUAymKuRFmkEyEEv.xml"),
        ("Morrre.dsgn",            "https://rss.app/feeds/3KJRbjCWALNchKKQ.xml"),
        ("Minimal Lemonade",       "https://rss.app/feeds/JcrKTHdrIen89Uxa.xml"),
        ("Zünc Studio",            "https://rss.app/feeds/beB30MqiSadXRbWn.xml"),
        ("Состав",                 "https://rss.app/feeds/39PxHUbWGZeF4raF.xml"),
        ("Figma",                  "https://rss.app/feeds/qZ4WFeenR3uo0All.xml"),
    ],
    "Интерфейсы и пром дизайн": [
        ("Awwwards",            "https://rss.app/feeds/jOgzZtcN0KJqYc2m.xml"),
        ("Figma",               "https://rss.app/feeds/qZ4WFeenR3uo0All.xml"),
        ("Microsoft Design",    "https://rss.app/feeds/tdhEU2RBJNDa4e3K.xml"),
        ("Yandex Design",       "https://rss.app/feeds/3wZPUUx2ACQbsthN.xml"),
    ],
    "3D и моушен": [
        ("FIELD.IO",            "https://rss.app/feeds/DJHMIPnkYMtKm4bA.xml"),
        ("HOLOGRAPHIK",         "https://rss.app/feeds/cTFcNTeSA0SYJfTt.xml"),
    ],
    "Студии и блоги": [
        ("It's Nice That",       "https://rss.app/feeds/pcows50evH5Tfy47.xml"),
        ("HERE CREATIVE",        "https://rss.app/feeds/UgcHtGU4juOnCUjL.xml"),
        ("Kiln",                 "https://rss.app/feeds/8Jf34QpsLnK6LvDQ.xml"),
        ("Enigma",               "https://rss.app/feeds/8zTXqqbnCfIuXkZ8.xml"),
        ("Database",             "https://rss.app/feeds/mBrULWUseRllVD7l.xml"),
        ("DOT4",                 "https://rss.app/feeds/AIJ37uxt0OkEFAZh.xml"),
        ("Nick Medukha",         "https://rss.app/feeds/CJfklfcm1dXrO0Rt.xml"),
        ("Fresh Air Design",     "https://rss.app/feeds/Co8ReXRqg6WfhZFR.xml"),
        ("Davar Azarbeygui",     "https://rss.app/feeds/V25ZpIm30VVuQzfz.xml"),
    ],
    "Искусство": [
        ("The Blueprint",     "https://rss.app/feeds/uAnx817uSfagXw9u.xml"),
        ("Артгид",            "https://rss.app/feeds/hy3ahClzRt5NKxZ9.xml"),
    ],
    "ИИ в дизайне": [
        ("AI Newz",       "https://rss.app/feeds/wyKW6fcSVQ5YMMF2.xml"),
        ("The Verge AI",  "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
    ],
    "Москва события": [
        ("Кабачковая икра",  "https://rss.app/feeds/B7mYNVND7Qhw5aOw.xml"),
    ],
}

# Pinterest-доски по дням. Вечером бот берёт 6 картинок из досок дня.
# Создай rss.app фид для каждой доски и подставь URL вместо "URL_СЮДА".
PINTEREST_BOARDS = {
    0: [  # ПН: типографика, брендинг, 3D
        ("Шрифт",           "https://rss.app/feeds/X3w5rGocYMoKltnV.xml"),           # type/
        ("Графдизайн",      "https://rss.app/feeds/pXv1u6JC4ampeWtC.xml"),
        ("Реклама",         "https://rss.app/feeds/sFI2N2hna4zqr6XL.xml"),           # adv/
        ("Мерч",            "https://rss.app/feeds/8X6A9IYpuK1Zw1iO.xml"),           # merch/
        ("Печать",          "https://rss.app/feeds/ltSGLs9VwQLgNzD2.xml"),           # print-pack/
        ("3D",              "https://rss.app/feeds/yCPWrKPEfoLk8KJ8.xml"),           # 3d-motion/
    ],
    1: [  # ВТ: интерфейсы
        ("UI/UX",           "https://rss.app/feeds/WTIYeLbkTKCzsR5E.xml"),           # ui/
        ("Иконки",          "https://rss.app/feeds/6B7YwzQ6LYi98HfL.xml"),           # icon/
    ],
    2: [  # СР: студии, искусство
        ("Иллюстрации",    "https://rss.app/feeds/oiTkOZF2emEtELSI.xml"),           # illustration/
        ("Фото",           "https://rss.app/feeds/ohf3PbfiqGcO2zWH.xml"),           # photo/
        ("Интерьер",       "https://rss.app/feeds/8crrdblCPkDLBqkl.xml"),           # interior-design/
        ("Пространство",   "https://rss.app/feeds/UfinmwzLRnQHDQRf.xml"),           # space/
        ("Текстуры",       "https://rss.app/feeds/rbGR1QFPhnL51B7Y.xml"),           # textures/
    ],
    3: [  # ЧТ: ИИ день — берём графдизайн + иллюстрации
        ("Графдизайн",     "https://rss.app/feeds/pXv1u6JC4ampeWtC.xml"),
        ("Иллюстрации",    "https://rss.app/feeds/oiTkOZF2emEtELSI.xml"),           # illustration/
    ],
    4: [  # ПТ: после утренних событий — пространство, интерьер
        ("Пространство",   "https://rss.app/feeds/UfinmwzLRnQHDQRf.xml"),           # space/
        ("Интерьер",       "https://rss.app/feeds/8crrdblCPkDLBqkl.xml"),           # interior-design/
        ("Текстуры",       "https://rss.app/feeds/rbGR1QFPhnL51B7Y.xml"),           # textures/
    ],
    5: [  # СБ: микс
        ("Графдизайн",     "https://rss.app/feeds/pXv1u6JC4ampeWtC.xml"),
        ("Реклама",        "https://rss.app/feeds/sFI2N2hna4zqr6XL.xml"),           # adv/
        ("Мерч",           "https://rss.app/feeds/8X6A9IYpuK1Zw1iO.xml"),           # merch/
    ],
}

PINTEREST_ALBUM_SIZE = 6

DAILY_CATEGORIES = {
    0: ["Типографика", "Брендинг и граф дизайн", "3D и моушен"],
    1: ["Интерфейсы и пром дизайн"],
    2: ["Студии и блоги", "Искусство"],
    3: ["ИИ в дизайне"],
    4: ["Москва события"],
    5: ["Брендинг и граф дизайн", "Студии и блоги"],
}

CATEGORY_EMOJI = {
    "Типографика":               "🔤",
    "Брендинг и граф дизайн":    "🎨",
    "Интерфейсы и пром дизайн":  "💻",
    "3D и моушен":               "🧊",
    "Студии и блоги":            "✍️",
    "Искусство":                 "🖼",
    "ИИ в дизайне":              "🤖",
    "Москва события":            "📍",
}

DAY_LABEL = {
    0: "Типографика · Брендинг · 3D",
    1: "Интерфейсы · Пром дизайн",
    2: "Студии · Искусство",
    3: "ИИ в дизайне",
    4: "Дизайн-события в Москве",
    5: "Разбор проекта",
}

DAY_HASHTAGS = {
    0: "#типографика #брендинг #графдизайн #3d",
    1: "#интерфейсы #промдизайн #ux",
    2: "#дизайнстудии #искусство",
    3: "#ии #нейросети #дизайн",
    4: "#москва #выставки #дизайнсобытия",
    5: "#разбор #дизайн #кейс",
}

CATEGORY_COLOR = {
    "Типографика":               (220, 50, 47),
    "Брендинг и граф дизайн":    (211, 54, 130),
    "Интерфейсы и пром дизайн":  (38, 139, 210),
    "3D и моушен":               (108, 113, 196),
    "Студии и блоги":            (181, 137, 0),
    "Искусство":                 (203, 75, 22),
    "ИИ в дизайне":              (88, 110, 117),
    "Москва события":            (220, 50, 47),
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
FONT_PATH       = "/tmp/Inter-SemiBold.ttf"
FONT_PATH_REG   = "/tmp/Inter-Regular.ttf"
FONT_URL        = "https://github.com/rsms/inter/releases/download/v4.1/Inter-4.1.zip"


# ═══════════════════════════════════════════════════════════════
#  УТИЛИТЫ
# ═══════════════════════════════════════════════════════════════
def clean_text(text):
    if not text:
        return ""
    text = re.sub(r"[\n\r\t]+", " ", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def clean_source_name(name):
    name = clean_text(name)
    name = name.strip(" ·•|—–-/\\")
    return name


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
#  ШРИФТ
# ═══════════════════════════════════════════════════════════════
def ensure_font():
    if Path(FONT_PATH).exists():
        return
    try:
        import zipfile
        zip_path = "/tmp/inter.zip"
        urllib.request.urlretrieve(FONT_URL, zip_path)
        with zipfile.ZipFile(zip_path) as zf:
            for name in zf.namelist():
                if name.endswith("Inter-SemiBold.ttf"):
                    with open(FONT_PATH, "wb") as f:
                        f.write(zf.read(name))
                if name.endswith("Inter-Regular.ttf"):
                    with open(FONT_PATH_REG, "wb") as f:
                        f.write(zf.read(name))
        os.remove(zip_path)
        print("  шрифт Inter загружен")
        return
    except Exception as e:
        print(f"  Inter не скачался: {e}")
    deja = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    deja_reg = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    if Path(deja).exists():
        import shutil
        shutil.copy(deja, FONT_PATH)
        if Path(deja_reg).exists():
            shutil.copy(deja_reg, FONT_PATH_REG)
        print("  используем DejaVu Sans")


def get_font(size, bold=True):
    path = FONT_PATH if bold else FONT_PATH_REG
    if not Path(path).exists():
        path = FONT_PATH
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


# ═══════════════════════════════════════════════════════════════
#  КАРТИНКА
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


def crop_16_9(img):
    w, h = img.size
    target = 16 / 9
    current = w / h
    if current > target:
        new_w = int(h * target)
        left = (w - new_w) // 2
        img = img.crop((left, 0, left + new_w, h))
    else:
        new_h = int(w / target)
        top = (h - new_h) // 2
        img = img.crop((0, top, w, top + new_h))
    return img.resize((IMAGE_WIDTH, IMAGE_HEIGHT), Image.LANCZOS)


def add_visual_frame(img, category, source=""):
    draw = ImageDraw.Draw(img, "RGBA")
    w, h = img.size
    color = CATEGORY_COLOR.get(category, (88, 110, 117))

    draw.rectangle([0, 0, w, 20], fill=color)

    grad_h = 120
    for i in range(grad_h):
        alpha = int(200 * (i / grad_h))
        y = h - grad_h + i
        draw.rectangle([0, y, w, y + 1], fill=(0, 0, 0, alpha))

    font_label = get_font(28, bold=True)
    font_small = get_font(20, bold=False)

    dot_y = h - 50
    draw.ellipse([24, dot_y, 40, dot_y + 16], fill=color)
    draw.text((50, h - 60), category, font=font_label, fill=(255, 255, 255, 240))
    draw.text((w - 24, h - 55), CHANNEL_NAME, font=font_small,
              fill=(255, 255, 255, 160), anchor="ra")
    if source:
        src = clean_source_name(source)
        draw.text((24, h - 90), src, font=font_small, fill=(255, 255, 255, 140))
    return img


def make_cover_image(image_url, category="", source=""):
    try:
        r = requests.get(image_url, timeout=20, headers={"User-Agent": USER_AGENT})
        if not r.ok:
            return None
        img = Image.open(io.BytesIO(r.content)).convert("RGBA")
        img = crop_16_9(img)
        if category:
            img = add_visual_frame(img, category, source)
        img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=92)
        buf.seek(0)
        return buf.getvalue()
    except Exception as e:
        print(f"    картинка: {e}")
        return None


def generate_friday_card(title, events):
    try:
        card_w, card_h = 1280, 720
        bg_color = (25, 25, 30)
        accent = CATEGORY_COLOR.get("Москва события", (220, 50, 47))

        img = Image.new("RGB", (card_w, card_h), bg_color)
        draw = ImageDraw.Draw(img)

        draw.rectangle([0, 0, card_w, 6], fill=accent)

        font_title = get_font(42, bold=True)
        font_event = get_font(26, bold=True)
        font_desc  = get_font(20, bold=False)
        font_small = get_font(18, bold=False)

        draw.ellipse([48, 55, 68, 75], fill=accent)
        draw.text((78, 40), title, font=font_title, fill=(255, 255, 255))

        y = 120
        for i, ev in enumerate(events[:5]):
            if y > card_h - 80:
                break
            name = ev.get("name", ev.get("title", ""))[:60]
            oneliner = ev.get("oneliner", ev.get("desc", ""))[:90]

            draw.text((48, y), f"{i+1}.", font=font_event, fill=accent)
            draw.text((80, y), name, font=font_event, fill=(255, 255, 255))
            y += 36
            if oneliner:
                draw.text((80, y), oneliner, font=font_desc, fill=(180, 180, 185))
                y += 30
            y += 20

        draw.text((48, card_h - 50), CHANNEL_NAME, font=font_small, fill=(120, 120, 125))
        draw.text((card_w - 48, card_h - 50), "Москва · эта неделя",
                  font=font_small, fill=(120, 120, 125), anchor="ra")

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=92)
        buf.seek(0)
        return buf.getvalue()
    except Exception as e:
        print(f"    генерация карточки: {e}")
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
#  RSS
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
                        "id": item_id, "category": category,
                        "source": clean_source_name(source_name),
                        "title": clean_text(entry.get("title", "")),
                        "link": entry.get("link", ""),
                        "image": extract_image_url(entry),
                        "summary": clean_text(re.sub(r"<[^>]+>", " ", summary))[:2000],
                        "ts": pub_ts,
                    })
            except Exception as e:
                print(f"  ошибка {source_name}: {e}")
    candidates.sort(key=lambda x: x["ts"], reverse=True)
    return candidates


# ═══════════════════════════════════════════════════════════════
#  KUDAGO
# ═══════════════════════════════════════════════════════════════
def fetch_kudago_events(limit=8):
    now_ts = int(time.time())
    week_later = now_ts + 7 * 86400
    events = []
    for cats in ["exhibition", "festival", "cinema"]:
        try:
            r = requests.get("https://kudago.com/public-api/v1.4/events/", params={
                "location": "msk", "categories": cats,
                "fields": "title,short_title,description,dates,site_url,images,place",
                "page_size": 10, "actual_since": now_ts, "actual_until": week_later,
                "order_by": "-publication_date", "text_format": "plain",
            }, timeout=20)
            if r.ok:
                for ev in r.json().get("results", []):
                    title = ev.get("short_title") or ev.get("title", "")
                    desc = ev.get("description", "")[:500]
                    link = ev.get("site_url", "")
                    image = ""
                    imgs = ev.get("images", [])
                    if imgs:
                        image = imgs[0].get("image", "")
                    events.append({"title": title, "desc": clean_text(desc),
                                   "link": link, "image": image, "cat": cats})
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
#  ПРОМПТЫ
# ═══════════════════════════════════════════════════════════════
VOICE_RULES = """
ГОЛОС КАНАЛА:
- Пишешь как умный коллега в курилке, не как новостная лента. Живо, точно, без воды.
- Логика первична, метафора — упаковка. Если можешь объяснить через аналогию, делай.
- Фирменные связки: «и это аргумент», «поэтому», «да, но». Используй уместно, не в каждом посте.
- Заголовок — это тезис, не пересказ. «Pentagram ушёл в монохром» лучше «Pentagram представил новый ребрендинг».
- Тон как у Loewe: умно, неожиданно, без корпоративной глянцевости.
- НИКОГДА: «является», «представляет собой», «в мире дизайна», «стоит отметить», «безусловно», «данный», «осуществлять».
- Названия брендов, продуктов, шрифтов, студий на иностранном языке НЕ переводить. Apple, Helvetica, Pentagram — как есть.
"""

REWRITE_PROMPT = """Ты редактор русскоязычного телеграм-канала о дизайне для практикующих дизайнеров.
{voice}

ЗАДАЧА: перепиши материал в короткий пост. Фокус — один конкретный приём или идея, которую дизайнер может применить в своём проекте сегодня.

СТРУКТУРА:
1. Заголовок-тезис: 40-80 символов, без точки. Не дословный перевод, а суть через позицию.
2. Пересказ: 2-3 предложения. Что случилось, конкретика.
3. Если уместно, одним предложением свяжи с более широким трендом («Третий кейс за месяц, где...», «Это перекликается с...»).

ПРАВИЛА:
- Не выдумывай фактов. Имена, цифры — ТОЛЬКО из источника.
- Общая длина: до 450 символов.

JSON БЕЗ ```:
{{"title": "...", "summary": "...", "trend": "..."}}

МАТЕРИАЛ:
Заголовок: {title}
Текст: {content}
Источник: {source}
""".replace("{voice}", VOICE_RULES)


SATURDAY_PROMPT = """Ты редактор русскоязычного телеграм-канала о дизайне. Сделай мини-разбор проекта.
{voice}

СТРУКТУРА:
1. Заголовок: 40-80 символов, позиция, не описание.
2. Контекст: 1-2 предложения. Кто, что, зачем — без лишнего.
3. Что работает: 2-3 конкретных наблюдения о дизайне. Не «красивые цвета», а «контраст между гротеском в заголовках и антиквой в наборе создаёт...».
4. Что спорно: 1 наблюдение — что вызывает вопросы или можно было решить иначе. Без хейта, с аргументом.
5. Украсть: один приём из проекта, который можно переиспользовать.

ПРАВИЛА:
- Не выдумывай. Только то, что видно в материале.
- До 700 символов.

JSON БЕЗ ```:
{{"title": "...", "context": "...", "works": "...", "debatable": "...", "steal": "..."}}

МАТЕРИАЛ:
Заголовок: {title}
Текст: {content}
Источник: {source}
""".replace("{voice}", VOICE_RULES)


DIGEST_PROMPT = """Ты редактор русскоязычного телеграм-канала о дизайне. Вечерний дайджест — лучшее за день.
{voice}

СТРУКТУРА:
1. Заголовок дайджеста: 30-50 символов, ёмкий. Не «Дайджест за среду», а что-то с характером.
2. На каждый материал: суть в одном-двух предложениях.
3. Если между материалами есть связь или общий тренд — упомяни одним предложением в конце.

JSON БЕЗ ```:
{{"title": "...", "items": [{{"name": "...", "summary": "..."}}], "trend": "..."}}

МАТЕРИАЛЫ:
{materials}
""".replace("{voice}", VOICE_RULES)


FRIDAY_PROMPT = """Ты редактор телеграм-канала о дизайне. Подборка дизайн-событий, выставок и музейных событий в Москве.
{voice}

ПРАВИЛА:
1. Только предоставленные события. Не выдумывай.
2. Заголовок: 30-60 символов, с характером.
3. На событие: название, 1 предложение что это, почему дизайнеру стоит сходить.
4. Максимум 5 событий. Приоритет: выставки дизайна и искусства > архитектура > кино.

JSON БЕЗ ```:
{{"title": "...", "events": [{{"name": "...", "oneliner": "...", "why": "..."}}]}}

СОБЫТИЯ:
{events_text}
""".replace("{voice}", VOICE_RULES)


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
    trend = parsed.get("trend", "").strip()

    parts = [
        f"<b>{html.escape(parsed['title'])}</b>",
        "",
        html.escape(parsed['summary']),
    ]
    if trend:
        parts += ["", f"📎 {html.escape(trend)}"]
    parts += [
        "",
        f"<i>{html.escape(clean_source_name(source))} · {html.escape(label)}</i>",
        html.escape(tags),
        "",
        f'🔗 <a href="{link}">Источник</a>',
    ]
    return "\n".join(parts)


def format_saturday_post(source, parsed, link):
    tags = DAY_HASHTAGS.get(5, "")
    return "\n".join([
        f"<b>🔍 {html.escape(parsed['title'])}</b>",
        "",
        html.escape(parsed['context']),
        "",
        f"✅ <b>Работает:</b> {html.escape(parsed['works'])}",
        "",
        f"🤔 <b>Спорно:</b> {html.escape(parsed['debatable'])}",
        "",
        f"🔑 <b>Украсть:</b> {html.escape(parsed['steal'])}",
        "",
        f"<i>{html.escape(clean_source_name(source))} · Разбор</i>",
        html.escape(tags),
        "",
        f'🔗 <a href="{link}">Источник</a>',
    ])


def format_digest_post(weekday, parsed, items_data):
    label = DAY_LABEL.get(weekday, "")
    tags  = DAY_HASHTAGS.get(weekday, "")
    trend = parsed.get("trend", "").strip()

    parts = [f"<b>📋 {html.escape(parsed['title'])}</b>", ""]
    for i, item in enumerate(parsed.get("items", [])):
        link = items_data[i]["link"] if i < len(items_data) else ""
        parts.append(
            f"▪️ <b>{html.escape(item['name'])}</b>\n"
            f"{html.escape(item['summary'])}"
            + (f'\n🔗 <a href="{link}">Источник</a>' if link else "")
        )
        parts.append("")
    if trend:
        parts.append(f"📎 {html.escape(trend)}")
        parts.append("")
    parts.append(f"<i>{html.escape(label)}</i>")
    parts.append(html.escape(tags))
    return "\n".join(parts)


def format_friday_post(parsed, events):
    parts = [f"<b>📍 {html.escape(parsed['title'])}</b>", ""]
    for i, ev in enumerate(parsed.get("events", [])):
        link = events[i]["link"] if i < len(events) else ""
        parts.append(
            f"▪️ <b>{html.escape(ev['name'])}</b>\n"
            f"{html.escape(ev['oneliner'])}\n"
            f"→ {html.escape(ev.get('why', ''))}"
            + (f'\n🔗 <a href="{link}">Подробнее</a>' if link else "")
        )
        parts.append("")
    parts.append(html.escape(DAY_HASHTAGS.get(4, "")))
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


def post_to_telegram(token, chat_id, text, image_bytes=None):
    """Если текст влезает в caption (1024) — фото + подпись.
       Если нет — сначала фото без подписи, потом текст отдельно."""
    if image_bytes and len(text) <= 1024:
        if tg_send_photo_bytes(token, chat_id, image_bytes, text):
            return True

    if image_bytes and len(text) > 1024:
        tg_send_photo_bytes(token, chat_id, image_bytes, "")
        return tg_send_text(token, chat_id, text)

    return tg_send_text(token, chat_id, text)


def tg_send_media_group(token, chat_id, images_bytes, caption=""):
    """Отправляет альбом из нескольких картинок. caption — на первой."""
    if not images_bytes:
        return False
    try:
        media = []
        files = {}
        for i, img_bytes in enumerate(images_bytes):
            file_key = f"photo_{i}"
            files[file_key] = (f"{file_key}.jpg", img_bytes, "image/jpeg")
            entry = {"type": "photo", "media": f"attach://{file_key}"}
            if i == 0 and caption:
                cap = caption if len(caption) <= 1024 else caption[:1020] + "..."
                entry["caption"] = cap
                entry["parse_mode"] = "HTML"
            media.append(entry)
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMediaGroup",
            data={"chat_id": chat_id, "media": json.dumps(media)},
            files=files,
            timeout=60,
        )
        if r.ok:
            return True
        print(f"    sendMediaGroup: {r.text[:200]}")
    except Exception as e:
        print(f"    sendMediaGroup: {e}")
    return False


# ═══════════════════════════════════════════════════════════════
#  ПРОВЕРКА
# ═══════════════════════════════════════════════════════════════
def check_feeds():
    print("Проверяю RSS...\n")
    ok = bad = 0
    bad_list = []
    seen = set()
    for cat, sources in SOURCES.items():
        print(f"\n[{cat}]")
        for name, url in sources:
            if url in seen:
                continue
            seen.add(url)
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
    print(f"\n\nИтого: {ok} живых, {bad} мёртвых")
    if bad_list:
        print("\nМёртвые:")
        for b in bad_list:
            print(b)


# ═══════════════════════════════════════════════════════════════
#  PINTEREST АЛЬБОМ (вечерний пост)
# ═══════════════════════════════════════════════════════════════
def extract_author(entry):
    """Пытается достать автора из RSS-записи Pinterest."""
    # Поле author
    author = entry.get("author", "")
    if author:
        return clean_text(author)
    detail = entry.get("author_detail", {})
    if detail.get("name"):
        return clean_text(detail["name"])
    # Ищем в описании: "by ...", "© ...", Behance-ссылку
    for field in ("title", "summary"):
        val = entry.get(field, "")
        if isinstance(val, list) and val:
            val = val[0].get("value", "")
        if not isinstance(val, str):
            continue
        # Behance ссылка
        beh = re.search(r'(https?://(?:www\.)?behance\.net/[^\s"<>]+)', val)
        if beh:
            return beh.group(1)
        # "by Author Name"
        by = re.search(r'(?:by|BY|By)\s+([A-Za-zА-Яа-яёЁ][A-Za-zА-Яа-яёЁ\s\.]{2,30})', val)
        if by:
            return by.group(1).strip()
        # "© Author"
        copy = re.search(r'©\s*([A-Za-zА-Яа-яёЁ][A-Za-zА-Яа-яёЁ\s\.]{2,30})', val)
        if copy:
            return copy.group(1).strip()
    return ""


def detect_media_type(url):
    """Определяет тип контента по URL."""
    low = url.lower().split("?")[0]
    if low.endswith((".mp4", ".mov", ".webm")):
        return "video"
    if low.endswith(".gif"):
        return "animation"
    return "photo"


def collect_pinterest(weekday, state):
    """Собирает пины из Pinterest-досок для текущего дня."""
    boards = PINTEREST_BOARDS.get(weekday, [])
    if not boards:
        return []
    sent_ids = set(state["sent"])
    items = []
    for name, url in boards:
        if "URL_СЮДА" in url:
            continue
        try:
            feed = feedparser.parse(url, request_headers={"User-Agent": USER_AGENT})
            for entry in (feed.entries or [])[:6]:
                item_id = entry.get("id") or entry.get("link")
                if not item_id or item_id in sent_ids:
                    continue
                image = extract_image_url(entry)
                if not image and entry.get("link"):
                    image = fetch_og_image(entry.get("link", ""))
                if image:
                    author = extract_author(entry)
                    items.append({
                        "id": item_id,
                        "image": image,
                        "media_type": detect_media_type(image),
                        "source": name,
                        "link": entry.get("link", ""),
                        "author": author,
                    })
        except Exception as e:
            print(f"  Pinterest {name}: {e}")
    return items


def tg_send_media_group_raw(token, chat_id, media_items, caption=""):
    """Отправляет альбом по URL без обработки. Поддерживает photo/video/animation."""
    if not media_items:
        return False
    try:
        media = []
        for i, item in enumerate(media_items):
            entry = {"type": item["media_type"], "media": item["url"]}
            if i == 0 and caption:
                cap = caption if len(caption) <= 1024 else caption[:1020] + "..."
                entry["caption"] = cap
                entry["parse_mode"] = "HTML"
            media.append(entry)
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMediaGroup",
            data={"chat_id": chat_id, "media": json.dumps(media)},
            timeout=60,
        )
        if r.ok:
            return True
        print(f"    sendMediaGroup: {r.text[:200]}")
    except Exception as e:
        print(f"    sendMediaGroup: {e}")
    return False


def run_pinterest_album(token, chat_id, weekday, state):
    """Вечерний пост: альбом из 6 пинов без обработки + авторы."""
    print("Вечер — Pinterest-подборка")
    pinterest_items = collect_pinterest(weekday, state)
    print(f"  Найдено пинов: {len(pinterest_items)}")

    if len(pinterest_items) < 2:
        print("  мало контента для альбома")
        return False

    selected = pinterest_items[:PINTEREST_ALBUM_SIZE]

    tags = DAY_HASHTAGS.get(weekday, "")
    label = DAY_LABEL.get(weekday, "")
    boards_used = list(dict.fromkeys(it["source"] for it in selected))
    boards_str = " · ".join(boards_used[:3])
    caption = (
        f"<b>🎨 Визуальные референсы дня</b>\n\n"
        f"<i>{html.escape(boards_str)} · {html.escape(label)}</i>\n"
        f"{html.escape(tags)}"
    )

    # Готовим медиа — отправляем как есть, без кропа
    media_for_tg = []
    used = []
    for item in selected:
        media_for_tg.append({
            "url": item["image"],
            "media_type": item["media_type"],
        })
        used.append(item)

    if not tg_send_media_group_raw(token, chat_id, media_for_tg, caption):
        print("  ✗ альбом не отправился")
        return False

    for item in used:
        state["sent"].append(item["id"])

    # Авторы: собираем тех, у кого указан автор
    credits = []
    for item in used:
        if item["author"]:
            author = item["author"]
            if author.startswith("http"):
                credits.append(f'<a href="{author}">{html.escape(item["source"])}</a>')
            else:
                line = html.escape(author)
                if item["link"]:
                    line += f' · <a href="{item["link"]}">пин</a>'
                credits.append(line)

    if credits:
        unique_credits = list(dict.fromkeys(credits))
        credits_text = "✏️ " + " | ".join(unique_credits)
        tg_send_text(token, chat_id, credits_text)

    print(f"  ✓ альбом из {len(used)} пинов")
    return True


# ═══════════════════════════════════════════════════════════════
#  УТРЕННИЙ ПОСТ (статья)
# ═══════════════════════════════════════════════════════════════
def run_morning(token, chat_id, client, weekday, state):
    if weekday == 4:
        return run_friday(token, chat_id, client, state)

    categories = DAILY_CATEGORIES[weekday]
    candidates = collect_candidates(categories, state)
    print(f"Кандидатов: {len(candidates)}")
    if not candidates:
        print("Нет свежих материалов.")
        return False

    is_saturday = (weekday == 5)

    for item in candidates:
        print(f"\n→ {item['source']}: {item['title'][:60]}")
        content = item["summary"]
        if len(content) < 400 and item["link"]:
            print("    подтягиваю текст...")
            content = fetch_full_text(item["link"], fallback=content) or content

        image_url = item["image"]
        if not image_url and item["link"]:
            image_url = fetch_og_image(item["link"])

        try:
            if is_saturday:
                parsed = call_claude(client, SATURDAY_PROMPT.format(
                    title=item["title"], content=content[:4000], source=item["source"]))
                text = format_saturday_post(item["source"], parsed, item["link"])
            else:
                parsed = call_claude(client, REWRITE_PROMPT.format(
                    title=item["title"], content=content[:4000], source=item["source"]))
                text = format_regular_post(weekday, item["source"], parsed, item["link"])
        except Exception as e:
            print(f"    Claude: {e}")
            continue

        cover = None
        if image_url:
            cover = make_cover_image(image_url, item["category"], item["source"])

        if post_to_telegram(token, chat_id, text, cover):
            state["sent"].append(item["id"])
            print("    ✓ опубликовано")
            return True
        print("    ✗ ошибка отправки")
    return False


# ═══════════════════════════════════════════════════════════════
#  ПЯТНИЦА
# ═══════════════════════════════════════════════════════════════
def run_friday(token, chat_id, client, state):
    print("Пятница — мероприятия, музеи, выставки")
    events = fetch_kudago_events(8)
    print(f"  KudaGo: {len(events)} событий")

    for src_name, feed_url in SOURCES.get("Москва события", []):
        try:
            feed = feedparser.parse(feed_url, request_headers={"User-Agent": USER_AGENT})
            for entry in (feed.entries or [])[:5]:
                title = clean_text(entry.get("title", ""))
                link = entry.get("link", "")
                summary = entry.get("summary", "")
                if isinstance(summary, list):
                    summary = summary[0].get("value", "") if summary else ""
                events.append({"title": title, "desc": clean_text(re.sub(r"<[^>]+>", " ", summary))[:300],
                               "link": link, "image": extract_image_url(entry) or "", "cat": "telegram"})
        except Exception as e:
            print(f"  {src_name}: {e}")

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

    card = generate_friday_card(parsed.get("title", "События"), parsed.get("events", events))
    if not card:
        image_url = next((ev["image"] for ev in events if ev.get("image")), None)
        if image_url:
            card = make_cover_image(image_url, "Москва события")

    if post_to_telegram(token, chat_id, text, card):
        for ev in events:
            if ev.get("link"):
                state["sent"].append(ev["link"])
        print("  ✓ опубликовано")
        return True
    return False


# ═══════════════════════════════════════════════════════════════
#  ВЕЧЕРНИЙ ПОСТ: Pinterest-альбом или текстовый дайджест
# ═══════════════════════════════════════════════════════════════
def run_digest(token, chat_id, client, weekday, state):
    """Вечер: Pinterest-альбом. Если нет досок или картинок — текстовый дайджест."""
    # Сначала пробуем Pinterest
    if weekday in PINTEREST_BOARDS:
        result = run_pinterest_album(token, chat_id, weekday, state)
        if result:
            return True
        print("  Pinterest не получился, пробуем текстовый дайджест")

    # Фоллбэк: текстовый дайджест (для дней без Pinterest, напр. четверг)
    categories = DAILY_CATEGORIES[weekday]
    candidates = collect_candidates(categories, state)
    print(f"Кандидатов для дайджеста: {len(candidates)}")
    if not candidates:
        print("Нет материалов.")
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
    image_url = next((it["image"] for it in selected if it.get("image")), None)
    cover = None
    if image_url:
        first_cat = selected[0]["category"] if selected else ""
        cover = make_cover_image(image_url, first_cat)

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

    print(f"Режим: {mode}")
    print(f"Рубрика: {DAY_LABEL.get(weekday, '')}\n")

    ensure_font()

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
