# AICAN — Yeni (Temiz) PC Kurulumu

Sergiye konacak, yeni formatlanmış bir Windows 11 PC'yi oyunu çalıştıracak hâle
getirme rehberi. Kurulum sırasında **internet şarttır**; sergide internet
opsiyoneldir (sesler cache'ten + Piper çevrimdışı yedeğiyle çalışır).

## 1. Projeyi kopyala (USB önerilir)

`aican` klasörünün **TAMAMINI** (≈1 GB) yeni PC'ye kopyala, ör. `C:\aican` ya da
Masaüstü. Şunların geldiğinden emin ol:

- `orchestrator/tts/cache/` → ön-üretilmiş ElevenLabs sesleri (~450 MB).
  Bu klasör gelmezse sergide her cümle canlı sentezlenir (kredi + gecikme)!
- `orchestrator/tts/voices/` → Piper çevrimdışı ses modeli.
- `assets/emojis/` → yüz animasyon kareleri.

> Git ile klonlamak yerine USB kopyası önerilir: cache ve ses dosyaları
> depoda olmayabilir, USB'de kesin gelir.

## 2. KUR.bat'ı çalıştır

`kurulum\KUR.bat` → çift tık. Betik sırasıyla:

1. **Python 3.13** kurar (winget; yoksa python.org bağlantısı gösterir).
   Python yeni kurulduysa pencereyi kapatıp KUR.bat'ı **bir kez daha** çalıştırman istenebilir.
2. **VC++ Redistributable** kurar (Whisper ve Piper'ın DLL'leri için şart —
   temiz Windows'ta yoktur, eksikse sesli giriş "DLL load failed" ile ölür).
3. pip bağımlılıklarını kurar (`orchestrator/requirements.txt`).
4. **Profil** sorar → sergi PC'sinde `sergi` de (config.sergi.json devreye girer).
5. **Ollama**'yı kurar, sunucuyu başlatır, dil modelini indirir (~2.5 GB).
6. **Whisper** ses-tanıma modelini ön-indirir (~460 MB) — sergide internet gerekmesin diye.
7. **ElevenLabs anahtarı** sorar (opsiyonel; boş geçersen ücretsiz edge-tts + Piper çalışır).
8. Masaüstüne **AICAN Baslat** kısayolu koyar; istersen **otomatik başlatma** açar
   (PC her açılışta oyunu başlatır — sergi için önerilir).
9. **Sağlık kontrolü** koşar → `0 HATA` görmeden sergiye çıkma.

Soru sormadan kurmak için: `KUR.bat --sessiz` (profil=sergi, otomatik=evet).

## 3. Başlat & doğrula

- **Başlat:** Masaüstündeki `AICAN Baslat` (veya proje kökünde `BASLAT.bat`).
  Ollama'yı gerekirse başlatır, sunucuyu kaldırır, sergi + kontrol sekmelerini açar.
- **Sağlık kontrolü (istediğin an):** `python kurulum\saglik_kontrol.py`
- **Test modu:** herhangi bir ekranda **`g`** → sadece Eş/Zıt + Atasözü, sohbet kapalı,
  "merhaba" doğrudan oyun menüsü açar. Ayar kalıcıdır.
- Ekran kısayolları: `f` tam ekran · `d` sürekli mikrofon aç/kapa · `s` ses aç/kapa.

## Sergi günü kontrol listesi

- [ ] `saglik_kontrol.py` → 0 HATA
- [ ] Ses geliyor mu? (ilk tıklamadan sonra — tarayıcı ses kilidi ilk dokunuşta açılır)
- [ ] Mikrofon izni verildi mi? (tarayıcı ilk açılışta sorar → "İzin ver")
- [ ] Test modu rozeti yanıyor mu? (`g`)
- [ ] Her iki oyundan birer tur oyna
- [ ] Ses seviyesi / mikrofon mesafesi sahada ayarlandı mı?

## Sorun giderme

| Belirti | Çare |
|---|---|
| "Python bulunamadi" | KUR.bat'ı tekrar çalıştır; olmadıysa python.org'dan kur ("Add to PATH" işaretli) |
| "DLL load failed" (faster_whisper/piper) | VC++ Redistributable eksik → https://aka.ms/vs/17/release/vc_redist.x64.exe kur, sağlık kontrolünü tekrar koş |
| Model inmiyor | İnterneti kontrol et; `ollama pull <model>` elle dene |
| Ses yok | Tarayıcıda sayfaya bir kez tıkla; `s` tuşu ses kapalı olabilir; sağlık kontrolüne bak |
| Mikrofon çalışmıyor | Tarayıcı adres çubuğu → mikrofon izni; Windows ayarları → gizlilik → mikrofon |
| Cevaplar çok yavaş | Ollama GPU kullanıyor mu: `ollama ps`; sergi profili seçildi mi |
