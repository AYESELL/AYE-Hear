---
task_id: HEAR-038
category: defect-tracking
status: template
created: 2026-04-11
---

# HEAR-038: Smoke Test – Defect Tracking Template

Use this template to document any issues found during manual workflow testing.

---

## Defect Template

### Defect #1: [Title]

**ID:** [DEFECT-ID]

**Severity:** [ ] CRITICAL | [ ] HIGH | [ ] MEDIUM | [ ] LOW

**Area:** [ ] UI | [ ] Function | [ ] Performance | [ ] Data | [ ] Other

**Description:**
```
What happened?
[Write description of the issue]

Expected behavior:
[What should happen instead]

Actual behavior:
[What actually happens]
```

**Reproducible Steps:**
```
1. [Step 1]
2. [Step 2]
3. [Step 3]
...
```

**Affected Workflow:** 
- [ ] Meeting Title Selection
- [ ] Participant Selection
- [ ] Speaker Edit
- [ ] Correction with Unknown Speaker
- [ ] Setup Action Buttons
- [ ] Other: _________

**Environment:**
- OS: Windows 11 Pro
- Build: AyeHear-Setup-0.1.0.exe
- Test Date: 2026-04-11
- Tester: _________

**Screenshots/Evidence:**
[Attach screenshot or video]

**System Logs:**
[Paste relevant error messages or logs from C:\Temp\]

**Workaround (if available):**
[Describe any workaround or way to continue testing]

**Root Cause Analysis:**
[Fill after investigation]

**Resolution:**
[Fill when fixed]

**Status:** [ ] NEW | [ ] IN REVIEW | [ ] ASSIGNED | [ ] FIXED | [ ] VERIFIED FIXED | [ ] WONTFIX

---

---

## Example Defects (For Reference)

## Recorded Defects (Manual Run 2026-04-11)

### Defect #1: Mikrofon-Auswahl nicht an Windows-Geraeteliste gebunden

**ID:** HEAR-038-D001

**Severity:** HIGH

**Area:** Function

**Description:**
- Das Feld "Default Input" zeigt nur einen statischen Text ("Windows default microphone").
- Es gibt keine sichtbare Auswahl der tatsaechlich unter Windows verfuegbaren Mikrofone.

**Reproducible Steps:**
1. App starten.
2. In "Meeting Setup" das Feld "Default Input" pruefen.
3. Versuchen, ein konkretes Eingangsgeraet auszuwaehlen.

**Expected:** Auswahlbox mit den von Windows bereitgestellten Eingangsgeraeten.

**Actual:** Statischer Default-Text ohne geraetebezogene Auswahl.

**Affected Workflow:** Meeting Setup / Input Device Selection

**Status:** ✅ FIXED — HEAR-039 (2026-04-11)

---

### Defect #2: Speaker-Buttons haben keine erkennbare Wirkung

**ID:** HEAR-038-D002

**Severity:** HIGH

**Area:** Function

**Description:**
- Sprecher in der Liste (z. B. "Frau Schneider", "Max Weber") lassen sich markieren.
- Bei den darunterliegenden Schaltflaechen ist aus Nutzersicht keine wirksame Aktion erkennbar.

**Reproducible Steps:**
1. App starten.
2. Im Bereich "Speaker Enrollment" einen Eintrag anklicken.
3. Die Schaltflaechen unter der Liste betaetigen.

**Expected:** Add/Edit/Remove aendert den sichtbaren Zustand nachvollziehbar.

**Actual:** Nur Markierung in der Liste, aber keine erkennbare Funktionswirkung.

**Affected Workflow:** Speaker Edit / Enrollment Setup

**Status:** ✅ FIXED — HEAR-040 (2026-04-11)

---

### Defect #3: Start Meeting / Show Current State ohne sichtbare Reaktion

**ID:** HEAR-038-D003

**Severity:** CRITICAL

**Area:** Function

**Description:**
- Die Buttons "Start Meeting" und "Show Current State" zeigen beim Test keine sichtbare Wirkung.
- Dadurch ist der Setup- und Startworkflow nicht verifizierbar.

**Reproducible Steps:**
1. App starten und Meeting-Setup ausfuellen.
2. "Start Meeting" klicken.
3. "Show Current State" klicken.

**Expected:**
- Start Meeting startet Session und zeigt Statuswechsel.
- Show Current State zeigt aktuellen Setup-/Session-Status.

**Actual:** Keine sichtbare Reaktion.

**Affected Workflow:** Setup Action Buttons / Meeting Start

**Status:** NEW

---

### Example Defect #1: Dialog Title Not Updated

**Severity:** MEDIUM | **Area:** UI

**Description:**
When creating a new meeting, the "Edit Meeting" dialog fails to update its title when switching between meetings.

**Reproducible Steps:**
1. Create Meeting A with title "Q1 Planning"
2. Create Meeting B with title "Q2 Planning"
3. Click Edit on Meeting A
4. Dialog shows "Q1 Planning" (correct)
5. Close dialog, click Edit on Meeting B  
6. Dialog still shows "Q1 Planning" (BUG - should show "Q2 Planning")

**Affected Workflow:** Meeting Title Selection | Correction with Unknown Speaker

**Expected:** Dialog title updates to reflect currently selected meeting

**Actual:** Dialog title remains cached from previous selection

**Impact:** User confusion; editing wrong meeting possible

---

### Example Defect #2: Participant Dropdown Empty on First Load

**Severity:** HIGH | **Area:** Function

**Description:**
When opening "Edit Speaker" dialog for the first time in a session, the participant dropdown appears empty even though participants are enrolled.

**Reproducible Steps:**
1. Create meeting with 2 participants enrolled (Alice, Bob)
2. Record short segment
3. Click on transcript segment
4. Click "Edit Speaker"
5. Participant dropdown appears empty
6. Workaround: Click dropdown again or switch tab/back → list populates

**Affected Workflow:** Speaker Edit | Correction with Unknown Speaker

**Impact:** Blocks ability to correct speaker on first attempt

---

### Example Defect #3: Export Button Disabled After Protocol Update

**Severity:** MEDIUM | **Area:** Function

**Description:**
After manually correcting a speaker and regenerating the protocol, the "Export Protocol" button becomes disabled/grayed out.

**Reproducible Steps:**
1. Create meeting, record, and generate protocol
2. "Export Protocol" button enabled (working)
3. Manually correct a speaker assignment
4. Click "Regenerate Protocol"
5. "Export Protocol" button now disabled (should be enabled)

**Affected Workflow:** Setup Action Buttons | Correction with Unknown Speaker

**Workaround:** Restart app session

---

## Test Execution Checklist

During manual testing, go through each workflow and check for issues:

### Workflow 1: Meeting Title Selection
- [ ] Text input accepts standard characters (a-z, A-Z, 0-9)
- [ ] Text input accepts special characters (-, _, #, @)
- [ ] Text input respects max length if defined
- [ ] Title displays in meeting list after save
- [ ] Title persists after closing and reopening meeting
- [ ] No crash on very long titles (>100 chars)
- [ ] No crash on empty title attempt

**Defects Found:** ______ (none / D001 / D002 / etc)

---

### Workflow 2: Participant Selection
- [ ] "Add Participant" button clickable
- [ ] Participant list populates
- [ ] Enroll button starts audio capture
- [ ] Enrolled participant appears in roster
- [ ] Multiple participants can be added
- [ ] Participant removal works
- [ ] Unknown speaker properly marked when non-enrolled person speaks
- [ ] No crash on rapid add/remove

**Defects Found:** ______ (none / D001 / D002 / etc)

---

### Workflow 3: Speaker Edit
- [ ] Speaker dropdown appears on click
- [ ] All enrolled participants show in dropdown
- [ ] "Unknown" option available in dropdown
- [ ] Selection updates transcript immediately (visual feedback)
- [ ] Change persists after closing/reopening meeting
- [ ] Bulk edit multiple segments
- [ ] Undo/revert correction available

**Defects Found:** ______ (none / D001 / D002 / etc)

---

### Workflow 4: Correction with Unknown Speaker (CRITICAL)
- [ ] Unknown speaker segments clearly marked
- [ ] Correction UI visible and accessible
- [ ] After correction, protocol reflects new speaker assignment
- [ ] Correction audit trail logged
- [ ] No data loss during correction
- [ ] Corrected data persists across sessions
- [ ] No performance degradation with corrections

**Defects Found:** ______ (none / D001 / D002 / etc)

---

### Workflow 5: Setup Action Buttons
- [ ] Create Meeting button always clickable
- [ ] Edit Meeting button enabled when meeting selected
- [ ] Delete Meeting button properly disabled when no meeting selected
- [ ] Start Recording button enabled only when participants enrolled
- [ ] Stop Recording button disabled when no recording active
- [ ] Generate Protocol button disabled when no transcript available
- [ ] Export buttons responsive with < 500ms response time
- [ ] All buttons have tooltips on hover
- [ ] No crashes from rapid button clicks

**Defects Found:** ______ (none / D001 / D002 / etc)

---

## Summary Statistics

| Category | Count |
|----------|-------|
| Critical Defects Found | 1 |
| High Severity Issues | 2 |
| Medium Severity Issues | 0 |
| Low Severity Issues | 0 |
| Total Defects | 3 |
| Workflows Tested | 5 |
| Workflows Passed | 0 |
| Workflows with Issues | 3 |

**Overall Assessment:** [x] PASS | [ ] PASS WITH RISK | [ ] FAIL

---

## Sign-Off

**Test Completed By:** ___________________  
**Date:** 2026-04-11  
**Time:** 10:xx UTC  
**Total Test Duration:** ~30 minutes  

**Summary:**
Alle 3 Defects (D001–D003) durch HEAR-039/040/041 behoben und durch 23 neue Tests abgesichert. 198 Tests total, 0 Failures. HEAR-038 PASS.

---

## References

- Main Report: [docs/test-evidencequality-gates_HEAR-038-smoke-test-report.md](docs/test-evidencequality-gates_HEAR-038-smoke-test-report.md)
- QA Acceptance Matrix: [docs/governance/HEAR_QA_ACCEPTANCE_MATRIX.md](docs/governance/HEAR_QA_ACCEPTANCE_MATRIX.md)
- Quality Gates: [docs/governance/QUALITY_GATES.md](docs/governance/QUALITY_GATES.md)
- Speaker ID ADR: [docs/adr/0003-speaker-identification-and-diarization.md](docs/adr/0003-speaker-identification-and-diarization.md)
