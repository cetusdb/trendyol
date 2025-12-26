import setuptools
import google.generativeai as genai
import re
import time
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
            self.model = genai.GenerativeModel('gemini-2.5-flash')
        except:
            print("[Sistem] Gemini pasif.")

        # --- MEVCUT CHROME'A BAĞLANMA AYARI ---
        chrome_options = Options()
        chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

        try:
            print("[Sistem] Açık olan Chrome'a bağlanılıyor...")
            # Mevcut Chrome'a bağlandığımız için Service veya DriverManager gerekmez
            self.driver = webdriver.Chrome(options=chrome_options)
            print("[Tamam] Mevcut Chrome üzerinden kontrol sağlandı.")
        except Exception as e:
            print(f"[Hata] Chrome'a bağlanılamadı. Önce 1. adımı yapın: {e}")
            return

    def analyze_request_with_gemini(self, user_input):
        # Hedef fiyatı bulma mantığı
        numbers = re.findall(r'\d+', user_input.replace(".", "").replace(",", ""))
        if numbers:
            # Kullanıcı 318'in altı dediyse, hedefi 318-1 gibi değil, direkt 318 yapıyoruz
            # çünkü karşılaştırma operatörü (<=) zaten altını kapsıyor.
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
        # Manuel açtığımız için pop-up'ları kendin de kapatabilirsin ama kod yine denesin
        try:
            self.driver.find_element(By.CSS_SELECTOR, "div.modal-close").click()
        except:
            pass

    def analyze_product_with_ai(self):
        """Gemini AI kullanarak ürünün stok ve fiyat durumunu analiz eder."""
        if not self.driver: return {"stok": False, "fiyat": "Bilinmiyor"}
        try:
            # Sayfadaki metni alıp AI'ya analiz ettiriyoruz
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
            import json
            data = json.loads(raw_text)
            return {
                "stok": data.get("stok", "HAYIR").upper() == "EVET",
                "fiyat": data.get("fiyat", "Bilinmiyor")
            }
        except Exception as e:
            print(f"AI Analiz Hatası: {e}")
            return {"stok": False, "fiyat": "Hata"}