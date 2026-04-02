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
        "tr_nufus.jpg": {"label": "NÜFUS YOĞUNLUĞU", "marker": (150, 130), "info": "İstanbul-Kocaeli Çevresi"},
        "tr_delta.jpg": {"label": "DELTA OVALARI", "marker": (550, 400), "info": "Çukurova Bölgesi"},
        "tr_demir.jpg": {"label": "DEMİR MADENİ", "marker": (600, 220), "info": "Sivas-Divriği Çevresi"},
        "tr_bor.jpg": {"label": "BOR REZERVLERİ", "marker": (180, 200), "info": "Güney Marmara-Eskişehir"},
        "tr_petrol.jpg": {"label": "PETROL YATAKLARI", "marker": (720, 350), "info": "Batman ve Çevresi"},
        "tr_iklim.jpg": {"label": "KARADENİZ İKLİMİ", "marker": (500, 100), "info": "Kıyı Şeridi Taranmış"}
    }

    def create_fallback_map(name, path):
        """İndirme başarısız olursa manuel harita taslağı oluşturur."""
        data = map_metadata.get(name, {"label": "COĞRAFYA HARİTASI", "marker": (400, 300), "info": ""})
        img = Image.new('RGB', (800, 500), color=(15, 23, 42)) 
        draw = ImageDraw.Draw(img)

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

        # 1. Koordinat Izgarası (Grid)
        for x in range(0, 800, 50): draw.line([(x, 0), (x, 500)], fill=(22, 30, 46), width=1)
        for y in range(0, 500, 50): draw.line([(0, y), (800, y)], fill=(22, 30, 46), width=1)

        # 2. Basitleştirilmiş Türkiye Formu (Sınırlar)
        turkey_outline = [
            (50, 180), (80, 140), (130, 110), (180, 105), (250, 120), (320, 100),
            (450, 80), (600, 100), (750, 120), (780, 200), (790, 280), (760, 350),
            (700, 400), (600, 420), (500, 450), (400, 430), (300, 440), (200, 450),
            (100, 420), (60, 350), (45, 280)
        ]
        
        # Kara parçasını doldur ve sınırı çiz
        draw.polygon(turkey_outline, fill=(30, 41, 59), outline=(51, 65, 85), width=2)

        # 2.5 Nehirleri Çiz
        for river in rivers:
            draw.line(river, fill=(100, 149, 237), width=2)

        # 2.6 Şehirleri Ekle
        for city, pos in ref_cities.items():
            draw.ellipse([pos[0]-2, pos[1]-2, pos[0]+2, pos[1]+2], fill=(200, 200, 200))

        # 3. Başlık
        draw.text((320, 20), data["label"], fill=(250, 204, 21))
        
        # Deniz İsimleri
        draw.text((350, 40), "KARADENİZ", fill=(51, 65, 85))
        draw.text((350, 460), "AKDENİZ", fill=(51, 65, 85))
        draw.text((15, 250), "EGE", fill=(51, 65, 85))

        # İşaretçi çiz (Kırmızı Daire)
        mx, my = data["marker"]
        draw.ellipse([mx-12, my-12, mx+12, my+12], fill=(239, 68, 68), outline=(255, 255, 255), width=2)
        draw.text((mx+20, my-10), f"📍 {data['info']}", fill=(255, 255, 255))
        img.save(path)
        print(f"🎨 {name} üretildi.")

    print("🚀 Harita üretim süreci başlıyor...")
    for filename in map_metadata.keys():
        create_fallback_map(filename, os.path.join("images", filename))
    print("\n✨ TÜM HARİTALAR HAZIR! 🚀")

if __name__ == "__main__":
    download_kpss_images()
