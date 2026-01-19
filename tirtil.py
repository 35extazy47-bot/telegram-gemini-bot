import os
import json
import threading
from threading import Timer
import time
import random
from datetime import datetime, timedelta, timezone
import io
import requests
import html
from dotenv import load_dotenv
from flask import Flask
from telebot import TeleBot, types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from google import genai
from PIL import Image, ImageDraw, ImageFont

import database
from database import *
from quiz import register_quiz_handlers
from market import register_market_handlers, update_market, apply_bank_interest

# --- Bot ve API Başlatma ---
bot = TeleBot(BOT_TOKEN)
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# --- Yardımcı Fonksiyonlar ---
def safe_generate_content(prompt_content):
    """Modeller arası geçiş yaparak hata riskini azaltır."""
    if not client: return type('obj', (object,), {'text': '⚠️ AI Kapalı.'})()
    # Sırasıyla bu modelleri dener. Biri çalışırsa cevap döner.
    models = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash", "gemini-1.5-flash"]
    for model in models:
        try:
            return client.models.generate_content(model=model, contents=prompt_content)
        except Exception as e: print(f"⚠️ {model} hatası: {e}")
    raise Exception("Tüm Gemini modelleri başarısız oldu.")

def escape_md(text): return str(text).replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[")

def get_rank(level, username=None):
    if username == DEVELOPER_USERNAME: return "Kurucu 👑"
    if level >= 20: return "Bilge 🧙‍♂️"
    elif level >= 10: return "Usta ⚔️"
    elif level >= 5: return "Çırak 🛠️"
    else: return "Acemi 👶"

def get_badges(user_data):
    badges = []
    if user_data.get("total_mines", 0) >= 50: badges.append("⛏️ Madenci")
    if user_data.get("duel_wins", 0) >= 10: badges.append("⚔️ Gladyatör")
    if user_data.get("total_correct", 0) >= 50: badges.append("🧠 Bilgin")
    if user_data.get("money", 0) >= 100000: badges.append("💸 Baron")
    if user_data.get("is_weekly_winner", False):
        badges.append("🏆 Haftanın Lideri")
    return " | ".join(badges) if badges else "Yok"

def check_daily_limit(user_id):
    if users.get(str(user_id), {}).get("username") == DEVELOPER_USERNAME: return True
    today = datetime.now().strftime("%Y-%m-%d")
    user_data = users[str(user_id)]
    if user_data.get("last_gemini_date") != today:
        user_data["last_gemini_date"] = today; user_data["daily_gemini_count"] = 0
    if user_data.get("daily_gemini_count", 0) >= 3: return False
    user_data["daily_gemini_count"] = user_data.get("daily_gemini_count", 0) + 1
    save_users(); return True

def generate_daily_quests(user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    if users[str(user_id)].get("quests", {}).get("date") == today: return
    users[str(user_id)]["quests"] = {
        "date": today,
        "list": [
            {"type": "quiz_correct", "target": 10, "current": 0, "desc": "10 Soru Doğru Bil", "reward": 150, "done": False},
            {"type": "mine", "target": 3, "current": 0, "desc": "3 Kez Madene İn", "reward": 100, "done": False},
            {"type": "duel_win", "target": 1, "current": 0, "desc": "1 Düello Kazan", "reward": 200, "done": False}
        ]
    }; save_users()

def update_quest_progress(user_id, q_type):
    generate_daily_quests(user_id)
    for q in users[str(user_id)]["quests"]["list"]:
        if q["type"] == q_type and not q["done"]:
            q["current"] += 1
            if q["current"] >= q["target"]:
                q["done"] = True; users[str(user_id)]["exp"] += q["reward"]
                try: bot.send_message(user_id, f"✅ **GÖREV TAMAMLANDI!**\n📜 {q['desc']}\n💰 Ödül: +{q['reward']} EXP")
                except: pass
            save_users(); break

def get_user_profile_image(user_id):
    try:
        photos = bot.get_user_profile_photos(user_id)
        if photos.total_count > 0:
            file_info = bot.get_file(photos.photos[0][-1].file_id)
            return Image.open(io.BytesIO(bot.download_file(file_info.file_path)))
    except: pass
    return None

def create_profile_image(user_id, user_data):
    width, height = 600, 400
    img = Image.new('RGB', (width, height), color=(35, 39, 42))
    draw = ImageDraw.Draw(img)
    try:
        font_path = "arial.ttf"
        if not os.path.exists(font_path): font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        name_font, header_font, normal_font, small_font = ImageFont.truetype(font_path, 32), ImageFont.truetype(font_path, 24), ImageFont.truetype(font_path, 18), ImageFont.truetype(font_path, 14)
    except:
        name_font, header_font, normal_font, small_font = ImageFont.load_default(), ImageFont.load_default(), ImageFont.load_default(), ImageFont.load_default()

    name, level, exp, money = user_data.get('name', 'Bilinmiyor')[:20], user_data.get('level', 1), user_data.get('exp', 0), user_data.get('money', 0)
    target_xp, rank = level * 100, get_rank(level, user_data.get('username'))
    
    profile_pic = get_user_profile_image(user_id)
    text_x = 30
    if profile_pic:
        profile_pic = profile_pic.resize((80, 80)); mask = Image.new("L", (80, 80), 0)
        draw_mask = ImageDraw.Draw(mask); draw_mask.ellipse((0, 0, 80, 80), fill=255)
        img.paste(profile_pic, (30, 30), mask); text_x = 130

    draw.text((text_x, 30), name, font=name_font, fill=(255,255,255))
    draw.text((text_x, 75), rank, font=header_font, fill=(0, 174, 255))
    draw.text((450, 20), f"Level {level}", font=name_font, fill=(255, 215, 0))
    draw.text((450, 60), f"{money} $", font=header_font, fill=(46, 204, 113))

    bar_x, bar_y, bar_w, bar_h = 30, 130, 540, 20
    draw.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], fill=(60,60,60))
    percent = min(exp / target_xp, 1.0)
    if percent > 0: draw.rectangle([bar_x, bar_y, bar_x + int(bar_w * percent), bar_y + bar_h], fill=(46,204,113))
    draw.text((bar_x, bar_y - 20), f"EXP: {exp} / {target_xp}", font=small_font, fill=(200,200,200))
    
    # Diğer istatistikler buraya eklenebilir
    
    bio = io.BytesIO(); img.save(bio, 'PNG'); bio.seek(0)
    return bio

def create_leaderboard_image(sorted_users):
    width, height = 800, 140 + (len(sorted_users) * 60)
    img = Image.new('RGB', (width, height), color=(35, 39, 42))
    draw = ImageDraw.Draw(img)
    
    try:
        font_path = "arial.ttf"
        if not os.path.exists(font_path): font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        title_font, row_font = ImageFont.truetype(font_path, 40), ImageFont.truetype(font_path, 26)
    except: title_font, row_font = ImageFont.load_default(), ImageFont.load_default()

    draw.text((220, 30), "🏆 LİDERLİK TABLOSU 🏆", font=title_font, fill=(255, 215, 0))
    draw.rectangle([(20, 90), (width-20, 140)], fill=(44, 47, 51))
    
    headers = ["#", "OYUNCU", "RÜTBE", "LEVEL", "EXP"]
    x_pos = [40, 130, 380, 580, 700]
    for i, h in enumerate(headers): draw.text((x_pos[i], 100), h, font=row_font, fill=(200, 200, 200))
        
    y = 160
    for i, (uid, data) in enumerate(sorted_users, 1):
        name = data.get("name", "Gizli")[:12]
        lvl, xp = str(data.get("level", 1)), str(data.get("exp", 0))
        rank = get_rank(int(lvl), data.get("username")).split()[0]
        
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
        draw.text((x_pos[2], y), rank, font=row_font, fill=color)
        draw.text((x_pos[3], y), lvl, font=row_font, fill=color)
        draw.text((x_pos[4], y), xp, font=row_font, fill=color)
        draw.line([(40, y+45), (width-40, y+45)], fill=(60, 60, 60), width=1)
        y += 60
        
    bio = io.BytesIO(); img.save(bio, 'PNG'); bio.seek(0)
    return bio

def create_weekly_leaderboard_image(sorted_users):
    width, height = 800, 140 + (len(sorted_users) * 60)
    img = Image.new('RGB', (width, height), color=(35, 39, 42))
    draw = ImageDraw.Draw(img)
    
    try:
        font_path = "arial.ttf"
        if not os.path.exists(font_path): font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        title_font, row_font = ImageFont.truetype(font_path, 40), ImageFont.truetype(font_path, 26)
    except: title_font, row_font = ImageFont.load_default(), ImageFont.load_default()

    draw.text((180, 30), "🏆 HAFTALIK LİDERLİK 🏆", font=title_font, fill=(153, 102, 255)) # Mor renk
    draw.rectangle([(20, 90), (width-20, 140)], fill=(44, 47, 51))
    
    headers = ["#", "OYUNCU", "ÇÖZÜLEN SORU"]
    x_pos = [40, 130, 580]
    for i, h in enumerate(headers): draw.text((x_pos[i], 100), h, font=row_font, fill=(200, 200, 200))
        
    y = 160
    for i, (uid, data) in enumerate(sorted_users, 1):
        name = data.get("name", "Gizli")[:15]
        solved = str(data.get("weekly_questions_solved", 0))
        
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
        draw.text((x_pos[2], y), solved, font=row_font, fill=color)
        draw.line([(40, y+45), (width-40, y+45)], fill=(60, 60, 60), width=1)
        y += 60
        
    bio = io.BytesIO(); img.save(bio, 'PNG'); bio.seek(0)
    return bio

def create_tarot_image(cards):
    width, height = 800, 450
    img = Image.new('RGB', (width, height), color=(25, 20, 40))
    draw = ImageDraw.Draw(img)
    try:
        font_path = "arial.ttf"
        if not os.path.exists(font_path): font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        title_font, label_font = ImageFont.truetype(font_path, 36), ImageFont.truetype(font_path, 20)
    except: title_font, label_font = ImageFont.load_default(), ImageFont.load_default()

    draw.text((260, 30), "🔮 TAROT FALI 🔮", font=title_font, fill=(186, 85, 211))
    positions = ["GEÇMİŞ", "ŞİMDİ", "GELECEK"]
    for i, card_name in enumerate(cards):
        x = 80 + (i * 240)
        draw.rectangle([(x, 100), (x + 180, 380)], fill=(48, 25, 52), outline=(255, 215, 0), width=3)
        draw.text((x + 50, 115), positions[i], font=label_font, fill=(200, 200, 200))
        draw.text((x + 20, 200), card_name, font=label_font, fill=(255, 255, 255))

    bio = io.BytesIO(); img.save(bio, 'PNG'); bio.seek(0)
    return bio

def send_morning_broadcast():
    for uid, u in users.items():
        try: bot.send_message(uid, f"☀️ **GÜNAYDIN {u.get('name', 'Dostum').upper()}!**\nBugün piyasalar hareketli, bol kazançlar! 🚀")
        except: pass

def give_weekly_reward():
    """Haftanın en çok soru çözen kullanıcısını bulur, ödüllendirir ve rozet verir."""
    print("🏆 Haftalık ödül süreci başladı...")
    
    # 1. Tüm kullanıcılardan 'Haftanın Lideri' rozetini kaldır
    for uid, u_data in users.items():
        if u_data.get('is_weekly_winner'):
            u_data['is_weekly_winner'] = False
            print(f"🏅 Eski şampiyon {u_data.get('name')} rozeti kaldırıldı.")

    winner_id = None
    max_solved = 0

    # 2. Geçen haftanın skorlarına göre yeni kazananı bul
    for uid, u_data in users.items():
        solved_count = u_data.get("last_week_questions_solved", 0)
        if solved_count > max_solved:
            max_solved = solved_count
            winner_id = uid

    # 3. Yeni kazanana ödül ve rozet ver (En az 5 soru çözme şartı)
    if winner_id and max_solved > 5:
        reward = 1000
        users[winner_id]["money"] = users[winner_id].get("money", 0) + reward
        users[winner_id]['is_weekly_winner'] = True
        
        winner_name = users[winner_id].get("name", "Bilinmiyor")
        print(f"🏆 Haftanın şampiyonu: {winner_name} ({max_solved} soru). Ödül: {reward} $ ve rozet verildi.")
        
        try:
            bot.send_message(winner_id, f"🏆 **HAFTANIN ŞAMPİYONU!** 🏆\n\nGeçen hafta en çok soruyu ({max_solved} adet) sen çözdün!\n\n💰 Ödülün: +{reward} $\n🏅 Rozet: **Haftanın Lideri** rozetini kazandın!")
        except Exception as e:
            print(f"Haftalık ödül mesajı gönderilemedi: {e}")
    else:
        print("🏆 Geçen hafta kimse yeterli soru çözmedi, ödül ve rozet verilmedi.")

    # 4. Tekrar ödül verilmemesi için geçen haftanın skorlarını sıfırla
    for uid in users:
        if "last_week_questions_solved" in users[uid]:
            users[uid]["last_week_questions_solved"] = 0
    save_users()
    print("🏆 Haftalık ödül süreci tamamlandı.")

# --- Admin & Genel Komutlar ---
@bot.message_handler(commands=['admin_panel'])
def admin_panel(message):
    if message.from_user.username != DEVELOPER_USERNAME: return

    user_count = len(users)
    total_questions_solved = sum(u.get("total_questions", 0) for u in users.values())
    active_today = sum(1 for u in users.values() if u.get("last_gemini_date") == datetime.now().strftime("%Y-%m-%d"))
    pending_count = sum(1 for u in users.values() if not u.get("is_approved", True))

    text = (
        f"👑 **YÖNETİCİ KONTROL MERKEZİ** 👑\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 **Toplam Kullanıcı:** {user_count}\n"
        f"🔥 **Bugün Aktif:** {active_today}\n"
        f"⏳ **Onay Bekleyen:** {pending_count}\n"
        f"📝 **Çözülen Soru:** {total_questions_solved}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        "👇 **İşlem Seçiniz:**"
    )

    markup = InlineKeyboardMarkup()
    # Satır 1: Kullanıcı Yönetimi
    markup.add(InlineKeyboardButton(f"⏳ Onay ({pending_count})", callback_data="admin_pending_list"), InlineKeyboardButton("👥 Üyeler", callback_data="admin_user_list"))
    # Satır 2: Özel Listeler
    markup.add(InlineKeyboardButton("🚫 Yasaklılar", callback_data="admin_banned_list"), InlineKeyboardButton("👑 VIP'ler", callback_data="admin_vip_list"))
    markup.add(InlineKeyboardButton("📉 Tüm Emirler", callback_data="admin_all_orders"), InlineKeyboardButton("📊 Eko. Analiz", callback_data="admin_economy_stats"))
    # Satır 3: İletişim & Anket
    markup.add(InlineKeyboardButton("📢 Duyuru", callback_data="admin_help_duyuru"), InlineKeyboardButton("📊 Anket", callback_data="admin_help_anket"))
    # Satır 4: Yönetim
    markup.add(InlineKeyboardButton("🎁 Hediye", callback_data="admin_help_hediye"), InlineKeyboardButton("🔨 Ban", callback_data="admin_help_ban"))
    markup.add(InlineKeyboardButton("💾 Yedek Al", callback_data="admin_backup"))

    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_"))
def admin_callbacks(call):
    if call.from_user.username != DEVELOPER_USERNAME: return

    if call.data == "admin_pending_list":
        pending = [(uid, u) for uid, u in users.items() if not u.get("is_approved", True)]
        if not pending: bot.answer_callback_query(call.id, "✅ Bekleyen yok!"); return
        bot.send_message(call.message.chat.id, f"⏳ **Onay Bekleyen {len(pending)} Kişi Var:**")
        for uid, u in pending:
            safe_name = escape_md(u.get('name', 'Bilinmiyor'))
            safe_username = escape_md(u.get('username', 'Yok'))
            info = f"👤 {safe_name}\n🆔 `{uid}`\n🔗 @{safe_username}"
            markup = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Onayla", callback_data=f"approve_{uid}"), InlineKeyboardButton("❌ Reddet", callback_data=f"reject_{uid}"))
            bot.send_message(call.message.chat.id, info, reply_markup=markup, parse_mode="Markdown")

    elif call.data == "admin_user_list":
        text = "📋 **Kayıtlı Üyeler Listesi**\n\n"
        for i, (uid, u) in enumerate(users.items(), 1):
            line = f"{i}. {escape_md(u.get('name'))} (@{escape_md(u.get('username'))}) - ID: `{uid}` - Lvl: {u.get('level', 1)}\n"
            if len(text + line) > 4000:
                bot.send_message(call.message.chat.id, text, parse_mode="Markdown"); text = ""
            text += line
        if text: bot.send_message(call.message.chat.id, text, parse_mode="Markdown")

    elif call.data == "admin_backup":
        try:
            users_json = json.dumps(users, ensure_ascii=False, indent=2)
            users_file = io.BytesIO(users_json.encode('utf-8'))
            users_file.name = f"users_backup_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.json"
            bot.send_document(call.message.chat.id, users_file, caption=f"💾 Yedek: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        except Exception as e: bot.send_message(call.message.chat.id, f"Yedek alınamadı: {e}")

    elif call.data == "admin_banned_list":
        text = "🚫 **Yasaklılar:**\n" + "\n".join([f"• {u.get('name')}" for u in users.values() if u.get("is_banned")])
        bot.send_message(call.message.chat.id, text if len(text) > 20 else "Yasaklı yok.")

    elif call.data == "admin_vip_list":
        vips = [u for u in users.values() if u.get("level", 1) >= 15]
        bot.send_message(call.message.chat.id, "👑 **VIP Üyeler:**\n" + "\n".join([f"• {u.get('name')}" for u in vips]) if vips else "VIP yok.")

    elif call.data == "admin_all_orders":
        text = "📉 **Bekleyen Emirler:**\n"
        for uid, u in users.items():
            for o in u.get("limit_orders", []):
                item_name = TRADE_GOODS.get(o['item'], {}).get('name', o['item'])
                text += f"👤 {escape_md(u.get('name'))}: {o['type']} {escape_md(item_name)} @ {o['target']}$\n"
        bot.send_message(call.message.chat.id, text if len(text) > 25 else "Emir yok.")

    elif call.data == "admin_economy_stats":
        total_money = sum(u.get("money", 0) for u in users.values())
        total_bank = sum(u.get("bank_balance", 0) for u in users.values())
        bot.send_message(call.message.chat.id, f"📊 **Ekonomi:**\n💵 Cüzdan: {total_money} $\n🏦 Banka: {total_bank} $\n💰 Toplam: {total_money+total_bank} $")

    elif call.data == "admin_help_duyuru": bot.send_message(call.message.chat.id, "📢 `/duyuru Mesaj`")
    elif call.data == "admin_help_anket": bot.send_message(call.message.chat.id, "📊 `/anket Soru | Cevap1 | Cevap2`")
    elif call.data == "admin_help_hediye": bot.send_message(call.message.chat.id, "🎁 `/hediye <ID> <Miktar>` veya `/dagit <Miktar>`")
    elif call.data == "admin_help_ban": bot.send_message(call.message.chat.id, "🚫 `/ban <ID>`\n✅ `/unban <ID>`")
    elif "help" in call.data:
        bot.answer_callback_query(call.id, "Komut kullanımı için koda bakınız.", show_alert=True)

@bot.message_handler(commands=['duyuru'])
def admin_broadcast(message):
    if message.from_user.username != DEVELOPER_USERNAME: return
    text = message.text.replace("/duyuru", "").strip()
    if not text: return
    count = 0
    for uid in users:
        try: bot.send_message(uid, f"📢 **DUYURU**\n\n{text}"); count += 1
        except: pass
    bot.reply_to(message, f"✅ {count} kişiye iletildi.")

@bot.message_handler(commands=['anket'])
def admin_poll(message):
    if message.from_user.username != DEVELOPER_USERNAME: return
    try:
        parts = message.text.replace("/anket", "").split("|")
        if len(parts) < 3: return
        question, options = parts[0].strip(), [o.strip() for o in parts[1:]]
        for uid in users:
            try: bot.send_poll(uid, question, options, is_anonymous=True)
            except: pass
        bot.reply_to(message, "✅ Anket gönderildi.")
    except: pass

@bot.message_handler(commands=['dagit'])
def admin_distribute(message):
    if message.from_user.username != DEVELOPER_USERNAME: return
    try: amount = int(message.text.split()[1])
    except: return
    for uid in users: users[uid]["money"] = users[uid].get("money", 0) + amount
    save_users(); bot.reply_to(message, f"✅ Herkese {amount} $ dağıtıldı.")

@bot.message_handler(commands=['hediye'])
def admin_gift(message):
    if message.from_user.username != DEVELOPER_USERNAME: return
    try:
        target, amount = message.text.split()[1], int(message.text.split()[2])
        uid = target if target in users else next((u for u, d in users.items() if d.get("username") == target.replace("@", "")), None)
        if uid:
            users[uid]["money"] = users[uid].get("money", 0) + amount; save_users()
            bot.send_message(uid, f"🎁 **HEDİYE!** Hesabına {amount} $ yüklendi."); bot.reply_to(message, "✅ Gönderildi.")
    except: bot.reply_to(message, "Hata: /hediye <ID/@User> <Miktar>")

@bot.message_handler(commands=['ban', 'unban'])
def ban_manager(message):
    if message.from_user.username != DEVELOPER_USERNAME: return
    try:
        cmd, target = message.text.split()[0], message.text.split()[1]
        if target in users:
            users[target]["is_banned"] = (cmd == "/ban"); save_users()
            bot.reply_to(message, f"✅ İşlem tamam: {cmd} {target}")
    except: pass

@bot.message_handler(commands=['backup', 'yedek'])
def admin_backup_command(message):
    if message.from_user.username != DEVELOPER_USERNAME: return
    
    wait_msg = bot.reply_to(message, "💾 Veritabanı yedeği hazırlanıyor...")
    
    try:
        # 1. Kullanıcı Verileri (Memory -> JSON)
        users_json = json.dumps(users, ensure_ascii=False, indent=2)
        users_file = io.BytesIO(users_json.encode('utf-8'))
        users_file.name = f"users_backup_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.json"
        
        # 2. Market Verileri (Memory -> JSON)
        market_data = {
            "prices": market_prices, "volumes": market_volumes, "last_prices": last_prices,
            "price_history": price_history, "news": market_news, "trend": market_trend,
            "last_update": last_market_update.strftime("%Y-%m-%d %H:%M:%S") if last_market_update else None
        }
        market_json = json.dumps(market_data, ensure_ascii=False, indent=2)
        market_file = io.BytesIO(market_json.encode('utf-8'))
        market_file.name = f"market_backup_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.json"
        
        bot.send_document(message.chat.id, users_file, caption="👤 **Kullanıcı Veritabanı**")
        bot.send_document(message.chat.id, market_file, caption="📈 **Piyasa Veritabanı**")
        bot.delete_message(message.chat.id, wait_msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ Yedekleme hatası: {e}", message.chat.id, wait_msg.message_id)

@bot.message_handler(commands=['gunluk'])
def daily_reward(message):
    user_id = str(message.from_user.id)
    today = datetime.now().strftime("%Y-%m-%d")
    if users[user_id].get("last_daily_reward") == today: bot.reply_to(message, "⏳ Bugünün ödülünü zaten aldın!"); return
    
    streak = users[user_id].get("daily_streak", 0) + 1 if users[user_id].get("last_daily_reward") == (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d") else 1
    
    base_reward = 50
    bonus = min(streak * 10, 150)
    total_reward = base_reward + bonus
    money_reward = 100 + (streak * 20)

    users[user_id].update({"exp": users[user_id].get("exp", 0) + total_reward, "money": users[user_id].get("money", 0) + money_reward, "last_daily_reward": today, "daily_streak": streak})
    save_users()
    
    msg = bot.send_dice(message.chat.id, emoji="🎰")
    time.sleep(3)
    
    dice_value = msg.dice.value
    luck_msg = ""
    if dice_value == 64: # Jackpot
        total_reward *= 5; money_reward *= 5
        users[user_id].setdefault("inventory", {})["elmas"] = users[user_id].get("inventory", {}).get("elmas", 0) + 1
        luck_msg = "\n\n🎰 **JACKPOT! (777)**\n🚀 Ödüller 5'e katlandı!\n💎 +1 Elmas kazandın!"
    elif dice_value in [1, 22, 43]: # Şanslı
        total_reward *= 2; money_reward *= 2
        luck_msg = "\n\n🎰 **Şanslı Çevirme!**\n🔥 Ödüller 2'ye katlandı!"
    
    if luck_msg:
        users[user_id]["exp"] += total_reward - (base_reward + bonus)
        users[user_id]["money"] += money_reward - (100 + (streak * 20))
        save_users()

    bot.reply_to(message, f"🎁 **GÜNLÜK ÖDÜL ALINDI!**\n\n⭐️ EXP: +{total_reward}\n💵 Para: +{money_reward} $\n🔥 Seri: {streak}. Gün{luck_msg}")

@bot.message_handler(commands=['ozet'])
def get_summary(message):
    if not check_daily_limit(message.from_user.id): bot.reply_to(message, "⛔ Günlük limit doldu."); return
    try:
        topic = message.text.replace("/ozet", "").strip()
        if not topic: bot.reply_to(message, "⚠️ Konu yazmalısın."); return
        res = safe_generate_content(f"'{topic}' konusunu KPSS öğrencisi için maddeler halinde özetle.")
        bot.reply_to(message, f"📝 **ÖZET: {topic.upper()}**\n\n{res.text}", parse_mode="Markdown")
    except: bot.reply_to(message, "Hata oluştu.")

@bot.message_handler(commands=['ruya'])
def dream_interpret(message):
    if not check_daily_limit(message.from_user.id): bot.reply_to(message, "⛔ Günlük limit doldu."); return
    try:
        dream = message.text.replace("/ruya", "").strip()
        if not dream: bot.reply_to(message, "⚠️ Rüyayı yazmalısın."); return
        res = safe_generate_content(f"Rüya tabircisi gibi konuş. Şu rüyayı yorumla: '{dream}'")
        bot.reply_to(message, f"🌙 **RÜYA TABİRİ**\n\n{res.text}")
    except: bot.reply_to(message, "Hata oluştu.")

@bot.message_handler(commands=['tarot'])
def tarot_reading(message):
    if not check_daily_limit(message.from_user.id): bot.reply_to(message, "⛔ Günlük limit doldu."); return
    msg = bot.reply_to(message, "🔮 Niyetini yaz...")
    bot.register_next_step_handler(msg, perform_tarot_reading)

def perform_tarot_reading(message):
    try:
        cards = ["Deli", "Büyücü", "Azize", "İmparatoriçe", "İmparator", "Aşıklar", "Savaş Arabası", "Güç", "Ermiş", "Kader Çarkı", "Adalet", "Asılan Adam", "Ölüm", "Denge", "Şeytan", "Yıkılan Kule", "Yıldız", "Ay", "Güneş", "Mahkeme", "Dünya"]
        drawn = random.sample(cards, 3)
        res = safe_generate_content(f"Tarot falı bak. Soru: '{message.text}'. Kartlar: {drawn}. Yorumla.")
        photo = create_tarot_image(drawn)
        bot.send_photo(message.chat.id, photo, caption=f"🔮 **TAROT FALI**\n\n{res.text[:900]}")
    except: bot.reply_to(message, "Fal bakılamadı.")

@bot.message_handler(commands=['burc'])
def daily_horoscope(message):
    if not check_daily_limit(message.from_user.id): bot.reply_to(message, "⛔ Günlük limit doldu."); return
    msg = bot.reply_to(message, "♈ Burcunu yaz...")
    bot.register_next_step_handler(msg, lambda m: bot.reply_to(m, safe_generate_content(f"{m.text} burcu için günlük yorum yap.").text))

@bot.message_handler(commands=['bilgi'])
def random_fact(message):
    if not check_daily_limit(message.from_user.id): bot.reply_to(message, "⛔ Günlük limit doldu."); return
    bot.reply_to(message, safe_generate_content("İlginç bir genel kültür bilgisi ver.").text)

@bot.message_handler(commands=['tarihtebugun'])
def history_today(message):
    bot.reply_to(message, safe_generate_content(f"Tarihte bugün ({datetime.now().strftime('%d %B')}) ne oldu?").text)

@bot.message_handler(commands=['pomodoro'])
def start_pomodoro(message):
    msg = bot.reply_to(message, "🍅 **Pomodoro Başladı!**\n\n25 dakika boyunca odaklan. Süre bitince seni etiketleyip haber vereceğim! 📚\n_(Botu sessize alma)_")
    
    def finish_pomodoro():
        try:
            bot.reply_to(msg, "⏰ **SÜRE DOLDU!**\n\n5 dakika mola ver, sonra tekrar başla! ☕")
        except:
            pass
    Timer(1500, finish_pomodoro).start()

@bot.message_handler(commands=['help', 'yardim', 'menu'])
def help_guide(message):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(
        InlineKeyboardButton("🎮 Oyunlar", callback_data="help_games"),
        InlineKeyboardButton("💰 Ekonomi", callback_data="help_economy")
    )
    markup.row(
        InlineKeyboardButton("👤 Profil & Araçlar", callback_data="help_profile"),
        InlineKeyboardButton("🔮 AI & Diğer", callback_data="help_ai")
    )
    bot.send_message(message.chat.id, "📚 **BOT YARDIM MENÜSÜ**\n\nLütfen bilgi almak istediğin kategoriyi seç: 👇", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data.startswith("help_"))
def help_callback(call):
    category = call.data
    text = ""
    
    if category == "help_games":
        text = (
            "🎮 **OYUN MODLARI**\n\n🔹 `/quiz` - Kategorili KPSS soruları çöz.\n🔹 `/maraton` - Tek canla ne kadar gidebilirsin?\n🔹 `/gorevler` - Günlük görevleri tamamla.\n🔹 `/clock` - Zamana karşı Global sorular.\n🔹 `/duello <@kisi> <para>` - Oyuncuya meydan oku.\n🔹 `/duello <para>` - Botla zar atışı yap.\n🔹 `/bahis <para>` - Sıradaki soruya bahis oyna."
        )
    elif category == "help_economy":
        text = (
            "💰 **EKONOMİ & TİCARET**\n\n🔹 `/banka` - Banka hesabını yönet (Günlük %5 Faiz).\n🔹 `/kredi <miktar>` - Kredi çek.\n🔹 `/borsa` - Kapalıçarşı fiyatlarını gör.\n🔹 `/analiz` - Piyasa analizi satın al.\n🔹 `/grafik_detay <mal>` - Detaylı grafik.\n🔹 `/dedikodu` - İçeriden bilgi al.\n🔹 `/kara_borsa` - Riskli ucuz pazar.\n🔹 `/al <mal> <adet>` - Mal Al.\n🔹 `/sat <mal> <adet>` - Mal Sat.\n🔹 `/emir_ver` - Otomatik emir gir.\n🔹 `/kaz` - Madene in.\n🔹 `/market` - Eşya satın al.\n🔹 `/transfer` - Para gönder."
        )
    elif category == "help_profile":
        text = (
            "👤 **PROFİL & ARAÇLAR**\n\n🔹 `/profil` - Profil kartını gör.\n🔹 `/envanter` - Çantanı gör.\n🔹 `/top10` - Liderlik tablosu.\n🔹 `/yanlislarim` - Hatalarını tekrar et.\n🔹 `/pomodoro` - Ders çalışma sayacı.\n🔹 `/soruekle` - Soru öner."
        )
    elif category == "help_ai":
        text = (
            "🔮 **AI & DİĞER ARAÇLAR**\n\n🔹 `/ozet <konu>` - Konu özeti çıkar.\n🔹 `/dogruyanlis` - Bilgi yarışması.\n🔹 `/ruya <metin>` - Rüya tabiri.\n🔹 `/tarot` - 3 kart tarot falı.\n🔹 `/burc` - Günlük burç yorumu.\n🔹 `/bilgi` - İlginç bir bilgi öğren.\n🔹 `/tarihtebugun` - Tarihte bugün."
        )
    elif category == "help_back":
        markup = InlineKeyboardMarkup(row_width=2)
        markup.row(
            InlineKeyboardButton("🎮 Oyunlar", callback_data="help_games"),
            InlineKeyboardButton("💰 Ekonomi", callback_data="help_economy")
        )
        markup.row(
            InlineKeyboardButton("👤 Profil & Araçlar", callback_data="help_profile"),
            InlineKeyboardButton("🔮 AI & Diğer", callback_data="help_ai")
        )
        bot.edit_message_text("📚 **BOT YARDIM MENÜSÜ**\n\nLütfen bilgi almak istediğin kategoriyi seç: 👇", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        return

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Geri", callback_data="help_back")), parse_mode="Markdown")

# --- Ana Komut Handler'ları ---
@bot.message_handler(commands=['start'])
def start_message(message):
    user_id, username = str(message.from_user.id), message.from_user.username
    if username == DEVELOPER_USERNAME:
        users.setdefault(user_id, {"level": 1, "exp": 0, "lives": 3, "category": "karisik"})["is_approved"] = True
        save_users()
    
    if user_id in users and "money" not in users[user_id]: users[user_id]["money"] = 1000; save_users()
    if users.get(user_id, {}).get("is_banned"): bot.reply_to(message, "🚫 Hesabınız yasaklanmıştır."); return

    if user_id not in users:
        users[user_id] = {"level": 1, "exp": 0, "lives": 3, "category": "karisik", "is_approved": False, "username": username, "name": message.from_user.first_name, "join_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "money": 1000}
        save_users()
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("📝 Üye Olmak İstiyorum", callback_data="request_access"))
        bot.send_message(message.chat.id, "🔒 **Bot Erişim İzni**\nBu bot özeldir. Erişim izni istemek için butona tıkla. 👇", reply_markup=markup); return

    if not users.get(user_id, {}).get("is_approved", True):
        bot.send_message(message.chat.id, "⏳ **Onay Bekleniyor...**"); return

    text = "👋 **Hoş Geldin!**\nLütfen dil seçimi yap.\nPlease select your language."
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("🇹🇷 Türkçe", callback_data="lang_tr"), types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"), types.InlineKeyboardButton("🇧🇬 Български", callback_data="lang_bg"))
    bot.send_message(message.chat.id, text, reply_markup=keyboard)

@bot.callback_query_handler(func=lambda c: c.data == "request_access")
def request_access_handler(call):
    user_id = str(call.from_user.id)
    bot.edit_message_text("✅ Talebiniz Alındı! Kurucuya bildirim gönderildi.", call.message.chat.id, call.message.message_id)
    admin_id = next((uid for uid, u in users.items() if u.get("username") == DEVELOPER_USERNAME), None)
    if admin_id:
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("✅ Onayla", callback_data=f"approve_{user_id}"), types.InlineKeyboardButton("❌ Reddet", callback_data=f"reject_{user_id}"))
        bot.send_message(admin_id, f"🔔 **YENİ ÜYELİK TALEBİ!**\n\nKullanıcı: @{call.from_user.username} (ID: {user_id})", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("approve_") or c.data.startswith("reject_"))
def admin_approval_callback(call):
    if call.from_user.username != DEVELOPER_USERNAME: bot.answer_callback_query(call.id, "⛔ Yetkisiz işlem!"); return
    action, target_id = call.data.split("_")
    if action == "approve":
        if target_id in users:
            users[target_id]["is_approved"] = True; save_users()
            bot.edit_message_text(f"✅ Kullanıcı ({target_id}) ONAYLANDI.", call.message.chat.id, call.message.message_id)
            try: bot.send_message(target_id, "🎉 **Tebrikler! Üyeliğiniz Onaylandı!**\nBaşlamak için 👉 /start")
            except: pass
    elif action == "reject":
        bot.edit_message_text(f"❌ Kullanıcı ({target_id}) REDDEDİLDİ.", call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("lang_"))
def language_selected(call):
    user_id, lang_code = str(call.from_user.id), call.data.replace("lang_", "")
    if user_id not in users: users[user_id] = {"level": 1, "exp": 0, "lives": 3, "category": "karisik"}
    users[user_id].update({"lang": lang_code, "name": call.from_user.first_name, "username": call.from_user.username})
    save_users()
    
    user_text = f"@{call.from_user.username}" if call.from_user.username else call.from_user.first_name
    messages = {
        "tr": {
            "text": (
                f"👋 **Hoş Geldin, {user_text}!**\n\n"
                "Ben, senin için geliştirilmiş yapay zeka destekli bir asistanım. Hem eğlenip hem öğrenebileceğin harika özelliklerim var! 🚀\n"
                "Aşağıdaki **☰ Menü** butonundan tüm komutlara erişebilirsin.\n\n"
                "🎮 **Oyun & Yarışma**\n━━━━━━━━━━━━━━━━━━━━\n🔹 `/quiz` - KPSS Soruları Çöz 📚\n🔹 `/maraton` - Tek Hakla İlerle 🏃‍♂️\n🔹 `/duello` - PvP Düello ⚔️\n\n"
                "💰 **Ekonomi & Ticaret**\n━━━━━━━━━━━━━━━━━━━━\n🔹 `/banka` - Banka & Faiz 🏦\n🔹 `/borsa` - Kapalıçarşı 📈\n🔹 `/kaz` - Maden Kaz ⛏️\n🔹 `/market` - Eşya Al 🛒\n\n"
                "👤 **Profil & Araçlar**\n━━━━━━━━━━━━━━━━━━━━\n🔹 `/profil` - İstatistikler 📊\n🔹 `/envanter` - Çantan 🎒\n🔹 `/top10` - Liderlik 🏆\n\n"
                "🔮 **Ekstra**\n━━━━━━━━━━━━━━━━━━━━\n🔹 `/ruya`, `/tarot`, `/burc`, `/ozet`"
            ), "btn": "📩 Geliştiriciye Mesaj Gönder"
        },
        "en": {
            "text": f"👋 **Welcome, {user_text}!**\n\nI am an AI-powered assistant. Use the **Menu** button to access commands.", "btn": "📩 Contact Developer"
        },
        "bg": {
            "text": (
                f"👋 **Добре дошъл, {user_text}!**\n\n"
                "Аз съм AI асистент, създаден за теб. Имам страхотни функции за забавление и учене! 🚀\n"
                "Можете да получите достъп до всички команди от бутона **☰ Меню** по-долу.\n\n"
                "🎮 **Игри и Викторини**\n━━━━━━━━━━━━━━━━━━━━\n🔹 `/quiz` - Решаване на въпроси 📚\n🔹 `/maraton` - Маратон режим 🏃‍♂️\n🔹 `/duello` - PvP Дуел ⚔️\n\n"
                "💰 **Икономика и Търговия**\n━━━━━━━━━━━━━━━━━━━━\n🔹 `/banka` - Банка и лихви 🏦\n🔹 `/borsa` - Търговия на пазара 📈\n🔹 `/kaz` - Копаене ⛏️\n🔹 `/market` - Купи предмети 🛒\n\n"
                "👤 **Профил и Инструменти**\n━━━━━━━━━━━━━━━━━━━━\n🔹 `/profil` - Вашата статистика 📊\n🔹 `/envanter` - Инвентар 🎒\n🔹 `/top10` - Класация 🏆\n\n"
                "🔮 **Екстра Функции**\n━━━━━━━━━━━━━━━━━━━━\n🔹 `/ruya`, `/tarot`, `/burc`, `/ozet`"
            ), "btn": "📩 Свържи се с разработчика"
        }
    }
    selected = messages.get(lang_code, messages["en"])
    
    markup = InlineKeyboardMarkup()
    # Kategorili Menü Butonları
    markup.row(
        InlineKeyboardButton("🎮 Oyunlar", callback_data="help_games"),
        InlineKeyboardButton("💰 Ekonomi", callback_data="help_economy")
    )
    markup.row(
        InlineKeyboardButton("👤 Profil & Araçlar", callback_data="help_profile"),
        InlineKeyboardButton("🔮 AI & Diğer", callback_data="help_ai")
    )
    markup.add(
        InlineKeyboardButton(text=selected["btn"], url=f"https://t.me/{DEVELOPER_USERNAME}")
    )

    bot.edit_message_text(selected["text"], call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    bot.send_message(call.message.chat.id, "✅ Kurulum tamamlandı! Sol alttaki **Menu** butonunu kullanabilirsin.")

@bot.message_handler(commands=['profil'])
def my_profile(message):
    user_id = str(message.from_user.id)
    if user_id not in users: return
    u = users[user_id]
    u.update({"name": message.from_user.first_name, "username": message.from_user.username}); save_users()
    try:
        photo = create_profile_image(user_id, u)
        bot.send_photo(message.chat.id, photo, caption=f"👤 **{u.get('name')}** Profil Kartı")
    except Exception as e:
        bot.reply_to(message, f"Profil hatası: {e}")

@bot.message_handler(commands=['top10'])
def leaderboard(message):
    sorted_users = sorted(users.items(), key=lambda x: (x[1].get("level", 1), x[1].get("exp", 0)), reverse=True)[:10]
    try:
        photo = create_leaderboard_image(sorted_users)
        bot.send_photo(message.chat.id, photo, caption="🏆 **Liderlik Tablosu**\nZirve yarışında son durum! 🚀")
    except:
        text = "🏆 **Liderlik Tablosu (Top 10)** 🏆\n\n"
        for i, (uid, data) in enumerate(sorted_users, 1):
            text += f"{i}. {data.get('name', 'Bilinmiyor')} - Lvl {data.get('level', 1)} | {data.get('exp', 0)} EXP\n"
        bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['haftaliktop10'])
def weekly_leaderboard(message):
    current_week_str = datetime.now().strftime("%Y-%W")
    
    # Sadece bu hafta soru çözenleri al ve sırala
    weekly_players = [
        (uid, u_data) for uid, u_data in users.items() 
        if u_data.get("last_weekly_question_week") == current_week_str and u_data.get("weekly_questions_solved", 0) > 0
    ]
    
    sorted_users = sorted(
        weekly_players, 
        key=lambda x: x[1].get("weekly_questions_solved", 0), 
        reverse=True
    )[:10]
    
    if not sorted_users:
        bot.reply_to(message, "Bu hafta henüz kimse soru çözmedi. İlk sen ol! 🚀")
        return

    try:
        photo = create_weekly_leaderboard_image(sorted_users)
        bot.send_photo(message.chat.id, photo, caption=f"🏆 **Haftanın En Çalışkanları**\n(Pazartesi sıfırlanır)")
    except Exception as e:
        bot.reply_to(message, f"Liderlik tablosu oluşturulamadı: {e}")

def create_stats_image(user_stats, global_stats, date_str):
    width, height = 800, 600
    bg_color = (30, 33, 43)
    text_color = (220, 220, 220)
    green = (74, 222, 128)
    red = (248, 113, 113)
    
    img = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    
    try:
        font_path = "arial.ttf"
        if not os.path.exists(font_path): font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        title_font = ImageFont.truetype(font_path, 36)
        header_font = ImageFont.truetype(font_path, 24)
        bar_label_font = ImageFont.truetype(font_path, 20)
        bar_text_font = ImageFont.truetype(font_path, 18)
    except:
        title_font, header_font, bar_label_font, bar_text_font = ImageFont.load_default(), ImageFont.load_default(), ImageFont.load_default(), ImageFont.load_default()

    draw.text((width/2, 40), "📊 GÜNLÜK SORU İSTATİSTİKLERİ", font=title_font, fill=(255, 215, 0), anchor="mt")
    draw.text((width/2, 85), date_str, font=header_font, fill=(150, 163, 184), anchor="mt")

    stats = {"Senin İstatistiklerin": user_stats, "Genel İstatistikler": global_stats}
    bar_width, gap, group_gap, start_y = 120, 50, 180, 520
    
    all_values = list(user_stats.values()) + list(global_stats.values())
    max_val = max(all_values) if all_values else 1
    graph_height = 300
    
    x = (width - (2 * (bar_width * 2 + gap) + group_gap - gap)) / 2 + 50

    for title, data in stats.items():
        draw.text((x + bar_width + gap/2, start_y + 25), title, font=header_font, fill=text_color, anchor="mt")
        
        correct_val = data.get('correct', 0)
        bar_h = (correct_val / max_val) * graph_height if max_val > 0 else 0
        draw.rectangle([(x, start_y - bar_h), (x + bar_width, start_y)], fill=green)
        draw.text((x + bar_width/2, start_y - bar_h - 10), str(correct_val), font=bar_label_font, fill=green, anchor="mb")
        draw.text((x + bar_width/2, start_y - 20), "Doğru", font=bar_text_font, fill=(0,0,0), anchor="ms")
        x += bar_width + gap
        
        incorrect_val = data.get('incorrect', 0)
        bar_h = (incorrect_val / max_val) * graph_height if max_val > 0 else 0
        draw.rectangle([(x, start_y - bar_h), (x + bar_width, start_y)], fill=red)
        draw.text((x + bar_width/2, start_y - bar_h - 10), str(incorrect_val), font=bar_label_font, fill=red, anchor="mb")
        draw.text((x + bar_width/2, start_y - 20), "Yanlış", font=bar_text_font, fill=(0,0,0), anchor="ms")
        x += bar_width + group_gap

    bio = io.BytesIO(); img.save(bio, 'PNG'); bio.seek(0)
    return bio

@bot.message_handler(commands=['istatistik'])
def daily_stats(message):
    user_id = str(message.from_user.id)
    if not users.get(user_id, {}).get("is_approved", True): return
    
    today = datetime.now().strftime("%Y-%m-%d")
    u_data = users[user_id]
    if u_data.get("last_question_date") != today:
        u_data["daily_correct_solved"] = 0
        u_data["daily_incorrect_solved"] = 0

    user_stats = {'correct': u_data.get("daily_correct_solved", 0), 'incorrect': u_data.get("daily_incorrect_solved", 0)}
    global_correct = sum(u.get("daily_correct_solved", 0) for u in users.values() if u.get("last_question_date") == today)
    global_incorrect = sum(u.get("daily_incorrect_solved", 0) for u in users.values() if u.get("last_question_date") == today)
    global_stats = {'correct': global_correct, 'incorrect': global_incorrect}
    
    try:
        photo = create_stats_image(user_stats, global_stats, today)
        user_total = user_stats['correct'] + user_stats['incorrect']
        global_total = global_stats['correct'] + global_stats['incorrect']
        caption = f"📊 **Günün Özeti**\n\n👤 **Sen:** {user_total} soru ({user_stats['correct']} D, {user_stats['incorrect']} Y)\n🌍 **Genel:** {global_total} soru ({global_stats['correct']} D, {global_stats['incorrect']} Y)"
        bot.send_photo(message.chat.id, photo, caption=caption)
    except Exception as e:
        bot.reply_to(message, f"Grafik hatası: {e}")

@bot.message_handler(commands=['gorevler'])
def show_daily_quests(message):
    user_id = str(message.from_user.id)
    generate_daily_quests(user_id)
    quests = users[user_id]["quests"]["list"]
    text = "📋 **GÜNLÜK GÖREVLER**\n\n"
    all_done = True
    for q in quests:
        status = "✅" if q["done"] else f"{q['current']}/{q['target']}"
        text += f"{status} {q['desc']} (+{q['reward']} EXP)\n"
        if not q["done"]: all_done = False
    if all_done: text += "\n🎉 **Tebrikler! Bugünün tüm görevlerini bitirdin!**"
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(func=lambda message: not message.text.startswith("/"))
def handle_message(message):
    user_id = str(message.from_user.id)
    if not users.get(user_id, {}).get("is_approved", True) or users.get(user_id, {}).get("is_banned"): return
    if any(word in message.text.lower() for word in BANNED_WORDS):
        try: bot.delete_message(message.chat.id, message.message_id)
        except: pass
        return
    if not check_daily_limit(user_id):
        bot.reply_to(message, "⛔ Günlük Gemini mesaj hakkın doldu!"); return
    try:
        response = safe_generate_content(message.text)
        bot.reply_to(message, response.text)
    except Exception as e:
        bot.reply_to(message, f"Bir hata oluştu: {e}")

# --- Periyodik Görevler ---
def scheduler_thread():
    while True:
        now_utc3 = datetime.now(timezone.utc) + timedelta(hours=3)

        # Haftalık Ödül (Pazartesi 05:00)
        current_week_str = now_utc3.strftime("%Y-%W")
        if now_utc3.weekday() == 0 and now_utc3.hour == 5 and database.last_rewarded_week != current_week_str:
            give_weekly_reward()
            database.last_rewarded_week = current_week_str
            database.save_market_data()
            time.sleep(65) # Tekrar çalışmasını önle

        if now_utc3.hour == 8 and now_utc3.minute == 0:
            send_morning_broadcast(); time.sleep(65)
        if now_utc3.hour == 9 and now_utc3.minute == 0:
            apply_bank_interest(bot); time.sleep(65)
        if (datetime.now() - database.last_market_update).total_seconds() > 90:
            update_market(bot)
        time.sleep(20)

# --- Botu Çalıştırma ---
if __name__ == "__main__":
    print("Bot komutları ayarlanıyor...")
    bot.set_my_commands([
        types.BotCommand("menu", "Ana Menü"),
        types.BotCommand("profil", "Profil ve İstatistikler"),
        types.BotCommand("envanter", "Çanta ve Eşyalar"),
        types.BotCommand("gunluk", "Günlük Ödülünü Al"),
        types.BotCommand("gorevler", "Günlük Görevler"),
        types.BotCommand("quiz", "Soru Çöz (KPSS)"),
        types.BotCommand("maraton", "Maraton Modu"),
        types.BotCommand("clock", "Global Yarışma"),
        types.BotCommand("dogruyanlis", "Doğru/Yanlış Oyunu"),
        types.BotCommand("duello", "Düello At"),
        types.BotCommand("bahis", "Bahis Oyna"),
        types.BotCommand("yanlislarim", "Yanlışlarını Tekrar Et"),
        types.BotCommand("borsa", "Kapalıçarşı Piyasası"),
        types.BotCommand("al", "Mal Satın Al"),
        types.BotCommand("sat", "Mal Sat"),
        types.BotCommand("market", "Eşya ve Joker Al"),
        types.BotCommand("banka", "Banka Hesabı"),
        types.BotCommand("kredi", "Kredi Çek"),
        types.BotCommand("yatir", "Bankaya Yatır"),
        types.BotCommand("cek", "Bankadan Çek"),
        types.BotCommand("transfer", "Para Gönder"),
        types.BotCommand("kaz", "Maden Kaz"),
        types.BotCommand("portfoyum", "Yatırımlarını Gör"),
        types.BotCommand("emir", "Bekleyen Emirler"),
        types.BotCommand("emir_ver", "Otomatik Emir Gir"),
        types.BotCommand("analiz", "Piyasa Analizi"),
        types.BotCommand("grafik", "Fiyat Grafiği"),
        types.BotCommand("dedikodu", "Piyasa Tüyosu"),
        types.BotCommand("kara_borsa", "Kara Borsa"),
        types.BotCommand("zenginler", "En Zenginler"),
        types.BotCommand("ozet", "Konu Özeti"),
        types.BotCommand("ruya", "Rüya Tabiri"),
        types.BotCommand("tarot", "Tarot Falı"),
        types.BotCommand("burc", "Burç Yorumu"),
        types.BotCommand("bilgi", "İlginç Bilgi"),
        types.BotCommand("tarihtebugun", "Tarihte Bugün"),
        types.BotCommand("pomodoro", "Pomodoro Sayacı"),
        types.BotCommand("soruekle", "Soru Öner"),
        types.BotCommand("top10", "Liderlik Tablosu"),
        types.BotCommand("halkaarz", "Aktif Halka Arz"),
        types.BotCommand("talepet", "Halka Arza Katıl"),
        types.BotCommand("talep_iptal", "Halka Arz Talebini İptal Et"),
        types.BotCommand("sirket_kur", "Kendi Şirketini Kur (50k$)"),
        types.BotCommand("halkaarz_yap", "Şirketini Borsaya Aç"),
        types.BotCommand("haftaliktop10", "Haftalık Liderlik"),
        types.BotCommand("istatistik", "Günlük İstatistikler"),
        types.BotCommand("help", "Yardım"),
    ])
    
    tirtil_utils = {
        'get_rank': get_rank, 'check_daily_limit': check_daily_limit, 
        'update_quest_progress': update_quest_progress, 'safe_generate_content': safe_generate_content,
        'get_badges': get_badges
    }
    register_quiz_handlers(bot, tirtil_utils)
    register_market_handlers(bot, tirtil_utils)

    scheduler = threading.Thread(target=scheduler_thread, daemon=True)
    scheduler.start()

    app = Flask(__name__)
    @app.route('/')
    def home(): return "Bot calisiyor!"
    
    http_server = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080))), daemon=True)
    http_server.start()

    print("Bot aktif ve çalışıyor...")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
