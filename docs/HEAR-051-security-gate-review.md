---
owner: AYEHEAR_SECURITY
task: HEAR-051
status: complete
date: 2026-04-16
category: security-review
residual-risk-status: CLOSED (see HEAR-056)
---

# HEAR-051: Security Gate Review - Secret Provisioning and Deployment Preflight

## Scope

Final security validation for Operations handoff after Phase-1B release readiness updates.

Reviewed items:
- Installer-managed DSN and secret provisioning path
- Repository leakage risk for credentials or static secret material
- BitLocker or approved equivalent evidence status
- Runtime boundary enforcement (PostgreSQL loopback, local LLM loopback)

Reference ADRs:
- ADR-0006 (installer-managed local PostgreSQL and loopback-only runtime)
- ADR-0009 (data protection and secret handling)

---

## Executive Decision

**APPROVED WITH RISKS**

The implementation satisfies all code and packaging security controls for DSN provisioning, local-only runtime boundaries, and secret handling in source-controlled artifacts.

One operational residual risk remains open for GA handoff:
- Target-machine BitLocker evidence is not attached in the repository at review time.

No blocking code-level finding remains.

---

## Security Preflight Checklist

| Check | Result | Evidence |
|---|---|---|
| Installer-managed DSN provisioning is implemented | PASS | Install script generates per-install password and writes DSN to runtime path with restricted ACL |
| No source-controlled live credentials or static shared secrets | PASS | Config and source review plus focused secret-pattern scan |
| BitLocker preflight evidence exists for target deployment machine | PARTIAL | Script and procedure exist; deployment evidence artifact not present in repo |
| PostgreSQL runtime remains loopback-only | PASS | Installer enforces localhost listen address; runtime bootstrap and startup checks fail closed |
| Local LLM path remains loopback-only | PASS | Protocol engine rejects non-loopback Ollama URLs at construction |

---

## Findings by Requirement

### 1) Installer-managed DSN and secret provisioning path

Status: PASS

Verified controls:
- Random per-install DB credential is generated in installer provisioning script.
- DSN is materialized to C:\AyeHear\runtime\pg.dsn (not app bundle path).
- DSN file ACL is restricted to SYSTEM and Administrators.
- Installer executes provisioning and startup health-check scripts automatically.

Evidence:
- tools/scripts/Install-PostgresRuntime.ps1
- tools/scripts/Start-AyeHearRuntime.ps1
- build/installer/ayehear-installer.iss
- build/installer/ayehear-installer.nsi
- tests/test_hear_049_installer_postgres.py

Assessment:
- Meets ADR-0006 and ADR-0009 requirements for installer authority, per-install secrets, and protected local handoff.

### 2) No source-controlled credentials or static secret material

Status: PASS

Scope reviewed:
- config/default.yaml
- docs and tooling artifacts relevant to release path
- source and test files (excluding local virtual environment and generated build artifacts)

Observed matches from focused scan:
- Test-only DSN placeholders in tests/test_hear_049_installer_postgres.py
- Runtime DSN construction line in installer provisioning script (expected behavior)

No live credential, API key, static token, or committed DSN file was found.

Assessment:
- Repository state is aligned with "no source-controlled secrets" policy.

### 3) BitLocker or approved equivalent evidence

Status: PARTIAL (operational residual risk)

Verified:
- Evidence capture script exists and produces timestamped artifacts.
- Runbooks define QA-DP-01 as mandatory pre-GA control.
- QA governance notes formal waiver context for Phase-1B and explicit requirement before GA.

Not available at review time:
- No deployment-evidence directory or bitlocker-evidence artifact present in the repository snapshot.

Evidence:
- tools/scripts/Invoke-BitLockerPreFlight.ps1
- docs/governance/HEAR_SECURITY_RUNBOOK.md
- docs/quick-refs/WINDOWS_PACKAGING_RUNBOOK.md
- docs/governance/HEAR_QA_ACCEPTANCE_MATRIX.md

Assessment:
- Control design is in place.
- Operational proof from target machine is pending and must be attached before GA handoff completion.

### 4) Runtime remains loopback-only for PostgreSQL and local LLM path

Status: PASS

PostgreSQL boundary:
- Installer sets listen_addresses to localhost.
- Runtime startup check validates listen_addresses as loopback-safe only.
- Application bootstrap enforces loopback-only check and fails closed on remote exposure.

Local LLM boundary:
- Protocol engine validates Ollama base URL host and rejects non-loopback endpoints.

Evidence:
- tools/scripts/Install-PostgresRuntime.ps1
- tools/scripts/Start-AyeHearRuntime.ps1
- src/ayehear/storage/database.py
- src/ayehear/services/protocol_engine.py
- tests/test_protocol_engine.py
- tests/test_qa_runtime_evidence.py
- tests/test_hear_049_installer_postgres.py

Assessment:
- Runtime network boundary controls are implemented and test-covered.

---

## Update (HEAR-056 · 2026-04-16)

HEAR-051-R1 is formally **CLOSED**. Evidence and waiver attached; see [HEAR-056-security-recheck.md](HEAR-056-security-recheck.md).

---

## Residual Risk Statement

Residual Risk ID: HEAR-051-R1

- Risk: Missing target-machine BitLocker evidence artifact at time of security gate review.
- Impact: GA handoff cannot claim complete encryption-at-rest evidence chain for deployment host.
- Severity: Low (procedural, not code-level).
- Mitigation required before GA final handoff:
  1. Run tools/scripts/Invoke-BitLockerPreFlight.ps1 on the target deployment machine.
  2. Attach generated bitlocker-evidence-YYYYMMDD-HHmmss.txt to release artifacts/ticket.
  3. If BitLocker unavailable, attach approved equivalent control and explicit AYEHEAR_SECURITY waiver.

---

## Validation Evidence

Security-relevant tests executed during this review:
- .\\.venv\\Scripts\\python.exe -m pytest tests/test_hear_049_installer_postgres.py tests/test_protocol_engine.py tests/test_qa_runtime_evidence.py -q
- Result: PASS (all tests in selected scope)

Focused secret-pattern scan executed (source-controlled scope with artifact exclusions):
- Result: only expected test placeholders and installer runtime DSN construction line; no live secrets found.

---

## Sign-off

Decision: APPROVED WITH RISKS

Security gate outcome for HEAR-051:
- Code and packaging security controls: approved
- Operational pre-GA evidence requirement: open (BitLocker artifact attachment)

Reviewer: AYEHEAR_SECURITY
Date: 2026-04-16
