---
owner: AYEHEAR_QA
status: draft
updated: 2026-04-19
category: qa-evidence
---

# HEAR-088 QA Evidence - Runtime Readiness Indicators and Test-Abort Semantics

## Scope
Validate runtime readiness indicators against the architecture spec and verify test-abort semantics before functional validation.

## Executed Checks
- Automated suite: `pytest tests/test_hear_087_system_readiness.py -q` -> **35 passed**
- Spec conformance inspection against:
  - docs/architecture/SYSTEM_READINESS_INDICATORS_SPEC.md
  - src/ayehear/app/system_readiness.py
  - tests/test_hear_087_system_readiness.py

## Key Evidence

### Spec requirements (selected)
- Audio Blocked when no usable capture path can be opened
- Enrollment Ready requires both speaker profile repository and participant repository
- Database Ready requires runtime DSN resolved and bootstrap succeeded

### Implemented behavior (selected)
- Audio without enumerable devices currently reported as **DEGRADED** (not Blocked)
- Enrollment currently reported **READY** when only participant repository is present
- Database currently reported **READY** when repo references are non-null, without explicit DSN/bootstrap health signal

## Acceptance Criteria Assessment

1. QA evidence covers green/amber/red states for required components
- Status: **PARTIAL**
- Reason: States are rendered and tested, but conformance mismatches exist versus spec semantics.

2. Missing DSN/runtime persistence shown as blocked
- Status: **PARTIAL / RISK**
- Reason: DB readiness logic does not explicitly validate DSN/bootstrap health.

3. Missing Ollama shown as degraded and disqualifies protocol-quality sign-off
- Status: **PASS**
- Reason: LLM path degrades on unreachable Ollama and is tested.

4. QA records whether testing continued or aborted based on aggregate status
- Status: **PASS**
- Decision: Product-complete testing should be **aborted** until semantics are aligned.

5. Evidence includes screenshots and matching runtime-log excerpts
- Status: **PARTIAL**
- Reason: Code/test evidence captured; installed runtime screenshot/log bundle pending after fixes.

## Findings

### F1 - Audio blocked/degraded mismatch to spec
- Severity: **High**
- Spec: audio should be Blocked when no usable capture path opens.
- Current: degraded fallback text.

### F2 - Enrollment ready criteria too weak
- Severity: **High**
- Spec: requires participant + speaker-profile persistence path.
- Current: participant repository alone marks ready.

### F3 - Database ready criteria too weak
- Severity: **Medium**
- Spec: DSN + bootstrap success semantics.
- Current: non-null repos imply ready.

## Corrective Action Link
- Developer correction task created: **HEAR-090** (align readiness semantics with spec)

## QA Gate Decision
- **Result:** NO-GO for product-complete readiness-indicator sign-off at current state
- **Continue/Abort rule:** Abort product-complete validation until HEAR-090 is implemented and revalidated in installed runtime.

---

## HEAR-091 Post-Fix Revalidation (After HEAR-090)

### Revalidation Execution
- `pytest tests/test_hear_087_system_readiness.py -q` -> **37 passed**
- Combined regression check: `pytest tests/test_hear_083_install_root_handoff.py tests/test_hear_087_system_readiness.py -q` -> **53 passed**

### Post-Fix Conformance Summary

1. Audio semantics: no usable capture path -> **Blocked**
- Status: **PASS**

2. Database readiness semantics: DSN/bootstrap-aware readiness, no false-green on repo references alone
- Status: **PASS** (automated semantics validation)

3. Enrollment persistence semantics: requires participant + speaker-profile persistence path
- Status: **PASS**

4. Aggregate and abort semantics: blocked/degraded signaling aligned with spec intent
- Status: **PASS**

### Remaining HEAR-091 Evidence Gap
- Installed-runtime screenshot/log bundle from a fresh packaged non-default install is not attached in this document yet.
- Therefore, readiness semantics are validated at code/test level, but not yet fully evidenced in packaged-runtime UX artifacts.

### HEAR-091 Acceptance Criteria Mapping (HEAR-088 perspective)

1. Green/amber/red evidence for required components
- Status: **PARTIAL** (automated coverage complete, installed screenshot artifacts pending)

2. Missing DSN/runtime persistence shown as blocked
- Status: **PASS** (semantics tests green)

3. Missing Ollama shown as degraded and disqualifies protocol-quality sign-off
- Status: **PASS**

4. Continue/abort decision recorded
- Status: **PASS** (abort product-complete claims until installed E2E bundle is complete)

5. Screenshots + matching runtime-log excerpts
- Status: **FAIL / PENDING ARTIFACT BUNDLE**

### QA Gate Decision (HEAR-091 Revalidation)
- **Readiness semantics implementation:** GO at automated test level
- **Package commissioning / product-complete evidence:** **NO-GO** until installed-runtime screenshot and log evidence is attached for the non-default packaged run.

---

## Installed Runtime Observation Update (2026-04-16, v0.4.1)

### Installed Evidence Correlation
- Screenshot from installed runtime shows aggregate **Product Path Blocked**.
- Displayed component states are consistent with provided runtime logs:
  - Database / Runtime Persistence -> Blocked
  - Transcript Persistence -> Blocked
  - Speaker Enrollment Persistence -> Blocked
  - Local LLM / Protocol Engine -> Degraded
  - Audio Input -> Ready
  - Export Target -> Ready

### Log-to-UI Consistency
- Startup log warning repeatedly states missing runtime DSN and local-only mode.
- This directly explains blocked persistence-related readiness components.
- Export and audio events are present in logs and match green indicators for audio/export.

### Updated Semantics Assessment
- Readiness semantics are not only test-green but also empirically confirmed in installed runtime behavior.
- Product path remains blocked for commissioning because persistence prerequisites are absent.

### Blocking Follow-up
- Developer blocker opened: **HEAR-092** (runtime DSN bootstrap in packaged install).

---

## HEAR-111 Readiness Revalidation Update (2026-04-19, v0.5.3)

### Installed Runtime Re-Observation
- Installed app started from `D:\AYE\AyeHear\app\AyeHear.exe`
- Installed log path confirmed: `D:\AYE\AyeHear\logs\ayehear.log`
- Installed runtime persistence assets confirmed present (`runtime\pg.dsn`)

### Readiness/Boundary Evidence from Installed Log
- `AYE Hear logging initialised ... frozen=True`
- `PostgreSQL loopback-only check passed: listen_addresses='localhost'`
- `Database bootstrap completed.`
- `Persistence bootstrap completed; review queue and protocol snapshots enabled.`

### Offline-First Boundary Check
- Runtime process connection observed as loopback-only DB session (`127.0.0.1` to `127.0.0.1:5433`).
- No evidence in this pass of remote DB endpoint usage.

### HEAR-111 Acceptance-Criteria Perspective (Readiness Doc)
1. Readiness semantics reflected in installed runtime evidence
- Status: **PASS (bootstrap + loopback checks confirmed in installed log)**

2. Persistence path no longer false-green due missing DSN/bootstrap
- Status: **PASS in this run**
- Evidence: installed runtime has DSN and successful bootstrap log entries.

3. Continue/abort decision documented
- Status: **PASS**

4. Screenshot + log correlation bundle complete
- Status: **PASS**
- Evidence: screenshot/log/artifact bundle completed under `deployment-evidence/hear-091/2026-04-19-hear-111/` and indexed in `deployment-evidence/hear-091/README.md`.

### QA Gate Decision (HEAR-111, Readiness Scope)
- **Readiness semantics / runtime bootstrap:** **GO**
- **Final installed E2E checklist closure:** **GO (HEAR-111 checklist closed)**
