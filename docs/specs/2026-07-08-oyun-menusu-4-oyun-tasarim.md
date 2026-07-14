# Oyun Menüsü + 4 Oyun (Kelime · Eş/Zıt · Atasözü · Doğru/Yanlış) — Tasarım

**Tarih:** 2026-07-08
**Durum:** Tasarım onaylandı (brainstorming → tasarım), uygulama planı yazılacak
**Kapsam:** `01-Projects/aican` — oyun katmanı. Çekirdek sohbet/jest (`llm_bridge.py`, `system_prompt.txt`, `gestures.json`) DEĞİŞMEZ.

---

## 1. Amaç

"oyun oynayalım" dendiğinde artık doğrudan Kelime Türetme'ye atlamak yerine **4 seçenekli düz menü** göster:

**🔤 Kelime Türetme · 🔁 Eş/Zıt Anlam · 📜 Atasözü · ✅ Doğru/Yanlış**

Kullanıcı butonla veya sesle birini seçer, o oyun başlar. Oyun bitince ana menüye döner.

## 2. Arka plan — bu bir GERİ GETİRME işidir (sıfırdan yapım değil)

Bu oyunlar daha önce **tam yapılıp test edildi** ve son git commit'inde (`HEAD = 4937af0`) duruyor:
`game_engine.py` (1288 satır) içinde `_Provider` + `_EsZitProvider` + `_AtasozuProvider` +
`_DogruYanlisProvider` + `GameEngine` (menü + TKM + Kelime + quiz). 2026-07-07'de "sadece Kelime
Türetme'ye indir" sadeleştirmesi **çalışma dizininde yapıldı ama commit edilmedi** — bu yüzden
diskteki dosya kırpılmış 567 satır, git'teki commit tam hâli tutuyor.

**Sonuç:** Yeni oyun tasarlamıyoruz; commit'teki test edilmiş motoru geri getirip
(a) TKM'yi çıkarıyoruz, (b) Kelime'nin sadeleştirmedeki iyileştirmelerini koruyoruz,
(c) menüyü 4 düz butona indiriyoruz.

## 3. Kilitli kararlar

1. **Menü:** Düz 4 buton (alt-menü YOK). Kullanıcının zihnindeki modelle birebir, kiosk'ta tek dokunuş.
2. **TKM (Taş-Kağıt-Makas):** Geri getirilmez, menüde yer almaz.
3. **Kelime Türetme:** ŞU ANKİ iyileştirilmiş sürüm korunur — **kategori/tema seçimi YOK**
   (birleşik edebiyat+tarih+bilim havuzu), kısa & sıcak mesajlar, menüden seçilince doğrudan
   kural+"başla" adımına gider.
4. **Eş/Zıt · Atasözü · Doğru/Yanlış:** HEAD'deki test edilmiş ortak quiz motoruyla gelir
   (dostça puanlı, 5 soru, sert kayıp yok, süre barı, duygusal jest).
5. **Endpoint'ler:** Değişmez — `/api/game/start|input|ai_turn|exit`. Menü bir "faz", seçim
   `/api/game/input`'tan akar. Yeni endpoint gerekmez.
6. **Veri:** `ai/es_zit_anlam.json`, `ai/atasozu.json`, `ai/dogru_yanlis.json` zaten yerinde ve dolu.

## 4. Menü akışı (düz 4 buton)

```
Ziyaretçi: "oyun oynayalım"  (sesli/yazılı)
   ↓  (LLM'e GİTMEZ — sabit menü)
GameEngine.start() → phase="menu", 4 buton:
   [🔤 Kelime Türetme] [🔁 Eş/Zıt Anlam] [📜 Atasözü] [✅ Doğru/Yanlış]
   ↓  seçim (buton key'i veya ses) → /api/game/input → handle() → _handle_menu(n)
      "kelime"   → _start_kelime()          (mevcut iyileştirilmiş; kategori yok)
      "eszit"    → _start_quiz("eszit")
      "atasozu"  → _start_quiz("atasozu")
      "dogruyanlis" → _start_quiz("dogruyanlis")
   ↓
[Oyun oynanır]  → bitince skor + [🔁 Ana menü] / [Çıkış]
   ↓  "Ana menü" → start() (menüye döner) · "çıkış"/"dur"/boşta → sohbet moduna döner
```

**Menü butonları** (`_menu_buttons()`):
```python
[{"key": "kelime",      "label": "🔤 Kelime Türetme"},
 {"key": "eszit",       "label": "🔁 Eş/Zıt Anlam"},
 {"key": "atasozu",     "label": "📜 Atasözü"},
 {"key": "dogruyanlis", "label": "✅ Doğru/Yanlış"}]
```

**Menü yönlendirme** (`_handle_menu(n)`) — buton key'i + doğal dil eşleşmesi:
- `kelime` / "kelime" → Kelime Türetme
- `eszit` / "eş" / "zıt" / "anlam" → Eş/Zıt
- `atasozu` / "atasöz" / "atasozu" → Atasözü
- `dogruyanlis` / "doğru" / "yanlış" → Doğru/Yanlış
- Anlaşılmazsa: `kind="reprompt"`, menüyü tekrar göster (nazik "hangisini oynayalım?").

## 5. Oyunlar

### 5.1 Kelime Türetme (mevcut, korunur)
- Kelime zinciri: son harfle başlayan yeni kelime; sırayla AI↔ziyaretçi; 20 sn/tur; 1 tekrar hakkı.
- AI kelimeleri **birleşik havuzdan** (edebiyat+tarih+bilim), LLM'siz seçilir; geçerlilik önce
  yerel sözlük, gerekirse `word_llm` (lenient).
- AI yenilme eğrisi deterministik (~4-5. turda pes). Duygusal jestler korunur.
- **Değişiklik:** Yok — mevcut kod aynen taşınır; sadece `handle()` "kategori" dalı ve
  `_start_kelime_category` gelmez (menüden doğrudan `_start_kelime`).

### 5.2 Ortak quiz motoru — Eş/Zıt · Atasözü · Doğru/Yanlış
Tek `_Provider` arayüzü + 3 sağlayıcı. Format: 5 soru, doğru/yanlış say, sert kayıp yok, süre barı,
her cevapta duygusal jest, sonda skor.

**Sağlayıcı arayüzü** (modül seviyesi sınıflar):
```python
key, label, intro(n)  →  next_question(used) → {
    "id": str, "prompt": str, "accept_norm": set, "reveal": str, "match": "token"|"substring"}
```
Cevap kontrolü tek yerde (`_quiz_check`): `token` = normalize edilmiş kesişim; `substring` = kabul
ifadesi kullanıcı metninin içinde mi (atasözü için lenient).

- **`_EsZitProvider`** (`ai/es_zit_anlam.json`): "'X' kelimesinin eş/zıt anlamlısı ne?"; match=token.
- **`_AtasozuProvider`** (`ai/atasozu.json`): "'Damlaya damlaya …' nasıl devam eder?"; match=substring.
- **`_DogruYanlisProvider`** (`ai/dogru_yanlis.json`): "'[ifade]' — doğru mu, yanlış mı?"; match=token
  (doğru→{doğru,evet,d}, yanlış→{yanlış,hayır,y}); reveal = "Doğru/Yanlış — açıklama".

**Bitişte:** buton `[🔁 Ana menü]` (quiz alt-menüsü yerine ana menüye döner) + `[Çıkış]`.
`quiz_turn is None` iken girdi → `self.start()` (ana menü).

## 6. Backend değişiklikleri

**`orchestrator/game_engine.py`** (ana iş — dikkatli birleştirme):
- Temel: HEAD'in çok-oyunlu iskeleti (menü + `_Provider`/3 sağlayıcı + quiz metotları).
- **Çıkar:** TKM/RPS ile ilgili her şey (`_start_rps`, `_handle_rps`, `_ai_move`, RPS `_JEST`/`_TXT`
  girdileri, menü RPS butonu, `handle()` `rps` dalı, `insist` RPS'e özgüyse).
- **Kelime'yi güncel tut:** HEAD'in kategori'li Kelime'si yerine mevcut çalışma dizinindeki
  iyileştirilmiş Kelime metotları/metinleri (`_start_kelime`, `_begin_kelime`, `_handle_kelime`,
  `_pick_ai_word(req_letter, used)` — kategori paramsız, birleşik `_ai_pool`).
- **Menü:** `_menu_buttons()` = 4 düz buton; `_handle_menu` = yukarıdaki yönlendirme; quiz alt-menüsü
  (`_start_quiz_menu`/`_quiz_menu_buttons`/`_handle_quiz_select`) KALDIRILIR — menü doğrudan
  `_start_quiz(provider_key)` çağırır (provider'ı `_handle_menu` set eder).

**`orchestrator/web_server.py`:** Endpoint imzaları aynı. `start()` artık menü döndürdüğü için
warmup/ön-ısıtma sabit metinleri (varsa Kelime kural kopyası) gözden geçirilir; TKM'ye özgü kod varsa çıkar.

## 7. Frontend değişiklikleri (çoğu zaten hazır)

`control.js` "ince yönlendirici" ve **generic**: `applyGamePayload` butonları (`renderGameButtons`),
skoru, `quiz_progress`'i, `quiz` kind'ını zaten işliyor; `gamePhase` `menu`/`rps` destekliyor.

- **`control.js`:** `startGame` → `/api/game/start` (menü döner) → butonlar render. Menü seçimi buton
  key'i ile `submitGameInput`. Quiz payload işleme mevcut; eksik/kırpılmış parça varsa HEAD'den geri
  al. TKM'ye özel dallar (rps) temizlenebilir (dormant bırakmak da zararsız).
- **`app.js`:** Sergi ekranında menü/quiz gösterimi; HEAD'de mevcut. Kırpılan quiz/menü görselleri
  geri getirilir; TKM görselleri gelmez.

## 8. Veri dosyaları
Hepsi yerinde ve dolu (yeni veri gerekmez): `es_zit_anlam.json` (kelime→{es,zit}),
`atasozu.json` ([{bas,tamam}]), `dogru_yanlis.json` ([{ifade,dogru,aciklama}] ~60, bilim müzesi dostu).

## 9. Test
- **`orchestrator/test_quiz.py`:** HEAD'den geri getirilir (3 sağlayıcı + `_quiz_check` token/substring).
- **`game_engine` testleri:** Kelime zinciri/1-tekrar/timeout/yenilme eğrisi geçmeye devam etmeli.
- **Menü:** `_handle_menu` 4 yönlendirme + reprompt için birim testi eklenir.
- **Doğrulama:** Backend testleri (Ollama gerekmez, LLM mock) + Flask `test_client` ile
  `/api/game/*` uçtan uca. Tarayıcı canlı oynanış manuel (menü→her oyun→bitiş→ana menü).

## 10. Kaldırılanlar / Kapsam dışı (YAGNI)
- **TKM (Taş-Kağıt-Makas):** menüde yok, kodu çıkar.
- **Kelime tema/kategori seçimi:** geri getirilmez (mevcut birleşik havuz korunur).
- **LLM ile quiz üretimi/doğrulaması:** yok — küratörlü JSON + yerel eşleşme (sergi deterministik ilkesi).

## 11. Riskler
- **Kelime regresyonu:** Körlemesine `git checkout HEAD` YAPILMAZ; Kelime bölümü mevcut iyileştirilmiş
  sürümden korunur. Birleştirme dosya-dosya, testlerle doğrulanır.
- **Çalışma dizini kirli:** Mevcut değişiklikler (sadeleştirme) commit edilmemiş; birleştirme sırasında
  yanlışlıkla ezme riskine karşı önce güncel Kelime metotları ayrı not/alınır.
