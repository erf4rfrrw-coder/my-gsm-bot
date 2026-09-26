import asyncio
import os
import re
import requests
from bs4 import BeautifulSoup
from aiogram import Bot
from aiohttp import web

# ================= НАСТРОЙКИ =================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8920355118:AAFexi7N6hqjcGjz-IiUhCQbuQZgphlXmSI")
CHAT_ID = int(os.environ.get("CHAT_ID", "1059060123"))

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
# =============================================

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
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        res = requests.get(search_url, headers=headers, timeout=5)
        if res.status_code != 200:
            return None

        soup = BeautifulSoup(res.text, 'html.parser')
        items = soup.find_all('li', class_=re.compile(r'ads-list-detail-item'))
        
        prices = []
        for item in items[:8]:
            p_tag = item.find('div', class_=re.compile(r'ads-list-detail-item-price'))
            if p_tag:
                val = parse_price(p_tag.text)
                if val and val > 50:
                    prices.append(val)
        
        if prices:
            return sum(prices) // len(prices)
    except Exception as e:
        print(f"Ошибка получения средней цены: {e}")
    return None

def check_ads():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    new_matches = []

    for url in CATEGORIES:
        try:
            response = requests.get(url, headers=headers, timeout=8)
            if response.status_code != 200:
                continue

            soup = BeautifulSoup(response.text, 'html.parser')
            items = soup.find_all('li', class_=re.compile(r'ads-list-detail-item'))

            for item in items:
                subtext = item.find('div', class_=re.compile(r'ads-list-detail-item-subtext'))
                region = subtext.text.strip().lower() if subtext else ""
                
                if region and not any(city in region for city in ["chișinău", "chisinau", "кишинев", "кишинёв"]):
                    continue

                link_tag = item.find('a', href=re.compile(r'/(ru|ro)/\d+'))
                if not link_tag:
                    continue

                ad_href = link_tag['href']
                ad_id = re.sub(r'^/(ru|ro)/', '/', ad_href)

                if ad_id in seen_ads:
                    continue

                title = link_tag.text.strip()
                title_lower = title.lower()

                price_tag = item.find('div', class_=re.compile(r'ads-list-detail-item-price'))
                raw_price = price_tag.text.strip() if price_tag else "Не указана"
                num_price = parse_price(raw_price)

                has_defect = any(kw in title_lower for kw in DEFECT_KEYWORDS)
                is_priority = any(brand in title_lower for brand in PRIORITY_BRANDS)

                avg_market = get_market_average(title)
                discount_percent = 0
                
                if num_price and avg_market and avg_market > num_price:
                    discount_percent = int(((avg_market - num_price) / avg_market) * 100)

                is_good_deal = (has_defect) or (discount_percent >= 15)

                if is_good_deal:
                    full_link = f"https://999.md{ad_href}" if not ad_href.startswith('http') else ad_href
                    
                    new_matches.append({
                        'title': title,
                        'link': full_link,
                        'raw_price': raw_price,
                        'num_price': num_price,
                        'avg_market': avg_market,
                        'discount': discount_percent,
                        'has_defect': has_defect,
                        'is_priority': is_priority,
                        'id': ad_id
                    })

                seen_ads.add(ad_id)

        except Exception as e:
            print(f"Ошибка парсинга {url}: {e}")

    return new_matches

async def main():
    # Запуск фонового веб-сервера для прохождения Health Check на Render
    asyncio.create_task(start_dummy_server())
    
    print("🚀 Бот запущен! Ищет целую технику по скидке + дефекты под ремонт (Кишинев)...")
    try:
        await bot.send_message(
            CHAT_ID, 
            "⚙️ **Обновленный бот-перекуп готов к охоте!**\n"
            "📍 **Город:** Только Кишинев\n"
            "📱 **Ищет:**\n"
            "1. Целые нормальные телефоны/технику ниже рынка (скидка от 15%)\n"
            "2. Варианты под ремонт / с дефектами"
        )
    except Exception as e:
        print(f"Ошибка стартового сообщения: {e}")

    while True:
        try:
            ads = check_ads()
            for ad in ads:
                if ad['discount'] >= 30:
                    header = "🔥🚨 **СВЕРХВЫГОДНЫЙ ЛОТ (СКИДКА ОТ 30%)!** 🚨🔥"
                elif not ad['has_defect'] and ad['discount'] >= 15:
                    header = "📱✅ **ОТЛИЧНЫЙ ЦЕЛЫЙ ТЕЛЕФОН / ТЕХНИКА НИЖЕ РЫНКА!**"
                elif ad['has_defect']:
                    header = "🛠 **ПОТЕНЦИАЛЬНЫЙ ЛОТ ПОД РЕМОНТ / НА ДЕТАЛИ**"
                else:
                    header = "📌 **ИНТЕРЕСНОЕ ПРЕДЛОЖЕНИЕ**"

                price_info = f"💳 **Цена продавца:** `{ad['raw_price']}`\n"
                if ad['avg_market']:
                    price_info += f"📈 **Средняя цена рынка:** `~{ad['avg_market']} MDL/€`\n"
                    if ad['discount'] > 0:
                        price_info += f"🎁 **Выгода:** `~{ad['discount']}% ниже рынка`\n"
                else:
                    price_info += "📈 **Средняя цена рынка:** `Сложится при анализе`\n"

                status_tag = "🛠 Дефект/Ремонт" if ad['has_defect'] else "✅ Целое / Рабочее состояние"

                message = (
                    f"{header}\n\n"
                    f"📌 **Товар:** {ad['title']}\n"
                    f"📍 **Город:** Кишинев\n"
                    f"Состояние: {status_tag}\n\n"
                    f"{price_info}\n"
                    f"🔗 [Открыть на 999.md]({ad['link']})"
                )

                try:
                    await bot.send_message(
                        CHAT_ID, 
                        message, 
                        parse_mode="Markdown", 
                        disable_web_page_preview=False
                    )
                except Exception as e:
                    print(f"Ошибка отправки: {e}")

        except Exception as e:
            print(f"Ошибка в цикле парсинга: {e}")

        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())
