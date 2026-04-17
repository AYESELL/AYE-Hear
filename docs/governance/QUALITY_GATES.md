---
owner: AYEHEAR_ARCHITECT
status: active
updated: 2026-04-16
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
- ✅ **Installed Runtime E2E Evidence (V1-Critical):** For V1-critical flows, evidence must come from the packaged installed application (not only from in-repo/unit/headless runs)
- ✅ **Installed E2E Scope Coverage:** Meeting setup, enrollment, transcription, speaker attribution, protocol drafting, export, and runtime bootstrap must be validated in installed runtime evidence
- ✅ **Error Paths:** Graceful failure handling (device disconnect, buffer underrun, etc.)
- ✅ **Acceptance Criteria:** All AC from task satisfied
- ✅ **Manual Testing:** Product owner or QA sign-off
- ✅ **No Placeholder in V1 Path:** No mock/stub/placeholder behavior in V1-critical user flows (meeting setup, enrollment, transcription, speaker attribution, protocol, export)
- ✅ **V1 Capability Matrix:** Product-complete claim allowed only when all V1 capabilities are marked Green with linked evidence
- ✅ **Completion Language Guardrail:** "Done", "product-complete", or equivalent completion claims are forbidden when required installed E2E evidence is missing

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
- ✅ **Scope Integrity Note:** If Operations-handoff GO differs from Product-complete GO, release docs must state the difference explicitly
- ✅ **Installed Evidence References:** Release/readiness docs link the concrete installed E2E evidence artifacts used for completion claims

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
- [ ] Installed runtime E2E evidence exists for V1-critical flow
- [ ] Installed E2E scope covers setup, enrollment, transcription, speaker attribution, protocol, export, and runtime bootstrap
- [ ] No placeholder/stub behavior in V1-critical user flows
- [ ] V1 capability matrix fully green (with evidence links)
- [ ] No completion/product-complete claim without installed E2E evidence
- [ ] ADR alignment checked
- [ ] No external calls (offline-first)
- [ ] Speaker confidence flagged
- [ ] Code comments added
- [ ] Documentation updated
- [ ] Scope integrity note added when Ops-GO differs from Product-complete GO
- [ ] Release/readiness docs reference installed E2E evidence artifacts
- [ ] Accessibility OK

**Approval:** [ ] AYEHEAR_ARCHITECT [ ] AYEHEAR_QA [ ] AYEHEAR_SECURITY
```

---

**Owner:** AYEHEAR_ARCHITECT  
**Updated:** 2026-04-16
