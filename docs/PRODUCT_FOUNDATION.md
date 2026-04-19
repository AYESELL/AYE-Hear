---
status: active
owner: AYEHEAR_ARCHITECT
updated: 2026-04-16
---

# AYE Hear Product Foundation

**Version:** Active (Two-State Scope Baseline)  
**Date:** 2026-04-16  
**Audience:** All AYEHEAR\_\* personas

---

## 🎯 Product Vision

AYE Hear is a Windows desktop application for **local, offline-first meeting transcription, speaker identification, and intelligent protocol generation**. Designed for organizations that require privacy-first meeting intelligence with full local control.

## Scope Integrity Statement (ADR-0010)

Current release governance uses two explicit states:

| State | Current Status | Source |
| --- | --- | --- |
| Operations-Handoff Readiness | GO | HEAR-052 / HEAR-112 |
| Product-Complete Readiness | GO | HEAR-086 / HEAR-088 / HEAR-110 / HEAR-112 |

This distinction remains mandatory for all V1 scope claims, and both states are currently green for validation candidate `0.5.3`.

## Reading Guide: Current State vs Target State

To avoid ambiguity, this document uses a strict separation:

- **Target State (Vision):** `Core Promises`, `Architecture at a Glance`, and `User Workflow` describe the intended product-complete behavior.
- **Current State (Operations-Handoff):** `V1.0 Operations-Handoff Scope (Current)` is the only authoritative description of what is currently release-approved.

If a target statement conflicts with current implementation, the operations-handoff scope and release governance records take precedence.

### Core Promises

Target-state note:
- The following promises describe the intended product-complete vision and are not a claim that all capabilities are currently available in operations-handoff.

- **Complete Privacy:** All audio processing happens locally. Zero transmission to cloud.
- **Speaker Clarity:** Pre-meeting voice enrollment + live speaker identification with confidence scoring.
- **Live Insight:** Real-time meeting protocol with captured decisions, tasks, open items, risks.
- **Meeting Context:** Distinguish internal meetings from external (customer/vendor conversations).
- **Reliability:** Offline operation. Confidence scores for every speech attribution. Manual override always available.

---

## 🏗️ Architecture at a Glance (ADR-0001)

Target-state note:
- The architecture table below reflects the intended product-complete architecture baseline and not a statement that every component is fully implemented in the current operations-handoff release.

| Component               | Tech                                  | Why                                                                            |
| ----------------------- | ------------------------------------- | ------------------------------------------------------------------------------ |
| **Desktop App**         | PySide6 (Qt6)                         | Native Windows feel, thread-safe audio                                         |
| **Audio Input**         | WASAPI via sounddevice                | Standard Windows microphone                                                    |
| **Speech Segmentation** | Silero VAD + Pyannote                 | Filters noise, detects speaker changes                                         |
| **Speaker ID**          | Pyannote embeddings + cosine matching | Pre-meeting enrollment, confidence-scored                                      |
| **Transcription**       | Faster-Whisper                        | Fast, offline, CPU/GPU adaptive                                                |
| **Protocol Engine**     | Local LLM via Ollama                  | 7B–13B model, real-time extracts decisions/tasks                               |
| **Storage**             | PostgreSQL                            | Canonical storage for meeting history, speaker profiles and protocol revisions |
| **Export**              | Markdown, DOCX, PDF                   | User-friendly final output                                                     |

---

## 📋 User Workflow

Target-state note:
- The workflow below describes the intended product-complete flow. For currently available behavior, see `V1.0 Operations-Handoff Scope (Current)`.

```
1. Start Meeting
   ├─ Choose type: Internal | External (Customer/Vendor)
   ├─ Meeting name & participants
   ├─ Select participant template:
   │  ├─ Herr/Frau + Last Name + Company
   │  └─ First Name + Last Name + Company
   └─ Confirm audio device (Windows default)

2. Speaker Enrollment (Pre-Meeting)
   ├─ Each participant speaks 5-10 sec reference
   ├─ Introduction text is matched against pre-registered participant names
   ├─ System captures voice profile
   └─ Quality check (confidence ≥ 0.75)

3. Live Recording & Protocol
   ├─ Standard microphone active
   ├─ Real-time transcription with speaker labels
   ├─ Live protocol updates (decisions, tasks, risks)
   ├─ "Show Current State" button for mid-meeting review
   └─ Flag uncertain speaker matches

4. End & Finalize
   ├─ Review captured decisions, tasks, open items
   ├─ Correct any speaker mismatches and participant name assignments
   ├─ Approve protocol
   └─ Export as Markdown, DOCX, or PDF
```

---

## 🔑 Key Design Principles (ADRs)

1. **Offline-First (ADR-0001):** No external API calls. All processing local.
2. **Windows-First (ADR-0002):** Desktop app with PySide6, WASAPI audio, NSIS installer.
3. **Speaker Identification (ADR-0003):** Mandatory pre-enrollment. Confidence-scored matching.
4. **Audio Quality (ADR-0004):** WASAPI capture, 16 kHz, VAD filtering, level normalization.
5. **Local Protocol Engine (ADR-0005):** Real-time LLM-powered extractions with confidence.

---

## 🚀 V1 Scope

### V1.0 Operations-Handoff Scope (Current)

- ✅ Windows 10/11 desktop app (standalone)
- ✅ Standard Windows microphone capture
- ✅ Speaker identification with confidence scoring and manual correction path
- ✅ Real microphone-based enrollment workflow implemented in code/runtime path
- ✅ Live transcription
- ✅ Real-time protocol generation (decisions, tasks, open items)
- ✅ Protocol export implementation for Markdown, DOCX and PDF
- ✅ Transcript export as runtime TXT artifact
- ✅ Meeting history (local PostgreSQL)
- ✅ Manual speaker correction
- ✅ CPU & GPU adaptive (auto-profile at startup)
- ✅ Installed-package commissioning evidence bundle completed for validation candidate `0.5.3`

### V1 Product-Complete Scope (Target)

- ✅ Real microphone-based speaker enrollment workflow
- ✅ Production speaker embedding backend (no deterministic stub in production path)
- ✅ Export parity with Markdown, DOCX, PDF contract
- ✅ All V1 capability matrix entries Green with linked evidence
- ✅ Installed-package E2E evidence bundle for setup, enrollment, transcription, attribution, protocol drafting, export, and runtime bootstrap/persistence

### Out of V1 (Post-Release)

- ⏳ Meeting platform integrations (Zoom, Teams plugins)
- ⏳ Stereo/multi-mic capture
- ⏳ Speaker profile sharing across meetings
- ⏳ Cloud sync / backup
- ⏳ Web dashboard
- ⏳ Advanced analytics (turn-taking stats, sentiment, etc.)

---

## 🎯 Success Criteria (V1 Release)

Status note:
- Operations-handoff release criteria are currently met for controlled deployment.
- Product-complete criteria are satisfied for validation candidate `0.5.3`.

Current authority note:
- Installed-package E2E evidence is complete and green for the current validation candidate.
- Current release-state authority is documented in `docs/HEAR-112-readiness-reconciliation.md` with supporting evidence in `docs/HEAR-086-qa-evidence.md`, `docs/HEAR-088-qa-evidence.md`, `docs/HEAR-110-build-evidence.md`, and `deployment-evidence/hear-091/README.md`.

- **Usability:** End-to-end meeting protocol in <5 min (enroll + record + export)
- **Accuracy:** Speaker identification ≥85% on target hardware (CPU-only laptop, GPU laptop)
- **Reliability:** No crashes for 60-min recording; graceful recovery from device disconnect
- **Privacy:** Zero external API calls verified; audit logs show local-only processing
- **Documentation:** Setup guide, FAQ, troubleshooting guide included

---

## 👥 Roles (Agents)

| Role              | Owner    | Focus                                               |
| ----------------- | -------- | --------------------------------------------------- |
| AYEHEAR_ARCHITECT | Lead     | Architecture, ADRs, design governance               |
| AYEHEAR_DEVELOPER | Team     | Implementation, testing, code quality               |
| AYEHEAR_DEVOPS    | Infra    | CI/CD, Windows installer, build pipeline            |
| AYEHEAR_QA        | Quality  | Test strategy, quality gates, acceptance            |
| AYEHEAR_SECURITY  | Security | Privacy, encryption, GDPR, offline-first validation |

---

## 📚 Key Documents

- **ADRs:** [docs/adr/](docs/adr/) – Architecture decisions
- **Governance:** [docs/governance/](docs/governance/) – Process & roles
- **Quick Refs:** [docs/quick-refs/](docs/quick-refs/) – Setup, testing, CI/CD
- **This Doc:** PRODUCT_FOUNDATION.md

---

## 🔒 Privacy & Compliance

- **Audio:** Remains on user's machine; never transmitted
- **Speaker Profiles:** Stored in local PostgreSQL with repository-governed protection requirements
- **Protocol Artifacts:** Local files only; protocol export implementation supports Markdown, DOCX and PDF, while transcript export remains TXT
- **GDPR:** Users own all data; delete on-demand via local file removal
- **Telemetry:** None by default; opt-in analytics for V2+

---

## 💪 Tech Stack at a Glance

```
Backend:          Python 3.11+
GUI:              PySide6 (Qt6)
Audio:            sounddevice + WASAPI
VAD:              Silero VAD
Diarization:      Pyannote.audio
Transcription:    Faster-Whisper
LLM:              Ollama (7B–13B)
Storage:          PostgreSQL
Export:           python-docx, reportlab (PDF)
Build:            PyInstaller + NSIS
CI/CD:            GitHub Actions (planned)
```

---

## 🎓 Getting Started by Role

### 👨‍💼 AYEHEAR_ARCHITECT

1. Read this document
2. Review [docs/adr/](docs/adr/) – Understand core decisions
3. Define design approval process for PRs

### 👨‍💻 AYEHEAR_DEVELOPER

1. Read this document
2. Setup: [docs/quick-refs/DEVELOPMENT_SETUP_QUICKREF.md](docs/quick-refs/DEVELOPMENT_SETUP_QUICKREF.md)
3. Start with Phase 1: `Get-Task -Role AYEHEAR_DEVELOPER`

### 🔒 AYEHEAR_SECURITY

1. Read this document + [docs/adr/0001 thru 0005](docs/adr/)
2. Define security checklist (offline-first, encryption, credential handling)
3. Review every PR touching audio, storage, or speaker data

### 🧪 AYEHEAR_QA

1. Read this document + [docs/governance/QUALITY_GATES.md](docs/governance/QUALITY_GATES.md)
2. Set up test hardware (CPU-only laptop + GPU laptop)
3. Create test plan for speaker identification (confidence thresholds)

### 🚀 AYEHEAR_DEVOPS

1. Read this document + [docs/adr/0002](docs/adr/0002-windows-desktop-app-stack.md)
2. Design CI/CD pipeline (GitHub Actions)
3. Create NSIS installer script

---

**Owner:** AYEHEAR_ARCHITECT  
**Updated:** 2026-04-16
