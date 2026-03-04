import json
import random
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Bu değişkenler tirtil.py'den register fonksiyonu aracılığıyla alınacak
safe_generate_content = None
check_daily_limit = None
users = None
save_users = None

def register_study_handlers(bot, utils):
    """Ders ve çalışma ile ilgili komutları bota kaydeder."""
    global safe_generate_content, check_daily_limit, users, save_users
    safe_generate_content = utils['safe_generate_content']
    check_daily_limit = utils['check_daily_limit']
    users = utils['users']
    save_users = utils['save_users']

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

    @bot.message_handler(commands=['notal'])
    def take_note(message):
        user_id = str(message.from_user.id)
        try:
            args = message.text.split(maxsplit=2)
            if len(args) < 3:
                bot.reply_to(message, "⚠️ Kullanım: `/notal <Ders> <Notun>`\nÖrnek: `/notal Tarih İstanbul 1453'te fethedildi.`", parse_mode="Markdown")
                return
            
            subject = args[1].capitalize()
            note_text = args[2]
            
            if "notes" not in users[user_id]:
                users[user_id]["notes"] = {}
            
            if subject not in users[user_id]["notes"]:
                users[user_id]["notes"][subject] = []
                
            users[user_id]["notes"][subject].append(note_text)
            save_users()
            
            bot.reply_to(message, f"✅ **{subject}** notu kaydedildi!")
        except Exception as e:
            bot.reply_to(message, f"Hata: {e}")

    @bot.message_handler(commands=['notlarim'])
    def view_notes(message):
        user_id = str(message.from_user.id)
        user_notes = users[user_id].get("notes", {})
        
        if not user_notes:
            bot.reply_to(message, "📂 Henüz hiç not almamışsın.\n`/notal <Ders> <Not>` ile başlayabilirsin.")
            return
            
        text = "📝 **DERS NOTLARIN**\n\n"
        for subject, notes in user_notes.items():
            text += f"📌 **{subject}**\n"
            for i, note in enumerate(notes, 1):
                text += f"   {i}. {note}\n"
            text += "\n"
            
        bot.send_message(message.chat.id, text, parse_mode="Markdown")

    @bot.message_handler(commands=['kaynak'])
    def recommend_resources(message):
        if not check_daily_limit(message.from_user.id): bot.reply_to(message, "⛔ Günlük AI limitin doldu!"); return
        try:
            subject = message.text.replace("/kaynak", "").strip()
            if not subject: bot.reply_to(message, "⚠️ Hangi ders? Örnek: `/kaynak Coğrafya`", parse_mode="Markdown"); return
            wait_msg = bot.reply_to(message, f"📚 **{subject}** için kaynaklar araştırılıyor...")
            res = safe_generate_content(f"KPSS öğrencisi için '{subject}' dersine yönelik en iyi YouTube kanalları, soru bankaları ve çalışma taktiklerini öner. Samimi ol.")
            bot.delete_message(message.chat.id, wait_msg.message_id)
            bot.send_message(message.chat.id, f"📚 **KAYNAK TAVSİYELERİ: {subject.upper()}**\n\n{res.text}", parse_mode="Markdown")
        except: bot.reply_to(message, "Hata oluştu.")