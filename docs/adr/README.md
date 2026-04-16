---
status: active
context_date: 2026-04-08
decision_owner: AYEHEAR_ARCHITECT
---

# ADR Index – AYE Hear Architecture Decisions

This directory contains all significant architecture decisions for the AYE Hear product.

## Core ADRs

| #    | Title                                         | Status   | Owner             |
| ---- | --------------------------------------------- | -------- | ----------------- |
| 0001 | AYE Hear Product Architecture                 | Accepted | AYEHEAR_ARCHITECT |
| 0002 | Windows Desktop App Stack (PySide6 + Python)  | Accepted | AYEHEAR_ARCHITECT |
| 0003 | Speaker Identification & Diarization Pipeline | Accepted | AYEHEAR_ARCHITECT |
| 0004 | Audio Capture & Preprocessing (WASAPI)        | Accepted | AYEHEAR_ARCHITECT |
| 0005 | Meeting Protocol Engine & LLM Integration     | Accepted | AYEHEAR_ARCHITECT |
| 0006 | PostgreSQL Local Deployment Model on Windows  | Accepted | AYEHEAR_ARCHITECT |
| 0007 | Persistence Contract and Lifecycle            | Accepted | AYEHEAR_ARCHITECT |
| 0008 | Hardware Profiles and Acceleration Strategy   | Accepted | AYEHEAR_ARCHITECT |
| 0009 | Data Protection and Encryption-at-Rest Model  | Accepted | AYEHEAR_ARCHITECT |
| 0010 | V1 Scope Integrity and Release State Separation | Accepted | AYEHEAR_ARCHITECT |
| 0011 | Install-Root Relative Runtime and Artifact Paths | Accepted | AYEHEAR_ARCHITECT |

## Supporting Architecture Documents

- [docs/architecture/SYSTEM_BOUNDARIES.md](../architecture/SYSTEM_BOUNDARIES.md) – subsystem responsibilities, ownership and runtime boundaries

## How to Create a New ADR

1. Copy template from an existing ADR (e.g., 0001)
2. Use next sequential number: `00XX-title.md`
3. Fill in Context, Decision, Consequences, Alternatives
4. Update this Index
5. Submit for review via Pull Request

---

**Maintained by:** AYEHEAR_ARCHITECT  
**Last Updated:** 2026-04-16
