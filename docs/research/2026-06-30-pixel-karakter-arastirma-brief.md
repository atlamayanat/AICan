# Araştırma Brief'i — Sergi AI'sı için Pixel-Art Karakter (3. Tepki Tipi)

> **Bu dosya bir ARAŞTIRMA TALİMATIDIR.** Claude'a (web / deep research) verilecek; amacı, aşağıda
> tanımlanan probleme **derinlemesine, kaynaklı ve uygulanabilir** bir araştırma raporu ürettirmektir.
> Kod yazman istenmiyor — **karar verdirecek bilgi, somut seçenekler, linkler, lisanslar ve bir entegrasyon yolu** istiyoruz.
> Repoya erişimin yok; ihtiyacın olan tüm bağlam bu dosyada. Türkçe yanıt ver; arama terimleri İngilizce olabilir.

---

## 1. Proje nedir? (bağlam)

**aican**, Konya Bilim Merkezi'nde sergilenecek etkileşimli bir yapay-zekâ ünitesinin yazılım prototipidir.
Sergi sorusu: **"Yapay zekânın duyguları var mı?"** Ziyaretçi (çoğunlukla çocuklar dahil genel kitle)
AI ile yazılı/sesli Türkçe etkileşir; AI **duygusal tepkiler** verir (sevinir, üzülür, şaşırır, kırılır)
ve küçük oyunlar oynar (Taş-Kağıt-Makas, Kelime Türetme, Bilgi Yarışması). Serginin kalbi:
**AI'nın bir "beden" üzerinden duygularını görsel olarak ifade etmesi.**

Teknik özet:
- Yerel LLM (Ollama, `gemma3:4b`) ziyaretçi metnine karşılık bir **jest** (duygu/ifade) seçer ve kısa bir söz üretir.
- Bir **TTS** katmanı sözü duyguya göre tonlanmış sesle okur.
- Bir **görsel beden** seçilen jestin animasyonunu oynatır. ← **Bu araştırma tam olarak burayla ilgili.**
- Tamamen **yerel/çevrimdışı** çalışması beklenir (sergide internet garanti değil).

---

## 2. Mevcut görsel mimari (kritik — yeni çözüm buna oturmalı)

Görsel beden, **tarayıcıda çalışan bir web uygulaması**dır (vanilla JS + HTML5 Canvas; Flask sunucu statik dosyaları sunar).
Şu an **96×96'lık yazılımsal bir "LED matris"** Canvas üzerine render edilir (glow/bloom efektli).

Şu anda **2 farklı "tepki çeşidi" (görsel mod)** var, ikisi de aynı veri modelinden sürülür:

1. **`desen` (pattern) modu:** ~36 sembolik şekil/animasyon, matematiksel olarak çizilir.
   Her desen bir fonksiyondur: `(x, y, t, ana_renk, ikincil_renk, hız, yoğunluk) -> [r, g, b, a]`.
   Örnekler: gülen yüz, üzgün yüz, kalp, ünlem, soru işareti, alev, şimşek, nabız, dalga…
2. **`emoji` modu:** Önceden hazırlanmış PNG kare dizileri (`assets/emojis/<jest_id>/frame_00.png …`),
   ~12 fps oynatılır; bir manifest her jestin kare sayısını tutar.

Ek olarak boştayken çalışan **otonom "canlı göz" (EyeSystem)** animasyonu var (RoboEyes mantığından ilham,
kod tamamen projeye özel; kırpma/bakınma/uyku gibi durumlar). Mod boştayken patterns/emoji devre dışı, göz oynar.

### Veri modeli — HER görsel çözüm bunun üzerinden sürülmeli
Tek doğruluk kaynağı `gestures.json`: **31 jest**. Her jestin alanları (özet):
- `id` (örn. `mutluluk_yogun`), `kategori` (`duygu_tepkisi` | `cevap_tepkisi`), `aciklama`, `tetikleyiciler`.
- **`duygu_valansi`** (valence, −1…+1): olumlu/olumsuz.
- **`uyarilma_seviyesi`** (arousal, 0…1): sakin/uyarılmış.
- **`gorsel_tipi`**: `"emoji"` veya `"desen"` (o jestin hangi modda çizileceği).
- **`emoji_kaynak`**: unicode kod (örn. `1f604`).
- **`animasyon`**: `{ ana_renk:[r,g,b], ikincil_renk, desen:"smile_face", hiz:"orta", sure_sn:3.5, yogunluk_varsayilan:0.95 }`.

**Önemli:** LLM çıktısı = bir `jest_id` + bir `yogunluk` (0–1). Yeni karakter sistemi de **bu 31 jest_id'den
herhangi birine + bir yoğunluk değerine** karşılık bir ifade/animasyon üretebilmeli. Yani karakterin
**31 ifadeyi (veya valence/arousal'a göre türetilmiş bir ifade uzayını) kapsaması** gerekir.

### 31 jestin duygu yelpazesi (karakterin ifade etmesi gerekenler)
- **Olumlu/yoğun:** mutluluk_yogun, nese, hayranlik, sevgi, gurur
- **Olumlu/sakin:** mutluluk_sakin, huzur, sicaklik, meditatif
- **Olumsuz/hüzün:** uzgun_yavas, uzgun_derin, yalniz, hayal_kirikligi
- **Olumsuz/uyarılmış:** ofke, korku, panik
- **Nötr/bilişsel:** saskinlik, merak, dusunce, kararsiz, bilmiyorum, sikilma
- **İletişimsel (cevap):** onayla_net, onayla_sicak, reddet_net, reddet_yumusak, soru_isareti, dinliyorum, bekle, selamlama, anlamadim

---

## 3. Ne eklemek istiyorum? (hedef)

Mevcut **desen** ve **emoji** modlarının yanına **3. bir tepki çeşidi**: **sabit, tutarlı bir 2D PIXEL-ART
KARAKTER**. Bu karakter AI'nın "yüzü/bedeni" olur ve **tüm jestleri/mimikleri onun üzerinden** sergiler
(sevinince güler, üzülünce ağlar/somurtur, şaşırınca irkilir, düşününce başını eğer, selam verir, vb.) —
ayrıca boştayken doğal idle mimikleri (nefes, göz kırpma, bakınma) yapar.

Amaç: emoji/desen'e göre **daha kişilikli, "canlı bir varlık" hissi** veren tek bir karakter kimliği.
Ziyaretçi "bu AI'nın bir karakteri var ve gerçekten hissediyor gibi" duygusuna kapılsın (sergi temasıyla birebir).

Bu araştırma **detaylı** olmalı çünkü iki büyük belirsizlik var:
1. **Hazır mı?** Tüm bu duygu yelpazesini kapsayan, animasyonlu, lisansı sergi/ticari kullanıma uygun
   **hazır 2D pixel-art karakter varlıkları** var mı? Nerede, hangi formatta, ne kapsamda, ne lisansla?
2. **Kendimiz mi yaparız?** Yoksa bu karakteri (ve 31 ifadeyi) **kendimiz mi üretmeliyiz**? Hangi araç/iş akışıyla,
   ne kadar emekle, hangi beceriyle? (AI-destekli pixel-art üretimi dahil.)

---

## 4. Kısıtlar ve gereksinimler (çözüm bunlara UYMALI)

1. **Render ortamı:** Tarayıcı, **HTML5 Canvas 2D** (vanilla JS). Mevcut hatta oturmalı; ağır 3D/WebGL motoru
   (Unity/Godot web export gibi) tercih edilmez — hafif olmalı. (Eğer güçlü bir gerekçe varsa WebGL2 tartışılabilir.)
2. **Donanım:** Sergi makinesi **RTX 3050 Ti Laptop, 4GB VRAM, 16GB RAM**. GPU zaten Ollama + STT ile dolu;
   karakter render'ı **CPU/Canvas'ta hafif** olmalı (GPU'ya yük bindirmemeli).
3. **Çevrimdışı:** Tüm varlıklar **yerel paketlenmeli** (sergide internet yok varsay). Çalışma anında bulut/asset-CDN yok.
4. **Veri-güdümlü eşleme:** Karakter, **31 jest_id + yoğunluk(0–1)** ile sürülebilmeli (bkz. §2 veri modeli).
   İdeali: her jest için bir ifade/animasyon; yoğunluk ifadenin şiddetini ölçekleyebilir.
   Valence/arousal ile **türetilmiş** (daha az asset, formülle ölçeklenen) bir yaklaşım da değerlendirilmeli.
5. **Tek tutarlı kimlik:** Tüm ifadeler **aynı karakter**e ait, tutarlı stil. (31 ilgisiz sprite değil.)
6. **Boşta (idle) davranış:** Nefes/göz kırpma/bakınma gibi otonom mikro-animasyonlar (mevcut EyeSystem'in yerini
   alabilir veya onunla bütünleşebilir).
7. **Kitle:** Müze + çocuklar. **Ürkütücü/agresif olmayan**, sevimli, uzaktan okunur (sergi mesafesi) bir stil.
8. **Mevcut yapıyı bozma:** Çekirdek sohbet/oyun mantığı değişmeyecek; bu **ek bir görsel mod** (3. seçenek);
   desen/emoji modları kalmalı (mod seçimi `gorsel_tipi` benzeri bir anahtarla yapılıyor).
9. **Çözünürlük/yerleşim açık sorusu:** Mevcut beden 96×96. Karakter 96×96'ya mı sığacak (küçük), yoksa sergi
   ekranında **daha büyük ayrı bir karakter alanı** mı olmalı? (Araştırma bunu da ele alsın — pixel-art tipik
   çözünürlükleri 32×32 / 64×64 / 128×128 vs. ve sergi mesafesinde okunurluk.)
10. **Lisans:** Sergi kamuya açık ve kurumsal; kullanılacak her varlık/araç için **ticari/kamusal kullanım
    lisansı net olmalı** (CC0/CC-BY/satın alınmış telifsiz vb.; "yalnızca kişisel kullanım" ya da
    atıf/pay-share kısıtları varsa açıkça belirt).

---

## 5. Araştırma soruları (cevaplanması gerekenler)

### A) Hazır varlık yolu
1. Bu duygu yelpazesini kapsayan **hazır animasyonlu 2D pixel-art karakter** varlıkları nerede bulunur?
   (itch.io, Unity Asset Store, GameDevMarket, OpenGameArt, Kenney, CraftPix, Humble vb.) Somut **örnekler + linkler**.
2. Bu varlıklar tipik olarak hangi **ifade/animasyon setini** içerir (idle, happy, sad, angry, surprised, talk…)?
   31 jestimizin ne kadarını karşılar? Eksikler nasıl kapatılır?
3. **Format** ne olur (sprite sheet PNG, Aseprite `.ase`, GIF, Spine/DragonBones skeletal, LottieJSON)?
   Tarayıcı Canvas'a entegrasyon kolaylığı açısından hangisi uygun?
4. **Lisanslar:** sergi/ticari/kamusal kullanım uygun mu? Atıf/pay-share/king yükümlülükleri? Fiyat aralığı?
5. "Talking head / emote set / character emotions pixel" gibi hazır paketlerin **kalite ve tutarlılığı** nasıl;
   tek bir karaktere bağlı kalmak mümkün mü?

### B) Kendin yap (DIY) yolu
6. Pixel-art karakter + ifade seti üretmek için **araçlar:** Aseprite, LibreSprite, Piskel, Pixelorama —
   hangileri animasyon/sprite-sheet/onion-skin açısından uygun; öğrenme eğrisi; fiyat/lisans.
7. **AI-destekli üretim:** pixel-art üreten modeller/araçlar (örn. Stable Diffusion + pixel LoRA'ları,
   Scenario, PixelLab, Retro Diffusion vb.) bu işe ne kadar yarar? Tutarlı tek karakter + 31 tutarlı ifade
   üretmek **gerçekçi mi**? Sınırları, kalite, telif/lisans durumu, iş akışı.
8. Sıfırdan veya yarı-otomatik üretimde **gerçekçi emek tahmini** (kişi-gün), gereken beceri seviyesi.
9. **Animasyon yaklaşımı kıyası:**
   - (a) **Kare-kare sprite sheet** (her ifade için birkaç kare) — basit, Canvas'a çok uygun, ama çok asset.
   - (b) **İskeletsel/parçalı** (Spine, DragonBones, Rive) — daha az asset, daha akıcı, ama runtime + lisans.
   - (c) **Parametrik/prosedürel** (mevcut EyeSystem gibi kodla çizim; göz/kaş/ağız parametreleri valence/arousal'dan) —
     en az asset, en esnek, "veri-güdümlü"ye en uygun, ama sanatsal tavanı düşük.
   31 ifadeyi + yoğunluk ölçeklemesini en verimli karşılayan hangisi? (Hibrit?)

### C) Entegrasyon yolu
10. Seçilen yaklaşım mevcut **Canvas 2D + 96×96 / büyük karakter alanı** hattına nasıl bağlanır?
    `jest_id + yogunluk` → ifade/animasyon eşlemesi pratikte nasıl kurulur (manifest, atlas, durum makinesi)?
11. **Performans:** 4GB VRAM/CPU-Canvas kısıtında akıcı (≥24–30 fps) çalışır mı? Bellek/önbellek stratejisi?
12. **Geçiş/karışım:** ifadeler arası yumuşak geçiş (örn. nötr→mutlu) ve idle mikro-animasyonlar nasıl yapılır?
13. **Konuşma senkronu (opsiyonel):** TTS konuşurken basit ağız hareketi (lip-flap) eklenebilir mi?

---

## 6. İstenen çıktı (rapor formatı)

1. **Yönetici özeti + net tavsiye:** Hazır mı, kendin yap mı, hibrit mi? Neden? (donanım/lisans/emek/kalite dengesi)
2. **Hazır varlık tablosu:** kaynak · örnek karakter · ifade kapsamı · format · lisans · fiyat · link.
3. **DIY planı:** araç seçimi + (AI-destekli dahil) iş akışı + emek tahmini + örnek kaynaklar/eğitimler.
4. **Animasyon yaklaşımı kararı:** sprite vs skeletal vs parametrik — bizim 31-jest/veri-güdümlü/Canvas/4GB
   bağlamımız için gerekçeli seçim (hibrit önerisi olabilir).
5. **Somut entegrasyon taslağı:** `jest_id + yogunluk` → karakter ifadesi eşleme şeması; dosya/format yapısı;
   Canvas'a çizim stratejisi; idle + geçişler.
6. **Çözünürlük/yerleşim önerisi:** karakter boyutu ve sergi ekranındaki yeri.
7. **Riskler + yedek plan:** (örn. AI-üretim tutarsızsa, lisans uymuyorsa, emek bütçesi aşılırsa ne yapılır.)
8. Tüm iddialar için **kaynak linkleri**.

---

## 7. Kapsam dışı (bunlara girme)
- Çekirdek sohbet/LLM, TTS, oyun mantığını değiştirme önerme (onlar sabit; bu yalnızca görsel beden katmanı).
- 3D karakter/Unity/Godot tam motor gömme (hafiflik kısıtına aykırı; ancak çok güçlü gerekçe varsa kısaca değin).
- Buluta/çevrimiçi servise runtime bağımlılığı (sergide internet yok).

> Kısaca: **"Bu sergi AI'sına, 31 duyguyu/jesti tarayıcı-Canvas'ta, 4GB'lık bir makinede, çevrimdışı ve
> uygun lisansla sergileyebilecek tutarlı bir 2D pixel-art karakteri nasıl ekleriz — hazır mı alalım, kendimiz mi
> yapalım, nasıl?"** sorusunu kaynaklı ve uygulanabilir biçimde yanıtla.
