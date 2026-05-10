"""
Telegram-бот для дизайн-канала.

- Раз в сутки в 17:00 МСК (14:00 UTC) собирает свежее из RSS
- Берёт рубрики дня (ротация по дням недели)
- Пересказывает каждую новость на русском через Claude (без выдумывания фактов)
- Постит 3 материала с картинкой, структурой и хэштегами

Запуск:
  python bot.py        # обычный прогон
  python bot.py check  # проверка живости всех лент
"""

import os
import re
import sys
import json
import time
import html
from pathlib import Path
from datetime import datetime, timezone, timedelta

import feedparser
import requests
import anthropic
import trafilatura


# ---------- Источники ----------
SOURCES = {
    "Дизайн": [
        ("Dezeen",             "https://www.dezeen.com/feed/"),
        ("Lemanoosh",          "https://lemanoosh.com/rss"),
        ("Designboom",         "https://www.designboom.com/feed/"),
        ("Creative Review",    "https://www.creativereview.co.uk/feed/"),
        ("Brand New",          "https://www.underconsideration.com/brandnew/atom.xml"),
        ("Print Magazine",     "https://www.printmag.com/feed/"),
        ("Slanted",            "https://www.slanted.de/feed/"),
    ],
    "Типографика": [
        ("Typewolf",          "https://www.typewolf.com/feed"),
        ("I Love Typography", "https://ilovetypography.com/feed/"),
        ("Alphabettes",       "https://www.alphabettes.org/feed/"),
    ],
    "Студии и блоги": [
        ("Sidebar.io",          "https://sidebar.io/feed.xml"),
        ("Илья Бирман",         "https://ilyabirman.ru/meanwhile/rss/"),
        ("Артемий Лебедев",     "https://tema.livejournal.com/data/rss"),
    ],
    "Архитектура": [
        ("ArchDaily",            "https://www.archdaily.com/feed"),
        ("Architizer",           "https://architizer.com/blog/feed/"),
        ("Architectural Digest", "https://www.architecturaldigest.com/feed/rss"),
    ],
    "Веб и интерфейсы": [
        ("Smashing Magazine", "https://www.smashingmagazine.com/feed/"),
        ("Codrops",           "https://tympanus.net/codrops/feed/"),
        ("Awwwards",          "https://www.awwwards.com/blog/feed/"),
    ],
    "Анимация": [
        ("Motionographer", "https://motionographer.com/feed/"),
    ],
    "Искусство": [
        ("Hyperallergic",     "https://hyperallergic.com/feed/"),
        ("Colossal",          "https://www.thisiscolossal.com/feed/"),
        ("ARTnews",           "https://www.artnews.com/feed/"),
        ("Juxtapoz",          "https://www.juxtapoz.com/news?format=feed"),
        ("Artsy",             "https://www.artsy.net/rss/news"),       
        ("Colta",             "https://www.colta.ru/feed"),            
        ("The Blueprint",     "https://theblueprint.ru/rss"),          
    ],
    "Русский дизайн": [
        ("Хабр Дизайн",         "https://habr.com/ru/rss/hub/design/?fl=ru"),
        ("Awdee",               "https://awdee.ru/feed/"),               
    ],
    "Кино": [
        ("IndieWire",         "https://www.indiewire.com/feed/"),
        ("Variety",           "https://variety.com/feed/"),
        ("Little White Lies", "https://lwlies.com/feed/"),
    ],
    "Музыка": [
        ("Pitchfork",     "https://pitchfork.com/rss/news/"),
        ("The Quietus",   "https://thequietus.com/feed"),
        ("FACT Magazine", "https://www.factmag.com/feed/"),
    ],
}

CATEGORY_EMOJI = {
    "Дизайн":           "🎨",
    "Типографика":      "🔤",
    "Студии и блоги":   "✍️",
    "Архитектура":      "🏛",
    "Веб и интерфейсы": "💻",
    "Анимация":         "🎞",
    "Искусство":        "🖼",
    "Русский дизайн":   "🇷🇺",
    "Кино":             "🎬",
    "Музыка":           "🎵",
}

CATEGORY_HASHTAG = {
    "Дизайн":           "#дизайн",
    "Типографика":      "#типографика",
    "Студии и блоги":   "#студии",
    "Архитектура":      "#архитектура",
    "Веб и интерфейсы": "#веб",
    "Анимация":         "#анимация",
    "Искусство":        "#искусство",
    "Русский дизайн":   "#русдизайн",
    "Кино":             "#кино",
    "Музыка":           "#музыка",
}

# Расписание рубрик по дням недели (0 = понедельник).
# Все 10 рубрик прокатываются за неделю, без полных повторений.
DAILY_CATEGORIES = {
    0: ["Дизайн", "Типографика"],
    1: ["Архитектура", "Веб и интерфейсы"],
    2: ["Студии и блоги", "Русский дизайн"],
    3: ["Искусство"],
    4: ["Анимация", "Кино"],
    5: ["Музыка", "Дизайн"],
    6: ["Искусство", "Типографика"],
}

# ---------- Параметры ----------
STATE_FILE          = "sent_items.json"
POSTS_PER_DAY       = 3
MAX_AGE_HOURS       = 36
HISTORY_LIMIT       = 3000
SLEEP_BETWEEN_POSTS = 4
USER_AGENT          = "Mozilla/5.0 (compatible; DesignNewsBot/1.0)"
CLAUDE_MODEL        = "claude-haiku-4-5"


# ---------- Состояние ----------
def load_state():
    p = Path(STATE_FILE)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"sent": [], "initialized": False}


def save_state(state):
    state["sent"] = state["sent"][-HISTORY_LIMIT:]
    Path(STATE_FILE).write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ---------- Извлечение картинки ----------
def extract_image(entry):
    thumb = entry.get("media_thumbnail")
    if thumb:
        url = thumb[0].get("url")
        if url:
            return url
    media = entry.get("media_content")
    if media:
        url = media[0].get("url")
        if url:
            return url
    for link in entry.get("links", []):
        if link.get("type", "").startswith("image"):
            return link.get("href")
    for field in ("content", "summary"):
        val = entry.get(field)
        if isinstance(val, list) and val:
            val = val[0].get("value", "")
        if isinstance(val, str) and val:
            m = re.search(r'<img[^>]+src="([^"]+)"', val)
            if m:
                return m.group(1)
    return None


def fetch_og_image(url):
    """Запасной вариант: тащим og:image со страницы материала."""
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": USER_AGENT})
        if not r.ok:
            return None
        m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', r.text)
        if m:
            return m.group(1)
    except Exception:
        pass
    return None


# ---------- Извлечение полного текста ----------
def fetch_full_text(url, fallback=""):
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(
                downloaded,
                include_comments=False,
                include_tables=False,
                favor_precision=True,
            )
            if text and len(text) > 200:
                return text[:4000]
    except Exception as e:
        print(f"    trafilatura: {e}")
    return fallback


# ---------- Перевод и пересказ через Claude ----------
REWRITE_PROMPT = """Ты редактор русскоязычного телеграм-канала о дизайне для практикующих дизайнеров.
Перепиши материал в короткий пост для канала.

ЖЁСТКИЕ ПРАВИЛА:
1. Не выдумывай факты. Если чего-то нет в оригинале — не пиши. Имена, цифры, названия студий и брендов пиши ТОЛЬКО как в источнике.
2. Живой русский язык. Без канцелярита. Без длинных тире. Без лишних кавычек. Без "является", "представляет собой".
3. Заголовок: одна строка, 50-90 символов, без точки и кавычек. Не переводи дословно — сделай заголовок-тезис.
4. Пересказ: 2-3 коротких предложения. Что произошло, о чём материал. Конкретно.
5. Польза: 1-2 предложения, что дизайнер может из этого вынести (приём, идея, наблюдение). Если материал чисто новостной — короткое наблюдение или вывод.
6. Хэштеги: 2-3 коротких тематических на русском, без пробелов внутри (например #брендинг #айдентика #моушен). Без #дизайн — он добавится автоматически.
7. Общая длина title + summary + value: до 600 символов.

ВЕРНИ СТРОГО ТОЛЬКО JSON, БЕЗ ОБЁРТКИ ```:
{"title": "...", "summary": "...", "value": "...", "hashtags": ["#...", "#..."]}

МАТЕРИАЛ:
Заголовок: {title}
Текст: {content}
Источник: {source}
Ссылка: {link}
"""


def extract_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    # на всякий случай ищем фигурные скобки
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        text = m.group(0)
    return json.loads(text)


def rewrite_with_claude(client, title, content, source, link):
    prompt = REWRITE_PROMPT.format(
        title=title,
        content=content[:4000],
        source=source,
        link=link,
    )
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=800,
        temperature=0.3,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text
    parsed = extract_json(raw)
    # валидация
    for key in ("title", "summary", "value", "hashtags"):
        if key not in parsed:
            raise ValueError(f"нет ключа {key} в ответе модели")
    return parsed


# ---------- Формат поста ----------
def format_post(category, source, parsed):
    emoji = CATEGORY_EMOJI.get(category, "•")
    base_tag = CATEGORY_HASHTAG.get(category, "")
    extra_tags = [t for t in parsed.get("hashtags", []) if isinstance(t, str)]
    # склеиваем хэштеги, базовый первым, без дублей
    seen = set()
    all_tags = []
    for t in [base_tag] + extra_tags:
        t_norm = t.strip().lower()
        if t and t_norm not in seen:
            seen.add(t_norm)
            all_tags.append(t.strip())
    hashtags = " ".join(all_tags)

    return (
        f"{emoji} <i>{html.escape(category)} · {html.escape(source)}</i>\n\n"
        f"<b>{html.escape(parsed['title'].strip())}</b>\n\n"
        f"{html.escape(parsed['summary'].strip())}\n\n"
        f"💡 {html.escape(parsed['value'].strip())}\n\n"
        f"{html.escape(hashtags)}"
    )


# ---------- Telegram ----------
def send_photo(token, chat_id, image_url, caption):
    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendPhoto",
        data={"chat_id": chat_id, "photo": image_url,
              "caption": caption, "parse_mode": "HTML"},
        timeout=30,
    )
    return r.ok, r.text[:200]


def send_message(token, chat_id, text):
    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data={"chat_id": chat_id, "text": text, "parse_mode": "HTML",
              "disable_web_page_preview": False},
        timeout=30,
    )
    return r.ok, r.text[:200]


def post_to_telegram(token, chat_id, text, link, image_url=None):
    text_with_link = f"{text}\n\n{link}"
    # caption в sendPhoto — лимит 1024 символа
    if image_url and len(text_with_link) <= 1024:
        ok, _ = send_photo(token, chat_id, image_url, text_with_link)
        if ok:
            return True
        # картинка не подгрузилась — фоллбэк ниже
    return send_message(token, chat_id, text_with_link)[0]


# ---------- Проверка фидов ----------
def check_feeds():
    print("Проверяю все ленты...\n")
    ok_count = bad_count = 0
    bad = []
    for category, sources in SOURCES.items():
        print(f"\n[{category}]")
        for name, url in sources:
            try:
                feed = feedparser.parse(url, request_headers={"User-Agent": USER_AGENT})
                count = len(feed.entries)
                if count > 0:
                    print(f"  ✓ {name:<22} {count} записей")
                    ok_count += 1
                else:
                    reason = "пусто"
                    if feed.bozo:
                        reason = f"ошибка: {type(feed.bozo_exception).__name__}"
                    print(f"  ✗ {name:<22} {reason}")
                    bad.append(f"{category} · {name}  →  {url}")
                    bad_count += 1
            except Exception as e:
                print(f"  ✗ {name:<22} {e}")
                bad.append(f"{category} · {name}  →  {url}")
                bad_count += 1
    print(f"\n\nИтого: {ok_count} живых, {bad_count} мёртвых")
    if bad:
        print("\nМёртвые — выкинь из SOURCES в bot.py или замени URL:")
        for b in bad:
            print(f"  {b}")


# ---------- Основной прогон ----------
def main():
    token         = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id       = os.environ["TELEGRAM_CHAT_ID"]
    anthropic_key = os.environ["ANTHROPIC_API_KEY"]

    client = anthropic.Anthropic(api_key=anthropic_key)

    # Рубрики на сегодня по МСК
    msk = datetime.now(timezone(timedelta(hours=3)))
    weekday = msk.weekday()
    today_categories = DAILY_CATEGORIES[weekday]
    print(f"Сегодня {msk.strftime('%A %d.%m')}, рубрики: {', '.join(today_categories)}")

    state = load_state()
    sent_ids = set(state["sent"])
    is_first_run = not state.get("initialized")

    now = time.time()
    max_age = MAX_AGE_HOURS * 3600
    candidates = []

    for category in today_categories:
        sources = SOURCES.get(category, [])
        for source_name, feed_url in sources:
            try:
                feed = feedparser.parse(feed_url, request_headers={"User-Agent": USER_AGENT})
                if not feed.entries:
                    continue
                for entry in feed.entries[:8]:
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
                        "title":    entry.get("title", "Без заголовка"),
                        "link":     entry.get("link", ""),
                        "image":    extract_image(entry),
                        "summary":  re.sub(r"<[^>]+>", " ", summary)[:2000],
                        "ts":       pub_ts,
                    })
            except Exception as e:
                print(f"  ошибка {source_name}: {e}")

    if is_first_run:
        for item in candidates:
            state["sent"].append(item["id"])
        state["initialized"] = True
        save_state(state)
        print(f"Первый запуск: записано {len(candidates)} ID, без постинга.")
        return

    candidates.sort(key=lambda x: x["ts"], reverse=True)
    print(f"Кандидатов: {len(candidates)}")

    posted = 0
    for item in candidates:
        if posted >= POSTS_PER_DAY:
            break
        print(f"\n→ {item['source']}: {item['title'][:60]}")

        # Достаём полный текст если summary куцый
        content = item["summary"]
        if len(content) < 400 and item["link"]:
            print("    подтягиваю полный текст...")
            content = fetch_full_text(item["link"], fallback=content) or content

        # Картинка: пробуем из RSS, иначе og:image
        image = item["image"]
        if not image and item["link"]:
            image = fetch_og_image(item["link"])

        # Пересказ через Claude
        try:
            parsed = rewrite_with_claude(
                client, item["title"], content, item["source"], item["link"]
            )
        except Exception as e:
            print(f"    не удалось пересказать: {e}")
            continue

        text = format_post(item["category"], item["source"], parsed)

        ok = post_to_telegram(token, chat_id, text, item["link"], image)
        if ok:
            state["sent"].append(item["id"])
            posted += 1
            print(f"    ✓ опубликовано")
        else:
            print(f"    ✗ ошибка отправки")

        time.sleep(SLEEP_BETWEEN_POSTS)

    save_state(state)
    print(f"\nГотово. Опубликовано: {posted}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        check_feeds()
    else:
        main()
