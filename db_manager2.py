import sqlite3
from datetime import datetime, timedelta


class DBManager:
    def __init__(self, db_name="asistan.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        # Aktif takip listesi
        cursor.execute('''CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            url TEXT UNIQUE,
            mode TEXT,
            target REAL,
            autopilot INTEGER,
            min_price REAL DEFAULT 0,
            last_price REAL DEFAULT 0
        )''')

        # Geçmiş tablosu
        cursor.execute('''CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            url TEXT,
            final_price REAL,
            status TEXT,
            timestamp TEXT
        )''')

        # Uygulama Ayarları Tablosu
        cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )''')

        # YENİ: Fiyat Geçmişi Tablosu (30 günlük takip için)
        cursor.execute('''CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT,
            price REAL,
            timestamp TEXT,
            FOREIGN KEY (url) REFERENCES products(url)
        )''')

        # YENİ: Benzer Ürünler Önbellekleme
        cursor.execute('''CREATE TABLE IF NOT EXISTS similar_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_url TEXT,
            similar_name TEXT,
            similar_url TEXT,
            similar_price REAL,
            similarity_score REAL,
            timestamp TEXT
        )''')

        self.conn.commit()

    # --- AYARLAR İÇİN METOTLAR ---
    def set_setting(self, key, value):
        """Bir ayarı kaydeder veya günceller."""
        cursor = self.conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
        self.conn.commit()

    def get_setting(self, key, default=""):
        """Bir ayarı getirir, yoksa varsayılan değeri döner."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row[0] if row else default

    # --- FİYAT GEÇMİŞİ METOTLARI ---
    def add_price_history(self, url, price):
        """Ürün için fiyat geçmişi kaydeder."""
        cursor = self.conn.cursor()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute('''INSERT INTO price_history (url, price, timestamp) 
                        VALUES (?, ?, ?)''', (url, price, timestamp))
        self.conn.commit()
        # 30 günden eski kayıtları temizle
        self.clean_old_price_history()

    def get_price_history(self, url, days=30):
        """Son X gün için fiyat geçmişini getirir."""
        cursor = self.conn.cursor()
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute('''SELECT price, timestamp FROM price_history 
                        WHERE url = ? AND timestamp > ?
                        ORDER BY timestamp ASC''', (url, cutoff_date))
        rows = cursor.fetchall()
        return [{"price": r[0], "timestamp": r[1]} for r in rows]

    def clean_old_price_history(self):
        """30 günden eski fiyat kayıtlarını siler."""
        cursor = self.conn.cursor()
        cutoff_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("DELETE FROM price_history WHERE timestamp < ?", (cutoff_date,))
        self.conn.commit()

    def get_price_statistics(self, url):
        """Ürün için fiyat istatistikleri döner."""
        history = self.get_price_history(url)
        if not history:
            return None
        
        prices = [h['price'] for h in history]
        return {
            "min": min(prices),
            "max": max(prices),
            "avg": sum(prices) / len(prices),
            "current": prices[-1] if prices else 0,
            "trend": "düşüş" if len(prices) > 1 and prices[-1] < prices[0] else "yükseliş"
        }

    # --- BENZERİ ÜRÜNLER METOTLARI ---
    def save_similar_products(self, source_url, similar_list):
        """Benzer ürünleri kaydeder."""
        cursor = self.conn.cursor()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Eski benzerleri temizle
        cursor.execute("DELETE FROM similar_products WHERE source_url = ?", (source_url,))
        
        for item in similar_list:
            cursor.execute('''INSERT INTO similar_products 
                            (source_url, similar_name, similar_url, similar_price, similarity_score, timestamp)
                            VALUES (?, ?, ?, ?, ?, ?)''',
                          (source_url, item['name'], item['url'], item['price'], 
                           item.get('score', 0.8), timestamp))
        self.conn.commit()

    def get_similar_products(self, source_url, max_age_hours=24):
        """Önbellekten benzer ürünleri getirir."""
        cursor = self.conn.cursor()
        cutoff_time = (datetime.now() - timedelta(hours=max_age_hours)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute('''SELECT similar_name, similar_url, similar_price, similarity_score 
                        FROM similar_products 
                        WHERE source_url = ? AND timestamp > ?
                        ORDER BY similarity_score DESC''', (source_url, cutoff_time))
        rows = cursor.fetchall()
        return [{"name": r[0], "url": r[1], "price": r[2], "score": r[3]} for r in rows]

    # --- MEVCUT METOTLAR ---
    def add_product(self, data):
        cursor = self.conn.cursor()
        try:
            cursor.execute('''INSERT INTO products (name, url, mode, target, autopilot) 
                            VALUES (?, ?, ?, ?, ?)''',
                           (data['name'], data['url'], data['mode'], data['target'], data['autopilot']))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_active_products(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT name, url, mode, target, autopilot, min_price, last_price FROM products")
        rows = cursor.fetchall()
        return [{"name": r[0], "url": r[1], "mode": r[2], "target": r[3],
                 "autopilot": bool(r[4]), "min_price": r[5], "last_price": r[6]} for r in rows]

    def update_price(self, url, last_price, min_price):
        cursor = self.conn.cursor()
        cursor.execute("UPDATE products SET last_price = ?, min_price = ? WHERE url = ?", (last_price, min_price, url))
        self.conn.commit()
        # Fiyat geçmişine de kaydet
        self.add_price_history(url, last_price)

    def move_to_history(self, product, status):
        cursor = self.conn.cursor()
        cursor.execute('''INSERT INTO history (name, url, final_price, status, timestamp) 
                        VALUES (?, ?, ?, ?, ?)''',
                       (product['name'], product['url'], product.get('last_price', 0),
                        status, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        cursor.execute("DELETE FROM products WHERE url = ?", (product['url'],))
        self.conn.commit()

    def delete_product(self, url):
        cursor = self.conn.cursor()
        cursor.execute("SELECT name, last_price FROM products WHERE url = ?", (url,))
        row = cursor.fetchone()
        if row:
            self.move_to_history({'name': row[0], 'url': url, 'last_price': row[1]}, status="KULLANICI SİLDİ")