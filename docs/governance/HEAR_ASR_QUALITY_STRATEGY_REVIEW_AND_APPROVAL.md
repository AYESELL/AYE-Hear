---
owner: AYEHEAR_ARCHITECT, AYEHEAR_DEVELOPER
status: APPROVED_FOR_IMPLEMENTATION
date: 2026-04-22
category: architecture-governance
related_document: docs/architecture/AYEHEAR_Spracherkennung_Architekturkonzept_v1.1.md
---

# HEAR ASR-Qualitätsstrecke: Review & Implementation Approval

**Document:** [AYEHEAR_Spracherkennung_Architekturkonzept_v1.1.md](../architecture/AYEHEAR_Spracherkennung_Architekturkonzept_v1.1.md)  
**Status:** ✅ **APPROVED FOR PHASE 1 IMPLEMENTATION**  
**Date:** 22. April 2026  
**Reviewed by:** AYEHEAR_ARCHITECT (Analysis & Strategy), AYEHEAR_DEVELOPER (Implementation Feasibility)

---

## Executive Decision

**APPROVED:** The ASR-Qualitätsstrecke Concept (v1.1.1) is production-ready for Phase 1 (Evaluations-Infrastruktur) and Phase 2 (Modell-Benchmark). The document establishes:

1. Clear separation of concerns (ASR-Qualität ≠ Runtime-Stabilität)
2. Evidence-based decision gates with measurable criteria (WER ≥30%, RTF ≤1,5x, offline-first)
3. Operationalized metrics (Halluzinationsrate ≤2%, no external references)
4. Implementable test design with lauffähig testskript

Both architect and developer sign off on proceeding to Phase 1.

---

## Architect Review

**Reviewer:** AYEHEAR_ARCHITECT  
**Review Date:** 22. April 2026  
**Scope:** Architecture soundness, governance alignment, offline-first compliance, decision gates

### Architecture Checklist

| Check | Status | Notes |
|---|---|---|
| **Problem Separation** | ✅ PASS | ASR-Qualität strictly separated from Runtime-Stabilität in Abschnitt 1. Keine Vermischung in Ursachen/Lösungen. |
| **Ist-Architektur Accuracy** | ✅ PASS | Korrekt: faster-whisper bereits aktiv, small/balanced default, lokale Modell-Bundling. Gemessene WER-Werte (0,257 / 0,285) sind belastbar und referenziert. |
| **Offline-First Compliance** | ✅ PASS | Kritikpunkt behoben: VAD-Bundling explizit gefordert (Abschnitt 3.2). Kriterium 3 um Packaging-Integration erweitert. |
| **External Claims Contextualized** | ✅ PASS | "6x Qualitätssprung" / "WER 2,6%" sind jetzt deutlich als "Referenzwerte, interne Validierung erforderlich" gekennzeichnet. |
| **Decision Gates Measurable** | ✅ PASS | Alle drei Go/No-Go-Kriterien (Qualität, Laufzeit, Offline-First) sind konkret und prüfbar. WER ≥30%, RTF ≤1,5x, lokal gecacht. |
| **Halluzinationsrate Operationalized** | ✅ PASS | Definition: nicht-alignbare Token pro 100 Wörter, Schwelle ≤2%. Messbar und in Testskript integrierbar. |
| **Testdesign Sound** | ✅ PASS | Evaluations-Datensatz (10–15 reale Meetings, Ground-Truth), vier Kandidaten, klare Messprotokoll, lauffähiges Code-Beispiel. |
| **Governance Alignment** | ✅ PASS | Passt zur QUALITY_FIRST_NEXT_RELEASE_SCOPE. ASR als Qualitätshebel, nicht als Release-Blocker. Parallel zu Runtime-Stabilität ausführbar. |
| **ADR Compliance** | ✅ PASS | Keine Violations gegenüber ADR-0002 (Windows Stack), ADR-0004 (Audio-Capture), ADR-0006/0008 (Persistence, Hardware-Profiles). |

### Architect Sign-Off

✅ **APPROVED BY ARCHITECT**

The ASR-Qualitätsstrecke strategy is architecturally sound, governance-aligned, and ready for developer implementation. The approach balances ambition (30% WER reduction) with reality (measured on own data, offline-first constraint). 

**Conditions for Phase 1 Implementation:**
- Evaluations-Datensatz-Owner muss klar benannt werden (Abschnitt 7, offene Frage 1)
- VAD-Bundling-Verantwortung muss zu DevOps/Packaging delegiert werden
- Testskript (Abschnitt 4.3) sollte in `tools/scripts/` oder `tests/` bereitgestellt werden

---

## Developer Review

**Reviewer:** AYEHEAR_DEVELOPER  
**Review Date:** 22. April 2026  
**Scope:** Implementation feasibility, code integration points, dependencies, timeline estimation

### Implementation Checklist

| Check | Status | Notes |
|---|---|---|
| **Dependencies Available** | ✅ PASS | faster-whisper ✓, jiwer ✓, torch (für Silero) ✓ — alle in pyproject.toml oder als optional `ml` extra. |
| **Integration Points Clear** | ✅ PASS | Preprocessing: `AudioCaptureService._preprocess()` hook ergänzbar. VAD: neue Stage vor ASR. Modell-Swap: `transcription.py` model_name Argument. |
| **Code Feasibility** | ✅ PASS | Testskript (Abschnitt 4.3) ist Python-Standard mit `faster_whisper`, `time`, `jiwer`. Kein Framework-Lift erforderlich. |
| **Database Impact** | ✅ PASS | Keine DB-Schema-Änderungen. Transcript-Persistierung bleibt unverändert. Testdaten sauber vom Produktivbetrieb trennbar. |
| **Build Pipeline Integration** | ⚠️ PARTIAL | Modell-Bundling (Phase 3) braucht Packaging-Anpassung. `Build-WindowsPackage.ps1` muss um Modell-Staging erweitert werden — ist **nicht in diesem Konzept gelöst**, aber bekannt und planbar. |
| **Timeline Estimation** | ✅ PASS | Phase 1 (Infrastruktur): 2–3 Tage ✓ realistisch. Phase 2 (Benchmark): 1–2 Tage ✓ realistisch (parallelisierbar mit Packaging-Prep). |
| **Rollback Path** | ⚠️ NOTED | Fallback-Szenario "Candidate C" ist dokumentiert, aber Rollback-Automation (z. B. WER-Monitoring) ist nicht in diesem Konzept — empfohlen als Phase 3+ Verbesserung. |
| **Offline-First Testability** | ✅ PASS | VAD und Preprocessing können offline entwickelt werden. Modell-Swap-Tests können mit gecachten Modellen laufen. |

### Developer Sign-Off

✅ **APPROVED BY DEVELOPER**

The ASR-Qualitätsstrecke is implementable without architectural surprises. Phases 1 and 2 are well-scoped and timeline-realistic. Dependencies are available. Integration points are clear.

**Implementation Roadmap:**

| Phase | Owner | Duration | Dependencies | Blocker Risks |
|---|---|---|---|---|
| **Phase 1: Evaluations-Infrastruktur** | AYEHEAR_QA (Primary), AYEHEAR_DEVELOPER (Support) | 2–3 Tage | Ground-Truth-Datensatz, Zugriff auf echte Meeting-Aufnahmen | Evaluations-Datensatz-Beschaffung (größte Unsicherheit) |
| **Phase 2: Modell-Benchmark** | AYEHEAR_DEVELOPER | 1–2 Tage | Phase 1 komplett, vier Modelle lokal cachebar | Keine bekannt — Testskript ist isolated |
| **Phase 3: Packaging-Integration** | AYEHEAR_DEVOPS (Primary), AYEHEAR_DEVELOPER (Support) | 1–2 Tage | Phase 2 Go/No-Go Entscheidung (Siegermodell) | Build-Pipeline-Änderungen (DevOps-Scope) |

**Critical Dependencies Before Start:**
1. ☑️ Evaluations-Datensatz-Owner (AYEHEAR_QA recommended)
2. ☑️ Mindestens 10–15 reale Meeting-Aufnahmen (anonymisiert, ~30 Min total)
3. ☑️ Ground-Truth-Transkripte (manuell oder Seed + Korrektur)

---

## Risk Assessment

| Risk | Severity | Mitigation | Owner |
|---|---|---|---|
| **R1: Evaluations-Datensatz nicht repräsentativ** | Medium | Kriterium: Mix aus 1:1, Gruppen, Fachvokabular, unterschiedliche Akustik (Abschnitt 4.1) | AYEHEAR_QA |
| **R2: Keine Kandidat erfüllt WER ≥30% Gate** | Medium | Fallback: Candidate C + Preprocessing-Effekt messen; oder Re-Evaluation mit Custom-Modellen | AYEHEAR_ARCHITECT (Go/No-Go) |
| **R3: Silero VAD Add-Dependency-Overhead** | Low | VAD ist optional; kann in Phase 3+ oder separate Branch entwickelt werden | AYEHEAR_DEVELOPER |
| **R4: RTF (Laufzeit) überschreitet Zielhardware-Budget** | Medium | Candidate C ist Fallback; wenn auch zu langsam, fokus auf Preprocessing-only | AYEHEAR_DEVELOPER |
| **R5: Packaging Integration komplexer als erwartet** | Low | Modell-Bundling nicht kritisch für Phase 2; kann iterativ in Phase 3 gelöst werden | AYEHEAR_DEVOPS |

---

## Quality Gates (Before Production Release)

Dieser Phase-1/2-Release (Testdesign & Benchmark) **erfordert nicht** die vollen AYE-Hear Quality Gates, da es **interne QA/Evaluations-Infrastruktur** ist, nicht produktiv live.

**Vor Produktiv-Release eines neuen Modells (Phase 3):**
- ✅ Benchmark-Ergebnis muss alle drei Go/No-Go-Kriterien erfüllen
- ✅ Kandidat muss in `config/default.yaml` und `requirements.txt` konservativ gepinnt werden
- ✅ Regression-Test: `small` weiterhin funktional (Fallback)
- ✅ Security recheck (Silero VAD offline, kein Netzwerk)
- ✅ Release notes dokumentieren: alte WER → neue WER, RTF Impact, Hardware-Anforderungen

**Produktpräferenz für Packaging (2026-04-22):**
- Wenn das Benchmark-Gate für **Kandidat B** (`TheChola/whisper-large-v3-turbo-german-faster-whisper`) auf GO geht, ist dieser Kandidat der **bevorzugte Standard für die nächste Installer-Version**.
- Phase 3 ist dann nicht als generische "irgendein Gewinner-Modell"-Integration zu lesen, sondern als gezielte Verankerung des deutschen Fine-Tune-Modells im Build- und Bundling-Pfad.
- Bis HEAR-137 formal abgeschlossen ist, bleibt `small` der aktuelle Default; nach GO muss HEAR-138 das deutsche Modell als gebündelten Default umsetzen und `small` nur noch als validierten Fallback behalten.

**Nicht-Waiver für HEAR-136 (2026-04-22):**
- Der vorhandene Seed-Datensatz genügt, um den Benchmark-Helper technisch per Dry-Run zu verifizieren.
- Er genügt **nicht** als Evidenzbasis für eine autoritative HEAR-137-Entscheidung über einen neuen Installer-Default.
- Wenn das Ziel ein belastbarer Modellwechsel im Produkt ist, bleibt HEAR-136 mit repräsentativen realen Meeting-Aufnahmen und Ground-Truth-Transkripten verpflichtend.

---

## Sign-Off Summary

| Role | Status | Signature | Date |
|---|---|---|---|
| **AYEHEAR_ARCHITECT** | ✅ APPROVED | [Architect Name/ID] | 22. April 2026 |
| **AYEHEAR_DEVELOPER** | ✅ APPROVED | [Developer Name/ID] | 22. April 2026 |
| **AYEHEAR_QA** (Implicit) | ℹ️ NOTED | Task owner HEAR-XXX | — |

---

## Next Steps & Task Delegation

### Immediate (Next 2–3 Days)

1. **Evaluations-Datensatz vorbereiten** (AYEHEAR_QA Owner)
   - Sammeln: 10–15 echte Meeting-Aufnahmen (~30 Min total)
   - Anonymisieren: Personenbezogene Daten entfernen
   - Ground-Truth: Manuelle Transkript-Korrektur oder Seed + Validator

2. **Testskript aus Abschnitt 4.3 ins Repo integrieren** (AYEHEAR_DEVELOPER)
   - `tools/scripts/evaluate_asr_candidates.py` oder `tests/test_asr_benchmark.py`
   - Abhängigkeiten prüfen (jiwer, psutil, torch falls VAD getestet)
   - Lokale Test-Run mit `small`-Baseline

3. **Task-CLI Tasks erstellen** (AYEHEAR_ARCHITECT oder Task-Owner)
   - HEAR-XXX-A: Phase 1 — Evaluations-Infrastruktur
   - HEAR-XXX-B: Phase 2 — Modell-Benchmark
   - HEAR-XXX-C: Phase 3 — Packaging-Integration (defer if Go for Candidate)

4. **Packaging-Umsetzungsregel anwenden** (AYEHEAR_DEVOPS, nach HEAR-137 GO)
   - Bevorzugter Zielkandidat für den Installer: `TheChola/whisper-large-v3-turbo-german-faster-whisper`
   - `Build-WindowsPackage.ps1` und Bundling-Layout auf das neue Default-Modell erweitern
   - `small` als Offline-Fallback-Regressionspfad beibehalten

### Timeline Estimate

| Phase | Weeks | Teams |
|---|---|---|
| **Phase 1** | W1 (Mon–Wed) | QA, Developer |
| **Phase 2** | W1 (Wed–Fri) | Developer |
| **Phase 3** (if Go) | W2 | DevOps, Developer |
| **Release Decision** | End W2 | Architect |

---

## Reference Documents

- [ASR-Qualitätsstrecke Concept](../architecture/AYEHEAR_Spracherkennung_Architekturkonzept_v1.1.md)
- [Quality-First Release Scope](../architecture/QUALITY_FIRST_NEXT_RELEASE_SCOPE.md)
- [HEAR-113 ASR Benchmark](../HEAR-113-qa-evidence.md) (Current small baseline)
- [ADR-0004 Audio Capture](../adr/0004-audio-capture-and-preprocessing.md)
- [Build Windows Package](../../tools/scripts/Build-WindowsPackage.ps1)

---

**Document Status:** ✅ **FINAL — Ready for Implementation Hand-Off**

Prepared by: AYEHEAR_ARCHITECT (Analysis) + AYEHEAR_DEVELOPER (Feasibility)  
Date: 22. April 2026
