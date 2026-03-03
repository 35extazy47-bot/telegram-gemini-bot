import json
import random
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Bu değişkenler tirtil.py'den register fonksiyonu aracılığıyla alınacak
safe_generate_content = None
check_daily_limit = None

def register_study_handlers(bot, utils):
    """Ders ve çalışma ile ilgili komutları bota kaydeder."""
    global safe_generate_content, check_daily_limit
    safe_generate_content = utils['safe_generate_content']
    check_daily_limit = utils['check_daily_limit']

    @bot.message_handler(commands=['kart'])
    def flashcard(message):
        user_id = str(message.from_user.id)
        if not check_daily_limit(user_id):
            bot.reply_to(message, "⛔ Günlük AI limitin doldu! Yarın tekrar gel.")
            return

        args = message.text.split()
        subject = args[1] if len(args) > 1 else "Tarih"

        wait_msg = bot.reply_to(message, f"📇 **{subject}** dersi için bilgi kartı hazırlanıyor...", parse_mode="Markdown")

        try:
            prompt = (
                f"KPSS {subject} dersi için sınavda çıkabilecek çok önemli bir terim, kavram, olay veya tarih seç. "
                "Bunu şu JSON formatında ver: {\"soru\": \"Kavram/Soru\", \"cevap\": \"Kısa ve net açıklama\"}. "
                "Sadece JSON çıktısı ver, başka bir şey yazma."
            )
            response = safe_generate_content(prompt)
            text = response.text.replace("```json", "").replace("```", "").strip()
            if text.startswith("json"): text = text[4:].strip()
            
            data = json.loads(text)
            q = data['soru']
            a = data['cevap']
            
            # HTML formatında spoiler kullanarak cevabı gizliyoruz
            html_text = f"📇 <b>BİLGİ KARTI ({subject.upper()})</b>\n\n❓ <b>{q}</b>\n\n👇 <i>Cevabı görmek için dokun:</i>\n<span class=\"tg-spoiler\">💡 {a}</span>"
            
            bot.delete_message(message.chat.id, wait_msg.message_id)
            bot.send_message(message.chat.id, html_text, parse_mode="HTML")

        except Exception as e:
            bot.delete_message(message.chat.id, wait_msg.message_id)
            bot.send_message(message.chat.id, f"Kart oluşturulurken hata: {e}")

    @bot.message_handler(commands=['plan'])
    def study_plan(message):
        user_id = str(message.from_user.id)
        if not check_daily_limit(user_id):
            bot.reply_to(message, "⛔ Günlük AI limitin doldu!")
            return

        wait_msg = bot.reply_to(message, "📅 **Kişisel çalışma programın hazırlanıyor...**\n_(Yapay zeka senin için en verimli saatleri planlıyor)_", parse_mode="Markdown")
        
        try:
            prompt = (
                "KPSS'ye hazırlanan bir öğrenci için bugünlük (tek günlük) motive edici, "
                "gerçekçi ve verimli bir ders çalışma programı hazırla. "
                "Sabah, Öğle ve Akşam blokları olsun. Mola sürelerini de ekle. "
                "Samimi bir koç gibi konuş. Emoji kullan."
            )
            response = safe_generate_content(prompt)
            
            bot.delete_message(message.chat.id, wait_msg.message_id)
            bot.send_message(message.chat.id, f"📅 **GÜNLÜK ÇALIŞMA PLANI**\n\n{response.text}", parse_mode="Markdown")
        except Exception as e:
            bot.edit_message_text("Plan hazırlanamadı.", message.chat.id, wait_msg.message_id)

    @bot.message_handler(commands=['ozet'])
    def get_summary(message):
        if not check_daily_limit(message.from_user.id): bot.reply_to(message, "⛔ Günlük limit doldu."); return
        try:
            topic = message.text.replace("/ozet", "").strip()
            if not topic: bot.reply_to(message, "⚠️ Hangi konuyu özetleyeyim? Örnek: `/ozet Islahat Fermanı`", parse_mode="Markdown"); return
            
            wait_msg = bot.reply_to(message, f"📚 '{topic}' konusu özetleniyor...")
            res = safe_generate_content(f"'{topic}' konusunu KPSS öğrencisi için maddeler halinde, akılda kalıcı şekilde özetle.")
            
            bot.delete_message(message.chat.id, wait_msg.message_id)
            bot.reply_to(message, f"📝 **ÖZET: {topic.upper()}**\n\n{res.text}", parse_mode="Markdown")
        except: bot.reply_to(message, "Hata oluştu.")

    @bot.message_handler(commands=['motivasyon'])
    def motivation(message):
        quotes = [
            "Başarı, her gün tekrarlanan küçük çabaların toplamıdır. ✨",
            "Gelecek, bugünden hazırlananlara aittir. 🚀",
            "Yorgun olduğunda dinlen, bırakma. 💪",
            "Zorluklar, başarının değerini artıran süslerdir. 💎",
            "Sadece çalış, gerisi kendiliğinden gelir. 📚",
            "Hayallerin, bahanelerinden büyük olsun! 🌟"
        ]
        bot.reply_to(message, f"🔥 **Günün Sözü:**\n\n_{random.choice(quotes)}_", parse_mode="Markdown")