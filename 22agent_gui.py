import customtkinter as ctk
import threading
import time
import re
import os
import subprocess
from selenium.webdriver.common.by import By
from wllmagent3 import SmartShoppingAgent
from db_manager2 import DBManager
from telethon.sync import TelegramClient
import asyncio


class ConfirmationPopup(ctk.CTkToplevel):
    def __init__(self, master, title, message, on_confirm):
        super().__init__(master)
        self.title(title)
        self.geometry("400x200")
        self.attributes("-topmost", True)
        self.on_confirm = on_confirm
        self.label = ctk.CTkLabel(self, text=message, font=("Arial", 14), wraplength=350)
        self.label.pack(pady=30)
        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.pack(pady=10)
        ctk.CTkButton(self.btn_frame, text="SEPETE EKLE", fg_color="green", command=self.confirm).grid(row=0, column=0,
                                                                                                       padx=10)
        ctk.CTkButton(self.btn_frame, text="İPTAL", fg_color="#cc0000", command=self.cancel).grid(row=0, column=1,
                                                                                                  padx=10)

    def confirm(self): self.on_confirm(True); self.destroy()

    def cancel(self): self.on_confirm(False); self.destroy()

class CodeInputDialog(ctk.CTkToplevel):
    def __init__(self, master, phone):
        super().__init__(master)
        self.title("Telegram Onay")
        self.geometry("300x180")
        self.attributes("-topmost", True)
        self.result = None
        ctk.CTkLabel(self, text=f"Kod ({phone}):").pack(pady=10)
        self.entry = ctk.CTkEntry(self, width=150)
        self.entry.pack(pady=5)
        ctk.CTkButton(self, text="ONAYLA", command=self.submit).pack(pady=20)

    def submit(self):
        self.result = self.entry.get().strip()
        self.destroy()

class AgentGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Trendyol Kesintisiz Asistan v23.0 + Telegram")
        self.geometry("1000x850")
        ctk.set_appearance_mode("dark")

        self.db = DBManager()
        self.products = self.db.get_active_products()

        self.is_monitoring = False
        self.agent = None
        self.lock = threading.Lock()

        self.telegram_token = ""
        self.telegram_chat_id = ""

        self.setup_ui()
        self.load_settings()  # DB'den yükler
        self.render_list()

    def setup_ui(self):
        self.grid_rowconfigure(4, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.header = ctk.CTkLabel(self, text="TRENDYOL KESİNTİSİZ ASİSTAN", font=("Impact", 28), text_color="#F27A1A")
        self.header.grid(row=0, column=0, pady=(15, 5))

        self.browser_btn = ctk.CTkButton(self, text="🌐 TARAYICIYI HAZIRLA VE OTURUMU AÇ",
                                         command=self.launch_browser,
                                         fg_color="#444444", hover_color="#555555", height=40)
        self.browser_btn.grid(row=1, column=0, padx=20, pady=5, sticky="ew")

        # 18agent_gui.py içindeki setup_ui fonksiyonunun ilgili kısmı
        self.tg_frame = ctk.CTkFrame(self, fg_color="#1e1e1e", corner_radius=12)
        self.tg_frame.grid(row=2, column=0, padx=20, pady=5, sticky="ew")

        ctk.CTkLabel(self.tg_frame, text="Telefon No:").grid(row=0, column=0, padx=5, pady=10)
        self.phone_entry = ctk.CTkEntry(self.tg_frame, placeholder_text="+905...", width=200)
        self.phone_entry.grid(row=0, column=1, padx=5)

        self.save_tg_btn = ctk.CTkButton(self.tg_frame, text="KAYDET", width=80, command=self.save_settings,
                                         fg_color="#0088cc")
        self.save_tg_btn.grid(row=0, column=2, padx=5)

        self.test_tg_btn = ctk.CTkButton(self.tg_frame, text="TEST", width=60, fg_color="purple",
                                         command=lambda: self.send_telegram("🔔 Bağlantı Testi Başarılı!"))
        self.test_tg_btn.grid(row=0, column=3, padx=5)

        # Ayarları Kaydetme ve Yükleme Metotları

    def save_settings(self):
        self.telegram_phone = self.phone_entry.get().strip()
        self.db.set_setting("tg_phone", self.telegram_phone)
        self.log("✅ Telefon numarası kaydedildi.")

    def load_settings(self):
        self.telegram_phone = self.db.get_setting("tg_phone", "")
        self.phone_entry.insert(0, self.telegram_phone)

        #self.test_tg_btn = ctk.CTkButton(self.tg_frame, text="TEST", width=60, fg_color="purple",
                                        # command=lambda: self.send_telegram("🔔 Bağlantı Testi Başarılı!"))
        #self.test_tg_btn.grid(row=0, column=5, padx=5)

        self.input_frame = ctk.CTkFrame(self, fg_color="#242424", corner_radius=12)
        self.input_frame.grid(row=3, column=0, padx=20, pady=10, sticky="ew")

        self.name_entry = ctk.CTkEntry(self.input_frame, placeholder_text="Ürün Adı", width=200)
        self.name_entry.grid(row=0, column=0, padx=10, pady=10)

        self.url_entry = ctk.CTkEntry(self.input_frame, placeholder_text="Ürün Linki...", width=400)
        self.url_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        self.sub_frame = ctk.CTkFrame(self.input_frame, fg_color="transparent")
        self.sub_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=5, sticky="ew")

        self.mode_var = ctk.StringVar(value="Fiyat")
        self.mode_menu = ctk.CTkOptionMenu(self.sub_frame, values=["Fiyat", "İndirim", "Stok"],
                                           variable=self.mode_var, width=100, command=self.toggle_price_entry)
        self.mode_menu.pack(side="left", padx=5)

        self.ins_entry = ctk.CTkEntry(self.sub_frame, placeholder_text="Hedef TL", width=80)
        self.ins_entry.pack(side="left", padx=5)

        self.autopilot_var = ctk.BooleanVar(value=False)
        self.autopilot_switch = ctk.CTkSwitch(self.sub_frame, text="OTO-PİLOT", variable=self.autopilot_var,
                                              progress_color="#F27A1A")
        self.autopilot_switch.pack(side="left", padx=20)

        self.add_btn = ctk.CTkButton(self.sub_frame, text="LİSTEYE EKLE", command=self.add_to_list, fg_color="#2fa572",
                                     font=("Arial", 12, "bold"))
        self.add_btn.pack(side="right", padx=5)

        self.list_frame = ctk.CTkScrollableFrame(self, fg_color="#1a1a1a",
                                                 label_text="Aktif Takip Listesi (Veritabanı)")
        self.list_frame.grid(row=4, column=0, padx=20, pady=5, sticky="nsew")

        self.status_box = ctk.CTkTextbox(self, height=100, font=("Consolas", 11), fg_color="#000000",
                                         text_color="#00ff00")
        self.status_box.grid(row=5, column=0, padx=20, pady=5, sticky="ew")

        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.grid(row=6, column=0, pady=15, sticky="ew")
        self.btn_frame.grid_columnconfigure((0, 1), weight=1)

        self.start_btn = ctk.CTkButton(self.btn_frame, text="▶ TAKİBİ BAŞLAT", command=self.start_monitoring,
                                       fg_color="#F27A1A", height=50)
        self.start_btn.grid(row=0, column=0, padx=20, sticky="ew")

        self.stop_btn = ctk.CTkButton(self.btn_frame, text="■ DURDUR", command=self.stop_monitoring, fg_color="#cc0000",
                                      height=50)
        self.stop_btn.grid(row=0, column=1, padx=20, sticky="ew")

    def launch_browser(self):
        potential_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expanduser("~") + r"\AppData\Local\Google\Chrome\Application\chrome.exe"
        ]
        chrome_path = next((p for p in potential_paths if os.path.exists(p)), None)

        if not chrome_path:
            self.log("❌ Chrome.exe bulunamadı!")
            return

        user_data = os.path.join(os.getcwd(), "asistan_profil")
        self.log("🚀 Tarayıcı hazırlanıyor...")
        cmd = f'"{chrome_path}" --remote-debugging-port=9222 --user-data-dir="{user_data}"'
        subprocess.Popen(cmd, shell=True)
        self.log("✅ Tarayıcı açıldı. Oturumunuzu açın.")

    def send_telegram(self, message):
        # Önceki kodlarınızda paylaştığınız sabit değerler
        api_id = 36215153
        api_hash = '5d78b538fcf894705c57acf35ebdfd13'
        phone = self.db.get_setting("tg_phone", "")  # db_manager'dan çekiyoruz

        if not phone:
            self.log("⚠️ Önce telefon numaranızı kaydedin!")
            return

        def _run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            session_name = f"session_{phone.replace('+', '')}"
            try:
                client = TelegramClient(session_name, api_id, api_hash)
                client.connect()

                if not client.is_user_authorized():
                    client.send_code_request(phone)
                    # Ana pencerede kod giriş ekranını açar
                    diag = CodeInputDialog(self, phone)
                    self.wait_window(diag)
                    if diag.result:
                        client.sign_in(phone, diag.result)
                    else:
                        self.log("❌ Onay kodu girilmedi.")
                        return

                client.send_message('me', message, parse_mode='html')
                client.disconnect()
                self.log("📩 Telegram: Mesaj gönderildi.")
            except Exception as e:
                self.log(f"❌ Telegram Hatası: {e}")
            finally:
                loop.close()

        threading.Thread(target=_run, daemon=True).start()


    def toggle_price_entry(self, choice):
        if choice == "Fiyat":
            self.ins_entry.configure(state="normal", fg_color="#FFFFFF")
        else:
            self.ins_entry.delete(0, 'end')
            self.ins_entry.configure(state="disabled", fg_color="#333333")

    def log(self, message):
        self.after(0, lambda: self.status_box.insert("end", f"[{time.strftime('%H:%M:%S')}] {message}\n"))
        self.after(0, lambda: self.status_box.see("end"))

    def add_to_list(self):
        current_mode = self.mode_var.get()
        name = self.name_entry.get().strip() or f"Ürün {len(self.products) + 1}"
        url = self.url_entry.get().strip()
        if not url: return

        target_price = 0
        if current_mode == "Fiyat":
            try:
                target_price = float(re.findall(r'\d+', self.ins_entry.get())[0])
            except:
                self.log("❌ Geçersiz fiyat!")
                return

        success = self.db.add_product({
            "name": name, "url": url, "mode": current_mode,
            "target": target_price, "autopilot": int(self.autopilot_var.get())
        })

        if success:
            with self.lock:
                self.products = self.db.get_active_products()
            self.render_list()
            self.log(f"✅ {name} eklendi.")
        else:
            self.log("⚠️ Bu ürün zaten listede!")

    def render_list(self):
        def _update():
            for widget in self.list_frame.winfo_children(): widget.destroy()
            with self.lock:
                for p in self.products:
                    card = ctk.CTkFrame(self.list_frame, fg_color="#2b2b2b", corner_radius=8)
                    card.pack(fill="x", pady=3, padx=5)
                    m_text = f"<{p['target']} TL" if p['mode'] == "Fiyat" else p['mode']
                    info = f"{p['name']} | Mod: {m_text}\nMin: {p['min_price']} TL | Son: {p['last_price']} TL"
                    ctk.CTkLabel(card, text=info, font=("Arial", 12), justify="left").pack(side="left", padx=15, pady=8)
                    if p.get('autopilot'):
                        ctk.CTkLabel(card, text="🚀 OTO-PİLOT", text_color="#F27A1A", font=("Arial", 10, "bold")).pack(
                            side="left", padx=5)
                    ctk.CTkButton(card, text="SİL", width=50, fg_color="#444444",
                                  command=lambda u=p['url']: self.manual_remove(u)).pack(side="right", padx=10)

        self.after(0, _update)

    def manual_remove(self, url):
        self.db.delete_product(url)
        with self.lock: self.products = self.db.get_active_products()
        self.render_list()

    def start_monitoring(self):
        if not self.products: return
        self.is_monitoring = True
        self.start_btn.configure(state="disabled", text="TAKİP AKTİF")
        threading.Thread(target=self.monitoring_thread, daemon=True).start()

    def stop_monitoring(self):
        self.is_monitoring = False
        self.start_btn.configure(state="normal", text="▶ TAKİBİ BAŞLAT")

    def monitoring_thread(self):
        try:
            if not self.agent: self.agent = SmartShoppingAgent()
        except Exception as e:
            self.log(f"❌ Hata: {e}")
            self.stop_monitoring()
            return

        while self.is_monitoring:
            with self.lock:
                items_to_check = list(self.products)

            for product in items_to_check:
                if not self.is_monitoring: break
                if not any(p['url'] == product['url'] for p in self.products): continue

                self.log(f"🔍 Kontrol: {product['name']}")
                try:
                    self.agent.driver.get(product['url'])
                    time.sleep(4)
                except:
                    self.log("⚠️ Bağlantı hatası!")
                    self.stop_monitoring()
                    break

                c_price = 0
                selectors = [
                    "span.ty-plus-price-discounted-price",      # Trendyol Plus indirimi
                    ".product-price-container .selling-price", # Standart satış fiyatı
                    ".prc-slg",                             # Kampanyalı fiyat 1
                    ".prc-dsc",                             # Kampanyalı fiyat 2
                    "span.discounted",                      # İndirimli etiket
                    ".product-price-container",             # Genel fiyat kapsayıcısı
                    "div[class*='price']"                   # Class ismi 'price' geçen herhangi bir div
                ]


                for sel in selectors:
                    try:
                        elements = self.agent.driver.find_elements(By.CSS_SELECTOR, sel)
                        for el in elements:
                            if el.is_displayed() and el.text:
                                clean_text = el.text.replace(".", "").replace(",", ".")
                                price_match = re.findall(r"\d+\.\d+|\d+", clean_text)
                                if price_match:
                                    c_price = min([float(p) for p in price_match if float(p) > 0])
                                    break
                        if c_price > 0: break
                    except:
                        continue

                if c_price > 0:
                    new_min = c_price if product['min_price'] == 0 else min(c_price, product['min_price'])
                    self.db.update_price(product['url'], c_price, new_min)
                    product['min_price'], product['last_price'] = new_min, c_price

                    alert = False
                    if product['mode'] == "Fiyat" and c_price <= product['target']:
                        alert = True
                    elif product['mode'] == "İndirim" and product['last_price'] > 0 and c_price < product['last_price']:
                        alert = True
                    elif product['mode'] == "Stok":
                        try:
                            if not self.agent.driver.find_elements(By.CSS_SELECTOR, ".passive, .sold-out"): alert = True
                        except:
                            pass

                    self.render_list()
                    if alert:
                        self.log(f"🔥 YAKALANDI: {product['name']} ({c_price} TL)")
                        self.send_telegram(f"🔔 <b>{product['name']}</b> yakalandı!\n💰 Fiyat: {c_price} TL \n🔗 <a href='{product['url']}'>Ürüne Git</a>")
                        if product.get('autopilot'):
                            self.execute_buy(product)
                            self.db.move_to_history(product, status="OTO-SEPET")
                        else:
                            self.after(0, lambda p=product: self.show_popup(p))
                            self.db.move_to_history(product, status="MANUEL-YAKALANDI")
                        with self.lock:
                            self.products = self.db.get_active_products()
                        self.render_list()
                else:
                    self.log(f"⚠️ {product['name']} okunamadı.")
            if self.is_monitoring: time.sleep(15)

    def execute_buy(self, product):
        try:
            btn = self.agent.driver.find_element(By.CSS_SELECTOR, ".add-to-basket, .add-to-cart-button")
            self.agent.driver.execute_script("arguments[0].click();", btn)
            self.log(f"🚀 OTO-PİLOT: {product['name']} sepete eklendi!")
            self.send_telegram(f"🚀 <b>{product['name']}</b> sepete eklendi!")
        except:
            self.log("❌ Sepet butonu yok.")

    def show_popup(self, product):
        def on_confirm(choice):
            if choice: self.execute_buy(product)

        ConfirmationPopup(self, "Hedef Yakalandı", f"{product['name']} kriteri sağladı!", on_confirm)


if __name__ == "__main__":
    app = AgentGUI()
    app.mainloop()