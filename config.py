GEMINI_CONFIG = {
    # Google AI Studio'dan aldığın anahtar
    "api_key" : "your api key",

    # Kullanılacak model ismi
    "MODEL_NAME":"gemini-1.5-flash",

    # Takip edilecek sitenin ana adresi
    "BASE_URL" : "https://dilayats.github.io/alisveris-test-sitesi/"}

    # Model Ayarları (Opsiyonel ama tutarlılık için önerilir)
GENERATION_CONFIG = {
    "temperature": 0.1,  # Daha kesin cevaplar için düşük tutuyoruz
    "max_output_tokens": 100,}
