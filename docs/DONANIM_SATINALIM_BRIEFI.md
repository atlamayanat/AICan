# AICAN — Donanım Satın Alım Briefi

> **Bu dosyanın amacı:** Aşağıdaki proje tanımını bir yapay zekâya (ChatGPT / Claude vb.) verip
> **"bu projeye en uygun bilgisayar, mikrofon, hoparlör, ekran ve çevre birimlerini öner"**
> demek için hazırlanmış, koda erişimi olmayan birinin de anlayacağı kendine yeten bir özettir.
> Sona eklenen **"Yapay Zekâdan Beklenenler"** bölümü, öneri isterken sorulacak soruları içerir.

---

## 1. Proje Nedir? (Tek Paragraf)

**AICAN** (kod adı *"AI Body"*), **Konya Bilim Merkezi**'ndeki bir **sergi ünitesi** için geliştirilen,
yapay zekâ tabanlı bir **etkileşimli ifade/karakter** prototipidir. Ziyaretçi bir ekrana yazı yazar **veya
mikrofonla konuşur**; yerel (internetsiz çalışabilen) bir yapay zekâ modeli bu girdiyi anlar, uygun bir
**duygu/jest** seçer ve **kısa, sıcak bir Türkçe cevap** üretir. Cevap aynı anda üç kanaldan verilir:
ekranda bir **ışık (LED matris) animasyonu** oynar, ekrandaki **"canlı göz"** karaktere hayat verir ve
cevap **sesli olarak** hoparlörden okunur. Ayrıca ziyaretçiyle **"Kelime Türetme"** oyunu oynanabilir.
Kurulum bir **kiosk** olarak, sergi açık olduğu sürece **günlerce kesintisiz** çalışacak şekilde tasarlanmıştır.

---

## 2. Ziyaretçi Deneyimi (Nasıl Kullanılıyor?)

1. Ziyaretçi sergi standındaki ekranın karşısına gelir. Ekranda animasyonlu bir "göz" karakteri ziyaretçiyi bekler.
2. Ziyaretçi **klavye/dokunmatikle yazarak** ya da **mikrofona konuşarak** bir şey söyler (ör. "merhaba", "bugün çok mutluyum", "bana bir oyun oyna").
3. Sistem birkaç saniye içinde:
   - Ekranda o duyguya uygun bir **animasyon** oynatır (gülen yüz, kalp, ateş, yıldız, onay/ret işareti vb.).
   - Kısa bir cümleyle **cevap verir** ve bu cevabı **sesli** okur.
4. İstenirse **Kelime Türetme oyunu** başlar: yapay zekâ bir kelime söyler, ziyaretçi son harfiyle başlayan yeni bir kelime söyler; sırayla devam eder.
5. Her oturum, analiz için bir günlük (log) dosyasına kaydedilir.

**Önemli kullanım gerçeği:** Aynı anda **tek bir ziyaretçi** etkileşir (çok kullanıcılı değil). Ama sistem
**gün boyu, arka arkaya yüzlerce kısa etkileşim** için ayakta kalmalıdır.

---

## 3. Teknik Mimari (Akış)

```
[ Ziyaretçi ]
   |  (yazi  VEYA  ses = mikrofon)
   v
[ Tarayici Kiosk Arayuzu ]  --ses-->  [ Konusma->Metin (STT) ]     : faster-whisper (yerel)
   |  metin                                    |
   |<-------------------------------------------+  (cozulen metin)
   v
[ Yerel Dil Modeli (LLM) ]  : Ollama + Qwen (~4B, gerekirse 7-9B)
   |   -> hangi jest? + kisa Turkce cevap metni
   +--------------> [ 96x96 yazilim LED matris + "canli goz" animasyonu ]  (ekran)
   +--------------> [ Metin->Konusma (TTS) ] : edge-tts (online) / Piper (offline)  --> [ Hoparlor ]
   |
   v
[ logs/session.log ]  (her oturumun detayli kaydi)
```

Tüm bu bileşenler **tek bir bilgisayarda** çalışır. Ekran arayüzü bir **web tarayıcısında** (kiosk/tam ekran)
açılır; arka planda küçük bir yerel sunucu (Python/Flask, `127.0.0.1:5057`) her şeyi birbirine bağlar.

---

## 4. Kullanılan Teknolojiler

| Katman | Teknoloji | Not (donanım açısından önemi) |
|---|---|---|
| **Dil modeli (beyin)** | **Ollama** + **Qwen 3 / 3.5** (`4B instruct`, gerekirse `7B–9B`) | En ağır iş. **GPU + VRAM** ister. Model dosyası ~2.5–3 GB, 9B için daha büyük. |
| **Konuşma → Metin (STT)** | **faster-whisper** (`small` model) | Şu an **CPU**'da (int8) çalışıyor çünkü GPU belleği modele ayrılmış. Daha fazla VRAM olursa GPU'ya alınıp hızlanır. |
| **Metin → Konuşma (TTS)** | **edge-tts** (Microsoft, çevrimiçi, "Emel" TR sesi) + yedek **Piper** (yerel/offline, CPU) + **ffmpeg** | edge-tts **internet ister** (kalite yüksek, ücretsiz). Piper internetsiz yedek, CPU'da çalışır. |
| **Arayüz / Ekran** | Web (HTML + JavaScript Canvas), tarayıcı kiosk | 96×96 "ışık matrisi" ve göz animasyonu tarayıcıda çizilir. **Dokunmatik** kullanılabiliyor ("butona dokun"). |
| **Sunucu / tutkal** | Python 3.10+, **Flask** | Hafif; CPU üzerinde döner. |
| **Ölçüm** | psutil | RAM/CPU istatistikleri. |
| **İşletim sistemi** | **Windows 11** (mevcut geliştirme ortamı) | Ollama, faster-whisper, Piper, edge-tts hepsi Windows'ta çalışıyor. |

**Tamamı yerel çalışabilir** (edge-tts hariç). Yani bulut/AI aboneliği ya da sunucu maliyeti yok; iş yükü
tamamen sergi bilgisayarının üstünde.

---

## 5. Donanımı Belirleyen Hesaplama Yükü (Kritik Bölüm)

Bu proje için **en belirleyici bileşen ekran kartı (GPU) ve VRAM'idir.** Neden:

- **Dil modeli GPU belleğine (VRAM) sığmalı.** Sığarsa cevaplar 3–5 saniyede gelir; sığmayıp CPU'ya
  taşarsa **4–5 kat yavaşlar** ve sergi deneyimi bozulur.
- Aynı GPU'yu aynı anda **STT (Whisper)** ve istenirse **nöral TTS** de kullanmak isteyebilir. Bellek
  bölüşülür. Bu yüzden **VRAM ne kadar fazlaysa o kadar rahat.**
- **RAM:** Model yüklendiğinde birkaç GB kullanır; işletim sistemi + tarayıcı + Python ile birlikte
  **en az 16 GB, rahatlık için 32 GB** hedeflenir.
- **Disk:** Model dosyaları + bağımlılıklar için **~10–20 GB** boş alan. SSD tercih edilir (model yükleme hızı).
- **CPU:** STT şu an CPU'da çalıştığı için çok zayıf bir işlemci konuşma çözümünü yavaşlatır. Orta-üst seviye
  bir CPU yeterli.
- **Ağ:** edge-tts (yüksek kaliteli ses) **internet bağlantısı** ister. İnternet yoksa/dalgalanırsa sistem
  otomatik olarak offline Piper sesine düşer — yani internet **tercih edilir ama zorunlu değil.**
- **Sürekli çalışma:** Kiosk günlerce açık kalır; her gece otomatik yeniden başlatma planlanmıştır. Donanımın
  **7/24 ısınma/dayanıklılık** açısından uygun olması (iyi soğutma, kaliteli güç kaynağı) önemlidir.

### Mevcut / Planlanan Donanım Profilleri (projede tanımlı)

| Profil | Ekran Kartı | RAM | Kullanım |
|---|---|---|---|
| **Sergi PC (hedef)** | **RTX 5070 Ti 16 GB VRAM** | 32 GB | Serginin çalışacağı asıl makine profili. |
| Geliştirme laptobu | 4 GB VRAM | — | Kısıtlı; bu yüzden Whisper ve TTS CPU'ya alınmış, sadece 4B model kullanılıyor. |

> 16 GB VRAM'li profil bu iş için **oldukça geniş bir tampon** sağlar (4B model + Whisper GPU + nöral TTS aynı
> anda rahat sığar; hatta 7–9B modele çıkılabilir). 4 GB profil ise **alt sınır**; çalışır ama Whisper/TTS'i
> CPU'da tutmak ve küçük model kullanmak gerekir.

---

## 6. Sergi Ortamı ve Kullanım Koşulları (Donanım Seçimini Etkiler)

- **Yer:** Bilim merkezi sergi salonu — **gürültülü**, kalabalık, yankılı bir ortam. Bu, **mikrofon seçimi**
  için kritik: ortam gürültüsünü bastıran, ziyaretçinin sesini net alan (yönlü / gürültü engelleyici / uygun
  mesafeden çalışan) bir mikrofon gerekir.
- **Etkileşim mesafesi:** Ziyaretçi ekrandan yaklaşık **kol mesafesinde** durur; mikrofonun bu mesafeden net
  ses alması beklenir (yaka mikrofonu takılamaz — herkese açık kiosk).
- **Ses çıkışı:** Cevaplar sesli okunuyor; **gürültülü salonda duyulabilecek, net konuşma için uygun bir
  hoparlör** gerekir.
- **Ekran:** Kiosk için büyükçe, mümkünse **dokunmatik** bir monitör (ziyaretçi butona dokunarak da etkileşiyor).
- **Dayanıklılık:** Halka açık, çok kullanımlı, gün boyu açık bir kurulum — donanımın kasa/soğutma/kablo yönetimi
  bakımından sergiye uygun ve dayanıklı olması önemli.
- **Bakım:** Teknik personel her gün başında değil; sistem kendini toparlayabilmeli (otomatik yeniden başlatma,
  internet gidince offline sese düşme gibi önlemler yazılımda mevcut).

---

## 7. Yapay Zekâdan Beklenenler (Öneri İsterken Sorulacaklar)

Bu briefi bir yapay zekâya verirken şunları iste:

1. **Bilgisayar / GPU:**
   - Yukarıdaki iş yükü için uygun bir **masaüstü PC konfigürasyonu** öner (GPU, VRAM, CPU, RAM, disk, güç, soğutma).
   - Planlanan **RTX 5070 Ti 16 GB / 32 GB RAM** profilini **doğrula**: yeterli mi, fazla mı, yetersiz mi?
   - **Daha ekonomik bir alternatif** (ör. daha küçük VRAM'le 4B modele yetecek) ve **daha güçlü bir alternatif**
     (7–9B model + GPU'da Whisper/TTS için) olarak 2–3 farklı bütçe seviyesinde seçenek ver.
   - 7/24 sergi kullanımı için dayanıklılık/soğutma açısından nelere dikkat edilmeli?
2. **Mikrofon:**
   - **Gürültülü bir sergi salonunda, kiosk üzerinde sabit**, ziyaretçinin ~1 m mesafeden konuşmasını net alacak
     bir mikrofon öner (yönlü mü, dizi/array mi, gürültü bastırmalı USB mikrofon mu?). Somut model örnekleri ver.
3. **Hoparlör / ses çıkışı:** Gürültülü salonda anlaşılır konuşma için uygun hoparlör öner.
4. **Ekran:** Kiosk için uygun boyut/çözünürlük ve **dokunmatik** monitör önerisi.
5. **Çevre birimleri / kurulum:** Kiosk kasası, kablo yönetimi, gerekiyorsa UPS/güç koruması, internet
   (kablolu tercih) gibi tamamlayıcı öneriler.

Her öneride **neden** (hangi teknik gereksinimden dolayı) ve mümkünse **tahmini fiyat aralığı** belirtmesini iste.

---

## 8. Özet (Bir Bakışta)

- **Ne:** Konya Bilim Merkezi için, konuşan/jest yapan **yerel yapay zekâ sergi karakteri** (kiosk).
- **Nasıl çalışır:** Ses/yazı → yerel LLM (Ollama+Qwen) → jest animasyonu + sesli cevap; ayrıca Kelime Türetme oyunu.
- **En kritik donanım:** **Bol VRAM'li ekran kartı** (model + konuşma tanıma + seslendirme aynı makinede).
- **Ortam:** Gürültülü sergi salonu, tek kullanıcı, 7/24 kiosk → **iyi mikrofon, net hoparlör, dokunmatik ekran, dayanıklı PC** gerekir.
- **Planlanan makine:** RTX 5070 Ti 16 GB / 32 GB RAM (doğrulanacak).
