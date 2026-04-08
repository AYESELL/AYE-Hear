---
status: accepted
context_date: 2026-04-08
decision_owner: AYEHEAR_ARCHITECT
---

# ADR-0002: Windows Desktop App Stack (PySide6 + Python)

## Context

AYE Hear requires a desktop GUI that integrates tightly with local audio capture, background processing (transcription, diarization), and real-time UI updates.

Stack tradeoffs:

- **Electron:** Cross-platform but heavy; audio integration challenging
- **Qt/PySide6:** Native look & feel, tight OS integration, good audio support
- **WinForms/.NET:** Windows-only but proven; heavy framework
- **PySimpleGUI:** Lightweight but limited for complex real-time UX

## Decision

Build AYE Hear using **Python 3.11+ backend + PySide6 (Qt) for desktop UI**, with the following rationale:

1. **Language:** Python
   - Faster prototyping for ML/audio pipelines
   - Rich ecosystem (faster-whisper, pyannote, Ollama client libraries)
   - Easy integration with NumPy, scipy for audio processing
   - Team skill alignment with AYE KNOW backend

2. **GUI Framework:** PySide6 (Qt6)
   - Native Windows look & feel; adheres to Windows design patterns
   - Strong audio integration (QAudioInput via WASAPI)
   - Declarative UI via .ui files or imperative PyQt style
   - Thread-safe signal/slot architecture for background tasks

3. **Packaging:** PyInstaller + NSIS
   - PyInstaller bundles Python runtime + dependencies into .exe
   - NSIS generates professional Windows installer
   - Automatic updates via custom launcher script (V2+)

4. **Project Structure:**

   ```
   src/
   ├── ayehear/
   │   ├── app/
   │   │   ├── main_window.py         (PySide6 main UI)
   │   │   ├── dialogs/
   │   │   ├── widgets/
   │   ├── services/
   │   │   ├── audio_capture.py       (WASAPI input)
   │   │   ├── diarization.py         (Pyannote)
   │   │   ├── transcription.py       (Faster-Whisper)
   │   │   ├── protocol_engine.py     (LLM + logic)
   │   │   ├── speaker_manager.py     (Enrollment + matching)
   │   ├── models/
   │   │   ├── meeting.py
   │   │   ├── segment.py
   │   │   ├── speaker.py
   │   ├── storage/
   │   │   ├── postgres_store.py      (PostgreSQL persistence layer)
   │   └── utils/
   │       ├── config.py
   │       ├── logging.py
   │   └── main.py                    (Entry point)
   └── tests/
   ```

5. **Dependencies (Core):**
   - `pyside6` – GUI framework
   - `faster-whisper` – Speech-to-text
   - `pyannote.audio` – Speaker diarization
   - `silero-vad` – Voice Activity Detection
   - `sounddevice` or `pyaudio` – Audio input
   - `numpy`, `scipy` – Signal processing
   - `ollama` (client library) – Local LLM
   - `sqlalchemy` + `psycopg[binary]` – PostgreSQL access layer

## Consequences

**Positive:**

- Pythonic codebase aligns with AYE KNOW team
- PySide6 handles real-time UI updates smoothly
- WASAPI integration via sounddevice + PySide6 audio
- Single-language stack simplifies deployment

**Negative:**

- Python app size: ~400-600 MB (with bundled models)
- Slower startup (Python interpreter + cold model load)
- Platform-limited to Windows (would need Qt for Mac/Linux)

**Mitigations:**

- Lazy-load heavy models (Whisper, Ollama) after splash screen
- Pre-cache models at install time
- Incremental startup telemetry

## Alternatives Considered

1. **Electron + Node.js backend**
   - Rejected: Heavy bundle, audio integration via node-speaker fragile

2. **Tauri (Rust + web UI)**
   - Considered: Lighter than Electron, but Rust learning curve + ecosystem immaturity for audio/ML

3. **C# WinForms + .NET**
   - Rejected: Language shift; Python ecosystem advantage for ML

## Related ADRs

- ADR-0001: Product Architecture
- ADR-0003: Diarization Pipeline
- ADR-0004: Audio Capture

---

**Status:** Accepted  
**Owner:** AYEHEAR_ARCHITECT  
**Updated:** 2026-04-08
