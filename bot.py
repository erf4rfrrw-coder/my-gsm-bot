import asyncio
import os
import re
import requests
from bs4 import BeautifulSoup
from aiogram import Bot
from aiohttp import web

# ================= НАСТРОЙКИ С ВАШИМИ ДАННЫМИ =================
TELEGRAM_TOKEN = "8920355118:AAFexi7N6hqjcGjz-IiUhCQbuQZgphlXmSI"
CHAT_ID = 1059060123

CATEGORIES = [
    "https://999.md/ru/list/phone-and-communication/mobile-phones",
    "https://999.md/ro/list/phone-and-communication/mobile-phones",
    "https://999.md/ru/list/computers-and-office-equipment/laptops",
    "https://999.md/ru/list/audio-video-photo/headphones",
    "https://999.md/ru/list/game-consoles-and-games/consoles"
]

DEFECT_KEYWORDS = [
    "разбит", "трещина", "экран", "не включается", "не заряжается", 
    "запчасти", "дефект", "пароль", "срочно", "замена", "под восстановление", 
    "утопленник", "плата", "без фейса", "spart", "ecran", "defect", "piese", 
    "nu se aprinde", "nu incarca", "blocat", "reparatie", "sticla", "baterie"
]

PRIORITY_BRANDS = ["iphone", "apple", "macbook", "airpods", "ipad", "playstation", "ps4", "ps5", "samsung", "xiaomi"]

CHECK_INTERVAL = 25  # Пауза между проверками (секунд)
# ==============================================================

bot = Bot(token=TELEGRAM_TOKEN)
seen_ads = set()

# ВЕБ-СЕРВЕР ДЛЯ ПРОХОЖДЕНИЯ HEALTH CHECK НА RENDER
async def handle_health_check(request):
    return web.Response(text="Bot is active 24/7!")

async def start_dummy_server():
    app = web.Application()
    app.router.add_get('/', handle_health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🌐 Веб-сервер успешно запущен на порту {port}")

def parse_price(price_str):
    if not price_str:
        return None
    numbers = re.findall(r'\d+', price_str.replace(" ", ""))
    if numbers:
        return int("".join(numbers))
    return None

def get_market_average(title):
    try:
        clean_title = re.sub(
            r'(разбит|spart|ecran|экран|дефект|defect|срочно|urgenta|на запчасти|stare buna|состояние хорошее|nou|новый)', 
            '', title, flags=re.IGNORECASE
        ).strip()
        
        if len(clean_title) < 4:
            return None

        search_url = f"https://999.md/ru/search?query={clean_title}"
        headers
