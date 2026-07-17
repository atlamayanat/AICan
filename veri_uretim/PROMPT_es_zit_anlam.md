# Eş/Zıt Anlam — Veri Üretim Promptu

Aşağıdaki promptun **tamamını** kopyalayıp gelişmiş bir AI'ya (Claude, ChatGPT, Gemini)
yapıştır. Dönen JSON'u `yeni_es_zit.json` gibi bir dosyaya **UTF-8** olarak kaydet,
sonra doğrula:

```
python veri_uretim/dogrula.py yeni_es_zit.json
```

Hata yoksa `--yukle` ile devreye al (eskisini otomatik yedekler):

```
python veri_uretim/dogrula.py yeni_es_zit.json --yukle
```

---

## ⇩ KOPYALANACAK PROMPT — BAŞLANGIÇ ⇩

Sen Türkçe sözcük bilgisi çok güçlü bir sözlükbilimcisin (leksikograf). Bir bilim
sergisinde çocukların ve ailelerin bir yapay zekâ karakteriyle oynadığı **"Eş/Zıt
Anlam" oyunu** için soru-cevap veri dosyası üreteceksin. Çıktın doğrudan oyun
motoruna yüklenecek; bu yüzden kurallara harfiyen uyman şart.

### Oyun nasıl işliyor (kuralların sebebi)

- Motor dosyadan rastgele bir kelime seçer ve ziyaretçiye sorar:
  *"'Kelime' kelimesinin eş (veya zıt) anlamlısı ne?"*
- Ziyaretçinin cevabı **yalnızca senin yazdığın listeyle** karşılaştırılır. Listede
  olmayan ama aslında doğru olan bir cevap "yanlış" sayılır ve ziyaretçi haksız yere
  üzülür. Bu oyunun 1 numaralı sorunu budur → her kelime için doğru kabul
  edilebilecek **TÜM tek kelimelik cevapları eksiksiz** yaz.
- Ziyaretçi bilemezse ekranda "Cevap: X" gösterilir; X = listenin **ilk** elemanıdır.
  → İlk eleman her zaman en yaygın, en doğal karşılık olsun.

### Dosya şeması

Tek bir JSON nesnesi; anahtar = sorulacak kelime, değer = kabul edilen cevaplar:

```json
{
  "cesur": {"es": ["yürekli", "yiğit", "korkusuz", "gözüpek", "atılgan"], "zit": ["korkak", "ödlek", "yüreksiz"]},
  "kolay": {"es": ["basit"], "zit": ["zor", "güç", "çetin"]},
  "siyah": {"es": ["kara"], "zit": ["beyaz", "ak"]}
}
```

### SERT KURALLAR — oyun motoru kısıtları (ihlal edilirse veri sessizce bozulur)

1. Anahtarlar ve listelerdeki her öğe **TEK KELİME** olmalı. Boşluklu
   ("iyi kalpli"), tireli ("açık-koyu"), noktalamalı veya rakamlı öğe **KESİNLİKLE
   YASAK** — motor bunları ilk kelimeye kadar kırpar ve fark edilmeden yanlış veri
   oluşur ("iyi kalpli" → "iyi").
2. Her şey **küçük harf**, Türkçe karakterler korunarak (ç ğ ı ö ş ü). Özel isim,
   kısaltma, yabancı yazımlı kelime yok. **Şapkalı harf (â, î, û) KULLANMA** —
   motor bu harfleri bozar; şapka gerektiren kelimeleri ("kâr", "hâlâ", "âdet")
   ne anahtar ne cevap yap.
3. Aynı anahtar dosyada **iki kez geçmesin** (JSON'da ikinci tanım ilkini sessizce
   ezer).
4. Her kayıtta `"es"` ve/veya `"zit"` alanlarından **en az biri dolu** olmalı. Boş
   liste yazma; o tip yoksa alanı hiç koyma.
5. Kelimenin kendisi kendi listelerinde geçmesin; aynı kaydın `es` ve `zit`
   listeleri **kesişmesin**.

### İçerik kuralları

6. Hedef kitle: sergi ziyaretçisi **çocuklar ve aileler (8 yaş ve üzeri)**. Yaygın,
   günlük, herkesin bildiği kelimeler. Argo, kaba, korkutucu, dini/siyasi yüklü
   kelime kullanma.
7. Zorluk dağılımı: yaklaşık **%70 kolay** (siyah–beyaz, büyük–küçük düzeyi),
   **%30 orta** (cömert–cimri düzeyi). Az bilinen/arkaik kelime **anahtar
   olmasın**; ama doğru bir karşılıksa kabul listesine eklenebilir (ör. anahtar
   "eski" olur, "kadim" yalnızca onun kabul listesinde yer alır).
8. Anlamı bağlama göre değişen kelimeleri **anahtar yapma** (ör. "yaş" hem 'ıslak'
   hem 'ömür yılı'; "yüz" hem sayı hem çehre). Soru belirsizleşir. Bu tür kelimeler
   gerekiyorsa yalnızca cevap listelerinde yer alabilir.
9. **KAPSAYICILIK — en kritik kalite kuralı.** Her listede, bir ziyaretçinin makul
   biçimde söyleyebileceği bütün doğru tek kelimelik karşılıklar bulunsun:
   - Olumsuzluk ekiyle türeyenler de zıttır: `"mutlu"` → `"zit": ["üzgün", "mutsuz", "kederli", "mahzun"]`
   - Halk dili / eski ama hâlâ bilinen karşılıklar da kabul edilir: `"siyah"` →
     `"zit": ["beyaz", "ak"]` (ekranda "beyaz" gösterilir, "ak" da kabul edilir).
   - **Simetri:** `"büyük"` kaydında zıt olarak `"küçük"` varsa, `"küçük"` kaydında
     da zıt olarak `"büyük"` olsun.
   - **Çaprazlama:** `"küçük"`ün eşleri (ufak, minik) aynı zamanda `"büyük"`ün
     zıtlarıdır → `"büyük": {"zit": ["küçük", "ufak", "minik"]}`. Bu çaprazlamayı
     tüm çiftlerde uygula.
10. **Doğruluk:** yakın-ama-eş-olmayan kelimeleri `es` listesine koyma. Ölçüt şu:
    *"X'in eş anlamlısı Y'dir"* cümlesi bir Türkçe öğretmenine doğru gelir mi?
    Evet → ekle. Emin değilsen → ekleme. (Çağrışım ≠ eş anlam: "sıcak" ile "yaz"
    eş anlamlı değildir.)
11. Kayıt sayısı: **en az 150, hedef 200**. Kayıtların en az yarısında `"es"` alanı
    da bulunsun (oyun eş anlam sorusu da soruyor).

### Çıktı formatı

- **SADECE geçerli JSON** döndür, tek bir kod bloğu içinde. Öncesinde/sonrasında
  açıklama, başlık, yorum yazma.
- Çift tırnak kullan; sonda virgül bırakma; yorum satırı ekleme.
- Türkçe karakterleri olduğu gibi yaz (`\uXXXX` kaçışı kullanma).
- Uzunluk sınırına takılırsan geçerli bir kaydın sonunda dur; ben "devam" yazınca
  kaldığın kayıttan sürdür (başa dönme, sadece kalan kayıtları yaz).

### Öz-denetim — çıktıyı vermeden önce şunları kontrol et

- [ ] Tüm anahtarlar ve liste öğeleri tek kelime ve küçük harf mi?
- [ ] Mükerrer anahtar var mı?
- [ ] Her listenin ilk elemanı en yaygın karşılık mı?
- [ ] Zıt çiftlerde simetri ve eş-zıt çaprazlaması tamamlandı mı?
- [ ] Yakın-ama-yanlış bir "eş anlamlı" sızdı mı?
- [ ] JSON sözdizimi geçerli mi (parantezler, virgüller)?

### Örnekler

DOĞRU:

```json
"cesur": {"es": ["yürekli", "yiğit", "korkusuz", "gözüpek"], "zit": ["korkak", "ödlek"]}
```

YANLIŞ — yapma:

```json
"iyi kalpli": {"es": ["merhametli"]}        → anahtar çok kelimeli (kırpılır)
"sıcak": {"es": ["yaz"]}                    → çağrışım, eş anlam değil
"mutlu": {"zit": ["üzgün"]}                 → eksik: "mutsuz", "kederli" de doğru cevap (kapsayıcılık ihlali)
"büyük": {"zit": ["küçük"], "es": ["küçük"]} → es ile zit kesişemez
```

Şimdi bu kurallara göre dosyayı üret.

## ⇧ KOPYALANACAK PROMPT — BİTİŞ ⇧
