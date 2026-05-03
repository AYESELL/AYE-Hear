---
owner: AYEHEAR_SECURITY
task: HEAR-141-RECHECK
status: APPROVED
date: 2026-04-22
category: security-review
prior-review: HEAR-142-security-review.md
---

# Security-Recheck: HEAR-141 Async-Pipeline + WAV-Persistenz

## Scope

Pflicht-Recheck (PM-3 aus HEAR-142) nach Abschluss der HEAR-141-Implementierung.

Geprüfte Dateien:
- `src/ayehear/services/audio_capture.py` (NEU: `_elevate_capture_thread_priority`, `WavPersistenceConfig`, `_flush_wav`, `cleanup_expired_wav_files`)
- `src/ayehear/services/transcription.py` (NEU: `AdaptiveTranscriptionQueue`, `_merge_segments`)
- `src/ayehear/services/protocol_engine.py` (NEU: CPU-Idle-Gate in `generate()`)
- `config/default.yaml` (NEU: `privacy:`-Block aus HEAR-142)
- `tests/test_hear_141_async_pipeline.py` (26 Tests, alle grün)

Aufbauend auf:
- HEAR-142 Security-Review (CONDITIONAL-APPROVED, 2026-04-22)
- HEAR-134 Security-Review (APPROVED)

---

## Executive Decision

**APPROVED**

Alle drei Pflicht-Maßnahmen aus HEAR-142 (PM-1, PM-2, PM-3) sind umgesetzt.
HEAR-141 hält die in HEAR-142 gesetzten Security-Auflagen ein. WAV-Persistenz ist
standardmäßig deaktiviert, der Offline-First-Vertrag ist unverändert, und keine
neuen externen Abhängigkeiten wurden eingeführt.

---

## Pflicht-Maßnahmen aus HEAR-142 – Abschlussstatus

| PM | Maßnahme | Status |
|----|----------|--------|
| PM-1 | GDPR-Löschdialog im Uninstaller | **UMGESETZT** (HEAR-142 Review, `ayehear-installer.nsi`) |
| PM-2 | WAV-Retention-Config in `config/default.yaml` + Implementierung | **UMGESETZT** (HEAR-141 + HEAR-142) |
| PM-3 | Security-Recheck nach PM-1 + PM-2 | **DIESES DOKUMENT – APPROVED** |

---

## Security-Checkliste HEAR-141

### 1. WAV-Persistenz (`WavPersistenceConfig`, `_flush_wav`)

| Prüfpunkt | Ergebnis | Nachweis |
|-----------|----------|---------|
| `enabled = False` als sicherer Default | PASS | `WavPersistenceConfig.enabled: bool = False`; `config/default.yaml: wav_persistence_enabled: false` |
| WAV-Ausgabepfad ist immer unter `runtime/wav/` | PASS | `out_dir = self._wav_config.output_dir` (default `Path("runtime/wav")`); kein Export-Pfad |
| WAV-Dateiname enthält keine User-kontrollierten Daten (Path-Traversal) | PASS | `stem = self._meeting_id or "unknown"` — `meeting_id` ist UUID (`str(uuid.uuid4())`), nur `[0-9a-f-]`; `timestamp` nur `[0-9TZ]`; `Path`-Konkatenation blockiert keine Verzeichniswechsel, aber UUID-Format schließt `..`/`/` aus |
| Stille-Frames werden nicht gepuffert | PASS | `if self._wav_config.enabled and not segment.is_silence: self._wav_buffer.append(...)` |
| Kein Netz-Upload für WAV-Dateien | PASS | Nur `wave.open(..., "wb")` und `wav_path.unlink()` — kein `requests`, `urllib`, `socket`, `httpx` in scope |
| TTL-Cleanup-Funktion vorhanden | PASS | `cleanup_expired_wav_files(wav_dir, retention_days)` implementiert und getestet |
| `delete_on_meeting_end`-Pfad korrekt | PASS | Datei wird nach Write sofort gelöscht via `wav_path.unlink(missing_ok=True)` |
| Exception-Handling verhindert Datenleck | PASS | `except Exception: logger.error(...); return None` — kein Partial-State-Leak |
| WAV-Buffer nach Flush geleert | PASS | `finally: self._wav_buffer = []` (im finally-Block) |

**Nebenbefund – WAV-Buffer-Clearing:** Der `finally`-Block in `_flush_wav()` stellt sicher, dass der Puffer auch bei Ausnahmen geleert wird — wichtig zur Vermeidung von Speicher-Akkumulation über mehrere Meetings. ✅

---

### 2. Thread-Priority-Elevation (`_elevate_capture_thread_priority`)

| Prüfpunkt | Ergebnis | Nachweis |
|-----------|----------|---------|
| Kein Privilege-Escalation-Risiko | PASS | `THREAD_PRIORITY_HIGHEST = 2` hebt nur die Thread-Priorität (nicht Prozessrechte); Standard-Win32-API, kein Admin erforderlich |
| Non-Windows wird sicher ignoriert | PASS | `if sys.platform != "win32": return False` als erste Prüfung |
| ctypes-Fehler werden abgefangen | PASS | `except Exception as exc: logger.warning(...); return False` |
| Capture-Pipeline startet auch ohne Elevation | PASS | Best-effort: `SetThreadPriority`-Fehler loggt Warnung, blockiert nicht |
| Kein Angreifer-kontrollierter Parameter | PASS | Keine User-Inputs; nur System-Handles aus `GetCurrentThread()` |

---

### 3. `AdaptiveTranscriptionQueue` und `_merge_segments`

| Prüfpunkt | Ergebnis | Nachweis |
|-----------|----------|---------|
| Kein externer I/O | PASS | Rein In-Process: `psutil.cpu_percent()` (lokal) + `transcribe_fn`-Aufruf (intern) |
| Exception in `transcribe_fn` propagiert nicht | PASS | `except Exception: logger.error(...)` in `_flush()` — Pipeline läuft weiter |
| CPU-Load-Check ohne Netz | PASS | `psutil.cpu_percent(interval=None)` — nur lokale Systemabfrage |
| `psutil` nicht verfügbar → sicherer Default | PASS | `_get_cpu_load` gibt `0.0` zurück → kein Batching (Low-CPU-Modus = sofort flush) |
| Merged Segment enthält keine neuen Daten | PASS | `np.concatenate` über bestehende Samples; kein externer Einfluss |

---

### 4. `ProtocolEngine` CPU-Idle-Gate

| Prüfpunkt | Ergebnis | Nachweis |
|-----------|----------|---------|
| Deferred-Snapshot enthält keine sensitiven Meeting-Daten | PASS | `ProtocolContent()` ist leer; nur `meeting_id` (UUID) und `version=0` übergeben |
| Kein LLM-Aufruf bei Deferral | PASS | Funktion kehrt vor `_call_ollama()` zurück |
| Loopback-Guard für Ollama unverändert | PASS | `_validate_loopback_url()` ist unverändert (verifiziert in HEAR-134) |
| CPU-Threshold durch externen Wert nicht manipulierbar | PASS | `_PROTOCOL_CPU_DEFER_THRESHOLD = 80.0` ist Konstante; kein Config-Lese-Pfad |

---

### 5. Keine neuen Netz-Abhängigkeiten

| Modul | Imports geprüft | Ergebnis |
|-------|----------------|---------|
| `audio_capture.py` | `sounddevice`, `numpy`, `wave`, `ctypes`, `threading`, `pathlib`, `struct`, `sys` | PASS – alle lokal/stdlib |
| `transcription.py` (Änderungen) | `psutil` (CPU-Check), `numpy` | PASS – psutil ist lokal |
| `protocol_engine.py` (Änderungen) | `psutil` (CPU-Check) | PASS – lokal |

---

### 6. Config-Sicherheit (`config/default.yaml`)

| Prüfpunkt | Ergebnis |
|-----------|----------|
| `wav_persistence_enabled: false` | PASS – sicherer Default |
| `wav_output_dir: runtime/wav` | PASS – relativ, nie absoluter Pfad zu System-Verzeichnissen |
| Kein Credential oder Secret in der Config | PASS – reine Retention-Parameter |

---

## Tests

| Test-Suite | Tests | Ergebnis |
|-----------|-------|---------|
| `tests/test_hear_141_async_pipeline.py` | 26 | **26/26 GRÜN** |

Abgedeckte Szenarien u.a.:
- WAV disabled → keine Datei geschrieben
- WAV enabled → korrekte Datei mit korrektem PCM-Format
- `delete_on_meeting_end` → Datei nach Write sofort entfernt
- Stille-Frames nicht gepuffert
- TTL-Cleanup: alte Dateien entfernt, neue behalten
- Thread-Priority: Windows-Erfolg, Windows-Fehler, non-Windows, ctypes-Import-Error
- AdaptiveQueue: Low-CPU sofort flush, High-CPU Batching, force-flush, Exception-Isolation
- CPU-Idle-Gate: Deferral bei ≥80%, kein Deferral bei <80%, Boundary-Test

---

## Offline-First und GDPR – Gesamtstatus nach HEAR-141

| Anforderung | Status |
|-------------|--------|
| Kein externer Audio-Aufruf | PASS |
| WAV-Persistenz standardmäßig aus | PASS |
| WAV-Dateien verbleiben lokal | PASS |
| Löschmethoden für Speaker-Profile | PASS (aus HEAR-142) |
| GDPR-Löschdialog bei Deinstallation | PASS (aus HEAR-142) |
| Loopback-Guard für Ollama | PASS (unverändert seit HEAR-134) |
| BitLocker als Pflicht-Voraussetzung | PASS (ADR-0009, unverändert) |

---

## Verwandte Dokumente

- [HEAR-142-security-review.md](HEAR-142-security-review.md) – ursprünglicher Privacy-Review (CONDITIONAL-APPROVED)
- ADR-0015: Async-First Audio Pipeline and Retention Controls
- ADR-0009: Data Protection and Encryption-at-Rest Model

---

**Erstellt:** 2026-04-22  
**Erstellt von:** AYEHEAR_SECURITY  
**Entscheidung:** APPROVED – HEAR-141 darf in die Integrations-/Release-Pipeline
