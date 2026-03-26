import json
import random
import os
import io
from PIL import Image
import uuid
from datetime import datetime
from threading import Timer

import matplotlib
matplotlib.use('Agg') # Non-GUI backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import shared_files, save_market_data, study_pool, active_sessions

FPDF = None
gTTS = None
try:
    from gtts import gTTS
except ImportError:
    pass

# Bu değişkenler tirtil.py'den register fonksiyonu aracılığıyla alınacak
class MockResponse: text = ""
safe_generate_content = lambda x: MockResponse()
check_daily_limit = lambda x: True
users = {}
save_users = lambda: None

DAY_MAP = {
    "pazartesi": 0, "pzt": 0,
    "sali": 1,
    "carsamba": 2, "çar": 2,
    "persembe": 3, "per": 3,
    "cuma": 4,
    "cumartesi": 5, "cmt": 5,
    "pazar": 6, "paz": 6
}
DAY_NAMES = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]


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

            try: bot.delete_message(message.chat.id, wait_msg.message_id)
            except: pass

            full_text = f"📅 GÜNLÜK ÇALIŞMA PLANI\n\n{response.text}"
            if len(full_text) > 4000:
                for i in range(0, len(full_text), 4000):
                    bot.send_message(message.chat.id, full_text[i:i+4000])
            else:
                bot.send_message(message.chat.id, full_text)
        except Exception as e:
            print(f"Plan hatası: {e}")
            bot.reply_to(message, f"Hata oluştu: {e}")

    @bot.message_handler(commands=['ozet'])
    def get_summary(message):
        if not check_daily_limit(message.from_user.id): bot.reply_to(message, "⛔ Günlük limit doldu."); return
        try:
            topic = message.text.replace("/ozet", "").strip()
            if not topic: bot.reply_to(message, "⚠️ Hangi konuyu özetleyeyim? Örnek: `/ozet Islahat Fermanı`"); return
            
            wait_msg = bot.reply_to(message, f"📚 '{topic}' konusu özetleniyor...")
            res = safe_generate_content(f"'{topic}' konusunu KPSS öğrencisi için maddeler halinde, akılda kalıcı şekilde özetle.")
            
            bot.delete_message(message.chat.id, wait_msg.message_id)
            
            full_text = f"📝 ÖZET: {topic.upper()}\n\n{res.text}"
            if len(full_text) > 4000:
                bot.reply_to(message, full_text[:4000])
                for i in range(4000, len(full_text), 4000):
                    bot.send_message(message.chat.id, full_text[i:i+4000])
            else:
                bot.reply_to(message, full_text)
        except Exception as e:
            print(f"Özet hatası: {e}")
            bot.reply_to(message, f"Hata oluştu: {e}")

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
        
        # Grafik için en az 2 veri noktası gerekir.
        if not exams or len(exams) < 2:
            bot.reply_to(message, "📂 Grafik oluşturmak için en az 2 kayıtlı deneme sonucun olmalı.\n`/deneme_ekle <Ad> <Net>` ile ekleyebilirsin.", parse_mode="Markdown")
            return

        wait_msg = bot.reply_to(message, "📈 Gelişim grafiğin oluşturuluyor...")

        try:
            # Verileri hazırla (Son 30 deneme)
            exams_to_plot = exams[-30:]
            dates = [datetime.strptime(ex['date'], "%Y-%m-%d") for ex in exams_to_plot]
            nets = [ex['net'] for ex in exams_to_plot]

            # t.style.use('dark_background')
            fig, ax = plt.subplots(figsize=(12, 7), dpi=100)
            ax.set_facecolor('#0f172a')

            # Yumuşak Çizgi ve Alan Doldurma (Area Chart)
            ax.plot(dates, nets, marker='o', markersize=8, linewidth=3, color='#22c55e', label='Netlerin', markerfacecolor='#ffffff', markeredgewidth=2)

            # Trend çizgisi (Lineer regresyon)
            if len(dates) > 1:
                x_nums = mdates.date2num(dates)
                m, b = np.polyfit(x_nums, nets, 1)
                ax.plot(dates, m*x_nums + b, linestyle='--', color='#38bdf8', alpha=0.8, label=f'Gelişim Eğilimi')

            ax.set_title('DENEME PERFORMANS ANALİZİ', fontsize=18, fontweight='bold', color='#f1f5f9', pad=30)
            ax.set_ylabel('Net Sayısı', fontsize=12, color='#94a3b8', labelpad=15) # Y ekseni etiketi
            ax.tick_params(axis='both', colors='#94a3b8', labelsize=10) # X ve Y ekseni işaretleri

            
            buf = io.BytesIO()
            plt.savefig(buf, format='png')
            buf.seek(0)
            plt.close(fig)

            all_nets = [e['net'] for e in exams]
            avg = sum(all_nets) / len(all_nets)
            
            caption = (f"📊 **DENEME PERFORMANSIN**\n\n"
                       f"📈 **Ortalama Net:** {avg:.2f}\n"
                       f"🚀 **En Yüksek Net:** {max(all_nets):.2f}\n"
                       f"📉 **En Düşük Net:** {min(all_nets):.2f}\n\n"
                       f"_Grafik son 30 denemeni göstermektedir._")

            bot.delete_message(message.chat.id, wait_msg.message_id)
            bot.send_photo(message.chat.id, buf, caption=caption, parse_mode="Markdown")
        except Exception as e:
            bot.delete_message(message.chat.id, wait_msg.message_id)
            bot.reply_to(message, f"Grafik oluşturulurken bir hata oluştu: {e}")

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

        if len(text) > 4096:
            # Mesaj çok uzunsa parçalara ayırarak gönder
            for i in range(0, len(text), 4096):
                bot.send_message(message.chat.id, text[i:i+4096], parse_mode="Markdown")
        else:
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

    @bot.message_handler(commands=['kelime_avcisi'])
    def vocab_builder_menu(message):
        user_id = str(message.from_user.id)
        if not check_daily_limit(user_id):
            bot.reply_to(message, "⛔ Günlük AI limitin doldu!"); return
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🇬🇧 Genel İngilizce", callback_data="vocab_genel"))
        markup.add(InlineKeyboardButton("🎓 YDS / YÖKDİL", callback_data="vocab_yds"))
        
        bot.reply_to(message, "🇬🇧 **İNGİLİZCE KELİME AVCISI**\n\nHangi seviyede çalışma yapmak istersin?", reply_markup=markup)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("vocab_"))
    def generate_vocab_card(call):
        user_id = str(call.from_user.id)
        level = "YDS/YÖKDİL (Akademik)" if "yds" in call.data else "Günlük Konuşma (A2-B1)"
        
        bot.answer_callback_query(call.id, "Kelimeler hazırlanıyor...")
        wait_msg = bot.send_message(call.message.chat.id, f"🤖 **{level}** seviyesinde kelimeler ve test hazırlanıyor... 🇬🇧")
        
        try:
            prompt = f"""
            İngilizce öğrenen bir Türk öğrenci için '{level}' seviyesinde 5 adet önemli İngilizce kelime seç.
            Her kelime için: Kelime, Türkçe anlamı ve İngilizce örnek cümle ver.
            Ayrıca bu 5 kelimeyi test etmek için 5 adet çoktan seçmeli soru (quiz) hazırla.
            
            Çıktıyı SADECE şu JSON formatında ver, başka hiçbir metin yazma:
            {{
                "words": [
                    {{"word": "Kelime1", "meaning": "Anlamı", "sentence": "Örnek cümle"}}, ...
                ],
                "quiz": [
                    {{"question": "Soru metni...", "options": ["A) ...", "B) ...", "C) ...", "D) ..."], "answer": "A", "explanation": "Açıklama"}}, ...
                ]
            }}
            """
            response = safe_generate_content(prompt)
            text_resp = response.text.replace("```json", "").replace("```", "").strip()
            if text_resp.startswith("json"): text_resp = text_resp[4:].strip()
            
            data = json.loads(text_resp)
            msg_text = f"🇬🇧 **GÜNÜN KELİMELERİ ({level})**\n\n"
            for w in data["words"]: msg_text += f"🔹 **{w['word']}**: {w['meaning']}\n   _{w['sentence']}_\n\n"
            msg_text += "👇 Kelimeleri öğrendiysen teste geç!"
            
            users[user_id]["ai_quiz_queue"] = data["quiz"]; users[user_id]["ai_quiz_topic"] = f"Kelime Avcısı ({level})"; save_users()
            markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🧠 Testi Başlat", callback_data="start_vocab_quiz"))
            bot.delete_message(call.message.chat.id, wait_msg.message_id); bot.send_message(call.message.chat.id, msg_text, reply_markup=markup, parse_mode="Markdown")
        except Exception as e: bot.delete_message(call.message.chat.id, wait_msg.message_id); bot.send_message(call.message.chat.id, f"Hata: {e}")

    @bot.message_handler(content_types=['voice'])
    def handle_voice_note(message):
        user_id = str(message.from_user.id)
        if not users.get(user_id, {}).get("is_approved", True): return
        
        if not check_daily_limit(user_id):
            bot.reply_to(message, "⛔ Günlük AI limitin doldu!"); return

        wait_msg = bot.reply_to(message, "🎧 Sesli notun dinleniyor ve özetleniyor...", parse_mode="Markdown")

        try:
            file_info = bot.get_file(message.voice.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            
            prompt_parts = [
                "Bu ses kaydını deşifre et ve içeriğini net, anlaşılır bir ders notu olarak özetle. Önemli terimleri vurgula.",
                {"mime_type": "audio/ogg", "data": downloaded_file}
            ]
            
            response = safe_generate_content(prompt_parts)
            note_content = response.text
            
            if "notes" not in users[user_id]: users[user_id]["notes"] = {}
            category = "Sesli Notlar"
            if category not in users[user_id]["notes"]: users[user_id]["notes"][category] = []
            
            users[user_id]["notes"][category].append(f"🎙️ {datetime.now().strftime('%d.%m %H:%M')}\n{note_content}")
            save_users()
            
            bot.delete_message(message.chat.id, wait_msg.message_id)
            full_text = f"📝 **SESLİ NOT KAYDEDİLDİ**\n\n{note_content}\n\n_Notlarına /notlarim ile ulaşabilirsin._"
            if len(full_text) > 4096:
                bot.reply_to(message, full_text[:4096], parse_mode="Markdown")
                for i in range(4096, len(full_text), 4096):
                    bot.send_message(message.chat.id, full_text[i:i+4096], parse_mode="Markdown")
            else:
                bot.reply_to(message, full_text, parse_mode="Markdown")
            
        except Exception as e:
            try: bot.delete_message(message.chat.id, wait_msg.message_id)
            except: pass
            bot.reply_to(message, f"Hata: {e}")

    @bot.message_handler(commands=['harita'])
    def generate_mind_map(message):
        user_id = str(message.from_user.id)
        if not check_daily_limit(user_id):
            bot.reply_to(message, "⛔ Günlük AI limitin doldu!"); return
        
        try:
            topic = message.text.replace("/harita", "").strip()
            if not topic:
                bot.reply_to(message, "⚠️ Hangi konu için kavram haritası oluşturayım?\nÖrnek: `/harita Osmanlı Duraklama Dönemi`", parse_mode="Markdown")
                return
            
            wait_msg = bot.reply_to(message, f"🗺️ **'{topic}'** için kavram haritası oluşturuluyor...")
            
            prompt = f"""
            '{topic}' konusu için detaylı bir kavram haritası (zihin haritası) oluştur.
            Hiyerarşik bir yapı kullan. Ana başlık, alt başlıklar ve detaylar olsun.
            Görselliği artırmak için emojiler ve ağaç yapısı (dallar) kullan.
            Metin tabanlı bir şema olsun. Cevabı sadece şema olarak ver.
            Örnek yapı:
            🌳 ANA KONU
            ├── 🌿 Alt Başlık 1
            │   ├── 🍃 Detay A
            │   └── 🍃 Detay B
            └── 🌿 Alt Başlık 2
            """
            response = safe_generate_content(prompt)
            
            bot.delete_message(message.chat.id, wait_msg.message_id)
            full_text = f"🗺️ **KAVRAM HARİTASI: {topic.upper()}**\n\n{response.text}"
            if len(full_text) > 4096:
                for i in range(0, len(full_text), 4096):
                    bot.send_message(message.chat.id, full_text[i:i+4096])
            else:
                bot.send_message(message.chat.id, full_text)
        except Exception as e:
            bot.reply_to(message, f"Hata oluştu: {e}")

    @bot.message_handler(commands=['hedef'])
    def set_exam_goal(message):
        user_id = str(message.from_user.id)
        
        try:
            # /hedef KPSS 2024-07-14
            args = message.text.split(maxsplit=2)
            if len(args) < 3:
                bot.reply_to(message, "⚠️ Kullanım: `/hedef <Sınav Adı> <YYYY-AA-GG>`\nÖrnek: `/hedef KPSS 2024-07-14`", parse_mode="Markdown")
                return
            
            exam_name = args[1]
            date_str = args[2]
            
            # Tarih formatı kontrolü
            exam_date = datetime.strptime(date_str, "%Y-%m-%d")
            today = datetime.now()
            
            if exam_date < today:
                bot.reply_to(message, "⚠️ Geçmiş bir tarihe hedef koyamazsın.")
                return
                
            users[user_id]["exam_goal"] = {
                "name": exam_name,
                "date": date_str
            }
            save_users()
            
            remaining = (exam_date.date() - today.date()).days
            bot.reply_to(message, f"✅ **HEDEF KAYDEDİLDİ!**\n\n🎯 Sınav: {exam_name}\n📅 Tarih: {date_str}\n⏳ Kalan Süre: {remaining} Gün\n\n_Her sabah 08:30'da sana hatırlatacağım!_ ⏰", parse_mode="Markdown")
            
        except ValueError:
            bot.reply_to(message, "⚠️ Tarih formatı hatalı. Yıl-Ay-Gün (2024-07-14) şeklinde olmalı.")
        except Exception as e:
            bot.reply_to(message, f"Hata: {e}")

    @bot.message_handler(commands=['sesli_ozet'])
    def voice_summary(message):
        user_id = str(message.from_user.id)
        if not check_daily_limit(user_id):
            bot.reply_to(message, "⛔ Günlük AI limitin doldu!"); return
        
        if not gTTS:
            bot.reply_to(message, "⚠️ Bu özellik için sunucuda 'gTTS' kütüphanesi eksik.\n`pip install gTTS` komutu ile yüklenmelidir.", parse_mode="Markdown")
            return

        try:
            topic = message.text.replace("/sesli_ozet", "").strip()
            if not topic:
                bot.reply_to(message, "⚠️ Hangi konuyu sesli anlatayım?\nÖrnek: `/sesli_ozet Kurtuluş Savaşı`", parse_mode="Markdown")
                return
            
            wait_msg = bot.reply_to(message, f"🎧 **'{topic}'** için podcast hazırlanıyor... (Biraz sürebilir)")
            
            prompt = f"'{topic}' konusunu KPSS'ye hazırlanan bir öğrenci için samimi, akıcı bir radyo programcısı gibi anlat. Önemli yerleri vurgula. Metin çok uzun olmasın (yaklaşık 1-2 dakika okunacak kadar). Sadece okunacak metni ver."
            response = safe_generate_content(prompt)
            
            tts = gTTS(text=response.text, lang='tr')
            voice_data = io.BytesIO()
            tts.write_to_fp(voice_data)
            voice_data.seek(0)
            
            bot.delete_message(message.chat.id, wait_msg.message_id)
            bot.send_voice(message.chat.id, voice_data, caption=f"🎧 **PODCAST: {topic.upper()}**\n\n_Bot tarafından seslendirildi._")
        except Exception as e:
            bot.reply_to(message, f"Hata oluştu: {e}")

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

    @bot.message_handler(commands=['haftalik_plan'])
    def weekly_plan_menu(message):
        user_id = str(message.from_user.id)
        schedule = users[user_id].get("weekly_schedule", {})
        
        text = "📅 **HAFTALIK DERS PROGRAMIN**\n\n"
        if not any(schedule.values()):
            text += "_Henüz bir program oluşturmadın._\n\n"
        else:
            for day_idx in range(7):
                day_name_tr = DAY_NAMES[day_idx].lower()
                if day_name_tr in schedule and schedule[day_name_tr]:
                    text += f"🗓️ **{day_name_tr.title()}**\n"
                    sorted_entries = sorted(schedule[day_name_tr], key=lambda x: x['time'])
                    for entry in sorted_entries:
                        text += f"  - `{entry['time']}`: {entry['subject']}  (/program_sil {entry['id']})\n"
                    text += "\n"
        
        text += "🔹 **Ekle:** `/program_ekle <gün> <saat> <ders>`\n"
        text += "   _Örnek: /program_ekle Salı 10:30 Tarih_\n"
        text += "🔹 **Sil:** `/program_sil <ID>`"

        bot.reply_to(message, text, parse_mode="Markdown")

    @bot.message_handler(commands=['program_ekle'])
    def add_weekly_plan(message):
        user_id = str(message.from_user.id)
        try:
            args = message.text.split(maxsplit=3)
            if len(args) < 4:
                bot.reply_to(message, "⚠️ Kullanım: `/program_ekle <gün> <saat> <ders>`\nÖrnek: `/program_ekle Salı 10:30 Coğrafya`", parse_mode="Markdown")
                return
            
            day_input, time_input, subject_input = args[1].lower(), args[2], args[3]
            if day_input not in DAY_MAP:
                bot.reply_to(message, f"❌ Geçersiz gün: {args[1]}."); return
            datetime.strptime(time_input, "%H:%M")

            day_name = DAY_NAMES[DAY_MAP[day_input]].lower()
            
            schedule = users[user_id].setdefault("weekly_schedule", {})
            day_schedule = schedule.setdefault(day_name, [])
            
            if any(entry['time'] == time_input for entry in day_schedule):
                bot.reply_to(message, f"❌ Bu saatte ({time_input}) zaten bir dersin var."); return

            day_schedule.append({"id": str(uuid.uuid4())[:6], "time": time_input, "subject": subject_input})
            save_users()
            bot.reply_to(message, f"✅ Eklendi: **{day_name.title()} {time_input}** - {subject_input}\nProgramını görmek için: /haftalik_plan")
        except ValueError:
            bot.reply_to(message, "❌ Geçersiz saat formatı. Lütfen `SS:DD` formatında girin (Örn: 09:30, 14:00).")
        except Exception as e: bot.reply_to(message, f"Hata: {e}")

    @bot.message_handler(commands=['program_sil'])
    def delete_weekly_plan(message):
        user_id = str(message.from_user.id)
        try: entry_id_to_delete = message.text.split()[1]
        except IndexError: bot.reply_to(message, "⚠️ Kullanım: `/program_sil <ID>`\nID'yi görmek için `/haftalik_plan` yaz.", parse_mode="Markdown"); return

        schedule = users[user_id].get("weekly_schedule", {})
        for day, entries in schedule.items():
            for i, entry in enumerate(entries):
                if entry.get("id") == entry_id_to_delete:
                    deleted_entry = schedule[day].pop(i)
                    save_users(); bot.reply_to(message, f"🗑️ Silindi: **{deleted_entry['subject']}** ({deleted_entry['time']})"); return
        bot.reply_to(message, "❌ Bu ID'ye sahip bir program bulunamadı.")

    @bot.message_handler(commands=['calisma_arkadasi'])
    def study_buddy_init(message):
        user_id = str(message.from_user.id)
        if user_id in active_sessions:
            bot.reply_to(message, "⚠️ Zaten aktif bir çalışma arkadaşın var! Bitirmek için: `/arkadas_bitir`", parse_mode="Markdown")
            return
            
        markup = InlineKeyboardMarkup()
        subjects = ["Tarih", "Coğrafya", "Vatandaşlık", "Genel"]
        for sub in subjects:
            markup.add(InlineKeyboardButton(f"📚 {sub}", callback_data=f"buddy_join_{sub}"))
            
        bot.reply_to(message, "🤝 **ÇALIŞMA ARKADAŞI BUL**\n\nHangi dersten soru çözmek istersin? Seninle aynı dersi seçen biriyle eşleşeceksin ve 30 dakika boyunca skorlarınız yarışacak.", reply_markup=markup, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("buddy_join_"))
    def buddy_join_queue(call):
        user_id = str(call.from_user.id)
        subject = call.data.replace("buddy_join_", "")
        
        # Temizlik (Eski kuyruktan çıkar)
        for s in study_pool:
            if user_id in study_pool[s]:
                study_pool[s].remove(user_id)
        
        if subject not in study_pool: study_pool[subject] = []
        
        # Eşleşme Kontrolü
        if study_pool[subject]:
            partner_id = study_pool[subject].pop(0)
            if partner_id == user_id: # Kendisiyle eşleşmesin
                study_pool[subject].append(user_id)
                bot.answer_callback_query(call.id, "Sıraya alındın.")
                return

            # Eşleşme Başladı
            start_buddy_session(user_id, partner_id, subject, bot)
            try: bot.delete_message(call.message.chat.id, call.message.message_id)
            except: pass
        else:
            study_pool[subject].append(user_id)
            bot.edit_message_text(f"⏳ **{subject}** için arkadaş aranıyor...\nBekleme listesindesin.", call.message.chat.id, call.message.message_id, parse_mode="Markdown")

    @bot.message_handler(commands=['arkadas_bitir'])
    def stop_buddy_session_cmd(message):
        user_id = str(message.from_user.id)
        if user_id not in active_sessions:
            bot.reply_to(message, "⚠️ Aktif bir çalışma oturumun yok.")
            return
        end_buddy_session(user_id, bot, "Kullanıcı isteğiyle sonlandırıldı.")

def start_buddy_session(u1, u2, subject, bot):
    active_sessions[u1] = {"partner": u2, "score": 0, "subject": subject}
    active_sessions[u2] = {"partner": u1, "score": 0, "subject": subject}
    
    msg = f"🤝 **EŞLEŞME BAŞARILI!** ({subject})\n\n30 dakikalık çalışma maratonu başladı! Birbirinizin doğru sayılarını göreceksiniz.\nHadi soru çözmeye başla! 🚀\n`/quiz`"
    try: bot.send_message(u1, msg, parse_mode="Markdown")
    except: pass
    try: bot.send_message(u2, msg, parse_mode="Markdown")
    except: pass
    
    Timer(1800, lambda: end_buddy_session(u1, bot, "Süre doldu!")).start()

def end_buddy_session(user_id, bot, reason):
    if user_id not in active_sessions: return
    partner_id = active_sessions[user_id]["partner"]
    s1, s2 = active_sessions.get(user_id, {}).get("score", 0), active_sessions.get(partner_id, {}).get("score", 0)
    msg = f"🏁 **ÇALIŞMA OTURUMU BİTTİ**\nNeden: {reason}\n\n📊 **Skorlar:**\nSen: {s1} Doğru\nArkadaşın: {s2} Doğru\n\nTebrikler! 🎉"
    try: bot.send_message(user_id, msg); bot.send_message(partner_id, msg.replace(f"Sen: {s1}", f"Sen: {s2}").replace(f"Arkadaşın: {s2}", f"Arkadaşın: {s1}"))
    except: pass
    if user_id in active_sessions: del active_sessions[user_id]
    if partner_id in active_sessions: del active_sessions[partner_id]