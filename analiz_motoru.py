import google.generativeai as genai
import re
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from config import GEMINI_CONFIG

import google.generativeai as genai
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from config import GEMINI_CONFIG

class SmartShoppingAgent:
    def __init__(self):
        genai.configure(api_key=GEMINI_CONFIG["api_key"])
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        
        chrome_options = Options()
        chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
        except:
            self.driver = None

    # SENİN LİSTENE BU FONKSİYONU EKLİYORUZ:
    def get_market_analysis(self):
        """Trendyol sayfasını analiz eder."""
        try:
            if not self.driver:
                return "Tarayıcı bağlı değil."
            
            title = self.driver.title
            body_text = self.driver.find_element(By.TAG_NAME, "body").text[:4000]
            
            prompt = f"Ürün: {title}\nVeriler: {body_text}\n\nBu fiyat mantıklı mı? Tavsiyen nedir?"
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Analiz hatası: {str(e)}"

    def analyze_product_with_ai(self):
        if not self.driver: return {"stok": False, "fiyat": "Bilinmiyor"}
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text[:2500]
            return {"stok": "EVET", "fiyat": "Analiz Edildi"}
        except:
            return {"stok": "HATA", "fiyat": "0"}