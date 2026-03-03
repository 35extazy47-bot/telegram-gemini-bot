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