import setuptools
import google.generativeai as genai
import re
import time
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from config import GEMINI_CONFIG


class SmartShoppingAgent:
    def __init__(self, url=""):
        self.url = url
        self.target_price = 0
        self.is_stock_trigger = False

        try:
            genai.configure(api_key=GEMINI_CONFIG["api_key"])
            self.model = genai.GenerativeModel('gemini-1.5-flash')
        except:
            print("[Sistem] Gemini pasif.")

        # --- MEVCUT CHROME'A BAĞLANMA AYARI ---
        chrome_options = Options()
        chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

        try:
            print("[Sistem] Açık olan Chrome'a bağlanılıyor...")
            self.driver = webdriver.Chrome(options=chrome_options)
            print("[Tamam] Mevcut Chrome üzerinden kontrol sağlandı.")
        except Exception as e:
            print(f"[Hata] Chrome'a bağlanılamadı. Önce 1. adımı yapın: {e}")
            return

    def analyze_request_with_gemini(self, user_input):
        numbers = re.findall(r'\d+', user_input.replace(".", "").replace(",", ""))
        if numbers:
            self.target_price = float(numbers[0])

        try:
            prompt = f"Analiz et: '{user_input}'. PRICE: [Sayı], STOCK_WAIT: [TRUE/FALSE]"
            response = self.model.generate_content(prompt)
            res = response.text.upper()
            ai_prices = re.findall(r"PRICE:(\d+)", res.replace(" ", ""))
            if ai_prices: self.target_price = float(ai_prices[0])
            self.is_stock_trigger = "TRUE" in res
            return True
        except:
            return True

    def close_popups(self):
        try:
            self.driver.find_element(By.CSS_SELECTOR, "div.modal-close").click()
        except:
            pass

    def analyze_product_with_ai(self):
        """Gemini AI kullanarak ürünün stok ve fiyat durumunu analiz eder."""
        if not self.driver: return {"stok": False, "fiyat": "Bilinmiyor"}
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text[:2500]
            prompt = (
                f"Sen bir alışveriş asistanısın. Aşağıdaki metni incele.\n"
                f"1. Ürün stokta mı ve 'Sepete Ekle' butonu aktif mi?\n"
                f"2. Ürünün güncel fiyatı nedir?\n"
                f"Sadece şu JSON formatında cevap ver: {{\"stok\": \"EVET/HAYIR\", \"fiyat\": \"fiyat_metni\"}}\n\n"
                f"METİN:\n{body_text}"
            )
            response = self.model.generate_content(prompt)
            raw_text = response.text.replace("```json", "").replace("```", "").strip()
            data = json.loads(raw_text)
            return {
                "stok": data.get("stok", "HAYIR").upper() == "EVET",
                "fiyat": data.get("fiyat", "Bilinmiyor")
            }
        except Exception as e:
            print(f"AI Analiz Hatası: {e}")
            return {"stok": False, "fiyat": "Hata"}

    # ==================== YENİ EKLENEN FONKSİYONLAR ====================

    def get_price_recommendation(self, price_history):
        """30 günlük fiyat geçmişine göre AI önerisi verir."""
        if not price_history or len(price_history) < 3:
            return "⚠️ Yeterli veri yok. Daha fazla takip gerekiyor."
        
        try:
            prices = [h['price'] for h in price_history]
            dates = [h['timestamp'] for h in price_history]
            
            min_price = min(prices)
            max_price = max(prices)
            avg_price = sum(prices) / len(prices)
            current_price = prices[-1]
            
            prompt = f"""Sen bir alışveriş danışmanısın. Aşağıdaki 30 günlük fiyat verilerini analiz et:

📊 Fiyat Verileri:
• Minimum: {min_price:.2f} TL
• Maksimum: {max_price:.2f} TL
• Ortalama: {avg_price:.2f} TL
• Güncel: {current_price:.2f} TL
• Toplam {len(prices)} kontrol

Tarihsel Fiyatlar: {prices}

Lütfen şu soruları cevapla:
1. Fiyat trendi nasıl? (yükseliş/düşüş/stabil)
2. Şu an alım için uygun mu?
3. Beklenmesi öneriliyor mu?
4. Tahmini ideal alım fiyatı ne olabilir?

Kısa ve net 4-5 cümleyle kullanıcıya öneride bulun."""

            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            return f"❌ Öneri oluşturulamadı: {str(e)}"

    def find_similar_products(self, product_name, current_price):
        """Sayfa içeriğini AI ile analiz ederek benzer ürünleri bulur."""
        if not self.driver:
            return []
        
        try:
            # Sayfadaki tüm ürün kartlarını ve metinleri topla
            body_text = self.driver.find_element(By.TAG_NAME, "body").text[:4000]
            
            prompt = f"""Şu ürün için benzer/alternatif ürünler arıyoruz: "{product_name}" (Mevcut Fiyat: {current_price} TL)

Aşağıdaki sayfa içeriğinde benzer ürünler, alternatif modeller veya aynı kategorideki ürünler var mı?

ÖNEMLI: Sadece GERÇEKTEN sayfa içeriğinde GÖRÜLEBİLEN ürünleri listele. Uydurma!

Varsa şu formatta JSON olarak ver:
[
  {{
    "name": "Ürün tam adı",
    "price": fiyat_sayı_olarak,
    "reason": "Neden benzer (örn: aynı marka, benzer özellikler)"
  }},
  ...
]

Eğer benzer ürün YOKSA boş liste dön: []

Sayfa İçeriği:
{body_text}

Not: Sadece JSON formatında cevap ver, başka açıklama ekleme."""

            response = self.model.generate_content(prompt)
            raw_text = response.text.replace("```json", "").replace("```", "").strip()
            
            try:
                similar_products = json.loads(raw_text)
            except:
                # JSON parse hatası varsa boş liste dön
                return []
            
            # Fiyat avantajı hesapla
            for product in similar_products:
                if product.get('price') and current_price:
                    saving = current_price - product['price']
                    product['saving'] = saving
                    product['saving_percent'] = (saving / current_price) * 100 if current_price > 0 else 0
                    product['url'] = ""  # Trendyol'da link çekimi zor, boş bırak
                else:
                    product['saving'] = 0
                    product['saving_percent'] = 0
                    
            return similar_products[:5]  # En fazla 5 öneri
            
        except Exception as e:
            print(f"Benzer ürün arama hatası: {e}")
            return []

    def analyze_product_features(self, product_url):
        """Ürün özelliklerini AI ile detaylı analiz eder. (BONUS ÖZELLİK)"""
        if not self.driver:
            return {}
        
        try:
            self.driver.get(product_url)
            time.sleep(3)
            
            body_text = self.driver.find_element(By.TAG_NAME, "body").text[:4000]
            
            prompt = f"""Aşağıdaki ürün sayfası içeriğini analiz et ve şu bilgileri JSON formatında ver:

{{
  "category": "ürün kategorisi (örn: Elektronik, Giyim)",
  "brand": "marka adı",
  "key_features": ["önemli özellik 1", "önemli özellik 2", "önemli özellik 3"],
  "pros": ["artı yön 1", "artı yön 2"],
  "cons": ["eksi yön 1", "eksi yön 2"],
  "target_audience": "kimler için uygun"
}}

Eğer bir bilgi bulunamazsa "Bilinmiyor" yaz.

Sayfa İçeriği:
{body_text}

Sadece JSON formatında cevap ver."""

            response = self.model.generate_content(prompt)
            raw_text = response.text.replace("```json", "").replace("```", "").strip()
            
            return json.loads(raw_text)
            
        except Exception as e:
            print(f"Özellik analiz hatası: {e}")
            return {}