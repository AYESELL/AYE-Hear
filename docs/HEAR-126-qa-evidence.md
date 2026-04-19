---
owner: AYEHEAR_QA
status: complete
updated: 2026-04-19
category: qa-evidence
---

# HEAR-126 QA Evidence - Installed-Package E2E Re-Run for Candidate 0.5.5

## Scope
Installed-runtime E2E re-validation for candidate `0.5.5` after HEAR-124 and HEAR-125 fixes, covering:
- setup and installed runtime bootstrap,
- enrollment and speaker attribution,
- transcription and protocol drafting,
- export generation,
- runtime persistence boundaries (review and traceability stores),
- explicit GO/NO-GO decision.

Reference build evidence:
- [docs/HEAR-129-build-evidence.md](docs/HEAR-129-build-evidence.md)

## Candidate and Environment
- Candidate version (installed): `0.5.5`
- Installed root observed: `D:\AYE\AyeHear`
- Installed binary hash: `4EB22618CA6868CE526D7F279036CAAF1E60799BD5F4CB200C22930C67C0DE8F`
- Installer hash: `4EF5311DE8C9EFC77CF6EFBBA3527AB16D2077D990D192FA9EC9BCDD2ED08D6D`

Evidence:
- [deployment-evidence/hear-126/2026-04-19-hear-126/01-install-root-tree.txt](deployment-evidence/hear-126/2026-04-19-hear-126/01-install-root-tree.txt)
- [deployment-evidence/hear-126/2026-04-19-hear-126/02-installed-version.txt](deployment-evidence/hear-126/2026-04-19-hear-126/02-installed-version.txt)
- [deployment-evidence/hear-126/2026-04-19-hear-126/09-ayehear-exe-sha256.txt](deployment-evidence/hear-126/2026-04-19-hear-126/09-ayehear-exe-sha256.txt)
- [deployment-evidence/hear-126/2026-04-19-hear-126/10-installer-sha256.txt](deployment-evidence/hear-126/2026-04-19-hear-126/10-installer-sha256.txt)

## Installed Runtime Findings

### Positive Evidence
1. Installed runtime exports are present across expected formats (`.md`, `.docx`, `.pdf`, transcript text).
2. Runtime bootstrap and DB migration checks are visible and complete in logs.
3. Loopback-only DB posture is present for PostgreSQL (`127.0.0.1`/`::1` on port `5433`).

Evidence:
- [deployment-evidence/hear-126/2026-04-19-hear-126/03-export-list.txt](deployment-evidence/hear-126/2026-04-19-hear-126/03-export-list.txt)
- [deployment-evidence/hear-126/2026-04-19-hear-126/04-runtime-log-tail.txt](deployment-evidence/hear-126/2026-04-19-hear-126/04-runtime-log-tail.txt)
- [deployment-evidence/hear-126/2026-04-19-hear-126/06-netstat-local-services.txt](deployment-evidence/hear-126/2026-04-19-hear-126/06-netstat-local-services.txt)

### Critical Defects Observed in Installed Run
1. Transcript persistence still fails with foreign key violations:
   - `transcript_segments_meeting_id_fkey`
   - meeting ID not found in `meetings`
2. Protocol rebuild repeatedly fails in the same run after transaction rollback.
3. Meeting close still fails: `Failed to end meeting in DB: Meeting '...' not found.`
4. Persisted review and traceability stores remain empty (`0 items`, `0 links`) for the captured run.

Evidence:
- [deployment-evidence/hear-126/2026-04-19-hear-126/04-runtime-log-tail.txt](deployment-evidence/hear-126/2026-04-19-hear-126/04-runtime-log-tail.txt)
- [deployment-evidence/hear-126/2026-04-19-hear-126/05-runtime-error-signatures.txt](deployment-evidence/hear-126/2026-04-19-hear-126/05-runtime-error-signatures.txt)
- [deployment-evidence/hear-126/2026-04-19-hear-126/07-trace-store.json](deployment-evidence/hear-126/2026-04-19-hear-126/07-trace-store.json)
- [deployment-evidence/hear-126/2026-04-19-hear-126/08-review-store.json](deployment-evidence/hear-126/2026-04-19-hear-126/08-review-store.json)

## Acceptance Mapping (HEAR-126)

1. Setup in installed runtime
- Status: PASS
- Evidence: installed root structure, version stamp `0.5.5`, successful bootstrap logs.

2. Enrollment, transcription, attribution, protocol drafting, export in installed runtime
- Status: PARTIAL
- Evidence: runtime flow executes and exports exist, but persistence errors break end-to-end data integrity.

3. No FK persistence errors
- Status: FAIL
- Evidence: repeated `transcript_segments_meeting_id_fkey` violations in installed runtime logs.

4. No failed meeting close
- Status: FAIL
- Evidence: explicit `Failed to end meeting in DB: Meeting '...' not found.` in installed runtime logs.

5. Protocol rebuild stable
- Status: FAIL
- Evidence: repeated `Protocol rebuild failed` after rolled-back transaction state.

6. Trace/review stores non-empty when applicable
- Status: FAIL
- Evidence: saved stores show `0 items` and `0 links`.

7. Evidence bundle + QA report updated
- Status: PASS
- Evidence: this report plus evidence folder under `deployment-evidence/hear-126/2026-04-19-hear-126/`.

## Quality Gate Decision (HEAR-126)
- Installed-package candidate `0.5.5`: NO-GO

Reason:
- The HEAR-126 acceptance criteria explicitly require no FK persistence errors and no failed meeting close.
- Both failure classes are still reproducible in the installed-runtime run and directly impact protocol rebuild stability and persistence integrity.

## Required Follow-Ups Before GO Re-Evaluation
1. Fix installed-runtime meeting lifecycle/persistence behavior causing `meeting_id` FK violations during segment persistence.
2. Ensure meeting end operation consistently resolves persisted meeting IDs in DB (`end meeting` path).
3. Re-run installed E2E on an updated candidate with fresh evidence showing:
   - zero FK persistence errors,
   - zero meeting-close failures,
   - stable protocol rebuild,
   - non-empty trace/review outputs when transcript/protocol content is present.

## QA Recommendation for Architect Reconciliation
- Recommend NO-GO for release progression after HEAR-126. The persistence defect remains active in candidate `0.5.5` and must be fixed before another release-readiness reconciliation.