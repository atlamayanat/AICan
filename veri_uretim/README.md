# Veri Üretim — Eş/Zıt Anlam & Atasözü havuzları

Sergi testinde oynatılacak iki quiz'in soru-cevap havuzları `ai/es_zit_anlam.json`
ve `ai/atasozu.json` dosyalarından gelir. Bu klasör, o dosyaları **gelişmiş bir
AI'ya güvenle ürettirmek** için gereken her şeyi içerir.

## Akış

1. **Promptu kopyala** — `PROMPT_es_zit_anlam.md` veya `PROMPT_atasozu.md`
   içindeki ⇩…⇧ işaretleri arasındaki bölümün tamamını gelişmiş bir AI'ya
   (Claude, ChatGPT, Gemini) yapıştır.
2. **Çıktıyı kaydet** — dönen JSON'u bir dosyaya kaydet (ör. `yeni_es_zit.json`),
   **UTF-8** olarak. AI'nın cevabı kesilirse "devam" yaz, parçaları birleştir.
3. **Doğrula:**
   ```
   python veri_uretim/dogrula.py yeni_es_zit.json
   ```
   - `HATA` varsa dosya yüklenmemeli — hatayı AI'ya geri yapıştırıp düzelttirmek
     en hızlısı ("şu hataları düzelt, dosyanın tamamını yeniden ver").
   - `UYARI`'lar bilgilendiricidir (özellikle simetri/çaprazlama uyarıları,
     ziyaretçinin doğru cevabının kabul edilmeyeceği durumları gösterir —
     mümkünse düzelttir).
4. **Yükle** — hatasız dosyayı devreye al (mevcut dosya otomatik yedeklenir):
   ```
   python veri_uretim/dogrula.py yeni_es_zit.json --yukle
   ```
5. **Sunucuyu yeniden başlat** — veri açılışta okunur.
6. **Hızlı oyun testi** — her iki oyundan birer tur oyna; soruların ve "Cevap: …"
   metinlerinin düzgün göründüğünü kontrol et.

## Neden bu kadar kural var?

Oyun motoru cevapları **sadece dosyadaki listeyle** karşılaştırır:

- Eş/Zıt: listede olmayan ama doğru olan cevap **yanlış sayılır** → listeler
  eksiksiz olmalı (promptun "kapsayıcılık" bölümü).
- Her öğe **tek kelime** olmalı: motor çok kelimeli öğeleri ilk kelimeye kırpar
  ("iyi kalpli" → "iyi") ve veri sessizce bozulur.
- Atasözü: ekranda "Cevap: {bas} {tamam[0]}" gösterilir → `bas` + ilk öğe tam ve
  doğal bir atasözü okutmalı; uydurma/birleştirilmiş söz kabul edilmez.

`dogrula.py` bu kuralların tamamını denetler ve motorla birebir aynı metin
temizleme fonksiyonlarını (`temiz_kelime`, `normalize`) kullanır.
