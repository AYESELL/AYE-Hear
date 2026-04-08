---
owner: AYEHEAR_ARCHITECT
status: active
updated: 2026-04-08
category: governance
---

# Quality Gates – AYE Hear

Before any PR is merged, the following quality gates MUST be satisfied.

## Code Quality

- ✅ **Unit Tests:** ≥75% code coverage (`pytest --cov`)
- ✅ **Build:** No errors (`python -m py_compile src/ayehear`)
- ✅ **Linting:** No errors (`pylint src/ayehear` or `ruff check`)
- ✅ **Type Hints:** Core modules type-checked (`mypy src/ayehear`)

## Functional Validation

- ✅ **Happy Path:** Primary workflow tested end-to-end
- ✅ **Error Paths:** Graceful failure handling (device disconnect, buffer underrun, etc.)
- ✅ **Acceptance Criteria:** All AC from task satisfied
- ✅ **Manual Testing:** Product owner or QA sign-off

## Architecture & Design

- ✅ **ADR Alignment:** Code follows relevant ADRs
- ✅ **AYEHEAR_ARCHITECT Review:** Design approved before coding
- ✅ **Interface Contracts:** APIs match ADR-0005 or design doc

## Security & Privacy

- ✅ **No External Calls:** Offline-first verified (no API, no telemetry default)
- ✅ **Speaker Data:** Confidence scores logged, no unauthorized speaker identification
- ✅ **Local Storage:** All artifacts remain on user's machine
- ✅ **Credentials:** No hardcoded secrets

## AI/ML Specific (ADR-0005)

- ✅ **Model Fix:** Ollama model version pinned in requirements
- ✅ **Prompt Fix:** Protocol engine prompt logged and versioned
- ✅ **Confidence Scoring:** Extractions include confidence thresholds
- ✅ **Fallback Behavior:** Manual override always available

## Documentation

- ✅ **Code Comments:** Complex logic documented (especially diarization, protocol engine)
- ✅ **User-Facing Changes:** Update README or docs/
- ✅ **ADR Updates:** If architecture changed, update ADRs

## Accessibility & UX

- ✅ **Windows Integration:** Uses WASAPI for audio, NSIS for installer
- ✅ **Error Messages:** User-friendly (not stack traces)
- ✅ **Live Feedback:** Protocol updates appear ≤60 sec after event

---

## Gate Checklist Template

```markdown
## Quality Gate Review

- [ ] Unit tests ≥75% coverage
- [ ] Build passes
- [ ] Linting passes
- [ ] Type hints verified
- [ ] Acceptance criteria met
- [ ] Manual testing done (sign-off: ___)
- [ ] ADR alignment checked
- [ ] No external calls (offline-first)
- [ ] Speaker confidence flagged
- [ ] Code comments added
- [ ] Documentation updated
- [ ] Accessibility OK

**Approval:** [ ] AYEHEAR_ARCHITECT [ ] AYEHEAR_QA [ ] AYEHEAR_SECURITY
```

---

**Owner:** AYEHEAR_ARCHITECT  
**Updated:** 2026-04-08
