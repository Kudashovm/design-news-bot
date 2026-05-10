# Telegram Design News Bot

Один пост в день, 10:00 МСК. Квадратная превью-картинка, пересказ на русском через Claude, ссылка на оригинал. Пятница — подборка дизайн-событий в Москве через KudaGo. Воскресенье — выходной.

## Расписание

| День | Рубрика |
|------|---------|
| ПН | Типографика · Брендинг · Интерфейсы · 3D |
| ВТ | Индустриальный дизайн |
| СР | Студии · Искусство · Фото |
| ЧТ | ИИ в дизайне |
| ПТ | Дизайн-события в Москве (подборка) |
| СБ | Туториалы · Ресурсы · Студии |
| ВС | Выходной |

## Структура поста

```
[Квадратная картинка 1080×1080]

Заголовок-тезис

Пересказ: 2-3 предложения

💡 Что можно вынести

Источник · Рубрика дня

#хэштеги

🔗 ссылка на оригинал
```

Пятница — подборка из 3-5 событий с описанием и ссылками.

## Источники

~40 RSS-лент: Fonts In Use, Typewolf, Type Today, ParaType, Brand New, Pentagram, Packaging of the World, Design Collector, Smashing Magazine, Codrops, Awwwards, LeManoosh, Dezeen, Designboom, Yanko Design, Core77, It's Nice That, Creative Review, Eye on Design, Hyperallergic, Colossal, Хабр, The Verge AI.

Telegram-каналы через RSSHub: @glvrdru, @ai_newz, @Vimeoinspiration, @DesignBoard, @sale_caviar.

Пятница: KudaGo API (выставки, фестивали, кино в Москве).

## Установка

### Секреты GitHub (Settings → Secrets → Actions)

| Имя | Откуда |
|-----|--------|
| `TELEGRAM_BOT_TOKEN` | @BotFather → /newbot |
| `TELEGRAM_CHAT_ID` | @username канала или числовой ID |
| `ANTHROPIC_API_KEY` | console.anthropic.com → API Keys |

### Workflows (создать через Add file → Create new file)

Файл `.github/workflows/post.yml` — основной прогон.
Файл `.github/workflows/check.yml` — проверка лент.

### Разрешения

Settings → Actions → General → Workflow permissions → **Read and write permissions**.

### Первый запуск

Actions → News bot → Run workflow. Первый раз ничего не постит, только инициализирует state.

## Настройка

В начале `bot.py`:

- `SOURCES` — источники по рубрикам
- `DAILY_CATEGORIES` — какие рубрики в какой день
- `DAY_HASHTAGS` — хэштеги по дням
- `REWRITE_PROMPT` / `FRIDAY_PROMPT` — промпты для Claude
- `IMAGE_SIZE` — размер квадрата (сейчас 1080)
- `CLAUDE_MODEL` — модель (сейчас claude-haiku-4-5)

Время — в `.github/workflows/post.yml`, cron `'0 7 * * *'` = 07:00 UTC = 10:00 МСК.

## Стоимость

~$0.10/мес (1 пост/день на Haiku 4.5). GitHub Actions и Telegram бесплатны.
