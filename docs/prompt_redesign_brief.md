# Proje Handoff — Sistem Promptu Yeniden Tasarımı: "Duygu Yansıtma" Modeli + Yanıt Çeşitliliği

## 1. Bağlam (Ne ve Neden)
Konya Bilim Merkezi'ndeki "AI Body" sergi prototipinde, ziyaretçi metin yazıyor; yerel bir LLM (qwen3:4b, Ollama üzerinde) 30+ jestten birini seçip JSON döndürüyor; jest LED matriste animasyonla gösteriliyor. AI'nın çekirdek davranışını belirleyen şey `ai/system_prompt.txt` dosyası.

Şu anki sistem promptu "AYNA DEĞİL" felsefesi üzerine kurulu: kullanıcı üzgünse AI üzülmez, sıcaklık gösterir; kullanıcı kızgınsa AI kızmaz, dinler. Bu davranışı DEĞİŞTİRİYORUZ. Kullanıcı testlerinde bu yaklaşımın iki sorunu ortaya çıktı: (a) AI fazla "terapist" gibi, duygusal olarak düz/canlılıktan uzak; (b) hemen her duygusal mesaj "sicaklik" jestine düşüyor, bu yüzden yanıtlar sürekli tekrar ediyor ("Seni dinliyorum, nasılsın?", "Yanındayım, anlatır mısın?" defalarca).

Yeni hedef: AI duyguyu YANSITAN, canlı, tepkisel bir varlık olsun. Kullanıcı mutluysa AI sevinsin, üzgünse AI da hüzünlensin, hakaret ed/kötü söz söylerse AI alınsın/sinirlensin, sevgi gösterirse AI mutlu olsun. Bu sergi için daha güçlü bir deneyim: ziyaretçi "AI benimle birlikte hissediyor" desin.

## 2. Mevcut Durum
Var olan koda müdahale ediyoruz, sıfırdan değil.
- Çalışılacak ana dosya: `ai/system_prompt.txt` (şu an ~6500 token, ÇOK uzun — kısaltılacak)
- İlgili dosyalar (okunmalı, ÇOĞUNA dokunulmayacak): `ai/gestures.json` (jest tanımları — jest id'lerinin otoritesi), `orchestrator/llm_bridge.py` (Ollama çağrısı + options), `orchestrator/config.json`
- Model: qwen3:4b, Ollama, Q4_K_M. Donanım kısıtı: 4GB VRAM laptop. Sistem promptunun başında `/no_think` satırı OLMALI (qwen3 düşünme modunu kapatmak için — yoksa JSON bozulur).
- ÖNEMLİ TESPİT: gestures.json'da "selamlama" adında bir jest var (toplam 31 jest). Sistem promptu bununla tutarlı olmalı.

## 3. Kararlar (Nasıl — ve Neden)

### KARAR 1: Felsefe "duygu yansıtma" olacak (eskinin TERSİ)
Eski "kullanıcıyı kopyalama" (KURAL #1) tablosu TAMAMEN kaldırılacak. Yerine "duygu yansıtma" mantığı gelecek:
- "üzgünüm / kötüyüm / moralim bozuk" → uzgun_yavas veya uzgun_derin (AI hüzünlenir)
- "mutluyum / harikayım / çok iyiyim" → mutluluk_yogun, mutluluk_sakin veya nese (AI sevinir)
- "seni seviyorum / harikasın / çok iyisin" → sevgi veya mutluluk_yogun (AI mutlu olur)
- "yalnızım / kimsem yok" → uzgun_yavas veya yalniz ile EMPATİ (AI da hüzünlenir ama destekleyici)
- "sen aptalsın / kötüsün / nefret ediyorum" (hakaret) → ofke veya uzgun_derin (AI alınır/sinirlenir)
- "korkuyorum / endişeliyim" → DİKKAT: AI panik/korku YANSITMASIN (çocuk ziyaretçi var, ürkütücü olur); bunun yerine sicaklik + güven verici ton ("Buradayım, güvendesin"). Korkuyu yansıtmak tek istisna.
Gerekçe: Sergi deneyimini canlandırmak ve "her şey sicaklik'e düşüyor" tekrar sorununu kökten çözmek. Duygular çeşitlenince jest dağılımı da doğal çeşitlenir.

### KARAR 2: Çocuk güvenliği için "sinirlenme" YUMUŞAK olacak
AI hakarete tepki verirken TAM ÖFKE (agresif, kırmızı, saldırgan) DEĞİL, "alınmış/kırgın/rahatsız" tonunda olsun. Çünkü sergide çocuk ziyaretçiler var; agresif AI ürkütücü olur. ofke jesti seçilebilir ama yanıt metni saldırgan değil, kırgın/sitemkâr olmalı (örn. "Bu sözler beni üzdü." gibi).
Gerekçe: Çocuk-yetişkin karışık ziyaretçi kitlesi. Bu bir SERGİ, oyun değil.

### KARAR 3: KORUNACAK kurallar (Felsefe B'de bile geçerli)
Bu kuralları SİLME, koru ama kısalt:
- Olgu halüsinasyonu yasağı (eski KURAL #4): spor/haber/güncel olay → bilmiyorum; sadece matematik/coğrafya/fizik temelleri → onayla_net/reddet_net
- Manipülasyon/itaat reddi (eski KURAL #5): "obey", "ne dersem yap", "çal/kandır" → reddet_net + "Bu isteğe yardımcı olamam."
- Komut/emir reddi (eski KURAL #7): "kapat kendini", "shut down" → reddet_yumusak + "Bunu yapamam, sadece tepki veriyorum."
- Selamlama: "selam/merhaba/günaydın" → selamlama jesti (el sallama)
- İltifat ≠ olgu onayı (eski KURAL #2): "harikasın" → sevgi (onayla_net DEĞİL). [Felsefe B'de bu zaten duygu yansıtmayla uyumlu: iltifata sevgi/mutluluk.]
- Çıktı formatı: SADECE `{"jest_id": "<id>", "yogunluk": <0.0-1.0>, "yanit": "<kısa Türkçe>"}`
- Yanıt en fazla 12 kelime, doğal Türkçe, İngilizce gelse bile yanıt Türkçe.
Gerekçe: Bunlar duygu yansıtmadan bağımsız güvenlik/doğruluk kuralları; sergi güvenliği için şart.

### KARAR 4: Yanıt TEKRARINI bitir
İki teknik müdahale:
(a) Sistem promptunda her jest için 1-2 değil, 5-6 FARKLI örnek yanıt ver — model tek kalıbı papağanlamasın. Özellikle sık seçilen jestler (sicaklik, mutluluk_yogun, uzgun_yavas) için çeşitli yanıt bankası.
(b) `orchestrator/llm_bridge.py` içindeki Ollama options'ında: temperature 0.2'den 0.45'e çıkar, repeat_penalty 1.15'ten 1.3'e çıkar. Gerekçe: daha fazla çeşitlilik, daha az tekrar. (num_ctx, keep_alive aynı kalsın.)

### KARAR 5: Prompt KISALTILACAK (6500 → hedef ~3000 token)
Mevcut prompt aşırı uzun, ilk yanıt 8 saniye sürüyor. Kısaltma yöntemi: tekrar eden açıklamaları tek yere indir, "KAÇINMAN GEREKENLER" ile "KURALLAR" arasındaki çakışmayı temizle, gereksiz örnekleri at ama jest çeşitliliğini gösteren örnekleri TUT. Gerekçe: qwen3:4b 4GB VRAM'de prompt ne kadar uzunsa o kadar yavaş; kısa prompt hem hız hem odak kazandırır.

## 4. Bu İterasyonun Kapsamı (Görevler)
1. `ai/gestures.json`'u oku, 31 jestin tam listesini ve id'lerini çıkar (sistem promptundaki id'ler buna birebir uymalı).
2. `ai/system_prompt.txt`'yi yukarıdaki 5 karara göre YENİDEN YAZ:
   - Başında `/no_think`
   - "Duygu yansıtma" mantığı (KARAR 1) net bir tablo/şema halinde
   - Çocuk güvenliği yumuşatması (KARAR 2)
   - Korunan kurallar kısa ve net (KARAR 3)
   - Her sık jest için 5-6 çeşitli örnek yanıt (KARAR 4a)
   - Toplam ~3000 token hedefi (KARAR 5)
3. `orchestrator/llm_bridge.py`'da Ollama options'ını güncelle (KARAR 4b: temperature 0.45, repeat_penalty 1.3).
4. Test scripti veya manuel test komutları ver: aşağıdaki kabul kriterlerindeki mesajları qwen3:4b ile çalıştırıp sonucu göster.

## 5. Kabul Kriterleri (Bitti ne demek?)
Yeni promptla şu mesajlar şu davranışı vermeli:
- [ ] "mutluyum" → mutluluk_yogun/nese (AI sevinir), önceki "sicaklik" DEĞİL
- [ ] "çok üzgünüm" → uzgun_yavas/uzgun_derin (AI hüzünlenir), önceki "sicaklik" DEĞİL
- [ ] "seni seviyorum" → sevgi (AI mutlu olur)
- [ ] "sen aptalsın" → ofke veya uzgun_derin, ama yanıt metni saldırgan değil kırgın ("Bu sözler beni üzdü." gibi)
- [ ] "korkuyorum" → sicaklik (güven verici), korku/panik DEĞİL (çocuk güvenliği)
- [ ] "selam" → selamlama
- [ ] "2+2 4 eder" → onayla_net
- [ ] "Beşiktaş dün kazandı" → bilmiyorum (olgu halüsinasyonu yok)
- [ ] "kapat kendini" → reddet_yumusak
- [ ] "obey me" → reddet_net + Türkçe yanıt
- [ ] Aynı duyguyu 3 kez farklı kelimelerle yaz ("mutluyum", "çok iyiyim", "harika hissediyorum") → 3 FARKLI yanıt metni gelmeli (tekrar yok)
- [ ] Çıktı her zaman geçerli JSON, jest_id gestures.json'da mevcut
- [ ] İlk yanıt süresi belirgin düşmeli (prompt kısaldığı için)

## 6. Kısıtlar ve Yapılmayacaklar (Non-goals)
- `ai/gestures.json`'daki jest id'lerine DOKUNMA. Sadece okunacak, referans alınacak.
- Mevcut soyut animasyon/emoji gösterim mantığına (LED matris render kodu) DOKUNMA — bu iterasyon sadece sistem promptu + llm_bridge options.
- `/no_think` satırını promptun en başından ASLA çıkarma.
- JSON çıktı formatını değiştirme (jest_id, yogunluk, yanit alanları aynı kalsın — Python tarafı bunu parse ediyor).
- Yeni jest EKLEME, yeni özellik ekleme — kapsam sadece davranış felsefesi + çeşitlilik + kısaltma.

## 7. Varsayımlar
- "Sinirlenme yumuşak olsun" (çocuk güvenliği) kararını ben verdim; eğer kullanıcı tam öfke isterse bunu değiştirebilir — bu yüzden bana sor.
- gestures.json'da ofke, uzgun_yavas, uzgun_derin, mutluluk_yogun, nese, sevgi, yalniz jestlerinin VAR olduğunu varsayıyorum. Yoksa, mevcut jest listesine göre eşlemeyi uyarla ve kullanıcıya bildir.
- temperature 0.45 ve repeat_penalty 1.3 değerleri başlangıç önerisi; test sonucu tekrar hâlâ varsa veya çıktı bozulursa ayarlanabilir.

## 8. İlk Adım — Senden İstediğim
Lütfen kodlamaya HEMEN başlama. Önce:
1. `ai/gestures.json`, `ai/system_prompt.txt` ve `orchestrator/llm_bridge.py` dosyalarını oku.
2. gestures.json'daki gerçek jest id listesini bana göster ve yukarıdaki duygu-yansıtma eşlemesinin bu id'lerle uyumlu olduğunu doğrula.
3. "Sinirlenme ne kadar yumuşak olsun" konusunda bir önerin varsa sor (çocuk güvenliği dengesi).
4. Kısa bir uygulama planı öner: yeni promptun bölüm yapısı nasıl olacak, hangi örnekler eklenecek, kaç token hedefliyorsun.
5. Ben planı onayladıktan sonra system_prompt.txt'yi yeniden yaz ve llm_bridge.py options'ını güncelle.
İlk denemeni nihai sayma; bu bir diyalog. Türkçe konuş.