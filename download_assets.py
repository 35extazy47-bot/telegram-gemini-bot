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
        "tr_nufus.jpg": [
            "https://mapdb.net/wp-content/uploads/2021/01/turkiye-nufus-yogunlugu-haritasi.jpg",
            "https://upload.wikimedia.org/wikipedia/commons/thumb/2/23/Turkey_population_density_map.png/800px-Turkey_population_density_map.png"
        ],
        "tr_delta.jpg": [
            "https://www.haritane.com/images/turkiye-ovalar-haritasi.jpg",
            "https://www.cografyaci.biz/wp-content/uploads/2020/05/turkiye-ovalar-haritasi.jpg"
        ],
        "tr_demir.jpg": [
            "https://www.cografyaci.biz/wp-content/uploads/2020/05/turkiye-demir-haritasi.jpg"
        ],
        "tr_bor.jpg": [
            "https://www.cografyaci.biz/wp-content/uploads/2020/05/turkiye-bor-haritasi.jpg"
        ],
        "tr_petrol.jpg": [
            "https://www.cografyaci.biz/wp-content/uploads/2020/05/turkiye-petrol-haritasi.jpg"
        ],
        "tr_iklim.jpg": [
            "https://www.haritane.com/images/turkiye-iklim-haritasi.jpg",
            "https://www.cografyaci.biz/wp-content/uploads/2020/05/turkiye-iklim-haritasi.jpg"
        ]
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "Referer": "https://www.google.com/",
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
