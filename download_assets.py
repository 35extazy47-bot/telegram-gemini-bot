import os
import random
from PIL import Image, ImageDraw, ImageFont

def download_kpss_images():
    # 1. Klasörü oluştur
    if not os.path.exists("images"):
        os.makedirs("images")
        print("✅ 'images' klasörü oluşturuldu.")

    # 2. İndirilecek resimlerin listesi
    # Harita oluşturma verileri (Eğer indirme başarısız olursa)
    map_metadata = {
        "tr_nufus.jpg": {
            "label": "NÜFUS YOĞUNLUĞU", "marker": (150, 130), "info": "İstanbul-Kocaeli Çevresi", 
            "type": "circle", "color": (56, 189, 248),
            "bg_color": (15, 23, 42), "land_color": (30, 41, 59) # Modern Koyu Mavi
        },
        "tr_delta.jpg": {
            "label": "DELTA OVALARI", "marker": (550, 400), "info": "Çukurova Bölgesi", 
            "type": "circle", "color": (34, 197, 94),
            "bg_color": (10, 20, 15), "land_color": (20, 45, 30) # Doğa Yeşili
        },
        "tr_demir.jpg": {
            "label": "DEMİR MADENİ", "marker": (600, 220), "info": "Sivas-Divriği Çevresi", 
            "type": "square", "color": (249, 115, 22),
            "bg_color": (25, 15, 15), "land_color": (55, 35, 30) # Pas/Metal Tonu
        },
        "tr_bor.jpg": {
            "label": "BOR REZERVLERİ", "marker": (180, 200), "info": "Güney Marmara-Eskişehir", 
            "type": "square", "color": (234, 179, 8),
            "bg_color": (20, 20, 30), "land_color": (40, 40, 65) # Kristal Moru
        },
        "tr_petrol.jpg": {
            "label": "PETROL YATAKLARI", "marker": (720, 350), "info": "Batman ve Çevresi", 
            "type": "diamond", "color": (71, 85, 105),
            "bg_color": (10, 10, 10), "land_color": (35, 35, 35) # Endüstriyel Siyah/Gri
        },
        "tr_iklim.jpg": {
            "label": "KARADENİZ İKLİMİ", "marker": (500, 100), "info": "Kıyı Şeridi Taranmış", 
            "type": "circle", "color": (239, 68, 68),
            "bg_color": (15, 25, 35), "land_color": (65, 55, 45) # Toprak Tonları
        }
    }

    def create_fallback_map(name, path):
        """İndirme başarısız olursa manuel harita taslağı oluşturur."""
        data = map_metadata.get(name, {
            "label": "COĞRAFYA HARİTASI", 
            "marker": (400, 300), 
            "info": "",
            "bg_color": (15, 23, 42),
            "land_color": (30, 41, 59)
        })
        
        bg_color = data.get("bg_color", (15, 23, 42))
        land_color = data.get("land_color", (30, 41, 59))
        neighbor_land_color = tuple(max(0, c - 5) for c in bg_color) # Komşu ülkeler için hafif ton
        grid_color = tuple(max(0, c - 10) for c in bg_color)
        outline_color = tuple(min(255, c + 40) for c in land_color)

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

        def draw_text_w_shadow(pos, text, font, fill, shadow=(0,0,0,200)):
            """Yazılara derinlik katar."""
            draw.text((pos[0]+1, pos[1]+1), text, font=font, fill=shadow)
            draw.text(pos, text, font=font, fill=fill)

        # Referans Şehirler (x, y)
        ref_cities = {
            "İstanbul": (140, 135), "Ankara": (380, 230), "İzmir": (75, 280),
            "Antalya": (300, 400), "Adana": (520, 380), "Diyarbakır": (700, 350),
            "Erzurum": (700, 220), "Samsun": (480, 110)
        }

        # Akarsu Hatları (Basitleştirilmiş)
        rivers = [
            [(720, 200), (650, 300), (600, 380)], # Fırat
            [(600, 250), (450, 300), (350, 220), (480, 100)], # Kızılırmak
            [(150, 150), (250, 200), (300, 300)] # Sakarya
        ]

        # 2.7 Göller (x, y, rx, ry)
        lakes = {
            "Van Gölü": (730, 260, 25, 15),
            "Tuz Gölü": (380, 280, 20, 20)
        }

        # 2.8 Dağlar (x, y)
        mountains = {
            "Ağrı Dağı": (770, 170),
            "Erciyes": (480, 300),
            "Uludağ": (160, 160)
        }

        # 1. Koordinat Izgarası (Grid)
        for x in range(0, 800, 50): draw.line([(x, 0), (x, 500)], fill=grid_color, width=1)
        for y in range(0, 500, 50): draw.line([(0, y), (800, y)], fill=grid_color, width=1)

        # 1.5 Komşu Kara Parçaları (Silüet)
        draw.rectangle([0, 0, 120, 150], fill=neighbor_land_color) # Balkanlar
        draw.rectangle([650, 0, 800, 150], fill=neighbor_land_color) # Kafkaslar
        draw.rectangle([750, 150, 800, 500], fill=neighbor_land_color) # İran hattı
        draw.rectangle([0, 450, 800, 500], fill=neighbor_land_color) # Afrika/Arap Yarımadası girişi

        # 2. Geliştirilmiş Türkiye Sınırları (Detaylandırıldı)
        turkey_outline = [
            (50, 150), (80, 130), (120, 120), (150, 135), (180, 110), (220, 115), 
            (300, 105), (450, 85), (480, 105), (550, 90), (650, 100), (750, 115), 
            (785, 180), (795, 280), (770, 360), (720, 390), (650, 405), (580, 410), 
            (545, 440), (530, 475), (510, 450), (450, 420), (380, 435), (300, 450), 
            (220, 430), (180, 445), (120, 435), (80, 400), (60, 360), (85, 330), 
            (55, 300), (80, 270), (50, 240), (90, 210), (65, 180)
        ]
        
        # Kara parçasını doldur ve sınırı çiz
        draw.polygon(turkey_outline, fill=land_color, outline=outline_color, width=3)

        # 2.5 Nehirleri Çiz
        for river in rivers:
            draw.line(river, fill=(100, 149, 237, 180), width=2)

        # 2.6 Şehirleri Ekle
        for city, pos in ref_cities.items():
            draw.ellipse([pos[0]-2, pos[1]-2, pos[0]+2, pos[1]+2], fill=(255, 255, 255, 150))

        # 2.7 Gölleri Çiz ve İsimlendir
        for name, (lx, ly, rx, ry) in lakes.items():
            draw.ellipse([lx-rx, ly-ry, lx+rx, ly+ry], fill=(100, 149, 237))
            draw.text((lx - 25, ly + ry + 2), name, font=small_font, fill=(100, 116, 139))

        # 2.8 Dağları Çiz (Üçgen) ve İsimlendir
        for name, (mx, my) in mountains.items():
            # Dağ ikonu (Gri Üçgen)
            draw.polygon([(mx, my-8), (mx-6, my+4), (mx+6, my+4)], fill=(148, 163, 184))
            draw.text((mx + 8, my - 8), name, font=small_font, fill=(100, 116, 139))

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
        draw.line([(750, 430), (750, 470)], fill=neighbor_color, width=2) # N-S
        draw.line([(730, 450), (770, 450)], fill=neighbor_color, width=2) # E-W
        draw.text((745, 415), "K", font=small_font, fill=neighbor_color)

        # 4. Dinamik İşaretçi Çizimi
        m_type = data.get("type", "circle")
        m_color = data.get("color", (239, 68, 68))
        mx, my = data["marker"]

        if m_type == "circle":
            draw.ellipse([mx-12, my-12, mx+12, my+12], fill=m_color, outline=(255, 255, 255), width=2)
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
