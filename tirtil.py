import os
import json
import threading
import time
import random
from datetime import datetime, timedelta, timezone
import io
import requests
import html
from dotenv import load_dotenv
from flask import Flask
from telebot import TeleBot, types
from google import genai
from PIL import Image, ImageDraw, ImageFont

# Modülleri import et
from database import *
from quiz import register_quiz_handlers
from market import register_market_handlers, update_market, apply_bank_interest

# --- Bot ve API Başlatma ---
bot = TeleBot(BOT_TOKEN)
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# --- Yardımcı Fonksiyonlar ---
def safe_generate_content(prompt_content):
    if not client: raise Exception("Gemini API anahtarı ayarlanmamış.")
    models = ["gemini-1.5-flash", "gemini-pro"]
    for model in models:
        try: return client.generate_content(model=model, contents=prompt_content)
        except Exception as e: print(f"⚠️ {model} hatası: {e} -> Diğer modele geçiliyor...")
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
    keyboard = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🇹🇷 Türkçe", callback_data="lang_tr"), types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"))
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
    users.setdefault(user_id, {"level": 1, "exp": 0, "lives": 3})
    users[user_id].update({"lang": lang_code, "name": call.from_user.first_name, "username": call.from_user.username})
    save_users()
    help_text = "👋 **Hoş Geldin!**\nBen yapay zeka destekli bir asistanım. 🚀\n**☰ Menü**'den komutlara erişebilirsin."
    bot.edit_message_text(help_text, call.message.chat.id, call.message.message_id, parse_mode="Markdown")

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
    text = "🏆 **Liderlik Tablosu (Top 10)** 🏆\n\n"
    for i, (uid, data) in enumerate(sorted_users, 1):
        text += f"{i}. {data.get('name', 'Bilinmiyor')} - Lvl {data.get('level', 1)} | {data.get('exp', 0)} EXP\n"
    bot.send_message(message.chat.id, text)

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
        if now_utc3.hour == 9 and now_utc3.minute == 0:
            apply_bank_interest(bot); time.sleep(65)
        if (datetime.now() - last_market_update).total_seconds() > 90:
            update_market(bot)
        time.sleep(20)

# --- Botu Çalıştırma ---
if __name__ == "__main__":
    print("Bot komutları ayarlanıyor...")
    bot.set_my_commands([
        types.BotCommand("start", "Botu başlatır"),
        types.BotCommand("profil", "Profilini Görüntüle"),
        types.BotCommand("quiz", "Soru Çöz"),
        types.BotCommand("maraton", "Maraton Modu"),
        types.BotCommand("borsa", "Kapalıçarşı'yı Görüntüle"),
        types.BotCommand("portfoyum", "Yatırımlarını Gör"),
        types.BotCommand("banka", "Banka İşlemleri"),
        types.BotCommand("kaz", "Maden Kaz"),
        types.BotCommand("top10", "Liderlik Tablosu"),
        types.BotCommand("gorevler", "Günlük Görevler"),
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
