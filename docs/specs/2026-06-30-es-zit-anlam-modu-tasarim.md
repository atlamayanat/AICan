# Eş/Zıt Anlam Modu — Tasarım (Dostça Puanlı Quiz)

**Tarih:** 2026-06-30
**Durum:** Onaylandı (brainstorming → tasarım), uygulama planı yazılacak
**Kapsam:** `01-Projects/aican` — yalnızca oyun katmanı. Çekirdek sohbet/jest sistemi DEĞİŞMEZ. Mevcut 31 jest yeniden kullanılır.

---

## 1. Amaç

Oyun moduna 3. mod: **Eş/Zıt Anlam**. AI bir kelime + rastgele "eş anlamlısı?" ya da "zıt anlamlısı?" sorar; ziyaretçi cevaplar. Dostça puanlı quiz — yanlışta sert kayıp yok.

## 2. Kilitli kararlar (brainstorming)

1. **Format:** Dostça puanlı quiz. AI **N=5** soru sorar; doğru sayısı tutulur. Yanlış/boş/timeout'ta AI beklediği cevabı nazikçe söyler ve devam eder (kayıp YOK). Sonunda skor + duygusal tepki.
2. **Yön:** Tek yönlü — AI sorar, kullanıcı cevaplar. (Kullanıcı AI'ya soramaz → `ai_turn` GEREKMEZ.)
3. **Tip:** Eş + zıt **tek modda karışık** (her soruda rastgele, kelimede mevcut olan tipten).
4. **Veri:** Küratörlü statik JSON (offline), güvenilir kaynaklardan çapraz-doğrulanmış.
5. **Süre:** Her soruda mevcut 20s zaman barı (who="user"); timeout = nazik geçiş (kayıp değil).

## 3. Veri dosyası — `ai/es_zit_anlam.json` (YENİ)

```json
{
  "siyah":  {"zit": ["beyaz", "ak"]},
  "büyük":  {"zit": ["küçük"], "es": ["iri", "kocaman"]},
  "mutlu":  {"es": ["sevinçli", "neşeli", "mesut"], "zit": ["üzgün", "mutsuz"]}
}
```

- Her kelimede `es` (eş anlamlı) ve/veya `zit` (zıt anlamlı) **kabul listesi**; biri olmayabilir.
- ~80-120 tanınır kelime (sergi + çocuk kitlesi). Antonim net (1-2 cevap); sinonimde **geniş kabul kümesi** (yanlış-reddetme azalsın).
- Kaynaklar: KeNet / mythes-tr (eş) + standart zıt-anlam listeleri; sergi-uygun ortak kelimeler için küratörlü.
- Tüm kelimeler tek sözcük, küçük, Türkçe harf.

### 3.1 Yükleme & normalizasyon (init)
- JSON yüklenir → `self._ea_data = {kelime: {"es":[...], "zit":[...]}}`.
- Eşleştirme için **normalize'lı kabul kümeleri** önceden hesaplanır: her (kelime,tip) için `{normalize(w) for w in kabul}`.
- Sorulabilir kelimeler listesi: en az bir tipi olanlar.
- **Sağlamlık:** JSON yoksa/bozuksa mod devre dışı kalmaz — küçük gömülü yedek (`_EA_FALLBACK`, ~10 çift) kullanılır; log uyarısı.

## 4. Soru seçimi (AI) — saf havuz, LLM YOK

- `_ea_next_question()`: kullanılmamış rastgele kelime + o kelimede mevcut rastgele tip (es/zit) seçer.
- `ea_used` ile aynı kelime tekrar sorulmaz.
- Hızlı, halüsinasyonsuz, offline.

## 5. Cevap doğrulama (dostça / lenient)

- Kullanıcı cevabı `normalize()` ile sadeleştirilir (Türkçe→ascii fold → "sevincli" da "sevinçli"yi tutar).
- `user_norm` veya ilk token, o (kelime,tip) normalize-kabul kümesinde mi?
  - **Doğru** → "Bravo!" + puan + sevinç jesti (`kel_user_ok` havuzu).
  - **Yanlış/boş/timeout** → AI beklediği cevaplardan birini nazikçe söyler ("Yaklaştın! Ben 'beyaz' diyecektim 😊") — kayıp YOK; `kel_retry`/`merak` jesti.
- Bulanıklık önlemi: kabul kümesi geniş; **ters-yön kontrolü** opsiyonel (basit tutulur, ilk sürümde yok).

## 6. Akış / durum makinesi

```
menü → "3" → _start_esanlam (kural + 'başla', süre yok)
       → 'başla' → _begin_esanlam (soru 1 + süre)
       → cevap → _handle_esanlam (doğru/yanlış göster + sonraki soru)
       → N. sorudan sonra → ea_end (skor + duygusal tepki)
```
- Yeni faz: `self.phase = "esanlam"`.
- Durum alanları (`_reset_ea`): `ea_turn` ("hazir"|"soru"|None), `ea_used` (set), `ea_score` ({"dogru":0,"toplam":0}), `ea_q_index` (0..N), `ea_current` ({"kelime","tip","kabul_norm","kabul_goster"}).
- `ea_turn=None` (oyun bitti) + girdi → yeni oyun (`_start_esanlam`).
- Soru sayısı sabiti: `EA_QUESTION_COUNT = 5`.

## 7. Backend (`game_engine.py`)

- Veri yükleme + normalize kümeleri (init); `_EA_FALLBACK` gömülü yedek.
- `_reset_ea`, `_start_esanlam`, `_handle_esanlam_ready`, `_begin_esanlam`, `_ea_next_question`, `_handle_esanlam(text, timeout)`, `_ea_end`.
- Payload: `_ea_payload(kind, ...)` (kel payload'a benzer; `kind: "ea_ready"|"ea_question"|"ea_result"|"ea_end"`, alanlar: `soru`, `tip`, `dogru_mu`, `beklenen`, `score`, `timer`, `buttons`, `ended`).
- Menü: `_menu_buttons`'a 3. buton; `_handle_menu`'da "3"/"es"/"zit"/"anlam" → `_start_esanlam`; `_TXT["menu"]` metnine (3) eklenir.
- `handle()`: `esanlam` faz yönlendirmesi + exit kontrolüne `esanlam` dahil.
- **`web_server.py` DEĞİŞMEZ** (`/api/game/input` mevcut; quiz tek-yönlü → ai_turn yok).
- Duygu: mevcut jest havuzları (yeni görsel yok).

## 8. Frontend

- **`control.js` / `app.js`:** yeni `kind`'ları işle — soru metni AI yanıtı olarak gösterilir (`ai_reply`), skor güncellenir, süre barı mevcut infra ile, butonlar (başla/çıkış/yeni oyun) `renderGameButtons` ile.
- Menüye **"3) Eş/Zıt Anlam"** butonu (backend payload'undan otomatik gelir).
- Tema etiketi alanı yeniden kullanılabilir (opsiyonel: "Eş/Zıt Anlam — Soru 2/5"). Minimal.

## 9. Veri küratörlüğü

~80-120 kelime, güvenilir kaynaklardan çapraz-doğrulanmış, tanınır. Antonim net; sinonimde geniş kabul. Sergi+çocuk kitlesine uygun (obscure jargon yok).

## 10. Hata yönetimi & sağlamlık

- JSON okunamazsa `_EA_FALLBACK`'e düş (mod yine çalışır).
- Hiç sorulabilir kelime yoksa (bozuk veri) → mod menüye nazik dönüş + log.
- LLM/Ollama gerektirmez (tamamen offline veri).

## 11. Test

- **Birim (standalone, Ollama'sız):** veri yükleme + normalize kümeleri; `_ea_next_question` (kullanılmamış + geçerli tip); doğrulama doğru/yanlış/fold ("sevincli"→kabul); timeout = nazik geçiş (kayıp değil); N soru sonunda `ea_end` + skor; menü "3" yönlendirme; yeni-oyun.
- **HTTP entegrasyon (test_client):** menü → 3 → başla → soru → cevap → … → skor.
- **Manuel:** tarayıcıda 5 soru, eş/zıt karışık, süre barı, dostça yanlış geri bildirimi, skor.

## 12. Kapsam dışı (YAGNI)

- Kullanıcı AI'ya soramaz (tek yön).
- Zorluk seviyesi / kategori yok.
- Ters-yön doğrulama (ilk sürümde yok).
- Yeni jest yok; canlı internet API yok (statik veri).
