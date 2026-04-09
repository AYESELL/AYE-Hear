---
owner: AYEHEAR_QA
status: active
updated: 2026-04-09
---

# Local Testing Quick Reference – AYE Hear

## Reference

- Full acceptance criteria matrix: `docs/governance/HEAR_QA_ACCEPTANCE_MATRIX.md`

## Local Test Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Focused Regression Suite (HEAR-023)

Run this suite before sign-off on participant mapping, intro matching, correction audit and storage-contract changes:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_participant_metadata.py tests/test_name_correction_audit.py tests/test_storage.py tests/test_speaker_manager.py tests/test_database.py -q
```

Expected scope:

- participant salutation/full-name templates are covered by regression tests
- constrained intro matching is covered for known, ambiguous and company-formatted names
- corrected speaker-name persistence and audit history are covered
- acceptance-significant persistence tests validate PostgreSQL contract behavior only

Do not add SQLite DSNs, sqlite3-backed fixtures or alternate-backend acceptance paths. Storage contract tests must target the PostgreSQL schema/runtime contract directly or use storage-independent doubles when PostgreSQL is not the subject under test.

## Speaker Identification Tests

**Test 1: Enrollment Quality**

- Start app, create meeting
- 2 participants enroll (5-10 sec each)
- ✅ Both ≥ 0.75 confidence → Pass

**Test 2: Live Matching**

- Alice speaks → "Alice (high confidence)"
- Bob speaks → "Bob (high confidence)"
- ✅ Correct labels → Pass

**Test 3: Unknown Handling**

- New (non-enrolled) speaker talks
- ✅ Marked "Unknown" or "Uncertain" → Pass

## Protocol Generation Tests

**Test 1: Decision Capture**

- Speak decision phrase
- ✅ Decision in protocol ≤60 sec → Pass

**Test 2: Task Capture**

- Speak action phrase
- ✅ Task with owner + deadline → Pass

## Export Tests

- ✅ Markdown: Created and readable
- ✅ DOCX: Opens in Word
- ✅ PDF: Opens in reader

## Offline Runtime Validation (HEAR-025)

1. Disconnect the machine from external network access or disable the active adapter.
2. Start the app and execute the core meeting flow: create meeting, enroll participant, record short transcript, generate protocol.
3. Verify the workflow still completes because all dependencies are local-only.
4. Capture evidence that only loopback traffic is used for local services, for example with `netstat -ano` or Resource Monitor.
5. Validate the PostgreSQL runtime remains loopback-only by checking `SHOW listen_addresses` and confirming only `localhost`, `127.x.x.x` or `::1` are present.

Pass criteria:

- no outbound network dependency is required for core meeting flow
- no public or LAN destination is contacted during the run
- local PostgreSQL remains loopback-only per ADR-0006

## Encryption / Data Protection Validation (HEAR-025)

1. Identify the volume containing PostgreSQL data and local AYE Hear state.
2. Run `manage-bde -status` and capture evidence that BitLocker or an approved equivalent protects that volume.
3. Verify sensitive data classes from ADR-0009 are covered by that protected volume: transcript content, participant identity, protocol snapshots and speaker embeddings.
4. Confirm repository-tracked config and examples do not contain live DSNs, passwords or static encryption material.

Pass criteria:

- OS-managed volume encryption is enabled for the relevant data volume
- sensitive meeting data resides only on the protected local machine
- no source-controlled credentials or shared static secret material are present

---

**Owner:** AYEHEAR_QA
