# 🚜 ArenaSpetsTeh.RF Telegram Bot

> 🌐 English version below — Русская версия ниже

Bilingual Telegram bot for renting and selling special equipment. Integrates with Google Sheets as a database, features real-time dynamic translation for international users, and uses a Cloudflare Worker as a stable proxy for the Telegram API.

## 📋 Table of Contents

- [Demo](#demo)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Installation](#installation)
- [Run](#run)
- [Project Structure](#project-structure)
- [How It Works](#how-it-works)
- [License](#license)

<a id="demo"></a>
## 🎬 Demo

| Start | Welcome & Menu | Categories | Equipment Type |
|:---:|:---:|:---:|:---:|
| ![Start](images/screenshot1.png) | ![Menu](images/Screenshot1ENG.png) | ![Categories](images/Screenshot2ENG.png) | ![Equipment Type](images/Screenshot3ENG.png) |

| Listing Card | Card | Latest & Search | Filter Menu |
|:---:|:---:|:---:|:---:|
| ![Listing List](images/Screenshot4ENG.png) | ![Card](images/Screenshot5ENG.png) | ![Latest & Search](images/Screenshot6ENG.png) | ![Filter Menu](images/Screenshot7ENG.png) |

| Filter Region | Filter Results | Add: Rent/Sale (New card) | Add: Equipment Type |
|:---:|:---:|:---:|:---:|
| ![Filter Region](images/Screenshot8ENG.png) | ![Filter Results](images/Screenshot9ENG.png) | ![Add: Rent/Sale (New card)](images/Screenshot10ENG.png) | ![Add: Equipment Type](images/Screenshot11ENG.png) |

| Add: Name | Add: Brand, Year & Condition | Add: Specs & Docs | Add: Region, Delivery & Price |
|:---:|:---:|:---:|:---:|
| ![Add: Name](images/Screenshot12ENG.png) | ![Add: Brand, Year & Condition](images/Screenshot13ENG.png) | ![Add: Specs & Docs](images/Screenshot14ENG.png) | ![Add: Region, Delivery & Price](images/Screenshot15ENG.png) |

| Add: Upload Photo & Confirmation | Add: Success & Latest(1) | Latest(2) & Help |
|:---:|:---:|:---:|
| ![Add: Upload Photo & Confirmation](images/Screenshot16ENG.png) | ![Add: Success & Latest(1) ](images/Screenshot17ENG.png) | ![Latest(2) & Help](images/Screenshot18ENG.png) |

| Sheet1 | Sheet2 | 
|:---:|:---:|
| ![Sheet1](images/Screenshot19ENG.png) | ![Sheet2](images/Screenshot20ENG.png) |
<a id="features"></a>
## ✨ Features

- **Bilingual interface (RU/EN)** — switch language at any time via `/lang`. The bot asks for language preference on the very first `/start`.
- **Dynamic Content Translation** — Data in Google Sheets can be stored in Russian or English. The bot translates listing titles, specs, and regions on the fly using an internal Google Translate endpoint.
- **Index-Based Google Sheets Integration** — The bot reads data by column indices (A, B, C...). You can rename the column headers to anything (or delete them) without breaking the bot.
- **Smart Search & Filter** — The search and filter algorithms check both the original query and its translated version. Searching for "USA" will find listings with "США" and vice versa.
- **Step-by-Step Wizard** — A user-friendly `/new` command to add new listings directly from Telegram with strict input validation.
- **Fault Tolerance** — Multi-layer retry, local backup for failed Google Sheets writes, and automatic recovery on startup.
- **Cloudflare Worker Proxy** — Stable access to the Telegram API bypassing regional restrictions without a local SOCKS proxy.

<a id="tech-stack"></a>
## 🛠️ Tech Stack
<div align="center">

| Component | Purpose |
|-----------|---------|
| Python 3.10+ | Development language |
| pyTelegramBotAPI (telebot) | Telegram Bot API wrapper |
| gspread + oauth2client | Google Sheets integration |
| requests | Dynamic translation API calls |
| python-dotenv | Load variables from `.env` |
| Flask | Lightweight web server for health checks |
| Cloudflare Workers | Telegram API proxy |

</div>

<a id="installation"></a>
## 🚀 Installation

### 1. Clone the repository

```bash
git clone <YOUR_REPO_URL>
cd arena-spetsteh-bot
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

Windows:
```cmd
venv\Scripts\activate
```

Linux / macOS:
```bash
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure `.env`

Copy `.env.example` to `.env`:
```cmd
copy .env.example .env
```
Open `.env` and fill in your values (Bot Token, Spreadsheet ID, Sheet Name, Worker URL).

### 5. Place `arena_creds.json`

Download the Google Service Account key from Google Cloud Console and place it in the project root next to `main.py`. 
*(This file is strictly ignored in `.gitignore` and must never be committed!)*

### 6. Set up Cloudflare Worker

Deploy your Cloudflare Worker. Put the Worker URL in `.env` as `WORKER_URL`.

<a id="run"></a>
## ▶️ Run

```bash
python main.py
```

Expected output:

```text
🌐 Using Cloudflare Worker: https://your-worker.workers.dev
🔗 API URL: https://your-worker.workers.dev/bot{0}/{1}
✅ Connected to Google Sheets
Bot is running. Waiting for updates...
```

<a id="project-structure"></a>
## 📁 Project Structure

```text
arena-spetsteh-bot/
├── images/                  # Screenshots used in this README
├── .env.example             # Variables template
├── .gitignore               # Git exclusions (protects secrets)
├── LICENSE                  # MIT License
├── README.md                # This file
├── main.py                  # Main bot code
├── requirements.txt         # Python dependencies
└── arena_creds.json         # Google Cloud credentials (ignored by Git)
```
*(Note: `.env`, `arena_creds.json`, and `advertisements_backup.json` are omitted in the repository because they are ignored by Git).*

<a id="how-it-works"></a>
## ⚙️ How It Works

### Dynamic Translation & Caching

To avoid duplicating data in Google Sheets (e.g., having separate columns for RU and EN), the bot translates text on the fly. When an English user opens a listing, the bot grabs the Russian text from the database, sends it to a hidden Google Translate endpoint, and caches the result in memory (`translation_cache`). Subsequent requests for the same word are instant. The search and filter functions also utilize this logic, checking both the original and translated query to ensure nothing is missed.

### Index-Based Google Sheets Parsing

Standard `gspread` relies on column header names. To make the database structure flexible, the bot uses `sheet.get_all_values()` and maps data strictly by index (Column A = ID, Column B = Rent/Sale, Column C = Equipment Type, etc.). This means you can rename the headers to `Name`, `Brand`, `Цена` or delete them entirely, and the bot will still read and write data perfectly.

### Bypassing Blocks via Cloudflare

Instead of an unstable local SOCKS proxy, the bot uses a Cloudflare Worker as a reverse proxy. In the code, this is just one line:

```python
telebot.apihelper.API_URL = f"{WORKER_URL}/bot{{0}}/{{1}}"
```

All requests to `api.telegram.org` are routed through your Cloudflare Worker. If the Worker URL changes, only one variable in `.env` needs to be updated.

### Fault Tolerance

The bot is designed to accept new listings even if Google Sheets temporarily fails:

**1. Retries with Delays:** If a write to Google Sheets fails (network error, quota), the bot retries **3 times with a 5-second pause**.
**2. Local Backup (`advertisements_backup.json`):** If all retries fail, the listing is saved locally so it is not lost.
**3. Automatic Recovery:** On startup, `retry_failed_ads()` reads the backup file and attempts to resend everything to Google Sheets. Successful entries are removed from the file.
**4. Auto-restart:** The main polling loop is wrapped in `try/except` with a 5-second delay before restarting. Any unhandled exception will not kill the process.

<a id="license"></a>
## 📄 License

MIT — see [LICENSE](LICENSE).

---

# 🚜 Telegram-бот «АренаСпецТех.РФ»

Двуязычный Telegram-бот для аренды и продажи спецтехники. Использует Google Таблицы в качестве базы данных, поддерживает динамический перевод в реальном времени для иностранных пользователей и использует Cloudflare Worker как стабильный прокси для Telegram API.

## 📋 Содержание

- [Демо](#демо)
- [Возможности](#возможности)
- [Технологии](#технологии)
- [Установка](#установка)
- [Запуск](#запуск)
- [Структура проекта](#структура-проекта)
- [Как это работает](#как-это-работает)
- [Лицензия](#лицензия)

<a id="демо"></a>
## 🎬 Демо

| Старт | Приветствие и Меню | Категории | Тип техники |
|:---:|:---:|:---:|:---:|
| ![Старт](images/screenshot1.png) | ![Меню](images/Screenshot1ENG.png) | ![Категории](images/Screenshot2ENG.png) | ![Тип техники](images/Screenshot3ENG.png) |

| Список объявлений | Карточка | Последние и Поиск | Меню фильтра |
|:---:|:---:|:---:|:---:|
| ![Список объявлений](images/Screenshot4ENG.png) | ![Карточка](images/Screenshot5ENG.png) | ![Последние и Поиск](images/Screenshot6ENG.png) | ![Меню фильтра](images/Screenshot7ENG.png) |

| Регион фильтра | Результаты фильтра | Добавить: Аренда/Продажа (Новая карточка) | Добавить: Тип техники |
|:---:|:---:|:---:|:---:|
| ![Регион фильтра](images/Screenshot8ENG.png) | ![Результаты фильтра](images/Screenshot9ENG.png) | ![Добавить: Аренда/Продажа (Новая карточка)](images/Screenshot10ENG.png) | ![Добавить: Тип техники](images/Screenshot11ENG.png) |

| Добавить: Название | Добавить: Марка, Год и Состояние | Добавить: Хар-ки и Документы | Добавить: Регион, Доставка и Цена |
|:---:|:---:|:---:|:---:|
| ![Добавить: Название](images/Screenshot12ENG.png) | ![Добавить: Марка, Год и Состояние](images/Screenshot13ENG.png) | ![Добавить: Хар-ки и Документы](images/Screenshot14ENG.png) | ![Добавить: Регион, Доставка и Цена](images/Screenshot15ENG.png) |

| Добавить: Загрузка фото и Подтверждение | Добавить: Успех и Последние(1) | Последние(2) и Помощь |
|:---:|:---:|:---:|
| ![Добавить: Загрузка фото и Подтверждение](images/Screenshot16ENG.png) | ![Добавить: Успех и Последние(1) ](images/Screenshot17ENG.png) | ![Последние(2) и Помощь](images/Screenshot18ENG.png) |

| Лист1 | Лист2 | 
|:---:|:---:|
| ![Лист1](images/Screenshot19ENG.png) | ![Лист2](images/Screenshot20ENG.png) |

<a id="возможности"></a>
## ✨ Возможности

- **Двуязычный интерфейс (RU/EN)** — переключение языка в любой момент через `/lang`. При первом `/start` бот просит выбрать язык.
- **Динамический перевод контента** — Данные в Google Таблицах могут храниться на русском или английском. Бот переводит названия, характеристики и регионы на лету с помощью внутреннего эндпоинта Google Translate.
- **Интеграция с Google Sheets по индексам** — Бот считывает данные по индексам колонок (A, B, C...). Вы можете переименовать шапку таблицы во что угодно (или удалить её), и бот продолжит работать.
- **Умный поиск и фильтр** — Алгоритмы поиска и фильтрации проверяют как оригинальный запрос, так и его перевод. Поиск по "USA" найдет объявления с "США" и наоборот.
- **Пошаговый мастер** — Удобная команда `/new` для добавления объявлений прямо из Telegram со строгой валидацией ввода.
- **Отказоустойчивость** — Многослойная система повторов, локальный резервный файл при сбоях записи в Google Sheets и автовосстановление при запуске.
- **Cloudflare Worker как прокси** — Стабильный доступ к Telegram API в обход региональных блокировок без использования локального SOCKS-прокси.

<a id="технологии"></a>
## 🛠️ Технологии

| Компонент | Назначение |
|-----------|-----------|
| Python 3.10+ | Язык разработки |
| pyTelegramBotAPI (telebot) | Работа с Telegram Bot API |
| gspread + oauth2client | Интеграция с Google Sheets |
| requests | Запросы к API перевода |
| python-dotenv | Загрузка переменных из `.env` |
| Flask | Легкий веб-сервер для health-check (деплой) |
| Cloudflare Workers | Прокси для Telegram API |

<a id="установка"></a>
## 🚀 Установка

### 1. Клонировать репозиторий

```bash
git clone <URL_вашего_репозитория>
cd arena-spetsteh-bot
```

### 2. Создать виртуальное окружение

```bash
python -m venv venv
```

Windows:
```cmd
venv\Scripts\activate
```

Linux / macOS:
```bash
source venv/bin/activate
```

### 3. Установить зависимости

```bash
pip install -r requirements.txt
```

### 4. Настроить `.env`

Скопируйте `.env.example` в `.env`:
```cmd
copy .env.example .env
```
Откройте `.env` и заполните значения (Токен бота, ID таблицы, Имя листа, URL воркера).

### 5. Положить `arena_creds.json`

Скачайте ключ Google Service Account из Google Cloud Console и положите его в корень проекта рядом с `main.py`. 
*(Этот файл строго добавлен в `.gitignore` и не должен попадать в репозиторий!)*

### 6. Настроить Cloudflare Worker

Разверните ваш Cloudflare Worker. URL воркера укажите в `.env` как `WORKER_URL`.

<a id="запуск"></a>
## ▶️ Запуск

```bash
python main.py
```

Ожидаемый вывод:

```text
🌐 Используем Cloudflare Worker: https://your-worker.workers.dev
🔗 API URL: https://your-worker.workers.dev/bot{0}/{1}
✅ Подключение к Google Sheets успешно
Бот запущен. Ожидание обновлений...
```

<a id="структура-проекта"></a>
## 📁 Структура проекта

```text
arena-spetsteh-bot/
├── images/                  # Скриншоты для README
├── .env.example             # Шаблон переменных
├── .gitignore               # Исключения для Git
├── LICENSE                  # MIT License
├── README.md                # Этот файл
├── main.py                  # Основной код бота
├── requirements.txt         # Зависимости Python
└── arena_creds.json         # Ключи Google (игнорируются Git)
```
*(Примечание: `.env`, `arena_creds.json` и `advertisements_backup.json` отсутствуют в репозитории, так как добавлены в `.gitignore`).*

<a id="как-это-работает"></a>
## ⚙️ Как это работает

### Динамический перевод и кэширование

Чтобы не дублировать данные в Google Таблицах (например, отдельные колонки для RU и EN), бот переводит текст на лету. Когда англоязычный пользователь открывает объявление, бот берет русский текст из базы, отправляет его на скрытый эндпоинт Google Translate и кэширует результат в памяти (`translation_cache`). Повторные запросы того же слова выполняются мгновенно. Функции поиска и фильтрации также используют эту логику, проверяя и оригинальный, и переведенный запрос.

### Чтение Google Sheets по индексам

Стандартная библиотека `gspread` полагается на названия заголовков колонок. Чтобы сделать структуру базы данных гибкой, бот использует `sheet.get_all_values()` и сопоставляет данные строго по индексам (Колонка A = ID, Колонка B = Аренда/Продажа, Колонка C = Тип техники и т.д.). Это значит, что вы можете переименовать шапку в `Name`, `Brand`, `Цена` или вовсе удалить её, и бот продолжит идеально читать и записывать данные.

### Обход блокировок через Cloudflare

Вместо нестабильного локального SOCKS-прокси бот использует Cloudflare Worker как обратный прокси. В коде это одна строка:

```python
telebot.apihelper.API_URL = f"{WORKER_URL}/bot{{0}}/{{1}}"
```

Все запросы к `api.telegram.org` идут через ваш Cloudflare Worker. Если URL воркера изменится, достаточно поправить одну переменную в `.env`.

### Отказоустойчивость

Бот спроектирован так, чтобы принимать новые объявления даже при временных сбоях Google Sheets:

**1. Повторные попытки с паузами:** Если запись в Google Sheets отклонена (сетевая ошибка, квота), бот повторяет попытку **3 раза с паузой 5 секунд**.
**2. Локальный резерв (`advertisements_backup.json`):** Если все попытки провалились, объявление сохраняется локально, чтобы не потеряться.
**3. Автоматическая отправка при старте:** При запуске `retry_failed_ads()` читает резервный файл и пытается отправить всё в Google Sheets. Успешные записи удаляются из файла.
**4. Автоперезапуск:** Основной цикл `bot.polling()` обёрнут в `try/except` с паузой 5 секунд. Любое необработанное исключение не убьет процесс — бот просто переподключится.

<a id="лицензия"></a>
## 📄 Лицензия

MIT — см. [LICENSE](LICENSE).
