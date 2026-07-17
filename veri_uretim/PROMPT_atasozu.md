# Atasözü Tamamlama — Veri Üretim Promptu

Aşağıdaki promptun **tamamını** kopyalayıp gelişmiş bir AI'ya (Claude, ChatGPT, Gemini)
yapıştır. Dönen JSON'u `yeni_atasozu.json` gibi bir dosyaya **UTF-8** olarak kaydet,
sonra doğrula:

```
python veri_uretim/dogrula.py yeni_atasozu.json
```

Hata yoksa `--yukle` ile devreye al (eskisini otomatik yedekler):

```
python veri_uretim/dogrula.py yeni_atasozu.json --yukle
```

---

## ⇩ KOPYALANACAK PROMPT — BAŞLANGIÇ ⇩

Sen Türk halk edebiyatı ve atasözleri konusunda uzman bir Türkolog'sun. Bir bilim
sergisinde çocukların ve ailelerin bir yapay zekâ karakteriyle oynadığı **"Atasözü
Tamamlama" oyunu** için veri dosyası üreteceksin. Çıktın doğrudan oyun motoruna
yüklenecek; kurallara harfiyen uyman şart.

### Oyun nasıl işliyor (kuralların sebebi)

- Motor bir atasözünün başını gösterir: *"'Damlaya damlaya …' nasıl devam eder?"*
- Ziyaretçi devamını söyler; cevap senin yazdığın `tamam` listesindeki öğelerle
  esnek biçimde karşılaştırılır. Esneklik kuralı: **söylenen metnin içinde öğe
  geçiyorsa YA DA söylenen metin öğenin içinde geçiyorsa doğru sayılır** — bu
  yüzden öğeler ayırt edici olmalı; tek başına yaygın bir kelime olan öğe, o
  kelimeyi içeren her yanlış cevabı da doğru saydırır.
- Ziyaretçi bilemezse ekranda **"Cevap: {bas} {tamam[0]}"** gösterilir → yani
  `bas` + boşluk + listenin ilk öğesi birleşince atasözünün **tam ve doğal hali**
  okunmalı.

### Dosya şeması

JSON dizisi; her öğe bir atasözü:

```json
[
  {"bas": "Damlaya damlaya", "tamam": ["göl olur"]},
  {"bas": "İşleyen demir", "tamam": ["ışıldar", "pas tutmaz"]},
  {"bas": "Ağaç yaşken", "tamam": ["eğilir"]}
]
```

### SERT KURALLAR

1. **SADECE gerçek, yerleşik Türk atasözleri.** Ölçüt: TDK Atasözleri ve Deyimler
   Sözlüğü'nde geçen biçim. **ASLA** atasözü uydurma, iki atasözünü birleştirme,
   sözcüklerini değiştirme. Bu dosyanın var olma sebebi, uydurma/yanlış içeriği
   tamamen engellemek. Emin olmadığın atasözünü **hiç yazma** — eksik dosya, yanlış
   dosyadan iyidir.
2. **Kanonik biçim:** atasözünün en yaygın söylenişini kullan.
3. `bas` + boşluk + `tamam[0]` birleşince atasözünün tamamı düzgün ve doğal
   okunmalı (ekranda aynen böyle gösterilir).
4. `bas` **en az 2 kelime** olsun ve atasözünü tanımaya yetsin; sonunda **HİÇBİR
   noktalama işareti olmasın** (nokta, virgül, üç nokta, soru ve ünlem işareti
   dahil — motor "…" işaretini kendisi ekler).
5. `tamam` öğeleri kısa ve **ayırt edici** olsun: **1–5 kelime**, en kısa öğe en
   az 4 harf. Tek kelimelik öğe ancak ayırt edici bir kelime olabilir ("ışıldar"
   gibi); **tek başına yaygın bir fiil ("olur", "olmaz", "gelir", "eder") ASLA
   öğe olamaz** — devam yaygın bir fiille bitiyorsa bölme noktasını sola kaydır,
   cevap en az 2 kelime olsun ("göl olur"). Öğelerin **içinde noktalama
   kullanma** (kesme işareti, tire, ünlem); kesme işaretli kelime içeren
   atasözlerini tercih etme. Yaygın söyleyiş varyantları varsa hepsini ekle
   (ör. "İşleyen demir" → `["ışıldar", "pas tutmaz"]`).
6. Cevap (`tamam` öğeleri) `bas`ın içinde geçmesin.
7. Her atasözü listede **bir kez** geçsin — aynı atasözünü farklı bölme noktasıyla
   tekrar yazmak da mükerrerdir; anlamca aynı olan varyant atasözlerinden yalnızca
   en yaygın biçimi al. `bas` değerleri benzersiz olmalı.
8. **Aile dostu seçim:** kaba, argo, şiddet içeren veya ayrımcı atasözlerini alma
   (ör. "Kızını dövmeyen dizini döver" gibi sorunlu olanlar KESİNLİKLE alınmaz).
9. **Bölme noktası:** atasözünün en akılda kalan, karakteristik kısmı cevap
   tarafında kalsın. Ziyaretçi `bas`ı duyunca "haa, şu atasözü!" diyebilmeli.
   Sayı kelimeleri ("bir", "kırk", "bin") mümkünse `bas` tarafında kalsın;
   cevapta sayı kelimesi kalıyorsa rakamlı varyantı da ekle (sesli giriş rakam
   yazabilir): `["kırk yıl hatırı vardır", "40 yıl hatırı vardır"]`.
10. Sayı: **en az 100, hedef 120.** Yaklaşık %80'i herkesin bildiği çok yaygın
    atasözleri, %20'si orta bilinirlikte olsun (ziyaretçiler çocuklu aileler;
    bilinen atasözü eğlencelidir, hiç duyulmamış olan can sıkar).

### Çıktı formatı

- **SADECE geçerli JSON** döndür, tek bir kod bloğu içinde. Öncesinde/sonrasında
  açıklama, başlık, yorum yazma.
- Çift tırnak kullan; sonda virgül bırakma; yorum satırı ekleme.
- Türkçe karakterleri olduğu gibi yaz (`\uXXXX` kaçışı kullanma).
- Uzunluk sınırına takılırsan geçerli bir öğenin sonunda dur; ben "devam" yazınca
  kaldığın öğeden sürdür (başa dönme, sadece kalan öğeleri yaz).

### Öz-denetim — çıktıyı vermeden önce şunları kontrol et

- [ ] Her atasözü gerçek ve kanonik biçimde mi? (Uydurma ya da değiştirilmiş söz var mı?)
- [ ] `bas` + `tamam[0]` birleşimi doğal, tam bir atasözü mü?
- [ ] Mükerrer atasözü var mı (farklı bölünmüş kopyalar dahil)?
- [ ] `bas` sonlarında noktalama kaldı mı?
- [ ] Kaba/şiddet içerikli söz sızdı mı?
- [ ] JSON sözdizimi geçerli mi?

### Örnekler

DOĞRU:

```json
{"bas": "Sakla samanı", "tamam": ["gelir zamanı"]}
{"bas": "Bir elin nesi var", "tamam": ["iki elin sesi var"]}
```

YANLIŞ — yapma:

```json
{"bas": "Sakla samanı gelir zamanı", "tamam": ["bir gün sana yarar"]}  → atasözü uzatılıp uydurulmuş
{"bas": "Damlaya damlaya göl", "tamam": ["olur"]}                      → bölme noktası kötü: karakteristik kısım ("göl olur") cevap tarafında kalmalı; tek başına "olur" yanlış cevapları da doğru saydırır
{"bas": "Ağaç yaşken…", "tamam": ["eğilir"]}                           → bas sonunda noktalama var
{"bas": "Bir elin", "tamam": ["nesi var iki elin sesi var"]}           → "Bir elin nesi var" zaten listedeyse farklı bölme noktası da MÜKERRERDİR
```

Şimdi bu kurallara göre dosyayı üret.

## ⇧ KOPYALANACAK PROMPT — BİTİŞ ⇧
