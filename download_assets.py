import os
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

def download_kpss_images():
    # Kalibrasyon yapmak istersen burayı True yap knk, resimlerin üstüne koordinat yazar
    DEBUG_MODE = True

    # 1. Klasörü oluştur
    if not os.path.exists("images"):
        os.makedirs("images")
        print("✅ 'images' klasörü oluşturuldu.")

    # 2. İndirilecek resimlerin listesi
    # Harita oluşturma verileri (Eğer indirme başarısız olursa)
    map_metadata = {
        "tr_nufus.jpg": {
            "label": "NÜFUS YOĞUNLUĞU", "marker": (160, 130), "info": "İstanbul-Kocaeli Çevresi", 
            "type": "circle", "color": (56, 189, 248),
            "bg_color": (15, 23, 42)
        },
        "tr_delta.jpg": {
            "label": "DELTA OVALARI", "marker": (430, 380), "info": "Çukurova Bölgesi", 
            "type": "circle", "color": (34, 197, 94),
            "bg_color": (10, 20, 15)
        },
        "tr_demir.jpg": {
            "label": "DEMİR MADENİ", "marker": (585, 215), "info": "Sivas-Divriği Çevresi", 
            "type": "square", "color": (249, 115, 22),
            "bg_color": (25, 15, 15)
        },
        "tr_bor.jpg": {
            "label": "BOR REZERVLERİ", "marker": (150, 180), "info": "Güney Marmara-Eskişehir", 
            "type": "square", "color": (234, 179, 8),
            "bg_color": (20, 20, 30)
        },
        "tr_petrol.jpg": {
            "label": "PETROL YATAKLARI", "marker": (650, 300), "info": "Batman ve Çevresi", 
            "type": "diamond", "color": (71, 85, 105),
            "bg_color": (10, 10, 10)
        },
        "tr_iklim.jpg": {
            "label": "KARADENİZ İKLİMİ", "marker": (400, 100), "info": "Kıyı Şeridi Taranmış", 
            "type": "circle", "color": (239, 68, 68),
            "bg_color": (15, 25, 35)
        }
    }

    def create_fallback_map(name, path):
        """İndirme başarısız olursa manuel harita taslağı oluşturur."""
        data = map_metadata.get(name, {
            "label": "COĞRAFYA HARİTASI", 
            "marker": (400, 300), 
            "info": "",
            "bg_color": (15, 23, 42),
        })
        
        bg_color = data.get("bg_color", (15, 23, 42))
        neighbor_land_color = tuple(max(0, c - 5) for c in bg_color) # Komşu ülkeler için hafif ton
        grid_color = tuple(max(0, c - 10) for c in bg_color)
        
        # 0. Arkaplan Görseli Kontrolü (Senin yükleyeceğin harita)
        base_img_path = os.path.join("images", "tr_base_blank.png")
        use_base_img = os.path.exists(base_img_path)

        if use_base_img:
            # Senin haritanı yükle ve sistem boyutuna (800x500) getir
            img = Image.open(base_img_path).convert('RGB').resize((800, 500))
        else:
            img = Image.new('RGB', (800, 500), color=bg_color) 
        
        draw = ImageDraw.Draw(img)

        # Fontları Yükle (Netlik için kritik)
        try:
            font_path = "arial.ttf"
            if not os.path.exists(font_path): font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            title_font = ImageFont.truetype(font_path, 26)
            label_font = ImageFont.truetype(font_path, 18)
            small_font = ImageFont.truetype(font_path, 14)
        except:
            title_font = label_font = small_font = ImageFont.load_default()

        # Eğer arkaplan görseli yoksa (fallback), kendi haritamızı çizelim
        if not use_base_img:
            # 1. Izgara (Grid)
            for x in range(0, 800, 50): draw.line([(x, 0), (x, 500)], fill=grid_color, width=1)
            for y in range(0, 500, 50): draw.line([(0, y), (800, y)], fill=grid_color, width=1)

            # 2. Türkiye Sınırları
            turkey_outline = [
                (50, 150), (60, 140), (80, 130), (100, 125), (125, 120), (150, 135), (165, 125), (180, 110), 
                (200, 112), (220, 115), (250, 118), (300, 105), (350, 100), (400, 95), (450, 85), (480, 105), 
                (520, 100), (550, 90), (600, 95), (650, 100), (700, 105), (750, 115), (770, 130), (785, 180), 
                (795, 230), (795, 280), (785, 330), (770, 360), (740, 380), (720, 390), (680, 400), (650, 405), 
                (620, 408), (580, 410), (560, 425), (545, 440), (535, 460), (530, 475), (520, 465), (510, 450), 
                (480, 435), (450, 420), (420, 425), (380, 435), (340, 445), (300, 450), (260, 440), (220, 430), 
                (200, 435), (180, 445), (150, 445), (120, 435), (100, 420), (80, 400), (70, 380), (60, 360), 
                (75, 345), (85, 330), (70, 315), (55, 300), (65, 285), (80, 270), (65, 255), (50, 240), (70, 225), 
                (90, 210), (75, 195), (65, 180), (55, 165)
            ]

            # 1.5 Gölge Efekti (3D Relief)
            shadow_img = Image.new('RGBA', (800, 500), (0, 0, 0, 0))
            shadow_draw = ImageDraw.Draw(shadow_img)
            shadow_outline = [(x+4, y+4) for x, y in turkey_outline]
            shadow_draw.polygon(shadow_outline, fill=(0, 0, 0, 120))
            shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(radius=5))
            img.paste(shadow_img, (0, 0), shadow_img)

            # 3. Fiziki Renklendirme
            mask = Image.new('L', (800, 500), 0)
            mask_draw = ImageDraw.Draw(mask); mask_draw.polygon(turkey_outline, fill=255)
            for x in range(800):
                if x < 300: r, g, b = int(45 + 150*(x/300)), int(120 + 50*(x/300)), 45
                elif x < 600: r, g, b = int(195 + 20*((x-300)/300)), int(170 - 50*((x-300)/300)), 45
                else: r, g, b = int(215 - 100*((x-600)/200)), int(120 - 60*((x-600)/200)), int(45 - 20*((x-600)/200))
                for y in range(500):
                    if mask.getpixel((x, y)) == 255: img.putpixel((x, y), (r, g, b))
            draw.polygon(turkey_outline, outline=(255, 255, 255, 100), width=2)

        # Her iki durumda da hafif doku ekle
        noise = np.random.randint(-10, 10, (500, 800, 3), dtype='int16')
        img_np = np.array(img).astype('int16')
        img_np = np.clip(img_np + noise, 0, 255).astype('uint8')
        img = Image.fromarray(img_np)
        draw = ImageDraw.Draw(img)

        def draw_text_w_shadow(pos, text, font, fill, shadow=(0,0,0,200)):
            """Yazılara derinlik katar."""
            draw.text((pos[0]+1, pos[1]+1), text, font=font, fill=shadow)
            draw.text(pos, text, font=font, fill=fill)

        # Referans Şehirler (x, y)
        ref_cities = {
            "İstanbul": (130, 110), "Ankara": (360, 185), "İzmir": (65, 260),
            "Antalya": (290, 370), "Adana": (510, 350), "Diyarbakır": (685, 315),
            "Erzurum": (705, 180), "Samsun": (475, 100)
        }

        # 0.5 Kalibrasyon Izgarası (Sadece DEBUG_MODE açıksa)
        if DEBUG_MODE:
            for x in range(0, 800, 50):
                draw.line([(x, 0), (x, 500)], fill=(200, 0, 0, 100), width=1)
                draw.text((x, 5), str(x), font=small_font, fill=(200, 0, 0))
            for y in range(0, 500, 50):
                draw.line([(0, y), (800, y)], fill=(200, 0, 0, 100), width=1)
                draw.text((5, y), str(y), font=small_font, fill=(200, 0, 0))

        # Eğer gerçek harita kullanıyorsak manuel detayları (nehir, göl, dağ) çizmiyoruz.
        # Sadece fallback (kodla çizim) durumunda bunlar gözükebilir.
        if not use_base_img:
            for city, pos in ref_cities.items():
                draw.ellipse([pos[0]-2, pos[1]-2, pos[0]+2, pos[1]+2], fill=(255, 255, 255, 150))
            # Buraya istersen diğer fallback detaylarını da (dağ, göl vb.) if içine alabiliriz.
            # Ancak şimdilik senin isteğin üzerine nehirleri tamamen sildim.

        # 3. Başlık
        draw_text_w_shadow((320, 20), data["label"], title_font, (250, 204, 21))
        
        # Deniz İsimleri (Daha net ve açık renk)
        sea_color = (148, 163, 184)
        draw.text((350, 45), "KARADENİZ", fill=sea_color, font=label_font)
        draw.text((350, 465), "AKDENİZ", fill=sea_color, font=label_font)
        draw.text((10, 250), "EGE", fill=sea_color, font=label_font)

        # 3.5 Komşu Ülkeler (Netleştirildi)
        neighbor_color = (90, 100, 120)
        draw.text((25, 85), "BULGARİSTAN", fill=neighbor_color, font=small_font)
        draw.text((10, 320), "YUNANİSTAN", fill=neighbor_color, font=small_font)
        draw.text((680, 65), "GÜRCİSTAN", fill=neighbor_color, font=small_font)
        draw.text((710, 145), "ERMENİSTAN", fill=neighbor_color, font=small_font)
        draw.text((745, 285), "İRAN", fill=neighbor_color, font=small_font)
        draw.text((650, 445), "IRAK", fill=neighbor_color, font=small_font)
        draw.text((250, 465), "SURİYE", fill=neighbor_color, font=small_font)

        # 3.6 Pusula (Compass Rose) - Sağ Alt
        draw.line([(760, 430), (760, 470)], fill=neighbor_color, width=2) # N-S
        draw.line([(740, 450), (780, 450)], fill=neighbor_color, width=2) # E-W
        draw.text((755, 415), "K", font=small_font, fill=neighbor_color)

        # 4. Profesyonel Modern İşaretçi (Marker) Çizimi
        m_type = data.get("type", "circle")
        m_color = data.get("color", (239, 68, 68))
        mx, my = data["marker"]

        # Marker Gölgesi
        draw.ellipse([mx-14, my-14, mx+14, my+14], fill=(0, 0, 0, 80))

        if m_type == "circle":
            # Parlama efekti olan bir daire
            draw.ellipse([mx-12, my-12, mx+12, my+12], fill=m_color, outline=(255, 255, 255), width=3)
            # İç nokta
            draw.ellipse([mx-4, my-4, mx+4, my+4], fill=(255, 255, 255))
            # Pulse (Hafif dış halka)
            draw.ellipse([mx-20, my-20, mx+20, my+20], outline=m_color + (100,), width=1)
        elif m_type == "square":
            draw.rectangle([mx-12, my-12, mx+12, my+12], fill=m_color, outline=(255, 255, 255), width=2)
        elif m_type == "diamond":
            draw.polygon([(mx, my-15), (mx+15, my), (mx, my+15), (mx-15, my)], fill=m_color, outline=(255, 255, 255), width=2)

        draw_text_w_shadow((mx+20, my-10), f"📍 {data['info']}", label_font, (255, 255, 255))
        img.save(path)
        print(f"🎨 {name} üretildi.")

    print("🚀 Harita üretim süreci başlıyor...")
    for filename in map_metadata.keys():
        create_fallback_map(filename, os.path.join("images", filename))
    print("\n✨ TÜM HARİTALAR HAZIR! 🚀")

if __name__ == "__main__":
    download_kpss_images()
