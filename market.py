import os
import random
import uuid
import time
from datetime import datetime, timedelta
import io
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from database import (
    users, save_users, market_prices, market_volumes, last_prices,
    price_history, market_news, market_trend, last_market_update,
    TRADE_GOODS, save_market_data, market_lock, data_lock, active_news_item,
    active_news_direction, active_global_modifier, last_news_update
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
    global market_prices, market_volumes, last_prices, market_news, market_trend, price_history, last_news_update, active_news_item, active_news_direction, active_global_modifier
    with market_lock:
        last_prices = market_prices.copy()
        if active_news_item is None or (datetime.now() - last_news_update).total_seconds() > 300:
            last_news_update = datetime.now()
            market_trend = random.choices([-1, 0, 1], weights=[0.3, 0.4, 0.3])[0]
            active_news_item = random.choice(list(TRADE_GOODS.keys()))
            active_news_direction = random.choice(["up", "down"])
            market_news = random.choice(NEWS_TEMPLATES[active_news_item][active_news_direction])
            
            event_roll = random.randint(1, 100)
            active_global_modifier = -0.25 if event_roll <= 3 else (0.25 if event_roll >= 97 else 0.0)
            if active_global_modifier == -0.25: market_news = "📉 **KARA GÜN!** Küresel kriz patlak verdi! Piyasalar çakılıyor!"
            elif active_global_modifier == 0.25: market_news = "🚀 **ALTIN ÇAĞ!** Yabancı yatırımcılar ülkeye akın etti!"
            print(f"📊 Piyasa Trendi: {market_trend}, Haber: {market_news}")

        trend_strength = random.uniform(0.01, 0.03)
        for code, data in TRADE_GOODS.items():
            change_percent = random.gauss(0, data["volatility"]) + (market_trend * trend_strength) + active_global_modifier
            if market_volumes.get(code, 0) != 0: change_percent += (market_volumes[code] * 0.002)
            if code == active_news_item: change_percent += random.uniform(0.05, 0.15) * (1 if active_news_direction == "up" else -1)
            
            limit = 0.30 if active_global_modifier != 0 else 0.10
            change_percent = max(-limit, min(change_percent, limit))
            price_change = int(market_prices[code] * change_percent) or (random.randint(1, 3) * (-1 if change_percent < 0 else 1))
            
            market_prices[code] = max(data["min"], min(market_prices[code] + price_change, data["max"]))
            price_history.setdefault(code, []).append(market_prices[code])
            if len(price_history[code]) > 20: price_history[code].pop(0)

        market_volumes = {k: 0 for k in TRADE_GOODS.keys()}
        check_limit_orders(bot)
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
    if count > 0: print(f"🏦 {count} kişiye faiz dağıtıldı.")

def create_market_image(user_data=None):
    num_items, row_height, header_height, footer_height = len(TRADE_GOODS), 80, 180, 60
    width, height = 1100, header_height + (num_items * row_height) + footer_height
    img = Image.new('RGB', (width, height), color=(25, 28, 36))
    draw = ImageDraw.Draw(img)
    try:
        font_path = "arial.ttf"
        if not os.path.exists(font_path): font_path = next((f for f in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"] if os.path.exists(f)), font_path)
        title_font, header_font, row_font, small_font = ImageFont.truetype(font_path, 42), ImageFont.truetype(font_path, 26), ImageFont.truetype(font_path, 24), ImageFont.truetype(font_path, 18)
    except:
        title_font, header_font, row_font, small_font = ImageFont.load_default(), ImageFont.load_default(), ImageFont.load_default(), ImageFont.load_default()

    draw.rectangle([(0, 0), (width, 100)], fill=(46, 204, 113)); draw.text((40, 25), "📈 KAPALIÇARŞI BORSASI", font=title_font, fill=(255, 255, 255))
    current_index, last_index = sum(market_prices.values()), sum(last_prices.values())
    idx_diff, idx_pct = current_index - last_index, (current_index - last_index) / last_index * 100 if last_index > 0 else 0
    idx_arrow = "▲" if idx_diff > 0 else ("▼" if idx_diff < 0 else "➖")
    draw.text((600, 35), f"ENDEKS: {current_index} {idx_arrow} %{abs(idx_pct):.2f}", font=header_font, fill=(240, 240, 240))
    draw.rectangle([(30, 120), (width-30, 170)], fill=(38, 43, 54)); draw.text((45, 135), f"📰 {market_news[:87] + '...' if len(market_news) > 90 else market_news}", font=row_font, fill=(220, 220, 220))
    
    y = 200; headers = ["ÜRÜN", "FİYAT", "DEĞİŞİM", "VARLIK", "DERİNLİK"]; x_pos = [40, 280, 450, 650, 850]
    for i, h in enumerate(headers): draw.text((x_pos[i], y), h, font=header_font, fill=(150, 150, 150))
    draw.line([(40, y + 40), (width-40, y + 40)], fill=(80, 80, 80), width=2)
    
    y += 60
    for code, data in TRADE_GOODS.items():
        price, old_price = market_prices.get(code, data["base"]), last_prices.get(code, data["base"])
        diff = price - old_price
        draw.rectangle([(40, y), (width-40, y+60)], fill=(38, 43, 54))
        draw.text((50, y+15), data['name'], font=row_font, fill=(255, 255, 255))
        draw.text((280, y+15), f"{price} $", font=row_font, fill=(255, 215, 0))
        diff_str, color = (f"▲ +{diff}", (46, 204, 113)) if diff > 0 else ((f"▼ {diff}", (231, 76, 60)) if diff < 0 else ("➖ 0", (149, 165, 166)))
        draw.text((450, y+15), diff_str, font=row_font, fill=color)
        user_stock = user_data.get("inventory", {}).get(code, 0) if user_data else 0
        draw.text((650, y+15), f"{user_stock} Adet", font=row_font, fill=((255, 255, 255) if user_stock > 0 else (100, 100, 100)))
        
        vol = market_volumes.get(code, 0); bar_x, bar_w, center_x = 850, 200, 850 + 100
        draw.rectangle([(bar_x, y+25), (bar_x + bar_w, y+40)], fill=(50, 50, 50)); draw.line([(center_x, y+20), (center_x, y+45)], fill=(150, 150, 150), width=1)
        bar_len = min(abs(vol) * 2, 100)
        if vol >= 0: draw.rectangle([(center_x, y+25), (center_x + bar_len, y+40)], fill=(46, 204, 113))
        else: draw.rectangle([(center_x - bar_len, y+25), (center_x, y+40)], fill=(231, 76, 60))
        y += row_height

    seconds_left = max(0, 90 - (datetime.now() - last_market_update).total_seconds())
    draw.text((width - 350, height - 40), f"⏳ Yenilenme: {int(seconds_left // 60)}dk {int(seconds_left % 60)}sn", font=small_font, fill=(100, 100, 100))
    bio = io.BytesIO(); img.save(bio, 'PNG'); bio.seek(0)
    return bio

def register_market_handlers(bot, tirtil_utils):
    """Ekonomi ile ilgili tüm komutları ve callback'leri bota kaydeder."""
    global get_badges, update_quest_progress
    get_badges = tirtil_utils['get_badges']
    update_quest_progress = tirtil_utils['update_quest_progress']

    @bot.message_handler(commands=['borsa'])
    def check_market(message):
        chat_id = message.chat.id
        if hasattr(message, 'message'): chat_id = message.message.chat.id; bot.delete_message(chat_id, message.message.message_id)
        try:
            photo = create_market_image(users.get(str(message.from_user.id)))
            markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔄 Yenile", callback_data="market_refresh"), InlineKeyboardButton("🤫 Dedikodu Al (100$)", callback_data="market_rumor"), InlineKeyboardButton("📊 Detaylı Grafik", callback_data="market_graph_menu"))
            bot.send_photo(chat_id, photo, caption="🛒 **İşlemler:**\n`/al <mal> <adet>` | `/sat <mal> <adet>`\n`/emir_ver` | `/portfoyum`", reply_markup=markup)
        except Exception as e:
            bot.send_message(chat_id, f"Borsa görseli oluşturulurken hata: {e}")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("market_"))
    def market_actions(call):
        if call.data == "market_refresh": check_market(call)
        elif call.data == "market_rumor": call.message.from_user.id = call.from_user.id; buy_rumor(call.message)
        elif call.data == "market_graph_menu":
            markup = InlineKeyboardMarkup().add(*[InlineKeyboardButton(d["name"], callback_data=f"show_graph_{c}") for c, d in TRADE_GOODS.items()])
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

    # Diğer market komutları (banka, kredi, portfoy, vs.) buraya eklenecek...
