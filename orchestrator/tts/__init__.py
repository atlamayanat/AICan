"""aican seslendirme (TTS) paketi.

Motordan bagimsiz katman:
  - emotion_voice_map : duygu (valans+uyarilma) -> prosodi parametreleri
  - engine_base       : TTSEngine soyut arayuzu
  - engine_piper      : yerel, CPU, ucretsiz Piper motoru (varsayilan)
  - cache             : (metin+jest+yogunluk) -> wav dosya onbellegi

Agir bagimliliklar (piper/onnxruntime) burada IMPORT EDILMEZ; web_server motoru
arka planda tembel yukler (Whisper ile ayni desen).
"""
