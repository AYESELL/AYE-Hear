---
status: accepted
context_date: 2026-04-08
decision_owner: AYEHEAR_ARCHITECT
---

# ADR-0006: PostgreSQL Local Deployment Model on Windows

## Context

AYE Hear already mandates PostgreSQL as the only valid database target. The missing decision is the canonical runtime shape for local Windows deployments.

The deployment model must preserve:

- offline-first execution without cloud dependencies
- predictable local administration for end users
- a Windows-first installation story
- a single canonical storage backend for meetings, speaker profiles and protocol revisions

The evaluated runtime options are:

1. Bundled local PostgreSQL runtime managed by the application installer
2. Pre-existing user-managed PostgreSQL service
3. Installer-managed external Windows service installation
4. Container-assisted runtime for development only

## Decision

AYE Hear will use an **installer-managed local PostgreSQL runtime** for production Windows deployments, with a **container-assisted PostgreSQL runtime allowed for development only**.

### Production Runtime Shape

- PostgreSQL runs locally on the same Windows host as AYE Hear
- The installer provisions the runtime, initializes the data directory and applies schema migrations
- The database binds to loopback only and is never exposed for remote access
- AYE Hear connects through an installer-provisioned local DSN source and never through hardcoded credentials in source control
- PostgreSQL 16 is the version lock for V1 unless a later ADR supersedes it

### Credential Provisioning and DSN Sourcing

- The Windows installer generates a per-installation PostgreSQL application credential for AYE Hear
- The generated credential must not be committed to source control, written into ADR examples or shipped as a static default secret
- The installer is the canonical authority for initial DSN materialization, rotation bootstrap and secure local storage handoff
- Runtime DSN sourcing must resolve from installer-provided local configuration or an equivalent OS-protected secret source
- Runtime code may accept environment-variable injection for development and CI, but this is not the canonical production path
- DSN examples in repository code and documentation must use non-secret placeholders or installer-oriented wording only

### Local Security Expectations

- PostgreSQL configuration must enforce loopback-only `listen_addresses` for production installs
- Startup validation must fail closed when runtime checks indicate PostgreSQL is reachable beyond loopback
- Local firewall configuration and installer validation are part of the production control boundary, not optional hardening
- Credential rotation is supported operationally through installer or local administration workflow, even if UI support lands after V1 GA
- Data protection for transcript content, participant identity and speaker embeddings is governed by ADR-0009

### Development Runtime Shape

- Local development may use container-assisted PostgreSQL for convenience
- Development parity must still target PostgreSQL 16 and the same schema/migration path
- Development-only container usage is not a supported end-user runtime

## Rationale

### Why installer-managed local PostgreSQL

- Keeps PostgreSQL as the single canonical backend without fallback engines
- Reduces end-user setup friction compared with requiring a manually installed service
- Fits a Windows desktop product better than requiring Docker on customer machines
- Preserves offline-first behavior because the runtime remains fully local
- Gives DevOps a clear packaging and upgrade boundary

### Why not bundled embedded binaries only

- The product still needs explicit lifecycle management, upgrades and service behavior
- Treating PostgreSQL as an installer-managed local dependency is clearer operationally than implying an embedded database mode

### Why not user-managed PostgreSQL prerequisite

- Increases support burden and install complexity
- Produces inconsistent local environments across customer machines

## Consequences

**Positive:**

- Clear production topology for AYEHEAR_DEVOPS and AYEHEAR_DEVELOPER
- PostgreSQL-only rule is enforceable at install and runtime
- Upgrade and migration ownership are explicit
- Credential sourcing responsibility is explicit and reviewable
- Loopback-only posture becomes testable rather than implicit

**Negative:**

- Installer complexity increases
- Windows packaging must handle initialization, upgrades and local lifecycle checks
- Secret provisioning and rotation flows must be designed and tested deliberately

**Mitigations:**

- Keep loopback-only binding as the default security posture
- Version-lock PostgreSQL for V1
- Maintain a development container path for local iteration and CI parity where useful
- Keep production credentials in OS-protected local storage instead of repo-managed config files

## Deployment Topology

```mermaid
flowchart LR
    UI[AYE Hear UI Shell] --> Services[Local Application Services]
    Services --> Store[PostgreSQL 16 Local Runtime]
    Store --> Disk[Local Windows Storage]
```

## Related ADRs

- ADR-0001: AYE Hear Product Architecture
- ADR-0002: Windows Desktop App Stack (PySide6 + Python)
- ADR-0003: Speaker Identification & Diarization Pipeline
- ADR-0007: Persistence Contract and Lifecycle
- ADR-0009: Data Protection and Encryption-at-Rest Model

---

**Status:** Accepted  
**Owner:** AYEHEAR_ARCHITECT  
**Updated:** 2026-04-09
