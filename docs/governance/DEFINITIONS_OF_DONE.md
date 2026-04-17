---
owner: AYEHEAR_ARCHITECT
status: active
updated: 2026-04-16
---

# Definition of Done – AYE Hear

A feature/fix is **Done** when:

## Code
- ✅ PEP 8 compliant, type hints applied
- ✅ Unit tests ≥75% coverage
- ✅ Code compiles and imports without errors
- ✅ No mock/stub/placeholder behavior remains in V1-critical user workflow paths

## Runtime Evidence
- ✅ For V1-critical scope, installed-package E2E evidence exists (not only local/in-repo/headless checks)
- ✅ Installed E2E coverage includes: meeting setup, enrollment, transcription, speaker attribution, protocol drafting, export, runtime bootstrap
- ✅ If critical component readiness is blocked/degraded, product-complete completion claim is not allowed

## Design
- ✅ Approved design from AYEHEAR_ARCHITECT
- ✅ ADRs created/updated if architecture affected

## Privacy
- ✅ No external API calls (offline-first verified)
- ✅ Speaker ID includes confidence scores
- ✅ No credentials hardcoded

## Review
- ✅ Code reviewed + quality gates passed
- ✅ Acceptance criteria met
- ✅ V1 Capability Matrix entry is Green with linked evidence (for V1-scoped work)
- ✅ Completion language guardrail respected: no "Done"/"product-complete" claim without required installed E2E evidence

## Documentation
- ✅ README and docs/* updated
- ✅ Code comments for complex logic
- ✅ Release docs explicitly distinguish Operations handoff vs Product-complete status when they differ
- ✅ Release/readiness docs link installed E2E evidence artifacts used for any completion/product-complete statement

---

**Owner:** AYEHEAR_ARCHITECT
