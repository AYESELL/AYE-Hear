---
status: accepted
context_date: 2026-04-16
decision_owner: AYEHEAR_ARCHITECT
task: HEAR-067
---

# ADR-0010: V1 Scope Integrity and Release State Separation

## Context

AYE Hear currently has two valid but different release viewpoints:

- Operations handoff readiness is GO (documented in HEAR-052).
- Product-complete V1 readiness is NO-GO (documented in HEAR-066).

Without an explicit architecture-level rule, these two states can be conflated in product and release communication.

The gap analysis identifies three product-complete blockers:

- B1: Real microphone-based enrollment workflow is not yet implemented.
- B2: Speaker embedding extraction still uses deterministic stub logic.
- B3: Runtime export contract does not yet match documented Markdown/DOCX/PDF expectation.

## Decision

AYE Hear adopts a mandatory two-state release model for V1 claims:

1. **Operations-Handoff Readiness**
2. **Product-Complete Readiness**

Both states MUST be recorded explicitly in governance and product scope documents.

### Normative Rules

- A document may declare Operations-Handoff GO while Product-Complete remains NO-GO.
- Product-complete claims are forbidden until B1, B2, and B3 are closed with linked evidence.
- V1 scope statements must distinguish between:
  - currently approved operations-handoff capabilities
  - target product-complete capabilities
- Release decision records must include both states when they differ.

### HEAR-067 Resolution Path

For the current release baseline, option B is selected:

- Downscope immediate V1 release claims to operations-handoff reality.
- Keep product-complete capabilities as target scope pending closure of B1-B3.

## Consequences

### Positive

- Prevents ambiguous "GO" statements that hide unresolved product-complete gaps.
- Aligns Product Foundation, QA evidence, and release decisions.
- Creates a stable gate for future product-complete declarations.

### Trade-Offs

- Documentation must be kept synchronized across product and governance records.
- Stakeholders must evaluate two states instead of one headline status.

### Required Follow-Up

- Keep B1/B2/B3 closure evidence linked in QA and release governance artifacts.
- Update Product Foundation and release decision docs whenever state changes.

## Related Artifacts

- `docs/HEAR-052-release-decision.md`
- `docs/HEAR-066-v1-readiness-gap-analysis.md`
- `docs/PRODUCT_FOUNDATION.md`
- `docs/governance/QUALITY_GATES.md`
- `docs/governance/DEFINITIONS_OF_DONE.md`

---

**Status:** Accepted  
**Owner:** AYEHEAR_ARCHITECT  
**Updated:** 2026-04-16
