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

from database import (
    users, save_users, QUIZ_QUESTIONS, DEVELOPER_USERNAME,
    user_timers, pending_duels
)

# Bu fonksiyonlar tirtil.py'den register fonksiyonu aracılığıyla alınacak
get_rank = None
check_daily_limit = None
update_quest_progress = None
safe_generate_content = None

def create_quiz_image(question, options, category, level, lives):
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
        bg_color, header_text_color = (35, 39, 42), (255, 215, 0)

    card_color = (44, 47, 51)
    img = Image.new('RGB', (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)
    
    try:
        font_path = "arial.ttf"
        if not os.path.exists(font_path):
            candidates = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/System/Library/Fonts/Helvetica.ttc"]
            font_path = next((f for f in candidates if os.path.exists(f)), font_path)
        header_font, question_font, option_font = ImageFont.truetype(font_path, 28), ImageFont.truetype(font_path, 32), ImageFont.truetype(font_path, 24)
    except:
        header_font, question_font, option_font = ImageFont.load_default(), ImageFont.load_default(), ImageFont.load_default()

    draw.rectangle([(0, 0), (width, 80)], fill=(30, 33, 36))
    draw.text((40, 25), f"🧠 {category.upper()}  |  LEVEL {level}  |  ❤️ {lives}", font=header_font, fill=header_text_color)
    draw.rectangle([(40, 100), (760, 300)], fill=card_color)
    
    wrapper = textwrap.TextWrapper(width=40) 
    lines = wrapper.wrap(text=question)
    y_text = 130
    for line in lines:
        draw.text((60, y_text), line, font=question_font, fill=(255, 255, 255))
        y_text += 40

    y_opt = 330
    for opt in options:
        draw.rectangle([(40, y_opt), (760, y_opt + 50)], fill=card_color)
        draw.text((60, y_opt + 10), opt, font=option_font, fill=(200, 200, 200))
        y_opt += 65

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

    def question_timeout(chat_id, user_id):
        evaluate_quiz_answer(chat_id, user_id, "TIMEOUT", bot)

    def send_question(chat_id, user_id):
        level, category = users[user_id]["level"], users[user_id]["category"]
        q = get_question(level, category)
        if not q:
            bot.send_message(chat_id, "❌ Bu kategoride soru kalmadı knk"); return

        users[user_id].update({"current_answer": q["answer"], "current_question_id": q["id"]})
        mode_prefix = f"🏃‍♂️ **MARATON: {users[user_id].get('marathon_score', 0) + 1}. SORU**\n" if users[user_id].get("mode") == "marathon" else ""
        photo = create_quiz_image(q['question'], q['options'], category, level, users[user_id]['lives'])
        caption = f"{mode_prefix}👇 Doğru şıkkı seç! (⏳ 30 sn)"

        markup = InlineKeyboardMarkup(row_width=4)
        markup.add(*[InlineKeyboardButton(s, callback_data=f"ans_{s}") for s in ["A", "B", "C", "D"]])
        
        joker_btns = []
        inv = users[user_id].get("inventory", {})
        if inv.get("joker_50", 0) > 0: joker_btns.append(InlineKeyboardButton(f"💡 %50 ({inv['joker_50']})", callback_data="joker_50"))
        if inv.get("joker_pass", 0) > 0: joker_btns.append(InlineKeyboardButton(f"⏭ Pas ({inv['joker_pass']})", callback_data="joker_pass"))
        if inv.get("joker_audience", 0) > 0: joker_btns.append(InlineKeyboardButton(f"👥 Seyirci ({inv['joker_audience']})", callback_data="joker_audience"))
        if inv.get("joker_ai", 0) > 0: joker_btns.append(InlineKeyboardButton(f"🤖 AI İpucu ({inv['joker_ai']})", callback_data="joker_ai"))
        if joker_btns: markup.add(*joker_btns)

        if user_id in user_timers: user_timers[user_id].cancel()
        msg = bot.send_photo(chat_id, photo, caption=caption, reply_markup=markup)
        users[user_id]["last_question_message_id"] = msg.message_id
        
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
        photo = create_quiz_image(q['question'], q['options'], q['category'], users[user_id]["level"], users[user_id]['lives'])
        markup = InlineKeyboardMarkup(row_width=4).add(*[InlineKeyboardButton(s, callback_data=f"ans_{s}") for s in ["A", "B", "C", "D"]])

        if user_id in user_timers: user_timers[user_id].cancel()
        msg = bot.send_photo(chat_id, photo, caption="🔄 **Tekrar Zamanı!** (⏳ 30 sn)", reply_markup=markup)
        users[user_id]["last_question_message_id"] = msg.message_id
        
        user_timers[user_id] = Timer(30.0, question_timeout, args=[chat_id, user_id]); user_timers[user_id].start()
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
        question_data = next((q for q in QUIZ_QUESTIONS if q["id"] == q_id), None)

        try:
            if message_id_to_delete: bot.delete_message(chat_id, message_id_to_delete)
            if "last_question_message_id" in users[user_id]: bot.delete_message(chat_id, users[user_id]["last_question_message_id"])
        except: pass

        correct = users[user_id]["current_answer"]
        u = users[user_id]
        level, exp, streak, bet_amount = u["level"], u["exp"], u.get("streak", 0), u.get("active_bet", 0)

        correct_msgs = ["✅ **Harikasın!**", "🔥 **Alev aldı buralar!**", "🧠 **Zeka küpü!**", "🎯 **Tam isabet!**"]
        wrong_msgs = ["❌ **Ah be! Yanlış oldu.**", "🐢 **Biraz daha dikkat!**", "🤔 **Mantıklıydı ama...**", "💥 **Patladık!**"]

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
            cat = question_data.get("category", "Genel"); u.setdefault("cat_stats", {})[cat] = u.get("cat_stats", {}).get(cat, 0) + 1
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
        else:
            if u.get("inventory", {}).get("streak_saver", 0) > 0:
                u["inventory"]["streak_saver"] -= 1; streak_saved = True
            else:
                streak = 0; streak_saved = False
            
            if u.get("mode") == "local": u.setdefault("wrong_answers", []).append(q_id)
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
            bot.send_message(chat_id, f"{result}\n\n💀 **OYUN BİTTİ!** 💀\nCanların tükendi.\n\n🔄 /quiz ile tekrar başla!")
            u["lives"] = 3; u.pop("current_answer", None); save_users(); return

        result_photo = create_quiz_result_image(answer == correct, correct, earned_exp_display, streak, answer)
        msg = bot.send_photo(chat_id, result_photo, caption=f"{result}\n\n📊 Level: {level} | ⭐️ EXP: {exp}/{level*100}")
        Timer(5.0, lambda: bot.delete_message(chat_id, msg.message_id) if msg else None).start()

        u.pop("current_answer", None); save_users()
        
        if u.get("mode") == "global": send_global_question(chat_id, user_id)
        elif u.get("mode") == "retry": send_wrong_question(chat_id, user_id)
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
            
            if user_id in user_timers: user_timers[user_id].cancel()
            bot.delete_message(chat_id, wait_msg.message_id)
            msg = bot.send_photo(chat_id, photo, caption=f"🌍 **Global Quiz** | {item['category']} (⏳ 30 sn)", reply_markup=markup)
            users[user_id]["last_question_message_id"] = msg.message_id
            user_timers[user_id] = Timer(30.0, question_timeout, args=[chat_id, user_id]); user_timers[user_id].start()
            save_users()
        except Exception as e:
            bot.edit_message_text(f"Hata: {str(e)}", chat_id, wait_msg.message_id)

    @bot.message_handler(commands=['quiz'])
    def quiz(message):
        if not users.get(str(message.from_user.id), {}).get("is_approved", True):
            bot.reply_to(message, "⛔ Onay bekleniyor."); return
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("📜 Tarih", callback_data="submenu_tarih"), InlineKeyboardButton("🌍 Coğrafya", callback_data="submenu_cografya"))
        kb.add(InlineKeyboardButton("⚖️ Vatandaşlık", callback_data="submenu_vatandaslik"), InlineKeyboardButton("📰 Güncel", callback_data="cat_guncel"))
        kb.add(InlineKeyboardButton(" Karışık", callback_data="cat_karisik"))

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
        kb.add(InlineKeyboardButton("⚖️ Vatandaşlık", callback_data="submenu_vatandaslik"), InlineKeyboardButton("📰 Güncel", callback_data="cat_guncel"))
        kb.add(InlineKeyboardButton("� Güncel", callback_data="cat_guncel"), InlineKeyboardButton("🔀 Karışık", callback_data="cat_karisik"))
        
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
        stats = {}
        for q in QUIZ_QUESTIONS:
            cat = q["category"].capitalize()
            stats[cat] = stats.get(cat, 0) + 1
        text = f"📊 **SORU BANKASI**\n🗂 Toplam: {len(QUIZ_QUESTIONS)}\n" + "\n".join([f"🔹 {k}: {v}" for k, v in stats.items()])
        bot.reply_to(message, text)
