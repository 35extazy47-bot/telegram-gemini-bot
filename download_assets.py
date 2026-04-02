import os
import requests
import time
import random
import urllib3
from PIL import Image, ImageDraw, ImageFont

# SSL uyarılarını kapatıyoruz
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def download_kpss_images():
    # 1. Klasörü oluştur
    if not os.path.exists("images"):
        os.makedirs("images")
        print("✅ 'images' klasörü oluşturuldu.")

    # 2. İndirilecek resimlerin listesi
    images_to_download = {
        "tr_nufus.jpg": [
            "https://upload.wikimedia.org/wikipedia/commons/thumb/2/23/Turkey_population_density_map.png/800px-Turkey_population_density_map.png",
            "https://i.postimg.cc/vH8XmXzX/tr-nufus.jpg"
        ],
        "tr_delta.jpg": [
            "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d1/Adana_in_Turkey.svg/800px-Adana_in_Turkey.svg.png"
        ],
        "tr_demir.jpg": [
            "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b2/Turkey_location_map.svg/800px-Turkey_location_map.svg.png"
        ],
        "tr_bor.jpg": [
            "https://i.postimg.cc/pL9P9P9/tr-bor.jpg"
        ],
        "tr_petrol.jpg": [
            "https://i.postimg.cc/rF8R8R8/tr-petrol.jpg"
        ]
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "Referer": "https://www.google.com/",
    }

    # Harita oluşturma verileri (Eğer indirme başarısız olursa)
    map_metadata = {
        "tr_nufus.jpg": {"label": "NÜFUS YOĞUNLUĞU", "marker": (150, 150), "info": "İstanbul-Kocaeli Çevresi"},
        "tr_delta.jpg": {"label": "DELTA OVALARI", "marker": (550, 480), "info": "Çukurova Bölgesi"},
        "tr_demir.jpg": {"label": "DEMİR MADENİ", "marker": (650, 250), "info": "Sivas-Divriği Çevresi"},
        "tr_bor.jpg": {"label": "BOR REZERVLERİ", "marker": (200, 280), "info": "Güney Marmara-Eskişehir"},
        "tr_petrol.jpg": {"label": "PETROL YATAKLARI", "marker": (750, 400), "info": "Batman ve Çevresi"},
        "tr_iklim.jpg": {"label": "KARADENİZ İKLİMİ", "marker": (500, 80), "info": "Kıyı Şeridi Taranmış"}
    }

    def create_fallback_map(name, path):
        """İndirme başarısız olursa manuel harita taslağı oluşturur."""
        data = map_metadata.get(name, {"label": "COĞRAFYA HARİTASI", "marker": (400, 300), "info": ""})
        img = Image.new('RGB', (800, 500), color=(30, 41, 59))
        draw = ImageDraw.Draw(img)
        draw.rectangle([20, 20, 780, 480], outline=(51, 65, 85), width=5)
        draw.text((300, 30), data["label"], fill=(250, 204, 21))
        # İşaretçi çiz (Kırmızı Daire)
        mx, my = data["marker"]
        draw.ellipse([mx-20, my-20, mx+20, my+20], fill=(239, 68, 68), outline=(255, 255, 255))
        draw.text((mx+30, my), f"<< İŞARETLİ ALAN: {data['info']}", fill=(255, 255, 255))
        img.save(path)
        print(f"🎨 {name} için özel harita taslağı OLUŞTURULDU (Fallback).")

    print("🚀 İşlem başlıyor. Önce indirme denenecek, olmazsa haritalar üretilecek...")
    success_count = 0

    for filename, urls in images_to_download.items():
        filepath = os.path.join("images", filename)
        
        if os.path.exists(filepath):
            print(f"⏩ {filename} zaten mevcut, geçiliyor.")
            success_count += 1
            continue

        downloaded = False
        for url_index, url in enumerate(urls):
            if downloaded: break
            
            max_retries = 2
            for attempt in range(max_retries):
                try:
                    source_label = f"Kaynak {url_index + 1}"
                    print(f"📥 {filename} indiriliyor ({source_label}, Deneme {attempt + 1})...")
                    response = requests.get(url, headers=headers, timeout=20, verify=False)
                    
                    if response.status_code == 200:
                        with open(filepath, "wb") as f:
                            f.write(response.content)
                        print(f"✅ {filename} başarıyla indirildi ({source_label}).")
                        success_count += 1
                        downloaded = True
                        time.sleep(random.uniform(2, 4)) # Rastgele bekleme (İnsansı hareket)
                        break
                    elif response.status_code == 429:
                        wait_time = (attempt + 1) * 15
                        print(f"⚠️ HTTP 429: Hız sınırı. {wait_time} saniye bekleniyor...")
                        time.sleep(wait_time)
                    else:
                        print(f"❌ {filename} indirilemedi (HTTP {response.status_code} - {source_label})")
                        break # Bu URL çalışmıyor, bir sonraki URL'e geçmek için döngüyü kır
                except Exception as e:
                    print(f"❌ Hata ({filename} - {source_label}): {e}")
                    time.sleep(2)
        
        if not downloaded:
            create_fallback_map(filename, filepath)
            success_count += 1

    print(f"\n✨ HARİTA OPERASYONU TAMAMLANDI!")
    print(f"✅ Hazır Durumdaki Harita Sayısı: {success_count}")
    print("Artık botu yerel görsellerle uçurabilirsin! 🚀")

if __name__ == "__main__":
    download_kpss_images()
