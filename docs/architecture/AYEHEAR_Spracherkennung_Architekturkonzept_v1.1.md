# AYEHEAR — ASR-Qualitätsstrecke: Technisches Konzept

**Version:** 1.1  
**Datum:** 20. April 2026  
**Status:** Überarbeitet nach Team-Review  
**Änderungen gegenüber v1.0:** Ist-Architektur korrigiert (faster-whisper bereits aktiv); strikte Trennung ASR-Qualität vs. Runtime-Stabilität; Testdesign und Go/No-Go-Kriterien neu ergänzt  
**Zielgruppe:** Architekten und Entwickler des AYEHEAR-Projekts

---

## Abgrenzung: Was dieses Dokument behandelt — und was nicht

Dieses Dokument befasst sich ausschließlich mit **Problemfeld 2: ASR-/Transkriptionsqualität** — also der inhaltlichen Erkennungsgenauigkeit der Sprachverarbeitung.

Nicht behandelt werden in diesem Dokument:

- Laufzeitstabilität (Abbrüche, Session-Handling)
- Persistenz- und Datenbankfehler (ID/FK-Fehler, Meeting-Close-Fehler)
- Architektur der Nachfolgekomponenten (Protokollgenerierung, Action-Item-Extraktion)

Diese Trennung ist bewusst, weil beide Problemfelder unterschiedliche Ursachen, Hebel und Lösungswege haben und eine Vermischung die Analyse verzerrt.

---

## 1. Ist-Architektur (korrigierter Stand)

AYE Hear betreibt bereits eine offline-first Desktop-Implementierung mit folgender ASR-Pipeline:

| Komponente | Aktueller Stand |
|---|---|
| ASR-Engine | `faster-whisper` (bereits integriert) |
| Default-Modell | `small` |
| Profil | `balanced` |
| Inferenz | CPU, vollständig lokal |
| Audio-Basis | 16 kHz, Mono |
| Verarbeitungsmodus | Chunk-basiert |
| Vorverarbeitung | RMS-Normalisierung, einfache Stille-Erkennung |
| Persistenz | Segment-basiert in lokale DB |
| Cloud-Abhängigkeit | Keine (offline-first) |

**Ablauf:**

```
Audioaufnahme (Segmente)
        │
        ▼
Vorverarbeitung: RMS-Normalisierung + Stille-Erkennung
        │
        ▼
Transkription pro Segment (faster-whisper, small, balanced)
        │
        ▼
Segment-Persistenz → Protokollgenerierung / Action-Item-Extraktion
```

### 1.1 Gemessene Erkennungsqualität (interne QA)

| Modell | Accuracy | WER | Einordnung |
|---|---|---|---|
| `small` | 74,29 % | 0,2571 | ca. jedes 4. Wort falsch |
| `base` | 71,43 % | 0,2857 | minimal schlechter als small |

Die Messwerte sind konsistent mit der User-Wahrnehmung. Der geringe Unterschied zwischen `base` und `small` zeigt, dass das Problem nicht durch ein weiteres kleines Upgrade innerhalb derselben Modell-Klasse gelöst wird.

### 1.2 Konsequenz für Folgeprozesse

Fehler in der Transkription pflanzen sich in nachgelagerte Komponenten fort. Ein WER von ~0,26 bedeutet, dass jede vierte Einheit im Transkript potenziell fehlerhaft ist — für semantisch sensible Aufgaben wie Protokollgenerierung oder Action-Item-Extraktion ist das ein kritischer Ausgangszustand.

---

## 2. Problemfeldanalyse: Ursachen der niedrigen ASR-Qualität

Modellgröße ist ein starker, aber nicht der einzige Hebel. Die folgende Übersicht zeigt alle identifizierten Einflussfaktoren auf die Erkennungsqualität:

| Faktor | Aktueller Zustand | Einfluss auf WER | Adressiert in v1.1? |
|---|---|---|---|
| Modellgröße | `small` — unterdimensioniert für Fachvokabular, Mehrsprecherszenarien | Hoch | Ja (Test-Kandidaten) |
| Audio-Preprocessing | RMS-Normalisierung, keine Filterung | Mittel | Ja |
| Segmentierung / VAD | Einfache Stille-Erkennung | Mittel–Hoch | Ja |
| Sprecherüberlappung | Nicht behandelt | Mittel | Teilweise (VAD-Verbesserung) |
| Fachvokabular | Kein domänenspezifisches Fine-Tuning | Mittel | Offen (Phase 2) |
| Dialekt / Akzent | Keine Konfiguration | Niedrig–Mittel | Implizit (größeres Modell) |

Die ASR-Qualitätsstrecke muss daher als **Gesamtsystem** betrachtet werden: Modell + Audio-Preprocessing + VAD. Ein isolierter Modellwechsel ohne Verbesserung der vorgelagerten Stufen verspielt einen Teil des möglichen Gewinns.

---

## 3. Ziel-Qualitätsstrecke (ASR-only)

Die nachfolgende Zielarchitektur ergänzt und verfeinert die bestehende Pipeline. Sie ist als **Evaluations- und Migrationspfad** konzipiert, nicht als Sofortwechsel.

```
Audioaufnahme (Segmente, 16 kHz Mono)
        │
        ▼
┌──────────────────────────────────────┐
│  Stufe 1: Audio-Preprocessing        │
│  FFmpeg-Pipeline:                    │
│  - Highpass-Filter (>200 Hz)         │
│  - Lowpass-Filter (<3.000 Hz)        │
│  - Spektrale Rauschreduzierung       │
│  - Pegeloptimierung                  │
│  Ziel: reproduzierbare Audiobasis    │
└────────────────┬─────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────┐
│  Stufe 2: VAD (Silero VAD)           │
│  - Sprachsegmente isolieren          │
│  - Stille und Nichtssprache          │
│    vor ASR entfernen                 │
│  - Halluzinationsreduktion           │
│  Ziel: saubere Segmentgrenzen        │
└────────────────┬─────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────┐
│  Stufe 3: ASR                        │
│  faster-whisper (bereits integriert) │
│  Modell: Test-Kandidaten (→ Kap. 4)  │
│  Sprache: de, beam_size ≥ 5          │
│  Ziel: WER ≤ 0,10 auf Zieldaten     │
└────────────────┬─────────────────────┘
                 │
                 ▼
Segment-Persistenz → Folgeprozesse (unverändert)
```

### 3.1 Stufe 1: Audio-Preprocessing

Die aktuelle RMS-Normalisierung ist ein guter Ausgangspunkt, aber sie adressiert weder Frequenzrauschen noch spektrale Artefakte, die Whisper-Modelle stören.

**Erweiterte FFmpeg-Pipeline:**

```python
import subprocess

def preprocess_audio(input_path: str, output_path: str) -> str:
    """
    Standardisierte Audio-Vorverarbeitung für AYEHEAR ASR.
    Konservative Einstellungen — bei clean audio nicht überprocessen.
    """
    subprocess.run([
        "ffmpeg", "-i", input_path,
        "-af", "highpass=f=200,lowpass=f=3000,afftdn=nf=-25,loudnorm",
        "-ar", "16000",
        "-ac", "1",
        output_path, "-y"
    ], check=True, capture_output=True)
    return output_path
```

Wichtiger Hinweis: Überprocessing bei qualitativ guter Audiobasis kann die WER verschlechtern. Die Preprocessing-Parameter müssen auf realen Meeting-Aufnahmen kalibriert werden.

### 3.2 Stufe 2: VAD mit Silero

Silero VAD ist ein schlankes, lokal lauffähiges Voice-Activity-Detection-Modell, das direkt in die bestehende Python-Pipeline integriert werden kann.

**Wichtig (Offline-First-Compliance):**  
Das Silero-VAD-Modell muss als vorgefertigtes Bundle im Paketierungsschritt (z. B. in `sys._MEIPASS` für PyInstaller) vorliegen. Runtime-Downloads von Hugging Face sind nicht zulässig, um die Offline-First-Anforderung zu erfüllen. Das Modell muss lokal vorinitialisiert werden, vergleichbar mit der bestehenden Whisper-Modell-Bundling-Strategie.

```python
import torch
from pathlib import Path

# ⚠️ OFFLINE-FIRST: torch.hub.load darf NICHT zur Laufzeit aufgerufen werden,
# da es standardmäßig Remote-Downloads auslöst.
# Korrekte Nutzung: Modell-Verzeichnis vorab lokal bereitstellen (Build-Schritt),
# dann per repo_or_dir auf absoluten lokalen Pfad zeigen (kein Remote-Repo-String).

# Entwicklungsumgebung (Modell vorab manuell gecacht):
SILERO_LOCAL_DIR = Path.home() / ".cache" / "silero_vad"

# Packaged Runtime (PyInstaller): aus sys._MEIPASS
# SILERO_LOCAL_DIR = Path(sys._MEIPASS) / "models" / "silero_vad"

model, utils = torch.hub.load(
    repo_or_dir=str(SILERO_LOCAL_DIR),  # lokaler Pfad — kein Remote-Download
    model='silero_vad',
    source='local',
    force_reload=False,
    trust_repo=True
)
get_speech_timestamps, _, read_audio, *_ = utils

def get_speech_segments(audio_path: str):
    """Gibt Sprachsegmente als Zeitstempel-Liste zurück."""
    wav = read_audio(audio_path, sampling_rate=16000)
    return get_speech_timestamps(wav, model, sampling_rate=16000)
```

Silero VAD ist:
- vollständig offline betreibbar (mit vorgefertigtem lokalem Modell-Bundle)
- sehr leichtgewichtig (~1 MB Modell)
- direkt mit faster-whisper kombinierbar

---

## 4. Testdesign: Evidenzbasierte Modellentscheidung

Die Entscheidung für oder gegen ein größeres Modell muss auf **eigenen Zieldaten** gemessen werden, nicht auf externen Benchmark-Referenzwerten. Externe WER-Werte sind aufnahmebedingungsabhängig und nicht übertragbar.

### 4.1 Evaluations-Datensatz

Ein robuster Entscheidungstest erfordert einen repräsentativen Datensatz aus realen AYEHEAR-Meetings:

| Anforderung | Spezifikation |
|---|---|
| Mindestumfang | 10–15 Meeting-Segmente, zusammen ≥ 30 Minuten Audio |
| Repräsentativität | Mix aus 1:1-Gesprächen, Gruppenrunden (≥3 Sprecher), Fachvokabular |
| Ground Truth | Manuell korrigierte Referenztranskripte (Gold Standard) |
| Varianz | Unterschiedliche Mikrofon-/Raumsituationen abdecken |
| Anonymisierung | Personenbezogene Daten vor Verwendung entfernen |

### 4.2 Test-Kandidaten (Modelle)

| Kandidat | Modell | Begründung |
|---|---|---|
| **Baseline (Status quo)** | `small` / `balanced` | Referenz für alle Vergleiche |
| **Kandidat A** | `large-v3-turbo` | Hauptkandidat: externe Referenzen deuten auf signifikanten Qualitätsgewinn bei vertretbaren CPU-Kosten; interne Messung erforderlich |
| **Kandidat B** | `TheChola/whisper-large-v3-turbo-german-faster-whisper` | DE-optimiertes Fine-Tune; externe Referenzen zeigen WER 2,6%, aber nicht auf euren Zieldaten; interne Validierung erforderlich |
| **Kandidat C** | `distil-large-v3` | Kompromiss-Kandidat: schnellere Variante als large-v3; externe Referenzen deuten auf ~1% WER-Nachteil, muss intern gemessen werden |

Alle Kandidaten laufen mit `faster-whisper` — die bestehende Integration bleibt unverändert, nur das Modell-Argument wird ausgetauscht.

### 4.3 Messprotokoll

Für jeden Kandidaten werden folgende Metriken auf dem eigenen Evaluations-Datensatz erhoben:

```
Primäre Qualitätsmetriken:
  WER (Word Error Rate)          — Standardmetrik, primär
  CER (Character Error Rate)     — stabiler bei kurzen Segmenten
  Accuracy (1 - WER)             — für Kommunikation mit Stakeholdern

Sekundäre Metriken:
  Laufzeit (Echtzeit-Faktor)     — Sekunden Verarbeitung / Sekunde Audio
  Peak-RAM-Verbrauch (MB)
  Halluzinationsrate             — Zählung: nicht-alignbare Token (Wörter/Zeichenfolgen, die nicht im Ground-Truth vorkommen) pro 100 Wörter Output; Schwelle: ≤ 2% für Acceptance

Zielplattform-Tests:
  Standard-Laptop CPU (kein GPU)  — z. B. Intel i7-12th Gen oder äquivalent
  RAM ≤ 8 GB Gesamtsystem (Speicherbudget)
```

**Testskript-Struktur:**

```python
from faster_whisper import WhisperModel
import time, jiwer

CANDIDATES = {
    "baseline":  ("small",                      {"language": "de", "beam_size": 5}),
    "kandidat_a": ("large-v3-turbo",             {"language": "de", "beam_size": 5}),
    "kandidat_b": ("TheChola/whisper-large-v3-turbo-german-faster-whisper",
                                                 {"language": "de", "beam_size": 5}),
    "kandidat_c": ("distil-whisper/distil-large-v3", {"language": "de", "beam_size": 5}),
}

def evaluate(model_name, transcribe_kwargs, audio_files, references):
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    results = []
    for audio, ref in zip(audio_files, references):
        t0 = time.time()
        segments, _ = model.transcribe(audio, **transcribe_kwargs)
        hypothesis = " ".join(s.text for s in segments)
        elapsed = time.time() - t0
        duration = get_audio_duration(audio)
        results.append({
            "wer":       jiwer.wer(ref, hypothesis),
            "rtf":       elapsed / duration,   # Echtzeit-Faktor
            "hypothesis": hypothesis,
            "reference":  ref,
        })
    return results
```

---

## 5. Go/No-Go-Kriterien für den Modellwechsel

Der Wechsel auf ein größeres Modell wird nur dann vollzogen, wenn **alle drei** der folgenden Kriterien erfüllt sind:

### Kriterium 1: Qualitätsgewinn reproduzierbar auf intern gemessenen Daten

| Messgröße | Go-Schwelle | Hinweis |
|---|---|---|
| WER-Reduktion gegenüber Baseline (`small`) | ≥ 30% relativ (d. h. von 0,257 auf ≤ 0,18) | Gemessen auf eigenem Evaluations-Datensatz, nicht auf externen Referenzen |
| Konsistenz | Gilt für ≥ 80% der Test-Segmente (kein Einzelwert-Ausreißer) | Keine extreme Variabilität zwischen Segmenten |
| Verbesserung bei Fachvokabular | Messbar besser als Baseline auf Fachbegriff-Teilmenge | Falls Fachvokabular im Evaluations-Set enthalten ist |
| Halluzinationsrate | ≤ 2% (siehe Messprotokoll in Abschnitt 4.3) | Keine erhöhte Neigung zu erfundenem Text |

### Kriterium 2: Laufzeit auf Zielhardware akzeptabel

| Szenario | Akzeptabler Echtzeit-Faktor |
|---|---|
| Post-Meeting-Verarbeitung | ≤ 1,5x Realtime (1h Meeting → max. 90 Min Verarbeitung) |
| Near-Realtime (optional) | ≤ 0,3x Realtime (für zukünftige Live-Protokollierung) |
| Peak-RAM | ≤ 6 GB (lässt 2 GB für OS und Folgeprozesse bei 8-GB-System) |

### Kriterium 3: Offline-first und Packaging gewährleistet

- Modell muss vollständig lokal gebündelt werden (z. B. in `sys._MEIPASS` oder als Docker-Layer)
- Kein Runtime-Download von Modellteilen, Hugging Face-Access oder externen Ressourcen zur Laufzeit
- DSGVO-konform: keine Audiodaten verlassen das Gerät
- Packaging-Integration: Das Modell muss in den Standard-Build-Prozess (z. B. `Build-WindowsPackage.ps1`) aufgenommen werden können

**Entscheidungsfluss:**

- **Wenn alle drei Kriterien erfüllt:** Wechsel auf Gewinner-Modell (z. B. Kandidat A oder B) als neuen Default  
  → Neu: `config/default.yaml` → `whisper_model: <Gewinner>`  
  → Modell in Bundling-Strategie aufnehmen

**Produktentscheidungs-Notiz (2026-04-22):**

- Falls **Kandidat B** (`TheChola/whisper-large-v3-turbo-german-faster-whisper`) die Go/No-Go-Kriterien erfüllt, ist er der **bevorzugte Zielkandidat für die nächste Installer-Version**.
- In diesem Fall soll der Installer das deutsche Modell nicht nur optional unterstützen, sondern als **gebündelten Standard** ausliefern.
- `small` bleibt als technischer Fallback und Regressionsanker erhalten, bis die produktive Stabilität des neuen Defaults im gebauten Paket bestätigt ist.

- **Wenn Kriterium 1 (Qualität) nicht erfüllt, aber Kriterium 2 & 3 ok:** Kandidat C (`distil-large-v3`) als Fallback evaluieren  
  → Besserer Kompromiss als `small`, wenn auch nicht die volle Qualitätszielstellung  
  → Abhängig von Prioritäten (Geschwindigkeit vs. Qualität)

- **Wenn kein Kandidat alle Kriterien erfüllt:** Fokus auf VAD und Audio-Preprocessing ohne Modellwechsel  
  → Messung des Effekts von Preprocessing + VAD auf `small`-Baseline  
  → Re-Evaluation mit neuen Kandidaten in nächster Iteration (z. B. Custom-Modelle, domänenspezifisches Fine-Tuning)

---

## 6. Implementierungsphasen

### Phase 1: Evaluations-Infrastruktur aufbauen (2–3 Tage)

- Evaluations-Datensatz aus realen Meetings zusammenstellen und Ground-Truth-Transkripte erstellen
- Testskript implementieren (WER, RTF, RAM-Messung)
- Baseline `small` formal messen und dokumentieren

### Phase 2: Modell-Benchmark (1–2 Tage)

- Alle drei Kandidaten auf Evaluations-Datensatz durchlaufen lassen
- Go/No-Go-Entscheidung treffen
- Siegerkandidaten als neuen Default konfigurieren

### Phase 3: Pipeline-Verbesserung (3–5 Tage, parallel möglich)

- Silero VAD integrieren und Segmentgrenzen-Qualität messen
- FFmpeg-Preprocessing als optionale Stufe einbauen und Effekt auf WER messen
- Kombination aller Stufen (Preprocessing + VAD + neues Modell) abschließend evaluieren

### Phase 4: Produktivübernahme (nach Go-Entscheidung)

- Konfiguration auf neues Default-Modell umstellen
- Laufzeitverhalten auf Zielhardware-Spektrum validieren
- Dokumentation und Rollback-Pfad festhalten

---

## 7. Offene Punkte — Entscheidungsbedarf Team

Die folgenden Fragen sind für den Fortgang relevant und liegen teilweise außerhalb des Scope dieses Konzepts:

- [ ] **Evaluations-Datensatz-Verantwortung**: Wer erstellt, pflegt und aktualisiert die Ground-Truth-Transkripte?
- [ ] **Use-Case-Priorisierung**: Ist Near-Realtime-Transkription (live protokollieren während Meeting läuft) ein Anforderungsziel, oder ist Post-Processing nach dem Meeting ausreichend? Dies beeinflusst die RTF-Schwellenwerte.
- [ ] **Fachvokabular-Tuning**: Soll domänenspezifisches Fine-Tuning (LoRA, Fachvokabular-Anpassung) als Phase 2 eingeplant werden, oder fokussieren wir zuerst auf Base-Modellwechsel?
- [ ] **Rollback-Strategie**: Wie wird gesteuert, wenn ein in Produktion eingeführtes Modell schlechter abschneidet als erwartet? (z. B. automatisches Downgrade bei WER-Anstieg)
- [ ] **Silero VAD Bundling**: Wer ist verantwortlich für das Bundling des VAD-Modells in den Installationsproduktionen? Abhängigkeit zu Packaging/DevOps.

---

## 8. Referenzen

- [faster-whisper — GitHub (SYSTRAN)](https://github.com/SYSTRAN/faster-whisper)
- [WhisperX — GitHub](https://github.com/m-bain/whisperX)
- [whisper-large-v3-turbo-german (Hugging Face)](https://huggingface.co/TheChola/whisper-large-v3-turbo-german-faster-whisper)
- [distil-whisper — Hugging Face](https://huggingface.co/distil-whisper/distil-large-v3)
- [Silero VAD — GitHub](https://github.com/snakers4/silero-vad)
- [jiwer — WER/CER Evaluationsbibliothek](https://github.com/jitsi/jiwer)
- [Best open source STT models 2026 — Northflank](https://northflank.com/blog/best-open-source-speech-to-text-stt-model-in-2026-benchmarks)
- [AYEHEAR Ist-Architektur](src/ayehear/services/transcription.py)
- [Audio Capture und Preprocessing](src/ayehear/services/audio_capture.py)
- [Aktuelle Konfiguration](config/default.yaml)

---

*Dokument v1.1.1 — AYE Digital UG, 22. April 2026*  
*Überarbeitet auf Basis des Architect-Reviews vom 22. April 2026:*
*- Offline-First-Widerspruch bei VAD behoben: explizite Anforderung lokales Modell-Bundling*
*- Externe Qualitätsclaims als "Referenzwerte, interne Validierung erforderlich" gekennzeichnet*
*- Halluzinationsrate operationalisiert (≤ 2% nicht-alignbare Token)*
*- Go/No-Go-Kriterium 3 um Packaging-Integration erweitert*
*- Offene Punkte präzisiert und Verantwortungsmodell skizziert*
