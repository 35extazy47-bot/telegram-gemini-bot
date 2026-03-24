import random
import io
import os
from datetime import datetime

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from PIL import Image, ImageDraw, ImageFont

# Bu değişkenler ana bot dosyasından (tirtil.py) doldurulacak
safe_generate_content = None
check_daily_limit = None

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

def register_fun_handlers(bot, utils):
    """Eğlence ve AI komutlarını bota kaydeder."""
    global safe_generate_content, check_daily_limit
    safe_generate_content = utils['safe_generate_content']
    check_daily_limit = utils['check_daily_limit']

    @bot.message_handler(commands=['ozet'])
    def get_summary(message):
        if not check_daily_limit(message.from_user.id): bot.reply_to(message, "⛔ Günlük limit doldu."); return
        try:
            topic = message.text.replace("/ozet", "").strip()
            if not topic: bot.reply_to(message, "⚠️ Konu yazmalısın."); return
            res = safe_generate_content(f"'{topic}' konusunu KPSS öğrencisi için maddeler halinde özetle.")
            full_text = f"📝 **ÖZET: {topic.upper()}**\n\n{res.text}"
            if len(full_text) > 4096:
                bot.reply_to(message, full_text[:4096], parse_mode="Markdown")
                for i in range(4096, len(full_text), 4096):
                    bot.send_message(message.chat.id, full_text[i:i+4096], parse_mode="Markdown")
            else:
                bot.reply_to(message, full_text, parse_mode="Markdown")
        except: bot.reply_to(message, "Hata oluştu.")

    @bot.message_handler(commands=['ruya'])
    def dream_interpret(message):
        if not check_daily_limit(message.from_user.id): bot.reply_to(message, "⛔ Günlük limit doldu."); return
        try:
            dream = message.text.replace("/ruya", "").strip()
            if not dream: bot.reply_to(message, "⚠️ Rüyayı yazmalısın."); return
            res = safe_generate_content(f"Rüya tabircisi gibi konuş. Şu rüyayı yorumla: '{dream}'")
            full_text = f"🌙 **RÜYA TABİRİ**\n\n{res.text}"
            if len(full_text) > 4096:
                bot.reply_to(message, full_text[:4096])
                for i in range(4096, len(full_text), 4096):
                    bot.send_message(message.chat.id, full_text[i:i+4096])
            else:
                bot.reply_to(message, full_text)
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
            caption = f"🔮 **TAROT FALI**\n\n{res.text}"
            if len(caption) > 1024:
                bot.send_photo(message.chat.id, photo)
                if len(caption) > 4096:
                    for i in range(0, len(caption), 4096):
                        bot.send_message(message.chat.id, caption[i:i+4096])
                else:
                    bot.send_message(message.chat.id, caption)
            else:
                bot.send_photo(message.chat.id, photo, caption=caption)
        except: bot.reply_to(message, "Fal bakılamadı.")

    @bot.message_handler(commands=['burc'])
    def daily_horoscope(message):
        if not check_daily_limit(message.from_user.id): bot.reply_to(message, "⛔ Günlük limit doldu."); return
        msg = bot.reply_to(message, "♈ Burcunu yaz...")
        def send_horoscope(m):
            text = safe_generate_content(f"{m.text} burcu için günlük yorum yap.").text
            if len(text) > 4096:
                bot.reply_to(m, text[:4096])
                for i in range(4096, len(text), 4096):
                    bot.send_message(m.chat.id, text[i:i+4096])
            else:
                bot.reply_to(m, text)
        bot.register_next_step_handler(msg, send_horoscope)

    @bot.message_handler(commands=['bilgi'])
    def random_fact(message):
        if not check_daily_limit(message.from_user.id): bot.reply_to(message, "⛔ Günlük limit doldu."); return
        text = safe_generate_content("İlginç bir genel kültür bilgisi ver.").text
        if len(text) > 4096:
            for i in range(0, len(text), 4096):
                bot.send_message(message.chat.id, text[i:i+4096])
        else:
            bot.reply_to(message, text)

    @bot.message_handler(commands=['tarihtebugun'])
    def history_today(message):
        text = safe_generate_content(f"Tarihte bugün ({datetime.now().strftime('%d %B')}) ne oldu?").text
        if len(text) > 4096:
            for i in range(0, len(text), 4096):
                bot.send_message(message.chat.id, text[i:i+4096])
        else:
            bot.reply_to(message, text)