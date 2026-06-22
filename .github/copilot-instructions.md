---
owner: AYEHEAR_ARCHITECT
status: active
updated: 2026-05-16
category: agent-configuration
---

# Copilot Instructions (AYE Hear)

**Version:** 1.0 | **Date:** 2026-04-08

---

## 🏠 Repository Context (PRIMARY)

**This is the PRIMARY repository for all AYEHEAR_* personas.**

**Home Personas:**
- AYEHEAR_ARCHITECT
- AYEHEAR_DEVELOPER
- AYEHEAR_DEVOPS
- AYEHEAR_QA
- AYEHEAR_SECURITY

**Default Behavior:**
- ✅ **Primary workspace:** `AYE-Hear` (this repository)
- ✅ **Default actions:** All file operations, commits happen HERE unless explicitly specified
- ✅ **Cross-repo read:** Access to `../platform-tools/` for ADRs, Quick-Refs, Task-CLI (read-only)
- ✅ **Cross-repo read:** Access to `../aye-know/` for offline-first appliance patterns (read-only)
- ⚠️ **Cross-repo write:** Only via task delegation

**Rule:** Unless user explicitly specifies different path, all AYEHEAR_* personas work in `AYE-Hear` by default.

---

## 🌍 Locale & Context

- **Antworten auf Deutsch (de)**
- **Code/Docs:** English
- **Task Names:** English (reference platform-tools task system)

---

## 📋 Key Documentation

### Foundation (MANDATORY START)
- [PRODUCT_FOUNDATION.md](docs/PRODUCT_FOUNDATION.md) – Product brief for all roles
- [ADR Index](docs/adr/README.md) – Architecture decisions
- [Governance](docs/governance/) – Process docs

### Quick References
- [LOCAL_TESTING_QUICKREF.md](docs/quick-refs/LOCAL_TESTING_QUICKREF.md)
- [DEVELOPMENT_SETUP_QUICKREF.md](docs/quick-refs/DEVELOPMENT_SETUP_QUICKREF.md)
- [AI_GOVERNANCE_QUICKREF.md](docs/quick-refs/AI_GOVERNANCE_QUICKREF.md)

---

## 🚀 8-Phase Workflow (MANDATORY)

All work follows this strict sequence:

1. **Phase 1 (PREP):** Get task from Task-CLI
2. **Phase 2 (CONTEXT & DESIGN):** Read ADRs, design doc, get approval
3. **Phase 3 (IMPLEMENT):** Code development
4. **Phase 4 (TEST):** Unit/integration tests (≥75% coverage)
5. **Phase 5 (VALIDATE):** Security/performance checks
6. **Phase 6 (REVIEW):** Code review + quality gates
7. **Phase 7 (RELEASE READY):** Deployment plan
8. **Phase 8 (COMPLETE):** Update docs, ADRs, close task

**Reference:** [7-PHASE-WORKFLOW.md](docs/governance/7-PHASE-WORKFLOW.md)

---

## 🔴 Critical Rules

- ❌ **Without ADR:** No significant architecture decisions
- ❌ **Skip design review:** AYEHEAR_ARCHITECT must approve before Phase 3
- ❌ **Code without tests:** ≥75% coverage MANDATORY
- ❌ **Skip quality gates:** Must pass before PR
- ❌ **No offline-promise:** All processing stays local (no cloud calls)
- ❌ **Bypass speaker identification:** Confidence scoring and manual override always present

---

## 👥 Roles & Responsibilities

| Role | Purpose |
|------|---------|
| AYEHEAR_ARCHITECT | Architecture decisions, ADRs, design review, sign-off |
| AYEHEAR_DEVELOPER | Feature implementation, testing, code quality |
| AYEHEAR_DEVOPS | Deployment, Windows installer, CI/CD, build pipeline |
| AYEHEAR_QA | Test strategy, acceptance criteria, quality gates |
| AYEHEAR_SECURITY | Audio privacy, storage encryption, credential handling |

---

## 🔗 Multi-Repo Workspace

When working in multi-repo workspace:

**Platform Tools (cross-cutting):**
- ADRs: `../platform-tools/docs/adr/` (read-only)
- Quick-Refs: `../platform-tools/docs/quick-refs/` (read-only)
- Task-CLI: `../platform-tools/tools/task-cli/` (read-only)

**AYE KNOW (offline-appliance patterns):**
- Architecture: `../aye-know/docs/architecture/` (reference for V1 design patterns)

All primary AYE Hear work happens locally in `AYE-Hear/` repository.

---

## Platform Service Awareness (MANDATORY)

- Read `../platform-tools/docs/quick-refs/PLATFORM_SERVICE_CATALOG.md` in Phase 2 before implementing cross-cutting features.
- Decide explicitly per feature: `reuse`, `defer`, or `local`.
- Document the decision in ADR, design doc, or task implementation notes.
- Do not reimplement existing platform service capabilities without documented rationale.

## Memory Routing

- User memory only for durable user preferences, global working rules, and repeatedly useful personal learnings.
- Session memory only for active work context, intermediate findings, and decisions likely to be reused in the current conversation.
- Repo memory only for verified repository conventions, stable commands, runbook facts, and confirmed gotchas with reuse value.

## Memory Guardrails

- Do not store anything that is one-off, temporary, or unverified.
- Check existing memory notes before creating a new one; update instead of duplicating when possible.
- Create or extend repo memory only when the fact is verified by documentation, tooling, tests, or repeated practice.

Before task closure, checkpoint reusable in-session context such as the current local hypothesis, failing validation result, or next step when it is likely to matter later in the same conversation. If the context will not be reused in-session, store nothing.

At task closure, briefly check whether a verified learning belongs in user, session, or repo memory. If there is no clear reuse value, store nothing.

Use `../platform-tools/docs/quick-refs/SESSION_MEMORY_HARVEST_PATTERNS.md` for canonical session-memory harvest patterns.

---

## 📚 Getting Started

### For Architects
1. Read [PRODUCT_FOUNDATION.md](docs/PRODUCT_FOUNDATION.md)
2. Review [ADR Index](docs/adr/README.md)
3. Understand Windows Desktop App architecture (ADR-0002)
4. Approve designs before Phase 3 implementation

### For Developers
1. Setup: [DEVELOPMENT_SETUP_QUICKREF.md](docs/quick-refs/DEVELOPMENT_SETUP_QUICKREF.md)
2. Clone AYE-Hear, install Python 3.11+
3. Install dependencies: `pip install -r requirements.txt`
4. Run local dev: `python -m ayehear.app`
5. Follow 8-Phase Workflow for all tasks

### For QA & Security
1. Review [QUALITY_GATES.md](docs/governance/QUALITY_GATES.md)
2. Understand speaker identification requirements (ADR-0003)
3. Audio privacy & local storage requirements
4. Test checklist for each PR

---

## 🤖 Task-CLI (Non-Interactive Agent Mode)

```powershell
# Load Task-CLI
Import-Module G:\Repo\platform-tools\tools\task-cli\task-cli.psd1 -Force

# Get open tasks
Get-Task -Role AYEHEAR_DEVELOPER -Status OPEN

# Start a task
Start-Task -Id HEAR-001 -Force

# Set description/notes
Set-Task -Id HEAR-001 -Description "..." -Force

# Complete task
Complete-Task -Id HEAR-001
```

**Note:** Use `-Force` flag for non-interactive (agent) mode.

---

## 🔐 Privacy & Governance

**Offline-First Pledge:**
- No audio transmission externally
- No telemetry by default
- Local PostgreSQL storage only
- GDPR-compliant (users own data)

**AI Governance:**
- Prompt change logs required (ADR-0005)
- Model version locked per release
- Speaker identification confidence tracked
- Fallback to manual review always available

---

**Maintained by:** AYEHEAR Team  
**Updated:** 2026-05-16

---

## Bootstrap Enforcement (MANDATORY)

### AYEHEAR_ARCHITECT — MEDIUM gate

**🚨 MANDATORY FIRST ACTION — BLOCKING REQUIREMENT**

Du MUSST diese Dateien laden, BEVOR du auf einen Task reagierst:
- `docs/PRODUCT_FOUNDATION.md`
- `docs/adr/README.md`
- `../platform-tools/docs/personas/_FOUNDATION_DOCS.md`

**Dann:** `Get-Task -Role AYEHEAR_ARCHITECT -Status OPEN`

**Gate-Stärke:** MEDIUM
**Bei fehlendem Checkpoint:** Warnung — Architect-Entscheidungen ohne Foundation-Kontext sind ungültig.

---

### AYEHEAR_DEVELOPER — SOFT gate

**🚨 MANDATORY FIRST ACTION — BLOCKING REQUIREMENT**

Du MUSST diese Dateien laden, BEVOR du auf einen Task reagierst:
- `docs/PRODUCT_FOUNDATION.md`
- `../platform-tools/docs/personas/_FOUNDATION_DOCS.md`

**Dann:** `Get-Task -Role AYEHEAR_DEVELOPER -Status OPEN`

**Gate-Stärke:** SOFT
**Bei fehlendem Checkpoint:** Flag in CI — fehlende Kontext-Dokumentation wird als Review-Finding markiert.

---

### AYEHEAR_SECURITY — HARD gate

**🚨 MANDATORY FIRST ACTION — BLOCKING REQUIREMENT**

Du MUSST diese Dateien laden, BEVOR du auf einen Task reagierst:
- `docs/PRODUCT_FOUNDATION.md`
- `docs/adr/README.md`

**Dann:** `Get-Task -Role AYEHEAR_SECURITY -Status OPEN`

**Gate-Stärke:** HARD
**Bei fehlendem Checkpoint:** Task blockiert — Security-Reviews ohne ADR- und Foundation-Kontext sind unzulässig.

---

### AYEHEAR_QA — SOFT gate

**🚨 MANDATORY FIRST ACTION — BLOCKING REQUIREMENT**

Du MUSST diese Dateien laden, BEVOR du auf einen Task reagierst:
- `docs/PRODUCT_FOUNDATION.md`
- `../platform-tools/docs/personas/_FOUNDATION_DOCS.md`

**Dann:** `Get-Task -Role AYEHEAR_QA -Status OPEN`

**Gate-Stärke:** SOFT
**Bei fehlendem Checkpoint:** Flag in CI — QA-Artefakte ohne Foundation-Kontext werden als unvollständig markiert.

---

### AYEHEAR_DEVOPS — MEDIUM gate

**🚨 MANDATORY FIRST ACTION — BLOCKING REQUIREMENT**

Du MUSST diese Dateien laden, BEVOR du auf einen Task reagierst:
- `docs/PRODUCT_FOUNDATION.md`
- `../platform-tools/docs/personas/_FOUNDATION_DOCS.md`

**Dann:** `Get-Task -Role AYEHEAR_DEVOPS -Status OPEN`

**Gate-Stärke:** MEDIUM
**Bei fehlendem Checkpoint:** Warnung — Deployment-Entscheidungen ohne Foundation-Kontext erfordern manuelle Review-Freigabe.
