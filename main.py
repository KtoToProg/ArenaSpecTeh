import telebot
from telebot import types
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import time
import json
import os
import re
import requests
from threading import Thread
from flask import Flask
from dotenv import load_dotenv

load_dotenv()

WORKER_URL = os.environ.get('WORKER_URL')
if not WORKER_URL:
    raise RuntimeError("WORKER_URL не найден в .env")


telebot.apihelper.API_URL = WORKER_URL + '/bot{0}/{1}'
telebot.apihelper.FILE_URL = WORKER_URL + '/file/bot{0}/{1}'

telebot.apihelper.CONNECT_TIMEOUT = 15
telebot.apihelper.READ_TIMEOUT = 30

TOKEN = os.environ.get('BOT_TOKEN')
if not TOKEN:
    raise RuntimeError(
        "BOT_TOKEN не найден. Создай файл .env рядом с main.py со строкой:\n"
        "BOT_TOKEN=твой_токен_из_BotFather"
    )

SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID')
if not SPREADSHEET_ID:
    raise RuntimeError("SPREADSHEET_ID не найден в .env")
    
SHEET_NAME = os.environ.get('SHEET_NAME', 'Лист1')
BACKUP_FILE = 'advertisements_backup.json'

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name('arena_creds.json', scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

log_sheet = None
try:
    log_sheet = client.open_by_key(SPREADSHEET_ID).worksheet('Логи')
except gspread.exceptions.WorksheetNotFound:
    log_sheet = client.open_by_key(SPREADSHEET_ID).add_worksheet(title='Логи', rows=1000, cols=5)
    log_sheet.append_row(['Дата', 'user_id', 'username', 'Команда', 'Параметры'])

bot = telebot.TeleBot(TOKEN)


user_lang = {}

TEXTS = {
    'ru': {
        'welcome': (
            "Добро пожаловать в бот «АренаСпецТех.РФ»!\n\n"
            "Я помогу вам найти спецтехнику и транспорт в аренду, лизинг или на продажу.\n\n"
            "На платформе представлены объявления по следующим категориям:\n"
            "• Наземная техника (колёсная, гусеничная, рельсовая, стационарная)\n"
            "• Водная техника (баржи, паромы, рыболовецкие суда, малые суда)\n"
            "• Воздушная, подводная и космическая техника\n\n"
            "На сайте пока нет актуальных объявлений. Только тестовые.\n\n"
            "Есть бесплатное размещение объявлений!\n\n"
            "Доступные команды:\n"
            "/categories — посмотреть категории\n"
            "/latest — свежие объявления\n"
            "/search [запрос] — поиск\n"
            "/filter — интерактивный фильтр по цене, году, региону\n"
            "/new — добавить своё объявление\n"
            "/help — помощь\n"
            "/lang — сменить язык / change language"
        ),
        'help': (
            "Справка по использованию бота:\n\n"
            "/start — главное меню\n"
            "/categories — выбор категорий (аренда/продажа, затем тип техники)\n"
            "/latest — последние 10 объявлений\n"
            "/search [текст] — поиск по названию или марке\n"
            "/filter — интерактивный фильтр: выберите параметр (цена, год, регион), введите значение, затем примените или добавьте ещё фильтры.\n"
            "/new — создать своё объявление (пошаговый мастер)\n"
            "/lang — сменить язык интерфейса (RU/EN)\n\n"
            "В каждом списке объявлений можно нажать на кнопку с номером, чтобы увидеть детали."
        ),
        'choose_ad_type': "Выберите тип объявлений:",
        'no_listings': "Объявлений пока нет.",
        'no_listings_short': "Нет объявлений.",
        'latest_title': "📌 Свежие объявления",
        'search_empty_prompt': "Введите запрос после команды, например: /search экскаватор",
        'search_nothing': "По запросу «{query}» ничего не найдено.",
        'search_title': "🔍 Результаты поиска: {query}",
        'nothing_found_filters': "По вашим фильтрам ничего не найдено.",
        'filter_title': "🔎 Отфильтрованные объявления",
        'filter_prompt': "Выберите параметр для фильтрации. После добавления всех условий нажмите «Применить».",
        'filter_price_prompt': "Введите минимальную и максимальную цену через пробел (например: 1000 5000):",
        'filter_year_prompt': "Введите год выпуска (например: 2020):",
        'filter_region_prompt': "Введите регион (например: Москва):",
        'filter_price_set': "✅ Цена от {min} до {max} установлена.",
        'filter_price_bad': "❌ Некорректный ввод. Введите два числа через пробел (например: 1000 5000).",
        'filter_year_set': "✅ Год выпуска установлен: {year}",
        'filter_year_bad': "❌ Введите год числом (например: 2020).",
        'filter_region_set': "✅ Регион установлен: {region}",
        'filter_current': "Текущие фильтры: {filters}\nВыберите действие:",
        'filter_reset_done': "Все фильтры сброшены. Вы можете добавить новые.",
        'filter_no_active': "Нет активного фильтра.",
        'filter_cancelled': "Фильтр отменён.",
        'new_start': "Начнём создание объявления.\nВыберите тип:",
        'choose_equipment_type': "Выберите тип техники:",
        'enter_title': "Введите название техники (например: Экскаватор):",
        'enter_brand': "Введите марку техники (например: CAT):",
        'enter_year': "Введите год выпуска (число от 1900 до текущего):",
        'choose_condition': "Выберите состояние техники:",
        'enter_specs': "Введите технические характеристики (минимум 5 символов):",
        'choose_docs': "Наличие документов:",
        'enter_region': "Введите регион (только буквы, минимум 3 символа):",
        'enter_delivery': "Введите условия доставки (только буквы, минимум 3 символа):",
        'enter_price': "Введите цену в рублях (только число):",
        'enter_photo': "Загрузите фото (прикрепите файл) или введите ссылку (или /skip):",
        'preview_header': "📋 Проверьте данные объявления:\n\n",
        'ad_created': "✅ Ваше объявление успешно добавлено!",
        'ad_backed_up': "⚠️ Ваше объявление сохранено, но произошла техническая задержка. Оно будет добавлено автоматически в ближайшее время.",
        'ad_cancelled': "Создание объявления отменено.",
        'ad_cancelled_hint': "Вы можете начать заново командой /new",
        'ad_start_error': "Ошибка. Начните заново /new",
        'ad_unknown_step': "Ошибка: неизвестный шаг. Начните заново /new",
        'ad_something_wrong': "Что-то пошло не так. Начните заново командой /new",
        'ad_use_buttons_state': "Используйте кнопки для выбора состояния.",
        'ad_use_buttons_docs': "Используйте кнопки для выбора наличия документов.",
        'ad_use_buttons_confirm': "Используйте кнопки для подтверждения или отмены.",
        'ad_follow_instructions': "Пожалуйста, следуйте инструкциям. Сейчас ожидается ввод текста или выбор кнопок.",
        'ad_enter_nonempty': "Пожалуйста, введите непустое значение.",
        'ad_title_short': "❌ Название должно содержать минимум 2 символа.",
        'ad_brand_short': "❌ Марка должна содержать минимум 2 символа.",
        'ad_year_bad': "❌ Введите год числом от 1900 до {current}.",
        'ad_specs_short': "❌ Характеристики должны содержать минимум 5 символов.",
        'ad_specs_bad_chars': "❌ Разрешены только буквы, цифры, пробелы, запятые, точки и дефисы.",
        'ad_region_short': "❌ Регион должен содержать минимум 3 символа.",
        'ad_region_bad_chars': "❌ Разрешены только буквы, пробелы и дефисы.",
        'ad_delivery_short': "❌ Условия доставки должны содержать минимум 3 символа.",
        'ad_delivery_bad_chars': "❌ Разрешены только буквы, пробелы, запятые, точки и дефисы.",
        'ad_price_bad': "❌ Введите корректную цену (положительное число, например: 1500000.50)",
        'ad_photo_bad_link': "❌ Это не похоже на ссылку. Введите ссылку, начиная с http:// или https://, либо отправьте фото файлом, либо введите /skip для пропуска.",
        'ad_missing_fields': "Заполните все поля: {fields}",
        'ad_data_lost': "Ошибка: данные утеряны. Начните заново /new",
        'lbl_brand': "Марка",
        'lbl_year': "Год выпуска",
        'lbl_condition': "Состояние",
        'lbl_type': "Тип техники",
        'lbl_rent_or_sale': "Аренда или продажа",
        'lbl_specs': "Характеристики",
        'lbl_docs': "Документы",
        'lbl_region': "Регион",
        'lbl_delivery': "Условия доставки",
        'lbl_price': "Цена",
        'lbl_photo': "Фото",
        'price_currency': "руб.",
        'no_name': "Без названия",
        'dash': "—",
        'page_of': "стр. {page}/{total}",
        'btn_back': "⬅️ Назад",
        'btn_forward': "Вперёд ➡️",
        'btn_main_menu': "🏠 В главное меню",
        'btn_back_list': "🔙 Назад к списку",
        'btn_view_site': "🌐 Смотреть на сайте",
        'btn_cancel': "❌ Отменить",
        'btn_confirm': "✅ Подтвердить",
        'btn_back_short': "🔙 Назад",
        'btn_rent': "🚜 Аренда",
        'btn_sale': "💰 Продажа",
        'btn_sub_ground': "Наземная техника",
        'btn_sub_water': "Водная техника",
        'btn_sub_air': "Воздушная/подводная/космическая",
        'btn_cond_new': "🆕 Новое",
        'btn_cond_used': "🔄 Б/У",
        'btn_cond_push': "💪 Толкнуть, поедет",
        'btn_docs_yes': "✅ Есть",
        'btn_docs_no': "❌ Отсутствуют",
        'btn_filter_price': "💰 Цена",
        'btn_filter_year': "📅 Год",
        'btn_filter_region': "📍 Регион",
        'btn_filter_apply': "✅ Применить",
        'btn_filter_reset': "❌ Сбросить",
        'btn_filter_cancel': "❌ Отмена",
        'list_outdated': "Список устарел, воспользуйтесь /categories",
        'data_outdated': "Данные устарели, попробуйте заново.",
        'listing_not_found': "Объявление не найдено.",
        'no_listings_in_cat': "В этой категории пока нет объявлений.",
        'unknown_command': "Неизвестная команда",
        'lang_choose': "Выберите язык интерфейса / Choose interface language:",
        'lang_set': "✅ Язык изменён на русский.",
        'lang_flag_ru': "🇷🇺 Русский",
        'lang_flag_en': "🇬🇧 English",
        'category_rent': "Аренда",
        'category_sale': "Продажа",
        'cat_title': "{category} — {sub}",
        'web_ok': "Бот работает!",
        'bot_started': "Бот успешно запущен!",
    },
    'en': {
        'welcome': (
            "Welcome to the ArenaSpetsTeh.RF bot!\n\n"
            "I will help you find special equipment and vehicles for rent, leasing, or sale.\n\n"
            "The platform offers listings in the following categories:\n"
            "• Ground equipment (wheeled, tracked, rail, stationary)\n"
            "• Water equipment (barges, ferries, fishing vessels, small boats)\n"
            "• Air, underwater and space equipment\n\n"
            "There are no current listings yet — only test ones.\n\n"
            "Free listing placement is available!\n\n"
            "Available commands:\n"
            "/categories — browse categories\n"
            "/latest — latest listings\n"
            "/search [query] — search\n"
            "/filter — interactive filter by price, year, region\n"
            "/new — add your own listing\n"
            "/help — help\n"
            "/lang — change language / сменить язык"
        ),
        'help': (
            "Bot usage help:\n\n"
            "/start — main menu\n"
            "/categories — choose categories (rent/sale, then equipment type)\n"
            "/latest — last 10 listings\n"
            "/search [text] — search by name or brand\n"
            "/filter — interactive filter: choose a parameter (price, year, region), enter a value, then apply.\n"
            "/new — create your own listing (step-by-step wizard)\n"
            "/lang — change interface language (RU/EN)\n\n"
            "In each listing list, you can tap a numbered button to see details."
        ),
        'choose_ad_type': "Choose listing type:",
        'no_listings': "No listings yet.",
        'no_listings_short': "No listings.",
        'latest_title': "📌 Latest listings",
        'search_empty_prompt': "Enter a query after the command, e.g.: /search excavator",
        'search_nothing': "Nothing found for «{query}».",
        'search_title': "🔍 Search results: {query}",
        'nothing_found_filters': "Nothing found for your filters.",
        'filter_title': "🔎 Filtered listings",
        'filter_prompt': "Choose a parameter to filter by. After adding all conditions, press \"Apply\".",
        'filter_price_prompt': "Enter minimum and maximum price separated by a space (e.g.: 1000 5000):",
        'filter_year_prompt': "Enter the year of manufacture (e.g.: 2020):",
        'filter_region_prompt': "Enter the region (e.g.: Moscow):",
        'filter_price_set': "✅ Price from {min} to {max} set.",
        'filter_price_bad': "❌ Invalid input. Enter two numbers separated by a space (e.g.: 1000 5000).",
        'filter_year_set': "✅ Year set: {year}",
        'filter_year_bad': "❌ Enter the year as a number (e.g.: 2020).",
        'filter_region_set': "✅ Region set: {region}",
        'filter_current': "Current filters: {filters}\nChoose an action:",
        'filter_reset_done': "All filters have been reset. You can add new ones.",
        'filter_no_active': "No active filter.",
        'filter_cancelled': "Filter cancelled.",
        'new_start': "Let's create a listing.\nChoose the type:",
        'choose_equipment_type': "Choose the equipment type:",
        'enter_title': "Enter the equipment name (e.g.: Excavator):",
        'enter_brand': "Enter the equipment brand (e.g.: CAT):",
        'enter_year': "Enter the year of manufacture (a number from 1900 to the current year):",
        'choose_condition': "Choose the equipment condition:",
        'enter_specs': "Enter technical specifications (at least 5 characters):",
        'choose_docs': "Documents available:",
        'enter_region': "Enter the region (letters only, at least 3 characters):",
        'enter_delivery': "Enter delivery terms (letters only, at least 3 characters):",
        'enter_price': "Enter the price in rubles (number only):",
        'enter_photo': "Upload a photo (attach a file) or enter a URL (or /skip):",
        'preview_header': "📋 Check the listing data:\n\n",
        'ad_created': "✅ Your listing has been successfully added!",
        'ad_backed_up': "⚠️ Your listing has been saved, but a technical delay occurred. It will be added automatically shortly.",
        'ad_cancelled': "Listing creation cancelled.",
        'ad_cancelled_hint': "You can start over with the /new command",
        'ad_start_error': "Error. Start over with /new",
        'ad_unknown_step': "Error: unknown step. Start over with /new",
        'ad_something_wrong': "Something went wrong. Start over with the /new command",
        'ad_use_buttons_state': "Please use the buttons to choose the condition.",
        'ad_use_buttons_docs': "Please use the buttons to choose documents availability.",
        'ad_use_buttons_confirm': "Please use the buttons to confirm or cancel.",
        'ad_follow_instructions': "Please follow the instructions. Text input or button selection is expected now.",
        'ad_enter_nonempty': "Please enter a non-empty value.",
        'ad_title_short': "❌ Name must contain at least 2 characters.",
        'ad_brand_short': "❌ Brand must contain at least 2 characters.",
        'ad_year_bad': "❌ Enter the year as a number from 1900 to {current}.",
        'ad_specs_short': "❌ Specifications must contain at least 5 characters.",
        'ad_specs_bad_chars': "❌ Only letters, digits, spaces, commas, periods and hyphens are allowed.",
        'ad_region_short': "❌ Region must contain at least 3 characters.",
        'ad_region_bad_chars': "❌ Only letters, spaces and hyphens are allowed.",
        'ad_delivery_short': "❌ Delivery terms must contain at least 3 characters.",
        'ad_delivery_bad_chars': "❌ Only letters, spaces, commas, periods and hyphens are allowed.",
        'ad_price_bad': "❌ Enter a valid price (a positive number, e.g.: 1500000.50)",
        'ad_photo_bad_link': "❌ This does not look like a link. Enter a link starting with http:// or https://, send a photo as a file, or type /skip to skip.",
        'ad_missing_fields': "Fill in all fields: {fields}",
        'ad_data_lost': "Error: data lost. Start over with /new",
        'lbl_brand': "Brand",
        'lbl_year': "Year",
        'lbl_condition': "Condition",
        'lbl_type': "Equipment type",
        'lbl_rent_or_sale': "Rent or sale",
        'lbl_specs': "Specifications",
        'lbl_docs': "Documents",
        'lbl_region': "Region",
        'lbl_delivery': "Delivery terms",
        'lbl_price': "Price",
        'lbl_photo': "Photo",
        'price_currency': "RUB",
        'no_name': "Untitled",
        'dash': "—",
        'page_of': "page {page}/{total}",
        'btn_back': "⬅️ Back",
        'btn_forward': "Next ➡️",
        'btn_main_menu': "🏠 Main menu",
        'btn_back_list': "🔙 Back to list",
        'btn_view_site': "🌐 View on website",
        'btn_cancel': "❌ Cancel",
        'btn_confirm': "✅ Confirm",
        'btn_back_short': "🔙 Back",
        'btn_rent': "🚜 Rent",
        'btn_sale': "💰 Sale",
        'btn_sub_ground': "Ground equipment",
        'btn_sub_water': "Water equipment",
        'btn_sub_air': "Air / underwater / space",
        'btn_cond_new': "🆕 New",
        'btn_cond_used': "🔄 Used",
        'btn_cond_push': "💪 Runs after a push",
        'btn_docs_yes': "✅ Available",
        'btn_docs_no': "❌ Not available",
        'btn_filter_price': "💰 Price",
        'btn_filter_year': "📅 Year",
        'btn_filter_region': "📍 Region",
        'btn_filter_apply': "✅ Apply",
        'btn_filter_reset': "❌ Reset",
        'btn_filter_cancel': "❌ Cancel",
        'list_outdated': "The list is outdated, please use /categories",
        'data_outdated': "Data outdated, please try again.",
        'listing_not_found': "Listing not found.",
        'no_listings_in_cat': "There are no listings in this category yet.",
        'unknown_command': "Unknown command",
        'lang_choose': "Choose interface language / Выберите язык интерфейса:",
        'lang_set': "✅ Language changed to English.",
        'lang_flag_ru': "🇷🇺 Русский",
        'lang_flag_en': "🇬🇧 English",
        'category_rent': "Rent",
        'category_sale': "Sale",
        'cat_title': "{category} — {sub}",
        'web_ok': "Bot is running!",
        'bot_started': "Bot started successfully!",
    }
}

DATA_VALUES_BIDIRECTIONAL = {
    'аренда': {'ru': 'Аренда', 'en': 'Rent'},
    'rent': {'ru': 'Аренда', 'en': 'Rent'},
    'продажа': {'ru': 'Продажа', 'en': 'Sale'},
    'sale': {'ru': 'Продажа', 'en': 'Sale'},
    'наземная техника': {'ru': 'Наземная техника', 'en': 'Ground equipment'},
    'ground equipment': {'ru': 'Наземная техника', 'en': 'Ground equipment'},
    'водная техника': {'ru': 'Водная техника', 'en': 'Water equipment'},
    'water equipment': {'ru': 'Водная техника', 'en': 'Water equipment'},
    'воздушная, подводная, космическая': {'ru': 'Воздушная, подводная, космическая', 'en': 'Air / underwater / space'},
    'air / underwater / space': {'ru': 'Воздушная, подводная, космическая', 'en': 'Air / underwater / space'},
    'новое': {'ru': 'Новое', 'en': 'New'},
    'new': {'ru': 'Новое', 'en': 'New'},
    'б/у': {'ru': 'Б/У', 'en': 'Used'},
    'used': {'ru': 'Б/У', 'en': 'Used'},
    'толкнуть, поедет': {'ru': 'Толкнуть, поедет', 'en': 'Runs after a push'},
    'runs after a push': {'ru': 'Толкнуть, поедет', 'en': 'Runs after a push'},
    'есть': {'ru': 'Есть', 'en': 'Available'},
    'available': {'ru': 'Есть', 'en': 'Available'},
    'отсутствуют': {'ru': 'Отсутствуют', 'en': 'Not available'},
    'not available': {'ru': 'Отсутствуют', 'en': 'Not available'},
}




def t(chat_id, key, **kwargs):
    lang = user_lang.get(chat_id, 'ru')
    text = TEXTS.get(lang, TEXTS['ru']).get(key)
    if text is None:
        text = TEXTS['ru'].get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text


def dv(chat_id, value):
    if value is None or value == '':
        return t(chat_id, 'dash')
    lang = user_lang.get(chat_id, 'ru')
    val_lower = str(value).strip().lower()
    if val_lower in DATA_VALUES_BIDIRECTIONAL:
        return DATA_VALUES_BIDIRECTIONAL[val_lower][lang]
    return value




translation_cache = {}


def translate_text(text, target_lang='en'):
    if not text:
        return text

    has_cyrillic = any('\u0400' <= c <= '\u04FF' for c in text)
    if target_lang == 'en' and not has_cyrillic:
        return text
    if target_lang == 'ru' and has_cyrillic:
        return text

    cache_key = f"{target_lang}:{text}"
    if cache_key in translation_cache:
        return translation_cache[cache_key]

    url = "https://clients5.google.com/translate_a/t"
    params = {
        "client": "dict-chrome-ex",
        "sl": "auto",
        "tl": target_lang,
        "q": text
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if isinstance(data, list) and len(data) > 0:
            if isinstance(data[0], list):
                translated = data[0][0]
            else:
                translated = data[0]
        else:
            translated = text

        translation_cache[cache_key] = translated
        return translated
    except Exception as e:
        print(f"⚠️ Ошибка перевода: {e}")
        return text





def get_lang_kb():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🇷🇺 Русский", callback_data='set_lang_ru'),
        types.InlineKeyboardButton("🇬🇧 English", callback_data='set_lang_en'),
    )
    return kb



def save_ad_to_backup(ad_data):
    ads = []
    if os.path.exists(BACKUP_FILE):
        try:
            with open(BACKUP_FILE, 'r', encoding='utf-8') as f:
                ads = json.load(f)
        except (json.JSONDecodeError, IOError):
            ads = []
    ads.append(ad_data)
    with open(BACKUP_FILE, 'w', encoding='utf-8') as f:
        json.dump(ads, f, ensure_ascii=False, indent=2)
    print(f"📦 Объявление '{ad_data['Название']}' сохранено в резервный файл")


def retry_failed_ads():
    if not os.path.exists(BACKUP_FILE):
        return
    try:
        with open(BACKUP_FILE, 'r', encoding='utf-8') as f:
            ads = json.load(f)
    except (json.JSONDecodeError, IOError):
        return
    if not ads:
        return
    print(f"📦 Найдено {len(ads)} неотправленных объявлений. Пытаемся отправить...")
    remaining = []
    for idx, ad in enumerate(ads, 1):
        print(f"⏳ Обработка объявления #{idx}...")
        success = write_ad_to_sheet(ad, max_retries=2, delay=3)
        if success:
            print(f"✅ Резервное объявление #{idx} отправлено")
        else:
            print(f"❌ Резервное объявление #{idx} не удалось отправить, оставляем в резерве")
            remaining.append(ad)
    if remaining:
        with open(BACKUP_FILE, 'w', encoding='utf-8') as f:
            json.dump(remaining, f, ensure_ascii=False, indent=2)
        print(f"⚠️ {len(remaining)} объявлений остались в резервном файле")
    else:
        if os.path.exists(BACKUP_FILE):
            os.remove(BACKUP_FILE)
            print("🗑️ Резервный файл очищен (все объявления отправлены)")


def write_ad_to_sheet(ad_data, max_retries=3, delay=5):
    all_records = get_all_listings()
    max_id = 0
    for row in all_records:
        try:
            row_id = int(row.get('ID', 0))
            if row_id > max_id:
                max_id = row_id
        except Exception:
            pass
    new_id = max_id + 1

    row = [
        new_id,
        ad_data.get('Аренда или продажа', ''),
        ad_data.get('Тип техники', ''),
        ad_data.get('Название', ''),
        ad_data.get('Марка', ''),
        ad_data.get('Год выпуска', ''),
        ad_data.get('Состояние', ''),
        ad_data.get('Технические характеристики', ''),
        ad_data.get('Наличие документов', ''),
        ad_data.get('Регион', ''),
        ad_data.get('Условия доставки', ''),
        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        ad_data.get('Цена', ''),
        ad_data.get('Фото_URL', '')
    ]

    for attempt in range(1, max_retries + 1):
        try:
            sheet.append_row(row)
            print(f"✅ Объявление '{ad_data['Название']}' записано в таблицу (попытка {attempt})")
            return True
        except Exception as e:
            print(f"⚠️ Попытка {attempt} записи не удалась: {e}")
            if attempt < max_retries:
                time.sleep(delay)
    return False




def get_all_listings():
    all_values = sheet.get_all_values()
    if not all_values or len(all_values) <= 1:
        return []

    listings = []
    for row in all_values[1:]:
        if not any(row):
            continue

        item = {
            'ID': row[0] if len(row) > 0 else '',
            'Аренда или продажа': row[1] if len(row) > 1 else '',
            'Тип техники': row[2] if len(row) > 2 else '',
            'Название': row[3] if len(row) > 3 else '',
            'Марка': row[4] if len(row) > 4 else '',
            'Год выпуска': row[5] if len(row) > 5 else '',
            'Состояние': row[6] if len(row) > 6 else '',
            'Технические характеристики': row[7] if len(row) > 7 else '',
            'Наличие документов': row[8] if len(row) > 8 else '',
            'Регион': row[9] if len(row) > 9 else '',
            'Условия доставки': row[10] if len(row) > 10 else '',
            'Время': row[11] if len(row) > 11 else '',
            'Цена': row[12] if len(row) > 12 else '',
            'Фото_URL': row[13] if len(row) > 13 else ''
        }
        listings.append(item)
    return listings




def get_listings_by_category(category_type, subcategory=None):
    all_listings = get_all_listings()
    filtered = []

    target_cat_ru = 'аренда' if category_type == 'аренда' else 'продажа'
    target_cat_en = 'rent' if target_cat_ru == 'аренда' else 'sale'

    sub_ru = subcategory.lower() if subcategory else None
    if sub_ru == 'наземная':
        sub_en = 'ground'
    elif sub_ru == 'водная':
        sub_en = 'water'
    elif sub_ru == 'воздушная':
        sub_en = 'air'
    else:
        sub_en = sub_ru

    for item in all_listings:
        item_cat = str(item.get('Аренда или продажа', '')).strip().lower()
        item_type = str(item.get('Тип техники', '')).strip().lower()

        if target_cat_ru not in item_cat and target_cat_en not in item_cat:
            continue

        if subcategory:
            if sub_ru not in item_type and sub_en not in item_type:
                continue

        filtered.append(item)
    return filtered




def get_listing_by_id(listing_id):
    all_listings = get_all_listings()
    for item in all_listings:
        if str(item.get('ID', '')).strip() == str(listing_id).strip():
            return item
    return None


def get_latest_listings(limit=10):
    all_listings = get_all_listings()
    try:
        sorted_list = sorted(all_listings, key=lambda x: x.get('Время', ''), reverse=True)
    except Exception:
        sorted_list = all_listings[::-1]
    return sorted_list[:limit]


def format_listing_text(chat_id, listing):
    d = t(chat_id, 'dash')
    lang = user_lang.get(chat_id, 'ru')

    name = listing.get('Название', t(chat_id, 'no_name'))
    brand = listing.get('Марка', d)
    year = listing.get('Год выпуска', d)
    price = listing.get('Цена')
    specs = listing.get('Технические характеристики', '')
    region = listing.get('Регион', '')
    delivery = listing.get('Условия доставки', '')

    if lang == 'en':
        name = translate_text(name, 'en')
        specs = translate_text(specs, 'en')
        region = translate_text(region, 'en')
        delivery = translate_text(delivery, 'en')
    elif lang == 'ru':
        name = translate_text(name, 'ru')
        specs = translate_text(specs, 'ru')
        region = translate_text(region, 'ru')
        delivery = translate_text(delivery, 'ru')

    text = f"🚜 *{name}*\n"
    text += f"{t(chat_id, 'lbl_brand')}: {brand}\n"
    text += f"{t(chat_id, 'lbl_year')}: {year}\n"
    text += f"{t(chat_id, 'lbl_condition')}: {dv(chat_id, listing.get('Состояние', d))}\n"
    text += f"{t(chat_id, 'lbl_type')}: {dv(chat_id, listing.get('Тип техники', d))}\n"
    text += f"{t(chat_id, 'lbl_rent_or_sale')}: {dv(chat_id, listing.get('Аренда или продажа', d))}\n"
    if specs: text += f"{t(chat_id, 'lbl_specs')}: {specs}\n"
    if listing.get(
            'Наличие документов'): text += f"{t(chat_id, 'lbl_docs')}: {dv(chat_id, listing.get('Наличие документов'))}\n"
    if region: text += f"{t(chat_id, 'lbl_region')}: {region}\n"
    if delivery: text += f"{t(chat_id, 'lbl_delivery')}: {delivery}\n"
    if price: text += f"{t(chat_id, 'lbl_price')}: {price} {t(chat_id, 'price_currency')}\n"
    return text




def log_to_sheet(command, params, user_id, username):
    if log_sheet:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_sheet.append_row([now, str(user_id), username or '', command, params])


def apply_filters(listings, filters, chat_id):
    result = listings
    if 'price_min' in filters and 'price_max' in filters:
        try:
            p_min = float(filters['price_min'])
            p_max = float(filters['price_max'])
            result = [item for item in result if
                      item.get('Цена') and p_min <= float(item.get('Цена', 0)) <= p_max]
        except Exception:
            pass
    if 'year' in filters:
        year_str = filters['year'].strip()
        if year_str.isdigit():
            year = int(year_str)
            result = [item for item in result if str(item.get('Год выпуска', '')).isdigit()
                      and int(item.get('Год выпуска', 0)) == year]
    if 'region' in filters:
        region_query_orig = filters['region'].strip().lower()
        region_query_trans = region_query_orig

        if user_lang.get(chat_id) == 'en':
            region_query_trans = translate_text(region_query_orig, 'ru').lower()
        elif user_lang.get(chat_id) == 'ru':
            region_query_trans = translate_text(region_query_orig, 'en').lower()

        result = [item for item in result if
                  region_query_orig in str(item.get('Регион', '')).lower() or
                  region_query_trans in str(item.get('Регион', '')).lower()]
    return result




def send_listings_list(chat_id, listings, title=None, page=0, per_page=5, callback_prefix='list'):
    if not listings:
        bot.send_message(chat_id, t(chat_id, 'no_listings_short'))
        return
    total = len(listings)
    total_pages = (total + per_page - 1) // per_page
    if page >= total_pages:
        page = total_pages - 1
    if page < 0:
        page = 0
    start = page * per_page
    end = min(start + per_page, total)
    page_listings = listings[start:end]

    user_pages[chat_id] = {
        'listings': listings,
        'page': page,
        'per_page': per_page,
        'total_pages': total_pages,
        'callback_prefix': callback_prefix,
        'title': title
    }

    page_info = t(chat_id, 'page_of', page=page + 1, total=total_pages)
    text = f"*{title or t(chat_id, 'latest_title')}* ({page_info})\n\n"

    lang = user_lang.get(chat_id, 'ru')
    for idx, item in enumerate(page_listings, start=start + 1):
        item_name = item.get('Название', t(chat_id, 'no_name'))
        item_name = translate_text(item_name, lang)
        text += f"{idx}. {item_name} — {item.get('Марка', '')}\n"

    markup = types.InlineKeyboardMarkup(row_width=3)
    for idx, item in enumerate(page_listings, start=start + 1):
        listing_id = item.get('ID', idx)
        markup.add(types.InlineKeyboardButton(f"{idx}", callback_data=f"{callback_prefix}_view_{listing_id}"))

    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            types.InlineKeyboardButton(t(chat_id, 'btn_back'), callback_data=f"{callback_prefix}_page_{page - 1}"))
    if page < total_pages - 1:
        nav_buttons.append(
            types.InlineKeyboardButton(t(chat_id, 'btn_forward'), callback_data=f"{callback_prefix}_page_{page + 1}"))
    if nav_buttons:
        markup.add(*nav_buttons)

    markup.add(types.InlineKeyboardButton(t(chat_id, 'btn_main_menu'), callback_data='main_menu'))
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')




user_pages = {}
user_filters = {}
user_ad_data = {}
ad_states = {}


def get_ad_state(chat_id):
    return ad_states.get(chat_id, [None])[-1] if chat_id in ad_states and ad_states[chat_id] else None


def push_ad_state(chat_id, state):
    if chat_id not in ad_states:
        ad_states[chat_id] = []
    ad_states[chat_id].append(state)


def pop_ad_state(chat_id):
    if chat_id in ad_states and len(ad_states[chat_id]) > 1:
        ad_states[chat_id].pop()
        return ad_states[chat_id][-1]
    return None


def clear_ad_state(chat_id):
    if chat_id in ad_states:
        del ad_states[chat_id]


def remove_keyboard(chat_id):
    if chat_id in user_ad_data and 'last_bot_msg_id' in user_ad_data[chat_id]:
        try:
            bot.edit_message_reply_markup(chat_id, user_ad_data[chat_id]['last_bot_msg_id'], reply_markup=None)
        except Exception:
            pass


@bot.message_handler(commands=['lang', 'language', 'язык'])
def cmd_lang(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, t(chat_id, 'lang_choose'), reply_markup=get_lang_kb())


@bot.message_handler(commands=['new'])
def start_new_ad(message):
    chat_id = message.chat.id
    user_ad_data[chat_id] = {}
    push_ad_state(chat_id, 'ad_type')
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(t(chat_id, 'btn_rent'), callback_data='ad_type_аренда'),
        types.InlineKeyboardButton(t(chat_id, 'btn_sale'), callback_data='ad_type_продажа')
    )
    markup.add(types.InlineKeyboardButton(t(chat_id, 'btn_cancel'), callback_data='ad_cancel'))
    msg = bot.send_message(chat_id, t(chat_id, 'new_start'), reply_markup=markup)
    user_ad_data[chat_id]['last_bot_msg_id'] = msg.message_id


@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    data = call.data
    chat_id = call.message.chat.id
    message_id = call.message.message_id

    if data in ('set_lang_ru', 'set_lang_en'):
        new_lang = 'ru' if data.endswith('ru') else 'en'
        user_lang[chat_id] = new_lang
        bot.edit_message_text(t(chat_id, 'lang_set'), chat_id, message_id)
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, t(chat_id, 'welcome'), parse_mode='Markdown')
        return

    if data.startswith('ad_type_'):
        ad_type = data.replace('ad_type_', '')
        user_ad_data[chat_id]['Аренда или продажа'] = dv(chat_id, ad_type)
        push_ad_state(chat_id, 'ad_sub')
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton(t(chat_id, 'btn_sub_ground'), callback_data='ad_sub_наземная'),
            types.InlineKeyboardButton(t(chat_id, 'btn_sub_water'), callback_data='ad_sub_водная'),
            types.InlineKeyboardButton(t(chat_id, 'btn_sub_air'), callback_data='ad_sub_воздушная')
        )
        markup.add(types.InlineKeyboardButton(t(chat_id, 'btn_back_short'), callback_data='ad_back'))
        markup.add(types.InlineKeyboardButton(t(chat_id, 'btn_cancel'), callback_data='ad_cancel'))
        bot.edit_message_text(t(chat_id, 'choose_equipment_type'), chat_id, message_id, reply_markup=markup)
        user_ad_data[chat_id]['last_bot_msg_id'] = message_id

    elif data.startswith('ad_sub_'):
        sub_map = {
            'наземная': 'Наземная техника',
            'водная': 'Водная техника',
            'воздушная': 'Воздушная, подводная, космическая'
        }
        sub_key = data.replace('ad_sub_', '')
        sub = sub_map.get(sub_key, sub_key)
        user_ad_data[chat_id]['Тип техники'] = dv(chat_id, sub)
        push_ad_state(chat_id, 'ad_title')

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(t(chat_id, 'btn_back_short'), callback_data='ad_back'))
        markup.add(types.InlineKeyboardButton(t(chat_id, 'btn_cancel'), callback_data='ad_cancel'))
        bot.edit_message_text(t(chat_id, 'enter_title'), chat_id, message_id, reply_markup=markup)
        user_ad_data[chat_id]['last_bot_msg_id'] = message_id

    elif data == 'ad_back':
        prev_state = pop_ad_state(chat_id)
        if prev_state is None:
            clear_ad_state(chat_id)
            if chat_id in user_ad_data:
                del user_ad_data[chat_id]
            bot.edit_message_text(t(chat_id, 'ad_cancelled'), chat_id, message_id)
            return
        try:
            bot.edit_message_reply_markup(chat_id, message_id, reply_markup=None)
        except Exception:
            pass
        show_step(chat_id)

    elif data == 'ad_cancel':
        user_ad_data.pop(chat_id, None)
        clear_ad_state(chat_id)
        bot.edit_message_text(t(chat_id, 'ad_cancelled'), chat_id, message_id)
        bot.send_message(chat_id, t(chat_id, 'ad_cancelled_hint'))

    elif data.startswith('ad_cond_'):
        condition = data.replace('ad_cond_', '')
        user_ad_data[chat_id]['Состояние'] = dv(chat_id, condition)
        push_ad_state(chat_id, 'ad_specs')
        show_step(chat_id)

    elif data.startswith('ad_docs_'):
        docs = data.replace('ad_docs_', '')
        user_ad_data[chat_id]['Наличие документов'] = dv(chat_id, docs)
        push_ad_state(chat_id, 'ad_region')
        show_step(chat_id)

    elif data == 'ad_confirm':
        ad = user_ad_data.get(chat_id)
        if not ad:
            bot.answer_callback_query(call.id, t(chat_id, 'ad_data_lost'), show_alert=True)
            return

        required_fields = ['Аренда или продажа', 'Тип техники', 'Название', 'Марка', 'Год выпуска',
                           'Состояние', 'Технические характеристики', 'Наличие документов',
                           'Регион', 'Условия доставки', 'Цена']
        missing = [f for f in required_fields if not ad.get(f, '').strip()]
        if missing:
            bot.answer_callback_query(call.id, t(chat_id, 'ad_missing_fields', fields=', '.join(missing)),
                                      show_alert=True)
            return
        success = write_ad_to_sheet(ad, max_retries=3, delay=5)
        if success:
            bot.edit_message_text(t(chat_id, 'ad_created'), chat_id, message_id)
            log_to_sheet('/new', f"Добавлено объявление: {ad['Название']}", call.from_user.id, call.from_user.username)
        else:
            save_ad_to_backup(ad)
            bot.edit_message_text(t(chat_id, 'ad_backed_up'), chat_id, message_id)
            log_to_sheet('/new', f"Объявление сохранено в резерв: {ad['Название']}", call.from_user.id,
                         call.from_user.username)
        if chat_id in user_ad_data:
            del user_ad_data[chat_id]
        clear_ad_state(chat_id)

    elif data == 'cat_rent':
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton(t(chat_id, 'btn_sub_ground'), callback_data='sub_rent_Наземная'),
            types.InlineKeyboardButton(t(chat_id, 'btn_sub_water'), callback_data='sub_rent_Водная'),
            types.InlineKeyboardButton(t(chat_id, 'btn_sub_air'), callback_data='sub_rent_Воздушная')
        )
        markup.add(types.InlineKeyboardButton(t(chat_id, 'btn_back_short'), callback_data='categories_back'))
        bot.edit_message_text(t(chat_id, 'choose_equipment_type'), chat_id, message_id, reply_markup=markup)

    elif data == 'cat_sale':
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton(t(chat_id, 'btn_sub_ground'), callback_data='sub_sale_Наземная'),
            types.InlineKeyboardButton(t(chat_id, 'btn_sub_water'), callback_data='sub_sale_Водная'),
            types.InlineKeyboardButton(t(chat_id, 'btn_sub_air'), callback_data='sub_sale_Воздушная')
        )
        markup.add(types.InlineKeyboardButton(t(chat_id, 'btn_back_short'), callback_data='categories_back'))
        bot.edit_message_text(t(chat_id, 'choose_equipment_type'), chat_id, message_id, reply_markup=markup)

    elif data == 'categories_back':
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton(t(chat_id, 'btn_rent'), callback_data='cat_rent'),
            types.InlineKeyboardButton(t(chat_id, 'btn_sale'), callback_data='cat_sale')
        )
        bot.edit_message_text(t(chat_id, 'choose_ad_type'), chat_id, message_id, reply_markup=markup)

    elif data.startswith('sub_rent_') or data.startswith('sub_sale_'):
        parts = data.split('_', 2)
        if len(parts) < 3:
            return
        type_part = parts[1]
        sub = parts[2]
        category_type = 'аренда' if type_part == 'rent' else 'продажа'
        listings = get_listings_by_category(category_type, sub)
        if not listings:
            bot.answer_callback_query(call.id, t(chat_id, 'no_listings_in_cat'), show_alert=True)
            return
        prefix = f"{type_part}_{sub}"
        cat_name = t(chat_id, 'category_rent' if type_part == 'rent' else 'category_sale')
        sub_name = dv(chat_id, sub)
        title = t(chat_id, 'cat_title', category=cat_name, sub=sub_name)
        send_listings_list(chat_id, listings, title=title, page=0, per_page=5, callback_prefix=prefix)
        log_to_sheet('/categories', f"{category_type} {sub}", call.from_user.id, call.from_user.username)

    elif '_page_' in data:
        parts = data.rsplit('_', 1)
        if len(parts) != 2 or not parts[1].isdigit():
            return
        page = int(parts[1])
        user_data = user_pages.get(chat_id)
        if not user_data:
            bot.answer_callback_query(call.id, t(chat_id, 'data_outdated'), show_alert=True)
            return
        listings = user_data['listings']
        per_page = user_data['per_page']
        total_pages = user_data['total_pages']
        prefix = user_data['callback_prefix']
        title = user_data.get('title') or t(chat_id, 'latest_title')
        if page >= total_pages:
            page = total_pages - 1
        bot.delete_message(chat_id, message_id)
        send_listings_list(chat_id, listings, title=title, page=page, per_page=per_page, callback_prefix=prefix)

    elif '_view_' in data:
        parts = data.rsplit('_', 1)
        if len(parts) != 2:
            return
        listing_id = parts[1]
        listing = get_listing_by_id(listing_id)
        if not listing:
            bot.answer_callback_query(call.id, t(chat_id, 'listing_not_found'), show_alert=True)
            return
        text = format_listing_text(chat_id, listing)
        markup = types.InlineKeyboardMarkup()
        site_url = listing.get('Ссылка_на_сайт', '')
        if not site_url:
            site_url = f"https://аренаспецтех.рф/объявление/{listing.get('ID', '')}"
        markup.add(types.InlineKeyboardButton(t(chat_id, 'btn_view_site'), url=site_url))
        markup.add(types.InlineKeyboardButton(t(chat_id, 'btn_back_list'), callback_data='back_to_list'))
        photo_url = listing.get('Фото_URL', '').strip()
        if photo_url:
            try:
                bot.send_photo(chat_id, photo_url, caption=text, reply_markup=markup, parse_mode='Markdown')
            except Exception:
                bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')
        else:
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')
        bot.delete_message(chat_id, message_id)
        log_to_sheet('/view', f"ID {listing_id}", call.from_user.id, call.from_user.username)

    elif data == 'back_to_list':
        user_data = user_pages.get(chat_id)
        if not user_data:
            bot.send_message(chat_id, t(chat_id, 'list_outdated'))
            return
        listings = user_data['listings']
        page = user_data['page']
        per_page = user_data['per_page']
        prefix = user_data['callback_prefix']
        title = user_data.get('title') or t(chat_id, 'latest_title')
        bot.delete_message(chat_id, message_id)
        send_listings_list(chat_id, listings, title=title, page=page, per_page=per_page, callback_prefix=prefix)

    elif data == 'main_menu':
        bot.delete_message(chat_id, message_id)
        fake_message = types.Message(
            message_id=message_id,
            from_user=call.from_user,
            date=int(time.time()),
            chat=call.message.chat,
            content_type='text',
            options={}
        )
        send_welcome(fake_message)

    elif data.startswith('filter_'):
        if data == 'filter_price':
            bot.edit_message_text(t(chat_id, 'filter_price_prompt'), chat_id, message_id)
            user_filters[chat_id]['step'] = 'waiting_price'
            bot.answer_callback_query(call.id)
        elif data == 'filter_year':
            bot.edit_message_text(t(chat_id, 'filter_year_prompt'), chat_id, message_id)
            user_filters[chat_id]['step'] = 'waiting_year'
            bot.answer_callback_query(call.id)
        elif data == 'filter_region':
            bot.edit_message_text(t(chat_id, 'filter_region_prompt'), chat_id, message_id)
            user_filters[chat_id]['step'] = 'waiting_region'
            bot.answer_callback_query(call.id)
        elif data == 'filter_apply':
            state = user_filters.get(chat_id)
            if not state:
                bot.answer_callback_query(call.id, t(chat_id, 'filter_no_active'), show_alert=True)
                return
            filtered = apply_filters(state['listings'], state['filters'], chat_id)
            if not filtered:
                bot.edit_message_text(t(chat_id, 'nothing_found_filters'), chat_id, message_id)
            else:
                bot.delete_message(chat_id, message_id)
                send_listings_list(chat_id, filtered, title=t(chat_id, 'filter_title'), page=0, per_page=5,
                                   callback_prefix='filter_result')
                log_to_sheet('/filter', str(state['filters']), call.from_user.id, call.from_user.username)
            del user_filters[chat_id]
            bot.answer_callback_query(call.id)
        elif data == 'filter_reset':
            if chat_id in user_filters:
                user_filters[chat_id]['filters'] = {}
                bot.edit_message_text(t(chat_id, 'filter_reset_done'), chat_id, message_id)
            else:
                bot.answer_callback_query(call.id, t(chat_id, 'filter_no_active'), show_alert=True)
        elif data == 'filter_cancel':
            if chat_id in user_filters:
                del user_filters[chat_id]
            bot.delete_message(chat_id, message_id)
            bot.send_message(chat_id, t(chat_id, 'filter_cancelled'))
            bot.answer_callback_query(call.id)
        else:
            bot.answer_callback_query(call.id, t(chat_id, 'unknown_command'))

    else:
        bot.answer_callback_query(call.id, t(chat_id, 'unknown_command'))


def show_step(chat_id):
    state = get_ad_state(chat_id)
    if state is None:
        bot.send_message(chat_id, t(chat_id, 'ad_start_error'))
        return

    remove_keyboard(chat_id)
    data = user_ad_data.get(chat_id, {})

    if state == 'ad_type':
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton(t(chat_id, 'btn_rent'), callback_data='ad_type_аренда'),
            types.InlineKeyboardButton(t(chat_id, 'btn_sale'), callback_data='ad_type_продажа')
        )
        markup.add(types.InlineKeyboardButton(t(chat_id, 'btn_cancel'), callback_data='ad_cancel'))
        msg = bot.send_message(chat_id, t(chat_id, 'choose_ad_type'), reply_markup=markup)

    elif state == 'ad_sub':
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton(t(chat_id, 'btn_sub_ground'), callback_data='ad_sub_наземная'),
            types.InlineKeyboardButton(t(chat_id, 'btn_sub_water'), callback_data='ad_sub_водная'),
            types.InlineKeyboardButton(t(chat_id, 'btn_sub_air'), callback_data='ad_sub_воздушная')
        )
        markup.add(types.InlineKeyboardButton(t(chat_id, 'btn_back_short'), callback_data='ad_back'))
        markup.add(types.InlineKeyboardButton(t(chat_id, 'btn_cancel'), callback_data='ad_cancel'))
        msg = bot.send_message(chat_id, t(chat_id, 'choose_equipment_type'), reply_markup=markup)

    elif state == 'ad_title':
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(t(chat_id, 'btn_back_short'), callback_data='ad_back'))
        markup.add(types.InlineKeyboardButton(t(chat_id, 'btn_cancel'), callback_data='ad_cancel'))
        msg = bot.send_message(chat_id, t(chat_id, 'enter_title'), reply_markup=markup)

    elif state == 'ad_brand':
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(t(chat_id, 'btn_back_short'), callback_data='ad_back'))
        markup.add(types.InlineKeyboardButton(t(chat_id, 'btn_cancel'), callback_data='ad_cancel'))
        msg = bot.send_message(chat_id, t(chat_id, 'enter_brand'), reply_markup=markup)

    elif state == 'ad_year':
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(t(chat_id, 'btn_back_short'), callback_data='ad_back'))
        markup.add(types.InlineKeyboardButton(t(chat_id, 'btn_cancel'), callback_data='ad_cancel'))
        msg = bot.send_message(chat_id, t(chat_id, 'enter_year'), reply_markup=markup)

    elif state == 'ad_condition':
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton(t(chat_id, 'btn_cond_new'), callback_data='ad_cond_Новое'),
            types.InlineKeyboardButton(t(chat_id, 'btn_cond_used'), callback_data='ad_cond_Б/У'),
            types.InlineKeyboardButton(t(chat_id, 'btn_cond_push'), callback_data='ad_cond_Толкнуть, поедет')
        )
        markup.add(types.InlineKeyboardButton(t(chat_id, 'btn_back_short'), callback_data='ad_back'))
        markup.add(types.InlineKeyboardButton(t(chat_id, 'btn_cancel'), callback_data='ad_cancel'))
        msg = bot.send_message(chat_id, t(chat_id, 'choose_condition'), reply_markup=markup)

    elif state == 'ad_specs':
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(t(chat_id, 'btn_back_short'), callback_data='ad_back'))
        markup.add(types.InlineKeyboardButton(t(chat_id, 'btn_cancel'), callback_data='ad_cancel'))
        msg = bot.send_message(chat_id, t(chat_id, 'enter_specs'), reply_markup=markup)

    elif state == 'ad_docs':
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton(t(chat_id, 'btn_docs_yes'), callback_data='ad_docs_Есть'),
            types.InlineKeyboardButton(t(chat_id, 'btn_docs_no'), callback_data='ad_docs_Отсутствуют')
        )
        markup.add(types.InlineKeyboardButton(t(chat_id, 'btn_back_short'), callback_data='ad_back'))
        markup.add(types.InlineKeyboardButton(t(chat_id, 'btn_cancel'), callback_data='ad_cancel'))
        msg = bot.send_message(chat_id, t(chat_id, 'choose_docs'), reply_markup=markup)

    elif state == 'ad_region':
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(t(chat_id, 'btn_back_short'), callback_data='ad_back'))
        markup.add(types.InlineKeyboardButton(t(chat_id, 'btn_cancel'), callback_data='ad_cancel'))
        msg = bot.send_message(chat_id, t(chat_id, 'enter_region'), reply_markup=markup)

    elif state == 'ad_delivery':
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(t(chat_id, 'btn_back_short'), callback_data='ad_back'))
        markup.add(types.InlineKeyboardButton(t(chat_id, 'btn_cancel'), callback_data='ad_cancel'))
        msg = bot.send_message(chat_id, t(chat_id, 'enter_delivery'), reply_markup=markup)

    elif state == 'ad_price':
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(t(chat_id, 'btn_back_short'), callback_data='ad_back'))
        markup.add(types.InlineKeyboardButton(t(chat_id, 'btn_cancel'), callback_data='ad_cancel'))
        msg = bot.send_message(chat_id, t(chat_id, 'enter_price'), reply_markup=markup)

    elif state == 'ad_photo':
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(t(chat_id, 'btn_back_short'), callback_data='ad_back'))
        markup.add(types.InlineKeyboardButton(t(chat_id, 'btn_cancel'), callback_data='ad_cancel'))
        msg = bot.send_message(chat_id, t(chat_id, 'enter_photo'), reply_markup=markup)

    elif state == 'ad_confirm':
        ad = user_ad_data.get(chat_id, {})
        preview = t(chat_id, 'preview_header')
        preview += f"{t(chat_id, 'lbl_rent_or_sale')}: {dv(chat_id, ad.get('Аренда или продажа', '—'))}\n"
        preview += f"{t(chat_id, 'lbl_type')}: {dv(chat_id, ad.get('Тип техники', '—'))}\n"
        preview += f"{t(chat_id, 'lbl_brand').replace('Brand', 'Name') if user_lang.get(chat_id) == 'en' else 'Название'}: {ad.get('Название', '—')}\n"
        preview += f"{t(chat_id, 'lbl_brand')}: {ad.get('Марка', '—')}\n"
        preview += f"{t(chat_id, 'lbl_year')}: {ad.get('Год выпуска', '—')}\n"
        preview += f"{t(chat_id, 'lbl_condition')}: {dv(chat_id, ad.get('Состояние', '—'))}\n"
        preview += f"{t(chat_id, 'lbl_specs')}: {ad.get('Технические характеристики', '—')}\n"
        preview += f"{t(chat_id, 'lbl_docs')}: {dv(chat_id, ad.get('Наличие документов', '—'))}\n"
        preview += f"{t(chat_id, 'lbl_region')}: {ad.get('Регион', '—')}\n"
        preview += f"{t(chat_id, 'lbl_delivery')}: {ad.get('Условия доставки', '—')}\n"
        preview += f"{t(chat_id, 'lbl_price')}: {ad.get('Цена', '—')} {t(chat_id, 'price_currency')}\n"
        photo = ad.get('Фото_URL', '') or ('—' if user_lang.get(chat_id) == 'ru' else 'not specified')
        preview += f"{t(chat_id, 'lbl_photo')}: {photo}\n"
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton(t(chat_id, 'btn_confirm'), callback_data='ad_confirm'),
            types.InlineKeyboardButton(t(chat_id, 'btn_back_short'), callback_data='ad_back'),
            types.InlineKeyboardButton(t(chat_id, 'btn_cancel'), callback_data='ad_cancel')
        )
        msg = bot.send_message(chat_id, preview, reply_markup=markup)

    else:
        msg = bot.send_message(chat_id, t(chat_id, 'ad_unknown_step'))
        clear_ad_state(chat_id)
        if chat_id in user_ad_data:
            del user_ad_data[chat_id]
        return

    user_ad_data[chat_id]['last_bot_msg_id'] = msg.message_id


@bot.message_handler(func=lambda message: get_ad_state(message.chat.id) is not None, content_types=['text', 'photo'])
def handle_ad_input(message):
    chat_id = message.chat.id
    state = get_ad_state(chat_id)

    if chat_id not in user_ad_data or state is None:
        return

    if message.content_type == 'photo':
        if state == 'ad_photo':
            file_id = message.photo[-1].file_id
            user_ad_data[chat_id]['Фото_URL'] = f"photo_file_id:{file_id}"
            push_ad_state(chat_id, 'ad_confirm')
            show_step(chat_id)
        else:
            bot.reply_to(message, t(chat_id, 'ad_follow_instructions'))
        return

    if message.content_type != 'text':
        return

    text = message.text.strip()
    if not text:
        bot.reply_to(message, t(chat_id, 'ad_enter_nonempty'))
        return

    if text.lower() == '/skip' and state == 'ad_photo':
        user_ad_data[chat_id]['Фото_URL'] = ''
        push_ad_state(chat_id, 'ad_confirm')
        show_step(chat_id)
        return

    if state == 'ad_title':
        if len(text) < 2:
            bot.reply_to(message, t(chat_id, 'ad_title_short'))
            return
        user_ad_data[chat_id]['Название'] = text
        push_ad_state(chat_id, 'ad_brand')
        show_step(chat_id)

    elif state == 'ad_brand':
        if len(text) < 2:
            bot.reply_to(message, t(chat_id, 'ad_brand_short'))
            return
        user_ad_data[chat_id]['Марка'] = text
        push_ad_state(chat_id, 'ad_year')
        show_step(chat_id)

    elif state == 'ad_year':
        if not text.isdigit() or not (1900 <= int(text) <= datetime.now().year):
            bot.reply_to(message, t(chat_id, 'ad_year_bad', current=datetime.now().year))
            return
        user_ad_data[chat_id]['Год выпуска'] = text
        push_ad_state(chat_id, 'ad_condition')
        show_step(chat_id)

    elif state == 'ad_condition':
        bot.reply_to(message, t(chat_id, 'ad_use_buttons_state'))

    elif state == 'ad_specs':
        if len(text) < 5:
            bot.reply_to(message, t(chat_id, 'ad_specs_short'))
            return
        if not re.match(r'^[а-яА-ЯёЁa-zA-Z0-9 ,.\-]+$', text):
            bot.reply_to(message, t(chat_id, 'ad_specs_bad_chars'))
            return
        user_ad_data[chat_id]['Технические характеристики'] = text
        push_ad_state(chat_id, 'ad_docs')
        show_step(chat_id)

    elif state == 'ad_docs':
        bot.reply_to(message, t(chat_id, 'ad_use_buttons_docs'))

    elif state == 'ad_region':
        if len(text) < 3:
            bot.reply_to(message, t(chat_id, 'ad_region_short'))
            return
        if not re.match(r'^[а-яА-ЯёЁa-zA-Z \-]+$', text):
            bot.reply_to(message, t(chat_id, 'ad_region_bad_chars'))
            return
        user_ad_data[chat_id]['Регион'] = text
        push_ad_state(chat_id, 'ad_delivery')
        show_step(chat_id)

    elif state == 'ad_delivery':
        if len(text) < 3:
            bot.reply_to(message, t(chat_id, 'ad_delivery_short'))
            return
        if not re.match(r'^[а-яА-ЯёЁa-zA-Z ,.\-]+$', text):
            bot.reply_to(message, t(chat_id, 'ad_delivery_bad_chars'))
            return
        user_ad_data[chat_id]['Условия доставки'] = text
        push_ad_state(chat_id, 'ad_price')
        show_step(chat_id)

    elif state == 'ad_price':
        try:
            price = float(text.replace(',', '.'))
            if price <= 0:
                raise ValueError
            user_ad_data[chat_id]['Цена'] = str(price)
            push_ad_state(chat_id, 'ad_photo')
            show_step(chat_id)
        except Exception:
            bot.reply_to(message, t(chat_id, 'ad_price_bad'))

    elif state == 'ad_photo':
        if re.match(r'^https?://\S+$', text):
            user_ad_data[chat_id]['Фото_URL'] = text
            push_ad_state(chat_id, 'ad_confirm')
            show_step(chat_id)
        else:
            bot.reply_to(message, t(chat_id, 'ad_photo_bad_link'))

    elif state == 'ad_confirm':
        bot.reply_to(message, t(chat_id, 'ad_use_buttons_confirm'))

    else:
        bot.reply_to(message, t(chat_id, 'ad_something_wrong'))


@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    if chat_id not in user_lang:
        bot.reply_to(
            message,
            "🇬🇧 Please choose your language:\n🇷🇺 Пожалуйста, выберите язык:",
            reply_markup=get_lang_kb()
        )
    else:
        bot.reply_to(message, t(chat_id, 'welcome'), parse_mode='Markdown')
    log_to_sheet('/start', '', message.from_user.id, message.from_user.username)


@bot.message_handler(commands=['help'])
def send_help(message):
    bot.reply_to(message, t(message.chat.id, 'help'))


@bot.message_handler(commands=['categories'])
def categories_menu(message):
    chat_id = message.chat.id
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(t(chat_id, 'btn_rent'), callback_data='cat_rent'),
        types.InlineKeyboardButton(t(chat_id, 'btn_sale'), callback_data='cat_sale')
    )
    bot.send_message(chat_id, t(chat_id, 'choose_ad_type'), reply_markup=markup)


@bot.message_handler(commands=['latest'])
def latest_listings(message):
    chat_id = message.chat.id
    listings = get_latest_listings(10)
    if not listings:
        bot.reply_to(message, t(chat_id, 'no_listings'))
        return
    send_listings_list(chat_id, listings, title=t(chat_id, 'latest_title'))
    log_to_sheet('/latest', '', message.from_user.id, message.from_user.username)


@bot.message_handler(commands=['search'])
def search_listings(message):
    chat_id = message.chat.id
    query = message.text.replace('/search', '').strip()
    if not query:
        bot.reply_to(message, t(chat_id, 'search_empty_prompt'))
        return

    search_query_orig = query.lower()

    search_query_trans = search_query_orig
    if user_lang.get(chat_id) == 'en':
        search_query_trans = translate_text(search_query_orig, 'ru').lower()
    elif user_lang.get(chat_id) == 'ru':
        search_query_trans = translate_text(search_query_orig, 'en').lower()

    all_listings = get_all_listings()
    found = []
    for item in all_listings:
        name = str(item.get('Название', '')).lower()
        mark = str(item.get('Марка', '')).lower()

        if (search_query_orig in name or search_query_orig in mark) or \
                (search_query_trans in name or search_query_trans in mark):
            found.append(item)

    if not found:
        bot.reply_to(message, t(chat_id, 'search_nothing', query=query))
        return
    send_listings_list(chat_id, found, title=t(chat_id, 'search_title', query=query))
    log_to_sheet('/search', query, message.from_user.id, message.from_user.username)




@bot.message_handler(commands=['filter'])
def start_filter(message):
    chat_id = message.chat.id
    user_filters[chat_id] = {
        'filters': {},
        'listings': get_all_listings(),
        'step': 'choose'
    }
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(t(chat_id, 'btn_filter_price'), callback_data='filter_price'),
        types.InlineKeyboardButton(t(chat_id, 'btn_filter_year'), callback_data='filter_year'),
        types.InlineKeyboardButton(t(chat_id, 'btn_filter_region'), callback_data='filter_region'),
        types.InlineKeyboardButton(t(chat_id, 'btn_filter_apply'), callback_data='filter_apply'),
        types.InlineKeyboardButton(t(chat_id, 'btn_filter_reset'), callback_data='filter_reset'),
        types.InlineKeyboardButton(t(chat_id, 'btn_filter_cancel'), callback_data='filter_cancel')
    )
    bot.send_message(chat_id, t(chat_id, 'filter_prompt'), reply_markup=markup)


@bot.message_handler(
    func=lambda message: message.chat.id in user_filters and user_filters[message.chat.id].get('step', '').startswith(
        'waiting_'))
def handle_filter_input(message):
    chat_id = message.chat.id
    state = user_filters[chat_id]['step']
    filters = user_filters[chat_id]['filters']
    text = message.text.strip()

    if state == 'waiting_price':
        parts = text.split()
        if len(parts) == 2 and parts[0].replace('.', '', 1).isdigit() and parts[1].replace('.', '', 1).isdigit():
            filters['price_min'] = float(parts[0])
            filters['price_max'] = float(parts[1])
            bot.reply_to(message, t(chat_id, 'filter_price_set', min=parts[0], max=parts[1]))
        else:
            bot.reply_to(message, t(chat_id, 'filter_price_bad'))
            return
    elif state == 'waiting_year':
        if text.isdigit():
            filters['year'] = text
            bot.reply_to(message, t(chat_id, 'filter_year_set', year=text))
        else:
            bot.reply_to(message, t(chat_id, 'filter_year_bad'))
            return
    elif state == 'waiting_region':
        filters['region'] = text
        bot.reply_to(message, t(chat_id, 'filter_region_set', region=text))

    user_filters[chat_id]['step'] = 'choose'
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(t(chat_id, 'btn_filter_price'), callback_data='filter_price'),
        types.InlineKeyboardButton(t(chat_id, 'btn_filter_year'), callback_data='filter_year'),
        types.InlineKeyboardButton(t(chat_id, 'btn_filter_region'), callback_data='filter_region'),
        types.InlineKeyboardButton(t(chat_id, 'btn_filter_apply'), callback_data='filter_apply'),
        types.InlineKeyboardButton(t(chat_id, 'btn_filter_reset'), callback_data='filter_reset'),
        types.InlineKeyboardButton(t(chat_id, 'btn_filter_cancel'), callback_data='filter_cancel')
    )
    bot.send_message(chat_id, t(chat_id, 'filter_current', filters=str(filters)), reply_markup=markup)


app = Flask('')


@app.route('/')
def home():
    return t(0, 'web_ok')


def run_web_server():
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)


if __name__ == '__main__':
    retry_failed_ads()
    Thread(target=run_web_server, daemon=True).start()
    print(t(0, 'bot_started'))
    bot.infinity_polling(skip_pending=True, timeout=10, long_polling_timeout=5)
