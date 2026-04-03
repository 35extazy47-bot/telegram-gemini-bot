import os
import subprocess
from datetime import datetime
from download_assets import download_kpss_images

def sync_to_github():
    print("🚀 Harita üretim ve GitHub senkronizasyonu başlıyor...")
    
    # 1. Haritaları güncelle
    try:
        print("🎨 Haritalar çiziliyor (Doku ve Gölgelendirme ekleniyor)...")
        download_kpss_images()
        print("✅ Haritalar 'images/' klasöründe başarıyla güncellendi.")
    except Exception as e:
        print(f"❌ Harita üretiminde bir sorun çıktı knk: {e}")
        return

    # 2. Git komutlarını sırayla çalıştır
    print("🌐 GitHub'a gönderiliyor...")
    
    # Git add
    subprocess.run(["git", "add", "."], capture_output=True)
    
    # Git commit
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    commit_msg = f"Auto-update maps: {timestamp}"
    commit_res = subprocess.run(["git", "commit", "-m", commit_msg], capture_output=True, text=True)
    
    if "nothing to commit" in commit_res.stdout or "working tree clean" in commit_res.stdout:
        print("ℹ️ Yapılacak bir değişiklik bulunamadı (Haritalar zaten güncel).")
    else:
        print(f"📝 Commit atıldı: {commit_msg}")

    # Git push
    # Mevcut dalı (branch) otomatik bulalım (main veya master)
    branch_res = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True)
    branch = branch_res.stdout.strip() or "main"
    
    push_res = subprocess.run(["git", "push", "origin", branch], capture_output=True, text=True)
    
    if push_res.returncode == 0:
        print(f"🚀 Başarıyla GitHub'a ({branch}) gönderildi knk!")
    else:
        print(f"❌ Push başarısız oldu:\n{push_res.stderr}")
        print("💡 İpucu: 'git remote -v' ile bağlantını kontrol et veya GitHub token ayarlarını doğrula.")

if __name__ == "__main__":
    sync_to_github()