# AI Body — Jest Rehberi

> Bu rehber **otomatik üretilir**. Elle düzenleme yapma.
> Kaynak: [`ai/gestures.json`](ai/gestures.json)
>
> Yeni jest eklemek/değiştirmek için:
> 1. `ai/gestures.json`'u düzenle
> 2. `cd orchestrator && python build_jest_rehberi.py`
> 3. Bu dosya yeniden yazılır

## Sistem nasıl çalışıyor?

```
Ziyaretçi metin yazar
        ↓
Yerel AI (Ollama / Gemma) tetikleyici örneklerle eşleştirir
        ↓
Tek bir jest seçilir — JSON: {jest_id, yogunluk, yanit}
        ↓
96×96 LED matrisinde animasyon başlar (sonsuz tekrar)
        ↓
Kullanıcı "Durdur" butonuna basana kadar oynar
        ↓
Idle nefes (sakin camgöbeği parıltı) geri gelir
```

**Toplam:** 32 jest, 2 kategori

**Önemli ilkeler** (system_prompt.txt'de detaylı):

- AI kullanıcının duygusunu **kopyalamaz**, kendi tepkisini verir. Kullanıcı "üzgünüm" dediğinde AI da üzülmez — sıcak yaklaşır (`sicaklik`/`dinliyorum`).
- İltifat (`harikasın`) ≠ bilgi onayı (`2+2=4`). İltifata `sicaklik`/`sevgi`/`hayranlik`, bilgiye `onayla_net` seçilir.
- Komut/itaat/manipülasyon istekleri her zaman `reddet_net` ile reddedilir.
- Spor sonuçları, güncel haberler gibi doğrulanamaz olgular → `bilmiyorum`.
- Selamlama ("merhaba", "selam") → `selamlama` (el sallama) veya `sicaklik`.

---

## Hızlı bakış tablosu

### Duygu tepkisi — AI'nin iç durumu (21)

| Görsel | ID | Renk | Süre | Açıklama |
|--------|-----|------|------|----------|
| 😊 | `mutluluk_yogun` | sarı | 3.5sn | Yogun sevinc, cosku, parlayan bir nese hali. |
| ◌ | `mutluluk_sakin` | sarı | 4.0sn | Hafif memnuniyet, ilik bir hosnutluk. |
| ♥ | `sevgi` | pembe | 4.0sn | Sicak yakinlik, sefkat ve yumusak bir baglanma. |
| ⭐ | `hayranlik` | sarı | 4.0sn | Etkileyici bir seyle karsilasildiginda olusan ilgili buyu... |
| 🏀 | `nese` | pembe | 3.5sn | Canli, neseli bir mutluluk; pozitif ve oyunsu bir hal. |
| 🏀 | `kahkaha` | sarı | 3.0sn | Kahkaha; komik bir seye katila katila, yuksek sesle gulme. |
| ○ | `huzur` | açık camgöbeği | 5.0sn | Sakin, dingin, akan zamanin yumusakligi. |
| ◌ | `sicaklik` | turuncu | 4.0sn | Empatik yaklasim, anlayis dolu bir kabul. |
| ↑ | `gurur` | sarı | 3.5sn | Basarinin yukseltici, kendinden hosnut hissi. |
| 💧 | `uzgun_yavas` | mavi | 4.5sn | Hafif uzuntu, ici cekilmis bir durgunluk. |
| ☹ | `uzgun_derin` | soğuk mavi | 5.0sn | Derin keder, agir ve yavas akan bir uzuntu. |
| ● | `yalniz` | soğuk mavi | 6.0sn | Yalnizlik hissi, ice kapanma ve sessiz bir bosluk. |
| ↓ | `hayal_kirikligi` | karışık (130,140,170) | 4.0sn | Beklentinin karsilanmamasi, asagi dogru cekilen bir his. |
| ⚡ | `korku` | karışık (200,200,255) | 3.0sn | Tedirgin, titrek ve dikkat kesilmis bir kaygi. |
| ✨ | `panik` | kırmızı | 2.5sn | Yogun ve ani uyari, savrulan bir kaygi dalgasi. |
| 🔥 | `ofke` | kırmızı | 3.5sn | Rahatsizlik tonunda, sergi senaryosuna uygun olcekli bir ... |
| ╱ | `sikilma` | soğuk mavi | 5.0sn | Duragan, ilgisi azalmis, zaman uzayan bir his. |
| ❗ | `saskinlik` | beyaz | 2.5sn | Beklenmedik bir uyaran karsisinda ani sasirma. |
| ↑ | `merak` | karışık (200,230,60) | 3.5sn | Daha fazlasini ogrenme istegi, ilgili yonelis. |
| ⋯ | `dusunce` | mavi | 4.0sn | Sessiz tartma, isleme, icteki bir oyalanma. |
| ◌ | `meditatif` | soğuk mavi | 6.0sn | Derin sakinlik, ice donuk uzun nefes hissi. |

### Cevap tepkisi — AI'nin iletişimsel yanıtı (11)

| Görsel | ID | Renk | Süre | Açıklama |
|--------|-----|------|------|----------|
| ✓ | `onayla_net` | yeşil | 2.5sn | Net evet, kesin onay, hizla okunan kabul. |
| ✓ | `onayla_sicak` | karışık (150,220,110) | 3.0sn | Sicak kabul, anlayisla beraber gelen onay. |
| ✗ | `reddet_net` | kırmızı | 2.5sn | Net hayir, kesin ret, hizli ve aciklayici. |
| ✗ | `reddet_yumusak` | karışık (110,130,200) | 3.0sn | Nazik ret, mesafeli ama saygili bir geri cekilis. |
| ⇋ | `kararsiz` | sarı | 4.0sn | Iki arada kalmis bir tereddut, sallanan bir cevap. |
| ⋯ | `bilmiyorum` | karışık (150,150,160) | 3.5sn | Bilgi yetmedi, durulmus ve mutevazi bir cevapsizlik. |
| ❓ | `soru_isareti` | sarı | 3.5sn | Karsi soru, anlamak icin geri donus, ilgili bir merak isa... |
| ← | `dinliyorum` | açık camgöbeği | 3.5sn | Devam et sinyali, yatay tarama ile dikkatin acik oldugunu... |
| 🕐 | `bekle` | açık camgöbeği | 4.0sn | Sabret sinyali, isleyen bir bekleme nefesi. |
| 👋 | `selamlama` | sarı | 3.5sn | El sallayarak karsilama; ziyaretciye gorulduğunu hissetti... |
| ¿ | `anlamadim` | karışık (220,200,100) | 3.0sn | Mesaj cozulemedi, tekrar gerekiyor sinyali. |

---

## Detaylı jest açıklamaları

## Duygu tepkisi — AI'nin iç durumu

_AI'nin ic durumunu, hissini, atmosferini gosteren jestler_

### 1. 😊 `mutluluk_yogun`

**Ne yapar:** Yogun sevinc, cosku, parlayan bir nese hali.

**Görsel:** gülen yüz — gözler + yukarı kıvrılan ağız

**Animasyon ayarları:**

- Ana renk: sarı (`#FFE63C`)
- İkincil renk: yok (tek renk)
- Hız: orta tempolu
- Bir döngü süresi: 3.5 saniye (Durdur basılana kadar tekrar eder)
- Yoğunluk: 0.95 (parlaklık çarpanı)

**Ne zaman tetiklenir (ziyaretçi örnek cümleleri):**

- "cok mutluyum"
- "harika bir haber"
- "muthis bir gun gecirdim"
- "kazandim"
- "rüyam gerceklesti"

### 2. ◌ `mutluluk_sakin`

**Ne yapar:** Hafif memnuniyet, ilik bir hosnutluk.

**Görsel:** nabız — tüm ekran sin dalgasıyla parlar/söner

**Animasyon ayarları:**

- Ana renk: sarı (`#F0D264`)
- İkincil renk: yok (tek renk)
- Hız: yavaş
- Bir döngü süresi: 4.0 saniye (Durdur basılana kadar tekrar eder)
- Yoğunluk: 0.60 (parlaklık çarpanı)

**Ne zaman tetiklenir (ziyaretçi örnek cümleleri):**

- "iyiyim"
- "guzel bir gun"
- "keyifliyim"
- "rahatim"
- "hoşuma gitti"

### 3. ♥ `sevgi`

**Ne yapar:** Sicak yakinlik, sefkat ve yumusak bir baglanma.

**Görsel:** atan kalp — iki tümsek + V tabanı, nabız atışı

**Animasyon ayarları:**

- Ana renk: pembe (`#F082A0`)
- İkincil renk: turuncu (`#FFB464`)
- Hız: orta tempolu
- Bir döngü süresi: 4.0 saniye (Durdur basılana kadar tekrar eder)
- Yoğunluk: 0.85 (parlaklık çarpanı)

**Ne zaman tetiklenir (ziyaretçi örnek cümleleri):**

- "seni seviyorum"
- "sana minnettarim"
- "iyi ki varsin"
- "kalbim isiniyor"
- "ailemi ozledim"

### 4. ⭐ `hayranlik`

**Ne yapar:** Etkileyici bir seyle karsilasildiginda olusan ilgili buyulenme.

**Görsel:** yıldız — 8 uçlu pusula + etrafta parıltı

**Animasyon ayarları:**

- Ana renk: sarı (`#FFC33C`)
- İkincil renk: beyaz (`#FFFFFF`)
- Hız: orta tempolu
- Bir döngü süresi: 4.0 saniye (Durdur basılana kadar tekrar eder)
- Yoğunluk: 0.90 (parlaklık çarpanı)

**Ne zaman tetiklenir (ziyaretçi örnek cümleleri):**

- "muhtesem"
- "inanilmaz guzel"
- "etkilendim"
- "hayran kaldim"
- "manzara harikaydi"

### 5. 🏀 `nese`

**Ne yapar:** Canli, neseli bir mutluluk; pozitif ve oyunsu bir hal.

**Görsel:** zıplayan toplar — 4 top farklı tempolarda

**Animasyon ayarları:**

- Ana renk: pembe (`#FF64B4`)
- İkincil renk: sarı (`#FFDC50`)
- Hız: hızlı
- Bir döngü süresi: 3.5 saniye (Durdur basılana kadar tekrar eder)
- Yoğunluk: 0.85 (parlaklık çarpanı)

**Ne zaman tetiklenir (ziyaretçi örnek cümleleri):**

- "cok eglenceli"
- "keyfim yerinde"
- "cocuklarla oynadim"
- "danstayim"
- "icim kipir kipir"

### 6. 🏀 `kahkaha`

**Ne yapar:** Kahkaha; komik bir seye katila katila, yuksek sesle gulme.

**Görsel:** zıplayan toplar — 4 top farklı tempolarda

**Animasyon ayarları:**

- Ana renk: sarı (`#FFDC46`)
- İkincil renk: turuncu (`#FFA028`)
- Hız: çok hızlı
- Bir döngü süresi: 3.0 saniye (Durdur basılana kadar tekrar eder)
- Yoğunluk: 0.95 (parlaklık çarpanı)

**Ne zaman tetiklenir (ziyaretçi örnek cümleleri):**

- "cok komik"
- "guldum"
- "kahkaha attim"
- "espri yaptin"
- "gulmekten kirildim"
- "cok guldum"

### 7. ○ `huzur`

**Ne yapar:** Sakin, dingin, akan zamanin yumusakligi.

**Görsel:** sabit parıltı — tüm ekran yumuşak nefes

**Animasyon ayarları:**

- Ana renk: açık camgöbeği (`#78DCD2`)
- İkincil renk: yok (tek renk)
- Hız: çok yavaş
- Bir döngü süresi: 5.0 saniye (Durdur basılana kadar tekrar eder)
- Yoğunluk: 0.50 (parlaklık çarpanı)

**Ne zaman tetiklenir (ziyaretçi örnek cümleleri):**

- "huzurluyum"
- "rahat bir gece"
- "deniz kenarindayim"
- "sessizlik guzel"
- "dingin bir an"

### 8. ◌ `sicaklik`

**Ne yapar:** Empatik yaklasim, anlayis dolu bir kabul.

**Görsel:** nabız — tüm ekran sin dalgasıyla parlar/söner

**Animasyon ayarları:**

- Ana renk: turuncu (`#FFA050`)
- İkincil renk: kırmızı (`#FF643C`)
- Hız: orta tempolu
- Bir döngü süresi: 4.0 saniye (Durdur basılana kadar tekrar eder)
- Yoğunluk: 0.70 (parlaklık çarpanı)

**Ne zaman tetiklenir (ziyaretçi örnek cümleleri):**

- "merhaba"
- "seni dinliyorum"
- "yanindayim"
- "icten paylasim"
- "tesekkur ederim"

### 9. ↑ `gurur`

**Ne yapar:** Basarinin yukseltici, kendinden hosnut hissi.

**Görsel:** yukarı ok — üçgen baş + kalın gövde

**Animasyon ayarları:**

- Ana renk: sarı (`#F0BE28`)
- İkincil renk: yok (tek renk)
- Hız: orta tempolu
- Bir döngü süresi: 3.5 saniye (Durdur basılana kadar tekrar eder)
- Yoğunluk: 0.85 (parlaklık çarpanı)

**Ne zaman tetiklenir (ziyaretçi örnek cümleleri):**

- "basardim"
- "isimi bitirdim"
- "iyi not aldim"
- "ekibim kazandi"
- "uzun emek karsiligi"

### 10. 💧 `uzgun_yavas`

**Ne yapar:** Hafif uzuntu, ici cekilmis bir durgunluk.

**Görsel:** gözyaşı — yavaşça düşen büyük damla + iz

**Animasyon ayarları:**

- Ana renk: mavi (`#64A0DC`)
- İkincil renk: yok (tek renk)
- Hız: yavaş
- Bir döngü süresi: 4.5 saniye (Durdur basılana kadar tekrar eder)
- Yoğunluk: 0.70 (parlaklık çarpanı)

**Ne zaman tetiklenir (ziyaretçi örnek cümleleri):**

- "biraz uzgunum"
- "moralim bozuk"
- "yorgunum"
- "icim sikildi"
- "iyi degilim"

### 11. ☹ `uzgun_derin`

**Ne yapar:** Derin keder, agir ve yavas akan bir uzuntu.

**Görsel:** üzgün yüz — gözler + aşağı kıvrılan ağız

**Animasyon ayarları:**

- Ana renk: soğuk mavi (`#3C64B4`)
- İkincil renk: yok (tek renk)
- Hız: yavaş
- Bir döngü süresi: 5.0 saniye (Durdur basılana kadar tekrar eder)
- Yoğunluk: 0.75 (parlaklık çarpanı)

**Ne zaman tetiklenir (ziyaretçi örnek cümleleri):**

- "birini kaybettim"
- "cok kotuyum"
- "her sey bitti"
- "kalbim kirik"
- "umutsuzum"

### 12. ● `yalniz`

**Ne yapar:** Yalnizlik hissi, ice kapanma ve sessiz bir bosluk.

**Görsel:** yalnız nokta — tek merkez disk, çok yavaş nefes

**Animasyon ayarları:**

- Ana renk: soğuk mavi (`#7864B4`)
- İkincil renk: yok (tek renk)
- Hız: çok yavaş
- Bir döngü süresi: 6.0 saniye (Durdur basılana kadar tekrar eder)
- Yoğunluk: 0.80 (parlaklık çarpanı)

**Ne zaman tetiklenir (ziyaretçi örnek cümleleri):**

- "kimsem yok"
- "yalnizim"
- "kimse anlamiyor"
- "tek basinayim"
- "konusacak biri yok"

### 13. ↓ `hayal_kirikligi`

**Ne yapar:** Beklentinin karsilanmamasi, asagi dogru cekilen bir his.

**Görsel:** aşağı ok — kalın gövde + üçgen alt

**Animasyon ayarları:**

- Ana renk: karışık (130,140,170) (`#828CAA`)
- İkincil renk: yok (tek renk)
- Hız: yavaş
- Bir döngü süresi: 4.0 saniye (Durdur basılana kadar tekrar eder)
- Yoğunluk: 0.70 (parlaklık çarpanı)

**Ne zaman tetiklenir (ziyaretçi örnek cümleleri):**

- "olmadi"
- "umdugum gibi cikmadi"
- "yine ayni"
- "hayal kirikligina ugradim"
- "yarim kaldi"

### 14. ⚡ `korku`

**Ne yapar:** Tedirgin, titrek ve dikkat kesilmis bir kaygi.

**Görsel:** şimşek — sağ-üst köşeden sol-alta kalın zigzag

**Animasyon ayarları:**

- Ana renk: karışık (200,200,255) (`#C8C8FF`)
- İkincil renk: yok (tek renk)
- Hız: hızlı
- Bir döngü süresi: 3.0 saniye (Durdur basılana kadar tekrar eder)
- Yoğunluk: 0.85 (parlaklık çarpanı)

**Ne zaman tetiklenir (ziyaretçi örnek cümleleri):**

- "korkuyorum"
- "endiseliyim"
- "kotu bir his"
- "tehlike var mi"
- "icim daraliyor"

### 15. ✨ `panik`

**Ne yapar:** Yogun ve ani uyari, savrulan bir kaygi dalgasi.

**Görsel:** kaotik flash — rastgele yoğun parlamalar

**Animasyon ayarları:**

- Ana renk: kırmızı (`#FF3232`)
- İkincil renk: sarı (`#FFC864`)
- Hız: çok hızlı
- Bir döngü süresi: 2.5 saniye (Durdur basılana kadar tekrar eder)
- Yoğunluk: 0.95 (parlaklık çarpanı)

**Ne zaman tetiklenir (ziyaretçi örnek cümleleri):**

- "panik atak"
- "nefes alamiyorum"
- "hemen yardim"
- "her sey ust uste"
- "kontrolum yok"

### 16. 🔥 `ofke`

**Ne yapar:** Rahatsizlik tonunda, sergi senaryosuna uygun olcekli bir hosnutsuzluk.

**Görsel:** ateş — üçgen taban + üstte titreşen alev uçları

**Animasyon ayarları:**

- Ana renk: kırmızı (`#F05014`)
- İkincil renk: sarı (`#FFC832`)
- Hız: orta tempolu
- Bir döngü süresi: 3.5 saniye (Durdur basılana kadar tekrar eder)
- Yoğunluk: 0.90 (parlaklık çarpanı)

**Ne zaman tetiklenir (ziyaretçi örnek cümleleri):**

- "haksizlik"
- "bu kabul edilemez"
- "cok bunaltici"
- "sinirim taşti"
- "yapmayin boyle"

### 17. ╱ `sikilma`

**Ne yapar:** Duragan, ilgisi azalmis, zaman uzayan bir his.

**Görsel:** köşegen tarama — diyagonal bant ekran boyunca

**Animasyon ayarları:**

- Ana renk: soğuk mavi (`#6E6E78`)
- İkincil renk: yok (tek renk)
- Hız: çok yavaş
- Bir döngü süresi: 5.0 saniye (Durdur basılana kadar tekrar eder)
- Yoğunluk: 0.30 (parlaklık çarpanı)

**Ne zaman tetiklenir (ziyaretçi örnek cümleleri):**

- "sikildim"
- "yapacak bir sey yok"
- "ayni seyler"
- "monotonluk"
- "zaman gecmiyor"

### 18. ❗ `saskinlik`

**Ne yapar:** Beklenmedik bir uyaran karsisinda ani sasirma.

**Görsel:** ünlem — kalın dikey çubuk + alttaki nokta

**Animasyon ayarları:**

- Ana renk: beyaz (`#FFFFF0`)
- İkincil renk: karışık (200,220,255) (`#C8DCFF`)
- Hız: hızlı
- Bir döngü süresi: 2.5 saniye (Durdur basılana kadar tekrar eder)
- Yoğunluk: 0.95 (parlaklık çarpanı)

**Ne zaman tetiklenir (ziyaretçi örnek cümleleri):**

- "vay canina"
- "buna inanamiyorum"
- "ciddi misin"
- "nasil yani"
- "hic dusunmemistim"

### 19. ↑ `merak`

**Ne yapar:** Daha fazlasini ogrenme istegi, ilgili yonelis.

**Görsel:** yukarı dalga — yatay bant aşağıdan yukarı

**Animasyon ayarları:**

- Ana renk: karışık (200,230,60) (`#C8E63C`)
- İkincil renk: yeşil (`#78C850`)
- Hız: hızlı
- Bir döngü süresi: 3.5 saniye (Durdur basılana kadar tekrar eder)
- Yoğunluk: 0.65 (parlaklık çarpanı)

**Ne zaman tetiklenir (ziyaretçi örnek cümleleri):**

- "neden boyle"
- "nasil calisiyor"
- "anlat bana"
- "ilginc"
- "daha fazla soyle"

### 20. ⋯ `dusunce`

**Ne yapar:** Sessiz tartma, isleme, icteki bir oyalanma.

**Görsel:** üç nokta — dalgalanan ardışık 3 disk

**Animasyon ayarları:**

- Ana renk: mavi (`#5A8CDC`)
- İkincil renk: yok (tek renk)
- Hız: yavaş
- Bir döngü süresi: 4.0 saniye (Durdur basılana kadar tekrar eder)
- Yoğunluk: 0.50 (parlaklık çarpanı)

**Ne zaman tetiklenir (ziyaretçi örnek cümleleri):**

- "dusunuyorum"
- "tartiyorum"
- "kafamda evirip ceviriyorum"
- "bir sey aklimda"
- "henuz emin degilim"

### 21. ◌ `meditatif`

**Ne yapar:** Derin sakinlik, ice donuk uzun nefes hissi.

**Görsel:** nabız — tüm ekran sin dalgasıyla parlar/söner

**Animasyon ayarları:**

- Ana renk: soğuk mavi (`#28828C`)
- İkincil renk: soğuk mavi (`#145064`)
- Hız: çok yavaş
- Bir döngü süresi: 6.0 saniye (Durdur basılana kadar tekrar eder)
- Yoğunluk: 0.45 (parlaklık çarpanı)

**Ne zaman tetiklenir (ziyaretçi örnek cümleleri):**

- "meditasyon yapiyorum"
- "varolusu dusunuyorum"
- "ic sesim"
- "derin nefes"
- "zaman donuyor"

---

## Cevap tepkisi — AI'nin iletişimsel yanıtı

_AI'nin kullanici mesajina iletisimsel cevabi_

### 1. ✓ `onayla_net`

**Ne yapar:** Net evet, kesin onay, hizla okunan kabul.

**Görsel:** onay — kalın yeşil/sıcak çek işareti çizilir

**Animasyon ayarları:**

- Ana renk: yeşil (`#3CDC50`)
- İkincil renk: yok (tek renk)
- Hız: hızlı
- Bir döngü süresi: 2.5 saniye (Durdur basılana kadar tekrar eder)
- Yoğunluk: 0.85 (parlaklık çarpanı)

**Ne zaman tetiklenir (ziyaretçi örnek cümleleri):**

- "evet"
- "anladim"
- "tamam"
- "kabul"
- "dogru"

### 2. ✓ `onayla_sicak`

**Ne yapar:** Sicak kabul, anlayisla beraber gelen onay.

**Görsel:** onay — kalın yeşil/sıcak çek işareti çizilir

**Animasyon ayarları:**

- Ana renk: karışık (150,220,110) (`#96DC6E`)
- İkincil renk: karışık (255,220,120) (`#FFDC78`)
- Hız: orta tempolu
- Bir döngü süresi: 3.0 saniye (Durdur basılana kadar tekrar eder)
- Yoğunluk: 0.70 (parlaklık çarpanı)

**Ne zaman tetiklenir (ziyaretçi örnek cümleleri):**

- "elbette"
- "tabii ki"
- "seni anliyorum"
- "olur"
- "memnuniyetle"

### 3. ✗ `reddet_net`

**Ne yapar:** Net hayir, kesin ret, hizli ve aciklayici.

**Görsel:** ret — kalın iki köşegen çizilir

**Animasyon ayarları:**

- Ana renk: kırmızı (`#E63232`)
- İkincil renk: yok (tek renk)
- Hız: hızlı
- Bir döngü süresi: 2.5 saniye (Durdur basılana kadar tekrar eder)
- Yoğunluk: 0.85 (parlaklık çarpanı)

**Ne zaman tetiklenir (ziyaretçi örnek cümleleri):**

- "hayir"
- "olmaz"
- "yapamam"
- "yanlis"
- "kabul edemem"

### 4. ✗ `reddet_yumusak`

**Ne yapar:** Nazik ret, mesafeli ama saygili bir geri cekilis.

**Görsel:** ret — kalın iki köşegen çizilir

**Animasyon ayarları:**

- Ana renk: karışık (110,130,200) (`#6E82C8`)
- İkincil renk: yok (tek renk)
- Hız: orta tempolu
- Bir döngü süresi: 3.0 saniye (Durdur basılana kadar tekrar eder)
- Yoğunluk: 0.65 (parlaklık çarpanı)

**Ne zaman tetiklenir (ziyaretçi örnek cümleleri):**

- "su an yapamam"
- "uygun degil"
- "belki sonra"
- "tercih etmem"
- "su an konusmak istemiyorum"

### 5. ⇋ `kararsiz`

**Ne yapar:** Iki arada kalmis bir tereddut, sallanan bir cevap.

**Görsel:** iki renk salınımı — renkler arasında gidip gelir

**Animasyon ayarları:**

- Ana renk: sarı (`#F0C83C`)
- İkincil renk: mavi (`#5082DC`)
- Hız: orta tempolu
- Bir döngü süresi: 4.0 saniye (Durdur basılana kadar tekrar eder)
- Yoğunluk: 0.60 (parlaklık çarpanı)

**Ne zaman tetiklenir (ziyaretçi örnek cümleleri):**

- "bilemedim"
- "ya evet ya hayir"
- "emin degilim"
- "ikisi de olabilir"
- "karar veremiyorum"

### 6. ⋯ `bilmiyorum`

**Ne yapar:** Bilgi yetmedi, durulmus ve mutevazi bir cevapsizlik.

**Görsel:** üç nokta — dalgalanan ardışık 3 disk

**Animasyon ayarları:**

- Ana renk: karışık (150,150,160) (`#9696A0`)
- İkincil renk: yok (tek renk)
- Hız: orta tempolu
- Bir döngü süresi: 3.5 saniye (Durdur basılana kadar tekrar eder)
- Yoğunluk: 0.45 (parlaklık çarpanı)

**Ne zaman tetiklenir (ziyaretçi örnek cümleleri):**

- "bilmiyorum"
- "fikrim yok"
- "elimde bilgi yok"
- "soyleyemem"
- "yanit veremiyorum"

### 7. ❓ `soru_isareti`

**Ne yapar:** Karsi soru, anlamak icin geri donus, ilgili bir merak isareti.

**Görsel:** soru — yuvarlak kanca + dikey gövde + nokta

**Animasyon ayarları:**

- Ana renk: sarı (`#F0DC3C`)
- İkincil renk: karışık (255,255,180) (`#FFFFB4`)
- Hız: orta tempolu
- Bir döngü süresi: 3.5 saniye (Durdur basılana kadar tekrar eder)
- Yoğunluk: 0.75 (parlaklık çarpanı)

**Ne zaman tetiklenir (ziyaretçi örnek cümleleri):**

- "ne demek istedin"
- "tam anlamadim"
- "biraz acabilir misin"
- "neden"
- "hangisini kastettin"

### 8. ← `dinliyorum`

**Ne yapar:** Devam et sinyali, yatay tarama ile dikkatin acik oldugunu gosterir.

**Görsel:** sola dalga — dikey bant sağdan sola

**Animasyon ayarları:**

- Ana renk: açık camgöbeği (`#78DCDC`)
- İkincil renk: yok (tek renk)
- Hız: orta tempolu
- Bir döngü süresi: 3.5 saniye (Durdur basılana kadar tekrar eder)
- Yoğunluk: 0.60 (parlaklık çarpanı)

**Ne zaman tetiklenir (ziyaretçi örnek cümleleri):**

- "anlat"
- "dinliyorum"
- "devam et"
- "buradayim"
- "seni duyuyorum"

### 9. 🕐 `bekle`

**Ne yapar:** Sabret sinyali, isleyen bir bekleme nefesi.

**Görsel:** saat — 12 marker + dönen ibre

**Animasyon ayarları:**

- Ana renk: açık camgöbeği (`#8CC8F0`)
- İkincil renk: yok (tek renk)
- Hız: orta tempolu
- Bir döngü süresi: 4.0 saniye (Durdur basılana kadar tekrar eder)
- Yoğunluk: 0.70 (parlaklık çarpanı)

**Ne zaman tetiklenir (ziyaretçi örnek cümleleri):**

- "biraz bekle"
- "sabret"
- "isleniyor"
- "dusunuyorum"
- "bir saniye"

### 10. 👋 `selamlama`

**Ne yapar:** El sallayarak karsilama; ziyaretciye gorulduğunu hissettiren sicak bir selam.

**Görsel:** el sallama — 4 parmaklı el bileğinden sağ/sol

**Animasyon ayarları:**

- Ana renk: sarı (`#FFD73C`)
- İkincil renk: beyaz (`#FFFFFF`)
- Hız: orta tempolu
- Bir döngü süresi: 3.5 saniye (Durdur basılana kadar tekrar eder)
- Yoğunluk: 0.85 (parlaklık çarpanı)

**Ne zaman tetiklenir (ziyaretçi örnek cümleleri):**

- "selam"
- "merhaba"
- "gunaydin"
- "iyi aksamlar"
- "naber"
- "hos geldin"

### 11. ¿ `anlamadim`

**Ne yapar:** Mesaj cozulemedi, tekrar gerekiyor sinyali.

**Görsel:** sallanan soru — soru işareti rastgele kayar

**Animasyon ayarları:**

- Ana renk: karışık (220,200,100) (`#DCC864`)
- İkincil renk: yok (tek renk)
- Hız: orta tempolu
- Bir döngü süresi: 3.0 saniye (Durdur basılana kadar tekrar eder)
- Yoğunluk: 0.65 (parlaklık çarpanı)

**Ne zaman tetiklenir (ziyaretçi örnek cümleleri):**

- "asdfgh"
- "????"
- "anlamadim"
- "rastgele harfler"
- "bos mesaj"

---

## Not

- Tetikleyici örnekleri **kesin eşleşme değil** — AI semantik benzerliğe bakar. "merhaba" ile "selamünaleyküm" aynı jeste düşebilir.
- Sistemde yanlış jest seçildiğini fark edersen `ai/system_prompt.txt`'deki örneklere ekleme yap; gerekirse `python build_model.py` çalıştır.
- Yeni desen (görsel animasyon) eklemek için `orchestrator/gesture_engine.py`'de `pat_*` fonksiyonu ve `PATTERN_DISPATCH` kaydı oluştur, sonra gestures.json'a yeni jesti ekleyip bu scripti çalıştır.
