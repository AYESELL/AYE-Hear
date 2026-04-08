---
owner: AYEHEAR_QA
status: draft
updated: 2026-04-08
---

# Local Testing Quick Reference – AYE Hear

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

---

## Protocol Generation Tests

**Test 1: Decision Capture**
- Speak decision phrase
- ✅ Decision in protocol ≤60 sec → Pass

**Test 2: Task Capture**
- Speak action phrase
- ✅ Task with owner + deadline → Pass

---

## Export Tests

- ✅ Markdown: Created and readable
- ✅ DOCX: Opens in Word
- ✅ PDF: Opens in reader

---

**Owner:** AYEHEAR_QA
