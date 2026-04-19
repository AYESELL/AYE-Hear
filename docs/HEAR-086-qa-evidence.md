---
owner: AYEHEAR_QA
status: draft
updated: 2026-04-19
category: qa-evidence
---

# HEAR-086 QA Evidence - Packaged Non-Default Install E2E

## Scope
Validate packaged-runtime end-to-end behavior from a non-default install location and report explicit pass/fail for product-complete claims.

## Inputs Reviewed
- Installer script: build/installer/ayehear-installer.iss
- Governance gate: docs/governance/QUALITY_GATES.md
- Regression suite: tests/test_hear_083_install_root_handoff.py

## Executed Evidence
- Automated check: `pytest tests/test_hear_083_install_root_handoff.py -q` -> **16 passed**
- Static contract check:
  - `DefaultDirName=C:\AyeHear\app`
  - `GetInstallRoot` derives root via `ExtractFileDir(WizardDirValue)`

## Findings

### F1 - Install-root derivation edge risk for customized directory selection
- Severity: **High**
- Observation: Installer root derivation currently assumes app dir semantics by stripping one parent level from `WizardDirValue`.
- Impact: In custom install-directory scenarios, provisioning/runtime scripts can receive an incorrect root and fail non-default path E2E expectations.
- Status: **Open defect task created: HEAR-089**

## Acceptance Criteria Assessment

1. Clean packaged install to non-default drive/path executed
- Status: **FAIL / BLOCKED**
- Reason: Functional confidence blocked by F1 root-derivation risk; full product-complete claim cannot be made until HEAR-089 is fixed and revalidated.

2. Runtime bootstrap, enrollment, transcription, speaker attribution, protocol draft, export validated in installed app
- Status: **FAIL / NOT VERIFIED**
- Reason: Upstream install-root correctness not reliable for non-default path product run.

3. QA evidence includes installed-path logs, artifacts, screenshots, explicit pass/fail
- Status: **PARTIAL**
- Provided here: explicit pass/fail rationale + technical evidence.
- Missing for pass: fresh installed runtime logs/screenshots from non-default packaged run after HEAR-089 fix.

4. Degraded fallback path called out as fail for product-complete
- Status: **PASS**
- Decision: Product-complete **NO-GO** for HEAR-086 scope at current state.

## QA Gate Decision
- **Result:** NO-GO for product-complete sign-off in HEAR-086 scope
- **Required next step:** complete HEAR-089, then rerun packaged non-default install E2E and update this report with installed-runtime screenshots/log excerpts.

---

## HEAR-091 Post-Fix Revalidation (After HEAR-089 + HEAR-090)

### Revalidation Inputs
- Task evidence: HEAR-089 (installer root derivation fix), HEAR-090 (readiness semantics alignment)
- Architecture spec: docs/architecture/SYSTEM_READINESS_INDICATORS_SPEC.md
- Governance guardrail: docs/governance/QUALITY_GATES.md, docs/governance/DEFINITIONS_OF_DONE.md

### Revalidation Execution
- `pytest tests/test_hear_089_installer_root_derivation.py -q` -> **16 passed**
- `pytest tests/test_hear_083_install_root_handoff.py -q` -> **16 passed**

### Revalidation Findings

#### R1 - Installer root-derivation edge case is corrected in code and regression suite
- Severity: **Resolved (previously High)**
- Evidence: HEAR-089 implementation notes + passing root-derivation and handoff tests.
- Assessment: Static and automated evidence now supports correct normalization for `<root>\\app` and `<root>` patterns.

#### R2 - Packaged non-default install runtime evidence is still missing in this QA pass
- Severity: **High (evidence gap)**
- Evidence gap: No fresh installed-runtime screenshot bundle or runtime-log excerpt from a real packaged install run to a non-default path is attached in this revalidation pass.
- Assessment: Code/test-level confidence improved, but installed E2E acceptance proof remains incomplete.

### HEAR-091 Acceptance Criteria Mapping (HEAR-086 perspective)

1. Install latest packaged installer on non-default path + capture screenshots/log excerpts
- Status: **FAIL / NOT EXECUTED (evidence missing in this pass)**

2. Validate setup/enrollment/transcription/speaker attribution/protocol/export/runtime bootstrap in installed runtime
- Status: **FAIL / NOT VERIFIED**

3. Verify readiness semantics against architecture spec
- Status: **PARTIAL (validated by automated semantics tests, not by installed runtime evidence in this document)**

4. Update HEAR-086 and HEAR-088 evidence docs with post-fix results + explicit GO/NO-GO
- Status: **PASS (this update + linked HEAR-088 update)**

5. Apply HEAR-082 completion-language guardrail
- Status: **PASS (no product-complete wording used without full installed E2E evidence)**

### QA Gate Decision (HEAR-091 Revalidation)
- **Package commissioning:** **NO-GO**
- **Reason:** Post-fix automated evidence is green, but required installed non-default E2E run evidence (screenshots/log excerpts + full workflow validation) is not yet present.
- **Guardrail compliance:** Product-complete statement remains blocked until installed E2E evidence is fully green.

---

## Installed Run Evidence Update (2026-04-16, v0.4.1)

### Installed Runtime Evidence Received
- Installed path observed: `D:\AYE\AyeHear`
- Screenshot evidence confirms System Readiness panel is visible and reports aggregate **Product Path Blocked**.
- Runtime log evidence confirms repeated startup warning:
  - `No runtime DSN found (env or installer path). Starting in local-only mode without persistence.`
- Runtime log evidence also confirms partial functional activity in local-only mode:
  - enrollment recording + stub profile event
  - audio capture + transcription processing
  - export event to `D:\AYE\AyeHear\exports\...-protocol.md`

### Additional Local Verification
- `D:\AYE\AyeHear\runtime\pg.dsn` -> missing
- `D:\AYE\AyeHear\pgsql` -> missing
- `D:\AYE\AyeHear\runtime` exists but empty

### Interpretation
- Non-default installation evidence now exists (AC1 evidence materially improved).
- Core blocker remains runtime persistence bootstrap (no installer-provisioned DSN), therefore product path remains blocked.
- Local-only fallback behavior is visible and correctly flagged as blocked/degraded in readiness UI.

### Follow-up Task
- Critical developer blocker created: **HEAR-092**
- Title: Fix Packaged Runtime DSN Bootstrap in Installed Build

### Updated Decision
- **Package commissioning:** **NO-GO (confirmed with real installed run evidence)**
- **Reason:** Runtime DSN/bootstrap provisioning is not operational in packaged installed runtime.

---

## HEAR-111 Validation Candidate Re-Run (2026-04-19, v0.5.3)

### Executed on Installed Runtime
- Installer artifact rebuilt and used: `dist\AyeHear-Setup-0.5.3.exe`
- Installed runtime root observed and verified on disk: `D:\AYE\AyeHear`
- Installed executable launch: `D:\AYE\AyeHear\app\AyeHear.exe`
- Runtime files present:
  - `D:\AYE\AyeHear\runtime\pg.dsn`
  - `D:\AYE\AyeHear\logs\ayehear.log`
  - `D:\AYE\AyeHear\exports\...` (protocol/transcript artifacts)

### Runtime/Network Evidence
- Startup bootstrap in installed app (`frozen=True`) succeeded:
  - `PostgreSQL loopback-only check passed: listen_addresses='localhost'`
  - `Database bootstrap completed.`
  - `Persistence bootstrap completed; review queue and protocol snapshots enabled.`
- Network boundary observed at runtime process level:
  - App process has loopback DB connection only (`127.0.0.1 -> 127.0.0.1:5433`)

### Regression Focus from HEAR-111
- Prior installed-run error report: psycopg/sqlalchemy rollback failure during shutdown (`consuming input failed: server closed the connection unexpectedly`).
- Current re-run result: no new traceback with this signature observed in installed runtime logs during launch/stop validation after fix.

### AC Mapping (HEAR-111 run)
1. Non-default packaged install execution evidence
- Status: **PASS (installed runtime on D-drive observed and runnable)**

2. Full fresh installed E2E flow (setup/enrollment/transcription/attribution/protocol/export/bootstrap)
- Status: **PASS**
- Evidence: installed runtime logs show setup/enrollment/transcription/attribution/protocol/export/bootstrap activity on 2026-04-19, plus generated export artifacts in install-root exports.

3. Evidence bundle with screenshots + logs + artifact index
- Status: **PASS**
- Evidence bundle: `deployment-evidence/hear-091/2026-04-19-hear-111/` + updated index in `deployment-evidence/hear-091/README.md`.

4. Explicit authoritative GO/NO-GO wording
- Status: **PASS**

5. Guardrail (kein product-complete claim ohne final reconciliation)
- Status: **PASS**
- Evidence: HEAR-111 marked task-complete scope only; final product-complete governance remains in HEAR-112.

### QA Gate Decision (HEAR-111)
- **Result:** **GO (HEAR-111 task scope)**
- **Reason:** Non-default installed runtime evidence bundle is now complete with screenshots, logs, install-tree, network-boundary proof, and export artifact listing.
