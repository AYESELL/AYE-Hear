# HEAR-158: Protocol Draft Panel Shows Empty Instead of [DEGRADED]

**Status:** BLOCKED (blocker für v0.6.8 release)  
**Date Identified:** 2026-05-03  
**Severity:** CRITICAL  
**Component:** Protocol Engine, MainWindow UI  

---

## Problem Statement

During v0.6.7 test run (2026-05-03), user reported:
- **Live Transcript:** Working ✅ (shows recognized text)
- **System Readiness:** All green ✅
- **Protocol Draft Panel:** **EMPTY** ❌ (no content, no error label)

### Root-Cause Analysis

Found in `src/ayehear/app/window.py` line 1343-1344:

```python
def _refresh_protocol_display(self) -> None:
    # ... AC3 degraded-label handling ...
    if self._snapshot_repo is None or self._active_meeting_id is None:
        # Shows [DEGRADED] ✅
        self._protocol_view.setPlainText(f"{_PROTOCOL_DEGRADED_PREFIX} ...")
        return
    
    try:
        snapshot = self._snapshot_repo.latest(self._active_meeting_id)
        if snapshot is None:
            return  # ← BUG: Returns silently without updating UI!
                    # Protocol panel remains EMPTY
```

**When snapshot_repo.latest() returns None:**
- This happens when protocol generation failed (Ollama unavailable, LLM errors, etc.)
- The panel is not updated → remains in prior state (often empty)
- No [DEGRADED] label shown → user has no visibility into the failure

### Supporting Evidence

**Test failures in v0.6.6+:**
```
FAILED tests/test_hear_085_protocol_draft.py::TestAC1ProtocolSeparateFromTranscript::test_transcript_text_never_appears_in_protocol_after_meeting_start_degraded
FAILED tests/test_hear_085_protocol_draft.py::TestAC3DegradedLabel::test_update_protocol_live_without_db_sets_degraded_not_transcript
FAILED tests/test_hear_085_protocol_draft.py::TestAC5UpdateProtocolLiveNeverMirrorsTranscript::test_update_protocol_live_without_db_multiple_lines_no_stacking
```

Related test (`test_hear_085_protocol_draft.py:216`):
```python
def test_update_protocol_live_without_db_sets_degraded_not_transcript(self, qapp):
    """_update_protocol_live without snapshot_repo must show [DEGRADED], not transcript text."""
    win = _make_window(qapp, snapshot_repo=None)
    win._active_meeting_id = "fake-id"
    win._update_protocol_live("Some important sentence from speaker")
    text = win._protocol_view.toPlainText()
    assert text.startswith("[DEGRADED]")  # ← FAILS in v0.6.7
    assert "Some important sentence" not in text
```

---

## Fix Strategy

**Change in `_refresh_protocol_display()` Zeile 1343-1344:**

```python
snapshot = self._snapshot_repo.latest(self._active_meeting_id)
if snapshot is None:
    # NEW: Show [DEGRADED] when protocol was not yet generated
    self._protocol_view.setPlainText(
        f"{_PROTOCOL_DEGRADED_PREFIX} Protokoll-Snapshot noch nicht verfügbar.\n\n"
        "Generierung läuft ... oder es ist ein Fehler aufgetreten.\n"
        "Bitte warten oder prüfen Sie das System-Readiness-Panel."
    )
    return
```

**Acceptance Criteria:**
- [ ] AC1: When snapshot is None, Protocol Draft shows "[DEGRADED]..." label (not empty)
- [ ] AC2: Test `test_update_protocol_live_without_db_sets_degraded_not_transcript` passes
- [ ] AC3: Test `test_transcript_text_never_appears_in_protocol_after_meeting_start_degraded` passes
- [ ] AC4: User sees clear feedback when protocol generation is pending

---

## Phase 3 Blocking?

**YES** — This is a Release Blocker.

- User cannot distinguish "protocol not yet generated" from "protocol generation failed"
- Panel state is confusing and violates AC3/AC5 contract
- Undermines trust in the app's status visibility

**Recommendation:** Fix before packaging v0.6.8 candidate.

---

## Related Issues

- HEAR-155: Post-0.5.3 readiness reconciliation (0.6.x lineage)
- HEAR-085: ADR-0005 Protocol Draft Instead of Transcript Mirror (feature spec)
- Tests: `tests/test_hear_085_protocol_draft.py` (multiple failures)
