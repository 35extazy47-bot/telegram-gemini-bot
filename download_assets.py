import os
import requests
import time
import random
import urllib3

# SSL uyarılarını kapatıyoruz
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def download_kpss_images():
    # 1. Klasörü oluştur
    if not os.path.exists("images"):
        os.makedirs("images")
        print("✅ 'images' klasörü oluşturuldu.")

    # 2. İndirilecek resimlerin listesi
    # Her görsel için bir liste oluşturduk. İlki başarısız olursa sonrakini deneyecek.
    images_to_download = {
        "agri_dagi.jpg": [
            "https://raw.githubusercontent.com/huseyinacar/assets/main/kpss/agri_dagi.jpg",
            "https://upload.wikimedia.org/wikipedia/commons/thumb/6/60/Mount_Ararat_and_the_Ararat_Plain.jpg/640px-Mount_Ararat_and_the_Ararat_Plain.jpg",
        ],
        "van_golu.jpg": [
            "https://www.kulturportali.gov.tr/contents/images/20170324151245656_Van%20Golu.jpg",
            "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d9/Lake_Van%2C_Turkey.jpg/640px-Lake_Van%2C_Turkey.jpg"
        ],
        "pamukkale.jpg": [
            "https://images.unsplash.com/photo-1524231757912-21f4fe3a7200?w=640",
            "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4a/Pamukkale_Travertines.jpg/640px-Pamukkale_Travertines.jpg"
        ],
        "van_golu_uzay.jpg": [
            "https://www.universetoday.com/wp-content/uploads/2021/04/Lake_Van_Turkey_ISS.jpg",
            "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e5/Lake_Van_from_space.jpg/640px-Lake_Van_from_space.jpg"
        ],
        "tuz_golu_uzay.jpg": [
            "https://landsat.gsfc.nasa.gov/wp-content/uploads/2014/08/LakeTuz_OLI_2013140_lrg.jpg",
            "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2c/Lake_Tuz_from_space.jpg/640px-Lake_Tuz_from_space.jpg"
        ],
        "nemrut_heykeller.jpg": [
            "https://images.unsplash.com/photo-1621274403997-37aae1848bbd?w=640",
            "https://upload.wikimedia.org/wikipedia/commons/thumb/6/66/Mount_Nemrut_heads.jpg/640px-Mount_Nemrut_heads.jpg"
        ],
        "kiz_kulesi.jpg": [
            "https://images.unsplash.com/photo-1541432901012-a5e35fc33aed?w=640",
            "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d9/Maiden%27s_Tower_August_2018.jpg/640px-Maiden%27s_Tower_August_2018.jpg"
        ],
        "tr_nufus_haritasi.jpg": [
            "https://raw.githubusercontent.com/huseyinacar/assets/main/kpss/tr_nufus_isaretli.jpg"
        ],
        "tr_cukurova_haritasi.jpg": [
            "https://raw.githubusercontent.com/huseyinacar/assets/main/kpss/tr_cukurova_isaretli.jpg"
        ]
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    print("🚀 Resim indirme işlemi başlıyor (Alternatif kaynak destekli)...")
    success_count = 0
    fail_count = 0

    for filename, urls in images_to_download.items():
        filepath = os.path.join("images", filename)
        
        if os.path.exists(filepath):
            print(f"⏩ {filename} zaten mevcut, geçiliyor.")
            success_count += 1
            continue

        downloaded = False
        # Her bir URL kaynağını sırayla dene
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
            print(f"🛑 {filename} hiçbir kaynaktan indirilemedi!")
            fail_count += 1

    print(f"\n✨ İşlem tamamlandı!")
    print(f"✅ Başarılı: {success_count}")
    print(f"❌ Hatalı: {fail_count}")
    print("Artık botu yerel görsellerle uçurabilirsin! 🚀")

if __name__ == "__main__":
    download_kpss_images()
