---
owner: AYEHEAR_LEAD
status: active
updated: 2026-09-30
category: governance
---

# Stand AYE Hear

Stand: 2026-09-30 · gepflegt von der Projektleitung `ayehear-lead` · höchstens eine Seite

## Aktueller Arbeitsblock

**Go/No-Go-Klärung (Block 1).** Ziel: Entscheidungsgrundlage für Sascha, ob AYE Hear weitergebaut, auf fertige Bausteine umgebaut oder eingestellt wird. Tasks: HEAR-197 (Architekt, 13 SP). Auftrag: [GO_NOGO_AUFTRAG.md](GO_NOGO_AUFTRAG.md), Bericht: `GO_NOGO_2026-10.md` (Entwurf).

## Wo wir stehen

- Letzte Code-Änderungen: 2026-05-11, Version 0.7.x (i18n DE/EN, ASR-Sprachumschaltung, Installer 0.7.1). Seitdem nur Governance-/Kit-Commits.
- Nachweislich erledigt: Migration 005 (Transcript-Confidence) ist im Code und in Installer 0.6.8 gebündelt (HEAR-164/166); HEAR-157 (Build 0.6.3) ist DONE.
- Veraltet oder offen: HEAR-164 (IN_PROGRESS), HEAR-155 (REVIEW, NO-GO-Stand von Mai), HEAR-136 (IN_PROGRESS), HEAR-194 (IN_PROGRESS, Rollout ist mit HEAR-195 DONE vermutlich überholt).
- Der ASR-Benchmark (HEAR-136/137/138) wartete auf Referenzdaten aus Live-Tests; er geht in HEAR-197 auf.
- Erkennungsgenauigkeit der Prototypen: etwa 80 bis 90 %, zu wenig für brauchbare Protokolle (Aussage Sascha).

## Nächste Schritte

1. HEAR-197 Phase 1 und 2: Bestandsaufnahme und Testplan (Architekt, läuft).
2. Sascha: Aufnahmen und Referenzen bereitstellen, Lizenzfragen vor Downloads entscheiden.
3. HEAR-197 Phase 3: Messungen und Marktvergleich, QA-Review der Messmethodik.
4. Sascha entscheidet Go / Umbau / No-Go. Danach Bereinigung der veralteten Tasks und Folgeplanung.

## Offene Entscheidungen für Sascha

- Testaufnahmen und Referenztranskripte (Testplan folgt mit Phase 2).
- Freigabe von Modell- und Tool-Downloads mit eingeschränkter Lizenz (nach Testplan).

## Aktuelle Tasks

Immer live aus der Task-CLI: `Get-Task -Project hear -Status IN_PROGRESS` bzw. `OPEN`.
