import os
import json
import random
from dotenv import load_dotenv
from flask import Flask
from threading import Thread, Timer
import requests
import html
from deep_translator import GoogleTranslator

load_dotenv()

with open("quiz_data.json", "r", encoding="utf-8") as f:
    QUIZ_QUESTIONS = json.load(f)
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from telebot import TeleBot
from google import genai
DEVELOPER_USERNAME = "HuseyinAcar35"

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

bot = TeleBot(BOT_TOKEN)
client = genai.Client(api_key=GEMINI_API_KEY)
USERS_FILE = "users_data.json"

def load_users():
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_users():
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)
users = load_users()
def get_question(level, category):
    if category == "karisik":
        uygun = [
            q for q in QUIZ_QUESTIONS
            if q["level"] <= level
        ]
    else:
        uygun = [
            q for q in QUIZ_QUESTIONS
            if q["level"] <= level and q["category"] == category
        ]
    return random.choice(uygun) if uygun else None
def send_question(chat_id, user_id):
    level = users[user_id]["level"]
    category = users[user_id]["category"]

    q = get_question(level, category)
    if not q:
        bot.send_message(chat_id, "❌ Bu kategoride soru kalmadı knk")
        return

    users[user_id]["current_answer"] = q["answer"]

    text = (
        f"🧠 {category.upper()} | Level {level}\n"
        f"❤️ Can: {users[user_id]['lives']}\n\n"
        f"{q['question']}\n\n" +
        "\n".join(q["options"])
    )

    msg = bot.send_message(chat_id, text)
    users[user_id]["last_question_message_id"] = msg.message_id
    save_users()

@bot.message_handler(commands=["start"])
def start_message(message):
    username = message.from_user.username
    if username:
        user_text = f"@{username}"
    else:
        user_text = message.from_user.first_name

    text = (
        f"Merhaba {user_text} 👋\n"
        "Lütfen dil seçiniz / Please choose a language / Моля, изберете език 🌍"
    )

    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("🇹🇷 Türkçe", callback_data="lang_tr"),
        InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
        InlineKeyboardButton("🇧🇬 Български", callback_data="lang_bg")
    )

    bot.send_message(message.chat.id, text, reply_markup=keyboard)
@bot.callback_query_handler(func=lambda call: call.data.startswith("lang_"))
def language_selected(call):
    username = call.from_user.username
    if username:
        user_text = f"@{username}"
    else:
        user_text = call.from_user.first_name

    # Dil tercihini kaydet / Save language preference
    user_id = str(call.from_user.id)
    lang_code = call.data.replace("lang_", "")
    if user_id not in users:
        users[user_id] = {"level": 1, "exp": 0, "lives": 3, "category": "karisik"}
    users[user_id]["lang"] = lang_code
    users[user_id]["name"] = call.from_user.first_name
    save_users()

    if call.data == "lang_tr":
        text = (
            f"Merhaba hoş geldin {user_text} 👋\n\n"
            "Ben geliştiricim Hüseyin tarafından yazıldım.\n\n"
            "🤖 **Komutlar:**\n"
            "🔹 /quiz - KPSS Soruları Çöz\n"
            "🔹 /clock - Global Yarışma (Zamanlı)\n"
            "🔹 /profil - Profilini Gör\n"
            "🔹 /top10 - Liderlik Tablosu\n\n"
            "Herhangi bir önerin veya geri bildirimin varsa\n"
            "aşağıdaki butona tıklayarak bana ulaşabilirsin 👇"
        )
        button_text = "📩 Geliştiriciye Mesaj Gönder"

    elif call.data == "lang_en":
        text = (
            f"Welcome {user_text} 👋\n\n"
            "I was developed by Hüseyin.\n\n"
            "🤖 **Commands:**\n"
            "🔹 /quiz - Solve Questions\n"
            "🔹 /clock - Global Trivia\n"
            "🔹 /profil - View Profile\n"
            "🔹 /top10 - Leaderboard\n\n"
            "If you have any suggestions or feedback,\n"
            "you can contact my developer by clicking the button below 👇"
        )
        button_text = "📩 Contact the Developer"

    else:  # lang_bg
        text = (
            f"Здравей, добре дошъл {user_text} 👋\n\n"
            "Аз бях създаден от моя разработчик Хюсеин.\n\n"
            "🤖 **Команди:**\n"
            "🔹 /quiz - Решаване на въпроси\n"
            "🔹 /clock - Глобален тест\n"
            "🔹 /profil - Виж профила\n"
            "🔹 /top10 - Класация\n\n"
            "Ако имаш предложения или обратна връзка,\n"
            "можеш да се свържеш с моя разработчик, като натиснеш бутона по-долу 👇"
        )
        button_text = "📩 Свържи се с разработчика"

    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton(
            text=button_text,
            url=f"https://t.me/{DEVELOPER_USERNAME}"
        )
    )

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=text,
        reply_markup=keyboard
    )
@bot.message_handler(commands=['quiz'])
def quiz(message):
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("📜 Tarih", callback_data="cat_tarih"),
        InlineKeyboardButton("🌍 Coğrafya", callback_data="cat_cografya")
    )
    kb.add(
        InlineKeyboardButton("⚖️ Vatandaşlık", callback_data="cat_vatandaslik"),
        InlineKeyboardButton("📰 Güncel", callback_data="cat_guncel")
    )
    kb.add(InlineKeyboardButton("🔀 Karışık", callback_data="cat_karisik"))

    bot.send_message(
        message.chat.id,
        "📚 KPSS Genel Kültür\n\nKategori seç knk 👇",
        reply_markup=kb
    )
@bot.callback_query_handler(func=lambda c: c.data.startswith("cat_"))
def category_selected(call):
    user_id = str(call.from_user.id)
    category = call.data.replace("cat_", "")

    if user_id not in users:
        users[user_id] = {"level": 1, "exp": 0, "lives": 3}

    users[user_id]["category"] = category
    users[user_id]["mode"] = "local"
    users[user_id]["name"] = call.from_user.first_name
    save_users()

    # 🔹 İlk soru gönder
    send_question(call.message.chat.id, user_id)

@bot.message_handler(commands=['clock'])
def open_trivia_question(message):
    user_id = str(message.from_user.id)
    
    # Kullanıcı yoksa oluştur
    if user_id not in users:
        users[user_id] = {"level": 1, "exp": 0, "lives": 3, "category": "karisik", "lang": "tr"}
    
    users[user_id]["mode"] = "global"
    users[user_id]["name"] = message.from_user.first_name
    save_users()
    
    target_lang = users[user_id].get("lang", "tr")
    
    # Bekleme mesajı
    wait_msg = bot.send_message(message.chat.id, "⏳ 🌍 ...")

    try:
        # 1. OpenTDB API'den soru çek
        response = requests.get("https://opentdb.com/api.php?amount=1&type=multiple", timeout=10)
        data = response.json()
        
        if data["response_code"] != 0:
            bot.edit_message_text("API Hatası / API Error", message.chat.id, wait_msg.message_id)
            return

        item = data["results"][0]
        
        # HTML karakterlerini temizle (örn: &quot; -> ")
        question_text = html.unescape(item["question"])
        correct_text = html.unescape(item["correct_answer"])
        incorrect_texts = [html.unescape(ans) for ans in item["incorrect_answers"]]
        
        # 2. Çeviri (Eğer dil İngilizce değilse)
        if target_lang != "en":
            translator = GoogleTranslator(source='auto', target=target_lang)
            # Hepsini tek seferde çevir (daha hızlı)
            texts_to_translate = [question_text, correct_text] + incorrect_texts
            translated = translator.translate_batch(texts_to_translate)
            
            question_text = translated[0]
            correct_text = translated[1]
            incorrect_texts = translated[2:]

        # 3. Şıkları hazırla ve karıştır
        all_options = incorrect_texts + [correct_text]
        random.shuffle(all_options)
        
        # Doğru cevabın harfini bul (A, B, C, D)
        letters = ["A", "B", "C", "D"]
        correct_index = all_options.index(correct_text)
        correct_letter = letters[correct_index]
        
        users[user_id]["current_answer"] = correct_letter
        save_users()
        
        options_text = "\n".join([f"{letters[i]}) {opt}" for i, opt in enumerate(all_options)])
        
        text = f"🌍 **Global Quiz** | {item['category']}\n\n❓ {question_text}\n\n{options_text}"
        
        bot.delete_message(message.chat.id, wait_msg.message_id)
        msg = bot.send_message(message.chat.id, text, parse_mode="Markdown")
        users[user_id]["last_question_message_id"] = msg.message_id
        save_users()
        
    except Exception as e:
        bot.edit_message_text(f"Hata / Error: {str(e)}", message.chat.id, wait_msg.message_id)

@bot.message_handler(func=lambda m: m.text and m.text.upper() in ["A", "B", "C", "D"])
def check_answer(message):
    user_id = str(message.from_user.id)

    if user_id not in users or "current_answer" not in users[user_id]:
        return
    
    # Eski soruyu ve kullanıcının cevabını sil / Delete old question and user answer
    if "last_question_message_id" in users[user_id]:
        try:
            bot.delete_message(message.chat.id, users[user_id]["last_question_message_id"])
        except:
            pass # Mesaj zaten silinmişse hata verme
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except:
        pass

    answer = message.text.upper()
    correct = users[user_id]["current_answer"]

    level = users[user_id]["level"]
    exp = users[user_id]["exp"]

    if answer == correct:
        exp += 20
        result = "✅ Doğru!"
    else:
        users[user_id]["lives"] -= 1
        exp = max(0, exp - 10)
        result = f"❌ Yanlış! ❤️ Kalan can: {users[user_id]['lives']}"

    # Level kontrolü
    if exp >= level * 100:
        level += 1
        exp = 0
        result += f"\n🎉 Level atladın! ({level})"

    users[user_id]["level"] = level
    users[user_id]["exp"] = exp

    # Can bitti mi?
    if users[user_id]["lives"] <= 0:
        bot.send_message(
            message.chat.id,
            f"{result}\n\n💀 Canların bitti!\n📊 Level: {level} | ⭐️ EXP: {exp}"
        )
        users[user_id]["lives"] = 3
        users[user_id].pop("current_answer", None)
        save_users()
        return

    msg = bot.send_message(
        message.chat.id,
        f"{result}\n\n📊 Level: {level}\n⭐️ EXP: {exp}/{level*100}"
    )
    
    def auto_delete():
        try:
            bot.delete_message(message.chat.id, msg.message_id)
        except:
            pass
    Timer(5.0, auto_delete).start()

    users[user_id].pop("current_answer", None)
    save_users()

    # 🔁 Otomatik yeni soru
    if users[user_id].get("mode") == "global":
        open_trivia_question(message)
    else:
        send_question(message.chat.id, user_id)

@bot.message_handler(commands=['profil'])
def my_profile(message):
    user_id = str(message.from_user.id)
    if user_id not in users:
        bot.reply_to(message, "Henüz bir profilin yok. /start ile başla!")
        return
    
    u = users[user_id]
    # İsim yoksa kaydet
    if "name" not in u:
        u["name"] = message.from_user.first_name
        save_users()

    text = (
        f"👤 **Profilin / Profile**\n\n"
        f"🏷 İsim: {u.get('name', 'Bilinmiyor')}\n"
        f"📊 Level: {u.get('level', 1)}\n"
        f"⭐️ EXP: {u.get('exp', 0)}\n"
        f"❤️ Can: {u.get('lives', 3)}\n"
        f"🌍 Mod: {u.get('mode', 'local').title()}\n"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['top10'])
def leaderboard(message):
    # Level'a göre, sonra EXP'ye göre sırala (Büyükten küçüğe)
    sorted_users = sorted(
        users.items(), 
        key=lambda x: (x[1].get("level", 1), x[1].get("exp", 0)), 
        reverse=True
    )[:10]
    
    text = "🏆 **Liderlik Tablosu (Top 10)** 🏆\n\n"
    for i, (uid, data) in enumerate(sorted_users, 1):
        name = data.get("name", "Gizli Oyuncu")
        lvl = data.get("level", 1)
        xp = data.get("exp", 0)
        text += f"{i}. {name} — 🏅 Lvl {lvl} | ⭐️ {xp}\n"
        
    bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda message: not message.text.startswith("/"))
def handle_message(message):
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=message.text
        )
        bot.reply_to(message, response.text)
    except Exception as e:
        bot.reply_to(message, "Bir hata oluştu knk 😅")

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot calisiyor! / I am alive!"

def run_http():
    # Render'ın atadığı PORT'u al, yoksa 8080 kullan
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    # Flask sunucusunu ayrı bir kanalda başlat ki botu engellemesin
    t = Thread(target=run_http)
    t.daemon = True
    t.start()
    
    # Botu çalıştır
    print("Bot aktif ve Render üzerinde çalışıyor...")
    try:
        bot.delete_webhook()
    except:
        pass
    bot.infinity_polling()