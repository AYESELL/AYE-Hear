---
owner: AYEHEAR_DEVOPS
status: ready
category: follow-up-brief
updated: 2026-05-02
---

# Follow-up Brief: Candidate Rebuild and Installed-E2E Automation Support

## Goal
Provide a new versioned installer candidate containing the latest fixes and stable automation hooks for HEAR-155 installed E2E validation.

## Why
QA cannot close the installed evidence gate without a same-candidate package and reproducible runtime startup/health-check workflow.

## References
- docs/HEAR-135-readiness-reconciliation.md
- docs/HEAR-144-build-evidence.md
- docs/HEAR-151-build-evidence.md
- tools/scripts/Start-AyeHearRuntime.ps1

## Required Scope
- build pipeline scripts and installer packaging metadata
- runtime startup/check scripts used by QA evidence runs
- build evidence documentation for new candidate

## Acceptance Criteria
- New versioned installer is generated and hash-documented.
- Runtime start/check script works for installed layout without manual patching.
- QA can execute HEAR-155 evidence run with documented commands only.

## Verification
- build command exits 0 with evidence log
- installer checksum generated and archived
- startup/check smoke command exits 0 on installed candidate

## Evidence To Produce
- docs/HEAR-<new>-build-evidence.md
- build log path and installer checksum
- runtime smoke-check output referenced for QA handover
