# aican Seslendirme (TTS)

AI cevaplarini **duyguya gore tonlanmis** sesle okur. Birincil: **edge-tts** (Microsoft,
ucretsiz/anahtarsiz, cevrimici, yuksek kaliteli Turkce neural ses — Emel/Ahmet). Internet
yoksa otomatik **Piper**'a (yerel, CPU, cevrimdisi) duser. Ikisi de GPU'ya dokunmaz
(4GB VRAM aktif LLM/Ollama ile dolu).

## Mimari (motordan bagimsiz)

| Dosya | Gorev |
|---|---|
| `emotion_voice_map.py` | `gestures.json`'daki **valans + uyarilma** -> prosodi (hiz/perde/ses/duraklama/tonlama-cesitliligi). `yogunluk` siddeti olcekler. 31 jestin hepsi formulle. Her iki motorda da ayni. |
| `engine_base.py` | `TTSEngine` soyut arayuzu + `FallbackEngine` (birincil hata/bos -> yedege duser). |
| `engine_edge.py` | **Birincil** — edge-tts (Microsoft, ucretsiz, cevrimici). Emel/Ahmet neural ses; mp3 -> ffmpeg ile WAV'a normalize. |
| `engine_piper.py` | **Yedek** — yerel Piper motoru (cevrimdisi). Model bir kez yuklenir; perde ffmpeg ile kaydirilir. |
| `cache.py` | `(ses, jest, yogunluk, metin)` -> wav dosya onbellegi (sik cumleler aninda). |
| `gen_demo.py` / `gen_demo_edge.py` | Ayni cumleyi farkli duygularda seslendiren kalite-testi betikleri (Piper / edge). |

Yeni motor (Chatterbox/ElevenLabs vb.) eklemek = `TTSEngine`'i uygulayan bir dosya +
`config.json`'da `tts_engine` degeri. Endpoint/onbellek/frontend ayni kalir.

## Kurulum (yeni makinede)

```bash
pip install -r requirements.txt        # edge-tts + piper-tts + imageio-ffmpeg
# Cevrimdisi YEDEK Piper sesini indir (60MB, bir kez):
python -m piper.download_voices tr_TR-dfki-medium --data-dir orchestrator/tts/voices
```

> edge-tts ek indirme istemez ama **cevrimici** calisir (Microsoft sunucusu, anahtarsiz).
> Internet yoksa otomatik Piper'a duser — bu yuzden yedek ses yine de indirilmeli.

## Ayarlar (`orchestrator/config.json`)

| Anahtar | Varsayilan | Aciklama |
|---|---|---|
| `tts_enabled` | `true` | Seslendirmeyi ac/kapa |
| `tts_engine` | `"edge"` | `"edge"` (cevrimici, yuksek kalite) veya `"piper"` (cevrimdisi) |
| `tts_voice` | `"tr-TR-EmelNeural"` | edge sesi: `tr-TR-EmelNeural` (kadin) / `tr-TR-AhmetNeural` (erkek). engine=piper ise `tr_TR-*` Piper sesi yaz |
| `tts_fallback_enabled` | `true` | edge basarisizsa (internet yok) Piper'a dus |
| `tts_fallback_voice` | `"tr_TR-dfki-medium"` | Cevrimdisi yedek Piper sesi |
| `tts_pitch_enabled` | `true` | Piper'da ffmpeg perde kaydirma (edge kendi pitch'ini kullanir) |
| `tts_cache_enabled` | `true` | Ses onbellegi |
| `tts_cache_max` | `500` | Onbellekte en fazla dosya |
| `tts_autoplay` | `true` | Frontend sesi otomatik calsin |

## API

- `GET  /api/speak/status` -> `{status, ready, engine, voice, enabled, autoplay}`
- `POST /api/speak` `{text, jest_id, yogunluk}` -> `audio/wav`

Frontend (`web/app.js`) `ai_reply` geldiginde sesi yaziyla **paralel** calar. Tarayici
autoplay kilidi ilk etkilesimde acilir. Gosterim ekraninda **`S`** tusu sesi ac/kapatir.

## Duygu -> ses mantigi

2 boyutlu duygu modeli (valans-uyarilma):
- **Uyarilma yuksek** -> hizli, gur, canli tonlama, kisa duraklar, yuksek perde
- **Valans pozitif** -> parlak/yuksek perde; **negatif** -> koyu/alcak perde

Ornek: `uzgun_derin` (V-0.85, A0.2) = cok yavas + pes + kisik + uzun durak;
`mutluluk_yogun` (V0.9, A0.85) = hizli + tiz + gur + canli.

Tum tabloyu gormek icin: `python orchestrator/tts/emotion_voice_map.py`
