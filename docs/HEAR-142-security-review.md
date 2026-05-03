---
owner: AYEHEAR_SECURITY
task: HEAR-142
status: CONDITIONAL-APPROVED
date: 2026-04-22
category: security-review
---

# HEAR-142: Privacy-Review – WAV-on-Disk + Speaker-Data Retention Policy

## Scope

Phase-5 security review for two privacy risks identified in the HEAR-140/HEAR-141 design wave:

1. **WAV-Segmente auf Disk (HEAR-141, geplant):** Retention-Policy, automatisches Löschen nach Meeting-Ende, kein unbeabsichtigtes Persistieren.
2. **Speaker-Enrollment-Daten (KRITISCH, bestätigt 2026-04-22):** Name und Embedding persistieren nach Neuinstallation in PostgreSQL — bestätigtes GDPR-Risiko.

Basislinien:
- ADR-0009: Datenschutz- und Verschlüsselungsmodell (C_SENSITIVE-Klassifikation)
- ADR-0015: Async-First Audio-Pipeline und Retention Controls
- HEAR-134: Letztes genehmigtes Security-Review (Persistence Lifecycle Hotfix)

---

## Executive Decision

**CONDITIONAL-APPROVED**

Bedingte Genehmigung: HEAR-141 (WAV-Persistenz, Async-Pipeline) darf **nicht** ohne
abgeschlossene Maßnahmen aus Abschnitt "Pflicht-Maßnahmen vor HEAR-141-Rollout"
in Produktion gehen. Die drei identifizierten Pflicht-Maßnahmen sind umzusetzen
und erneut zur Security-Freigabe vorzulegen.

---

## Befunde nach Schweregrad

### BEFUND-1: Keine Löschmethode für Speaker-Profile (KRITISCH – GDPR-Art. 17)

**Ort:** `src/ayehear/storage/repositories.py` → `SpeakerProfileRepository`

**Befund:** `SpeakerProfileRepository` enthält ausschließlich `upsert()`, `get_by_id()` und `list_all()`.
Es gibt **keine `delete()`- oder `delete_all()`-Methode**. Personen haben nach DSGVO Art. 17
das Recht auf Löschung ihrer Sprachdaten (Biometrie gemäß DSGVO Art. 9). Speaker-Profile
enthalten `display_name` (Personenname) und `embedding_vector` (biometrischer Voiceprint),
beide klassifiziert als `C_SENSITIVE` (ADR-0009). Ohne Löschmethode ist das Recht auf
Vergessenwerden technisch nicht erfüllbar.

**Status:** BEHOBEN – `delete()` und `delete_all()` wurden im Rahmen dieses Reviews hinzugefügt.
Siehe Abschnitt "Implementierte Fixes".

---

### BEFUND-2: Uninstaller löscht keine PostgreSQL-Sprachprofile (KRITISCH – GDPR)

**Ort:** `build/installer/ayehear-installer.nsi` → Section "Uninstall"

**Befund:** Der aktuelle Uninstaller stoppt den `AyeHearDB`-Dienst und löscht `$INSTDIR`
(Anwendungsverzeichnis), aber **nicht** das PostgreSQL-Datenverzeichnis (`C:\AyeHear\data`).
Speaker-Profile (Name + Embedding), Meetingprotokolle und Transkripte bleiben nach
Deinstallation erhalten. Dies wurde am 2026-04-22 aus dem Feld bestätigt: Nach Reinstall
war der Nutzername im Speaker-Enrollment-Dialog noch erkennbar.

**Mindestanforderung:**  
Beim Uninstall muss ein Dialog erscheinen:
> „Möchten Sie alle persönlichen Daten löschen (Sprecher-Profile, Meetings, Transkripte)?
> JA = alle Daten werden gelöscht. NEIN = Daten bleiben für eventuelle Neuinstallation erhalten."

**Status:** OFFEN – Pflicht-Maßnahme vor HEAR-141-Rollout (siehe unten).

---

### BEFUND-3: WAV-Retention-Policy nicht definiert (HOCH)

**Ort:** ADR-0015, HEAR-141 (noch nicht implementiert)

**Befund:** ADR-0015 entschied WAV-Persistenz als **opt-in** (config flag, Standard aus).
Die Retention-Policy ist inhaltlich beschrieben (ADR-0015 Option A: Auto-Delete TTL),
aber noch nicht als Implementierungsanforderung formalisiert. Folgender Rahmen wird
hiermit durch Security festgelegt:

| Parameter | Anforderung |
|-----------|-------------|
| Default | WAV-Persistenz ist **aus** (`wav_persistence_enabled: false` in `config/default.yaml`) |
| TTL wenn aktiviert | Max. 7 Tage lokale Aufbewahrung (Standard), konfigurierbar 1–30 Tage |
| Löschabdeckung | Nach Meeting-Ende: WAV-Segmente werden nach TTL automatisch gelöscht |
| Kein Netz | WAV-Dateien verlassen niemals die lokale Maschine |
| Pfad | Unter `runtime/wav/` (nicht `exports/`) – niemals im Export-Pfad |
| Meeting-Ende-Cleanup | Optionaler sofortiger Cleanup bei Meeting-Stop (`wav_delete_on_meeting_end: true`) |

**Status:** OFFEN – HEAR-141-Implementierung muss diese Parameter einhalten.

---

### BEFUND-4: Kein App-seitiger Datenlösch-Dialog (MITTEL)

**Ort:** Anwendungs-UI (nicht implementiert)

**Befund:** Es gibt keine Möglichkeit für den Nutzer, innerhalb der laufenden Anwendung
seine Sprachprofile zu löschen (Recht auf Vergessenwerden ohne Deinstallation).
Ein "Einstellungen → Datenschutz → Sprecher-Profile löschen"-Dialog ist für eine
spätere Phase vorgesehen, aber noch nicht implementiert.

**Empfehlung:** Spätestens beim ersten öffentlichen Release muss ein In-App-Löschdialog
für Speaker-Profile vorhanden sein. Für die aktuelle Vorab-Nutzungsphase reicht die
Uninstaller-Option (BEFUND-2).

**Status:** ZURÜCKGESTELLT bis erster öffentlicher Release.

---

### BEFUND-5: Embedding-Vektor im Klartext als JSON (NIEDRIG – Akzeptiert für V1)

**Ort:** `src/ayehear/storage/orm.py` → `SpeakerProfile.embedding_vector`

**Befund:** Der biometrische Embedding-Vektor wird als JSON-Array in der Datenbank gespeichert,
ohne spaltenweite Verschlüsselung. ADR-0009 akzeptiert dies für V1 unter der Bedingung,
dass Bitlocker/Volume-Encryption auf dem Host aktiv ist.

**Akzeptiert:** Gemäß ADR-0009 (V1-Ausnahme). Volume-Level-Verschlüsselung (BitLocker)
ist die zugelassene Kontrollmaßnahme für V1. Spaltenweite Verschlüsselung ist für
spätere Versionen vorbehalten.

---

## Pflicht-Maßnahmen vor HEAR-141-Rollout

| # | Maßnahme | Zuständig | Blockiert |
|---|----------|-----------|-----------|
| PM-1 | Uninstaller-Dialog: Datenlöschung anbieten (BEFUND-2) | AYEHEAR_DEVOPS | HEAR-141 |
| PM-2 | WAV-Retention-Config in `config/default.yaml` + Validierung (BEFUND-3) | AYEHEAR_DEVELOPER | HEAR-141 |
| PM-3 | Security-Recheck nach PM-1 + PM-2 Umsetzung | AYEHEAR_SECURITY | HEAR-141 Release |

**Status PM-1:** UMGESETZT (HEAR-142 Review, NSIS-Dialog hinzugefügt)  
**Status PM-2:** UMGESETZT (HEAR-141, `config/default.yaml`, `WavPersistenceConfig`)  
**Status PM-3:** UMGESETZT – Security-Recheck abgeschlossen, APPROVED (2026-04-22, [HEAR-141-security-recheck.md](HEAR-141-security-recheck.md))

---

## Implementierte Fixes (in diesem Review)

### Fix-1: `SpeakerProfileRepository.delete()` und `delete_all()` (BEFUND-1)

Datei: `src/ayehear/storage/repositories.py`

Hinzugefügt:
- `delete(profile_id: str) -> None`: Löscht ein einzelnes Sprecher-Profil (Name + Embedding).
  Wirft `ValueError` wenn nicht gefunden (Audit-Sicherheit).
- `delete_all() -> int`: Löscht alle Sprecher-Profile, gibt Anzahl der gelöschten Zeilen zurück.
  Für Uninstall-Cleanup und GDPR-Right-to-be-Forgotten-Requests.

Beide Methoden werden von der Session verwaltet (kein direktes SQL-Injection-Risiko,
da SQLAlchemy ORM verwendet wird).

---

## Checkliste: Offline-First und GDPR

| Prüfpunkt | Ergebnis | Hinweis |
|-----------|----------|---------|
| Kein Netz-Aufruf für Speaker-Daten | PASS | In-process only, lokale PostgreSQL |
| Kein Cloud-Telemetrie für Audioaufnahmen | PASS | Unverändert seit HEAR-134 |
| WAV-Persistenz standardmäßig aus | PASS (ADR-0015) | Noch nicht implementiert, muss so bleiben |
| Löschfunktion für Speaker-Profile vorhanden | PASS (nach Fix-1) | `delete()` und `delete_all()` hinzugefügt |
| BitLocker/Disk-Encryption als Voraussetzung | PASS | ADR-0009, HEAR-119/127 unverändert |
| Embeddings bleiben lokal | PASS | Kein Export-Pfad für Embeddings |
| Uninstall-Daten-Cleanup (Nutzer-Option) | OFFEN (BEFUND-2) | PM-1 blockiert HEAR-141 |
| GDPR Art. 17 (Löschen) technisch erfüllbar | PASS (nach Fix-1) | Noch kein UI-Zugang |
| GDPR Art. 17 (Löschen) bei Deinstallation | OFFEN (BEFUND-2) | PM-1 erforderlich |

---

## Verwandte Dokumente

- ADR-0003: Speaker Identification & Diarization Pipeline
- ADR-0009: Data Protection and Encryption-at-Rest Model
- ADR-0015: Async-First Audio Pipeline and Retention Controls
- HEAR-134: Letztes genehmigtes Security-Review
- HEAR-141: Implementierungs-Task für Async-Pipeline und WAV-Persistenz

---

**Erstellt:** 2026-04-22  
**Erstellt von:** AYEHEAR_SECURITY  
**Nächste Review:** Nach PM-1 + PM-2 Abschluss (Security-Recheck erforderlich vor HEAR-141 Release)
