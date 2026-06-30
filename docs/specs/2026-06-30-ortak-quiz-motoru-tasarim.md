# Ortak Quiz Motoru + Atasözü & Doğru/Yanlış — Tasarım

**Tarih:** 2026-06-30
**Durum:** Onaylandı (brainstorming → tasarım), uygulama planı yazılacak
**Kapsam:** `01-Projects/aican` — oyun katmanı. Çekirdek sohbet/jest DEĞİŞMEZ. Mevcut `esanlam` quiz'i genel motora taşınır (refactor); 2 yeni quiz türü eklenir.

---

## 1. Amaç

3 quiz türünü (Eş/Zıt · Atasözü · Doğru/Yanlış) **tek ortak quiz motoru + sağlayıcı (provider)** ile sun. Yeni quiz eklemek = 1 veri dosyası + ufak sağlayıcı. Ana menüde "Bilgi Yarışması" → alt-menü.

## 2. Kilitli kararlar (brainstorming)

1. **Mimari:** Ortak quiz motoru + 3 sağlayıcı (kopyalama DEĞİL).
2. **Menü:** Ana menü TKM · Kelime · **Bilgi Yarışması**; sonuncusu alt-menü (Eş/Zıt · Atasözü · Doğru/Yanlış · Çıkış).
3. **Refactor:** `esanlam` (faz/state/metot/kind/test/frontend) → genel `quiz`; Eş/Zıt bir sağlayıcı olur; davranış korunur.
4. **Veri:** Atasözü + Doğru/Yanlış için yeni statik JSON (offline, küratörlü).
5. **Format:** Mevcut dostça puanlı quiz (N=5, sert kayıp yok, süre barı, duygusal tepki) aynen korunur.

## 3. Genel motor (state: `quiz_*`)

Alanlar (`_reset_quiz`): `quiz_provider` (key|None), `quiz_turn` ("secim"|"hazir"|"soru"|None), `quiz_used` (set), `quiz_score` {dogru,toplam}, `quiz_q_index`, `quiz_current` (soru dict). Sabit: `QUIZ_QUESTION_COUNT = 5`.

Ortak metotlar: `_start_quiz_menu`, `_handle_quiz_select`, `_start_quiz`, `_handle_quiz_ready`, `_begin_quiz`, `_quiz_ask_next`, `_handle_quiz`, `_quiz_end`, `_quiz_check`, `_quiz_payload`, `_quiz_menu_buttons`, `_quiz_ready_buttons`.

Payload (`_quiz_payload`): `game="quiz"`, `kind` ("quiz_menu"|"quiz_ready"|"quiz_question"|"quiz_end"), `quiz` (sağlayıcı key), `quiz_progress`, `dogru_mu`, `turn`, `jest_id`, `yanit`, `timer`, `buttons`, `ended`, `score=None`.

## 4. Sağlayıcı arayüzü

Modül seviyesi sınıflar: `key`, `label`, `intro(n)` (kural metni), `next_question(used)` → tekdüze soru dict:
```python
{"id": str, "prompt": str, "accept_norm": set, "reveal": str, "match": "token"|"substring"}
```
Cevap kontrolü TEK yerde (`_quiz_check(q, text)`):
- `token`: `normalize(text)` ve token'ları kabul kümesiyle kesişiyor mu.
- `substring`: kabul ifadelerinden biri kullanıcı metninin içinde mi (ya da tersi) — atasözü ifadeleri için lenient.

## 5. Üç sağlayıcı

### `_EsZitProvider` (mevcut `ai/es_zit_anlam.json`)
"'X' kelimesinin eş/zıt anlamlısı ne?"; accept = normalize'lı eş/zıt; reveal = ilk kabul (büyük harf); match=token. *(esanlam mantığı buraya taşınır.)*

### `_AtasozuProvider` (`ai/atasozu.json`, YENİ ~50)
Veri: `[{"bas": "Damlaya damlaya", "tamam": ["göl olur"]}]`. Soru: "'Damlaya damlaya …' nasıl devam eder?"; accept = normalize'lı tamamlamalar; reveal = "bas + tamam[0]"; **match=substring**.

### `_DogruYanlisProvider` (`ai/dogru_yanlis.json`, YENİ ~60)
Veri: `[{"ifade": "…", "dogru": true, "aciklama": "…"}]`. Soru: "'[ifade]' — doğru mu, yanlış mı?"; accept = doğru ise {dogru,evet,d,…}, yanlış ise {yanlis,hayir,y,…} (normalize'lı eş küme); reveal = "Doğru/Yanlış — açıklama"; match=token. Olgular objektif, çocuk dostu (bilim müzesi).

## 6. Akış / menü

```
ana menü → "Bilgi Yarışması" → quiz alt-menü (secim)
  → [Eş/Zıt | Atasözü | Doğru/Yanlış] seç → _start_quiz (kural+başla)
  → başla → soru1…N → skor + "Yeni yarışma"(alt-menüye döner) / Çıkış
```
Faz `"quiz"`. `handle()`: quiz_turn None→alt-menü, "secim"→`_handle_quiz_select`, "hazir"→`_handle_quiz_ready`, diğer→`_handle_quiz`. Exit kontrolü quiz fazını da kapsar.

## 7. Refactor + dosyalar

- **`game_engine.py`:** modül seviyesi: atasözü/DY loader + fallback + 3 sağlayıcı sınıfı; `__init__`'te sağlayıcı kayıt (`self._providers`); `_reset_ea`→`_reset_quiz`; tüm `_ea_*`/`esanlam` metotları → `_quiz_*`; menü "3" → Bilgi Yarışması; `_menu_buttons` etiketi; `_TXT["menu"]`; `exit()` `_reset_quiz`.
- **`web_server.py`:** DEĞİŞMEZ.
- **`web/control.js`:** `'esanlam'`→`'quiz'` (isTimed, `quiz_progress`, log); alt-menü butonları `renderGameButtons` ile otomatik.
- **Test:** `test_es_zit_anlam.py` → `test_quiz.py` (genel motor + 3 sağlayıcı + HTTP; Eş/Zıt regresyonu korunur).

## 8. Veri küratörlüğü

Atasözü ~50 (standart, tanınır) + Doğru/Yanlış ~60 (objektif/doğrulanabilir, çocuk dostu). Offline, güvenilir.

## 9. Hata yönetimi

JSON yoksa/bozuksa sağlayıcı gömülü yedeğe düşer (mod çalışır). Sağlayıcıda soru tükenirse erken bitiş. LLM/Ollama gerektirmez.

## 10. Test

- **Birim (Ollama'sız):** her sağlayıcı `next_question` (geçerli soru + tükenme); `_quiz_check` token + substring + doğru/yanlış eş küme; akış (menü→seçim→başla→soru→cevap→bitiş); alt-menü reprompt; yeni-yarışma.
- **HTTP (test_client):** ana menü → Bilgi Yarışması → her 3 quiz → başla → soru.
- **Manuel:** tarayıcıda alt-menü, 3 quiz, süre barı, dostça geri bildirim, skor.

## 11. Kapsam dışı (YAGNI)

Zorluk seviyesi yok; yeni jest yok; canlı internet yok; soru sayısı sabit (5).
