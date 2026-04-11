---
task_id: HEAR-038  
title: Manual Smoke Test Quick Start
created: 2026-04-11
owner: AYEHEAR_QA
---

# HEAR-038: Quick Start – Manual Smoke Test Guide

## Prerequisites ✓

- [x] AyeHear installer executed successfully
- [x] App running: `C:\AyeHear\app\AyeHear.exe`
- [x] PostgreSQL available on localhost:5432
- [x] Microphone/audio device available for testing

## Part 1: Setup (2 minutes)

If app already running, skip to Part 2.

```powershell
# Start the application
C:\AyeHear\app\AyeHear.exe
```

**Verify:**
- [ ] App window appears within 3 seconds
- [ ] No error dialogs on startup
- [ ] Main UI responsive (clickable buttons)

---

## Part 2: Meeting Title Selection (5 minutes)

### Test Case 1: Create Meeting with Title

1. Look for "**New Meeting**" or "**Create**" button
   - **Screenshot:** Capture main screen with button highlighted
   
2. Click button → Meeting creation dialog appears
   - **Check:** Dialog title shows "Create Meeting" or similar
   
3. Find text input field for meeting title
   - **Type:** "Smoke Test Meeting 2026-04-11"
   - **Check:** Text appears in field (no invisible characters)
   
4. **Screenshot:** Capture meeting title entered in form
   
5. Click "**Save**" or "**Create**" button
   - **Check:** Dialog closes, meeting appears in list
   
6. **Screenshot:** Capture meeting created in list with correct title

**Expected Result:** ✅ Title persists and displays correctly

**Defect Template:** If title missing/wrong, use [HEAR-038-defect-tracking.md](HEAR-038-defect-tracking.md#defect-1-title)

---

## Part 3: Participant Selection & Enrollment (8 minutes)

### Test Case 2: Add Participants

1. Open your newly created meeting (double-click or select + Open)
   - **Screenshot:** Meeting detail view

2. Find "**Add Participant**" or "**Select Participants**" button
   - **Screenshot:** Button location

3. Click button → Participant list/dialog appears
   - **Check:** At least one participant option shown

4. Select a participant (or create new)
   - **Participant Example:** "Alice" or "Test Speaker 1"
   - **Screenshot:** Participant selected

5. Click "**Enroll**" or "**Add**"
   - **Check:** UI shows "Processing" or "Capturing audio..."
   - **Wait:** 3-5 seconds (audio enrollment)

6. **Screenshot:** Participant enrolled, appearing in meeting roster

7. **Repeat step 2-6** with second participant (e.g., "Bob")
   - **Screenshot:** Two participants in roster

**Expected Result:** ✅ Meeting has 2 enrolled participants

**Defect Notes:** If enrollment fails/hangs, proceed to Part 4

---

## Part 4: Speaker Identification & Unknown Speaker Marking (5 minutes)

### Test Case 3: Trigger Unknown Speaker Workflow

**Option A** (If recording works):
1. Click "**Start Recording**" button  
2. Speak a sentence (30 seconds)
3. Then invite non-enrolled person to speak
4. Click "**Stop Recording**"
5. Review transcript → Unknown speaker should be marked differently

**Option B** (Manual Test):
1. In transcript view, find any segment
2. Look for speaker name/icon
3. Verify **enrolled participants** show name + confidence
4. Verify **unknown segments** clearly marked (e.g., "Unknown", "Uncertain", "?")

**Screenshot:** Capture both enrolled speaker + unknown speaker segment

**Expected Result:** ✅ Unknown segments visually distinct from known speakers

---

## Part 5: Speaker Edit & Correction Flow (8 minutes) ⭐ CRITICAL

### Test Case 4: Correct Unknown Speaker Assignment

This is the **primary test case** for HEAR-038.

#### Step 1: Select Unknown Segment
1. In transcript view, find a segment marked "Unknown" (or create one)
2. **Screenshot:** Unknown segment highlighted
3. Click on the segment → Details panel appears

#### Step 2: Open Speaker Edit Dialog
1. Look for "**Edit Speaker**", "**Assign Speaker**", or speaker name field
2. Click to open speaker selection dialog
   - **Screenshot:** Dialog showing participant dropdown
   
3. **Verify:** All enrolled participants appear in dropdown
   - Example: ["Alice", "Bob", "Unknown"]

#### Step 3: Select Correct Participant
1. Click dropdown → Expand participant list
   - **Screenshot:** List with all participants visible
   
2. Select a participant (e.g., "Alice")
   - **Screenshot:** Selection highlighted

#### Step 4: Apply Correction
1. Click "**Apply**", "**Save**", or "**Confirm**" button
   - **Check:** Dialog closes, transcript updates
   - **Screenshot:** Segment now shows "Alice" instead of "Unknown"

#### Step 5: Verify Persistence
1. Close and reopen the meeting
   - **Check:** Correction still shows (data persisted)
   - **Screenshot:** Corrected speaker visible after reload

#### Step 6: Check Protocol Export
1. Click "**Generate Protocol**" or similar
2. Protocol view/export appears
3. Look for the corrected segment in protocol text
4. **Screenshot:** Protocol showing "Alice" in corrected segment (not "Unknown")
5. Export to PDF or DOCX
   - **Check:** File created successfully
   - **Screenshot:** Exported file in Explorer

**Expected Result:** ✅ Full end-to-end correction workflow functional

**Critical Success Criteria:**
- ✅ Unknown speaker clearly marked in transcript
- ✅ Speaker dropdown shows all participants
- ✅ Correction updates transcript immediately
- ✅ Correction persists across sessions
- ✅ Protocol reflects corrected speaker

**If ANY step fails:** Stop and document defect in [HEAR-038-defect-tracking.md](HEAR-038-defect-tracking.md)

---

## Part 6: Setup Action Buttons (5 minutes)

### Test Case 5: Button Functionality Checklist

| Button | Action | Expected | Screenshot |
|--------|--------|----------|-----------|
| **New Meeting** | Click | Dialog appears | [ ] |
| **Edit Meeting** | Click | Edit mode/dialog | [ ] |
| **Delete Meeting** | Click (if enabled) | Confirmation dialog | [ ] |
| **Start Recording** | Click (if participants exist) | Recording begins | [ ] |
| **Stop Recording** | Click (if recording) | Recording ends | [ ] |
| **Generate Protocol** | Click (if transcript exists) | Protocol view | [ ] |
| **Export PDF/DOCX** | Click (if protocol exists) | File save dialog | [ ] |

**For each button:**
1. Hover over button → **Check** tooltip appears
2. Click button → **Check** appropriate action occurs
3. **Screenshot:** If action visible/non-obvious

**Expected Result:** ✅ All buttons functional and appropriately enabled/disabled

---

## Part 7: Defect Documentation (As Found)

If you find issues, document using this format:

```markdown
### DEFECT FOUND: [Brief Title]

**Workflow:** [Which part failed?]
**Steps to Reproduce:**
1. [Step 1]
2. [Step 2]
3. [Result/ERROR]

**Expected:** [What should happen]
**Actual:** [What actually happens]

**Screenshot:** [Attach screenshot]

**Severity:** [ ] CRITICAL | [ ] HIGH | [ ] MEDIUM | [ ] LOW
```

Add to file: [HEAR-038-defect-tracking.md](HEAR-038-defect-tracking.md)

---

## Final Sign-Off

After completing all test cases:

```markdown
## Test Completion Sign-Off

Test Completed By: _________________
Date: 2026-04-11
Start Time: ____  End Time: ____
Total Duration: ____ minutes

Defects Found: __ (Critical: __, High: __, Medium: __, Low: __)

Overall Assessment:
[ ] ✅ PASS - All workflows functional
[ ] 🟡 PASS WITH ISSUES - Documented defects non-blocking  
[ ] ❌ FAIL - Critical defects block release

Comments:
[Any additional observations]
```

---

## Reference Files

- **Full Report:** [docs/test-evidencequality-gates_HEAR-038-smoke-test-report.md](docs/test-evidencequality-gates_HEAR-038-smoke-test-report.md)
- **Defect Template:** [docs/HEAR-038-defect-tracking.md](docs/HEAR-038-defect-tracking.md)
- **QA Acceptance Matrix:** [docs/governance/HEAR_QA_ACCEPTANCE_MATRIX.md](docs/governance/HEAR_QA_ACCEPTANCE_MATRIX.md)
- **Test Log:** `C:\Temp\hear-smoke-test-evidance.txt`

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| **App won't start** | Try: `C:\AyeHear\app\AyeHear.exe` manually; check logs in `C:\AyeHear\logs\` |
| **No participants to enroll** | Try: Create new participant first, then enroll |
| **Recording not working** | Check: Microphone device in Settings; test with system audio app first |
| **Correction dialog not opening** | Try: Right-click segment, look for context menu options |
| **Export button disabled** | Reason: No protocol generated yet; generate protocol first |

---

**Estimated Total Test Time:** 30-40 minutes  
**Difficulty:** Intermediate (follows documented workflows)  
**Risk if skipped:** MEDIUM (critical correction workflow may have issues)

---

**Questions?** See [docs/quick-refs/LOCAL_TESTING_QUICKREF.md](docs/quick-refs/LOCAL_TESTING_QUICKREF.md) or reach out to AYEHEAR_QA team.
