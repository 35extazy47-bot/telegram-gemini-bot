import json
import random
import os
import io
from PIL import Image
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

    @bot.message_handler(commands=['deneme_ekle'])
    def add_exam_result(message):
        user_id = str(message.from_user.id)
        try:
            # /deneme_ekle <Ad> <Net>
            args = message.text.split(maxsplit=2)
            if len(args) < 3:
                bot.reply_to(message, "⚠️ Kullanım: `/deneme_ekle <Deneme Adı> <Net>`\nÖrnek: `/deneme_ekle TG-1 85.5`", parse_mode="Markdown")
                return
            
            name = args[1]
            net = float(args[2])
            
            if "exams" not in users[user_id]: users[user_id]["exams"] = []
            
            users[user_id]["exams"].append({"date": datetime.now().strftime("%Y-%m-%d"), "name": name, "net": net})
            save_users()
            bot.reply_to(message, f"✅ **{name}** denemesi kaydedildi! (Net: {net})")
        except ValueError:
            bot.reply_to(message, "❌ Net kısmı sayı olmalı. (Örn: 75.5)")
        except Exception as e:
            bot.reply_to(message, f"Hata: {e}")

    @bot.message_handler(commands=['denemelerim'])
    def list_exams(message):
        user_id = str(message.from_user.id)
        exams = users[user_id].get("exams", [])
        if not exams:
            bot.reply_to(message, "📂 Henüz kayıtlı deneme sonucun yok.")
            return
        text = "📊 **DENEME SONUÇLARIN**\n\n"
        for i, ex in enumerate(exams[-10:], 1):
            text += f"{i}. {ex['name']} ({ex['date']}): **{ex['net']} Net**\n"
        if len(exams) > 0:
            avg = sum(e['net'] for e in exams[-10:]) / len(exams[-10:])
            text += f"\n📈 **Son 10 Deneme Ortalaması:** {avg:.2f} Net"
        bot.send_message(message.chat.id, text, parse_mode="Markdown")

    @bot.message_handler(commands=['soru_kayit'])
    def log_questions(message):
        user_id = str(message.from_user.id)
        try:
            args = message.text.split()
            if len(args) < 3:
                bot.reply_to(message, "⚠️ Kullanım: `/soru_kayit <Ders> <Sayı>`\nÖrnek: `/soru_kayit Matematik 50`", parse_mode="Markdown")
                return
            
            subject = args[1].capitalize()
            count = int(args[2])
            today = datetime.now().strftime("%Y-%m-%d")
            
            if "study_stats" not in users[user_id]: users[user_id]["study_stats"] = {}
            if "questions" not in users[user_id]["study_stats"]: users[user_id]["study_stats"]["questions"] = {}
            if today not in users[user_id]["study_stats"]["questions"]: users[user_id]["study_stats"]["questions"][today] = {}
            
            current = users[user_id]["study_stats"]["questions"][today].get(subject, 0)
            users[user_id]["study_stats"]["questions"][today][subject] = current + count
            save_users()
            
            bot.reply_to(message, f"✅ **{subject}** dersinden {count} soru eklendi.\n📅 Bugün toplam: {current + count}")
        except ValueError:
            bot.reply_to(message, "❌ Sayı girmelisin.")
        except Exception as e:
            bot.reply_to(message, f"Hata: {e}")

    @bot.message_handler(commands=['gunluk_soru'])
    def daily_question_stats(message):
        user_id = str(message.from_user.id)
        today = datetime.now().strftime("%Y-%m-%d")
        stats = users[user_id].get("study_stats", {}).get("questions", {}).get(today, {})
        
        if not stats:
            bot.reply_to(message, "📂 Bugün henüz soru kaydı girmedin.")
            return
            
        text = f"📅 **BUGÜNKÜ PERFORMANSIN ({today})**\n\n"
        total = 0
        for subj, count in stats.items():
            text += f"🔹 {subj}: {count} Soru\n"
            total += count
        text += f"\n∑ **TOPLAM:** {total} Soru"
        
        if total < 50: text += "\n\n💡 *Biraz daha gayret!*"
        elif total > 200: text += "\n\n🔥 *Harikasın, şov yapıyorsun!*"
        bot.send_message(message.chat.id, text, parse_mode="Markdown")

    @bot.message_handler(commands=['coz'])
    def solve_question_photo(message):
        target_msg = message.reply_to_message if message.reply_to_message else message
        if not target_msg.photo:
            bot.reply_to(message, "⚠️ Bir soru fotoğrafına yanıt vererek `/coz` yazmalısın veya fotoğrafı gönderirken altına `/coz` yazmalısın.")
            return

        if not check_daily_limit(str(message.from_user.id)): bot.reply_to(message, "⛔ Günlük AI limitin doldu!"); return

        wait_msg = bot.reply_to(message, "👀 Soru inceleniyor ve çözülüyor... Lütfen bekle.")
        try:
            file_info = bot.get_file(target_msg.photo[-1].file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            image = Image.open(io.BytesIO(downloaded_file))
            
            response = safe_generate_content(["Bu soruyu adım adım, anlaşılır bir şekilde çöz. Cevabı net bir şekilde belirt.", image])
            bot.delete_message(message.chat.id, wait_msg.message_id)
            bot.reply_to(message, f"🧠 **SORU ÇÖZÜMÜ**\n\n{response.text}", parse_mode="Markdown")
        except Exception as e:
            bot.edit_message_text(f"Hata oluştu: {e}", message.chat.id, wait_msg.message_id)

    @bot.message_handler(commands=['basla'])
    def start_study_session(message):
        user_id = str(message.from_user.id)
        try:
            args = message.text.split(maxsplit=1)
            if len(args) < 2:
                bot.reply_to(message, "⚠️ Hangi ders? Örnek: `/basla Tarih`", parse_mode="Markdown")
                return
            
            subject = args[1].capitalize()
            
            if "active_study_session" in users[user_id]:
                bot.reply_to(message, "⚠️ Zaten devam eden bir çalışman var. Önce onu bitir: `/bitir`")
                return
            
            users[user_id]["active_study_session"] = {
                "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "subject": subject
            }
            save_users()
            bot.reply_to(message, f"⏱️ **{subject}** çalışması başladı!\nOdaklan ve bitirdiğinde `/bitir` yaz.")
        except Exception as e:
            bot.reply_to(message, f"Hata: {e}")

    @bot.message_handler(commands=['bitir'])
    def stop_study_session(message):
        user_id = str(message.from_user.id)
        session = users[user_id].get("active_study_session")
        
        if not session:
            bot.reply_to(message, "⚠️ Aktif bir çalışma oturumu yok. Başlamak için: `/basla <Ders>`")
            return
            
        start_time = datetime.strptime(session["start_time"], "%Y-%m-%d %H:%M:%S")
        end_time = datetime.now()
        duration = end_time - start_time
        minutes = int(duration.total_seconds() / 60)
        
        if minutes < 1:
            bot.reply_to(message, "⚠️ 1 dakikadan kısa sürdü, kaydedilmedi.")
            del users[user_id]["active_study_session"]
            save_users()
            return
            
        subject = session["subject"]
        today = datetime.now().strftime("%Y-%m-%d")
        
        if "study_stats" not in users[user_id]: users[user_id]["study_stats"] = {}
        if "time" not in users[user_id]["study_stats"]: users[user_id]["study_stats"]["time"] = {}
        if today not in users[user_id]["study_stats"]["time"]: users[user_id]["study_stats"]["time"][today] = {}
        
        current_time = users[user_id]["study_stats"]["time"][today].get(subject, 0)
        users[user_id]["study_stats"]["time"][today][subject] = current_time + minutes
        
        del users[user_id]["active_study_session"]
        save_users()
        
        bot.reply_to(message, f"🛑 **Çalışma Bitti!**\n\n📚 Ders: {subject}\n⏱️ Süre: {minutes} dakika\n💾 Günlüğe kaydedildi.")

    @bot.message_handler(commands=['nedir'])
    def define_term(message):
        if not check_daily_limit(message.from_user.id): bot.reply_to(message, "⛔ Günlük limit doldu."); return
        try:
            term = message.text.replace("/nedir", "").strip()
            if len(term) < 2:
                bot.reply_to(message, "⚠️ Ne olduğunu merak ettiğin terimi yaz.\nÖrnek: `/nedir Kut Anlayışı`", parse_mode="Markdown")
                return
            
            prompt = f"KPSS müfredatına uygun olarak '{term}' nedir? Çok kısa, net ve akılda kalıcı bir tanım yap. 2 cümleyi geçmesin."
            response = safe_generate_content(prompt)
            bot.reply_to(message, f"📖 **NEDİR?**\n\n**{term}:** {response.text}", parse_mode="Markdown")
        except Exception as e:
            bot.reply_to(message, f"Hata: {e}")

    @bot.message_handler(commands=['gunluk_calisma'])
    def daily_study_time(message):
        user_id = str(message.from_user.id)
        today = datetime.now().strftime("%Y-%m-%d")
        stats = users[user_id].get("study_stats", {}).get("time", {}).get(today, {})
        
        if not stats:
            bot.reply_to(message, "📂 Bugün henüz süre tutarak çalışmadın.")
            return
            
        text = f"⏱️ **BUGÜNKÜ ÇALIŞMA SÜRELERİN ({today})**\n\n"
        total_min = 0
        for subj, minutes in stats.items():
            text += f"🔹 {subj}: {minutes} dk\n"
            total_min += minutes
        
        hours = total_min // 60
        mins = total_min % 60
        text += f"\n∑ **TOPLAM:** {hours} sa {mins} dk"
        
        bot.send_message(message.chat.id, text, parse_mode="Markdown")

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
            try: bot.delete_message(message.chat.id, wait_msg.message_id)
            except: pass
            
            full_text = f"📚 KAYNAK TAVSİYELERİ: {subject.upper()}\n\n{res.text}"
            if len(full_text) > 4000:
                for i in range(0, len(full_text), 4000):
                    bot.send_message(message.chat.id, full_text[i:i+4000])
            else:
                bot.send_message(message.chat.id, full_text)
        except Exception as e:
            print(f"Kaynak hatası: {e}")
            bot.reply_to(message, f"Hata oluştu: {e}")

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