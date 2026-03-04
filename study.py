import json
import random
import os
from datetime import datetime
from database import shared_files, save_market_data

FPDF = None

# Bu değişkenler tirtil.py'den register fonksiyonu aracılığıyla alınacak
class MockResponse: text = ""
safe_generate_content = lambda x: MockResponse()
check_daily_limit = lambda x: True
users = {}
save_users = lambda: None

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

    @bot.message_handler(commands=['ders_notu'])
    def generate_lecture_note(message):
        if not check_daily_limit(message.from_user.id): bot.reply_to(message, "⛔ Günlük AI limitin doldu!"); return
        try:
            topic = message.text.replace("/ders_notu", "").strip()
            if not topic: bot.reply_to(message, "⚠️ Hangi konuda not hazırlayayım? Örnek: `/ders_notu Osmanlı Duraklama Dönemi`", parse_mode="Markdown"); return
            
            wait_msg = bot.reply_to(message, f"📝 **'{topic}'** hakkında detaylı ders notu hazırlanıyor... (Bu biraz sürebilir)")
            
            prompt = f"'{topic}' konusu hakkında bir öğrenci için çok detaylı, maddeler halinde, sınavda çıkabilecek önemli yerleri vurgulayan bir ders notu hazırla. Başlıklar kullan. Uzun ve kapsamlı olsun."
            response = safe_generate_content(prompt)
            content = response.text
            
            # PDF Oluşturma
            file_name = f"{topic.replace(' ', '_')}_Notlari.pdf"
            
            if FPDF:
                pdf = FPDF()
                pdf.add_page()
                # Türkçe karakter sorunu için font eklemek gerekir ama basitlik adına latin-1 encode deneyeceğiz veya txt fallback yapacağız.
                # FPDF standart fontları Türkçe desteklemez. O yüzden güvenli yol olarak TXT veya basit PDF deneyelim.
                # En garantisi TXT dosyasıdır, çünkü font dosyası yüklemeden Türkçe PDF zordur.
                # Ancak kullanıcı PDF istedi, basit bir trick yapalım:
                
                # Türkçe karakterleri destekleyen bir font yoksa TXT daha sağlıklıdır.
                # Biz şimdilik TXT olarak kaydedip gönderelim, çünkü sunucuda font dosyası olmayabilir.
                file_name = f"{topic.replace(' ', '_')}_Notlari.txt"
                with open(file_name, "w", encoding="utf-8") as f:
                    f.write(f"KONU: {topic.upper()}\n\n" + content)
                
                with open(file_name, "rb") as f:
                    bot.send_document(message.chat.id, f, caption=f"📚 **{topic}** Ders Notu Hazır!")
                os.remove(file_name) # Temizlik
            else:
                # FPDF yoksa TXT
                file_name = f"{topic.replace(' ', '_')}_Notlari.txt"
                with open(file_name, "w", encoding="utf-8") as f:
                    f.write(f"KONU: {topic.upper()}\n\n" + content)
                with open(file_name, "rb") as f:
                    bot.send_document(message.chat.id, f, caption=f"📚 **{topic}** Ders Notu Hazır!")
                os.remove(file_name)

            bot.delete_message(message.chat.id, wait_msg.message_id)
        except Exception as e:
            bot.reply_to(message, f"Not oluşturulurken hata: {e}")

    @bot.message_handler(commands=['dosya_yukle'])
    def upload_file_instruction(message):
        if not message.reply_to_message or not message.reply_to_message.document:
            bot.reply_to(message, "⚠️ Dosya yüklemek için, bir PDF veya belgeye yanıt vererek şu komutu yazmalısın:\n\n`/dosya_yukle <Ders/Konu Adı>`\n\nÖrnek: Arkadaşının attığı PDF'e yanıt verip `/dosya_yukle Tarih Notları` yaz.", parse_mode="Markdown")
            return
        
        try:
            doc = message.reply_to_message.document
            file_name = message.text.replace("/dosya_yukle", "").strip()
            if not file_name: file_name = doc.file_name
            
            file_data = {
                "file_id": doc.file_id,
                "name": file_name,
                "type": doc.mime_type,
                "uploader": message.from_user.first_name,
                "date": datetime.now().strftime("%Y-%m-%d")
            }
            
            shared_files.append(file_data)
            save_market_data() # Veritabanına kaydet
            
            bot.reply_to(message, f"✅ **Dosya Kütüphaneye Eklendi!**\n📂 Adı: {file_name}\nTeşekkürler! Diğer öğrenciler `/dosya_ara` ile buna ulaşabilir.")
        except Exception as e:
            bot.reply_to(message, f"Yükleme hatası: {e}")

    @bot.message_handler(commands=['dosya_ara'])
    def search_files(message):
        query = message.text.replace("/dosya_ara", "").strip().lower()
        if not query:
            bot.reply_to(message, "⚠️ Ne arıyorsun? Örnek: `/dosya_ara Tarih`", parse_mode="Markdown")
            return
            
        results = [f for f in shared_files if query in f["name"].lower()]
        
        if not results:
            bot.reply_to(message, "📂 Aradığın kriterde dosya bulunamadı.\nBelki sen yüklemek istersin? (`/dosya_yukle`)")
            return
            
        text = f"🔎 **ARAMA SONUÇLARI: '{query}'**\n\n"
        for i, f in enumerate(results[:10]): # İlk 10 sonuç
            text += f"{i+1}. 📄 **{f['name']}**\n   👤 {f['uploader']} | 📅 {f['date']}\n   ⬇️ İndir: `/indir {i}` (Bu özellik yakında)\n\n"
        
        # Şimdilik direkt butonla veya ID ile indirme karmaşık olacağı için, bulunan ilk 3 dosyayı direkt gönderelim
        bot.send_message(message.chat.id, text, parse_mode="Markdown")
        
        for f in results[:3]:
            bot.send_document(message.chat.id, f["file_id"], caption=f"📄 {f['name']}\n👤 Gönderen: {f['uploader']}")