---
owner: AYEHEAR_QA
status: complete
updated: 2026-04-19
category: qa-evidence
---

# HEAR-123 QA Evidence - Installed-Package E2E Validation for Quality-First Candidate 0.5.4

## Scope
Installed-runtime E2E validation for the newly versioned quality-first candidate `0.5.4` (task HEAR-123), covering:
- setup and installed runtime bootstrap,
- enrollment/speaker attribution behavior,
- transcription and protocol drafting,
- export generation,
- runtime persistence boundaries (review and traceability stores),
- explicit GO/NO-GO recommendation for architect reconciliation.

Reference build evidence:
- [docs/HEAR-122-build-evidence.md](docs/HEAR-122-build-evidence.md)

## Candidate and Environment
- Candidate version (installed): `0.5.4`
- Installed root observed: `D:\AYE\AyeHear`
- Installed binary hash: matches HEAR-122 artifact hash
- Installer hash: matches HEAR-122 artifact hash

Evidence:
- [deployment-evidence/hear-123/2026-04-19-hear-123/01-install-root-app-tree.txt](deployment-evidence/hear-123/2026-04-19-hear-123/01-install-root-app-tree.txt)
- [deployment-evidence/hear-123/2026-04-19-hear-123/02-installed-version.txt](deployment-evidence/hear-123/2026-04-19-hear-123/02-installed-version.txt)
- [deployment-evidence/hear-123/2026-04-19-hear-123/09-ayehear-exe-sha256.txt](deployment-evidence/hear-123/2026-04-19-hear-123/09-ayehear-exe-sha256.txt)
- [deployment-evidence/hear-123/2026-04-19-hear-123/10-installer-sha256.txt](deployment-evidence/hear-123/2026-04-19-hear-123/10-installer-sha256.txt)

## Installed Runtime Findings

### Positive Evidence
1. Export pipeline generated protocol and transcript artifacts from installed runtime (`.md`, `.docx`, `.pdf`, transcript text).
2. Runtime persisted review and traceability files under runtime boundaries.
3. Loopback-only service posture observed for DB (`127.0.0.1:5433`) and local model host (`127.0.0.1:11434`).
4. Transcript evidence shows unresolved speaker attribution is surfaced (`Unknown Speaker [low-conf]`), consistent with review-first behavior.

Evidence:
- [deployment-evidence/hear-123/2026-04-19-hear-123/03-export-list.txt](deployment-evidence/hear-123/2026-04-19-hear-123/03-export-list.txt)
- [deployment-evidence/hear-123/2026-04-19-hear-123/06-netstat-local-services.txt](deployment-evidence/hear-123/2026-04-19-hear-123/06-netstat-local-services.txt)
- [deployment-evidence/hear-123/2026-04-19-hear-123/07-trace-store.json](deployment-evidence/hear-123/2026-04-19-hear-123/07-trace-store.json)
- [deployment-evidence/hear-123/2026-04-19-hear-123/08-review-store.json](deployment-evidence/hear-123/2026-04-19-hear-123/08-review-store.json)

### Critical Defects Observed in Installed Run
1. Transcript persistence repeatedly fails with foreign key violations:
   - `transcript_segments_meeting_id_fkey`
   - meeting ID not found in `meetings`
2. Protocol rebuild repeatedly fails during the same run due to rolled-back transaction state.
3. Meeting finalization fails: `Failed to end meeting in DB: Meeting '...' not found.`
4. Persisted review/trace stores are empty (`0 items`, `0 links`) for the problematic run.

Evidence:
- [deployment-evidence/hear-123/2026-04-19-hear-123/04-runtime-log-tail.txt](deployment-evidence/hear-123/2026-04-19-hear-123/04-runtime-log-tail.txt)
- [deployment-evidence/hear-123/2026-04-19-hear-123/05-runtime-log-current-run.txt](deployment-evidence/hear-123/2026-04-19-hear-123/05-runtime-log-current-run.txt)
- [deployment-evidence/hear-123/2026-04-19-hear-123/07-trace-store.json](deployment-evidence/hear-123/2026-04-19-hear-123/07-trace-store.json)
- [deployment-evidence/hear-123/2026-04-19-hear-123/08-review-store.json](deployment-evidence/hear-123/2026-04-19-hear-123/08-review-store.json)

### Additional Tooling Defect Found During Validation
`tools/scripts/Start-AyeHearRuntime.ps1` fails at runtime due to an invalid inline `if` expression usage in `Write-Host` string construction, so the health-check script is currently unreliable as an operational validator.

## Acceptance Mapping (HEAR-123)

1. Setup in installed runtime
- Status: PASS
- Evidence: installed app tree + version + hash confirmation.

2. Enrollment and speaker attribution behavior
- Status: PARTIAL
- Evidence exists for meeting-scoped profile matching and low-confidence speaker surfacing, but persistence failure undermines data integrity for the run.

3. Transcription and protocol drafting in installed runtime
- Status: PARTIAL
- Export artifacts exist, but runtime logs show repeated persistence and protocol rebuild errors.

4. Export in installed runtime
- Status: PASS
- Multi-format exports generated for the installed run.

5. Runtime bootstrap/persistence including traceability/review behavior
- Status: FAIL
- DB persistence is unstable in installed run (`meeting_id` FK violations, failed meeting close); trace/review outputs saved as empty.

6. Evidence bundle under deployment-evidence and QA report update
- Status: PASS
- Evidence bundle and this QA report created.

## Quality Gate Decision (HEAR-123)
- Installed-package candidate `0.5.4`: NO-GO

Reason:
- V1-critical installed E2E gate requires stable runtime persistence across setup/transcription/protocol/export/bootstrap flow.
- The captured installed run has repeated DB FK violations and meeting-close failure, producing incomplete/unstable traceability context.

## Required Follow-Ups Before GO Re-evaluation
1. Fix installed-runtime meeting lifecycle/persistence path causing `meeting_id` FK violations.
2. Re-run installed E2E on the same packaged candidate lineage with fresh evidence bundle and no critical runtime persistence errors.
3. Repair `Start-AyeHearRuntime.ps1` health-check script so preflight runtime validation is dependable.

## QA Recommendation for Architect Reconciliation
- Recommend NO-GO for release progression of candidate `0.5.4` until the persistence defects above are resolved and revalidated with a fresh installed evidence bundle.