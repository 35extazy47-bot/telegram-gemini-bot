import os
import random
import uuid
import time
import math
from datetime import datetime, timedelta
import io
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

import database
from database import (
    users, save_users, market_prices, market_volumes, last_prices,
    price_history, TRADE_GOODS, save_market_data, market_lock, data_lock, 
    DEVELOPER_USERNAME
)

# Bu fonksiyonlar tirtil.py'den register fonksiyonu aracılığıyla alınacak
get_badges = None
update_quest_progress = None

NEWS_TEMPLATES = {
    "ipek": {"up": ["Sarayda ipek modası başladı! 👗"], "down": ["Çin'den dev ipek kervanı ulaştı! 🐫"]},
    "baharat": {"up": ["Saray mutfağı için yüklü baharat siparişi verildi! 🍛"], "down": ["Yeni baharat yolu keşfedildi! 🗺️"]},
    "cini": {"up": ["Yeni cami inşaatı için binlerce çini aranıyor! 🕌"], "down": ["Çini atölyelerinde üretim rekoru kırıldı! 🏺"]},
    "tuz": {"up": ["Kış yaklaşıyor, halk tuz stokluyor! ❄️"], "down": ["Yeni tuz madeni keşfedildi! ⛏️"]},
    "elmas": {"up": ["Saray mücevherleri için dev elmas siparişi! 💍"], "down": ["Yeni bir elmas rezervi bulundu! 📉"]},
    "altin": {"up": ["Savaş söylentileri halkı altına yöneltti! 🛡️"], "down": ["Yeni altın madeni işletmeye açıldı! ⛏️"]},
    "demir": {"up": ["Ordu için yeni silah siparişi! ⚔️"], "down": ["Hurda demirler piyasaya sürüldü. ♻️"]}
}

def calculate_indicators(prices):
    """Fiyat geçmişine göre RSI ve SMA teknik indikatörlerini hesaplar."""
    if not prices: return {"rsi": 50, "sma": 0}
    current = prices[-1]
    sma_period = 5
    sma = sum(prices[-sma_period:]) / sma_period if len(prices) >= sma_period else current
    period = 14
    if len(prices) < period + 1: return {"rsi": 50, "sma": sma}
    gains, losses = [], []
    relevant_prices = prices[-(period+1):]
    for i in range(1, len(relevant_prices)):
        change = relevant_prices[i] - relevant_prices[i-1]
        if change > 0: gains.append(change); losses.append(0)
        else: gains.append(0); losses.append(abs(change))
    avg_gain, avg_loss = sum(gains) / period, sum(losses) / period
    if avg_loss == 0: rsi = 100
    else: rs = avg_gain / avg_loss; rsi = 100 - (100 / (1 + rs))
    return {"rsi": rsi, "sma": sma}

def check_limit_orders(bot):
    executed_count = 0
    for uid, user in list(users.items()):
        if not user.get("limit_orders"): continue
        for order in list(user["limit_orders"]):
            item, target, amount, o_type = order["item"], order["target"], order["amount"], order["type"]
            current_price = market_prices.get(item)
            if not current_price: continue
            
            executed, total_value = False, 0
            if o_type == "AL" and current_price <= target:
                cost = current_price * amount
                if user.get("money", 0) >= cost:
                    user["money"] -= cost; user.setdefault("inventory", {})[item] = user.get("inventory", {}).get(item, 0) + amount
                    executed, total_value = True, cost
                    p_item = user.setdefault("portfolio", {}).setdefault(item, {"amount": 0, "total_cost": 0})
                    p_item["amount"] += amount; p_item["total_cost"] += cost
            elif o_type == "SAT" and current_price >= target:
                if user.get("inventory", {}).get(item, 0) >= amount:
                    gain = current_price * amount
                    user["inventory"][item] -= amount; user["money"] = user.get("money", 0) + gain
                    executed, total_value = True, gain
                    if "portfolio" in user and item in user["portfolio"]:
                        p_item = user["portfolio"][item]
                        if p_item["amount"] > 0:
                            p_item["total_cost"] -= (p_item["total_cost"] / p_item["amount"]) * amount
                            p_item["amount"] -= amount
                            if p_item["amount"] < 1: del user["portfolio"][item]
            
            if executed:
                user.setdefault("orders", []).append({"type": f"OTOMATİK {o_type}IM", "item": TRADE_GOODS[item]['name'], "amount": amount, "price": current_price, "total": total_value, "date": datetime.now().strftime("%Y-%m-%d %H:%M")})
                if len(user["orders"]) > 20: user["orders"].pop(0)
                user["limit_orders"].remove(order); executed_count += 1
                try:
                    msg_body = f"✅ **{'Alım' if o_type == 'AL' else 'Satış'} Emri Gerçekleşti**\n📦 {TRADE_GOODS[item]['name']} | {amount} Adet | {current_price} $\n{'💰 Toplam Maliyet' if o_type == 'AL' else '💵 Toplam Kazanç'}: {total_value} $"
                    bot.send_message(uid, msg_body)
                except: pass
    if executed_count > 0: save_users(); print(f"🤖 {executed_count} adet limit emir tetiklendi.")

def update_market(bot):
    global market_prices, market_volumes, last_prices, price_history
    with market_lock:
        last_prices = market_prices.copy()
        if database.active_news_item is None or (datetime.now() - database.last_news_update).total_seconds() > 300:
            database.last_news_update = datetime.now()
            database.market_trend = random.choices([-1, 0, 1], weights=[0.3, 0.4, 0.3])[0]
            database.active_news_item = random.choice(list(TRADE_GOODS.keys()))
            database.active_news_direction = random.choice(["up", "down"])
            database.market_news = random.choice(NEWS_TEMPLATES[database.active_news_item][database.active_news_direction])
            
            event_roll = random.randint(1, 100)
            database.active_global_modifier = -0.25 if event_roll <= 3 else (0.25 if event_roll >= 97 else 0.0)
            if database.active_global_modifier == -0.25: database.market_news = "📉 **KARA GÜN!** Küresel kriz patlak verdi! Piyasalar çakılıyor!"
            elif database.active_global_modifier == 0.25: database.market_news = "🚀 **ALTIN ÇAĞ!** Yabancı yatırımcılar ülkeye akın etti!"
            print(f"📊 Piyasa Trendi: {database.market_trend}, Haber: {database.market_news}")

        trend_strength = random.uniform(0.01, 0.03)
        for code, data in TRADE_GOODS.items():
            # 1. Volatilite ve Trend
            change_percent = random.gauss(0, data["volatility"]) + (database.market_trend * trend_strength) + database.active_global_modifier
            
            # 2. Hacim Etkisi (Logaritmik - Daha gerçekçi)
            vol = market_volumes.get(code, 0)
            if vol != 0:
                vol_impact = (1 if vol > 0 else -1) * math.log(abs(vol) + 1) * 0.005
                change_percent += vol_impact

            # 3. Haber Etkisi
            if code == database.active_news_item: change_percent += random.uniform(0.05, 0.15) * (1 if database.active_news_direction == "up" else -1)
            
            # 4. Momentum (Önceki hareketin %20'si devam eder)
            history = price_history.get(code, [])
            if len(history) > 1:
                prev_change_pct = (history[-1] - history[-2]) / history[-2] if history[-2] != 0 else 0
                change_percent += prev_change_pct * 0.2

            limit = 0.30 if database.active_global_modifier != 0 else 0.15
            change_percent = max(-limit, min(change_percent, limit))
            price_change = int(market_prices[code] * change_percent) or (random.randint(1, 3) * (-1 if change_percent < 0 else 1))
            
            market_prices[code] = max(data["min"], min(market_prices[code] + price_change, data["max"]))
            price_history.setdefault(code, []).append(market_prices[code])
            if len(price_history[code]) > 40: price_history[code].pop(0) # Grafik için daha fazla veri

        # Hacim zamanla azalır (Likidite)
        for k in market_volumes:
            market_volumes[k] = int(market_volumes[k] * 0.8)
            
        check_limit_orders(bot)
        database.last_market_update = datetime.now()
        save_market_data()

def apply_bank_interest(bot):
    count = 0
    with data_lock:
        for uid, u in users.items():
            if u.get("bank_balance", 0) > 0:
                interest = int(u["bank_balance"] * 0.05)
                if interest > 0:
                    u["bank_balance"] += interest; count += 1
                    try: bot.send_message(uid, f"🏦 **GÜNLÜK FAİZ GELDİ!**\nKazanç: +{interest} $\nYeni Bakiye: {u['bank_balance']} $")
                    except: pass
    if count > 0: save_users(); print(f"🏦 {count} kişiye faiz dağıtıldı.")

def create_market_image(user_data=None):
    num_items, row_height, header_height, footer_height = len(TRADE_GOODS), 80, 180, 60
    width, height = 1400, header_height + (num_items * row_height) + footer_height
    img = Image.new('RGB', (width, height), color=(30, 33, 43)) # Daha modern koyu ton
    draw = ImageDraw.Draw(img)
    try:
        font_path = "arial.ttf"
        if not os.path.exists(font_path): font_path = next((f for f in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"] if os.path.exists(f)), font_path)
        title_font, header_font, row_font, small_font = ImageFont.truetype(font_path, 42), ImageFont.truetype(font_path, 26), ImageFont.truetype(font_path, 24), ImageFont.truetype(font_path, 18)
    except:
        title_font, header_font, row_font, small_font = ImageFont.load_default(), ImageFont.load_default(), ImageFont.load_default(), ImageFont.load_default()

    draw.rectangle([(0, 0), (width, 100)], fill=(52, 211, 153)); draw.text((40, 25), "📈 KAPALIÇARŞI BORSASI", font=title_font, fill=(20, 20, 30))
    current_index, last_index = sum(market_prices.values()), sum(last_prices.values())
    idx_diff, idx_pct = current_index - last_index, (current_index - last_index) / last_index * 100 if last_index > 0 else 0
    idx_arrow = "▲" if idx_diff > 0 else ("▼" if idx_diff < 0 else "➖")
    draw.text((700, 35), f"ENDEKS: {current_index} {idx_arrow} %{abs(idx_pct):.2f}", font=header_font, fill=(40, 40, 50))
    draw.rectangle([(30, 120), (width-30, 170)], fill=(40, 44, 56)); draw.text((45, 135), f"📰 {database.market_news[:100] + '...' if len(database.market_news) > 100 else database.market_news}", font=row_font, fill=(200, 200, 220))
    
    y = 200; headers = ["ÜRÜN", "FİYAT", "DEĞİŞİM", "VARLIK", "DERİNLİK", "GRAFİK (Son 1s)"]; x_pos = [40, 280, 450, 650, 850, 1100]
    for i, h in enumerate(headers): draw.text((x_pos[i], y), h, font=header_font, fill=(160, 170, 190))
    draw.line([(40, y + 40), (width-40, y + 40)], fill=(60, 65, 80), width=2)
    
    y += 60
    for code, data in TRADE_GOODS.items():
        price, old_price = market_prices.get(code, data["base"]), last_prices.get(code, data["base"])
        diff = price - old_price
        draw.rectangle([(40, y), (width-40, y+60)], fill=(40, 44, 56))
        draw.text((50, y+15), data['name'], font=row_font, fill=(255, 255, 255))
        draw.text((280, y+15), f"{price} $", font=row_font, fill=(250, 250, 250))
        diff_str, color = (f"▲ +{diff}", (74, 222, 128)) if diff > 0 else ((f"▼ {diff}", (248, 113, 113)) if diff < 0 else ("➖ 0", (148, 163, 184)))
        draw.text((450, y+15), diff_str, font=row_font, fill=color)
        user_stock = user_data.get("inventory", {}).get(code, 0) if user_data else 0
        draw.text((650, y+15), f"{user_stock} Adet", font=row_font, fill=((255, 255, 255) if user_stock > 0 else (120, 120, 140)))
        
        vol = market_volumes.get(code, 0); bar_x, bar_w, center_x = 850, 200, 850 + 100
        draw.rectangle([(bar_x, y+25), (bar_x + bar_w, y+40)], fill=(30, 33, 43)); draw.line([(center_x, y+20), (center_x, y+45)], fill=(100, 100, 120), width=1)
        bar_len = min(abs(vol) * 2, 100)
        if vol >= 0: draw.rectangle([(center_x, y+25), (center_x + bar_len, y+40)], fill=(74, 222, 128))
        else: draw.rectangle([(center_x - bar_len, y+25), (center_x, y+40)], fill=(248, 113, 113))
        
        # Sparkline (Mini Grafik)
        hist = price_history.get(code, [])[-20:] # Son 20 veri
        if len(hist) > 1:
            sl_x, sl_y, sl_w, sl_h = 1100, y + 10, 250, 40
            min_h, max_h = min(hist), max(hist)
            points = []
            for idx, val in enumerate(hist):
                px = sl_x + (idx * (sl_w / (len(hist) - 1)))
                py = sl_y + sl_h - ((val - min_h) / (max_h - min_h) * sl_h) if max_h != min_h else sl_y + sl_h/2
                points.append((px, py))
            
            sl_color = (74, 222, 128) if hist[-1] >= hist[0] else (248, 113, 113)
            draw.line(points, fill=sl_color, width=2)
            # Son nokta
            lx, ly = points[-1]
            draw.ellipse((lx-3, ly-3, lx+3, ly+3), fill=sl_color)

        y += row_height

    seconds_left = max(0, 90 - (datetime.now() - database.last_market_update).total_seconds())
    draw.text((width - 350, height - 40), f"⏳ Yenilenme: {int(seconds_left // 60)}dk {int(seconds_left % 60)}sn", font=small_font, fill=(150, 150, 170))
    bio = io.BytesIO(); img.save(bio, 'PNG'); bio.seek(0)
    return bio

def create_portfolio_image(user_data):
    width = 800
    portfolio = user_data.get("portfolio", {})
    num_items = len([v for v in portfolio.values() if v.get("amount", 0) > 0])
    height = 200 + (num_items * 50)
    
    img = Image.new('RGB', (width, height), color=(25, 28, 36))
    draw = ImageDraw.Draw(img)
    
    try:
        font_path = "arial.ttf"
        if not os.path.exists(font_path): font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        title_font, header_font, row_font = ImageFont.truetype(font_path, 36), ImageFont.truetype(font_path, 20), ImageFont.truetype(font_path, 18)
    except:
        title_font, header_font, row_font = ImageFont.load_default(), ImageFont.load_default(), ImageFont.load_default()

    draw.text((40, 20), f"💼 {user_data.get('name', '')} Portföyü", font=title_font, fill=(255, 215, 0))

    if not num_items:
        draw.text((40, 100), "Portföyün boş...", font=header_font, fill=(150, 150, 150))
        bio = io.BytesIO(); img.save(bio, 'PNG'); bio.seek(0)
        return bio, 0, 0

    y = 90
    headers = ["ÜRÜN", "ADET", "ORT. MALİYET", "P&L", "GÜNCEL DEĞER"]
    x_pos = [40, 250, 400, 550, 680]
    for i, h in enumerate(headers): draw.text((x_pos[i], y), h, font=header_font, fill=(150, 150, 150))
    
    y += 30
    total_portfolio_value, total_initial_cost = 0, 0

    with market_lock:
        for code, data in portfolio.items():
            if data.get("amount", 0) <= 0: continue
            item_info = TRADE_GOODS.get(code)
            if not item_info: continue
            
            current_price, amount, total_cost = market_prices.get(code, 0), data["amount"], data["total_cost"]
            avg_cost, current_value = total_cost / amount if amount > 0 else 0, current_price * amount
            profit_loss = current_value - total_cost
            
            total_portfolio_value += current_value; total_initial_cost += total_cost
            
            draw.line([(40, y-5), (width-40, y-5)], fill=(50, 50, 70), width=1)
            draw.text((x_pos[0], y), item_info["name"], font=row_font, fill=(255,255,255))
            draw.text((x_pos[1], y), str(int(amount)), font=row_font, fill=(255,255,255))
            draw.text((x_pos[2], y), f"{avg_cost:.1f} $", font=row_font, fill=(255,255,255))
            
            pl_color = (46, 204, 113) if profit_loss >= 0 else (231, 76, 60)
            pl_sign = "+" if profit_loss >= 0 else ""
            draw.text((x_pos[3], y), f"{pl_sign}{profit_loss:.0f} $", font=row_font, fill=pl_color)
            draw.text((x_pos[4], y), f"{current_value:.0f} $", font=row_font, fill=(255, 215, 0))
            y += 50

    total_profit_loss = total_portfolio_value - total_initial_cost
    draw.line([(40, y+10), (width-40, y+10)], fill=(80, 80, 80), width=2); y += 30
    
    draw.text((400, y), "Toplam Değer:", font=header_font, fill=(150, 150, 150))
    draw.text((680, y), f"{total_portfolio_value:.0f} $", font=header_font, fill=(255, 215, 0))
    y += 40
    
    pl_color = (46, 204, 113) if total_profit_loss >= 0 else (231, 76, 60)
    pl_sign = "+" if total_profit_loss >= 0 else ""
    draw.text((400, y), "Toplam Kar/Zarar:", font=header_font, fill=(150, 150, 150))
    draw.text((680, y), f"{pl_sign}{total_profit_loss:.0f} $", font=header_font, fill=pl_color)

    bio = io.BytesIO(); img.save(bio, 'PNG'); bio.seek(0)
    return bio, total_portfolio_value, total_profit_loss

def create_inventory_image(user_data):
    width, height = 800, 600
    img = Image.new('RGB', (width, height), color=(35, 39, 42))
    draw = ImageDraw.Draw(img)
    try:
        font_path = "arial.ttf"
        if not os.path.exists(font_path): font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        title_font, header_font, item_font = ImageFont.truetype(font_path, 40), ImageFont.truetype(font_path, 28), ImageFont.truetype(font_path, 22)
    except:
        title_font, header_font, item_font = ImageFont.load_default(), ImageFont.load_default(), ImageFont.load_default()

    draw.rectangle([(20, 80), (300, 580)], fill=(44, 47, 51))
    draw.text((30, 30), "🎒 OYUNCU ÇANTASI", font=title_font, fill=(255, 215, 0))
    
    y = 100
    draw.text((40, y), "👤 Sahibi:", font=item_font, fill=(150, 150, 150)); draw.text((40, y+25), user_data.get("name", "Bilinmiyor")[:15], font=header_font, fill=(255, 255, 255)); y += 90
    draw.text((40, y), "💵 Bakiye:", font=item_font, fill=(150, 150, 150)); draw.text((40, y+25), f"{user_data.get('money', 0)} $", font=header_font, fill=(46, 204, 113)); y += 90
    draw.text((40, y), "❤️ Can:", font=item_font, fill=(150, 150, 150)); draw.text((40, y+25), f"{user_data.get('lives', 3)}", font=header_font, fill=(231, 76, 60)); y += 90
    draw.text((40, y), "⛏️ Ekipman:", font=item_font, fill=(150, 150, 150)); draw.text((40, y+25), "Elmas Kazma" if user_data.get("has_pickaxe") else "Yok", font=item_font, fill=(52, 152, 219))

    items = []
    inv = user_data.get("inventory", {})
    if inv.get("joker_50", 0) > 0: items.append({"name": "%50 Joker", "count": inv["joker_50"], "icon": "💡"})
    if inv.get("joker_pass", 0) > 0: items.append({"name": "Pas Geç", "count": inv["joker_pass"], "icon": "⏭"})
    if inv.get("joker_audience", 0) > 0: items.append({"name": "Seyirci", "count": inv["joker_audience"], "icon": "👥"})
    if inv.get("joker_ai", 0) > 0: items.append({"name": "AI İpucu", "count": inv["joker_ai"], "icon": "🤖"})
    if inv.get("streak_saver", 0) > 0: items.append({"name": "Koruyucu", "count": inv["streak_saver"], "icon": "🛡️"})
    for code, count in inv.items():
        if count > 0 and code in TRADE_GOODS: items.append({"name": TRADE_GOODS[code]["name"].split()[0], "count": count, "icon": "📦"})

    start_x, start_y, box_w, box_h, gap = 340, 80, 210, 100, 20
    if not items: draw.text((start_x + 80, start_y + 200), "Çanta Boş... 🕸️", font=header_font, fill=(100, 100, 100))
    
    for i, item in enumerate(items):
        col, row = i % 2, i // 2
        x, y = start_x + (col * (box_w + gap)), start_y + (row * (box_h + gap))
        draw.rectangle([(x, y), (x + box_w, y + box_h)], fill=(44, 47, 51))
        draw.text((x + 15, y + 30), item["icon"], font=header_font, fill=(255, 255, 255))
        draw.text((x + 60, y + 20), item["name"], font=item_font, fill=(255, 255, 255))
        draw.text((x + 60, y + 50), f"x{item['count']}", font=header_font, fill=(255, 215, 0))

    bio = io.BytesIO(); img.save(bio, 'PNG'); bio.seek(0)
    return bio

def register_market_handlers(bot, tirtil_utils):
    """Ekonomi ile ilgili tüm komutları ve callback'leri bota kaydeder."""
    global get_badges, update_quest_progress
    get_badges = tirtil_utils['get_badges']
    update_quest_progress = tirtil_utils['update_quest_progress']

    def get_user_profile_image(user_id):
        try:
            photos = bot.get_user_profile_photos(user_id)
            if photos.total_count > 0:
                file_info = bot.get_file(photos.photos[0][-1].file_id)
                return Image.open(io.BytesIO(bot.download_file(file_info.file_path)))
        except: pass
        return None

    def create_rich_list_image(sorted_users):
        width, height = 800, 140 + (len(sorted_users) * 70)
        img = Image.new('RGB', (width, height), color=(35, 39, 42))
        draw = ImageDraw.Draw(img)
        
        try:
            font_path = "arial.ttf"
            if not os.path.exists(font_path): font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            title_font, row_font, small_font = ImageFont.truetype(font_path, 40), ImageFont.truetype(font_path, 24), ImageFont.truetype(font_path, 16)
        except: title_font, row_font, small_font = ImageFont.load_default(), ImageFont.load_default(), ImageFont.load_default()

        draw.text((180, 30), "💸 ZENGİNLER LİSTESİ 💸", font=title_font, fill=(46, 204, 113))
        draw.rectangle([(20, 90), (width-20, 140)], fill=(44, 47, 51))
        
        headers = ["#", "OYUNCU", "SERVET", "ROZETLER"]
        x_pos = [40, 130, 450, 600]
        for i, h in enumerate(headers): draw.text((x_pos[i], 100), h, font=row_font, fill=(200, 200, 200))
            
        y = 160
        for i, (uid, data, wealth, badges) in enumerate(sorted_users, 1):
            name = data.get("name", "Gizli")[:15]
            
            color = (255, 255, 255)
            if i == 1: color = (255, 215, 0)
            elif i == 2: color = (192, 192, 192)
            elif i == 3: color = (205, 127, 50)
            
            p_pic = get_user_profile_image(uid)
            if p_pic:
                p_pic = p_pic.resize((40, 40)); mask = Image.new("L", (40, 40), 0)
                draw_mask = ImageDraw.Draw(mask); draw_mask.ellipse((0, 0, 40, 40), fill=255)
                img.paste(p_pic, (80, y-5), mask)

            draw.text((x_pos[0], y), str(i), font=row_font, fill=color)
            draw.text((x_pos[1], y), name, font=row_font, fill=color)
            draw.text((x_pos[2], y), f"{int(wealth)} $", font=row_font, fill=color)
            draw.text((x_pos[3], y), badges, font=small_font, fill=(200, 200, 200))
            
            draw.line([(40, y+55), (width-40, y+55)], fill=(60, 60, 60), width=1)
            y += 70
            
        bio = io.BytesIO(); img.save(bio, 'PNG'); bio.seek(0)
        return bio

    def buy_rumor(message):
        user_id = str(message.from_user.id)
        cost = 100
        if users[user_id].get("money", 0) < cost:
            bot.reply_to(message, f"❌ Dedikodu için {cost} $ gerekli."); return

        users[user_id]["money"] -= cost; save_users()
        trend_text = "Piyasa kararsız görünüyor..."
        if database.market_trend > 0: trend_text = "🐂 **Kuşlar diyor ki:** Büyük tüccarlar alım yapıyor! Piyasa YÜKSELİŞ trendinde."
        elif database.market_trend < 0: trend_text = "🐻 **Kuşlar diyor ki:** Limanda mallar birikmiş! Piyasa DÜŞÜŞ trendinde."
        
        item = random.choice(list(TRADE_GOODS.keys()))
        hint = "değerlenecek gibi duruyor! 📈" if random.random() > 0.5 else "ucuzlayabilir! 📉"
        bot.reply_to(message, f"🤫 **KAPALIÇARŞI FISILTISI**\n\n{trend_text}\n\nÖzel Tüyo: **{TRADE_GOODS[item]['name']}** yakında {hint}", parse_mode="Markdown")

    def show_detailed_graph(message):
        try: item_code = message.text.split()[1].lower()
        except: bot.reply_to(message, "⚠️ Kullanım: `/grafik_detay altin`"); return
        if item_code not in TRADE_GOODS: bot.reply_to(message, "❌ Geçersiz ürün."); return
        
        history = price_history.get(item_code, [])
        if not history or len(history) < 2: bot.reply_to(message, "📉 Yeterli veri yok."); return

        # --- Ayarlar & Renkler ---
        width, height = 1000, 600
        bg_color = (15, 23, 42, 255) # Modern Koyu Lacivert
        grid_color = (30, 41, 59, 255)
        text_color = (148, 163, 184, 255)
        highlight_color = (255, 255, 255, 255)
        
        img = Image.new('RGBA', (width, height), bg_color)
        draw = ImageDraw.Draw(img)
        
        try:
            font_path = "arial.ttf"
            if not os.path.exists(font_path): font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            title_font = ImageFont.truetype(font_path, 32)
            price_font = ImageFont.truetype(font_path, 48)
            label_font = ImageFont.truetype(font_path, 16)
            indicator_font = ImageFont.truetype(font_path, 20)
        except:
            title_font = ImageFont.load_default()
            price_font = ImageFont.load_default()
            label_font = ImageFont.load_default()
            indicator_font = ImageFont.load_default()

        # --- Veri Hazırlığı ---
        current_price = history[-1]
        start_price = history[0]
        change = current_price - start_price
        change_pct = (change / start_price) * 100 if start_price != 0 else 0
        
        is_up = change >= 0
        main_color = (34, 197, 94, 255) if is_up else (239, 68, 68, 255) # Yeşil / Kırmızı
        
        min_p, max_p = min(history), max(history)
        padding_y = (max_p - min_p) * 0.2 if max_p != min_p else 10
        min_y, max_y = min_p - padding_y, max_p + padding_y
        
        margin_left, margin_right, margin_top, margin_bottom = 80, 40, 120, 60
        graph_w = width - margin_left - margin_right
        graph_h = height - margin_top - margin_bottom
        
        # --- Başlık ve Fiyat Bilgisi ---
        item_name = TRADE_GOODS[item_code]['name']
        draw.text((margin_left, 30), item_name, font=title_font, fill=text_color)
        draw.text((margin_left, 70), f"{current_price} $", font=price_font, fill=highlight_color)
        
        sign = "+" if is_up else ""
        change_text = f"{sign}{change} ({sign}%{abs(change_pct):.2f})"
        draw.text((margin_left + 250, 85), change_text, font=indicator_font, fill=main_color)

        # --- İndikatörler (RSI & SMA) ---
        ind = calculate_indicators(history)
        rsi = ind['rsi']
        sma = ind['sma']
        
        rsi_color = (34, 197, 94, 255) if 30 <= rsi <= 70 else (239, 68, 68, 255)
        draw.text((width - 250, 40), f"RSI (14): {rsi:.1f}", font=indicator_font, fill=rsi_color)
        draw.text((width - 250, 70), f"SMA (5): {sma:.1f}", font=indicator_font, fill=(56, 189, 248, 255))

        # --- Izgara ve Eksenler ---
        steps = 5
        for i in range(steps + 1):
            y_val = min_y + (max_y - min_y) * (i / steps)
            y_pos = height - margin_bottom - ((y_val - min_y) / (max_y - min_y) * graph_h)
            draw.line([(margin_left, y_pos), (width - margin_right, y_pos)], fill=grid_color, width=1)
            draw.text((20, y_pos - 10), f"{int(y_val)}", font=label_font, fill=text_color)

        # --- Grafik Çizimi ---
        points = []
        step_x = graph_w / (len(history) - 1)
        for i, price in enumerate(history):
            x = margin_left + (i * step_x)
            y = height - margin_bottom - ((price - min_y) / (max_y - min_y) * graph_h)
            points.append((x, y))
            
        if len(points) > 1:
            # Alt Alanı Doldurma (Yarı Saydam)
            overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)
            
            poly_points = [(margin_left, height - margin_bottom)] + points + [(points[-1][0], height - margin_bottom)]
            fill_color = main_color[:3] + (40,) # Düşük opaklık
            overlay_draw.polygon(poly_points, fill=fill_color)
            
            img = Image.alpha_composite(img, overlay)
            draw = ImageDraw.Draw(img)

            # Ana Çizgi
            draw.line(points, fill=main_color, width=4)
            
            # SMA Çizgisi (Hareketli Ortalama)
            sma_points = []
            sma_period = 5
            for i in range(len(history)):
                if i < sma_period - 1:
                    sma_points.append(None)
                    continue
                window = history[i - sma_period + 1 : i + 1]
                val = sum(window) / sma_period
                x = margin_left + (i * step_x)
                y = height - margin_bottom - ((val - min_y) / (max_y - min_y) * graph_h)
                sma_points.append((x, y))
            
            valid_sma = [p for p in sma_points if p is not None]
            if len(valid_sma) > 1:
                draw.line(valid_sma, fill=(56, 189, 248, 255), width=2)

            # Son Noktayı Vurgula
            lx, ly = points[-1]
            draw.ellipse((lx-6, ly-6, lx+6, ly+6), fill=highlight_color, outline=main_color, width=2)
        
        # --- Alt Bilgi ---
        draw.text((width/2 - 50, height - 30), "Zaman (Son 20 Veri)", font=label_font, fill=text_color)

        bio = io.BytesIO(); img.save(bio, 'PNG'); bio.seek(0)
        bot.send_photo(message.chat.id, bio, caption=f"📊 **{item_name}** Detaylı Piyasa Analizi")

    @bot.message_handler(commands=['dedikodu'])
    def buy_rumor_command(message): buy_rumor(message)

    @bot.message_handler(commands=['grafik_detay'])
    def show_detailed_graph_command(message): show_detailed_graph(message)

    @bot.message_handler(commands=['grafik'])
    def show_market_graph(message):
        text = "📊 **PİYASA FİYAT KONUMU**\n_(Min - Max Aralığı)_\n\n"
        with market_lock:
            for code, data in TRADE_GOODS.items():
                price = market_prices.get(code, data["base"])
                ratio = (price - data["min"]) / (data["max"] - data["min"]) if data["max"] > data["min"] else 0.5
                filled = int(ratio * 10)
                bar = "🟦" * filled + "⬜" * (10 - filled)
                text += f"**{data['name']}**: {price} $\n{bar} (%{int(ratio*100)})\n\n"
        bot.send_message(message.chat.id, text, parse_mode="Markdown")

    @bot.message_handler(commands=['analiz'])
    def market_analysis(message):
        user_id = str(message.from_user.id)
        if users[user_id].get("money", 0) < 200: bot.reply_to(message, "❌ Analiz için 200 $ gerekli."); return
        users[user_id]["money"] -= 200; save_users()
        
        text = "🧠 **TEKNİK ANALİZ (RSI & SMA)**\n\n"
        with market_lock:
            for code, data in TRADE_GOODS.items():
                ind = calculate_indicators(price_history.get(code, []))
                price = market_prices.get(code, data["base"])
                signal = "⚪ Nötr"
                if ind["rsi"] < 30: signal = "🟢 **GÜÇLÜ AL**"
                elif ind["rsi"] > 70: signal = "🔴 **GÜÇLÜ SAT**"
                elif price > ind["sma"]: signal = "📈 **AL** (Trend Yukarı)"
                elif price < ind["sma"]: signal = "📉 **SAT** (Trend Aşağı)"
                text += f"🔸 **{data['name']}** ({price}$)\n   └ Sinyal: {signal}\n"
        bot.reply_to(message, text, parse_mode="Markdown")

    @bot.message_handler(commands=['kara_borsa'])
    def black_market_menu(message):
        text = "🕵️ **KARA BORSA**\nFiyatlar %60 ama yakalanırsan paran yanar!\n\n"
        with market_lock:
            for code, data in TRADE_GOODS.items():
                text += f"▫️ {data['name']}: {int(market_prices[code]*0.6)} $\n"
        text += "\n🛒 `/kacak_al <mal> <adet>`"
        bot.send_message(message.chat.id, text, parse_mode="Markdown")

    @bot.message_handler(commands=['kacak_al'])
    def buy_illegal(message):
        user_id = str(message.from_user.id)
        try: item, amount = message.text.split()[1], int(message.text.split()[2])
        except: return
        if item not in TRADE_GOODS or amount <= 0: return
        
        price = int(market_prices[item] * 0.6)
        cost = price * amount
        if users[user_id].get("money", 0) < cost: bot.reply_to(message, "❌ Paran yetmiyor!"); return
        
        if random.random() < 0.30:
            users[user_id]["money"] -= cost; save_users()
            bot.reply_to(message, f"🚨 **POLİS BASKINI!** Paranı kaptırdın! (-{cost} $)")
        else:
            users[user_id]["money"] -= cost
            users[user_id].setdefault("inventory", {})[item] = users[user_id].get("inventory", {}).get(item, 0) + amount
            save_users()
            bot.reply_to(message, f"🕵️ **Başarılı!** {amount} {TRADE_GOODS[item]['name']} zulaladın.")

    @bot.message_handler(commands=['borsa'])
    def check_market(message):
        if hasattr(message, 'message'): # CallbackQuery ise (Yenile butonu)
            chat_id = message.message.chat.id
            user_id = str(message.from_user.id)
            try: 
                bot.delete_message(chat_id, message.message.message_id)
                bot.answer_callback_query(message.id) # Yükleniyor simgesini durdur
            except: pass
        else: # Normal mesaj ise (/borsa komutu)
            chat_id = message.chat.id
            user_id = str(message.from_user.id)
        
        try:
            photo = create_market_image(users.get(user_id))
            markup = InlineKeyboardMarkup().add(
                InlineKeyboardButton("🔄 Yenile", callback_data="market_refresh"), 
                InlineKeyboardButton("🤫 Dedikodu Al (100$)", callback_data="market_rumor"), 
                InlineKeyboardButton("📊 Detaylı Grafik", callback_data="market_graph_menu")
            )
            bot.send_photo(chat_id, photo, caption="🛒 **İşlemler:**\n`/al <mal> <adet>` | `/sat <mal> <adet>`\n`/emir_ver` | `/portfoyum`", reply_markup=markup)
        except Exception as e:
            bot.send_message(chat_id, f"Borsa görseli oluşturulurken hata: {e}")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("market_"))
    def market_actions(call):
        if call.data == "market_refresh": check_market(call)
        elif call.data == "market_rumor": 
            call.message.from_user.id = call.from_user.id
            buy_rumor(call.message)
        elif call.data == "market_graph_menu":
            markup = InlineKeyboardMarkup(row_width=2).add(*[InlineKeyboardButton(d["name"], callback_data=f"show_graph_{c}") for c, d in TRADE_GOODS.items()])
            bot.send_message(call.message.chat.id, "📊 Hangi ürünün grafiğini görmek istersin?", reply_markup=markup)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("show_graph_"))
    def show_graph_callback(call):
        call.message.text = f"/grafik_detay {call.data.replace('show_graph_', '')}"
        call.message.from_user.id = call.from_user.id
        show_detailed_graph(call.message)

    @bot.message_handler(commands=['al', 'sat'])
    def trade_item(message):
        user_id = str(message.from_user.id)
        try:
            cmd, item_code, amount_str = message.text.lower().split()
        except: bot.reply_to(message, "⚠️ Kullanım: `/(al|sat) <mal> <adet|hepsi>`"); return
        if item_code not in TRADE_GOODS: bot.reply_to(message, "❌ Böyle bir mal yok!"); return
        
        price = market_prices[item_code]
        user_money = users[user_id].get("money", 0)
        user_inv = users[user_id].setdefault("inventory", {})

        if cmd == "/al":
            amount = (user_money // price) if amount_str == "hepsi" else int(amount_str)
            if amount <= 0: bot.reply_to(message, "❌ Alım için miktar veya para yetersiz."); return
            total_cost, tax = price * amount, int(price * amount * 0.02)
            if user_money < total_cost + tax: bot.reply_to(message, f"❌ Yetersiz Bakiye! Gerekli: {total_cost + tax} $"); return
            
            user_inv[item_code] = user_inv.get(item_code, 0) + amount
            p_item = users[user_id].setdefault("portfolio", {}).setdefault(item_code, {"amount": 0, "total_cost": 0})
            p_item["amount"] += amount; p_item["total_cost"] += total_cost
            users[user_id]["money"] -= (total_cost + tax)
            market_volumes[item_code] = market_volumes.get(item_code, 0) + amount
            bot.reply_to(message, f"✅ **Alım Başarılı!**\n📥 {amount} {TRADE_GOODS[item_code]['name']} alındı.\n💰 Tutar: {total_cost} $ | 🏛️ Komisyon: -{tax} $")
            if total_cost >= 5000: bot.send_message(message.chat.id, f"🚨 **BALİNA ALARMI!** 🐋\n**{users[user_id]['name']}** {amount} adet {TRADE_GOODS[item_code]['name']} topladı!")
        elif cmd == "/sat":
            amount = user_inv.get(item_code, 0) if amount_str == "hepsi" else int(amount_str)
            if amount <= 0 or user_inv.get(item_code, 0) < amount: bot.reply_to(message, "❌ Satacak malın yok veya yetersiz."); return
            
            total_gain, tax = price * amount, int(price * amount * 0.02)
            user_inv[item_code] -= amount
            users[user_id]["money"] += (total_gain - tax)
            if "portfolio" in users[user_id] and item_code in users[user_id]["portfolio"]:
                p_item = users[user_id]["portfolio"][item_code]
                if p_item["amount"] > 0:
                    p_item["total_cost"] -= (p_item["total_cost"] / p_item["amount"]) * amount
                    p_item["amount"] -= amount
                    if p_item["amount"] < 1: del users[user_id]["portfolio"][item_code]
            market_volumes[item_code] = market_volumes.get(item_code, 0) - amount
            bot.reply_to(message, f"✅ **Satış Başarılı!**\n📤 {amount} {TRADE_GOODS[item_code]['name']} satıldı.\n💵 Net Kazanç: {total_gain - tax} $")
            if total_gain >= 5000: bot.send_message(message.chat.id, f"🚨 **BALİNA ALARMI!** 🐋\n**{users[user_id]['name']}** {amount} adet {TRADE_GOODS[item_code]['name']} sattı!")

        users[user_id].setdefault("orders", []).append({"type": f"{cmd[1:].upper()}IM", "item": TRADE_GOODS[item_code]['name'], "amount": amount, "price": price, "total": price*amount, "date": datetime.now().strftime("%Y-%m-%d %H:%M")})
        if len(users[user_id]["orders"]) > 20: users[user_id]["orders"].pop(0)
        save_users(); save_market_data()

    @bot.message_handler(commands=['kaz'])
    def mine_resource(message):
        user_id = str(message.from_user.id)
        last_mine = users[user_id].get("last_mine_time")
        if last_mine and (datetime.utcnow() - datetime.strptime(last_mine, "%Y-%m-%d %H:%M:%S")).total_seconds() < 900:
            remaining = int((900 - (datetime.utcnow() - datetime.strptime(last_mine, "%Y-%m-%d %H:%M:%S")).total_seconds()) / 60)
            bot.reply_to(message, f"⏳ Maden yorgun! {remaining} dakika sonra tekrar gel."); return

        wait_msg = bot.reply_to(message, "⛏️ **Madenciler iş başında...**"); time.sleep(2)
        users[user_id]["last_mine_time"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        users[user_id]["total_mines"] = users[user_id].get("total_mines", 0) + 1
        has_pickaxe = users[user_id].get("has_pickaxe", False)
        
        if random.random() < (0.02 if has_pickaxe else 0.01):
            users[user_id]["money"] = users[user_id].get("money", 0) + 5000
            msg = "🏺 **EFSANEVİ KEŞİF!** Antik bir hazine buldun! Değeri: +5000 $"
        else:
            roll = random.randint(1, 100) + (10 if has_pickaxe else 0)
            inv = users[user_id].setdefault("inventory", {})
            if roll > 95: inv["elmas"] = inv.get("elmas", 0) + 1; msg = "💎 **İNANILMAZ!** Bir **Elmas** buldun!"
            elif roll > 75: amount = random.randint(1, 2); inv["altin"] = inv.get("altin", 0) + amount; msg = f"✨ {amount} adet **Altın** buldun."
            elif roll > 40: amount = random.randint(2, 5); inv["demir"] = inv.get("demir", 0) + amount; msg = f"⛏️ {amount} adet **Demir** çıkardın."
            elif roll > 15: msg = "💨 Maalesef sadece toz ve toprak çıktı..."
            else:
                if has_pickaxe and random.random() > 0.5: msg = "⚠️ Göçük oldu ama **Elmas Kazman** seni korudu!"
                else: users[user_id]["lives"] -= 1; msg = "💥 **GÖÇÜK!** Üzerine çöktü. (-1 Can ❤️)"
        
        update_quest_progress(user_id, "mine"); save_users()
        bot.edit_message_text(msg, message.chat.id, wait_msg.message_id)

    @bot.message_handler(commands=['banka'])
    def bank_menu(message):
        u = users[str(message.from_user.id)]
        text = f"🏦 **MERKEZ BANKASI** 🏦\n\n👛 Cüzdan: {u.get('money', 0)} $\n💳 Banka Hesabı: {u.get('bank_balance', 0)} $\n\n📈 Günlük Faiz: %5\n\n📉 Kredi Borcu: {u.get('loan', 0)} $\n\n**İşlemler:**\n`/kredi <miktar>` | `/kredi_ode <miktar>`\n`/yatir <miktar>` | `/cek <miktar>`"
        bot.send_message(message.chat.id, text, parse_mode="Markdown")

    @bot.message_handler(commands=['yatir'])
    def deposit_money(message):
        user_id = str(message.from_user.id)
        try: amount = int(message.text.split()[1])
        except: bot.reply_to(message, "⚠️ Kullanım: `/yatir <miktar>`"); return
        if amount <= 0: return
        if users[user_id].get("money", 0) < amount: bot.reply_to(message, "❌ Cüzdanında bu kadar para yok!"); return
        users[user_id]["money"] -= amount
        users[user_id]["bank_balance"] = users[user_id].get("bank_balance", 0) + amount
        save_users()
        bot.reply_to(message, f"✅ Bankaya {amount} $ yatırıldı.\nYeni Banka Bakiyesi: {users[user_id]['bank_balance']} $")

    @bot.message_handler(commands=['cek'])
    def withdraw_money(message):
        user_id = str(message.from_user.id)
        try: amount = int(message.text.split()[1])
        except: bot.reply_to(message, "⚠️ Kullanım: `/cek <miktar>`"); return
        if amount <= 0: return
        if users[user_id].get("bank_balance", 0) < amount: bot.reply_to(message, "❌ Bankada bu kadar paran yok!"); return
        users[user_id]["bank_balance"] -= amount
        users[user_id]["money"] = users[user_id].get("money", 0) + amount
        save_users()
        bot.reply_to(message, f"✅ Bankadan {amount} $ çekildi.\nYeni Cüzdan Bakiyesi: {users[user_id]['money']} $")

    @bot.message_handler(commands=['kredi'])
    def take_loan(message):
        user_id = str(message.from_user.id)
        try: amount = int(message.text.split()[1])
        except: bot.reply_to(message, "⚠️ Kullanım: `/kredi <miktar>`"); return
        if amount <= 0: return
        level, max_loan, current_loan = users[user_id].get("level", 1), users[user_id].get("level", 1) * 5000, users[user_id].get("loan", 0)
        if current_loan + amount > max_loan: bot.reply_to(message, f"❌ Kredi limitin yetersiz! (Maks: {max_loan} $)"); return
        users[user_id]["loan"] = current_loan + amount
        users[user_id]["money"] = users[user_id].get("money", 0) + amount
        save_users()
        bot.reply_to(message, f"✅ Kredi Onaylandı! Hesaba geçen: {amount} $\nToplam Borç: {users[user_id]['loan']} $")

    @bot.message_handler(commands=['kredi_ode'])
    def pay_loan(message):
        user_id = str(message.from_user.id)
        current_loan = users[user_id].get("loan", 0)
        if current_loan <= 0: bot.reply_to(message, "🎉 Borcun yok!"); return
        try: amount = int(message.text.split()[1])
        except: amount = current_loan
        if amount <= 0: return
        if amount > current_loan: amount = current_loan
        if users[user_id].get("money", 0) < amount: bot.reply_to(message, f"❌ Yetersiz Bakiye!"); return
        users[user_id]["money"] -= amount
        users[user_id]["loan"] -= amount
        save_users()
        bot.reply_to(message, f"✅ Ödeme Başarılı! Ödenen: {amount} $\nKalan Borç: {users[user_id]['loan']} $")

    @bot.message_handler(commands=['transfer'])
    def transfer_money(message):
        user_id = str(message.from_user.id)
        try:
            args = message.text.split()
            target_input, amount = args[1], int(args[2])
        except: bot.reply_to(message, "⚠️ Kullanım: `/transfer <@KullanıcıAdı/ID> <Miktar>`"); return
        if amount <= 0: return
        if users[user_id].get("money", 0) < amount: bot.reply_to(message, f"❌ Yetersiz bakiye!"); return
        
        target_id = next((uid for uid, u in users.items() if u.get("username") == target_input.lstrip("@") or uid == target_input), None)
        if not target_id: bot.reply_to(message, "❌ Kullanıcı bulunamadı."); return
        if target_id == user_id: bot.reply_to(message, "❌ Kendine para gönderemezsin."); return

        tax, net_amount = int(amount * 0.05), amount - int(amount * 0.05)
        users[user_id]["money"] -= amount
        users[target_id]["money"] = users[target_id].get("money", 0) + net_amount
        save_users()
        bot.reply_to(message, f"✅ Transfer Başarılı!\n📤 Gönderilen: {amount} $\n🏛️ Vergi: -{tax} $\n📥 Alıcıya Geçen: {net_amount} $")
        try: bot.send_message(target_id, f"💸 **PARA GELDİ!**\n@{users[user_id].get('username', 'Biri')} sana {net_amount} $ gönderdi.")
        except: pass

    @bot.message_handler(commands=['portfoyum'])
    def show_portfolio(message):
        user_id = str(message.from_user.id)
        if "portfolio" not in users[user_id]: users[user_id]["portfolio"] = {}; save_users()
        try:
            photo, total_value, total_pl = create_portfolio_image(users[user_id])
            initial_cost = total_value - total_pl
            pl_percent = (total_pl / initial_cost * 100) if initial_cost != 0 else 0
            pl_sign = "+" if total_pl >= 0 else ""
            caption = f"💰 **Portföy Özeti**\n\n**Toplam Değer:** {total_value:.0f} $\n**Toplam Kar/Zarar:** {pl_sign}{total_pl:.0f} $ ({pl_sign}{pl_percent:.2f}%)"
            bot.send_photo(message.chat.id, photo, caption=caption, parse_mode="Markdown")
        except Exception as e:
            bot.reply_to(message, f"Portföy hatası: {e}")

    @bot.message_handler(commands=['emir_ver'])
    def set_limit_order(message):
        user_id = str(message.from_user.id)
        try:
            _, order_type, item_code, target_price, amount = message.text.lower().split()
            target_price, amount = int(target_price), int(amount)
        except: bot.reply_to(message, "⚠️ Kullanım: `/emir_ver <al/sat> <mal> <fiyat> <adet>`"); return
        if order_type not in ["al", "sat"] or item_code not in TRADE_GOODS or target_price <= 0 or amount <= 0:
            bot.reply_to(message, "❌ Geçersiz parametreler."); return
        
        users[user_id].setdefault("limit_orders", []).append({
            "id": str(uuid.uuid4())[:6], "type": order_type.upper(), "item": item_code, 
            "target": target_price, "amount": amount, "date": datetime.now().strftime("%Y-%m-%d %H:%M")
        }); save_users()
        bot.reply_to(message, f"✅ Limit Emir Girildi!", parse_mode="Markdown")

    @bot.message_handler(commands=['emir', 'emirler'])
    def order_history(message):
        user_id = str(message.from_user.id)
        orders, limit_orders = users[user_id].get("orders", []), users[user_id].get("limit_orders", [])
        if not orders and not limit_orders: bot.reply_to(message, "📜 Henüz bir işlem veya emir yok."); return
        
        text = "📋 BEKLEYEN EMİRLER\n"
        if limit_orders:
            for lo in limit_orders: text += f"🔹 {lo['id']} | {lo['type']} {TRADE_GOODS[lo['item']]['name']} | Hedef: {lo['target']}$\n"
            text += "\n(İptal: /emir_iptal <ID>)\n"
        else: text += "(Yok)\n"
        
        text += "\n📜 GEÇMİŞ İŞLEMLER\n"
        for order in reversed(orders[-10:]): text += f"▪️ {order['type']} {order['item']} x{order['amount']} @{order['price']}$\n"
        bot.send_message(message.chat.id, text)

    @bot.message_handler(commands=['emir_iptal'])
    def cancel_order(message):
        user_id = str(message.from_user.id)
        try: order_id_to_cancel = message.text.split()[1]
        except: bot.reply_to(message, "⚠️ Kullanım: `/emir_iptal <ID>`"); return
        
        user_orders = users[user_id].get("limit_orders", [])
        order_found = next((order for order in user_orders if order["id"] == order_id_to_cancel), None)
        if order_found:
            users[user_id]["limit_orders"].remove(order_found); save_users()
            bot.reply_to(message, f"✅ `{order_id_to_cancel}` nolu emir iptal edildi.", parse_mode="Markdown")
        else: bot.reply_to(message, "❌ Emir bulunamadı.")

    @bot.message_handler(commands=['zenginler'])
    def rich_list(message):
        leaderboard = []
        with market_lock:
            for uid, u in list(users.items()):
                net_worth = u.get("money", 0) + u.get("bank_balance", 0) + sum(count * market_prices.get(code, 0) for code, count in u.get("inventory", {}).items() if code in TRADE_GOODS)
                badges = get_badges(u)
                leaderboard.append((uid, u, net_worth, badges))
        
        leaderboard.sort(key=lambda x: x[2], reverse=True)
        
        try:
            photo = create_rich_list_image(leaderboard[:10])
            bot.send_photo(message.chat.id, photo, caption="💸 **Kapalıçarşı'nın En Zenginleri**\n_(Nakit + Banka + Varlıklar)_")
        except Exception as e:
            bot.reply_to(message, f"Liderlik tablosu oluşturulamadı: {e}")
            text = "💸 **Zenginler Listesi**\n\n" + "\n".join([f"{i+1}. {d[1].get('name')}: {int(d[2])} $" for i, d in enumerate(leaderboard[:10])])
            bot.send_message(message.chat.id, text)

    @bot.message_handler(commands=['iflas'])
    def declare_bankruptcy(message):
        user_id = str(message.from_user.id)
        if len(message.text.split()) < 2 or message.text.split()[1] != "ONAY":
            bot.reply_to(message, "⚠️ **DİKKAT!** İflas edersen her şeyin sıfırlanır (para, mal, borç).\nOnaylamak için: `/iflas ONAY`", parse_mode="Markdown"); return
        u = users[user_id]
        u.update({"money": 1000, "bank_balance": 0, "loan": 0, "portfolio": {}, "inventory": {}, "orders": [], "limit_orders": []})
        save_users()
        bot.reply_to(message, "🏳️ **İFLAS BAYRAĞI ÇEKİLDİ!**\nSana yeni bir başlangıç için 1000 $ verildi.")

    @bot.message_handler(commands=['market'])
    def market_menu(message):
        if not users.get(str(message.from_user.id), {}).get("is_approved", True): return
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("💡 %50 Joker (100 $)", callback_data="buy_joker_50"))
        markup.add(InlineKeyboardButton("⏭ Pas Geç (50 $)", callback_data="buy_joker_pass"))
        markup.add(InlineKeyboardButton("👥 Seyirci (150 $)", callback_data="buy_joker_audience"))
        markup.add(InlineKeyboardButton("🤖 AI İpucu (200 $)", callback_data="buy_joker_ai"))
        markup.add(InlineKeyboardButton("❤️ +1 Can (1000 $)", callback_data="buy_life"))
        markup.add(InlineKeyboardButton("🎁 Şans Kutusu (500 $)", callback_data="buy_box"))
        markup.add(InlineKeyboardButton("⛏️ Elmas Kazma (5000 $)", callback_data="buy_pickaxe"))
        markup.add(InlineKeyboardButton("🛡️ Seri Koruyucu (2000 $)", callback_data="buy_streak_saver"))
        bot.send_message(message.chat.id, "🛒 **MARKET**\nPuanlarını harcayarak güçlenebilirsin!", reply_markup=markup)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("buy_"))
    def market_buy(call):
        user_id = str(call.from_user.id)
        if user_id not in users: return
        item, money = call.data.replace("buy_", ""), users[user_id].get("money", 0)
        prices = {"joker_50": 100, "joker_pass": 50, "joker_audience": 150, "joker_ai": 200, "life": 1000, "box": 500, "pickaxe": 5000, "streak_saver": 2000}
        
        if money < prices.get(item, 0): bot.answer_callback_query(call.id, "❌ Yetersiz Bakiye!", show_alert=True); return
        users[user_id]["money"] -= prices[item]
        
        if item == "life": users[user_id]["lives"] += 1; msg = "✅ +1 Can alındı!"
        elif item == "pickaxe": users[user_id]["has_pickaxe"] = True; msg = "✅ Elmas Kazma alındı!"
        elif item == "box":
            reward = random.choice(["money_200", "money_1000", "life_1", "empty"])
            if reward == "money_200": users[user_id]["money"] += 200; msg = "🎁 Kutudan 200$ çıktı!"
            elif reward == "money_1000": users[user_id]["money"] += 1000; msg = "🎁 TEBRİKLER! 1000$ çıktı!"
            elif reward == "life_1": users[user_id]["lives"] += 1; msg = "🎁 Kutudan 1 Can çıktı!"
            else: msg = "🎁 Kutu boş çıktı..."
            bot.send_message(call.message.chat.id, msg)
        else:
            users[user_id].setdefault("inventory", {})[item] = users[user_id].get("inventory", {}).get(item, 0) + 1
            msg = f"✅ {item} alındı!"
        save_users(); bot.answer_callback_query(call.id, msg)

    @bot.message_handler(commands=['envanter'])
    def show_inventory(message):
        try: bot.send_photo(message.chat.id, create_inventory_image(users[str(message.from_user.id)]), caption="🎒 **Envanter Durumu**")
        except: bot.reply_to(message, "Envanter görüntülenemedi.")
