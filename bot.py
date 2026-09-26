import asyncio
import re
import requests
from bs4 import BeautifulSoup
from aiogram import Bot

# ================= НАСТРОЙКИ С ВАШИМИ ДАННЫМИ =================
TELEGRAM_TOKEN = "8920355118:AAFexi7N6hqjcGjz-IiUhCQbuQZgphlXmSI"
CHAT_ID = 1059060123

# Категории для поиска на 999.md (Телефоны, Ноутбуки, Аудио/Наушники, Приставки)
CATEGORIES = [
    "https://999.md/ru/list/phone-and-communication/mobile-phones",
    "https://999.md/ro/list/phone-and-communication/mobile-phones",
    "https://999.md/ru/list/computers-and-office-equipment/laptops",
    "https://999.md/ru/list/audio-video-photo/headphones",
    "https://999.md/ru/list/game-consoles-and-games/consoles"
]

# Ключевые слова дефектов / выгоды (RU + RO)
KEYWORDS = [
    # Неисправности / под ремонт
    "разбит", "трещина", "экран", "не включается", "не заряжается", 
    "запчасти", "дефект", "пароль", "срочно", "замена", "под восстановление", 
    "утопленник", "плата", "без фейса", "spart", "ecran", "defect", "piese", 
    "nu se aprinde", "nu incarca", "blocat", "reparatie", "sticla", "baterie",
    # Маркеры выгоды / срочной продажи
    "срочно", "urgenta", "cheap", "дешево", "распродажа", "новый", "sigilat"
]

# Приоритетные бренды (Айфоны выделяем отдельно)
PRIORITY_BRANDS = ["iphone", "apple", "macbook", "airpods", "ipad", "playstation", "ps4", "ps5"]

CHECK_INTERVAL = 20  # Проверка каждые 20 секунд
# ==============================================================

bot = Bot(token=TELEGRAM_TOKEN)
seen_ads = set()

def parse_price(price_str):
    """Извлекает числовое значение цены из строки"""
    if not price_str:
        return None
    # Ищем все цифры в строке цены
    numbers = re.findall(r'\d+', price_str.replace(" ", ""))
    if numbers:
        return int("".join(numbers))
    return None

def get_market_average(title):
    """
    Примерная оценка средней цены по заголовку.
    Скрипт делает быстрый поиск по похожим объявлениям на 999.md.
    """
    try:
        # Очищаем заголовок от слов дефектов для поиска целых аналогов
        clean_title = re.sub(r'(разбит|spart|ecran|экран|дефект|defect|срочно|urgenta|на запчасти)', '', title, flags=re.IGNORECASE).strip()
        if len(clean_title) < 4:
            return None

        search_url = f"https://999.md/ru/search?query={clean_title}"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(search_url, headers=headers, timeout=5)
        if res.status_code != 200:
            return None

        soup = BeautifulSoup(res.text, 'html.parser')
        items = soup.find_all('li', class_=re.compile(r'ads-list-detail-item'))
        
        prices = []
        for item in items[:8]:  # Берем первые 8 похожих товаров
            p_tag = item.find('div', class_=re.compile(r'ads-list-detail-item-price'))
            if p_tag:
                val = parse_price(p_tag.text)
                if val and val > 10:  # Игнорируем варианты за 1 лей
                    prices.append(val)
        
        if prices:
            # Считаем среднее арифметическое
            avg_price = sum(prices) // len(prices)
            return avg_price
    except Exception:
        pass
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
                # 1. ФИЛЬТР ПО ГОРОДУ: Проверяем, что лот из Кишинева
                subtext = item.find('div', class_=re.compile(r'ads-list-detail-item-subtext'))
                region = subtext.text.strip().lower() if subtext else ""
                
                # Если в описании региона есть упоминание района/города (Chisinau / Кишинев)
                # На 999.md если регион не указан в короткой карточке, пропускаем строгие блокировки
                if region and not any(city in region for city in ["chișinău", "chisinau", "кишинев", "кишинёв"]):
                    continue  # Пропускаем Бельцы, Тирасполь и т.д.

                link_tag = item.find('a', href=re.compile(r'/(ru|ro)/\d+'))
                if not link_tag:
                    continue

                ad_href = link_tag['href']
                ad_id = re.sub(r'^/(ru|ro)/', '/', ad_href)

                if ad_id in seen_ads:
                    continue

                title = link_tag.text.strip()
                title_lower = title.lower()

                # Проверка ключевых слов
                is_keyword_match = any(kw in title_lower for kw in KEYWORDS)
                is_priority = any(brand in title_lower for brand in PRIORITY_BRANDS)

                if is_keyword_match or is_priority:
                    price_tag = item.find('div', class_=re.compile(r'ads-list-detail-item-price'))
                    raw_price = price_tag.text.strip() if price_tag else "Не указана"
                    num_price = parse_price(raw_price)

                    full_link = f"https://999.md{ad_href}" if not ad_href.startswith('http') else ad_href

                    # Считаем среднюю рыночную цену
                    avg_market = get_market_average(title)

                    # Оцениваем, насколько выгоден лот
                    is_super_deal = False
                    discount_percent = 0
                    if num_price and avg_market and avg_market > num_price:
                        discount_percent = int(((avg_market - num_price) / avg_market) * 100)
                        if discount_percent >= 25:  # Если скидка от 25% и выше
                            is_super_deal = True

                    new_matches.append({
                        'title': title,
                        'link': full_link,
                        'raw_price': raw_price,
                        'num_price': num_price,
                        'avg_market': avg_market,
                        'discount': discount_percent,
                        'is_priority': is_priority,
                        'is_super_deal': is_super_deal,
                        'id': ad_id
                    })

                seen_ads.add(ad_id)

        except Exception as e:
            print(f"Ошибка парсинга {url}: {e}")

    return new_matches

async def main():
    print("🚀 Продвинутый бот запущен! Фильтр: Кишинев | Техника + Телефоны | Оценка рынка...")
    await bot.send_message(
        CHAT_ID, 
        "⚙️ **Умный бот-перекуп запущен!**\n"
        "📍 **Локация:** Только Кишинев\n"
        "📱 **Категории:** Apple, Android, Ноутбуки, Наушники, Консоли\n"
        "📊 **Анализ:** Авто-расчет средней рыночной цены и маржи."
    )

    while True:
        ads = check_ads()
        for ad in ads:
            # Заголовок карточки в зависимости от крутости лота
            if ad['is_super_deal'] and ad['is_priority']:
                header = "🔥🚨 **ТОП СВЕРХВЫГОДНЫЙ APPLE ЛОТ!** 🚨🔥"
            elif ad['is_super_deal']:
                header = "💎 **ВЫГОДНОЕ ПРЕДЛОЖЕНИЕ (НИЖЕ РЫНКА)!** 💎"
            elif ad['is_priority']:
                header = "🍏 **APPLE / ПРИОРИТЕТНЫЙ ТОВАР**"
            else:
                header = "🛠 **ПОТЕНЦИАЛЬНЫЙ ЛОТ ПОД РЕМОНТ / ПЕРЕКУП**"

            # Формируем красивую аналитику цен
            price_info = f"💳 **Цена продавца:** `{ad['raw_price']}`\n"
            if ad['avg_market']:
                price_info += f"📈 **Средняя цена б/у рынка:** `~{ad['avg_market']} (лей/€)`\n"
                if ad['discount'] > 0:
                    price_info += f"🎁 **Выгода / Скидка:** `~{ad['discount']}% ниже рынка`\n"
            else:
                price_info += "📈 **Средняя цена рынка:** `Уточняется / Уникальный лот`\n"

            message = (
                f"{header}\n\n"
                f"📌 **Товар:** {ad['title']}\n"
                f"📍 **Город:** Кишинев\n\n"
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

        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())