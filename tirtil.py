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
from market import register_market_handlers, update_market, apply_bank_interest, check_limit_orders

# --- Bot ve API Başlatma ---
bot = TeleBot(BOT_TOKEN)
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# --- Yardımcı Fonksiyonlar ---
def safe_generate_content(prompt_content):
    if not client: return "Gemini API anahtarı ayarlanmamış."
    models = ["gemini-1.5-flash", "gemini-pro"]
    for model in models:
        try: return client.generate_content(model=model, contents=prompt_content)
        except Exception as e: print(f"⚠️ {model} hatası: {e} -> Diğer modele geçiliyor...")
    raise Exception("Tüm Gemini modelleri başarısız oldu.")

def escape_md(text): return str(text).replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[")

BANNED_WORDS = ["aptal", "salak", "gerizekalı", "mal", "ezik", "amq", "orospu"]

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

# Diğer genel komutlar (profil, top10, envanter, admin, AI komutları vb.) buraya eklenecek...

# --- Periyodik Görevler ---
def scheduler_thread():
    while True:
        now_utc3 = datetime.now(timezone.utc) + timedelta(hours=3)
        if now_utc3.hour == 9 and now_utc3.minute == 0:
            apply_bank_interest(bot); time.sleep(65)
        if (datetime.now() - last_market_update).total_seconds() > 90:
            update_market(bot); time.sleep(1) # update_market zaten zaman alıyor
        time.sleep(20)

# --- Botu Çalıştırma ---
if __name__ == "__main__":
    print("Bot komutları ayarlanıyor...")
    bot.set_my_commands([
        types.BotCommand("start", "Botu başlatır"),
        types.BotCommand("quiz", "Soru Çöz"),
        types.BotCommand("borsa", "Borsa Durumu"),
        types.BotCommand("profil", "Profilim"),
    ])
    
    # Handler'ları kaydet
    tirtil_utils = {
        'get_rank': get_rank, 'check_daily_limit': check_daily_limit, 
        'update_quest_progress': update_quest_progress, 'safe_generate_content': safe_generate_content,
        'get_badges': get_badges
    }
    register_quiz_handlers(bot, tirtil_utils)
    register_market_handlers(bot, tirtil_utils)

    # Periyodik görevleri başlat
    scheduler = threading.Thread(target=scheduler_thread, daemon=True)
    scheduler.start()

    # Web sunucusunu başlat (Render için)
    app = Flask(__name__)
    @app.route('/')
    def home(): return "Bot calisiyor!"
    
    http_server = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080))), daemon=True)
    http_server.start()

    print("Bot aktif ve çalışıyor...")
    bot.infinity_polling(timeout=60)
