---
owner: AYEHEAR_QA
status: draft
updated: 2026-04-19
category: qa-evidence
---

# HEAR-108 QA Evidence - Short-Term Quality Wave Validation

## Scope
Integrated QA validation for the short-term quality wave across:
- HEAR-105 deterministic action-item scoring
- HEAR-106 review queue ordering, actions, and persistence
- HEAR-107 traceability persistence across restart and revision changes
- Export correctness after review edits

## Inputs Reviewed
- Task batch contract: docs/governance/HEAR_V2_SHORTTERM_TASKBATCH.md
- Service implementations:
  - src/ayehear/services/action_item_quality.py
  - src/ayehear/services/confidence_review.py
  - src/ayehear/services/protocol_traceability.py
- Existing unit suites:
  - tests/test_hear_105_action_item_quality.py
  - tests/test_hear_106_confidence_review.py
  - tests/test_hear_107_protocol_traceability.py

## HEAR-108 Integrated Test Artifact
- Automated integrated test: tests/test_hear_108_quality_wave_validation.py

## Acceptance-Test to Evidence Mapping

1. Deterministic behavior checks
- Evidence: `test_hear_108_integrated_quality_wave` verifies same action-item input produces identical score and reason set.

2. Review queue ordering and persistence checks
- Evidence: `test_hear_108_integrated_quality_wave` verifies severity ordering and save/load roundtrip preserving edit actions.

3. Trace-link persistence checks (restart + revision)
- Evidence: `test_hear_108_integrated_quality_wave` verifies trace store save/load and unchanged item mapping consistency across `snap-108-v1` and `snap-108-v2`.

4. Export consistency after review corrections
- Evidence: `test_hear_108_integrated_quality_wave` verifies markdown rendering includes reviewed edited action item and expected sections.

## Execution Commands
Run the consolidated quality-wave suite:

```powershell
.venv\Scripts\python.exe -m pytest \
  tests/test_hear_105_action_item_quality.py \
  tests/test_hear_106_confidence_review.py \
  tests/test_hear_107_protocol_traceability.py \
  tests/test_hear_108_quality_wave_validation.py -v
```

## Current Result
- Command executed:
  - `.venv\\Scripts\\python.exe -m pytest tests/test_hear_105_action_item_quality.py tests/test_hear_106_confidence_review.py tests/test_hear_107_protocol_traceability.py tests/test_hear_108_quality_wave_validation.py -v`
- Outcome:
  - **95 passed in 3.58s**
  - No failures, no skips, no xfails in the integrated wave suite.
- Observation:
  - Integrated HEAR-108 scenario (`test_hear_108_integrated_quality_wave`) passed and confirms review-edit data reaches export-facing markdown content.

## Residual Risks
- Risk R1 (Medium): Integration test validates markdown content path, but does not execute full GUI button export flow (`_export_meeting_artifacts`) with review queue integration in a single end-to-end scenario.
- Risk R2 (Low): Revision-safety validation currently asserts stable content-level mapping and segment association, not immutable link IDs across snapshots (by design snapshot IDs differ).

## Recommendation
- If HEAR-109 security checks stay green and no regression appears in full-suite execution, HEAR-108 can be considered QA-complete with documented residual risks.
