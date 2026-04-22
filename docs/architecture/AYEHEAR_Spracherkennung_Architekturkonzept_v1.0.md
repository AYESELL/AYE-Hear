# AYEHEAR — Technisches Konzeptdokument: Spracherkennung & Transkriptions-Pipeline

**Version:** 1.0  
**Datum:** 20. April 2026  
**Status:** Vorschlag / Review ausstehend  
**Autor:** AYE Digital UG — Strategische Analyse (Claude Cowork)  
**Zielgruppe:** Architekten und Entwickler des AYEHEAR-Projekts

---

## 1. Ausgangssituation und Problemstellung

AYEHEAR ist ein lokal betriebenes System zur DSGVO-konformen Protokollierung von Gesprächen und Meetings. Die aktuelle Implementierung basiert auf OpenAI Whisper (Python-Bibliothek `openai/whisper`) und erzielt mit den Modellgrößen `small` und `base` eine Erkennungsgenauigkeit von ca. **70%**. Dieser Wert ist für ein produktiv einsetzbares Meeting-Protokollierungssystem nicht ausreichend.

### 1.1 Symptome

- Wechsel von `base` auf `small` bringt keine signifikante Verbesserung
- Erkennungsfehler häufen sich bei Fachvokabular, Dialekten und mehreren gleichzeitigen Sprechern
- Folgeprozesse (Zusammenfassung, Aktionspunkte-Extraktion via LLM) sind direkt abhängig von der Transkriptionsqualität — Fehler potenzieren sich

### 1.2 Kerndiagnose

Die 70%-Erkennungsrate ist **kein Hardware-Problem** und **kein grundsätzliches Architekturproblem**. Es handelt sich um ein **Modell-Größen- und Konfigurationsproblem**. Die Modelle `base` (~74M Parameter) und `small` (~244M Parameter) sind für produktive Meeting-Transkription im deutschen Sprachraum mit mehreren Sprechern schlicht unterdimensioniert.

Vergleich der Word Error Rates (WER) nach Modellgröße für Deutsch:

| Modell | Parameter | WER Deutsch (ca.) | CPU-Tauglichkeit |
|---|---|---|---|
| `base` | 74M | ~20–30% | Ja |
| `small` | 244M | ~15–25% | Ja |
| `medium` | 769M | ~10–15% | Eingeschränkt |
| `large-v3` | 1.550M | ~5–8% | Nur GPU empfohlen |
| `large-v3-turbo` | ~800M (reduzierter Decoder) | ~5–8% | Ja (mit Einschränkungen) |
| `large-v3-turbo-german`* | ~800M, DE-finetuned | **~2,6%** | Ja |

*Fine-tuned Modell: `TheChola/whisper-large-v3-turbo-german-faster-whisper` (Hugging Face)

---

## 2. Technologiebewertung: Whisper als Basis

### 2.1 Entscheidung: Whisper bleibt die richtige Wahl

Ein Wechsel des Kernsystems ist nicht empfohlen. Whisper ist für den AYEHEAR-Use-Case die am besten geeignete Open-Source-Technologie, weil:

- **Multilingual & Deutsch-stark:** Deutsch gehört zu den bestunterstützten Sprachen (top 5 weltweit)
- **Vollständig lokal ausführbar:** Keine Cloud-Abhängigkeit, vollständig DSGVO-konform
- **Aktives Ökosystem:** Optimierte Implementierungen (`faster-whisper`, `WhisperX`), Community-Fine-Tunes für Deutsch
- **Lizenz:** MIT — produktiv einsetzbar ohne Lizenzkosten

### 2.2 Was sich ändern muss: drei konkrete Upgrades

Die aktuelle Implementierung nutzt `openai/whisper` mit kleinen Modellen und ohne Vorverarbeitung. Das sind die drei Stellschrauben mit dem höchsten Hebel.

---

## 3. Empfohlene Zielarchitektur

### 3.1 Überblick

```
Audio-Input (Mikrofon / Datei)
        │
        ▼
┌─────────────────────┐
│  Audio-Vorverarbeitung │
│  FFmpeg: Normalisierung,│
│  Rauschreduzierung,    │
│  Mono 16kHz Konvertierung│
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Voice Activity     │
│  Detection (VAD)    │
│  Silero VAD         │
│  → Stille entfernen │
│  → Sprachsegmente   │
└────────┬────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Transkription: faster-whisper      │
│  Modell: large-v3-turbo-german      │
│  Engine: CTranslate2 (4x schneller) │
│  Quantisierung: int8 (CPU-optimiert)│
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────┐
│  Speaker Diarization│
│  pyannote.audio     │
│  → Sprecher A/B/C   │
│  → Zeitstempel      │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Strukturiertes     │
│  Transkript         │
│  [Sprecher A 00:02] │
│  "Text..."          │
└─────────────────────┘
```

### 3.2 Kernkomponente 1: `faster-whisper` (Pflicht-Upgrade)

**Was es ist:** Eine vollständige Reimplementierung der Whisper-Inferenz auf Basis von CTranslate2 — ein optimiertes Inferenz-Framework für Transformer-Modelle.

**Warum es besser ist als `openai/whisper`:**
- **4x schneller** bei identischer Genauigkeit (gleiche Modell-Gewichte)
- **50% weniger RAM-Verbrauch**
- Unterstützt int8-Quantisierung: Modelle auf CPU deutlich beschleunigt
- Drop-in-fähig: API nahezu identisch zur originalen Bibliothek

**Installation:**
```bash
pip install faster-whisper
```

**Minimales Verwendungsbeispiel:**
```python
from faster_whisper import WhisperModel

model = WhisperModel(
    "TheChola/whisper-large-v3-turbo-german-faster-whisper",
    device="cpu",          # oder "cuda" für GPU
    compute_type="int8"    # CPU-optimiert
)

segments, info = model.transcribe("meeting.wav", language="de", beam_size=5)

for segment in segments:
    print(f"[{segment.start:.1f}s] {segment.text}")
```

**Modell-Empfehlung:**

| Szenario | Modell | Begründung |
|---|---|---|
| Primärempfehlung | `TheChola/whisper-large-v3-turbo-german-faster-whisper` | Auf Deutsch optimiert, WER 2,6% |
| Fallback (ressourcenarm) | `distil-whisper/distil-large-v3` | 6x schneller, nur 1% WER-Abweichung |
| GPU vorhanden | `Systran/faster-whisper-large-v3` | Maximale Genauigkeit |

---

### 3.3 Kernkomponente 2: WhisperX (Pipeline-Wrapper)

**Was es ist:** Ein Python-Package, das faster-whisper, Silero-VAD und pyannote Speaker Diarization zu einer fertigen Pipeline verbindet.

**Was es zusätzlich liefert:**
- **Voice Activity Detection (VAD):** Entfernt automatisch Stille und Nicht-Sprache vor der Transkription → reduziert Halluzinationen (Whisper tendiert dazu, bei Stille "Text zu erfinden")
- **Word-level Timestamps:** Jedes Wort bekommt einen präzisen Zeitstempel
- **Speaker Diarization:** Erkennung, wer wann gesprochen hat — entscheidend für Meeting-Protokolle

**Installation:**
```bash
pip install whisperx
```

**Verwendungsbeispiel mit Sprechererkennung:**
```python
import whisperx

# Transkription
model = whisperx.load_model("large-v3-turbo", device="cpu", compute_type="int8", language="de")
audio = whisperx.load_audio("meeting.wav")
result = model.transcribe(audio, batch_size=8)

# Alignment (Wort-Zeitstempel)
model_a, metadata = whisperx.load_align_model(language_code="de", device="cpu")
result = whisperx.align(result["segments"], model_a, metadata, audio, device="cpu")

# Speaker Diarization
diarize_model = whisperx.DiarizationPipeline(use_auth_token="HF_TOKEN", device="cpu")
diarize_segments = diarize_model(audio)
result = whisperx.assign_word_speakers(diarize_segments, result)

# Output
for segment in result["segments"]:
    speaker = segment.get("speaker", "UNKNOWN")
    print(f"[{speaker}] {segment['text']}")
```

**Hinweis zu pyannote:** Die Speaker-Diarization von pyannote erfordert einmalig ein kostenloses Hugging Face Token mit Zustimmung zu den Modell-Nutzungsbedingungen. Das Modell wird dann lokal gecacht — kein Cloud-Zugriff im Produktivbetrieb.

---

### 3.4 Kernkomponente 3: Audio-Vorverarbeitung mit FFmpeg

Schlechte Audioqualität ist nach der Modellgröße der zweitgrößte Faktor für niedrige Erkennungsraten. Whisper erwartet 16kHz Mono-Audio.

**Empfohlene FFmpeg-Pipeline:**
```bash
ffmpeg -i input.wav \
  -af "highpass=f=200,lowpass=f=3000,afftdn=nf=-25" \
  -ar 16000 \
  -ac 1 \
  output_clean.wav
```

Was diese Pipeline macht:
- `highpass=f=200`: Entfernt tiefe Frequenzen (Lüfter, Klimaanlage)
- `lowpass=f=3000`: Entfernt hohe Frequenzen über dem Sprachbereich
- `afftdn=nf=-25`: Rauschreduzierung (-25 dB Schwellenwert)
- `-ar 16000 -ac 1`: Konvertierung zu 16kHz Mono (Whisper-Standard)

**Python-Integration:**
```python
import subprocess

def preprocess_audio(input_path: str, output_path: str) -> str:
    subprocess.run([
        "ffmpeg", "-i", input_path,
        "-af", "highpass=f=200,lowpass=f=3000,afftdn=nf=-25",
        "-ar", "16000", "-ac", "1",
        output_path, "-y"
    ], check=True, capture_output=True)
    return output_path
```

---

## 4. Hardware-Anforderungen und Performance-Erwartungen

### 4.1 CPU-only (Standard-Laptop)

| Modell | RAM | Echtzeit-Faktor | Anmerkung |
|---|---|---|---|
| `base` | ~1 GB | 0,1x (sehr schnell) | Aktuelle, unzureichende Lösung |
| `large-v3-turbo` int8 | ~3–4 GB | 0,5–1x | 1h Meeting = 30–60 Min Verarbeitung |
| `distil-large-v3` int8 | ~2–3 GB | 0,2–0,4x | Guter Kompromiss für schwächere Laptops |

### 4.2 GPU (dediziert oder integriert)

| GPU VRAM | Modell | Echtzeit-Faktor |
|---|---|---|
| 4 GB | `large-v3-turbo` fp16 | ~0,1x |
| 8 GB+ | `large-v3` fp16 | ~0,05x |

**Fazit:** Für die Zielgruppe "Standard-Geschäftslaptop ohne dedizierte GPU" ist `large-v3-turbo` mit int8-Quantisierung via faster-whisper die optimale Wahl. Die Verarbeitungszeit ist akzeptabel für ein Post-Meeting-Protokoll.

---

## 5. Vergleich: Aktueller Stand vs. Zielarchitektur

| Kriterium | Aktuell | Ziel |
|---|---|---|
| Bibliothek | `openai/whisper` | `faster-whisper` / `WhisperX` |
| Modell | `small` / `base` | `large-v3-turbo-german` |
| Erkennungsrate | ~70% | ~95–97% |
| Sprechertrennung | Keine | pyannote Diarization |
| Halluzinationen | Häufig (keine VAD) | Reduziert (Silero VAD) |
| RAM-Verbrauch | ~1 GB | ~3–4 GB |
| Verarbeitungsgeschwindigkeit | Sehr schnell, ungenau | Echtzeit ±, präzise |
| DSGVO-Konformität | Ja | Ja (alles lokal) |
| Installationsaufwand | Gering | Mittel (einmalig) |

---

## 6. Alternativen zu Whisper — Bewertung

Zur Vollständigkeit eine Übersicht evaluierter Alternativen, die für AYEHEAR nicht empfohlen werden:

| System | Vorteil | Ausschlussgrund |
|---|---|---|
| **NVIDIA Parakeet V3** | 10x schneller als Whisper | Primär englisch; Deutsch-Unterstützung limitiert; NVIDIA-Hardware Voraussetzung |
| **Apple Transcription API** | Sehr genau, lokal | Nur macOS/iOS; nicht plattformübergreifend |
| **Vosk** | Sehr leichtgewichtig | Deutlich geringere Genauigkeit als Whisper Large |
| **DeepSpeech** | Open Source | Nicht mehr aktiv gepflegt |
| **Kommerzielle APIs** (Azure, Google, AWS) | Sehr hohe Genauigkeit | Cloud-Abhängigkeit; nicht DSGVO-konform ohne Auftragsverarbeitungsvertrag; laufende Kosten |

---

## 7. Implementierungsplan

### Phase 1: Schnell-Upgrade (1–2 Tage)
1. `openai/whisper` → `faster-whisper` austauschen
2. Modell auf `large-v3-turbo` oder deutsches Fine-Tune upgraden
3. Audio-Vorverarbeitung via FFmpeg einbauen
4. Erkennungsrate messen und dokumentieren

### Phase 2: Pipeline-Integration (3–5 Tage)
5. `WhisperX` als Pipeline-Wrapper einführen
6. VAD aktivieren und konfigurieren
7. Speaker Diarization integrieren (pyannote, HF Token einrichten)
8. Strukturiertes Transkript-Output-Format definieren (JSON + Markdown)

### Phase 3: Produktivintegration (nach Bedarf)
9. Batch-Verarbeitung für aufgezeichnete Meetings
10. Echtzeit-Transkription evaluieren (für Live-Protokollierung)
11. Fine-Tuning auf unternehmensspezifisches Vokabular prüfen (LoRA)

---

## 8. Abhängigkeiten und offene Punkte

### Abhängigkeiten
- **Hugging Face Token** (kostenlos): Für pyannote Speaker Diarization einmalig erforderlich. Token wird lokal gespeichert, kein Cloud-Zugriff im Betrieb.
- **FFmpeg**: Systemseitig installiert (verfügbar für Windows, macOS, Linux)
- **RAM**: Mindestens 8 GB empfohlen für large-v3-turbo + Diarization gleichzeitig

### Offene Punkte für das Entwicklungsteam
- [ ] Zielplattform klären: Wird AYEHEAR als Desktop-App, CLI oder Server-Dienst ausgeliefert?
- [ ] Echtzeit vs. Post-Processing: Soll live transkribiert werden oder nach dem Meeting?
- [ ] Ausgabeformat: Markdown-Protokoll, Word-Export, JSON für API-Weiterverarbeitung?
- [ ] Vokabular-Fine-Tuning: Lohnt sich domänenspezifisches Fine-Tuning für häufige Kunden-Branchen (Recht, Medizin, Technik)?

---

## 9. Referenzen

- [faster-whisper — GitHub (SYSTRAN)](https://github.com/SYSTRAN/faster-whisper)
- [WhisperX — GitHub](https://github.com/m-bain/whisperX)
- [whisper-large-v3-turbo-german (Hugging Face)](https://huggingface.co/TheChola/whisper-large-v3-turbo-german-faster-whisper)
- [distil-whisper — Hugging Face](https://huggingface.co/distil-whisper/distil-large-v3)
- [pyannote.audio — Speaker Diarization](https://github.com/pyannote/pyannote-audio)
- [Best open source STT models in 2026 — Northflank](https://northflank.com/blog/best-open-source-speech-to-text-stt-model-in-2026-benchmarks)
- [WhisperX vs Competitors Benchmark](https://brasstranscripts.com/blog/whisperx-vs-competitors-accuracy-benchmark)
- [Meetily — lokale DSGVO-konforme Meeting-Transkription](https://meetily.ai/de)

---

*Dokument erstellt durch AYE Digital — Claude Cowork, 20. April 2026*  
*Alle genannten Werkzeuge sind Open Source (MIT / Apache 2.0 lizenziert) und ohne Cloud-Abhängigkeit einsetzbar.*
