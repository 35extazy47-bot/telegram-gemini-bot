import os
import json
from datetime import datetime, timedelta
from threading import Lock, RLock
import pymongo
from dotenv import load_dotenv

load_dotenv()

# --- Constants ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")
DEVELOPER_USERNAME = "HuseyinAcar35"
USERS_FILE = "users_data.json"
MARKET_FILE = "market_data.json"

# --- Quiz Data ---
try:
    with open("quiz_data.json", "r", encoding="utf-8") as f:
        QUIZ_QUESTIONS = json.load(f)
except FileNotFoundError:
    print("❌ HATA: quiz_data.json bulunamadı!")
    QUIZ_QUESTIONS = []

# --- Database Connection ---
mongo_client = None
users_collection = None
db = None
if MONGO_URI is not None:
    try:
        mongo_client = pymongo.MongoClient(MONGO_URI)
        db = mongo_client["geminibot_db"]
        users_collection = db["users"]
        print("✅ MongoDB Bağlantısı Başarılı!")

        # JSON verilerini MongoDB'ye aktarma (Eğer MongoDB boşsa ve yerel dosya varsa)
        if users_collection.count_documents({}) == 0 and os.path.exists(USERS_FILE):
            try:
                with open(USERS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data is not None:
                        # Veri yapısını { "_id": "users_data", "data": { ... } } şeklinde düzelt
                        users_collection.replace_one({"_id": "users_data"}, {"data": data}, upsert=True)
                        print("✅ JSON kullanıcı verileri buluta başarıyla taşındı!")
            except Exception as e:
                print(f"⚠️ JSON aktarma hatası: {e}")
    except Exception as e:
        print(f"⚠️ MongoDB Bağlantı Hatası: {e}")

# --- Data Locks & Runtime State ---
data_lock = Lock()
market_lock = RLock()
user_timers = {}
pending_duels = {}

# --- Market Data ---
TRADE_GOODS = {
    "ipek": {"name": "İpek 🧶", "base": 100, "min": 50, "max": 250, "volatility": 0.05},
    "baharat": {"name": "Baharat 🌶️", "base": 80, "min": 40, "max": 200, "volatility": 0.04},
    "cini": {"name": "Çini 🏺", "base": 150, "min": 100, "max": 400, "volatility": 0.06},
    "tuz": {"name": "Tuz 🧂", "base": 30, "min": 10, "max": 100, "volatility": 0.02},
    "elmas": {"name": "Elmas 💎", "base": 500, "min": 300, "max": 800, "volatility": 0.08},
    "altin": {"name": "Altın 🥇", "base": 250, "min": 150, "max": 400, "volatility": 0.03},
    "demir": {"name": "Demir ⛓️", "base": 50, "min": 20, "max": 100, "volatility": 0.03}
}
market_prices = {k: v["base"] for k, v in TRADE_GOODS.items()}
market_volumes = {k: 0 for k in TRADE_GOODS.keys()}
last_prices = market_prices.copy()
price_history = {k: [v["base"]] * 20 for k, v in TRADE_GOODS.items()}
market_news = "Borsa işlemleri başladı. Piyasa sakin. ☁️"
last_market_update = datetime.now()
market_trend = 0
last_news_update = datetime.now() - timedelta(minutes=6)
active_news_item = None
active_news_direction = None
active_global_modifier = 0.0

# --- Data Loading/Saving Functions ---
def load_users():
    """Kullanıcı verilerini önce MongoDB'den, yoksa yerel dosyadan yükler."""
    if users_collection is not None:
        try:
            doc = users_collection.find_one({"_id": "users_data"})
            if doc is not None and "data" in doc:
                print("✅ Kullanıcı verileri MongoDB'den yüklendi.")
                return doc["data"]
        except Exception as e:
            print(f"MongoDB Users Yükleme Hatası: {e}")

    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                print("✅ Kullanıcı verileri yerel dosyadan yüklendi.")
                return json.load(f)
        except Exception as e:
            print(f"Yerel dosya yükleme hatası: {e}")
    
    return {}

def save_users():
    """Kullanıcı verilerini MongoDB'ye (varsa) ve yedek olarak yerel dosyaya kaydeder."""
    with data_lock:
        if users_collection is not None:
            try:
                users_collection.replace_one({"_id": "users_data"}, {"data": users}, upsert=True)
            except Exception as e:
                print(f"Kullanıcı verileri MongoDB'ye kaydedilirken hata: {e}")
        else:
            try:
                with open(USERS_FILE, "w", encoding="utf-8") as f:
                    json.dump(users, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"Kullanıcı verileri yerel dosyaya kaydedilirken hata: {e}")

def save_market_data():
    """Borsa verilerini kaydeder."""
    global market_prices, market_volumes, last_prices, price_history, market_news, market_trend, last_market_update
    data = {
        "prices": market_prices,
        "volumes": market_volumes,
        "last_prices": last_prices,
        "price_history": price_history,
        "news": market_news,
        "trend": market_trend,
        "last_update": last_market_update.strftime("%Y-%m-%d %H:%M:%S") if last_market_update else None
    }
    
    if db is not None:
        try:
            collection = db["market"]
            collection.replace_one({"_id": "market_data"}, data, upsert=True)
        except Exception as e:
            print(f"❌ MongoDB Market Kayıt Hatası: {e}")
            
    try:
        with open(MARKET_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"❌ Yerel Dosya Kayıt Hatası: {e}")

def load_market_data():
    """Borsa verilerini yükler."""
    global market_prices, market_volumes, last_prices, market_news, last_market_update, price_history, market_trend
    data = None
    
    if db is not None:
        try:
            collection = db["market"]
            doc = collection.find_one({"_id": "market_data"})
            if doc is not None:
                data = doc
                print("✅ Borsa verileri MongoDB'den yüklendi.")
        except Exception as e:
            print(f"MongoDB Market Yükleme Hatası: {e}")

    if  data is None and os.path.exists(MARKET_FILE):
        try:
            with open(MARKET_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                print("✅ Borsa verileri yerel dosyadan yüklendi.")
        except:
            pass

    if data is not None:
        with market_lock:
            loaded_prices = data.get("prices", {})
            for k, v in loaded_prices.items():
                if k in market_prices: market_prices[k] = v
            
            loaded_volumes = data.get("volumes", {})
            for k, v in loaded_volumes.items():
                if k in market_volumes: market_volumes[k] = v

            last_prices.update(data.get("last_prices", {}))
            price_history.update(data.get("price_history", {}))
            market_news = data.get("news", market_news)
            market_trend = data.get("trend", 0)
            
            if "last_update" in data and data["last_update"] is not None:
                try:
                    last_market_update = datetime.strptime(data["last_update"], "%Y-%m-%d %H:%M:%S")
                except (ValueError, TypeError):
                    last_market_update = datetime.now()


# --- Initial Data Load ---
users = load_users()
load_market_data()
