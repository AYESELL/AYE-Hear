---
owner: AYEHEAR_QA
status: draft
updated: 2026-04-16
category: qa-checklist
---

# HEAR-091 Installed E2E Checklist (Non-Default Path)

## Ziel
Diese Checkliste schließt die verbliebene HEAR-091-Evidenzluecke: frische Installed-Runtime-Nachweise (Screenshots + Logs + End-to-End-Flow) auf einem Non-Default-Installpfad.

## Guardrails (vor Start)
- Kein product-complete Claim ohne vollstaendig gruene Installed-E2E-Evidenz (HEAR-082).
- Degraded/Blocked in V1-kritischen Bereichen als NO-GO behandeln.
- Evidence muss aus der installierten Anwendung stammen (nicht nur aus Repo-Tests).

## 1) Preflight
- [ ] Aktuellen Installer verifizieren (Dateiname, Build-Zeit, SHA256)
- [ ] Zielpfad fuer Non-Default-Install festlegen (z. B. `D:\AyeHearCustom\app`)
- [ ] Lokalen Screenshot-Ordner fuer Evidence anlegen, z. B. `deployment-evidence/hear-091/`
- [ ] Runtime-Log-Sammelort notieren (install-root-relativ gemaess ADR-0011)

## 2) Installationsnachweis (Non-Default)
- [ ] Installer auf Non-Default-Pfad ausfuehren
- [ ] Screenshot: Installer-Zielpfad vor Abschluss
- [ ] Screenshot: erfolgreicher Installationsabschluss
- [ ] Screenshot/Log: tatsaechlicher Install-Root im Runtime-Kontext (kein harter C:-Pfad)

## 3) Readiness-Indikatoren im installierten Runtime-Start
- [ ] Screenshot: kompletter System-Readiness-Block sichtbar
- [ ] State je Komponente dokumentieren:
  - [ ] Database / Runtime Persistence
  - [ ] Transcript Persistence + Review Queue Backend
  - [ ] Speaker Enrollment Persistence
  - [ ] Local LLM / Protocol Engine Path
  - [ ] Audio Input Availability
  - [ ] Export Target Availability
- [ ] Aggregate State dokumentieren: Product Path Ready / Degraded / Blocked
- [ ] Passende Runtime-Log-Auszuege sichern (Zeitstempel + Bezug auf States)

## 4) E2E-Workflow im installierten App-Pfad
- [ ] Setup erfolgreich
- [ ] Enrollment mit persistenter Speicherung getestet
- [ ] Transcription laeuft im installierten Runtime-Flow
- [ ] Speaker Attribution sichtbar und nachvollziehbar
- [ ] Protocol Drafting (nicht nur Spiegelung) geprueft
- [ ] Export durchgefuehrt (Artefakte auffindbar und lesbar)
- [ ] Runtime Bootstrap konsistent (DSN/Backend-Verhalten plausibel)

## 5) Artefakt-Bundle (Pflicht)
- [ ] Mindestens 6-10 Screenshots mit Dateinamenkonvention gesammelt
- [ ] Runtime-Log-Auszuege je kritischem Schritt gesichert
- [ ] Export-Artefakte (Dateipfade + Dateiliste + Kurzpruefung) beigefuegt
- [ ] Evidence-Index erstellt (welcher Nachweis deckt welches AC)

## 6) AC-Mapping fuer HEAR-091
- [ ] AC1: Non-Default-Install + Screenshots/Logs = PASS
- [ ] AC2: Setup/Enrollment/Transcription/Attribution/Protocol/Export/Bootstrap = PASS
- [ ] AC3: Readiness-Semantik gegen Spec validiert = PASS
- [ ] AC4: docs/HEAR-086-qa-evidence.md und docs/HEAR-088-qa-evidence.md aktualisiert = PASS
- [ ] AC5: Guardrail eingehalten, kein product-complete ohne Gruenstatus = PASS

## 7) Abschlussentscheidung
- GO nur wenn alle AC PASS und kein V1-kritischer Blocked/Degraded-Widerspruch offen ist.
- NO-GO, wenn einer der Punkte fehlt oder nur durch lokale/in-repo Tests abgedeckt ist.

## 8) Dokument-Updates nach Durchlauf
- docs/HEAR-086-qa-evidence.md: Post-Fix Installed-E2E-Ergebnis + explizites GO/NO-GO
- docs/HEAR-088-qa-evidence.md: Readiness-Semantik mit installierten Screenshots/Logs
- Optional: zusaetzliche Sammeldoku unter `deployment-evidence/hear-091/README.md`
