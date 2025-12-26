import sqlite3
from datetime import datetime


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

        # YENİ: Uygulama Ayarları Tablosu (Telegram vb. için)
        cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )''')
        self.conn.commit()

    # --- AYARLAR İÇİN YENİ METOTLAR ---
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

    # --- MEVCUT METOTLAR (BOZULMADI) ---
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