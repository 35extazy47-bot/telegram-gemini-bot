import random
import html
import os
import io
import textwrap
import time
import uuid
import json
from threading import Timer
from datetime import datetime, timedelta

import requests
from PIL import Image, ImageDraw, ImageFont
from deep_translator import GoogleTranslator
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

gTTS = None
try:
    from gtts import gTTS
except ImportError:
    pass

try:
    from fpdf import FPDF
except ImportError:
    FPDF = None

import database
from database import (
    users, save_users, QUIZ_QUESTIONS, DEVELOPER_USERNAME,
    user_timers, pending_duels, active_sessions
)

active_quiz_duels = {}

# --- Kronoloji Oyunu Verileri (Olay, Yıl) ---
CHRONOLOGY_DATA = [
    ("Malazgirt Savaşı", 1071), ("Miryokefalon Savaşı", 1176), ("Kösedağ Savaşı", 1243),
    ("Söğüt'ün Alınması", 1299), ("Bursa'nın Fethi", 1326), ("Ankara Savaşı", 1402),
    ("İstanbul'un Fethi", 1453), ("Ridaniye Seferi", 1517), ("Preveze Deniz Zaferi", 1538),
    ("İnebahtı Deniz Savaşı", 1571), ("Viyana Kuşatması (II)", 1683), ("Karlofça Antlaşması", 1699),
    ("Pasarofça Antlaşması", 1718), ("Küçük Kaynarca", 1774), ("Yaş Antlaşması", 1792),
    ("Sened-i İttifak", 1808), ("Tanzimat Fermanı", 1839), ("Islahat Fermanı", 1856),
    ("I. Meşrutiyet", 1876), ("93 Harbi", 1877), ("II. Meşrutiyet", 1908),
    ("31 Mart Vakası", 1909), ("Trablusgarp Savaşı", 1911), ("Balkan Savaşları", 1912),
    ("I. Dünya Savaşı", 1914), ("Çanakkale Zaferi", 1915), ("Mondros Ateşkesi", 1918),
    ("Samsun'a Çıkış", 1919), ("Sivas Kongresi", 1919), ("TBMM'nin Açılışı", 1920),
    ("Sakarya Savaşı", 1921), ("Büyük Taarruz", 1922), ("Cumhuriyetin İlanı", 1923),
    ("Halifeliğin Kaldırılması", 1924), ("Hatay'ın Katılması", 1939), ("Çok Partili Hayat", 1946),
    ("NATO Üyeliği", 1952), ("6-7 Eylül Olayları", 1955), ("1960 Darbesi", 1960),
    ("Kıbrıs Barış Harekatı", 1974), ("1980 Darbesi", 1980), ("Gümrük Birliği", 1996)
]

# --- Boşluk Doldurma Verileri (Soru, [Doğru Cevaplar Listesi]) ---
FILL_BLANK_DATA = [
    ("Mustafa Kemal Atatürk 19 Mayıs 1919'da _________ iline çıkarak Milli Mücadele'yi başlatmıştır.", ["samsun"]),
    ("Türkiye Cumhuriyeti'nin başkenti _________ ilidir.", ["ankara"]),
    ("Malazgirt Savaşı _________ yılında yapılmıştır.", ["1071"]),
    ("İstanbul'u fetheden Osmanlı padişahı _________ Sultan Mehmet'tir.", ["fatih", "2. mehmet", "ii. mehmet"]),
    ("Türkiye'nin en yüksek dağı _________ Dağı'dır.", ["ağrı"]),
    ("İstiklal Marşı'nın şairi _________ Ersoy'dur.", ["mehmet akif"]),
    ("Cumhuriyet _________ yılında ilan edilmiştir.", ["1923"]),
    ("Hatay _________ yılında anavatana katılmıştır.", ["1939"]),
    ("Osmanlı Devleti'nin kurucusu _________ Bey'dir.", ["osman"]),
    ("İlk Türk devletlerinde devleti yöneten hükümdara _________ unvanı verilir.", ["kağan", "han", "hakan"]),
    ("Asya Hun Devleti'nin en parlak dönemi _________ Han zamanıdır.", ["mete"]),
    ("Müslümanların ilk kıblesi _________ şehrindedir.", ["kudüs"]),
    ("Türkiye'nin en büyük gölü _________ Gölü'dür.", ["van"]),
    ("Lozan Antlaşması _________ yılında imzalanmıştır.", ["1923"]),
    ("UNESCO koruması altındaki Pamukkale _________ ilimizdedir.", ["denizli"])
]

# Bu fonksiyonlar tirtil.py'den register fonksiyonu aracılığıyla alınacak
get_rank = None
check_daily_limit = None
update_quest_progress = None
safe_generate_content = None

def create_quiz_image(question, options, category, level, lives, question_img_url=None):
    width = 800
    height = 600
    
    cat_lower = category.lower()
    if "tarih" in cat_lower:
        bg_color, header_text_color = (60, 40, 30), (255, 200, 150)
    elif "cografya" in cat_lower or "coğrafya" in cat_lower:
        bg_color, header_text_color = (30, 60, 40), (150, 255, 150)
    elif "vatandaslik" in cat_lower or "vatandaşlık" in cat_lower:
        bg_color, header_text_color = (50, 30, 70), (200, 180, 255)
    elif "guncel" in cat_lower or "güncel" in cat_lower:
        bg_color, header_text_color = (80, 50, 20), (255, 220, 100)
    else:
        bg_color, header_text_color = (15, 23, 42), (255, 215, 0)

    card_color = (30, 41, 59)
    img = Image.new('RGBA', (width, height), color=bg_color + (255,))
    draw = ImageDraw.Draw(img)
    
    try:
        font_path = "arial.ttf"
        if not os.path.exists(font_path):
            candidates = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/System/Library/Fonts/Helvetica.ttc"]
            font_path = next((f for f in candidates if os.path.exists(f)), font_path)
        header_font = ImageFont.truetype(font_path, 28)
        question_font = ImageFont.truetype(font_path, 34)
        option_font = ImageFont.truetype(font_path, 26)
        tag_font = ImageFont.truetype(font_path, 20)
    except:
        header_font, question_font, option_font = ImageFont.load_default(), ImageFont.load_default(), ImageFont.load_default()
        tag_font = ImageFont.load_default()

    # Üst bar ve Zorluk Yıldızları
    draw.rectangle([(0, 0), (width, 80)], fill=(15, 23, 42))
    stars = "⭐" * level
    draw.text((40, 25), f"🧠 {category.upper()}  |  {stars}  |  ❤️ {lives}", font=header_font, fill=header_text_color)
    
    # Soru Kartı
    draw.rounded_rectangle([(40, 100), (760, 320)], radius=20, fill=card_color, outline=(51, 65, 85), width=2)
    draw.rounded_rectangle([(60, 110), (160, 140)], radius=10, fill=(56, 189, 248))
    draw.text((75, 115), "SORU", font=tag_font, fill=(255, 255, 255))
    
    y_text = 160
    # --- Resim Ekleme Bölümü ---
    if question_img_url:
        try:
            # Resmi indir
            # Daha güncel ve tarayıcıya benzer User-Agent
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
                "Referer": "https://www.google.com/",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache"
            }
            
            response = None
            max_attempts = 3
            for attempt in range(max_attempts):
                response = requests.get(question_img_url, headers=headers, timeout=10)
                # Sadece başarılı ve içerik tipi resimse döngüden çık
                if response.status_code == 200 and response.headers.get("Content-Type", "").lower().startswith("image/"):
                    break
                elif response.status_code in [409, 429, 503]:
                    time.sleep(attempt * 5 + 5) # Hata durumunda daha uzun bekleme süresi (5, 10, 15 saniye)
                else:
                    # Diğer hatalar veya resim olmayan içerik için denemeyi durdur
                    raise requests.exceptions.RequestException(f"Beklenmedik durum: Status {response.status_code}, Content-Type: {response.headers.get('Content-Type')}")
            
            # Eğer tüm denemeler başarısız olursa veya son deneme resim değilse hata fırlat
            if not (response and response.status_code == 200 and response.headers.get("Content-Type", "").lower().startswith("image/")):
                raise requests.exceptions.RequestException(f"Resim yüklenemedi veya geçerli bir resim değil. Son durum: Status {response.status_code}, Content-Type: {response.headers.get('Content-Type')}")
            
            q_img = Image.open(io.BytesIO(response.content)).convert("RGBA")
            
            # Resmi "Soru Kartı" içine sığacak şekilde boyutlandır (Max Genişlik: 300, Max Yükseklik: 180)
            max_w, max_h = 300, 180
            q_img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
            
            # Resmi sağ tarafa yapıştır
            img.paste(q_img, (760 - q_img.size[0] - 20, 120), q_img if q_img.mode == 'RGBA' else None)
            
            # Metin alanını daralt (Resim olduğu için)
            text_width = 30
        except Exception as e:
            print(f"Soru resmi yüklenemedi: {e}")
            text_width = 40
    else:
        text_width = 40

    # Metni yazdır
    wrapper = textwrap.TextWrapper(width=text_width) 
    lines = wrapper.wrap(text=question)
    for line in lines:
        draw.text((60, y_text), line, font=question_font, fill=(255, 255, 255))
        y_text += 45

    y_opt = 345
    for opt in options:
        draw.rounded_rectangle([(40, y_opt), (760, y_opt + 55)], radius=15, fill=(51, 65, 85))
        draw.text((70, y_opt + 12), opt, font=option_font, fill=(241, 245, 249))
        y_opt += 70

    bio = io.BytesIO()
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio

def get_question(level, category):
    if category == "karisik":
        uygun = [q for q in QUIZ_QUESTIONS if q["level"] <= level]
    else:
        uygun = [q for q in QUIZ_QUESTIONS if q["level"] <= level and q["category"] == category]
    return random.choice(uygun) if uygun else None

def create_quiz_result_image(is_correct, correct_answer, earned_exp, streak, user_answer):
    width, height = 800, 400
    if is_correct:
        bg_color, title_text = (39, 174, 96), "TEBRİKLER! DOĞRU 🎉"
    else:
        bg_color = (192, 57, 43)
        title_text = "SÜRE DOLDU! ⏳" if user_answer == "TIMEOUT" else "YANLIŞ CEVAP... 🥀"
    
    img = Image.new('RGB', (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)
    
    try:
        font_path = "arial.ttf"
        if not os.path.exists(font_path):
            candidates = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 
                "/System/Library/Fonts/Helvetica.ttc"]
            font_path = next((f for f in candidates if os.path.exists(f)), font_path)
        title_font, info_font, big_font = ImageFont.truetype(font_path, 45), ImageFont.truetype(font_path, 30), ImageFont.truetype(font_path, 55)
    except:
        title_font, info_font, big_font = ImageFont.load_default(), ImageFont.load_default(), ImageFont.load_default()

    draw.text((50, 40), title_text, font=title_font, fill=(255, 255, 255))
    
    y = 130
    if not is_correct:
        if user_answer != "TIMEOUT":
            draw.text((50, y), f"Senin Cevabın: {user_answer}", font=info_font, fill=(255, 200, 200)); y += 45
        draw.text((50, y), f"Doğru Cevap: {correct_answer}", font=info_font, fill=(255, 255, 255))
    else:
        draw.text((50, y), f"Cevap: {correct_answer}", font=info_font, fill=(255, 255, 255))
        
    y += 80
    if earned_exp > 0:
        draw.text((50, y), f"💰 +{earned_exp} EXP", font=big_font, fill=(255, 215, 0))
    elif earned_exp < 0:
        draw.text((50, y), f"📉 {earned_exp} EXP", font=big_font, fill=(255, 200, 200))
    else:
        draw.text((50, y), f"😐 0 EXP", font=big_font, fill=(255, 255, 255))

    if streak > 1:
        draw.text((500, y+10), f"🔥 {streak}x Seri", font=info_font, fill=(255, 165, 0))

    bio = io.BytesIO()
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio

def register_quiz_handlers(bot, tirtil_utils):
    """Quiz ile ilgili tüm komutları ve callback'leri bota kaydeder."""
    global get_rank, check_daily_limit, update_quest_progress, safe_generate_content
    get_rank = tirtil_utils['get_rank']
    check_daily_limit = tirtil_utils['check_daily_limit']
    update_quest_progress = tirtil_utils['update_quest_progress']
    safe_generate_content = tirtil_utils['safe_generate_content']

    # --- Akıllı Tekrar Sistemi (Leitner Kutuları) ---
    SPACED_INTERVALS = {1: 1, 2: 3, 3: 7, 4: 14, 5: 30} # Kutu: Gün

    def schedule_review(user_id, q_id, success):
        user_id, q_id = str(user_id), str(q_id)
        if "spaced_repetition" not in users[user_id]: users[user_id]["spaced_repetition"] = {}
        sr_data = users[user_id]["spaced_repetition"]
        today = datetime.now()
        
        if not success:
            # Yanlışsa 1. kutuya (Yarın tekrar)
            next_date = today + timedelta(days=SPACED_INTERVALS[1])
            sr_data[q_id] = {"box": 1, "next_review": next_date.strftime("%Y-%m-%d")}
        else:
            # Doğruysa kutu yükselir
            if q_id in sr_data:
                current_box = sr_data[q_id].get("box", 1)
                if current_box >= 5:
                    if q_id in sr_data: del sr_data[q_id] # Mezun oldu
                else:
                    new_box = current_box + 1
                    next_date = today + timedelta(days=SPACED_INTERVALS.get(new_box, 30))
                    sr_data[q_id] = {"box": new_box, "next_review": next_date.strftime("%Y-%m-%d")}
        save_users()

    def send_spaced_question(chat_id, user_id):
        queue = users[user_id].get("sr_queue", [])
        if not queue:
            bot.send_message(chat_id, "🎉 **Harika!** Bugünkü akıllı tekrarlarını tamamladın. Bilgiler hafızana kazındı! 🧠✨")
            users[user_id]["mode"] = "local"; save_users(); return

        q_id = queue[0]
        q = next((item for item in QUIZ_QUESTIONS if item["id"] == q_id), None)
        
        # Soru silinmişse geç
        if not q:
            users[user_id]["sr_queue"].pop(0)
            if str(q_id) in users[user_id].get("spaced_repetition", {}): del users[user_id]["spaced_repetition"][str(q_id)]
            save_users(); send_spaced_question(chat_id, user_id); return

        users[user_id].update({"current_answer": q["answer"], "current_question_id": q["id"]})
        
        box_num = users[user_id].get("spaced_repetition", {}).get(str(q_id), {}).get("box", 1)
        photo = create_quiz_image(q['question'], q['options'], f"TEKRAR (Kutu {box_num})", users[user_id]["level"], users[user_id]['lives'], q.get('image_url'))
        
        markup = InlineKeyboardMarkup(row_width=4).add(*[InlineKeyboardButton(s, callback_data=f"ans_{s}") for s in ["A", "B", "C", "D"]])
        markup.add(InlineKeyboardButton("🏁 Bitir", callback_data="finish_quiz"))
        # Tekrar modunda kaydet butonu eklemiyoruz (zaten kayıtlı mantığı)

        if user_id in user_timers: user_timers[user_id].cancel()
        
        # Timer Kontrolü
        is_timer_on = database.quiz_timer_enabled and users[user_id].get("timer_enabled", True)
        time_text = "(⏳ 30 sn)" if is_timer_on else "(⏳ ∞)"
        
        msg = bot.send_photo(chat_id, photo, caption=f"🔄 **AKILLI TEKRAR**\nKalan: {len(queue)}\n👇 Doğru şıkkı seç! {time_text}", reply_markup=markup)
        users[user_id]["last_question_message_id"] = msg.message_id
        
        if is_timer_on:
            user_timers[user_id] = Timer(30.0, question_timeout, args=[chat_id, user_id]); user_timers[user_id].start()
        save_users()

    def finish_exam_simulation(chat_id, user_id):
        stats = users[user_id].get("exam_stats", {})
        start_str = users[user_id].get("exam_start")
        
        duration_str = "0 dk"
        if start_str:
            start = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
            diff = datetime.now() - start
            mins = int(diff.total_seconds() / 60)
            secs = int(diff.total_seconds() % 60)
            duration_str = f"{mins} dk {secs} sn"

        correct = stats.get("correct", 0)
        incorrect = stats.get("incorrect", 0)
        empty = stats.get("empty", 0)
        total = users[user_id].get("exam_total", 20)
        
        net = correct - (incorrect / 4)
        exp_gain = max(0, int(net * 10)) # Net başına 10 EXP
        
        users[user_id]["exp"] += exp_gain
        
        # İstatistiğe kaydet (study.py'deki denemelerim komutuyla uyumlu)
        if "exams" not in users[user_id]: users[user_id]["exams"] = []
        users[user_id]["exams"].append({
            "date": datetime.now().strftime("%Y-%m-%d"),
            "name": "Mini Deneme",
            "net": net
        })
        
        text = (
            f"🏁 **DENEME SINAVI SONUCU** 🏁\n\n"
            f"⏱️ Süre: {duration_str}\n"
            f"✅ Doğru: {correct}\n"
            f"❌ Yanlış: {incorrect}\n"
            f"⭕ Boş: {empty}\n\n"
            f"📊 **NET: {net:.2f}**\n"
            f"⭐️ Kazanılan EXP: +{exp_gain}"
        )
        
        users[user_id]["mode"] = "local"
        users[user_id].pop("exam_queue", None)
        users[user_id].pop("exam_stats", None)
        users[user_id].pop("exam_start", None)
        users[user_id].pop("exam_total", None)
        users[user_id].pop("current_answer", None)
        save_users()
        
        bot.send_message(chat_id, text)

    def send_exam_question(chat_id, user_id):
        queue = users[user_id].get("exam_queue", [])
        if not queue:
            finish_exam_simulation(chat_id, user_id)
            return

        q_id = queue[0]
        q = next((item for item in QUIZ_QUESTIONS if item["id"] == q_id), None)
        if not q:
            users[user_id]["exam_queue"].pop(0)
            send_exam_question(chat_id, user_id)
            return

        users[user_id].update({"current_answer": q["answer"], "current_question_id": q["id"]})
        
        # Kaçıncı soru olduğunu hesapla
        current_idx = users[user_id]["exam_total"] - len(queue) + 1
        total = users[user_id]["exam_total"]
        
        photo = create_quiz_image(q['question'], q['options'], f"DENEME ({current_idx}/{total})", users[user_id]["level"], users[user_id]['lives'], q.get('image_url'))
        
        markup = InlineKeyboardMarkup(row_width=4)
        markup.add(*[InlineKeyboardButton(s, callback_data=f"ans_{s}") for s in ["A", "B", "C", "D"]])
        markup.add(InlineKeyboardButton("⏭ Boş Bırak", callback_data="ans_EMPTY"))
        markup.add(InlineKeyboardButton("🏁 Sınavı Bitir", callback_data="finish_quiz"))

        if user_id in user_timers: user_timers[user_id].cancel()
        
        msg = bot.send_photo(chat_id, photo, caption=f"📝 **Soru {current_idx}/{total}**", reply_markup=markup)
        users[user_id]["last_question_message_id"] = msg.message_id
        save_users()

    def question_timeout(chat_id, user_id):
        evaluate_quiz_answer(chat_id, user_id, "TIMEOUT", bot)

    def send_question(chat_id, user_id):
        level, category = users[user_id]["level"], users[user_id]["category"]
        q = get_question(level, category)
        if not q:
            bot.send_message(chat_id, "❌ Bu kategoride soru kalmadı knk"); return

        users[user_id].update({"current_answer": q["answer"], "current_question_id": q["id"]})
        mode_prefix = f"🏃‍♂️ **MARATON: {users[user_id].get('marathon_score', 0) + 1}. SORU**\n" if users[user_id].get("mode") == "marathon" else ""
        photo = create_quiz_image(q['question'], q['options'], category, level, users[user_id]['lives'], q.get('image_url'))
        
        # Timer Kontrolü
        is_timer_on = database.quiz_timer_enabled and users[user_id].get("timer_enabled", True)
        time_text = "(⏳ 30 sn)" if is_timer_on else "(⏳ ∞)"
        caption = f"{mode_prefix}👇 Doğru şıkkı seç! {time_text}"

        markup = InlineKeyboardMarkup(row_width=4)
        markup.add(*[InlineKeyboardButton(s, callback_data=f"ans_{s}") for s in ["A", "B", "C", "D"]])
        
        joker_btns = []
        inv = users[user_id].get("inventory", {})
        if inv.get("joker_50", 0) > 0: joker_btns.append(InlineKeyboardButton(f"💡 %50 ({inv['joker_50']})", callback_data="joker_50"))
        if inv.get("joker_pass", 0) > 0: joker_btns.append(InlineKeyboardButton(f"⏭ Pas ({inv['joker_pass']})", callback_data="joker_pass"))
        if inv.get("joker_audience", 0) > 0: joker_btns.append(InlineKeyboardButton(f"👥 Seyirci ({inv['joker_audience']})", callback_data="joker_audience"))
        if inv.get("joker_ai", 0) > 0: joker_btns.append(InlineKeyboardButton(f"🤖 AI İpucu ({inv['joker_ai']})", callback_data="joker_ai"))
        if joker_btns: markup.add(*joker_btns)

        markup.add(InlineKeyboardButton("💾 Kaydet", callback_data="save_fav"), InlineKeyboardButton("🏁 Bitir", callback_data="finish_quiz"))

        if user_id in user_timers: user_timers[user_id].cancel()
        msg = bot.send_photo(chat_id, photo, caption=caption, reply_markup=markup)
        users[user_id]["last_question_message_id"] = msg.message_id
        
        if is_timer_on:
            user_timers[user_id] = Timer(30.0, question_timeout, args=[chat_id, user_id]); user_timers[user_id].start()
        save_users()

    def send_wrong_question(chat_id, user_id):
        wrong_ids = users[user_id].get("wrong_answers", [])
        if not wrong_ids:
            bot.send_message(chat_id, "🎉 **Tebrikler!** Yanlış yaptığın tüm soruları temizledin. Harikasın! 👏")
            users[user_id]["mode"] = "local"; return

        q_id = random.choice(wrong_ids)
        q = next((item for item in QUIZ_QUESTIONS if item["id"] == q_id), None)
        if not q:
            users[user_id]["wrong_answers"].remove(q_id); send_wrong_question(chat_id, user_id); return

        users[user_id].update({"current_answer": q["answer"], "current_question_id": q["id"]})
        photo = create_quiz_image(q['question'], q['options'], q['category'], users[user_id]["level"], users[user_id]['lives'], q.get('image_url'))
        markup = InlineKeyboardMarkup(row_width=4).add(*[InlineKeyboardButton(s, callback_data=f"ans_{s}") for s in ["A", "B", "C", "D"]])

        markup.add(InlineKeyboardButton("💾 Kaydet", callback_data="save_fav"), InlineKeyboardButton("🏁 Bitir", callback_data="finish_quiz"))

        if user_id in user_timers: user_timers[user_id].cancel()
        
        # Timer Kontrolü
        is_timer_on = database.quiz_timer_enabled and users[user_id].get("timer_enabled", True)
        time_text = "(⏳ 30 sn)" if is_timer_on else "(⏳ ∞)"
        msg = bot.send_photo(chat_id, photo, caption=f"🔄 **Tekrar Zamanı!** {time_text}", reply_markup=markup)
        users[user_id]["last_question_message_id"] = msg.message_id
        
        if is_timer_on:
            user_timers[user_id] = Timer(30.0, question_timeout, args=[chat_id, user_id]); user_timers[user_id].start()
        save_users()

    def send_weakness_question(chat_id, user_id):
        weak_topics = users[user_id].get("weak_topics", [])
        if not weak_topics:
            bot.send_message(chat_id, "🎉 **Tebrikler!** Zayıf olduğun konuları tamamladın veya listen boş. Normal moda dönülüyor. 👏")
            users[user_id]["mode"] = "local"
            save_users()
            return

        candidates = [q for q in QUIZ_QUESTIONS if q.get("category") in weak_topics]
        
        if not candidates:
            bot.send_message(chat_id, "📂 Bu konularda soru bulunamadı. Normal moda dönülüyor.")
            users[user_id]["mode"] = "local"
            save_users()
            return

        q = random.choice(candidates)
        users[user_id].update({"current_answer": q["answer"], "current_question_id": q["id"]})
        
        photo = create_quiz_image(q['question'], q['options'], q['category'], users[user_id]["level"], users[user_id]['lives'], q.get('image_url'))
        
        markup = InlineKeyboardMarkup(row_width=4)
        markup.add(*[InlineKeyboardButton(s, callback_data=f"ans_{s}") for s in ["A", "B", "C", "D"]])
        
        joker_btns = []
        inv = users[user_id].get("inventory", {})
        if inv.get("joker_50", 0) > 0: joker_btns.append(InlineKeyboardButton(f"💡 %50 ({inv['joker_50']})", callback_data="joker_50"))
        if inv.get("joker_pass", 0) > 0: joker_btns.append(InlineKeyboardButton(f"⏭ Pas ({inv['joker_pass']})", callback_data="joker_pass"))
        if inv.get("joker_audience", 0) > 0: joker_btns.append(InlineKeyboardButton(f"👥 Seyirci ({inv['joker_audience']})", callback_data="joker_audience"))
        if inv.get("joker_ai", 0) > 0: joker_btns.append(InlineKeyboardButton(f"🤖 AI İpucu ({inv['joker_ai']})", callback_data="joker_ai"))
        if joker_btns: markup.add(*joker_btns)

        markup.add(InlineKeyboardButton("💾 Kaydet", callback_data="save_fav"), InlineKeyboardButton("🏁 Bitir", callback_data="finish_quiz"))

        if user_id in user_timers: user_timers[user_id].cancel()
        cat_display = q['category'].replace("_", " ").title()
        
        # Timer Kontrolü
        is_timer_on = database.quiz_timer_enabled and users[user_id].get("timer_enabled", True)
        time_text = "(⏳ 30 sn)" if is_timer_on else "(⏳ ∞)"
        msg = bot.send_photo(chat_id, photo, caption=f"📉 **Zayıf Konu Çalışması**\n📂 Konu: {cat_display}\n👇 Doğru şıkkı seç! {time_text}", reply_markup=markup)
        users[user_id]["last_question_message_id"] = msg.message_id
        
        if is_timer_on:
            user_timers[user_id] = Timer(30.0, question_timeout, args=[chat_id, user_id]); user_timers[user_id].start()
        save_users()

    def send_ai_question(chat_id, user_id):
        queue = users[user_id].get("ai_quiz_queue", [])
        if not queue:
            bot.send_message(chat_id, "🏁 **AI Testi Tamamlandı!**\nUmarım faydalı olmuştur. 🤖")
            users[user_id]["mode"] = "local"
            save_users()
            return

        q = queue[0] # Sıradaki soru
        users[user_id]["current_ai_question"] = q 
        users[user_id]["current_answer"] = q["answer"]
        
        photo = create_quiz_image(q['question'], q['options'], "AI TEST", users[user_id]["level"], users[user_id]['lives'], q.get('image_url'))
        
        markup = InlineKeyboardMarkup(row_width=4)
        markup.add(*[InlineKeyboardButton(s, callback_data=f"ans_{s}") for s in ["A", "B", "C", "D"]])
        markup.add(InlineKeyboardButton("💾 Kaydet", callback_data="save_fav"), InlineKeyboardButton("🏁 Bitir", callback_data="finish_quiz"))

        if user_id in user_timers: user_timers[user_id].cancel()
        
        topic = users[user_id].get('ai_quiz_topic', 'Genel')
        
        # Timer Kontrolü
        is_timer_on = database.quiz_timer_enabled and users[user_id].get("timer_enabled", True)
        time_text = "(⏳ 45 sn)" if is_timer_on else "(⏳ ∞)"
        msg = bot.send_photo(chat_id, photo, caption=f"🤖 **AI Tarafından Oluşturuldu**\n📂 Konu: {topic}\n👇 Doğru şıkkı seç! {time_text}", reply_markup=markup)
        users[user_id]["last_question_message_id"] = msg.message_id
        
        if is_timer_on:
            user_timers[user_id] = Timer(45.0, question_timeout, args=[chat_id, user_id]); user_timers[user_id].start()
        save_users()

    def send_saved_question(chat_id, user_id):
        queue = users[user_id].get("saved_queue", [])
        if not queue:
            bot.send_message(chat_id, "🏁 **Favori soruların bitti!**")
            users[user_id]["mode"] = "local"
            save_users()
            return

        item = queue[0]
        q = None
        
        if item.get("source") == "db":
            q = next((x for x in QUIZ_QUESTIONS if x["id"] == item["id"]), None)
            if not q: # Soru silinmişse geç
                users[user_id]["saved_queue"].pop(0)
                send_saved_question(chat_id, user_id)
                return
        else:
            q = item.get("data")
            
        users[user_id]["current_saved_item"] = item # Silme işlemi için takip
        users[user_id]["current_answer"] = q["answer"]
        
        photo = create_quiz_image(q['question'], q['options'], "FAVORİ", users[user_id]["level"], users[user_id]['lives'], q.get('image_url'))
        
        markup = InlineKeyboardMarkup(row_width=4)
        markup.add(*[InlineKeyboardButton(s, callback_data=f"ans_{s}") for s in ["A", "B", "C", "D"]])
        markup.add(InlineKeyboardButton("🗑️ Favorilerden Sil", callback_data="del_fav"))
        markup.add(InlineKeyboardButton("🏁 Bitir", callback_data="finish_quiz"))

        if user_id in user_timers: user_timers[user_id].cancel()
        
        # Timer Kontrolü
        is_timer_on = database.quiz_timer_enabled and users[user_id].get("timer_enabled", True)
        time_text = "(⏳ 30 sn)" if is_timer_on else "(⏳ ∞)"
        
        msg = bot.send_photo(chat_id, photo, caption=f"📂 **FAVORİ SORU**\n👇 Doğru şıkkı seç! {time_text}", reply_markup=markup)
        users[user_id]["last_question_message_id"] = msg.message_id
        
        if is_timer_on:
            user_timers[user_id] = Timer(30.0, question_timeout, args=[chat_id, user_id])
            user_timers[user_id].start()
        save_users()

    def evaluate_quiz_answer(chat_id, user_id, answer, bot, message_id_to_delete=None):
        if user_id not in users or "current_answer" not in users[user_id]: return
        if user_id in user_timers: user_timers[user_id].cancel(); del user_timers[user_id]

        u = users[user_id]
        
        # Günlük sayaç
        today_str = datetime.now().strftime("%Y-%m-%d")
        if u.get("last_question_date") != today_str:
            u["last_question_date"] = today_str
            u["daily_questions_solved"] = 0
            u["daily_correct_solved"] = 0
            u["daily_incorrect_solved"] = 0
        u["daily_questions_solved"] = u.get("daily_questions_solved", 0) + 1

        # Haftalık sayaç
        current_week_str = datetime.now().strftime("%Y-%W")
        if u.get("last_weekly_question_week") != current_week_str:
            u["last_week_questions_solved"] = u.get("weekly_questions_solved", 0)
            u["weekly_questions_solved"] = 0
            u["last_weekly_question_week"] = current_week_str
        u["weekly_questions_solved"] = u.get("weekly_questions_solved", 0) + 1

        q_id = users[user_id].get("current_question_id")
        if u.get("mode") == "ai_quiz":
            question_data = u.get("current_ai_question")
        elif u.get("mode") == "saved":
            question_data = u.get("current_saved_item", {}).get("data") or next((x for x in QUIZ_QUESTIONS if x["id"] == u.get("current_saved_item", {}).get("id")), None)
        else:
            question_data = next((q for q in QUIZ_QUESTIONS if q["id"] == q_id), None)

        try:
            if message_id_to_delete: bot.delete_message(chat_id, message_id_to_delete)
            if "last_question_message_id" in users[user_id]: bot.delete_message(chat_id, users[user_id]["last_question_message_id"])
        except: pass

        correct = users[user_id]["current_answer"]
        u = users[user_id]
        
        # İstatistik Hazırlığı (Konu Bazlı)
        cat = question_data.get("category", "Genel")
        u.setdefault("topic_stats", {}).setdefault(cat, {"correct": 0, "incorrect": 0})

        level, exp, streak, bet_amount = u["level"], u["exp"], u.get("streak", 0), u.get("active_bet", 0)

        correct_msgs = ["✅ **Harikasın!**", "🔥 **Alev aldı buralar!**", "🧠 **Zeka küpü!**", "🎯 **Tam isabet!**"]
        wrong_msgs = ["❌ **Ah be! Yanlış oldu.**", "🐢 **Biraz daha dikkat!**", "🤔 **Mantıklıydı ama...**", "💥 **Patladık!**"]

        # --- EXAM (DENEME) MODU ---
        if u.get("mode") == "exam":
            if u.get("exam_queue"): u["exam_queue"].pop(0)
            
            if answer == "EMPTY" or answer == "TIMEOUT":
                u["exam_stats"]["empty"] += 1
            elif answer == correct:
                u["exam_stats"]["correct"] += 1
            else:
                u["exam_stats"]["incorrect"] += 1
            
            save_users()
            # Deneme modunda anlık bildirim yok, sonraki soruya geç
            send_exam_question(chat_id, user_id)
            return
        # --------------------------

        # --- AKILLI TEKRAR MODU ---
        if u.get("mode") == "spaced_repetition":
            if u.get("sr_queue"): u["sr_queue"].pop(0) # Kuyruktan düş
            if answer == correct:
                bot.send_dice(chat_id, emoji="🎯"); u["exp"] += 10
                schedule_review(user_id, q_id, True)
                photo = create_quiz_result_image(True, correct, 10, 0, answer)
                msg = bot.send_photo(chat_id, photo, caption="✅ **Doğru!** Bir sonraki kutuya terfi etti. 📦⬆️")
                Timer(1.5, lambda: bot.delete_message(chat_id, msg.message_id)).start()
            else:
                schedule_review(user_id, q_id, False)
                photo = create_quiz_result_image(False, correct, 0, 0, answer)
                bot.send_photo(chat_id, photo, caption=f"❌ **Yanlış!** Soru 1. Kutuya döndü. Yarın tekrar soracağım. 📦⬇️\nDoğru Cevap: {correct}")
            u.pop("current_answer", None); save_users(); send_spaced_question(chat_id, user_id); return
        # --------------------------

        # --- SAVED (FAVORİ) MODU ---
        if u.get("mode") == "saved":
            if u.get("saved_queue"): u["saved_queue"].pop(0)
            if answer == correct:
                bot.send_dice(chat_id, emoji="🎯")
                bot.send_message(chat_id, f"✅ **Doğru!** {random.choice(correct_msgs)}")
            else:
                bot.send_message(chat_id, f"❌ **Yanlış!**\nDoğru Cevap: {correct}")
            
            u.pop("current_answer", None); save_users(); send_saved_question(chat_id, user_id); return
        # ---------------------------

        if u.get("mode") == "marathon":
            if answer == correct:
                u["marathon_score"] = u.get("marathon_score", 0) + 1
                score, reward = u["marathon_score"], 10 * u["marathon_score"]
                u["exp"] += reward
                photo = create_quiz_result_image(True, correct, reward, score, answer)
                msg = bot.send_photo(chat_id, photo, caption=f"{random.choice(correct_msgs)} ({score}. Soru)\n💰 +{reward} EXP\nDevam... 🏃‍♂️💨")
                Timer(1.5, lambda: bot.delete_message(chat_id, msg.message_id)).start()
                u.pop("current_answer", None); save_users(); send_question(chat_id, user_id); return
            else:
                score, best = u.get("marathon_score", 0), u.get("best_marathon", 0)
                result_msg = f"❌ **YANLIŞ! MARATON BİTTİ!** 🛑\n\n🏃‍♂️ **Skorun:** {score} Soru\n"
                if score > best: u["best_marathon"] = score; result_msg += f"🏆 **YENİ REKOR!** (Eski: {best})\n"
                else: result_msg += f"🏅 **En İyi Skorun:** {best}\n"
                photo = create_quiz_result_image(False, correct, 0, score, answer)
                u.update({"mode": "local", "marathon_score": 0}); u.pop("current_answer", None); save_users()
                bot.send_photo(chat_id, photo, caption=f"{result_msg}\nDoğru Cevap: {correct}"); return

        earned_exp_display = 0
        if answer == correct:
            bot.send_dice(chat_id, emoji="🎯")
            if q_id in u.get("wrong_answers", []): u["wrong_answers"].remove(q_id)
            u["total_correct"] = u.get("total_correct", 0) + 1
            
            # İstatistik Güncelleme (Doğru)
            u.setdefault("cat_stats", {})[cat] = u.get("cat_stats", {}).get(cat, 0) + 1 # Eski sistem (Profil için)
            u["topic_stats"][cat]["correct"] += 1 # Yeni detaylı sistem
            
            # Zayıf Konu Kontrolü (İyileşme varsa listeden çıkar)
            if u.get("mode") == "weakness" and cat in u.get("weak_topics", []):
                stats = u["topic_stats"][cat]
                total = stats["correct"] + stats["incorrect"]
                if total > 0 and (stats["correct"] / total) >= 0.5:
                    u["weak_topics"].remove(cat)
                    bot.send_message(chat_id, f"📈 **Gelişme Var!**\n'{cat.replace('_', ' ').title()}' konusundaki başarı oranın %50'yi geçti ve listeden çıkarıldı. 💪")

            update_quest_progress(user_id, "quiz_correct"); streak += 1
            u["daily_correct_solved"] = u.get("daily_correct_solved", 0) + 1
            
            q_level = question_data.get("level", 1) if question_data else 1
            total_points = (15 * q_level + 5) + (streak * 2)
            
            now, is_happy_hour = datetime.utcnow() + timedelta(hours=3), 20 <= (datetime.utcnow() + timedelta(hours=3)).hour < 22
            result = f"{random.choice(correct_msgs)}\n"
            if is_happy_hour: total_points *= 2; result += f"🔥 **HAPPY HOUR (2x EXP)**\n"
            result += f"🔥 Combo: {streak}x"
            
            if bet_amount > 0: win_amount = bet_amount * 2; total_points += win_amount; result += f"\n🎲 **BAHİS KAZANDIN!** (+{win_amount} EXP)"; u["active_bet"] = 0
            exp += total_points; earned_exp_display = total_points

            # --- STUDY BUDDY SCORE UPDATE ---
            if user_id in active_sessions:
                active_sessions[user_id]["score"] += 1
                partner_id = active_sessions[user_id]["partner"]
                partner_score = active_sessions.get(partner_id, {}).get("score", 0)
                result += f"\n\n🤝 **Çalışma Arkadaşı:**\nSen: {active_sessions[user_id]['score']} ✅ | O: {partner_score} ✅"
            # -------------------------------
        else:
            if u.get("inventory", {}).get("streak_saver", 0) > 0:
                u["inventory"]["streak_saver"] -= 1; streak_saved = True
            else:
                streak = 0; streak_saved = False
            
            if u.get("mode") == "local": u.setdefault("wrong_answers", []).append(q_id)
            
            # İstatistik ve Akıllı Tekrar Ekleme
            if u.get("mode") == "local": schedule_review(user_id, q_id, False) # Yanlışsa sisteme ekle
            u["topic_stats"][cat]["incorrect"] += 1
            
            u["lives"] -= 1; exp = max(0, exp - 10); earned_exp_display = -10
            u["daily_incorrect_solved"] = u.get("daily_incorrect_solved", 0) + 1
            result = f"{'⏳ **Süre Doldu!**' if answer == 'TIMEOUT' else random.choice(wrong_msgs)}\nDoğru Cevap: {correct}\n❤️ Kalan Can: {u['lives']}"
            if streak_saved: result += "\n🛡️ **Seri Koruyucu Devrede!**"
            if bet_amount > 0: result += f"\n💸 **BAHİS KAYBETTİN!**"; u["active_bet"] = 0

        if question_data and question_data.get("explanation"): result += f"\n\n💡 **Bilgi:** {question_data['explanation']}"

        old_rank = get_rank(level, u.get("username")); leveled_up = False
        while exp >= level * 100: exp -= level * 100; level += 1; leveled_up = True
        if leveled_up:
            result += f"\n\n🚀 **LEVEL ATLADIN!** 🚀\n🏆 Yeni Seviye: {level}"
            if get_rank(level, u.get("username")) != old_rank: result += f"\n🎖 **YENİ RÜTBE:** {get_rank(level, u.get('username'))}"
            if level == 15: result += "\n🌟 **TEBRİKLER! ARTIK VIP ÜYESİN!** 👑"

        u.update({"level": level, "exp": exp, "streak": streak, "total_questions": u.get("total_questions", 0) + 1})

        if u["lives"] <= 0:
            full_text = f"{result}\n\n💀 **OYUN BİTTİ!** 💀\nCanların tükendi.\n\n🔄 /quiz ile tekrar başla!"
            if len(full_text) > 4096:
                # Mesaj çok uzunsa parçalara ayırarak gönder
                for i in range(0, len(full_text), 4096):
                    try:
                        bot.send_message(chat_id, full_text[i:i+4096])
                    except Exception as e:
                        print(f"Mesaj gönderim hatası (parçalı): {e}")
            else:
                bot.send_message(chat_id, full_text)
            u["lives"] = 3; u.pop("current_answer", None); save_users(); return

        full_caption = f"{result}\n\n📊 Level: {level} | ⭐️ EXP: {exp}/{level*100}"
        result_photo = create_quiz_result_image(answer == correct, correct, earned_exp_display, streak, answer)
        if len(full_caption) > 1024:
            bot.send_photo(chat_id, result_photo)
            if len(full_caption) > 4096:
                for i in range(0, len(full_caption), 4096):
                    bot.send_message(chat_id, full_caption[i:i+4096])
            else:
                bot.send_message(chat_id, full_caption)
        else:
            msg = bot.send_photo(chat_id, result_photo, caption=full_caption)
            Timer(5.0, lambda: bot.delete_message(chat_id, msg.message_id) if msg else None).start()

        u.pop("current_answer", None); save_users()
        
        if u.get("mode") == "global": send_global_question(chat_id, user_id)
        elif u.get("mode") == "retry": send_wrong_question(chat_id, user_id)
        elif u.get("mode") == "weakness": send_weakness_question(chat_id, user_id)
        elif u.get("mode") == "ai_quiz":
            if u.get("ai_quiz_queue"):
                u["ai_quiz_queue"].pop(0)
            send_ai_question(chat_id, user_id)
        else: send_question(chat_id, user_id)

    def send_global_question(chat_id, user_id):
        target_lang = users[user_id].get("lang", "tr")
        wait_msg = bot.send_message(chat_id, "⏳ 🌍 ...")
        try:
            data = requests.get("https://opentdb.com/api.php?amount=1&type=multiple", timeout=10).json()
            if data["response_code"] != 0: bot.edit_message_text("API Hatası", chat_id, wait_msg.message_id); return
            item = data["results"][0]
            
            texts = [html.unescape(t) for t in [item["question"], item["correct_answer"]] + item["incorrect_answers"]]
            if target_lang != "en": texts = GoogleTranslator(source='auto', target=target_lang).translate_batch(texts)
            
            question_text, correct_text, incorrect_texts = texts[0], texts[1], texts[2:]
            all_options = incorrect_texts + [correct_text]; random.shuffle(all_options)
            
            letters = ["A", "B", "C", "D"]
            correct_letter = letters[all_options.index(correct_text)]
            users[user_id]["current_answer"] = correct_letter; save_users()
            
            formatted_options = [f"{letters[i]}) {opt}" for i, opt in enumerate(all_options)]
            photo = create_quiz_image(question_text, formatted_options, "GLOBAL", users[user_id]["level"], users[user_id]['lives'])
            
            markup = InlineKeyboardMarkup(row_width=4).add(*[InlineKeyboardButton(s, callback_data=f"ans_{s}") for s in letters])
            # Jokerler eklenebilir
            markup.add(InlineKeyboardButton("🏁 Bitir", callback_data="finish_quiz"))
            
            if user_id in user_timers: user_timers[user_id].cancel()
            bot.delete_message(chat_id, wait_msg.message_id)
            
            # Timer Kontrolü (Global Modda da geçerli olsun)
            is_timer_on = database.quiz_timer_enabled and users[user_id].get("timer_enabled", True)
            time_text = "(⏳ 30 sn)" if is_timer_on else "(⏳ ∞)"
            
            msg = bot.send_photo(chat_id, photo, caption=f"🌍 **Global Quiz** | {item['category']} {time_text}", reply_markup=markup)
            users[user_id]["last_question_message_id"] = msg.message_id
            
            if is_timer_on:
                user_timers[user_id] = Timer(30.0, question_timeout, args=[chat_id, user_id]); user_timers[user_id].start()
            save_users()
        except Exception as e:
            bot.edit_message_text(f"Hata: {str(e)}", chat_id, wait_msg.message_id)

    @bot.callback_query_handler(func=lambda c: c.data == 'finish_quiz')
    def finish_quiz_handler(call):
        user_id = str(call.from_user.id)
        if user_id not in users:
            return
            
        # Eğer deneme sınavındaysa, sınavı puanlayarak bitir
        if users[user_id].get("mode") == "exam":
            finish_exam_simulation(call.message.chat.id, user_id)
            try: bot.delete_message(call.message.chat.id, call.message.message_id)
            except: pass
            return

        # Zamanlayıcıyı durdur
        if user_id in user_timers:
            try:
                user_timers[user_id].cancel()
                del user_timers[user_id]
            except: pass

        # Kullanıcı durumunu temizle
        u = users[user_id]
        u.pop("current_answer", None)
        u.pop("current_question_id", None)
        u["mode"] = "local"  # Varsayılan moda dön
        u["lives"] = 3  # Canları sıfırla
        u.pop("active_bet", None) # Bahsi temizle
        u.pop("marathon_score", None) # Maratonu sıfırla
        save_users()

        # Kullanıcıyı bilgilendir
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except: pass
        bot.answer_callback_query(call.id, "Test bitirildi.")
        bot.send_message(call.message.chat.id, "🏁 Test bitirildi. Ana menüye dönmek için /start veya yeni bir teste başlamak için /quiz yazabilirsin.")

    @bot.message_handler(commands=['quiz'])
    def quiz(message):
        if not users.get(str(message.from_user.id), {}).get("is_approved", True):
            bot.reply_to(message, "⛔ Onay bekleniyor."); return
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("📜 Tarih", callback_data="submenu_tarih"), InlineKeyboardButton("🌍 Coğrafya", callback_data="submenu_cografya"))
        kb.add(InlineKeyboardButton("⚖️ Vatandaşlık", callback_data="submenu_vatandaslik"), InlineKeyboardButton("📰 Güncel", callback_data="submenu_guncel"))
        kb.add(InlineKeyboardButton("🖼️ Görselli Sorular", callback_data="cat_gorselli"))
        kb.add(InlineKeyboardButton("🔀 Karışık", callback_data="cat_karisik"))

        bot.send_message(message.chat.id, "📚 Kategori seç knk 👇", reply_markup=kb)

    @bot.callback_query_handler(func=lambda c: c.data == "submenu_tarih")
    def history_submenu(call):
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("🏹 İslamiyet Öncesi", callback_data="cat_tarih_islamiyet_oncesi"))
        kb.add(InlineKeyboardButton("🕌 Türk-İslam", callback_data="cat_tarih_ilk_turk_islam"))
        kb.add(InlineKeyboardButton("🏰 Osmanlı", callback_data="cat_tarih_osmanli"))
        kb.add(InlineKeyboardButton("🇹🇷 İnkılap", callback_data="cat_tarih_inkilap"))
        kb.add(InlineKeyboardButton("🌍 Çağdaş", callback_data="cat_tarih_cagdas"))
        kb.add(InlineKeyboardButton("🔙 Geri", callback_data="main_quiz_menu"))
        
        bot.edit_message_text("📜 **Tarih Alt Başlıkları**\nLütfen bir dönem seç:", call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda c: c.data == "main_quiz_menu")
    def main_quiz_menu(call):
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("📜 Tarih", callback_data="submenu_tarih"), InlineKeyboardButton("🌍 Coğrafya", callback_data="submenu_cografya"))
        kb.add(InlineKeyboardButton("⚖️ Vatandaşlık", callback_data="submenu_vatandaslik"), InlineKeyboardButton("📰 Güncel", callback_data="submenu_guncel"))
        kb.add(InlineKeyboardButton("🖼️ Görselli Sorular", callback_data="cat_gorselli"))
        kb.add(InlineKeyboardButton("🔀 Karışık", callback_data="cat_karisik"))
        
        bot.edit_message_text("📚 Kategori seç knk 👇", call.message.chat.id, call.message.message_id, reply_markup=kb)

    @bot.callback_query_handler(func=lambda c: c.data == "submenu_cografya")
    def geography_submenu(call):
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("🌍 Fiziki Coğrafya", callback_data="cat_cografya_fiziki"))
        kb.add(InlineKeyboardButton("🚜 Beşeri ve Tarım", callback_data="cat_cografya_beseri_tarim"))
        kb.add(InlineKeyboardButton("🏭 Maden & Sanayi", callback_data="cat_cografya_maden_sanayi"))
        kb.add(InlineKeyboardButton("✈️ Hizmet & Ulaşım", callback_data="cat_cografya_hizmet"))
        kb.add(InlineKeyboardButton("🔙 Geri", callback_data="main_quiz_menu"))
        
        bot.edit_message_text("🌍 **Coğrafya Alt Başlıkları**\nLütfen bir konu seç:", call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda c: c.data == "submenu_vatandaslik")
    def citizenship_submenu(call):
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("🏛️ Yasama", callback_data="cat_vatandaslik_yasama"))
        kb.add(InlineKeyboardButton("👔 Yürütme & İdare", callback_data="cat_vatandaslik_yurutme"))
        kb.add(InlineKeyboardButton("⚖️ Yargı", callback_data="cat_vatandaslik_yargi"))
        kb.add(InlineKeyboardButton("📘 Temel Hukuk", callback_data="cat_vatandaslik_temel"))
        kb.add(InlineKeyboardButton("🔙 Geri", callback_data="main_quiz_menu"))
        
        bot.edit_message_text("⚖️ **Vatandaşlık Alt Başlıkları**\nLütfen bir konu seç:", call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda c: c.data == "submenu_guncel")
    def current_submenu(call):
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("⚽ Spor", callback_data="cat_guncel_spor"))
        kb.add(InlineKeyboardButton("🎨 Sanat & Kültür", callback_data="cat_guncel_sanat"))
        kb.add(InlineKeyboardButton("🧬 Bilim & Teknoloji", callback_data="cat_guncel_bilim"))
        kb.add(InlineKeyboardButton("🌍 Genel & Siyaset", callback_data="cat_guncel_genel"))
        kb.add(InlineKeyboardButton("🔙 Geri", callback_data="main_quiz_menu"))
        
        bot.edit_message_text("📰 **Güncel Bilgiler Alt Başlıkları**\nLütfen bir konu seç:", call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="Markdown")

    @bot.message_handler(commands=['deneme'])
    def start_exam(message):
        user_id = str(message.from_user.id)
        if not users.get(user_id, {}).get("is_approved", True): return
        
        # Soru seçimi: Dengeli dağılım (8 Tarih, 6 Coğrafya, 3 Vatandaşlık, 3 Güncel)
        cats = {"tarih": 8, "cografya": 6, "vatandaslik": 3, "guncel": 3}
        exam_q_ids = []
        
        for cat_key, count in cats.items():
            pool = [q["id"] for q in QUIZ_QUESTIONS if cat_key in q["category"].lower()]
            if len(pool) >= count:
                exam_q_ids.extend(random.sample(pool, count))
            else:
                exam_q_ids.extend(pool)
                
        random.shuffle(exam_q_ids)
        
        users[user_id].update({
            "mode": "exam",
            "exam_queue": exam_q_ids,
            "exam_total": len(exam_q_ids),
            "exam_stats": {"correct": 0, "incorrect": 0, "empty": 0},
            "exam_start": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        save_users()
        
        bot.send_message(message.chat.id, f"⏳ **MİNİ DENEME SINAVI BAŞLIYOR!**\n\n📝 Toplam Soru: {len(exam_q_ids)}\n⏱️ Süre tutuluyor.\n\nBaşarılar! 🚀")
        send_exam_question(message.chat.id, user_id)

    @bot.message_handler(commands=['kronoloji'])
    def start_chronology(message):
        user_id = str(message.from_user.id)
        if not users.get(user_id, {}).get("is_approved", True): return
        
        # Rastgele 4 olay seç
        selection = random.sample(CHRONOLOGY_DATA, 4)
        
        # Doğru sıralamayı (yıla göre) bul ve indeksleri (1,2,3,4) belirle
        correct_order = sorted(selection, key=lambda x: x[1])
        # Seçilen listedeki olayların doğru sıralamadaki yerini bul (Örn: Seçilen listenin 3.sü aslında 1. sırada olmalı)
        # Basitçe: Kullanıcıdan seçilen listedeki numaraları doğru sırayla yazmasını isteyeceğiz.
        correct_indices = [selection.index(event) + 1 for event in correct_order]
        
        users[user_id]["chrono_answer"] = correct_indices
        users[user_id]["chrono_data"] = selection
        
        text = "📅 **KRONOLOJİ OYUNU**\n\nAşağıdaki olayları **ESKİDEN YENİYE (Tarih Sırasına Göre)** sırala.\nCevabını rakamlar arasında boşluk bırakarak yaz.\n__Örnek: 3 1 4 2__\n\n"
        
        for i, (event, year) in enumerate(selection, 1):
            text += f"**{i}.** {event}\n"
            
        msg = bot.send_message(message.chat.id, text, parse_mode="Markdown")
        bot.register_next_step_handler(msg, check_chronology_answer)

    def check_chronology_answer(message):
        user_id = str(message.from_user.id)
        if "chrono_answer" not in users.get(user_id, {}): return
        
        try:
            user_input = message.text.strip().replace(",", " ").replace("-", " ").split()
            user_order = [int(x) for x in user_input]
            
            if len(user_order) != 4:
                bot.reply_to(message, "⚠️ Lütfen 4 rakam girin (Örn: 3 1 4 2). Tekrar dene: /kronoloji")
                return
                
            correct_indices = users[user_id]["chrono_answer"]
            selection = users[user_id]["chrono_data"]
            sorted_events = sorted(selection, key=lambda x: x[1])

            if user_order == correct_indices:
                users[user_id]["exp"] += 50
                res_text = "🎉 **TEBRİKLER!** Doğru sıraladın.\n💰 Kazanç: +50 EXP\n\n✅ **Doğru Sıralama:**\n"
            else:
                res_text = "❌ **YANLIŞ OLDU...**\n\n✅ **Doğru Sıralama:**\n"
            
            for event, year in sorted_events:
                res_text += f"🔹 {year}: {event}\n"
            
            save_users()
            bot.send_message(message.chat.id, res_text, parse_mode="Markdown")
            
        except ValueError:
            bot.reply_to(message, "⚠️ Sadece rakam girmelisin. Tekrar dene: /kronoloji")
        
        # Temizlik
        users[user_id].pop("chrono_answer", None)
        users[user_id].pop("chrono_data", None)
        save_users()

    @bot.message_handler(commands=['bosluk'])
    def start_fill_in_the_blank(message):
        user_id = str(message.from_user.id)
        if not users.get(user_id, {}).get("is_approved", True): return
        
        question_data = random.choice(FILL_BLANK_DATA)
        question, answers = question_data
        
        users[user_id]["fill_blank_answers"] = answers
        users[user_id]["fill_blank_question"] = question
        save_users()
        
        msg = bot.send_message(message.chat.id, f"✍️ **BOŞLUK DOLDURMA**\n\n{question}\n\n_Cevabını yazıp gönder... (Sadece boşluğa gelecek kelimeyi yaz)_", parse_mode="Markdown")
        bot.register_next_step_handler(msg, check_fill_in_the_blank_answer)

    def check_fill_in_the_blank_answer(message):
        user_id = str(message.from_user.id)
        if "fill_blank_answers" not in users.get(user_id, {}): return
        
        # Komut girildiyse iptal et
        if message.text.startswith("/"):
            bot.reply_to(message, "⚠️ Oyun iptal edildi.")
            users[user_id].pop("fill_blank_answers", None); users[user_id].pop("fill_blank_question", None); save_users(); return

        user_input = message.text.strip().lower()
        correct_answers = users[user_id]["fill_blank_answers"]
        
        if user_input in correct_answers:
            users[user_id]["exp"] += 30; bot.reply_to(message, f"✅ **TEBRİKLER!** Doğru bildin.\n💰 Kazanç: +30 EXP")
        else:
            correct_display = correct_answers[0].title(); q = users[user_id].get("fill_blank_question", "").replace("_________", f"**{correct_display}**")
            bot.reply_to(message, f"❌ **YANLIŞ...**\n\nDoğrusu: {correct_display}\n\n_{q}_", parse_mode="Markdown")
        
        users[user_id].pop("fill_blank_answers", None); users[user_id].pop("fill_blank_question", None); save_users()

    @bot.message_handler(commands=['sesli'])
    def start_voice_quiz(message):
        user_id = str(message.from_user.id)
        if not users.get(user_id, {}).get("is_approved", True): return
        
        if not gTTS:
            bot.reply_to(message, "⚠️ Bu özellik için sunucuda 'gTTS' kütüphanesi eksik.\n`pip install gTTS` komutu ile yüklenmelidir.", parse_mode="Markdown")
            return

        wait_msg = bot.send_message(message.chat.id, "🎤 **Sesli Soru Hazırlanıyor...**\nLütfen bekleyin, hoparlörünüzü açın! 🔊")
        
        try:
            # Rastgele bir soru seç
            q = random.choice(QUIZ_QUESTIONS)
            
            users[user_id].update({"current_answer": q["answer"], "current_question_id": q["id"]})
            
            # Metni seslendirme için hazırla (Daha doğal okunması için düzenleme)
            text = f"Soru: {q['question']}\n\n"
            text += f"A şıkkı: {q['options'][0]}\n"
            text += f"B şıkkı: {q['options'][1]}\n"
            text += f"C şıkkı: {q['options'][2]}\n"
            text += f"D şıkkı: {q['options'][3]}\n"
            
            # Ses dosyasını bellekte oluştur
            tts = gTTS(text=text, lang='tr')
            voice_data = io.BytesIO()
            tts.write_to_fp(voice_data)
            voice_data.seek(0)
            
            # Klavye
            markup = InlineKeyboardMarkup(row_width=4)
            markup.add(*[InlineKeyboardButton(s, callback_data=f"ans_{s}") for s in ["A", "B", "C", "D"]])
            markup.add(InlineKeyboardButton("🏁 Bitir", callback_data="finish_quiz"))
            
            bot.delete_message(message.chat.id, wait_msg.message_id)
            
            caption = f"🔊 **SESLİ SORU**\n\n_{q['question']}_\n\n👇 Cevabını seç! (⏳ 45 sn)"
            msg = bot.send_voice(message.chat.id, voice_data, caption=caption, reply_markup=markup, parse_mode="Markdown")
            
            users[user_id]["last_question_message_id"] = msg.message_id
            
            # Ses dinleme süresi için zamanlayıcıyı biraz daha uzun tutuyoruz (45 sn)
            if user_id in user_timers: user_timers[user_id].cancel()
            user_timers[user_id] = Timer(45.0, question_timeout, args=[message.chat.id, user_id]); user_timers[user_id].start()
            save_users()
            
        except Exception as e:
            bot.edit_message_text(f"Ses oluşturulurken hata: {e}", message.chat.id, wait_msg.message_id)

    @bot.message_handler(commands=['koc'])
    def get_coach_analysis(message):
        user_id = str(message.from_user.id)
        if not check_daily_limit(user_id):
            bot.reply_to(message, "⛔ Günlük AI limitin doldu! Yarın tekrar dene.")
            return

        stats = users[user_id].get("topic_stats", {})
        if not stats:
            bot.reply_to(message, "📊 Analiz için henüz yeterli soru çözmedin. Biraz daha pratik yap!")
            return

        wait_msg = bot.reply_to(message, "🤖 Akıllı Koç, başarı karneni inceliyor ve sana özel tavsiyeler hazırlıyor... 🧠")

        # İstatistikleri AI için daha anlaşılır hale getir
        analysis_data = {}
        for cat, data in stats.items():
            total = data.get("correct", 0) + data.get("incorrect", 0)
            if total > 5: # Analiz için en az 5 soru çözülmüş olsun
                success_rate = (data.get("correct", 0) / total) * 100
                analysis_data[cat.replace("_", " ").title()] = {
                    "dogru": data.get("correct", 0),
                    "yanlis": data.get("incorrect", 0),
                    "basari_yuzdesi": f"%{int(success_rate)}"
                }
        
        if not analysis_data:
            bot.edit_message_text("📊 Analiz için henüz yeterli soru çözmedin. Biraz daha pratik yap!", message.chat.id, wait_msg.message_id)
            return

        try:
            prompt = (
                "Sen bir KPSS ders koçusun. Öğrencinin derslerdeki başarı istatistikleri aşağıda JSON formatında verilmiştir. "
                "Bu istatistikleri analiz et. Öğrencinin güçlü ve zayıf yönlerini belirle. Özellikle en zayıf olduğu 2-3 konuya odaklanmasını söyle. "
                "Bu zayıf konular için somut çalışma önerileri (örneğin 'bu konuyu tekrar et', 'bu konudan bol soru çöz' gibi) sun. "
                "Motive edici bir kapanış cümlesi yaz. Samimi ve destekleyici bir dil kullan. Emoji kullanmayı unutma. "
                f"İstatistikler:\n{json.dumps(analysis_data, ensure_ascii=False, indent=2)}"
            )
            response = safe_generate_content(prompt)
            bot.delete_message(message.chat.id, wait_msg.message_id)
            full_text = f"🧑‍🏫 **AKILLI KOÇ ANALİZİ**\n\n{response.text}"
            if len(full_text) > 4096:
                bot.reply_to(message, full_text[:4096], parse_mode="Markdown")
                for i in range(4096, len(full_text), 4096):
                    bot.send_message(message.chat.id, full_text[i:i+4096], parse_mode="Markdown")
            else:
                bot.reply_to(message, full_text, parse_mode="Markdown")
        except Exception as e:
            bot.edit_message_text(f"Analiz yapılırken bir hata oluştu: {e}", message.chat.id, wait_msg.message_id)

    @bot.message_handler(commands=['tekrar'])
    def start_smart_review(message):
        user_id = str(message.from_user.id)
        if not users.get(user_id, {}).get("is_approved", True): return
        
        sr_data = users[user_id].get("spaced_repetition", {})
        today_str = datetime.now().strftime("%Y-%m-%d")
        due = [int(qid) for qid, data in sr_data.items() if data["next_review"] <= today_str]
        
        if not due:
            bot.reply_to(message, "✅ **Bugünlük tekrarın yok!**\nYanlış yaptığın sorular buraya otomatik eklenir ve zamanı gelince sorulur.")
            return
            
        users[user_id].update({"mode": "spaced_repetition", "sr_queue": due}); save_users()
        bot.reply_to(message, f"🧠 **AKILLI TEKRAR SİSTEMİ**\n\nBugün tekrar etmen gereken **{len(due)}** soru var.\nLeitner sistemi ile hafızanı güçlendirelim! 🚀")
        send_spaced_question(message.chat.id, user_id)

    @bot.message_handler(commands=['karnem'])
    def show_report_card(message):
        user_id = str(message.from_user.id)
        if not users.get(user_id, {}).get("is_approved", True): return
        
        stats = users[user_id].get("topic_stats", {})
        if not stats:
            bot.reply_to(message, "📊 Henüz karne oluşturacak kadar soru çözmedin. Biraz pratik yap! ✍️")
            return
            
        report = {}
        weak_topics = []
        for cat, data in stats.items():
            parts = cat.split("_")
            main = parts[0].upper()
            sub = " ".join(parts[1:]).title() if len(parts) > 1 else "Genel"
            
            if main not in report: report[main] = []
            report[main].append((sub, data["correct"], data["incorrect"]))
            
            total = data["correct"] + data["incorrect"]
            if total > 0 and (data["correct"] / total) < 0.5:
                weak_topics.append(cat)
            
        text = "📊 **KİŞİSEL BAŞARI KARNESİ**\n\n"
        for main, items in sorted(report.items()):
            text += f"📂 **{main}**\n"
            for sub, c, i in sorted(items, key=lambda x: x[0]):
                total = c + i
                rate = (c / total * 100) if total > 0 else 0
                icon = "🟩" if rate >= 80 else ("🟨" if rate >= 50 else "🟥")
                text += f"   └ {sub}: {c}✅ {i}❌ ({icon} %{int(rate)})\n"
            text += "\n"
        
        markup = None
        if weak_topics:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("📉 Zayıf Konulara Çalış (%50 Altı)", callback_data="start_weakness_quiz"))
            text += "💡 **İpucu:** Başarısız olduğun konular tespit edildi. Aşağıdaki butona basarak sadece bu konulardan soru çözebilirsin."
            
        if len(text) > 4096:
            # Mesaj çok uzunsa parçalara ayırarak gönder
            for i in range(0, len(text), 4096):
                # Sadece son parçaya buton ekle
                current_markup = markup if i + 4096 >= len(text) else None
                bot.send_message(message.chat.id, text[i:i+4096], parse_mode="Markdown", reply_markup=current_markup)
        else:
            bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)


    @bot.callback_query_handler(func=lambda c: c.data == "start_weakness_quiz")
    def start_weakness_quiz_callback(call):
        user_id = str(call.from_user.id)
        stats = users[user_id].get("topic_stats", {})
        weak_topics = []
        for cat, data in stats.items():
            total = data["correct"] + data["incorrect"]
            if total > 0 and (data["correct"] / total) < 0.5:
                weak_topics.append(cat)
        
        if not weak_topics:
            bot.answer_callback_query(call.id, "🎉 Zayıf konun kalmadı!", show_alert=True); return
            
        users[user_id].update({"mode": "weakness", "weak_topics": weak_topics}); save_users()
        bot.answer_callback_query(call.id, "📉 Antrenman başlıyor...")
        bot.send_message(call.message.chat.id, "📉 **ZAYIF KONU ANTRENMANI**\n\nBaşarı oranın %50'nin altında olduğu konulardan sorular geliyor.\nBaşarana kadar devam! 🚀")
        send_weakness_question(call.message.chat.id, user_id)

    @bot.message_handler(commands=['test_olustur'])
    def create_ai_quiz(message):
        user_id = str(message.from_user.id)
        if not check_daily_limit(user_id): bot.reply_to(message, "⛔ Günlük AI limitin doldu!"); return
        
        try:
            topic = message.text.replace("/test_olustur", "").strip()
            if len(topic) < 3:
                bot.reply_to(message, "⚠️ Hangi konuda test istiyorsun?\nÖrnek: `/test_olustur Osmanlı Duraklama Dönemi`", parse_mode="Markdown")
                return
                
            wait_msg = bot.reply_to(message, f"🤖 **'{topic}'** hakkında 5 soruluk test hazırlanıyor... Lütfen bekle.")
            
            prompt = f"""
            KPSS formatında '{topic}' konusuyla ilgili 5 adet çoktan seçmeli soru hazırla.
            Zorluk seviyesi orta-zor olsun.
            Çıktıyı SADECE şu JSON formatında ver, başka hiçbir metin yazma:
            [
                {{ "question": "Soru metni", "options": ["A) Şık1", "B) Şık2", "C) Şık3", "D) Şık4"], "answer": "A", "explanation": "Kısa açıklama" }}, ...
            ]
            """
            response = safe_generate_content(prompt)
            text_resp = response.text.replace("```json", "").replace("```", "").strip()
            questions = json.loads(text_resp)
            
            users[user_id]["ai_quiz_queue"] = questions
            users[user_id]["ai_quiz_topic"] = topic
            users[user_id]["mode"] = "ai_quiz"
            save_users()
            
            bot.delete_message(message.chat.id, wait_msg.message_id)
            send_ai_question(message.chat.id, user_id)
        except Exception as e:
            bot.reply_to(message, f"Test oluşturulurken hata oluştu: {e}")

    @bot.message_handler(commands=['metin_test'])
    def quiz_from_text_request(message):
        user_id = str(message.from_user.id)
        if not check_daily_limit(user_id):
            bot.reply_to(message, "⛔ Günlük AI limitin doldu!"); return
        
        msg = bot.reply_to(message, "📄 **METİNDEN TEST OLUŞTURUCU**\n\nLütfen test oluşturmak istediğin ders notunu, paragrafı veya metni buraya yapıştır (veya ilet).")
        bot.register_next_step_handler(msg, process_text_for_quiz)

    def process_text_for_quiz(message):
        user_id = str(message.from_user.id)
        text_content = message.text
        
        if not text_content or text_content.startswith("/"):
            bot.reply_to(message, "⚠️ İşlem iptal edildi.")
            return

        if len(text_content) < 50:
             bot.reply_to(message, "⚠️ Metin çok kısa. Lütfen daha uzun bir metin gönder (En az 50 karakter).")
             return

        wait_msg = bot.reply_to(message, "🤖 Metin analiz ediliyor ve sorular çıkarılıyor... Lütfen bekle.")

        try:
            prompt = f"""
            Aşağıdaki metni analiz et ve bu metne dayalı 5 adet çoktan seçmeli soru (KPSS formatında) hazırla.
            Sorular SADECE verilen metindeki bilgilerle çözülebilir olsun.
            Zorluk seviyesi orta olsun.
            
            Metin:
            "{text_content}"

            Çıktıyı SADECE şu JSON formatında ver, başka hiçbir metin yazma:
            [
                {{ "question": "Soru metni", "options": ["A) Şık1", "B) Şık2", "C) Şık3", "D) Şık4"], "answer": "A", "explanation": "Kısa açıklama" }}, ...
            ]
            """
            response = safe_generate_content(prompt)
            text_resp = response.text.replace("```json", "").replace("```", "").strip()
            if text_resp.startswith("json"): text_resp = text_resp[4:].strip()
            
            questions = json.loads(text_resp)
            
            users[user_id]["ai_quiz_queue"] = questions
            users[user_id]["ai_quiz_topic"] = "Kendi Notun"
            users[user_id]["mode"] = "ai_quiz"
            save_users()
            
            bot.delete_message(message.chat.id, wait_msg.message_id)
            send_ai_question(message.chat.id, user_id)
        except Exception as e:
            bot.reply_to(message, f"Test oluşturulurken hata oluştu: {e}")

    @bot.callback_query_handler(func=lambda c: c.data == 'save_fav')
    def save_favorite_question(call):
        user_id = str(call.from_user.id)
        u = users.get(user_id)
        if not u: return
        
        if u.get("mode") == "ai_quiz":
            q_data = u.get("current_ai_question")
            if not q_data: bot.answer_callback_query(call.id, "⚠️ Hata: Soru verisi yok."); return
            
            if "saved_custom" not in u: u["saved_custom"] = []
            if q_data not in u["saved_custom"]:
                u["saved_custom"].append(q_data)
                save_users()
                bot.answer_callback_query(call.id, "✅ Soru favorilere eklendi!")
            else:
                bot.answer_callback_query(call.id, "⚠️ Bu soru zaten kayıtlı.")
        else:
            q_id = u.get("current_question_id")
            if not q_id: bot.answer_callback_query(call.id, "⚠️ Hata: Soru ID yok."); return
            
            if "saved_ids" not in u: u["saved_ids"] = []
            if q_id not in u["saved_ids"]:
                u["saved_ids"].append(q_id)
                save_users()
                bot.answer_callback_query(call.id, "✅ Soru favorilere eklendi!")
            else:
                bot.answer_callback_query(call.id, "⚠️ Bu soru zaten kayıtlı.")

    @bot.message_handler(commands=['kayitli_sorular'])
    def start_saved_quiz(message):
        user_id = str(message.from_user.id)
        if not users.get(user_id, {}).get("is_approved", True): return
        
        saved_ids = users[user_id].get("saved_ids", [])
        saved_custom = users[user_id].get("saved_custom", [])
        
        if not saved_ids and not saved_custom:
            bot.reply_to(message, "📂 **Favori listen boş!**\n\nSoru çözerken '💾 Kaydet' butonuna basarak buraya ekleyebilirsin.", parse_mode="Markdown")
            return
            
        queue = []
        for qid in saved_ids: queue.append({"source": "db", "id": qid})
        for qdata in saved_custom: queue.append({"source": "custom", "data": qdata})
        
        random.shuffle(queue)
        users[user_id]["mode"] = "saved"
        users[user_id]["saved_queue"] = queue
        save_users()
        
        bot.reply_to(message, f"📂 **FAVORİ SORULARIN**\n\nToplam: {len(queue)} soru\nBaşlıyoruz... 🚀", parse_mode="Markdown")
        send_saved_question(message.chat.id, user_id)

    @bot.callback_query_handler(func=lambda c: c.data == 'del_fav')
    def delete_favorite_question(call):
        user_id = str(call.from_user.id)
        u = users.get(user_id)
        item = u.get("current_saved_item")
        
        if not item: return
        
        if item["source"] == "db":
            if item["id"] in u.get("saved_ids", []):
                u["saved_ids"].remove(item["id"])
        else:
            if item["data"] in u.get("saved_custom", []):
                u["saved_custom"].remove(item["data"])
        
        save_users()
        bot.answer_callback_query(call.id, "🗑️ Soru favorilerden silindi.")

    @bot.callback_query_handler(func=lambda c: c.data == 'start_vocab_quiz')
    def start_vocab_quiz_callback(call):
        user_id = str(call.from_user.id)
        if not users.get(user_id, {}).get("ai_quiz_queue"):
            bot.answer_callback_query(call.id, "⚠️ Test verisi bulunamadı.", show_alert=True); return
        users[user_id]["mode"] = "ai_quiz"; save_users()
        bot.answer_callback_query(call.id, "Test başlıyor...")
        send_ai_question(call.message.chat.id, user_id)

    @bot.message_handler(commands=['pdf_olustur'])
    def pdf_creator_menu(message):
        user_id = str(message.from_user.id)
        if not users.get(user_id, {}).get("is_approved", True): return
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📂 Favori Sorularım", callback_data="make_pdf_fav"))
        markup.add(InlineKeyboardButton("❌ Yanlış Yaptıklarım", callback_data="make_pdf_wrong"))
        
        bot.send_message(message.chat.id, "📄 **PDF SORU BANKASI**\n\nHangi listenden PDF test oluşturmak istersin?", reply_markup=markup, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("make_pdf_"))
    def generate_pdf_action(call):
        user_id = str(call.from_user.id)
        action = call.data.replace("make_pdf_", "")
        
        if not FPDF:
            bot.answer_callback_query(call.id, "⚠️ Sunucuda 'fpdf2' kütüphanesi eksik!", show_alert=True)
            return

        question_list = []
        title = ""
        
        if action == "fav":
            saved_ids = users[user_id].get("saved_ids", [])
            question_list = [q for q in QUIZ_QUESTIONS if q["id"] in saved_ids]
            title = "FAVORİ SORULARIM"
        else:
            wrong_ids = users[user_id].get("wrong_answers", [])
            question_list = [q for q in QUIZ_QUESTIONS if q["id"] in wrong_ids]
            title = "YANLIŞ YAPTIKLARIM"
            
        if not question_list:
            bot.answer_callback_query(call.id, "⚠️ Bu listen boş!", show_alert=True)
            return
            
        bot.answer_callback_query(call.id, "PDF hazırlanıyor...")
        wait_msg = bot.send_message(call.message.chat.id, "📄 PDF oluşturuluyor, lütfen bekle...")
        
        try:
            pdf = FPDF()
            pdf.add_page()
            
            # Font Ayarı (Türkçe karakterler için)
            font_path = "arial.ttf"
            if not os.path.exists(font_path):
                # Linux sunucular için yedek font yolları
                candidates = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"]
                font_path = next((f for f in candidates if os.path.exists(f)), font_path)

            try:
                pdf.add_font("TrArial", "", font_path, uni=True)
                pdf.set_font("TrArial", size=12)
            except:
                pdf.set_font("Arial", size=12) # Fallback

            pdf.set_font_size(16)
            pdf.cell(0, 10, txt=f"KPSS CALISMA BOTU - {title}", ln=1, align='C')
            pdf.ln(10)
            pdf.set_font_size(12)
            
            answers = []
            for i, q in enumerate(question_list, 1):
                pdf.multi_cell(0, 10, txt=f"{i}) {q['question']}")
                for opt in q['options']:
                    pdf.cell(0, 8, txt=f"   {opt}", ln=1)
                pdf.ln(5)
                answers.append(f"{i}-{q['answer']}")

            # Cevap Anahtarı Sayfası
            pdf.add_page()
            pdf.cell(0, 10, txt="CEVAP ANAHTARI", ln=1, align='C')
            pdf.ln(10)
            pdf.multi_cell(0, 10, txt="  ".join(answers))

            file_name = f"Test_{action}_{user_id}.pdf"
            pdf.output(file_name)
            
            with open(file_name, "rb") as f:
                bot.send_document(call.message.chat.id, f, caption=f"📄 **{title}**\n📝 Toplam Soru: {len(question_list)}")
            
            os.remove(file_name)
            bot.delete_message(call.message.chat.id, wait_msg.message_id)
        except Exception as e:
            bot.edit_message_text(f"PDF hatası: {e}", call.message.chat.id, wait_msg.message_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("cat_"))
    def category_selected(call):
        user_id = str(call.from_user.id)
        users.setdefault(user_id, {"level": 1, "exp": 0, "lives": 3})
        users[user_id].update({"category": call.data.replace("cat_", ""), "mode": "local", "name": call.from_user.first_name, "username": call.from_user.username})
        save_users()
        send_question(call.message.chat.id, user_id)

    @bot.message_handler(commands=['maraton'])
    def start_marathon(message):
        user_id = str(message.from_user.id)
        if not users.get(user_id, {}).get("is_approved", True): bot.reply_to(message, "⛔ Onay bekleniyor."); return
        users[user_id].update({"mode": "marathon", "marathon_score": 0}); save_users()
        bot.send_message(message.chat.id, "🏃‍♂️ **MARATON BAŞLIYOR!**\nTek yanlış hakkın var. Hazırsan ilk soru geliyor... 🚀")
        send_question(message.chat.id, user_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("joker_"))
    def handle_jokers(call):
        user_id = str(call.from_user.id)
        action, inv, correct_answer = call.data, users[user_id].get("inventory", {}), users[user_id].get("current_answer")
        if not correct_answer: bot.answer_callback_query(call.id, "⚠️ Aktif bir soru yok!"); return
        
        joker_type = action.replace("joker_", "")
        if inv.get(action, 0) <= 0: bot.answer_callback_query(call.id, "❌ Bu jokerden kalmadı!", show_alert=True); return

        users[user_id]["inventory"][action] -= 1; save_users()

        if action == "joker_50":
            options = ["A", "B", "C", "D"]; options.remove(correct_answer)
            eliminated = random.sample(options, 2)
            bot.answer_callback_query(call.id, f"💡 İpucu: {eliminated[0]} ve {eliminated[1]} şıkları YANLIŞ! ❌", show_alert=True)
        elif action == "joker_pass":
            bot.answer_callback_query(call.id, "⏭ Soru geçiliyor...")
            try: bot.delete_message(call.message.chat.id, call.message.message_id)
            except: pass
            if users[user_id].get("mode") == "global": send_global_question(call.message.chat.id, user_id)
            else: send_question(call.message.chat.id, user_id)
        elif action == "joker_audience":
            percentages = {opt: 0 for opt in ["A", "B", "C", "D"]}
            correct_percent = random.randint(50, 85); percentages[correct_answer] = correct_percent
            remaining = 100 - correct_percent
            wrong_options = [o for o in ["A", "B", "C", "D"] if o != correct_answer]
            for i, opt in enumerate(wrong_options):
                val = random.randint(0, remaining) if i < 2 else remaining
                percentages[opt] = val; remaining -= val
            msg_text = "👥 **Seyirci Oylaması:**\n" + "\n".join([f"{k}: %{v} {'█' * (v // 10)}" for k, v in sorted(percentages.items())])
            bot.answer_callback_query(call.id, "Seyirciler oyladı!"); bot.send_message(call.message.chat.id, msg_text)
        elif action == "joker_ai":
            if not check_daily_limit(user_id): bot.answer_callback_query(call.id, "⛔ Günlük AI limitin doldu!", show_alert=True); return
            q_id = users[user_id].get("current_question_id")
            q = next((item for item in QUIZ_QUESTIONS if item["id"] == q_id), None)
            if q:
                prompt = f"Soru: {q['question']}. Seçenekler: {q['options']}. Doğru Cevap: {q['answer']}. Cevabı söylemeden kısa bir ipucu ver."
                try:
                    response = safe_generate_content(prompt)
                    bot.answer_callback_query(call.id, f"🤖 AI İpucu:\n{response.text}", show_alert=True)
                except:
                    bot.answer_callback_query(call.id, "🤖 Bağlantı hatası!", show_alert=True); users[user_id]["inventory"][action] += 1; save_users()

    @bot.message_handler(commands=['clock'])
    def open_trivia_question(message):
        user_id = str(message.from_user.id)
        if not users.get(user_id, {}).get("is_approved", True): bot.reply_to(message, "⛔ Onay bekleniyor."); return
        users.setdefault(user_id, {"level": 1, "exp": 0, "lives": 3, "lang": "tr"})
        users[user_id].update({"mode": "global", "name": message.from_user.first_name, "username": message.from_user.username})
        users[user_id].pop("current_question_id", None); save_users()
        send_global_question(message.chat.id, user_id)

    @bot.message_handler(commands=['yanlislarim'])
    def retry_wrongs(message):
        user_id = str(message.from_user.id)
        if not users.get(user_id, {}).get("is_approved", True): bot.reply_to(message, "⛔ Onay bekleniyor."); return
        users[user_id].update({"mode": "retry", "name": message.from_user.first_name}); save_users()
        send_wrong_question(message.chat.id, user_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("ans_"))
    def handle_quiz_answer_callback(call):
        user_id, answer = str(call.from_user.id), call.data.split("_")[1]
        evaluate_quiz_answer(call.message.chat.id, user_id, answer, bot, message_id_to_delete=call.message.message_id)
        try: bot.answer_callback_query(call.id)
        except: pass

    @bot.message_handler(func=lambda m: m.text and m.text.upper() in ["A", "B", "C", "D"])
    def check_answer(message):
        user_id, answer = str(message.from_user.id), message.text.upper()
        try: bot.delete_message(message.chat.id, message.message_id)
        except: pass
        evaluate_quiz_answer(message.chat.id, user_id, answer, bot)

    @bot.message_handler(commands=['dogruyanlis'])
    def true_false_game(message):
        user_id = str(message.from_user.id)
        if not users.get(user_id, {}).get("is_approved", True): bot.reply_to(message, "⛔ Onay bekleniyor."); return
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
            data = json.loads(response.text.replace("```json", "").replace("```", "").strip())
            users[user_id].update({"dy_answer": data["cevap"], "dy_explanation": data["aciklama"]}); save_users()
            markup = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Doğru", callback_data="dy_D"), InlineKeyboardButton("❌ Yanlış", callback_data="dy_Y"))
            bot.edit_message_text(f"❓ **Doğru mu Yanlış mı?**\n\n{data['soru']}", message.chat.id, wait_msg.message_id, reply_markup=markup)
        except Exception as e:
            bot.edit_message_text("Hata oluştu, tekrar dene.", message.chat.id, wait_msg.message_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("dy_"))
    def check_dy(call):
        user_id = str(call.from_user.id)
        if "dy_answer" not in users.get(user_id, {}): bot.answer_callback_query(call.id, "Soru zaman aşımına uğradı."); return
        choice, correct, explanation = call.data.split("_")[1], users[user_id]["dy_answer"], users[user_id]["dy_explanation"]
        if choice == correct: users[user_id]["exp"] += 15; msg = f"🎉 **Tebrikler!** Doğru bildin.\n\n💡 {explanation}"
        else: msg = f"🥀 **Yanlış!**\n\n💡 {explanation}"
        users[user_id].pop("dy_answer", None); users[user_id].pop("dy_explanation", None); save_users()
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id)
        
    @bot.message_handler(commands=['quiz_duello'])
    def quiz_duel_request(message):
        user_id = str(message.from_user.id)
        if not users.get(user_id, {}).get("is_approved", True): return
        
        args = message.text.split()
        if len(args) < 2 or not args[1].startswith("@"):
            bot.reply_to(message, "⚠️ Kullanım: `/quiz_duello <@kullanici>`\nÖrnek: `/quiz_duello @Ali`", parse_mode="Markdown")
            return
            
        target_username = args[1][1:]
        target_id = next((uid for uid, u in users.items() if u.get("username") == target_username), None)
        
        if not target_id:
            bot.reply_to(message, "❌ Kullanıcı bulunamadı.")
            return
        if target_id == user_id:
            bot.reply_to(message, "❌ Kendinle yarışamazsın.")
            return

        duel_id = str(uuid.uuid4())[:8]
        pending_duels[duel_id] = {
            "type": "quiz",
            "challenger": user_id,
            "target": target_id
        }
        
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("✅ Kabul Et", callback_data=f"qduel_accept_{duel_id}"),
            InlineKeyboardButton("❌ Reddet", callback_data=f"qduel_reject_{duel_id}")
        )
        
        bot.send_message(target_id, f"🧠 **BİLGİ YARIŞMASI DÜELLOSU!**\n\n@{users[user_id]['username']} sana meydan okuyor!\n3 Soru, En çok bilen kazanır.\n\nKabul ediyor musun?", reply_markup=markup)
        bot.reply_to(message, f"✅ Meydan okuma gönderildi: @{target_username}")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("qduel_"))
    def quiz_duel_response(call):
        action, duel_id = call.data.split("_")[1], call.data.split("_")[2]
        if duel_id not in pending_duels:
            bot.answer_callback_query(call.id, "⚠️ Teklif geçersiz.")
            return
            
        duel_data = pending_duels[duel_id]
        if str(call.from_user.id) != duel_data["target"]:
            bot.answer_callback_query(call.id, "⛔ Bu teklif sana değil.")
            return
            
        if action == "reject":
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.send_message(duel_data["challenger"], f"❌ @{users[duel_data['target']]['username']} düelloyu reddetti.")
            del pending_duels[duel_id]
            return
            
        # Kabul edildi
        bot.delete_message(call.message.chat.id, call.message.message_id)
        start_quiz_duel(duel_id)

    def start_quiz_duel(duel_id):
        data = pending_duels.pop(duel_id)
        p1, p2 = data["challenger"], data["target"]
        
        questions = random.sample(QUIZ_QUESTIONS, 3)
        active_quiz_duels[duel_id] = {
            "p1": p1, "p2": p2,
            "scores": {p1: 0, p2: 0},
            "questions": questions,
            "current_index": 0,
            "answers": {},
            "timers": []
        }
        
        bot.send_message(p1, "⚔️ **DÜELLO BAŞLIYOR!**\nİlk soru geliyor...")
        bot.send_message(p2, "⚔️ **DÜELLO BAŞLIYOR!**\nİlk soru geliyor...")
        time.sleep(2)
        send_duel_question(duel_id)

    def send_duel_question(duel_id):
        duel = active_quiz_duels.get(duel_id)
        if not duel: return
        
        idx = duel["current_index"]
        if idx >= len(duel["questions"]):
            finish_quiz_duel(duel_id)
            return
            
        q = duel["questions"][idx]
        duel["answers"] = {} 
        
        photo = create_quiz_image(q['question'], q['options'], "DÜELLO", idx+1, 0)
        markup = InlineKeyboardMarkup(row_width=2).add(*[InlineKeyboardButton(s, callback_data=f"dans_{s}_{duel_id}") for s in ["A", "B", "C", "D"]])
        
        try: bot.send_photo(duel["p1"], photo, caption=f"❓ **SORU {idx+1}/{len(duel['questions'])}**\n(⏳ 20 sn)", reply_markup=markup)
        except: pass
        
        photo.seek(0)
        try: bot.send_photo(duel["p2"], photo, caption=f"❓ **SORU {idx+1}/{len(duel['questions'])}**\n(⏳ 20 sn)", reply_markup=markup)
        except: pass

        t = Timer(20.0, duel_timeout, args=[duel_id, idx]); t.start()
        duel["timers"] = [t]

    def duel_timeout(duel_id, q_index):
        duel = active_quiz_duels.get(duel_id)
        if not duel or duel["current_index"] != q_index: return
        evaluate_duel_round(duel_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("dans_"))
    def handle_duel_answer_callback(call):
        _, ans, duel_id = call.data.split("_")
        user_id = str(call.from_user.id)
        duel = active_quiz_duels.get(duel_id)
        
        if not duel or user_id not in [duel["p1"], duel["p2"]]: return
        if user_id in duel["answers"]: bot.answer_callback_query(call.id, "Zaten cevap verdin."); return
            
        duel["answers"][user_id] = ans
        bot.answer_callback_query(call.id, f"Cevabın alındı: {ans}")
        bot.edit_message_caption("✅ Cevabın alındı, rakip bekleniyor...", call.message.chat.id, call.message.message_id)
        
        if len(duel["answers"]) == 2:
            for t in duel["timers"]: t.cancel()
            evaluate_duel_round(duel_id)

    def evaluate_duel_round(duel_id):
        duel = active_quiz_duels.get(duel_id)
        if not duel: return
        q, p1, p2 = duel["questions"][duel["current_index"]], duel["p1"], duel["p2"]
        correct, a1, a2 = q["answer"], duel["answers"].get(p1), duel["answers"].get(p2)
        
        if a1 == correct: duel["scores"][p1] += 1
        if a2 == correct: duel["scores"][p2] += 1
        
        duel["current_index"] += 1
        time.sleep(1)
        send_duel_question(duel_id)

    def finish_quiz_duel(duel_id):
        duel = active_quiz_duels.pop(duel_id, None)
        if not duel: return
        p1, p2 = duel["p1"], duel["p2"]
        s1, s2 = duel["scores"][p1], duel["scores"][p2]
        
        res = f"🏁 **DÜELLO BİTTİ!**\n\n👤 {users[p1]['name']}: {s1} Doğru\n👤 {users[p2]['name']}: {s2} Doğru\n\n"
        if s1 > s2: res += f"🏆 **KAZANAN:** {users[p1]['name']}! (+300 EXP)"; users[p1]["exp"] += 300
        elif s2 > s1: res += f"🏆 **KAZANAN:** {users[p2]['name']}! (+300 EXP)"; users[p2]["exp"] += 300
        else: res += "🤝 **BERABERE!** (+100 EXP)"; users[p1]["exp"] += 100; users[p2]["exp"] += 100
        
        save_users()
        bot.send_message(p1, res); bot.send_message(p2, res)

    @bot.message_handler(commands=['duello'])
    def duel_handler(message):
        user_id = str(message.from_user.id)
        if not users.get(user_id, {}).get("is_approved", True): return
        args = message.text.split()

        if len(args) >= 3 and args[1].startswith("@"):
            target_username, amount = args[1][1:], int(args[2])
            if users[user_id].get("money", 0) < amount: bot.reply_to(message, "❌ Yetersiz bakiye!"); return
            target_id = next((uid for uid, u in users.items() if u.get("username") == target_username), None)
            if not target_id: bot.reply_to(message, "❌ Kullanıcı bulunamadı."); return
            if target_id == user_id: bot.reply_to(message, "❌ Kendinle düello atamazsın."); return
            if users[target_id].get("money", 0) < amount: bot.reply_to(message, "❌ Rakibin parası yetersiz!"); return

            duel_id = str(uuid.uuid4())[:8]
            pending_duels[duel_id] = {"challenger": user_id, "target": target_id, "amount": amount}
            markup = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Kabul Et", callback_data=f"duel_accept_{duel_id}"), InlineKeyboardButton("❌ Reddet", callback_data=f"duel_reject_{duel_id}"))
            bot.send_message(message.chat.id, f"⚔️ **DÜELLO TEKLİFİ!** ⚔️\n\n@{users[user_id]['username']} sana meydan okuyor!\n💰 Bahis: {amount} $\n\n@{target_username}, kabul ediyor musun?", reply_markup=markup)
        elif len(args) == 2:
            amount = int(args[1])
            if users[user_id].get("money", 0) < amount: bot.reply_to(message, f"❌ Yetersiz Bakiye!"); return
            bot.reply_to(message, f"⚔️ **DÜELLO BAŞLADI!** ⚔️\nOrtadaki Ödül: {amount * 2} $\nZarlar atılıyor... 🎲")
            msg_user, msg_bot = bot.send_dice(message.chat.id, emoji="🎲"), bot.send_dice(message.chat.id, emoji="🎲")
            time.sleep(4)
            user_roll, bot_roll = msg_user.dice.value, msg_bot.dice.value
            msg = f"👤 Senin Zarın: {user_roll}\n🤖 Botun Zarı: {bot_roll}\n\n"
            if user_roll > bot_roll:
                users[user_id]["money"] += amount; users[user_id]["duel_wins"] = users[user_id].get("duel_wins", 0) + 1
                update_quest_progress(user_id, "duel_win"); msg += f"🎉 **KAZANDIN!** (+{amount} $)"
            elif bot_roll > user_roll:
                users[user_id]["money"] -= amount; msg += f"💀 **KAYBETTİN!** (-{amount} $)"
            else: msg += "🤝 **BERABERE!**"
            save_users(); bot.send_message(message.chat.id, msg)
        else:
            bot.reply_to(message, "⚠️ Kullanım:\n🤖 Botla: `/duello <miktar>`\n👤 Oyuncuyla: `/duello <@kullanici> <miktar>`")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("duel_"))
    def duel_response(call):
        action, duel_id = call.data.split("_")[1], call.data.split("_")[2]
        if duel_id not in pending_duels: bot.answer_callback_query(call.id, "⚠️ Teklif geçersiz."); return
        duel, user_id = pending_duels[duel_id], str(call.from_user.id)
        if user_id != duel["target"]: bot.answer_callback_query(call.id, "⛔ Bu teklif sana yapılmadı!"); return
        
        if action == "reject":
            bot.edit_message_text(f"❌ Düello reddedildi.", call.message.chat.id, call.message.message_id)
            del pending_duels[duel_id]; return
        
        challenger, amount = duel["challenger"], duel["amount"]
        if users[challenger]["money"] < amount or users[user_id]["money"] < amount:
            bot.edit_message_text("❌ Bakiyeler yetersiz, düello iptal.", call.message.chat.id, call.message.message_id)
            del pending_duels[duel_id]; return
            
        users[challenger]["money"] -= amount; users[user_id]["money"] -= amount
        bot.send_message(call.message.chat.id, f"⚔️ **DÜELLO KABUL EDİLDİ!** ⚔️\nOrtadaki Ödül: {amount * 2} $\n\n🎲 {users[challenger]['name']} atıyor...")
        dice1 = bot.send_dice(call.message.chat.id); time.sleep(3)
        bot.send_message(call.message.chat.id, f"🎲 {users[user_id]['name']} atıyor..."); dice2 = bot.send_dice(call.message.chat.id); time.sleep(3)
        
        val1, val2 = dice1.dice.value, dice2.dice.value
        if val1 > val2:
            users[challenger]["money"] += amount * 2; users[challenger]["duel_wins"] = users[challenger].get("duel_wins", 0) + 1
            bot.send_message(call.message.chat.id, f"🏆 **KAZANAN:** {users[challenger]['name']}! (+{amount} $)")
        elif val2 > val1:
            users[user_id]["money"] += amount * 2; users[user_id]["duel_wins"] = users[user_id].get("duel_wins", 0) + 1
            bot.send_message(call.message.chat.id, f"🏆 **KAZANAN:** {users[user_id]['name']}! (+{amount} $)")
        else:
            users[challenger]["money"] += amount; users[user_id]["money"] += amount
            bot.send_message(call.message.chat.id, "🤝 **BERABERE!** Paralar iade edildi.")
            
        del pending_duels[duel_id]; save_users()

    @bot.message_handler(commands=['bahis'])
    def set_bet(message):
        user_id = str(message.from_user.id)
        if not users.get(user_id, {}).get("is_approved", True): return
        try: amount = int(message.text.split()[1])
        except: bot.reply_to(message, "⚠️ Kullanım: /bahis <miktar>"); return
        if amount <= 0: bot.reply_to(message, "❌ Pozitif sayı gir."); return
        if users[user_id]["exp"] < amount: bot.reply_to(message, f"❌ Yetersiz EXP! ({users[user_id]['exp']})"); return
        if users[user_id].get("active_bet", 0) > 0: bot.reply_to(message, "⚠️ Zaten bahsin var!"); return
        
        users[user_id]["exp"] -= amount; users[user_id]["active_bet"] = amount; save_users()
        bot.reply_to(message, f"🎲 **BAHİS OYNANDI!**\nMasaya {amount} EXP koydun. Doğru bilirsen 2 katı!")

    @bot.message_handler(commands=['soruekle'])
    def suggest_question(message):
        user_id = str(message.from_user.id)
        if not users.get(user_id, {}).get("is_approved", True): return
        if len(message.text) < 15: bot.reply_to(message, "⚠️ Lütfen soruyu tam yaz.\nÖrnek: `/soruekle Soru... A)... B)... Cevap:A`", parse_mode="Markdown"); return
        
        suggestion = message.text.replace("/soruekle", "").strip()
        target_id = next((uid for uid, u in users.items() if u.get("username") == DEVELOPER_USERNAME), None)
        if target_id:
            bot.send_message(target_id, f"📩 **SORU ÖNERİSİ**\n👤 @{message.from_user.username}\n📝 {suggestion}")
            bot.reply_to(message, "✅ Önerin iletildi!")

    @bot.message_handler(commands=['sorudurumu'])
    def question_stats(message):
        user_id = str(message.from_user.id)
        if not users.get(user_id, {}).get("is_approved", True): return
        
        cat_stats = {}
        level_stats = {1: 0, 2: 0, 3: 0}
        
        for q in QUIZ_QUESTIONS:
            cat = q["category"].capitalize()
            cat_stats[cat] = cat_stats.get(cat, 0) + 1
            lvl = q.get("level", 1)
            level_stats[lvl] = level_stats.get(lvl, 0) + 1
            
        text = f"📊 **SORU BANKASI**\n🗂 Toplam: {len(QUIZ_QUESTIONS)}\n\n**📂 Kategoriler:**\n" + "\n".join([f"🔹 {k}: {v}" for k, v in cat_stats.items()])
        text += "\n\n**📈 Zorluk Analizi:**\n"
        text += f"🟢 Kolay (Lvl 1): {level_stats.get(1, 0)}\n🟡 Orta (Lvl 2): {level_stats.get(2, 0)}\n🔴 Zor (Lvl 3): {level_stats.get(3, 0)}"
        
        bot.reply_to(message, text)
