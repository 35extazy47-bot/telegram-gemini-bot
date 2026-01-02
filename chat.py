import os
import json
import random
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask
from threading import Thread, Timer, Lock
import requests
import html
from deep_translator import GoogleTranslator

load_dotenv()

with open("quiz_data.json", "r", encoding="utf-8") as f:
    QUIZ_QUESTIONS = json.load(f)
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from telebot import TeleBot
from google import genai
DEVELOPER_USERNAME = "HuseyinAcar35" # 👈 Buraya kendi kullanıcı adını yaz (@ olmadan)

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

bot = TeleBot(BOT_TOKEN)
client = genai.Client(api_key=GEMINI_API_KEY)
USERS_FILE = "users_data.json"
data_lock = Lock()

def safe_generate_content(prompt_content):
    """Modeller arası geçiş yaparak hata riskini azaltır."""
    # Sırasıyla bu modelleri dener. Biri çalışırsa cevap döner.
    models = ["gemini-2.5-flash", "gemini-1.5-flash", "gemini-2.0-flash-exp", "gemini-1.5-pro"]
    for model in models:
        try:
            return client.models.generate_content(
                model=model,
                contents=prompt_content
            )
        except Exception as e:
            print(f"⚠️ {model} hatası: {e} -> Diğer modele geçiliyor...")
    raise Exception("Tüm modeller başarısız oldu.")

# Yasaklı Kelimeler Listesi (Burayı istediğin gibi genişletebilirsin)
BANNED_WORDS = ["aptal", "salak", "gerizekalı", "mal", "ezik", "ahmak", "özürlü", "amq", "oruspu" ]

def load_users():
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_users():
    with data_lock:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
users = load_users()
def get_rank(level, username=None):
    if username == DEVELOPER_USERNAME:
        return "Kurucu 👑"
    if level >= 20:
        return "Bilge 🧙‍♂️"
    elif level >= 10:
        return "Usta ⚔️"
    elif level >= 5:
        return "Çırak 🛠️"
    else:
        return "Acemi 👶"

def check_daily_limit(user_id):
    """Kullanıcının günlük Gemini kullanım hakkını kontrol eder ve günceller."""
    # Yöneticiye (Sana) limit yok! 👑
    if users.get(user_id, {}).get("username") == DEVELOPER_USERNAME:
        return True

    today = datetime.now().strftime("%Y-%m-%d")
    user_data = users[user_id]
    
    # Eğer gün değişmişse sayacı sıfırla
    if user_data.get("last_gemini_date") != today:
        user_data["last_gemini_date"] = today
        user_data["daily_gemini_count"] = 0
    
    # Limit kontrolü (3 hak)
    if user_data.get("daily_gemini_count", 0) >= 3:
        return False
    
    # Kullanımı artır
    user_data["daily_gemini_count"] = user_data.get("daily_gemini_count", 0) + 1
    save_users()
    return True

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
    users[user_id]["current_question_id"] = q["id"]

    text = (
        f"🧠 {category.upper()} | Level {level}\n"
        f"❤️ Can: {users[user_id]['lives']}\n\n"
        f"{q['question']}\n\n" +
        "\n".join(q["options"])
    )

    # Joker Butonları
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("💡 %50 Joker (10 EXP)", callback_data="joker_50"),
        InlineKeyboardButton("⏭ Pas Geç (5 EXP)", callback_data="joker_pass"),
        InlineKeyboardButton("👥 Seyirci (15 EXP)", callback_data="joker_audience")
    )

    # Eğer soruda resim varsa fotoğraf olarak gönder
    if q.get("image"):
        try:
            msg = bot.send_photo(chat_id, photo=q["image"], caption=text, reply_markup=markup)
        except:
            msg = bot.send_message(chat_id, text, reply_markup=markup)
    else:
        msg = bot.send_message(chat_id, text, reply_markup=markup)
        
    users[user_id]["last_question_message_id"] = msg.message_id
    save_users()

def send_wrong_question(chat_id, user_id):
    wrong_ids = users[user_id].get("wrong_answers", [])
    if not wrong_ids:
        bot.send_message(chat_id, "🎉 **Tebrikler!** Yanlış yaptığın tüm soruları temizledin. Harikasın! 👏")
        users[user_id]["mode"] = "local"
        return

    q_id = random.choice(wrong_ids)
    # Soruyu bul
    q = next((item for item in QUIZ_QUESTIONS if item["id"] == q_id), None)
    
    if not q:
        # Soru veritabanından silinmişse listeden de sil
        users[user_id]["wrong_answers"].remove(q_id)
        send_wrong_question(chat_id, user_id)
        return

    users[user_id]["current_answer"] = q["answer"]
    users[user_id]["current_question_id"] = q["id"]

    text = (
        f"🔄 **Tekrar Zamanı** | {q['category'].upper()}\n"
        f"⚠️ Bu soruyu daha önce yanlış yapmıştın!\n\n"
        f"{q['question']}\n\n" +
        "\n".join(q['options'])
    )

    # Resim kontrolü (Tekrar soruları için)
    if q.get("image"):
        try:
            msg = bot.send_photo(chat_id, photo=q["image"], caption=text)
        except:
            msg = bot.send_message(chat_id, text)
    else:
        msg = bot.send_message(chat_id, text)
        
    users[user_id]["last_question_message_id"] = msg.message_id
    save_users()

@bot.message_handler(commands=["start"])
def start_message(message):
    user_id = str(message.from_user.id)
    username = message.from_user.username
    
    # 1. Kurucu ise her zaman onaylıdır ve giriş yapar
    if username == DEVELOPER_USERNAME:
        if user_id not in users:
            users[user_id] = {"level": 1, "exp": 0, "lives": 3, "category": "karisik", "is_approved": True}
            save_users()
        else:
            # Eğer önceden varsa ama approved flag yoksa ekle
            users[user_id]["is_approved"] = True
            save_users()

    # 2. Kullanıcı veritabanında yoksa (YENİ ÜYE)
    if user_id not in users:
        # Kullanıcıyı oluştur ama onaysız yap
        users[user_id] = {
            "level": 1, "exp": 0, "lives": 3, "category": "karisik",
            "is_approved": False, 
            "username": username,
            "name": message.from_user.first_name,
            "join_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        save_users()
        
        # Bilgi mesajı ve Talep Butonu
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📝 Üye Olmak İstiyorum", callback_data="request_access"))
        
        bot.send_message(message.chat.id, "🔒 **Bot Erişim İzni**\n\nMerhaba! Bu bot özel bir bottur ve sadece onaylı üyeler kullanabilir.\n\nErişim izni istemek için aşağıdaki butona tıklayabilirsin. 👇", reply_markup=markup)
        return

    # 3. Kullanıcı var ama onayı yoksa (Daha önce girmiş ama onaylanmamış)
    if not users.get(user_id, {}).get("is_approved", True): # Varsayılan True (Eski üyeler için)
        bot.send_message(message.chat.id, "⏳ **Onay Bekleniyor...**\n\nTalebiniz yöneticilere iletildi. Lütfen onaylanmayı bekleyin.")
        return

    # 4. Onaylı kullanıcılar için normal akış
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

@bot.callback_query_handler(func=lambda c: c.data == "request_access")
def request_access_handler(call):
    user_id = str(call.from_user.id)
    
    # Kullanıcıya bilgi ver
    bot.edit_message_text("✅ **Talebiniz Alındı!**\n\nKurucuya bildirim gönderildi. Onaylandığında size mesaj gelecektir. Lütfen bekleyin. ⏳", call.message.chat.id, call.message.message_id)
    
    # Kurucuya (Admin) bildirim gönder
    admin_id = get_admin_id()
    if admin_id:
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("✅ Onayla", callback_data=f"approve_{user_id}"),
            InlineKeyboardButton("❌ Reddet", callback_data=f"reject_{user_id}")
        )
        
        user_info = f"👤 İsim: {call.from_user.first_name}\n🆔 ID: {user_id}\n🔗 Kullanıcı Adı: @{call.from_user.username}"
        bot.send_message(admin_id, f"🔔 **YENİ ÜYELİK TALEBİ!**\n\n{user_info}\n\nBotu kullanmak için izin istiyor.", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("approve_") or c.data.startswith("reject_"))
def admin_approval_callback(call):
    # Sadece geliştirici bu butonları kullanabilir
    if call.from_user.username != DEVELOPER_USERNAME:
        bot.answer_callback_query(call.id, "⛔ Yetkisiz işlem!")
        return
        
    action, target_id = call.data.split("_")
    
    if action == "approve":
        if target_id in users:
            users[target_id]["is_approved"] = True
            save_users()
            
            bot.edit_message_text(f"✅ Kullanıcı ({target_id}) **ONAYLANDI**.", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
            
            # Kullanıcıya müjdeyi ver
            try:
                bot.send_message(target_id, "🎉 **Tebrikler! Üyeliğiniz Onaylandı!**\n\nArtık botu kullanabilirsiniz.\nBaşlamak için 👉 /start yazın.")
            except:
                pass
        else:
            bot.answer_callback_query(call.id, "Kullanıcı bulunamadı.")
            
    elif action == "reject":
        bot.edit_message_text(f"❌ Kullanıcı ({target_id}) **REDDEDİLDİ**.", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        # İstersen kullanıcıya reddedildi mesajı atabilirsin veya sessiz kalabilirsin.

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
    users[user_id]["username"] = call.from_user.username
    save_users()

    messages = {
        "tr": {
            "text": (
                f"Merhaba hoş geldin {user_text} 👋\n\n"
                "Ben geliştiricim tarafından yazıldım.\n\n"
                "🤖 **Komutlar:**\n"
                "🔹 /quiz - KPSS Soruları Çöz\n"
                "🔹 /macera - Tarihsel Macera (Yeni!)\n"
                "🔹 /clock - Global Yarışma (Zamanlı)\n"
                "🔹 /ikna - Botu İkna Et (Münazara)\n"
                "🔹 /tarihtebugun - Tarihte Bugün Ne Oldu?\n"
                "🔹 /profil - Profilini Gör\n"
                "🔹 /top10 - Liderlik Tablosu\n\n"
                "🛒 /market - Puanlarını Harca\n"
                "🎲 /bahis - Risk Al ve Kazan\n"
                "🧠 /bilgi - İlginç Bilgiler Öğren\n"
                "🔮 /ruya - Rüya Tabiri\n"
                "⛏️ /kaz - Maden Kaz ve Hazine Bul\n"
                "🎒 /envanter - Çantana Bak\n"
                "🔄 /yanlislarim - Hatalarını Telafi Et\n"
                "⚔️ /duello - Botla Kapış\n"
                "Herhangi bir önerin veya geri bildirimin varsa\n"
                "aşağıdaki butona tıklayarak bana ulaşabilirsin 👇"
            ),
            "btn": " Geliştiriciye Mesaj Gönder"
        },
        "en": {
            "text": (
                f"Welcome {user_text} 👋\n\n"
                "I was developed by my creator.\n\n"
                "🤖 **Commands:**\n"
                "🔹 /quiz - Solve Questions\n"
                "🔹 /macera - Historical Adventure (New!)\n"
                "🔹 /ikna - Debate with AI\n"
                "🔹 /tarihtebugun - On This Day\n"
                "🔹 /clock - Global Trivia\n"
                "🔹 /profil - View Profile\n"
                "🔹 /top10 - Leaderboard\n\n"
                "🔮 /ruya - Dream Interpretation\n"
                "If you have any suggestions or feedback,\n"
                "you can contact my developer by clicking the button below 👇"
            ),
            "btn": "📩 Contact the Developer"
        },
        "bg": {
            "text": (
                f"Здравей, добре дошъл {user_text} 👋\n\n"
                "Аз бях създаден от моя разработчик.\n\n"
                "🤖 **Команди:**\n"
                "🔹 /quiz - Решаване на въпроси\n"
                "🔹 /macera - Историческо приключение (Ново!)\n"
                "🔹 /ikna - Дебат с AI\n"
                "🔹 /tarihtebugun - На този ден\n"
                "🔹 /clock - Глобален тест\n"
                "🔹 /profil - Виж профила\n"
                "🔹 /top10 - Класация\n\n"
                "🔮 /ruya - Тълкуване на сънища\n"
                "Ако имаш предложения или обратна връзка,\n"
                "можеш да се свържеш с моя разработчик, като натиснеш бутона по-долу 👇"
            ),
            "btn": "📩 Свържи се с разработчика"
        }
    }

    selected = messages.get(lang_code, messages["en"])

    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton(
            text=selected["btn"],
            url=f"https://t.me/{DEVELOPER_USERNAME}"
        )
    )

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=selected["text"],
        reply_markup=keyboard
    )
@bot.message_handler(commands=['quiz'])
def quiz(message):
    user_id = str(message.from_user.id)
    if not users.get(user_id, {}).get("is_approved", True):
        bot.reply_to(message, "⛔ Botu kullanmak için onay almalısınız. /start yazarak talep oluşturun.")
        return
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
    users[user_id]["username"] = call.from_user.username
    save_users()

    # 🔹 İlk soru gönder
    send_question(call.message.chat.id, user_id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("joker_"))
def handle_jokers(call):
    user_id = str(call.from_user.id)
    action = call.data
    
    if user_id not in users:
        return

    current_exp = users[user_id].get("exp", 0)
    correct_answer = users[user_id].get("current_answer")

    if not correct_answer:
        bot.answer_callback_query(call.id, "⚠️ Aktif bir soru yok!")
        return

    # --- %50 JOKER ---
    if action == "joker_50":
        if current_exp < 10:
            bot.answer_callback_query(call.id, "❌ Yetersiz EXP! (Gereken: 10)", show_alert=True)
            return
        
        # Yanlış şıkları bul
        options = ["A", "B", "C", "D"]
        if correct_answer in options:
            options.remove(correct_answer)
        
        # Rastgele 2 yanlış şık seç
        eliminated = random.sample(options, 2)
        users[user_id]["exp"] -= 10
        save_users()
        
        bot.answer_callback_query(
            call.id, 
            f"💡 İpucu: {eliminated[0]} ve {eliminated[1]} şıkları YANLIŞ! ❌", 
            show_alert=True
        )

    # --- PAS GEÇ ---
    elif action == "joker_pass":
        if current_exp < 5:
            bot.answer_callback_query(call.id, "❌ Yetersiz EXP! (Gereken: 5)", show_alert=True)
            return

        users[user_id]["exp"] -= 5
        save_users()
        
        bot.answer_callback_query(call.id, "⏭ Soru geçiliyor...", show_alert=False)
        
        # Eski mesajı silmeye çalış
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass

    # --- SEYİRCİ JOKERİ ---
    elif action == "joker_audience":
        if current_exp < 15:
            bot.answer_callback_query(call.id, "❌ Yetersiz EXP! (Gereken: 15)", show_alert=True)
            return

        users[user_id]["exp"] -= 15
        save_users()

        # Mantık: Doğru cevaba %50-%80 arası ver, kalanı diğerlerine dağıt
        options = ["A", "B", "C", "D"]
        percentages = {}
        remaining_percent = 100

        # Doğru cevap oranı
        correct_percent = random.randint(50, 85)
        percentages[correct_answer] = correct_percent
        remaining_percent -= correct_percent

        # Yanlış şıklar
        wrong_options = [o for o in options if o != correct_answer]
        
        # Kalan yüzdeyi rastgele dağıt
        for i, opt in enumerate(wrong_options):
            if i == len(wrong_options) - 1:
                percentages[opt] = remaining_percent
            else:
                val = random.randint(0, remaining_percent)
                percentages[opt] = val
                remaining_percent -= val

        msg_text = "👥 **Seyirci Oylaması:**\n\n" + "\n".join([f"{k}: %{v} {'█' * (v // 10)}" for k, v in sorted(percentages.items())])
        bot.answer_callback_query(call.id, "Seyirciler oyladı! Sonuçlar mesaj olarak geldi.", show_alert=False)
        bot.send_message(call.message.chat.id, msg_text, parse_mode="Markdown")
        # Yeni soru gönder
        if users[user_id].get("mode") == "global":
            open_trivia_question(call.message)
        else:
            send_question(call.message.chat.id, user_id)

@bot.message_handler(commands=['clock'])
def open_trivia_question(message):
    user_id = str(message.from_user.id)
    if not users.get(user_id, {}).get("is_approved", True):
        bot.reply_to(message, "⛔ Onay bekleniyor...")
        return
    
    # Kullanıcı yoksa oluştur
    if user_id not in users:
        users[user_id] = {"level": 1, "exp": 0, "lives": 3, "category": "karisik", "lang": "tr"}
    
    users[user_id]["mode"] = "global"
    users[user_id]["name"] = message.from_user.first_name
    users[user_id]["username"] = message.from_user.username
    users[user_id].pop("current_question_id", None) # Global sorularda ID takibi yok
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
        
        # Joker Butonları
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("💡 %50 Joker (10 EXP)", callback_data="joker_50"),
            InlineKeyboardButton("⏭ Pas Geç (5 EXP)", callback_data="joker_pass"),
            InlineKeyboardButton("👥 Seyirci (15 EXP)", callback_data="joker_audience")
        )

        bot.delete_message(message.chat.id, wait_msg.message_id)
        msg = bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)
        users[user_id]["last_question_message_id"] = msg.message_id
        save_users()
        
    except Exception as e:
        bot.edit_message_text(f"Hata / Error: {str(e)}", message.chat.id, wait_msg.message_id)

@bot.message_handler(commands=['market'])
def market_menu(message):
    user_id = str(message.from_user.id)
    if not users.get(user_id, {}).get("is_approved", True):
        bot.reply_to(message, "⛔ Onay bekleniyor...")
        return
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("❤️ +1 Can (100 EXP)", callback_data="buy_life"))
    markup.add(InlineKeyboardButton("🎁 Şans Kutusu (50 EXP)", callback_data="buy_box"))
    markup.add(InlineKeyboardButton("⛏️ Elmas Kazma (500 EXP)", callback_data="buy_pickaxe"))
    bot.send_message(message.chat.id, "🛒 **MARKET**\n\nPuanlarını harcayarak güçlenebilirsin!", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data.startswith("buy_"))
def market_buy(call):
    user_id = str(call.from_user.id)
    if user_id not in users: return
    
    if call.data == "buy_life":
        cost = 100
        if users[user_id]["exp"] < cost:
            bot.answer_callback_query(call.id, "❌ Yetersiz EXP!", show_alert=True)
            return
        users[user_id]["exp"] -= cost
        users[user_id]["lives"] += 1
        bot.answer_callback_query(call.id, "✅ +1 Can satın alındı!")
        
    elif call.data == "buy_box":
        cost = 50
        if users[user_id]["exp"] < cost:
            bot.answer_callback_query(call.id, "❌ Yetersiz EXP!", show_alert=True)
            return
        users[user_id]["exp"] -= cost
        
        # Rastgele ödül mantığı
        reward = random.choice(["exp_20", "exp_100", "life_1", "empty"])
        if reward == "exp_20":
            users[user_id]["exp"] += 20
            msg = "kutudan 20 EXP çıktı! (Zarar ettin 😅)"
        elif reward == "exp_100":
            users[user_id]["exp"] += 100
            msg = "🎉 TEBRİKLER! Kutudan 100 EXP çıktı!"
        elif reward == "life_1":
            users[user_id]["lives"] += 1
            msg = "❤️ Kutudan 1 Can çıktı!"
        else:
            msg = "💨 Kutu boş çıktı... Şansına küs!"
            
        bot.answer_callback_query(call.id, "Kutu açılıyor...", show_alert=False)
        bot.send_message(call.message.chat.id, f"🎁 **ŞANS KUTUSU SONUCU:**\n{msg}", parse_mode="Markdown")

    elif call.data == "buy_pickaxe":
        if users[user_id].get("has_pickaxe"):
            bot.answer_callback_query(call.id, "⚠️ Zaten en iyi kazmaya sahipsin!", show_alert=True)
            return
        cost = 500
        if users[user_id]["exp"] < cost:
            bot.answer_callback_query(call.id, "❌ Yetersiz EXP! (500 Gerekli)", show_alert=True)
            return
        users[user_id]["exp"] -= cost
        users[user_id]["has_pickaxe"] = True
        bot.answer_callback_query(call.id, "✅ Elmas Kazma satın alındı! Artık madende daha şanslısın.")
        
    save_users()

@bot.message_handler(commands=['bahis'])
def set_bet(message):
    user_id = str(message.from_user.id)
    if not users.get(user_id, {}).get("is_approved", True):
        bot.reply_to(message, "⛔ Onay bekleniyor...")
        return
    if user_id not in users: return
    
    try:
        amount = int(message.text.split()[1])
    except:
        bot.reply_to(message, "⚠️ Kullanım: /bahis <miktar>\nÖrnek: /bahis 50")
        return
        
    if amount <= 0:
        bot.reply_to(message, "❌ Pozitif bir sayı girmelisin.")
        return
        
    if users[user_id]["exp"] < amount:
        bot.reply_to(message, f"❌ Yetersiz EXP! Mevcut: {users[user_id]['exp']}")
        return
        
    if users[user_id].get("active_bet", 0) > 0:
        bot.reply_to(message, "⚠️ Zaten aktif bir bahsin var! Önce sıradaki soruyu çöz.")
        return
    
    users[user_id]["exp"] -= amount
    users[user_id]["active_bet"] = amount
    save_users()
    
    bot.reply_to(message, f"🎲 **BAHİS OYNANDI!**\n\nMasaya {amount} EXP koydun.\nSıradaki soruyu doğru bilirsen {amount * 2} EXP kazanacaksın!\nYanlış bilirsen para gider. 💸")

@bot.message_handler(commands=['kaz'])
def mine_resource(message):
    user_id = str(message.from_user.id)
    if not users.get(user_id, {}).get("is_approved", True):
        bot.reply_to(message, "⛔ Onay bekleniyor...")
        return
    if user_id not in users: return

    # Cooldown kontrolü (15 dakika)
    last_mine = users[user_id].get("last_mine_time")
    now = datetime.utcnow()
    
    if last_mine:
        last_time = datetime.strptime(last_mine, "%Y-%m-%d %H:%M:%S")
        diff = now - last_time
        if diff.total_seconds() < 900: # 900 saniye = 15 dk
            remaining = int((900 - diff.total_seconds()) / 60)
            bot.reply_to(message, f"⏳ Maden yorgun knk! İşçiler dinleniyor.\n{remaining} dakika sonra tekrar gel.")
            return

    users[user_id]["last_mine_time"] = now.strftime("%Y-%m-%d %H:%M:%S")
    has_pickaxe = users[user_id].get("has_pickaxe", False)
    
    # Şans faktörü (1-100)
    roll = random.randint(1, 100)
    if has_pickaxe:
        roll += 10 # Kazma varsa şans artar
        
    if roll > 95: # Elmas
        amount = random.randint(200, 300)
        users[user_id]["exp"] += amount
        msg = f"💎 **İNANILMAZ!** Bir ELMAS buldun!\nDeğeri: +{amount} EXP"
    elif roll > 75: # Altın
        amount = random.randint(50, 100)
        users[user_id]["exp"] += amount
        msg = f"✨ **Parıl parıl!** Altın damarı buldun.\nKazanç: +{amount} EXP"
    elif roll > 40: # Kömür/Demir
        amount = random.randint(15, 40)
        users[user_id]["exp"] += amount
        msg = f"⛏️ Demir ve Kömür çıkardın.\nKazanç: +{amount} EXP"
    elif roll > 15: # Boş
        msg = "💨 Maalesef bu sefer sadece toz ve toprak çıktı..."
    else: # Göçük (Risk)
        if has_pickaxe and random.random() > 0.5:
             msg = "⚠️ Göçük oldu ama **Elmas Kazman** seni korudu! Ucuz atlattın."
        else:
            users[user_id]["lives"] -= 1
            msg = "💥 **GÖÇÜK!** Maden üzerine çöktü.\nHasar: -1 Can ❤️"
            
    save_users()
    bot.reply_to(message, msg, parse_mode="Markdown")

@bot.message_handler(commands=['envanter'])
def show_inventory(message):
    user_id = str(message.from_user.id)
    if not users.get(user_id, {}).get("is_approved", True):
        bot.reply_to(message, "⛔ Onay bekleniyor...")
        return
    if user_id not in users: return
    
    u = users[user_id]
    
    # Eşyalar listesi
    items = []
    if u.get("has_pickaxe"):
        items.append("⛏️ **Elmas Kazma** (Maden şansını artırır)")
    
    # Eğer hiç eşya yoksa
    if not items:
        items_text = "💨 Çantan boş..."
    else:
        items_text = "\n".join(items)
        
    text = (
        f"🎒 **ENVANTERİN**\n\n"
        f"👤 **Sahibi:** {u.get('name', 'Bilinmiyor')}\n"
        f"💰 **Varlık:** {u.get('exp', 0)} EXP\n"
        f"❤️ **Can:** {u.get('lives', 3)}\n"
        f"🎖 **Rütbe:** {get_rank(u.get('level', 1), u.get('username'))}\n\n"
        f"📦 **Eşyalar:**\n{items_text}"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['duello'])
def duel_bot(message):
    user_id = str(message.from_user.id)
    if not users.get(user_id, {}).get("is_approved", True):
        bot.reply_to(message, "⛔ Onay bekleniyor...")
        return
    if user_id not in users: return

    try:
        amount = int(message.text.split()[1])
    except:
        bot.reply_to(message, "⚠️ Kullanım: /duello <miktar>\nÖrnek: /duello 100")
        return

    if amount <= 0:
        bot.reply_to(message, "❌ Pozitif bir sayı girmelisin.")
        return

    if users[user_id]["exp"] < amount:
        bot.reply_to(message, f"❌ Yetersiz EXP! Mevcut: {users[user_id]['exp']}")
        return

    # Zar atma mantığı
    user_roll = random.randint(1, 6)
    bot_roll = random.randint(1, 6)
    
    msg = f"⚔️ **DÜELLO BAŞLADI!** ⚔️\nOrtadaki Ödül: {amount * 2} EXP\n\n"
    msg += f"👤 Senin Zarın: 🎲 {user_roll}\n"
    msg += f"🤖 Botun Zarı: 🎲 {bot_roll}\n\n"
    
    if user_roll > bot_roll:
        users[user_id]["exp"] += amount
        msg += f"🎉 **KAZANDIN!** Botu ezip geçtin! (+{amount} EXP)"
    elif bot_roll > user_roll:
        users[user_id]["exp"] -= amount
        msg += f"💀 **KAYBETTİN!** Bot seni yendi... (-{amount} EXP)"
    else:
        msg += "🤝 **BERABERE!** Zarlar aynı geldi, puanın iade edildi."
        
    save_users()
    bot.send_message(message.chat.id, msg, parse_mode="Markdown")

@bot.message_handler(commands=['yanlislarim'])
def retry_wrongs(message):
    user_id = str(message.from_user.id)
    if not users.get(user_id, {}).get("is_approved", True):
        bot.reply_to(message, "⛔ Onay bekleniyor...")
        return
    if user_id not in users: return
    
    users[user_id]["mode"] = "retry"
    users[user_id]["name"] = message.from_user.first_name
    save_users()
    send_wrong_question(message.chat.id, user_id)

@bot.message_handler(commands=['bilgi'])
def random_fact(message):
    user_id = str(message.from_user.id)
    if not users.get(user_id, {}).get("is_approved", True):
        bot.reply_to(message, "⛔ Onay bekleniyor...")
        return

    if not check_daily_limit(user_id):
        bot.reply_to(message, "⛔ Günlük Gemini mesaj hakkın (3/3) doldu! Yarın tekrar gel.")
        return

    try:
        prompt = "Bana çok ilginç, şaşırtıcı ve kısa bir genel kültür bilgisi ver. Sadece bilgiyi yaz."
        response = safe_generate_content(prompt)
        bot.reply_to(message, f"🧠 **Bunları Biliyor muydun?**\n\n{response.text}")
    except Exception as e:
        print(f"Bilgi Hatasi: {e}")
        bot.reply_to(message, "Şu an bilgi veremiyorum knk :(")

@bot.message_handler(func=lambda m: m.text and m.text.upper() in ["A", "B", "C", "D"])
def check_answer(message):
    user_id = str(message.from_user.id)
    if not users.get(user_id, {}).get("is_approved", True):
        return

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
    streak = users[user_id].get("streak", 0)
    bet_amount = users[user_id].get("active_bet", 0)

    if answer == correct:
        # Eğer tekrar modundaysak veya normal modda yanlış listesindeyse sil
        if "current_question_id" in users[user_id]:
            q_id = users[user_id]["current_question_id"]
            if "wrong_answers" in users[user_id] and q_id in users[user_id]["wrong_answers"]:
                users[user_id]["wrong_answers"].remove(q_id)

        users[user_id]["total_correct"] = users[user_id].get("total_correct", 0) + 1
        streak += 1
        
        # Puan Hesaplama
        base_points = 20
        streak_bonus = streak * 2
        total_points = base_points + streak_bonus

        # Happy Hour (20:00 - 22:00 TR Saati)
        now = datetime.utcnow() + timedelta(hours=3)
        is_happy_hour = 20 <= now.hour < 22

        if is_happy_hour:
            total_points *= 2
            result = f"✅ **Mükemmel! Doğru Cevap!** 🎉\n🔥 **HAPPY HOUR (2x EXP)** 🔥\n🔥 Combo: {streak}x"
        else:
            result = f"✅ **Mükemmel! Doğru Cevap!** 🎉\n🔥 Combo: {streak}x (+{streak_bonus} Bonus)"
            
        # Bahis Kazancı
        if bet_amount > 0:
            win_amount = bet_amount * 2
            total_points += win_amount
            result += f"\n🎲 **BAHİS KAZANDIN!** (+{win_amount} EXP)"
            users[user_id]["active_bet"] = 0
            
        exp += total_points
    else:
        # Yanlış yapıldıysa listeye ekle (Sadece local modda)
        if users[user_id].get("mode") == "local" and "current_question_id" in users[user_id]:
            q_id = users[user_id]["current_question_id"]
            if "wrong_answers" not in users[user_id]:
                users[user_id]["wrong_answers"] = []
            if q_id not in users[user_id]["wrong_answers"]:
                users[user_id]["wrong_answers"].append(q_id)

        streak = 0
        users[user_id]["lives"] -= 1
        exp = max(0, exp - 10)
        result = f"❌ **Maalesef Yanlış!** 🥀\nDoğru Cevap: {correct}\n❤️ Kalan Can: {users[user_id]['lives']}"
        
        if bet_amount > 0:
            result += f"\n💸 **BAHİS KAYBETTİN!** (-{bet_amount} EXP)"
            users[user_id]["active_bet"] = 0

    # Level kontrolü
    old_rank = get_rank(level, users[user_id].get("username"))
    if exp >= level * 100:
        level += 1
        exp = 0
        result += f"\n\n🚀 **TEBRİKLER! LEVEL ATLADIN!** 🚀\n🏆 Yeni Seviye: {level}"
        
        new_rank = get_rank(level, users[user_id].get("username"))
        if new_rank != old_rank:
            result += f"\n🎖 **YENİ RÜTBE:** {new_rank}"
            
        if level == 15:
            result += "\n🌟 **TEBRİKLER! ARTIK VIP ÜYESİN!** 👑\nBundan sonra adının yanında taç taşıyacaksın!"

    users[user_id]["level"] = level
    users[user_id]["exp"] = exp
    users[user_id]["streak"] = streak
    users[user_id]["total_questions"] = users[user_id].get("total_questions", 0) + 1

    # Can bitti mi?
    if users[user_id]["lives"] <= 0:
        bot.send_message(
            message.chat.id,
            f"{result}\n\n💀 **OYUN BİTTİ!** 💀\nCanların tükendi knk.\n📊 Ulaşılan Level: {level} | ⭐️ Toplam EXP: {exp}\n\n🔄 /quiz veya /clock yazarak tekrar başla!"
        )
        users[user_id]["lives"] = 3
        users[user_id].pop("current_answer", None)
        save_users()
        return

    msg = bot.send_message(
        message.chat.id,
        f"{result}\n\n📊 Level: {level} | ⭐️ EXP: {exp}/{level*100}"
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
    elif users[user_id].get("mode") == "retry":
        send_wrong_question(message.chat.id, user_id)
    else:
        send_question(message.chat.id, user_id)

@bot.message_handler(commands=['profil'])
def my_profile(message):
    user_id = str(message.from_user.id)
    if not users.get(user_id, {}).get("is_approved", True):
        bot.reply_to(message, "⛔ Onay bekleniyor...")
        return
    if user_id not in users:
        bot.reply_to(message, "Henüz bir profilin yok. /start ile başla!")
        return
    
    u = users[user_id]
    # Bilgileri güncelle
    u["name"] = message.from_user.first_name
    u["username"] = message.from_user.username
    save_users()

    total = u.get('total_questions', 0)
    correct_count = u.get('total_correct', 0)
    success_rate = (correct_count / total * 100) if total > 0 else 0

    dev_icon = " 👨‍💻" if u.get("username") == DEVELOPER_USERNAME else ""
    is_vip = u.get('level', 1) >= 15
    status_text = "👑 VIP Üye" if is_vip else "Standart Üye"
    
    equip = "⛏️ Elmas Kazma" if u.get("has_pickaxe") else "Yok"

    text = (
        f"👤 **Profilin / Profile**\n\n"
        f"🏷 İsim: {u.get('name', 'Bilinmiyor')}{dev_icon}\n"
        f"💎 Statü: {status_text}\n"
        f"🎒 Ekipman: {equip}\n"
        f"📊 Level: {u.get('level', 1)}\n"
        f"🎖 Rütbe: {get_rank(u.get('level', 1), u.get('username'))}\n"
        f"📝 Çözülen Soru: {total}\n"
        f"🎯 Başarı: %{success_rate:.1f}\n"
        f"⭐️ EXP: {u.get('exp', 0)}\n"
        f"❤️ Can: {u.get('lives', 3)}\n"
        f"🌍 Mod: {u.get('mode', 'local').title()}\n"
    )

    if total > 5 and success_rate < 30:
        text += "\n💡 **Tavsiye:** Biraz daha çalışmalısın knk! 📚 Bol bol test çöz."
    elif total > 5 and success_rate > 80:
        text += "\n🔥 **Durum:** Harika gidiyorsun! Bu hızla devam et. 🚀"

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
        
        t_q = data.get('total_questions', 0)
        t_c = data.get('total_correct', 0)
        rate = (t_c / t_q * 100) if t_q > 0 else 0
        
        rank = get_rank(lvl, data.get("username"))
        vip_tag = " 👑" if lvl >= 15 else ""
        dev_tag = " 👨‍💻" if data.get("username") == DEVELOPER_USERNAME else ""
        text += f"{i}. {name}{vip_tag}{dev_tag} — {rank} | 🏅 Lvl {lvl} | ⭐️ {xp} (🎯 %{rate:.0f})\n"
        
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['admin_panel'])
def admin_panel(message):
    if message.from_user.username != DEVELOPER_USERNAME:
        bot.reply_to(message, "⛔ Bu komut sadece Kurucu'ya özeldir!")
        return

    user_count = len(users)
    total_questions_solved = sum(u.get("total_questions", 0) for u in users.values())
    
    text = (
        f"👑 **YÖNETİCİ PANELİ** 👑\n\n"
        f"👥 **Toplam Kullanıcı:** {user_count}\n"
        f"📝 **Toplam Çözülen Soru:** {total_questions_solved}\n\n"
        "👇 **Hızlı İşlemler:**"
    )

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("⏳ Onay Bekleyenler", callback_data="admin_pending_list"))
    markup.add(InlineKeyboardButton("👥 Kayıtlı Üyeler", callback_data="admin_user_list"))
    markup.add(InlineKeyboardButton("📢 Duyuru Bilgisi", callback_data="admin_help_duyuru"))
    markup.add(InlineKeyboardButton("🎁 Hediye Bilgisi", callback_data="admin_help_hediye"))
    markup.add(InlineKeyboardButton("💾 Veritabanını İndir", callback_data="admin_backup"))

    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_"))
def admin_callbacks(call):
    if call.from_user.username != DEVELOPER_USERNAME:
        bot.answer_callback_query(call.id, "⛔ Yetkisiz işlem!")
        return

    if call.data == "admin_help_duyuru":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "📢 **Duyuru Kullanımı:**\n`/duyuru Mesajınız`\nÖrnek: `/duyuru Yarın bakım var!`", parse_mode="Markdown")
    
    elif call.data == "admin_pending_list":
        pending_users = [
            (uid, u) for uid, u in users.items() 
            if not u.get("is_approved", True)
        ]
        
        if not pending_users:
            bot.answer_callback_query(call.id, "✅ Onay bekleyen kimse yok!")
            return
            
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, f"⏳ **Onay Bekleyen {len(pending_users)} Kişi Var:**")
        
        for uid, u in pending_users:
            info = f"👤 {u.get('name', 'Bilinmiyor')}\n🆔 `{uid}`\n🔗 @{u.get('username', 'Yok')}"
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("✅ Onayla", callback_data=f"approve_{uid}"), InlineKeyboardButton("❌ Reddet", callback_data=f"reject_{uid}"))
            bot.send_message(call.message.chat.id, info, reply_markup=markup, parse_mode="Markdown")

    elif call.data == "admin_user_list":
        if not users:
            bot.answer_callback_query(call.id, "Hiç üye yok!")
            return
            
        text = "📋 **Kayıtlı Üyeler Listesi**\n\n"
        for i, (uid, u) in enumerate(users.items(), 1):
            name = u.get("name", "Bilinmiyor")
            username = u.get("username", "Yok")
            level = u.get("level", 1)
            line = f"{i}. {name} (@{username}) - ID: `{uid}` - Lvl: {level}\n"
            
            if len(text + line) > 4000:
                bot.send_message(call.message.chat.id, text, parse_mode="Markdown")
                text = ""
            text += line
            
        if text:
            bot.send_message(call.message.chat.id, text, parse_mode="Markdown")
        bot.answer_callback_query(call.id)

    elif call.data == "admin_help_hediye":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "🎁 **Hediye Kullanımı:**\n`/hediye <USER_ID> <MİKTAR>`\nÖrnek: `/hediye 123456789 500`", parse_mode="Markdown")
        
    elif call.data == "admin_backup":
        try:
            with open(USERS_FILE, "rb") as f:
                bot.send_document(call.message.chat.id, f, caption=f"💾 Yedek: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        except Exception as e:
            bot.send_message(call.message.chat.id, f"Hata: {e}")

@bot.message_handler(commands=['duyuru'])
def admin_broadcast_manual(message):
    # Sadece geliştirici kullanabilir
    if message.from_user.username != DEVELOPER_USERNAME:
        return

    # Komuttan sonraki metni al
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, "⚠️ Mesaj yazmayı unuttun knk!\nÖrnek: /duyuru Herkese selam")
        return

    text_to_send = args[1]
    count = 0
    
    bot.reply_to(message, "📨 Gönderim başladı...")
    
    for user_id in list(users.keys()):
        try:
            bot.send_message(user_id, f"📢 **DUYURU** 📢\n\n{text_to_send}", parse_mode="Markdown")
            count += 1
        except:
            pass
            
    bot.reply_to(message, f"✅ Mesaj başarıyla {count} kişiye iletildi.")

@bot.message_handler(commands=['ozet'])
def get_summary(message):
    user_id = str(message.from_user.id)
    if not users.get(user_id, {}).get("is_approved", True):
        bot.reply_to(message, "⛔ Onay bekleniyor...")
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, "⚠️ Hangi konuyu özetleyeyim? Örnek: `/ozet Islahat Fermanı`")
        return

    if not check_daily_limit(user_id):
        bot.reply_to(message, "⛔ Günlük Gemini mesaj hakkın (3/3) doldu! Yarın tekrar gel.")
        return
    
    topic = args[1]
    wait_msg = bot.reply_to(message, f"📚 '{topic}' konusu hazırlanıyor...")
    
    try:
        prompt = f"KPSS öğrencisi için '{topic}' konusunu maddeler halinde, akılda kalıcı ve özet şekilde anlat. Çok uzun olmasın, önemli noktaları vurgula. En sona bu konuyla ilgili 1 adet çoktan seçmeli örnek soru ve cevabını ekle."
        response = safe_generate_content(prompt)
        bot.delete_message(message.chat.id, wait_msg.message_id)
        bot.reply_to(message, f"📝 **KONU ÖZETİ: {topic.upper()}**\n\n{response.text}", parse_mode="Markdown")
    except Exception as e:
        print(f"Ozet Hatasi: {e}")
        bot.edit_message_text("Özet çıkarırken bir hata oluştu.", message.chat.id, wait_msg.message_id)

@bot.message_handler(commands=['pomodoro'])
def start_pomodoro(message):
    user_id = str(message.from_user.id)
    if not users.get(user_id, {}).get("is_approved", True):
        bot.reply_to(message, "⛔ Onay bekleniyor...")
        return
    msg = bot.reply_to(message, "🍅 **Pomodoro Başladı!**\n\n25 dakika boyunca odaklan. Süre bitince seni etiketleyip haber vereceğim! 📚\n_(Botu sessize alma)_")
    
    def finish_pomodoro():
        try:
            bot.reply_to(msg, "⏰ **SÜRE DOLDU!**\n\n5 dakika mola ver, sonra tekrar başla! ☕")
        except:
            pass
        
    Timer(1500, finish_pomodoro).start()

@bot.message_handler(commands=['dogruyanlis'])
def true_false_game(message):
    user_id = str(message.from_user.id)
    if not users.get(user_id, {}).get("is_approved", True):
        bot.reply_to(message, "⛔ Onay bekleniyor...")
        return
    wait_msg = bot.send_message(message.chat.id, "🤔 Bilgi hazırlanıyor...")
    
    try:
        prompt = """
        KPSS Tarih, Coğrafya veya Vatandaşlık konularından rastgele bir bilgi cümlesi yaz. 
        Bu cümle bazen doğru bilgi içersin, bazen yanlış bilgi içersin (şaşırtmalı olsun).
        Cevabı şu JSON formatında ver (başka bir şey yazma):
        {
            "soru": "Cümle buraya",
            "cevap": "D" veya "Y",
            "aciklama": "Neden doğru veya yanlış olduğu buraya"
        }
        """
        response = safe_generate_content(prompt)
        
        text_resp = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(text_resp)
        
        users[user_id]["dy_answer"] = data["cevap"]
        users[user_id]["dy_explanation"] = data["aciklama"]
        save_users()
        
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("✅ Doğru", callback_data="dy_D"),
            InlineKeyboardButton("❌ Yanlış", callback_data="dy_Y")
        )
        
        bot.delete_message(message.chat.id, wait_msg.message_id)
        bot.send_message(message.chat.id, f"❓ **Doğru mu Yanlış mı?**\n\n{data['soru']}", reply_markup=markup)
        
    except Exception as e:
        print(f"DogruYanlis Hatasi: {e}")
        bot.edit_message_text("Hata oluştu, tekrar dene.", message.chat.id, wait_msg.message_id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("dy_"))
def check_dy(call):
    user_id = str(call.from_user.id)
    if user_id not in users: return
    
    choice = call.data.split("_")[1] # D or Y
    
    if "dy_answer" not in users[user_id]:
        bot.answer_callback_query(call.id, "Bu soru zaman aşımına uğradı.")
        return
        
    correct = users[user_id]["dy_answer"]
    explanation = users[user_id]["dy_explanation"]
    
    if choice == correct:
        users[user_id]["exp"] += 15
        msg = f"🎉 **Tebrikler!** Doğru bildin.\n\n💡 {explanation}"
    else:
        msg = f"🥀 **Yanlış!**\n\n💡 {explanation}"
        
    users[user_id].pop("dy_answer", None)
    users[user_id].pop("dy_explanation", None)
    save_users()
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=msg
    )

@bot.message_handler(commands=['macera'])
def start_adventure(message):
    user_id = str(message.from_user.id)
    if not users.get(user_id, {}).get("is_approved", True):
        bot.reply_to(message, "⛔ Onay bekleniyor...")
        return
    
    # Maliyet kontrolü (Örn: 20 EXP)
    cost = 20
    if users[user_id].get("exp", 0) < cost:
        bot.reply_to(message, f"❌ Bu maceraya atılmak için {cost} EXP gerekli! (Mevcut: {users[user_id]['exp']})")
        return

    users[user_id]["exp"] -= cost
    save_users()

    wait_msg = bot.send_message(message.chat.id, "🕰️ Zaman makinesi çalıştırılıyor... Tarihin derinliklerine gidiyorsun... ⚡")

    try:
        prompt = """
        Sen bir tarihsel macera oyunu yöneticisisin.
        Kullanıcı için Türk Tarihi (Hunlar, Selçuklu, Osmanlı veya Cumhuriyet dönemi) ile ilgili kısa, sürükleyici, 2. tekil şahıs (sen) ile yazılmış bir kriz/karar anı senaryosu oluştur.
        Kullanıcıya 3 seçenek sun (A, B, C).
        Sadece BİR seçenek tarihsel gerçeklere veya mantığa göre başarıya ulaştırmalı. Diğerleri başarısızlığa yol açmalı.
        
        Yanıtı SADECE şu JSON formatında ver (başka hiçbir şey yazma):
        {
            "hikaye": "Senaryo metni buraya...",
            "secenekler": {"A": "...", "B": "...", "C": "..."},
            "dogru_cevap": "A",
            "kazanc_mesaji": "Başarı durumunda gösterilecek açıklama ve tarihsel bilgi.",
            "kayip_mesaji": "Başarısızlık durumunda gösterilecek açıklama."
        }
        """
        response = safe_generate_content(prompt)
        
        text_resp = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(text_resp)
        
        # Kullanıcının aktif macerasını kaydet
        users[user_id]["active_adventure"] = data
        save_users()
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(f"A) {data['secenekler']['A']}", callback_data="adv_A"))
        markup.add(InlineKeyboardButton(f"B) {data['secenekler']['B']}", callback_data="adv_B"))
        markup.add(InlineKeyboardButton(f"C) {data['secenekler']['C']}", callback_data="adv_C"))
        
        bot.delete_message(message.chat.id, wait_msg.message_id)
        bot.send_message(message.chat.id, f"📜 **TARİHSEL MACERA**\n\n{data['hikaye']}", reply_markup=markup)
        
    except Exception as e:
        print(f"Macera Hatasi: {e}")
        bot.edit_message_text("Zaman makinesinde bir arıza oluştu! Tekrar dene.", message.chat.id, wait_msg.message_id)
        # Hata durumunda parayı iade et
        users[user_id]["exp"] += cost
        save_users()

@bot.message_handler(commands=['ikna'])
def start_debate(message):
    user_id = str(message.from_user.id)
    if not users.get(user_id, {}).get("is_approved", True):
        return

    if not check_daily_limit(user_id):
        bot.reply_to(message, "⛔ Günlük Gemini mesaj hakkın (3/3) doldu! Yarın tekrar gel.")
        return

    if len(message.text.split()) < 2:
        bot.reply_to(message, "🗣️ **Münazara Modu**\n\nBir fikir ortaya at, botu ikna etmeye çalış veya tartış!\nBot sana 100 üzerinden puan verecek.\n\nÖrnek: `/ikna Çay kahveden daha sağlıklıdır çünkü doğaldır.`")
        return

    user_argument = message.text.split(maxsplit=1)[1]
    wait_msg = bot.reply_to(message, "🤔 Argümanın inceleniyor... Jüri toplanıyor...")

    try:
        prompt = f"""
        Sen zor beğenen, mantıklı ve biraz iğneleyici bir münazara jürisisin.
        Kullanıcının şu argümanını analiz et: "{user_argument}"
        
        1. Bu argümana kısa ve zekice bir karşı tez sun.
        2. Kullanıcının ikna kabiliyetine ve mantığına 1 ile 100 arasında bir puan ver.
        
        Yanıtı SADECE şu JSON formatında ver:
        {{
            "karsi_tez": "Senin cevabın...",
            "puan": 75
        }}
        """
        response = safe_generate_content(prompt)
        text_resp = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(text_resp)
        
        score = int(data.get("puan", 0))
        users[user_id]["exp"] += score
        save_users()

        bot.delete_message(message.chat.id, wait_msg.message_id)
        bot.reply_to(message, f"🗣️ **MÜNAZARA SONUCU**\n\n🤖 **Botun Cevabı:** {data['karsi_tez']}\n\n📊 **Puanın:** {score}/100\n💰 **Kazanç:** +{score} EXP")

    except Exception as e:
        print(f"Ikna Hatasi: {e}")
        bot.edit_message_text("Jüri şu an molada... Daha sonra tekrar dene.", message.chat.id, wait_msg.message_id)

@bot.message_handler(commands=['tarihtebugun'])
def history_today(message):
    user_id = str(message.from_user.id)
    if not users.get(user_id, {}).get("is_approved", True):
        return

    # Bu özellik basit olduğu için günlük limitten düşmeyebiliriz veya düşebiliriz.
    # Şimdilik düşmeyelim, hediye olsun.
    
    try:
        now = datetime.now()
        date_str = now.strftime("%d %B") # Örn: 02 January (Gemini bunu anlar)
        prompt = f"Bugün tarih {date_str}. Tarihte bugün yaşanmış, Türk veya Dünya tarihinden çok ilginç, şaşırtıcı tek bir olayı anlat. Kısa ve öz olsun."
        response = safe_generate_content(prompt)
        bot.reply_to(message, f"📅 **TARİHTE BUGÜN**\n\n{response.text}")
    except Exception as e:
        print(f"Tarih Hatasi: {e}")
        bot.reply_to(message, "Tarih kitapları şu an tozlu... Daha sonra bak.")

@bot.callback_query_handler(func=lambda c: c.data.startswith("adv_"))
def adventure_callback(call):
    user_id = str(call.from_user.id)
    if user_id not in users or "active_adventure" not in users[user_id]:
        save_users()

@bot.callback_query_handler(func=lambda c: c.data.startswith("adv_"))
def adventure_callback(call):
    user_id = str(call.from_user.id)
    if user_id not in users or "active_adventure" not in users[user_id]:
        bot.answer_callback_query(call.id, "Bu macera sona ermiş.")
        return

    choice = call.data.split("_")[1]
    data = users[user_id]["active_adventure"]
    
    if choice == data["dogru_cevap"]:
        reward = 50
        users[user_id]["exp"] += reward
        msg = f"🎉 **BAŞARDIN!**\n\n{data['kazanc_mesaji']}\n\n💰 Ödül: +{reward} EXP"
    else:
        users[user_id]["lives"] -= 1
        msg = f"💀 **BAŞARISIZ OLDUN...**\n\n{data['kayip_mesaji']}\n\n❤️ -1 Can Kaybettin."

    # Macerayı temizle
    users[user_id].pop("active_adventure", None)
    save_users()
    
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=msg)

@bot.message_handler(commands=['ruya'])
def dream_interpret(message):
    user_id = str(message.from_user.id)
    if not users.get(user_id, {}).get("is_approved", True):
        return
        
    if not check_daily_limit(user_id):
        bot.reply_to(message, "⛔ Günlük Gemini mesaj hakkın (3/3) doldu! Yarın tekrar gel.")
        return

    if len(message.text.split()) < 2:
        bot.reply_to(message, "😴 Rüyayı yazmadın knk!\nÖrnek: `/ruya uçurumdan düştüğümü gördüm`")
        return
        
    dream_text = message.text.split(maxsplit=1)[1]
    wait_msg = bot.reply_to(message, "🔮 Küreye bakıyorum... Rüyaların gizemini çözüyorum...")
    
    try:
        prompt = f"Sen mistik, bilge ve biraz gizemli konuşan bir rüya tabircisisin. Kullanıcının şu rüyasını yorumla: '{dream_text}'. Geleceğe dair (uydurma ama eğlenceli) kehanetlerde bulun. Kısa ve öz olsun."
        response = safe_generate_content(prompt)
        bot.delete_message(message.chat.id, wait_msg.message_id)
        bot.reply_to(message, f"🌙 **RÜYA TABİRİ** 🌙\n\n{response.text}")
    except Exception as e:
        print(f"Ruya Hatasi: {e}")
        bot.edit_message_text("Rüyalar alemi şu an kapalı... Daha sonra tekrar dene.", message.chat.id, wait_msg.message_id)

@bot.message_handler(commands=['hediye'])
def admin_gift(message):
    # Sadece geliştirici kullanabilir
    if message.from_user.username != DEVELOPER_USERNAME:
        return
    
    try:
        # Kullanım: /hediye <user_id> <miktar>
        args = message.text.split()
        target_input = args[1]
        amount = int(args[2])
        
        target_id = None
        
        # 1. Önce ID olarak kontrol et
        if target_input in users:
            target_id = target_input
        else:
            # 2. Bulunamazsa Kullanıcı Adı olarak ara (başındaki @ işaretini silerek)
            search_name = target_input.lstrip("@")
            for uid, u in users.items():
                if u.get("username") == search_name:
                    target_id = uid
                    break
        
        if target_id:
            users[target_id]["exp"] += amount
            save_users()
            bot.reply_to(message, f"✅ {users[target_id]['name']} kullanıcısına {amount} EXP gönderildi.")
            
            # Kullanıcıya da müjdeyi verelim
            try:
                bot.send_message(target_id, f"🎁 **YÖNETİCİ HEDİYESİ!**\n\nHesabına {amount} EXP yüklendi. İyi oyunlar! 🚀")
            except:
                pass
        else:
            bot.reply_to(message, "❌ Kullanıcı bulunamadı! (Doğru ID veya Kullanıcı Adı girdiğinden emin ol)")
    except:
        bot.reply_to(message, "⚠️ Kullanım: /hediye <KullanıcıAdı veya ID> <Miktar>\nÖrnek: /hediye @HuseyinAcar35 1000")

@bot.message_handler(commands=['help', 'hakkinda'])
def help_guide(message):
    text = (
        "📚 **BOT REHBERİ & OYUN KURALLARI** 📚\n\n"
        "🎮 **Nasıl Oynanır?**\n"
        "Amacın soruları bilerek EXP kazanmak, seviye atlamak ve en güçlü oyuncu olmak!\n\n"
        "🎓 **KPSS Çalışma Araçları:**\n"
        "🔹 `/ozet <konu>` - İstediğin konunun özetini çıkarır.\n"
        "🔹 `/dogruyanlis` - Doğru/Yanlış oyunu ile bilgilerini sına.\n"
        "🔹 `/yanlislarim` - Yanlış yaptığın soruları tekrar çöz.\n"
        "🔹 `/pomodoro` - 25 dakikalık ders çalışma sayacı başlat.\n\n"
        "⚔️ **Oyun Modları:**\n"
        "🔹 `/quiz` - Kategorili sorular çöz.\n"
        "🔹 `/macera` - Tarihsel bir olayın içinde rol yap ve karar ver! (Yeni! 🕰️)\n"
        "🔹 `/ikna <fikir>` - Botla tartış, argümanın kadar puan kazan! (Yeni! 🗣️)\n"
        "🔹 `/tarihtebugun` - Bugün tarihte ne olduğunu öğren. 📅\n"
        "🔹 `/clock` - Dünya genelinden zor sorular (Global).\n"
        "🔹 `/duello <miktar>` - Botla zar atışına gir. Kazanan hepsini alır!\n\n"
        "⛏️ **Madencilik & Ekonomi:**\n"
        "🔹 `/kaz` - Madene in (15 dk'da bir). Elmas, Altın veya Kömür bulabilirsin. Dikkat et göçük olabilir!\n"
        "🔹 `/market` - Kazandığın EXP ile Can, Şans Kutusu veya **Elmas Kazma** al.\n"
        "🔹 `/envanter` - Çantana, parana ve eşyalarına bak.\n\n"
        "🔮 **Eğlence & Mistik:**\n"
        "🔹 `/ruya <metin>` - Rüyalarını yapay zekaya yorumlat. 🌙\n"
        "🎲 **Risk & Ödül:**\n"
        "🔹 `/bahis <miktar>` - Kendine güveniyorsan sıradaki soruya bahis oyna. Doğru bilirsen 2 katı!\n"
        "🔹 **Happy Hour:** Her akşam 20:00-22:00 arası 2 kat EXP!\n\n"
        "🏆 **Rütbeler:**\n"
        "👶 Acemi -> 🛠️ Çırak -> ⚔️ Usta -> 🧙‍♂️ Bilge\n"
        "👑 **VIP:** Level 15 olursan isminin yanına taç gelir!\n\n"
        "💡 **Jokerler:**\n"
        "Sorularda %50, Pas Geç ve Seyirci jokerlerini kullanabilirsin."
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda message: not message.text.startswith("/"))
def handle_message(message):
    user_id = str(message.from_user.id)
    if not users.get(user_id, {}).get("is_approved", True):
        # Onaysız kullanıcıların mesajlarını yoksay
        return
    # Küfür/Hakaret Kontrolü
    text_lower = message.text.lower()
    if any(word in text_lower for word in BANNED_WORDS):
        try:
            bot.delete_message(message.chat.id, message.message_id)
            warning = bot.send_message(message.chat.id, f"⚠️ {message.from_user.first_name}, lütfen saygılı olalım! 🚫")
            Timer(5.0, lambda: bot.delete_message(message.chat.id, warning.message_id)).start()
        except:
            pass
        return

    if not check_daily_limit(user_id):
        bot.reply_to(message, "⛔ Günlük Gemini mesaj hakkın (3/3) doldu! Yarın tekrar gel.")
        return

    try:
        response = safe_generate_content(message.text)
        bot.reply_to(message, response.text)
    except Exception as e:
        print(f"Sohbet Hatasi: {e}")
        bot.reply_to(message, "Bir hata oluştu knk 😅")

def send_morning_broadcast():
    # Kullanıcı listesi üzerinde dön ve mesaj at
    for user_id, data in list(users.items()):
        try:
            name = data.get("name", "Dostum")
            bot.send_message(user_id, f"GOOD MORNİNG {name.upper()} ☀️")
        except:
            pass # Kullanıcı botu engellemiş olabilir, devam et

def scheduler_thread():
    while True:
        # Türkiye Saati (UTC+3) hesaplama
        now = datetime.utcnow() + timedelta(hours=3)
        if now.hour == 8 and now.minute == 0:
            send_morning_broadcast()
            time.sleep(65) # 1 dakika bekle ki tekrar tekrar atmasın
        time.sleep(20) # 20 saniyede bir saati kontrol et

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
    
    # Sabah 8 mesajı için zamanlayıcıyı başlat
    s = Thread(target=scheduler_thread)
    s.daemon = True
    s.start()
    
    # Botu çalıştır
    print("Bot aktif ve Render üzerinde çalışıyor...")
    # Botu başlatmadan hemen önce eski webhookları ve takılı kalan mesajları siler
    bot.delete_webhook(drop_pending_updates=True)
    bot.infinity_polling()