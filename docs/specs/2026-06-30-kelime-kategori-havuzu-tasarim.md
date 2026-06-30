# Kelime Türetme — Kategorili Sözcük Havuzu Tasarımı

**Tarih:** 2026-06-30
**Durum:** Onaylandı (brainstorming → tasarım), uygulama planı yazılacak
**Kapsam:** `01-Projects/aican` — yalnızca oyun katmanı (Kelime Türetme). Çekirdek sohbet/jest sistemi (`llm_bridge.py`, `system_prompt.txt`, `gestures.json`) DEĞİŞMEZ.

---

## 1. Amaç

Kelime Türetme oyununda AI'nın **temalı terimlerle** (Edebiyat / Tarih / Bilim) oynamasını sağlamak; ziyaretçiye bilgi + kişilik gösteren bir deneyim. Ziyaretçi oyun başında temayı seçer.

## 2. Kilitli kararlar (brainstorming)

1. **Temalı kapsam:** SADECE AI temalı oynar; **ziyaretçi herhangi geçerli Türkçe kelime** söyleyebilir. (Kullanıcı kelimesi için "bu terim mi?" doğrulaması GEREKMEZ → çocuk dahil kitleye uygun.)
2. **Yaklaşım:** Havuz-tabanlı (LLM-tabanlı DEĞİL). AI kelimeleri küratörlü statik veri dosyasından gelir. Gerekçe: gemma3:4b alan-terimlerinde halüsinasyon/uydurma yapar, yavaştır; deterministik doğrulama "gerçekten edebiyat terimi mi"yi kontrol edemez.
3. **Kategoriler:** Edebiyat, Tarih, Bilim, **Genel** (mevcut ~230 yaygın kelime korunur).
4. **Kategori seçimi:** "Kelime Türetme" seçilince **alt-menü** (4 seçenek); ziyaretçi dokunur veya yazar.

## 3. Mevcut durum (zemin)

- **Kural:** kelime zinciri — önceki kelimenin SON harfiyle başlayan yeni kelime.
- **AI kelimesi:** `word_llm.uret_kelime(harf, kullanilmis)` (Ollama) + deterministik doğrulama; başaramazsa pes.
- **Yedek:** Ollama düşerse `_local_ai_word` → `_TR_COMMON_WORDS` (~230 kelime). *Havuzdan seçme deseni zaten var.*
- **Kullanıcı doğrulama:** `_gecerli_kelime` → önce `_TR_COMMON_WORDS` (anında), yoksa `word_llm.gecerli_mi` (lenient).
- **AI yenilme eğrisi:** `_word_ai_success_p` (GRACE=2, BASE=0.95, DECAY=0.30, FLOOR=0.05) → ~4-5 turda kasıtlı pes.
- **Akış (state):** `idle → menu → kelime` ; `kelime` içinde `word_turn`: `hazir → user/ai`. `_start_kelime` (kural+hazır), `_begin_kelime` (oyna), `_handle_kelime` (kullanıcı turu), `ai_turn` (AI turu).

## 4. Veri dosyası — `ai/word_categories.json` (YENİ)

JSON YALNIZCA 3 yeni temalı kategoriyi içerir. `"genel"` kategorisi koddaki mevcut `_TR_COMMON_WORDS`'ten gelir (taşınmaz → çift kaynak yok + sağlam fallback korunur).

```json
{
  "edebiyat": ["roman", "şiir", "metafor", "dize", "kafiye", "..."],
  "tarih":    ["imparatorluk", "fetih", "antlaşma", "hanedan", "..."],
  "bilim":    ["atom", "hücre", "fotosentez", "yerçekimi", "..."]
}
```

- `gestures.json` deseniyle uyumlu: kod değiştirmeden düzenlenebilir.
- Tüm kelimeler `temiz_kelime()` çıktısıyla uyumlu olmalı (küçük, Türkçe harf, tek sözcük).

### 4.1 Yükleme & indeksleme (GameEngine init)
- JSON yüklenir (3 tema) + `"genel"` = `_TR_COMMON_WORDS`. Her kategori için **ilk-harfe göre indeks**: `pools = {kategori: {harf: [kelime,...]}}`.
- **Birleşik doğrulama kümesi:** `_ALL_WORDS = _TR_COMMON_WORDS ∪ (3 temadaki tüm kelimeler)` → kullanıcı-doğrulama hızlı yolu (temalı kelimeler de anında geçerli sayılır).
- **Sağlamlık:** JSON yoksa/bozuksa yalnız `"genel"` kategorisi kullanılabilir olur (sergi çökmez); temalı seçim de `"genel"`'e düşer + log uyarısı.

## 5. AI kelime seçimi (saf havuz)

- Yeni: `_pick_ai_word(kategori, req_harf, used)` → `pools[kategori][req_harf]` içinden kullanılmamış rastgele kelime; yoksa `None`. Bu metot hem eski LLM yolunun (`uret_kelime`) hem de eski Ollama-down yedeğinin (`_local_ai_word`) YERİNE geçer — tek AI-kelime kaynağı.
- `ai_turn()` artık `word_llm.uret_kelime` ÇAĞIRMAZ; `_pick_ai_word` kullanır (tüm kategoriler dahil, "genel" de). Daha hızlı, halüsinasyonsuz, **Ollama'dan bağımsız**.
- **Yenilme eğrisi korunur:** `_word_ai_success_p()` AI'nın deneyip denemeyeceğine karar verir. "Dene" + havuzda kelime var → oyna. "Dene" + havuz o harfte boş → **temaya uygun pes**. "Deneme" → pes.
- **Seyrek harf:** havuzlar yaygın başlangıç harflerini kapsayacak şekilde küratörlenir; nadir harflerde erken pes tematik olarak kabul.
- `word_llm.gecerli_mi` kullanıcı doğrulaması için KALIR (değişmez). `word_llm.uret_kelime` ve `_local_ai_word` artık AI tarafında kullanılmaz (ölü yol; silinmesi opsiyonel, ileride).
- **`ai_error` bayrağı:** AI artık Ollama gerektirmediğinden "Ollama-down → sessiz pes" ayrımı geçersiz; AI turunda `ai_error` her zaman `False` (payload'da kalabilir, kullanıcı turundaki LLM doğrulaması hâlâ lenient).

## 6. Akış / durum makinesi (kategori alt-menüsü)

Yeni adım eklenir:
```
menu → (Kelime Türetme seçildi) → KATEGORİ ALT-MENÜSÜ → _start_kelime → _begin_kelime → oyun
```
- Yeni durum: `word_turn = "kategori"` (oyun fazı `kelime`'ye geçer ama henüz kural/süre yok).
- Alt-menü metni: "Hangi temada oynayalım? 1) Edebiyat 2) Tarih 3) Bilim 4) Genel" + 4 dokunmatik buton (`_kel_category_buttons`).
- Seçim parse: `normalize()` ile "edebiyat"/"1"/"tarih"/"2"... eşleşir; geçersizse tekrar sorar. Buton `key` = kategori adı.
- Seçim sonrası `self.word_category` ayarlanır → `_start_kelime` tema-bilinçli kural anlatımı verir ("Edebiyat temasında oynuyoruz! ...") → hazır → oyna.

## 7. Backend değişiklikleri

### `game_engine.py`
- JSON yükleme + `pools` indeksi + `_ALL_WORDS` (init).
- Yeni durum alanı: `self.word_category` (varsayılan `None`; `_reset_word`'te sıfırlanır).
- Kategori alt-menü payload'u (`kind:"category_select"`) + `_handle_kelime_category(text)` parse/yönlendirme.
- `_pick_ai_word(...)` yeni; `ai_turn` LLM yerine buna geçer; `_local_ai_word` ve `uret_kelime` AI yolundan çıkar (ölü yol).
- `_gecerli_kelime`: hızlı yol `_TR_COMMON_WORDS` yerine `_ALL_WORDS` (temalılar dahil).
- Tema-bilinçli intro + pes metinleri (kategori adı enjekte edilir).
- "Kelime Türetme" menü seçimi artık doğrudan `_start_kelime` yerine kategori alt-menüsünü açar.

### `web_server.py`
- Kategori adımı `/api/game/input` ile yönlendirilir (yeni uç GEREKMEZ). Payload `kind:"category_select"` döner; `game_lock` korunur.

## 8. Frontend değişiklikleri

- **`control.js`:** `kind:"category_select"` payload'unu işle → 4 kategori butonunu göster; seçimi `/api/game/input`'a yolla. Oyun sırasında küçük "Tema: <kategori>" etiketi.
- **`app.js`:** sergi ekranında kategori menüsü + tema etiketi gösterimi.
- **`AI_Body_v2.html` / `Kontrol_Paneli.html`:** kategori butonları + tema etiketi için minimal DOM/CSS.
- Zaman barı, jestler, kelime akışı AYNI kalır.

## 9. Havuz küratörlüğü (içerik)

3 temalı kategori (`edebiyat`, `tarih`, `bilim`) AI yardımıyla üretilir:
- Kitleye uygun, **tanınır** terimler (obscure jargon değil); müze + çocuk kitlesi.
- Yaygın başlangıç harflerini (a, b, d, e, i, k, m, s, t, y...) kapsa.
- Kategori başına ~150-200 kelime; hepsi gerçek, tek sözcük, `temiz_kelime` uyumlu.
- "Özel isim kullanma" kuralı: tarih için kişi/yer özel adları yerine kavramlar (örn. "fetih", "antlaşma", "hanedan") tercih; ama tanınır dönem/kavramlar olabilir.

## 10. Hata yönetimi & sağlamlık

- JSON okunamazsa `_TR_COMMON_WORDS`'e düş; oyun "genel" ile çalışmaya devam eder.
- Seçilen kategoride hiç kelime yoksa (bozuk veri) → "genel"e düş + log.
- AI turu: havuz o harfte boşsa temaya uygun pes (çökme yok).
- Ollama bağımsızlığı: AI kelimeleri artık Ollama gerektirmez (yalnız kullanıcı doğrulaması lenient LLM kullanır; o da down ise kabul).

## 11. Test

- **Birim (Ollama gerektirmez):** JSON yükleme + indeks; `_pick_ai_word` harf/kategori/kullanılmış filtresi; kategori parse ("1"/"edebiyat"/geçersiz); seyrek harf → pes; `_ALL_WORDS` doğrulama hızlı yolu; tema-bilinçli metinler.
- **Akış (mevcut test_client deseni):** menu → kategori seç → hazır → oyna → AI temalı kelime → kullanıcı serbest kelime → zincir devamı; geçersiz kategori tekrar sorar.
- **Manuel:** tarayıcıda 4 kategori, buton + yazı seçimi, tema etiketi, AI kelimelerinin gerçekten temalı/anında olması.

## 12. Kapsam dışı (YAGNI)

- Zorluk modu / ikisi-de-temalı mod yok.
- Skor/duygu eğrisi değişmez.
- Yeni jest yok (mevcut `kel_*` jest havuzları).
- Kullanıcıya tema zorunluluğu yok.
- `word_llm.uret_kelime` silme (ölü yol bırakılır; ayrı temizlik işi).
