"""
Telegram-бот для дизайн-канала.

Один пост в день, 10:00 МСК. Рубрики ротируются по дням недели.
Пятница — подборка событий в Москве (KudaGo API).
Воскресенье — выходной.

  python bot.py        # обычный прогон
  python bot.py check  # проверка живости всех RSS
"""

import os
import re
import sys
import json
import time
import html
import io
from pathlib import Path
from datetime import datetime, timezone, timedelta

import feedparser
import requests
import anthropic
import trafilatura
from PIL import Image


# ═══════════════════════════════════════════════════════════════
#  ИСТОЧНИКИ
# ═══════════════════════════════════════════════════════════════
# Помечено # ? — непроверенные фиды. Запусти `python bot.py check`.
# Telegram-каналы идут через rsshub.app — бесплатный публичный мост.
# Если rsshub.app лежит — разверни свой: github.com/DIYgod/RSSHub

SOURCES = {
    # --- ПОНЕДЕЛЬНИК: типографика, брендинг, интерфейсы, 3D ---
    "Типографика": [
        ("Fonts In Use",      "https://fontsinuse.com/all.atom"),
        ("Typewolf",          "https://www.typewolf.com/feed"),
        ("I Love Typography", "https://ilovetypography.com/feed/"),
        ("Type Today",        "https://type.today/feed"),              # ?
        ("ParaType",          "https://info.paratype.ru/feed/"),       # ?
        ("Alphabettes",       "https://www.alphabettes.org/feed/"),
        ("Главред",           "https://rsshub.app/telegram/channel/glvrdru"),  # ?
    ],
    "Брендинг": [
        ("Brand New",              "https://www.underconsideration.com/brandnew/atom.xml"),
        ("Pentagram",              "https://www.pentagram.com/feed/"),        # ?
        ("Packaging of the World", "https://packagingoftheworld.com/feeds/posts/default?alt=rss"),
        ("Design Collector",       "https://designcollector.net/feed/"),      # ?
    ],
    "Интерфейсы": [
        ("Smashing Magazine", "https://www.smashingmagazine.com/feed/"),
        ("Codrops",           "https://tympanus.net/codrops/feed/"),
        ("Awwwards",          "https://www.awwwards.com/blog/feed/"),
        ("DesignBoard",       "https://rsshub.app/telegram/channel/DesignBoard"),  # ?
    ],
    "3D и моушен": [
        ("LeManoosh",          "https://lemanoosh.com/feed/"),                         # ?
        ("Vimeo Inspiration",  "https://rsshub.app/telegram/channel/Vimeoinspiration"),  # ?
        ("Motionographer",     "https://motionographer.com/feed/"),
    ],

    # --- ВТОРНИК: индустриальный дизайн ---
    "Индустриальный дизайн": [
        ("Dezeen",           "https://www.dezeen.com/feed/"),
        ("Designboom",       "https://www.designboom.com/feed/"),
        ("Design Collector", "https://designcollector.net/feed/"),    # ?
        ("LeManoosh",        "https://lemanoosh.com/feed/"),          # ?
        ("Yanko Design",     "https://www.yankodesign.com/feed/"),
        ("Core77",           "https://www.core77.com/feed"),          # ?
    ],

    # --- СРЕДА: студии, искусство, фото ---
    "Студии и блоги": [
        ("It's Nice That",   "https://www.itsnicethat.com/rss"),
        ("Creative Review",  "https://www.creativereview.co.uk/feed/"),
        ("Eye on Design",    "https://eyeondesign.aiga.org/feed/"),
        ("Sidebar.io",       "https://sidebar.io/feed.xml"),
        ("Илья Бирман",      "https://ilyabirman.ru/meanwhile/rss/"),
    ],
    "Искусство": [
        ("Hyperallergic",     "https://hyperallergic.com/feed/"),
        ("Colossal",          "https://www.thisiscolossal.com/feed/"),
        ("Juxtapoz",          "https://www.juxtapoz.com/news?format=feed"),
        ("Артгид",            "https://artguide.com/rss"),             # ?
    ],
    "Фото": [
        ("The Blueprint",     "https://theblueprint.ru/rss"),          # ?
        ("Colta",             "https://www.colta.ru/feed"),            # ?
    ],

    # --- ЧЕТВЕРГ: ИИ в дизайне ---
    "ИИ в дизайне": [
        ("AI Newz",       "https://rsshub.app/telegram/channel/ai_newz"),   # ?
        ("Хабр",          "https://habr.com/en/feed/"),
        ("The Verge AI",  "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),  # ?
    ],

    # --- ПЯТНИЦА: события в Москве (KudaGo API, не RSS) ---
    # Источники для пятницы задаются отдельно через KudaGo.
    # Дополнительно: @sale_caviar
    "Москва события": [
        ("sale_caviar",  "https://rsshub.app/telegram/channel/sale_caviar"),  # ?
    ],

    # --- СУББОТА: туториалы, ресурсы, студии ---
    "Туториалы": [
        ("Smashing Magazine", "https://www.smashingmagazine.com/feed/"),
        ("Codrops",           "https://tympanus.net/codrops/feed/"),
        ("Хабр",              "https://habr.com/en/feed/"),
        ("DesignBoard",       "https://rsshub.app/telegram/channel/DesignBoard"),  # ?
        ("Design Collector",  "https://designcollector.net/feed/"),                # ?
        ("LeManoosh",         "https://lemanoosh.com/feed/"),                       # ?
        ("Motionographer",    "https://motionographer.com/feed/"),
    ],
}

# Какие рубрики в какой день. 0 = ПН, 6 = ВС.
DAILY_CATEGORIES = {
    0: ["Типографика", "Брендинг", "Интерфейсы", "3D и моушен"],
    1: ["Индустриальный дизайн"],
    2: ["Студии и блоги", "Искусство", "Фото"],
    3: ["ИИ в дизайне"],
    4: ["Москва события"],          # пятница — подборка событий
    5: ["Туториалы"],
    # 6 (воскресенье) — выходной, бот не постит
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
    5: "Туториалы · Ресурсы · Студии",
}

DAY_HASHTAGS = {
    0: "#типографика #брендинг #ui #3d",
    1: "#индустриальныйдизайн #продуктовыйдизайн",
    2: "#искусство #фотография #дизайнстудии",
    3: "#ии #нейросети #дизайн",
    4: "#москва #выставки #дизайнсобытия",
    5: "#туториал #ресурсы #инструменты",
}

# ═══════════════════════════════════════════════════════════════
#  ПАРАМЕТРЫ
# ═══════════════════════════════════════════════════════════════
STATE_FILE     = "sent_items.json"
MAX_AGE_HOURS  = 48
HISTORY_LIMIT  = 3000
USER_AGENT     = "Mozilla/5.0 (compatible; DesignNewsBot/1.0)"
CLAUDE_MODEL   = "claude-haiku-4-5"
IMAGE_SIZE     = 1080   # квадрат 1080x1080


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
#  КАРТИНКА: извлечение + обрезка в квадрат
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


def make_square_image(image_url):
    """Скачивает картинку, обрезает в квадрат, возвращает bytes JPEG."""
    try:
        r = requests.get(image_url, timeout=20, headers={"User-Agent": USER_AGENT})
        if not r.ok:
            return None
        img = Image.open(io.BytesIO(r.content))
        img = img.convert("RGB")
        w, h = img.size
        side = min(w, h)
        left = (w - side) // 2
        top  = (h - side) // 2
        img = img.crop((left, top, left + side, top + side))
        img = img.resize((IMAGE_SIZE, IMAGE_SIZE), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=92)
        buf.seek(0)
        return buf.getvalue()
    except Exception as e:
        print(f"    обрезка картинки: {e}")
        return None


# ═══════════════════════════════════════════════════════════════
#  ПОЛНЫЙ ТЕКСТ СТАТЬИ
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
#  KUDAGO API — пятничная подборка событий в Москве
# ═══════════════════════════════════════════════════════════════
def fetch_kudago_events(limit=6):
    """Возвращает список актуальных дизайн/арт/кино событий в Москве."""
    now_ts = int(time.time())
    week_later = now_ts + 7 * 86400
    events = []
    for cats in ["exhibition", "festival", "cinema"]:
        try:
            r = requests.get(
                "https://kudago.com/public-api/v1.4/events/",
                params={
                    "location":     "msk",
                    "categories":   cats,
                    "fields":       "title,short_title,description,dates,site_url,images,place",
                    "page_size":    10,
                    "actual_since": now_ts,
                    "actual_until": week_later,
                    "order_by":     "-publication_date",
                    "text_format":  "plain",
                },
                timeout=20,
            )
            if r.ok:
                data = r.json()
                for ev in data.get("results", []):
                    title = ev.get("short_title") or ev.get("title", "")
                    desc  = ev.get("description", "")[:500]
                    link  = ev.get("site_url", "")
                    image = ""
                    imgs  = ev.get("images", [])
                    if imgs:
                        image = imgs[0].get("image", "")
                    events.append({
                        "title": title,
                        "desc":  re.sub(r"<[^>]+>", " ", desc).strip(),
                        "link":  link,
                        "image": image,
                        "cat":   cats,
                    })
        except Exception as e:
            print(f"  KudaGo ({cats}): {e}")
    # дедуплицируем по заголовку
    seen = set()
    unique = []
    for ev in events:
        key = ev["title"].lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(ev)
    return unique[:limit]


# ═══════════════════════════════════════════════════════════════
#  CLAUDE: пересказ обычного поста
# ═══════════════════════════════════════════════════════════════
REWRITE_PROMPT = """Ты редактор русскоязычного телеграм-канала о дизайне для практикующих дизайнеров.
Перепиши материал в короткий пост.

ПРАВИЛА:
1. Не выдумывай фактов. Имена, цифры, бренды — ТОЛЬКО из источника.
2. Живой русский. Без канцелярита, "является", "представляет собой", длинных тире.
3. Заголовок: одна строка, 40-80 символов, без точки. Заголовок-тезис, не дословный перевод.
4. Пересказ: 2-3 коротких предложения. Что произошло, о чём материал. Конкретика.
5. Польза: 1-2 предложения — что дизайнер может отсюда забрать (приём, идея, инструмент, наблюдение).
6. Общая длина title + summary + value: до 500 символов.

ВЕРНИ СТРОГО JSON БЕЗ ```:
{{"title": "...", "summary": "...", "value": "..."}}

МАТЕРИАЛ:
Заголовок: {title}
Текст: {content}
Источник: {source}
"""

FRIDAY_PROMPT = """Ты редактор телеграм-канала о дизайне. Составь пост-подборку дизайн-событий в Москве на ближайшую неделю.

ПРАВИЛА:
1. Не выдумывай. Используй ТОЛЬКО предоставленные события.
2. Живой русский. Без канцелярита.
3. Заголовок подборки: короткий, 30-60 символов.
4. На каждое событие: название, 1 предложение что это, и почему стоит сходить дизайнеру.
5. Максимум 5 событий. Если событий меньше — бери сколько есть.

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


def rewrite_article(client, title, content, source):
    resp = client.messages.create(
        model=CLAUDE_MODEL, max_tokens=800, temperature=0.3,
        messages=[{"role": "user", "content": REWRITE_PROMPT.format(
            title=title, content=content[:4000], source=source)}],
    )
    return extract_json(resp.content[0].text)


def rewrite_events(client, events):
    events_text = ""
    for i, ev in enumerate(events, 1):
        events_text += f"{i}. {ev['title']}\n   {ev['desc'][:200]}\n   Ссылка: {ev['link']}\n\n"
    resp = client.messages.create(
        model=CLAUDE_MODEL, max_tokens=1000, temperature=0.3,
        messages=[{"role": "user", "content": FRIDAY_PROMPT.format(events_text=events_text)}],
    )
    return extract_json(resp.content[0].text)


# ═══════════════════════════════════════════════════════════════
#  ФОРМАТИРОВАНИЕ ПОСТОВ
# ═══════════════════════════════════════════════════════════════
def format_regular_post(weekday, source, parsed, link):
    label = DAY_LABEL.get(weekday, "")
    tags  = DAY_HASHTAGS.get(weekday, "")
    return (
        f"<b>{html.escape(parsed['title'])}</b>\n\n"
        f"{html.escape(parsed['summary'])}\n\n"
        f"💡 {html.escape(parsed['value'])}\n\n"
        f"<i>{html.escape(source)} · {html.escape(label)}</i>\n\n"
        f"{html.escape(tags)}\n\n"
        f"🔗 {link}"
    )


def format_friday_post(parsed, events, links):
    parts = [f"<b>{html.escape(parsed['title'])}</b>\n"]
    for i, ev in enumerate(parsed.get("events", [])):
        link = links[i] if i < len(links) else ""
        parts.append(
            f"\n▪️ <b>{html.escape(ev['name'])}</b>\n"
            f"{html.escape(ev['oneliner'])}\n"
            f"→ {html.escape(ev.get('why', ''))}"
            + (f"\n🔗 {link}" if link else "")
        )
    tags = DAY_HASHTAGS.get(4, "")
    parts.append(f"\n\n{html.escape(tags)}")
    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════
#  TELEGRAM
# ═══════════════════════════════════════════════════════════════
def tg_send_photo_bytes(token, chat_id, photo_bytes, caption):
    """Отправляет квадратную картинку как файл."""
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
        print(f"    sendPhoto (bytes): {e}")
    return False


def tg_send_photo_url(token, chat_id, url, caption):
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendPhoto",
            data={"chat_id": chat_id, "photo": url,
                  "caption": caption, "parse_mode": "HTML"},
            timeout=30,
        )
        if r.ok:
            return True
    except Exception:
        pass
    return False


def tg_send_text(token, chat_id, text):
    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data={"chat_id": chat_id, "text": text, "parse_mode": "HTML",
              "disable_web_page_preview": False},
        timeout=30,
    )
    return r.ok


def post_to_telegram(token, chat_id, text, image_url=None):
    """Пытается отправить пост с квадратной картинкой. Фоллбэки по цепочке."""
    caption = text if len(text) <= 1024 else text[:1020] + "..."

    if image_url:
        # 1. Скачиваем и обрезаем в квадрат
        sq = make_square_image(image_url)
        if sq:
            if tg_send_photo_bytes(token, chat_id, sq, caption):
                return True

        # 2. Фоллбэк: картинка по URL как есть
        if tg_send_photo_url(token, chat_id, image_url, caption):
            return True

    # 3. Просто текст
    return tg_send_text(token, chat_id, text)


# ═══════════════════════════════════════════════════════════════
#  ПРОВЕРКА ЛЕНТ
# ═══════════════════════════════════════════════════════════════
def check_feeds():
    print("Проверяю все RSS-ленты...\n")
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
                    print(f"  ✓ {name:<24} {count} записей")
                    ok += 1
                else:
                    print(f"  ✗ {name:<24} пусто / ошибка")
                    bad_list.append(f"  {cat} · {name}  →  {url}")
                    bad += 1
            except Exception as e:
                print(f"  ✗ {name:<24} {e}")
                bad_list.append(f"  {cat} · {name}  →  {url}")
                bad += 1
    # Проверяем KudaGo
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
#  ОБЫЧНЫЙ ПРОГОН (не пятница)
# ═══════════════════════════════════════════════════════════════
def run_regular(token, chat_id, client, weekday, state):
    categories = DAILY_CATEGORIES[weekday]
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
                        "source":   source_name,
                        "title":    entry.get("title", ""),
                        "link":     entry.get("link", ""),
                        "image":    extract_image_url(entry),
                        "summary":  re.sub(r"<[^>]+>", " ", summary)[:2000],
                        "ts":       pub_ts,
                    })
            except Exception as e:
                print(f"  ошибка {source_name}: {e}")

    if not candidates:
        print("Нет свежих материалов.")
        return False

    candidates.sort(key=lambda x: x["ts"], reverse=True)
    print(f"Кандидатов: {len(candidates)}")

    # Берём самый свежий
    for item in candidates:
        print(f"\n→ {item['source']}: {item['title'][:60]}")

        content = item["summary"]
        if len(content) < 400 and item["link"]:
            print("    подтягиваю полный текст...")
            content = fetch_full_text(item["link"], fallback=content) or content

        image = item["image"]
        if not image and item["link"]:
            image = fetch_og_image(item["link"])

        try:
            parsed = rewrite_article(client, item["title"], content, item["source"])
        except Exception as e:
            print(f"    Claude ошибка: {e}")
            continue

        text = format_regular_post(weekday, item["source"], parsed, item["link"])
        ok = post_to_telegram(token, chat_id, text, image)
        if ok:
            state["sent"].append(item["id"])
            print("    ✓ опубликовано")
            return True
        else:
            print("    ✗ ошибка отправки, пробую следующий")
            continue

    print("Не удалось опубликовать ни один материал.")
    return False


# ═══════════════════════════════════════════════════════════════
#  ПЯТНИЧНАЯ ПОДБОРКА
# ═══════════════════════════════════════════════════════════════
def run_friday(token, chat_id, client, state):
    print("Пятница — подборка событий в Москве")

    # 1. KudaGo
    events = fetch_kudago_events(8)
    print(f"  KudaGo: {len(events)} событий")

    # 2. RSS @sale_caviar и другие из "Москва события"
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
                    "desc":  re.sub(r"<[^>]+>", " ", summary)[:300],
                    "link":  link,
                    "image": extract_image_url(entry) or "",
                    "cat":   "telegram",
                })
        except Exception as e:
            print(f"  {source_name}: {e}")

    if not events:
        print("  нет событий, пропускаем")
        return False

    # Пересказ через Claude
    try:
        parsed = rewrite_events(client, events[:8])
    except Exception as e:
        print(f"  Claude ошибка: {e}")
        return False

    links = [ev.get("link", "") for ev in events]
    text  = format_friday_post(parsed, events, links)

    # Картинка — от первого события с картинкой
    image = None
    for ev in events:
        if ev.get("image"):
            image = ev["image"]
            break

    ok = post_to_telegram(token, chat_id, text, image)
    if ok:
        # помечаем все ссылки как отправленные
        for ev in events:
            if ev.get("link"):
                state["sent"].append(ev["link"])
        print("  ✓ подборка опубликована")
        return True
    else:
        print("  ✗ ошибка отправки")
        return False


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════
def main():
    token         = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id       = os.environ["TELEGRAM_CHAT_ID"]
    anthropic_key = os.environ["ANTHROPIC_API_KEY"]
    client        = anthropic.Anthropic(api_key=anthropic_key)

    msk     = datetime.now(timezone(timedelta(hours=3)))
    weekday = msk.weekday()
    print(f"Сегодня: {msk.strftime('%A %d.%m.%Y')}, день {weekday}")

    if weekday == 6:
        print("Воскресенье — выходной, бот не постит.")
        return

    if weekday not in DAILY_CATEGORIES:
        print(f"Нет рубрик для дня {weekday}.")
        return

    state = load_state()
    is_first_run = not state.get("initialized")

    if is_first_run:
        # Инициализация: запоминаем текущие ID без постинга
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
        print(f"Записано {len(state['sent'])} ID. Со следующего запуска пойдут посты.")
        return

    label = DAY_LABEL.get(weekday, "")
    print(f"Рубрика дня: {label}\n")

    if weekday == 4:
        run_friday(token, chat_id, client, state)
    else:
        run_regular(token, chat_id, client, weekday, state)

    save_state(state)
    print("\nГотово.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        check_feeds()
    else:
        main()
