import os
import sys
import subprocess
from datetime import datetime
from download_assets import download_kpss_images

def sync_to_github(commit_msg=None):
    print("🚀 GitHub senkronizasyonu başlıyor...")
    
    # 1. Haritaları güncelle
    try:
        print("🎨 Haritalar çiziliyor (Doku ve Gölgelendirme ekleniyor)...")
        download_kpss_images()
        print("✅ Haritalar 'images/' klasöründe başarıyla güncellendi.")
    except Exception as e:
        print(f"❌ Harita üretiminde bir sorun çıktı knk: {e}")
        print("⚠️ Harita üretimi atlanıyor, sadece kod değişiklikleri gönderilecek...")

    # 2. Git komutlarını sırayla çalıştır
    print("🌐 GitHub'a gönderiliyor...")
    
    # Git add
    subprocess.run(["git", "add", "."], capture_output=False)
    
    # Git commit
    if not commit_msg:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        commit_msg = f"Bot geliştirmeleri ve düzeltmeler: {timestamp}"
    
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
    # Eğer komut satırından mesaj girilmişse onu kullan
    custom_msg = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None
    if not custom_msg:
        custom_msg = input("📝 Commit mesajını gir (Boş bırakırsan otomatik tarih atılır): ").strip()
    sync_to_github(custom_msg if custom_msg else None)