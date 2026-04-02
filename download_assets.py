import os
import requests
import time
import urllib3

# SSL uyarılarını kapatıyoruz
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def download_kpss_images():
    # 1. Klasörü oluştur
    if not os.path.exists("images"):
        os.makedirs("images")
        print("✅ 'images' klasörü oluşturuldu.")

    # 2. İndirilecek resimlerin listesi
    images_to_download = {
        "agri_dagi.jpg": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/60/Mount_Ararat_and_the_Ararat_Plain.jpg/640px-Mount_Ararat_and_the_Ararat_Plain.jpg",
        "van_golu.jpg": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d9/Lake_Van%2C_Turkey.jpg/640px-Lake_Van%2C_Turkey.jpg",
        "pamukkale.jpg": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4a/Pamukkale_Travertines.jpg/640px-Pamukkale_Travertines.jpg",
        "van_golu_uzay.jpg": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e5/Lake_Van_from_space.jpg/640px-Lake_Van_from_space.jpg",
        "tuz_golu_uzay.jpg": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2c/Lake_Tuz_from_space.jpg/640px-Lake_Tuz_from_space.jpg",
        "nemrut_heykeller.jpg": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/66/Mount_Nemrut_heads.jpg/640px-Mount_Nemrut_heads.jpg",
        "kiz_kulesi.jpg": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d9/Maiden%27s_Tower_August_2018.jpg/640px-Maiden%27s_Tower_August_2018.jpg"
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    print("🚀 Resim indirme işlemi başlıyor...")
    success_count = 0
    fail_count = 0

    for filename, url in images_to_download.items():
        filepath = os.path.join("images", filename)
        
        if os.path.exists(filepath):
            print(f"⏩ {filename} zaten mevcut, geçiliyor.")
            continue

        try:
            print(f"📥 {filename} indiriliyor...")
            response = requests.get(url, headers=headers, timeout=15, verify=False)
            if response.status_code == 200:
                with open(filepath, "wb") as f:
                    f.write(response.content)
                print(f"✅ {filename} başarıyla indirildi.")
                success_count += 1
            else:
                print(f"❌ {filename} indirilemedi (HTTP {response.status_code})")
                fail_count += 1
            
            # Bloklanmamak için kısa bir bekleme
            time.sleep(1.5)
        except Exception as e:
            print(f"❌ Hata ({filename}): {e}")
            fail_count += 1

    print(f"\n✨ İşlem tamamlandı!")
    print(f"✅ Başarılı: {success_count}")
    print(f"❌ Hatalı: {fail_count}")
    print("Artık botu yerel görsellerle uçurabilirsin! 🚀")

if __name__ == "__main__":
    download_kpss_images()
