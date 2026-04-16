---
status: accepted
context_date: 2026-04-16
decision_owner: AYEHEAR_ARCHITECT
task: HEAR-072
---

# ADR-0011: Install-Root Relative Runtime and Artifact Paths

## Context

AYE Hear currently assumes a fixed production path of `C:/AyeHear` in multiple runtime surfaces:

- application logging resolves to `C:/AyeHear/logs`
- runtime DSN sourcing resolves to `C:/AyeHear/runtime/pg.dsn`
- exported meeting artifacts resolve to `C:/AyeHear/exports`
- PostgreSQL installer and health-check scripts default to `C:/AyeHear`

This is operationally brittle because the Windows installer may install AYE Hear into a different directory. In that case, packaged runtime behavior can split across the real install directory and the hard-coded fallback root.

The architecture needs one canonical rule so downstream implementation does not invent path behavior independently for app logs, PostgreSQL logs, DSN/runtime files and user-visible exports.

This decision must remain compatible with:

- ADR-0002 (Windows desktop packaged application)
- ADR-0006 (installer-managed local PostgreSQL runtime)
- ADR-0009 (local data protection and local secret handling)
- HEAR-073 (runtime-path implementation)
- HEAR-074 / HEAR-076 user-facing artifact discoverability work

## Decision

AYE Hear adopts a **single install-root-relative path model** for packaged Windows runtime behavior.

### 1. Canonical Path Anchor

For packaged installs, all production runtime paths must resolve from one canonical **install root**.

The install root is determined in this priority order:

1. Explicit installer or launcher override via `AYEHEAR_INSTALL_DIR`
2. Explicit function/script parameter passed by installer, launcher or test harness
3. Packaged-runtime self-discovery from the executable or script location
4. Development fallback root for local source execution and CI

`C:/AyeHear` is no longer a canonical production location. It is only an installer default value when the user accepts that destination.

### 2. Required Production Directory Layout

All packaged runtime components must treat the following subdirectories as normative relative children of the resolved install root:

- `app/` for the packaged application bundle
- `runtime/` for installer-managed DSN material, runtime state files and future local machine-scoped configuration handoff
- `logs/` for application logs, PostgreSQL logs and helper-script diagnostics
- `exports/` for user-generated meeting artifacts that the UI surfaces to the user
- `pgsql/` for PostgreSQL binaries managed by the installer
- `data/` for PostgreSQL data directories and related service state
- `scripts/` for post-install operational scripts when copied under the install tree

### 3. Distinction Between Internal Runtime State and User-Generated Artifacts

The path model distinguishes two classes:

#### A. Internal runtime-managed state

This includes:

- DSN files
- runtime lock/state files
- application logs
- PostgreSQL logs
- PostgreSQL binaries and data directories
- machine-scoped operational helper outputs

These files are **internal runtime assets**. They must resolve only under the install-root-controlled runtime, logs, pgsql or data subtrees. They are not user-facing output locations.

#### B. User-generated meeting artifacts

This includes:

- exported protocol files
- exported transcript files
- future Markdown, DOCX and PDF protocol exports

These files are **user-visible artifacts**. They must resolve under the dedicated install-root-relative `exports/` subtree unless a future approved ADR introduces a user-configurable export destination.

The application UI must treat the export directory as a discoverable user destination, not as hidden runtime state.

### 4. Shared Resolution Contract

AYE Hear runtime code, launcher code and PowerShell helper scripts must use one shared logical contract:

- resolve install root once
- derive child paths from named subdirectories
- do not hard-code absolute production paths in individual modules
- keep development and CI fallbacks explicit and separate from packaged-production logic

Downstream implementation should centralize this in one path-resolution module or equivalent shared helper surface rather than repeating path assembly in each subsystem.

### 5. Development and CI Behavior

When AYE Hear runs from source rather than from an installed package:

- development may use a local fallback root such as the repository working directory or current working directory
- `logs/`, `runtime/` and `exports/` may be created under that fallback root for testability
- development fallback behavior must not redefine packaged-production behavior

### 6. Security and Privacy Constraints

- DSN files remain installer-managed local secrets per ADR-0006 and ADR-0009
- runtime-managed directories must remain local-only and must not introduce cloud-backed path dependencies
- logs must continue to avoid transcript text, speaker embeddings and raw audio content per existing security review constraints
- exports remain local user artifacts and must be treated as sensitive meeting content under ADR-0009

## Normative Rules

- Production code must not hard-code `C:/AyeHear` as the effective runtime path.
- Installer scripts may offer `C:/AyeHear` as a default destination, but all persisted paths must derive from the actual selected install root.
- Application logging, PostgreSQL logging, DSN sourcing and export path resolution must all use the same install-root anchor.
- The `exports/` subtree is the canonical packaged default for user-generated artifacts until another ADR explicitly changes export-destination behavior.
- Development fallback paths must never silently override the packaged install root when an install-root signal is present.

## Rationale

### Why install-root-relative instead of fixed `C:/AyeHear`

- It matches Windows installer reality when users choose a non-default destination.
- It avoids split-brain support cases where app files live in one directory while logs or exports silently appear in another.
- It gives HEAR-073 one implementable contract instead of multiple local conventions.

### Why exports remain under the install-root model for now

- HEAR-073 explicitly requires exported artifacts to resolve from the configured install root.
- Keeping exports under a dedicated sibling subtree preserves a single discoverable product footprint for packaged deployments.
- The user-facing distinction is still preserved because `exports/` is a surfaced artifact directory, not hidden runtime state.

## Consequences

**Positive:**

- Packaged installations behave consistently regardless of chosen install directory.
- Support, QA and DevOps get one predictable place to inspect runtime state and one predictable place to find meeting artifacts.
- Developer tasks can replace ad-hoc literals with one approved resolver contract.

**Negative:**

- Existing code and runbooks that mention `C:/AyeHear` need targeted updates.
- Export discoverability still depends on the UI surfacing the `exports/` path clearly.

**Mitigations:**

- Centralize path resolution in one implementation surface.
- Update packaging/runbook references as downstream follow-up where they currently describe fixed paths.
- Pair HEAR-073 with HEAR-076 so the export location is visible and actionable in the UI.

## Required Follow-Up

- HEAR-073 must replace hard-coded production literals in runtime code and scripts with install-root-relative resolution.
- HEAR-073 tests must cover packaged mode and development fallback mode.
- HEAR-076 must expose the export directory clearly in the UI and post-meeting flow.
- Packaging and QA runbooks should be updated to describe the selected install root rather than assuming `C:/AyeHear`.

## Related ADRs

- ADR-0002: Windows Desktop App Stack (PySide6 + Python)
- ADR-0006: PostgreSQL Local Deployment Model on Windows
- ADR-0009: Data Protection and Encryption-at-Rest Model
- ADR-0010: V1 Scope Integrity and Release State Separation

---

**Status:** Accepted  
**Owner:** AYEHEAR_ARCHITECT  
**Updated:** 2026-04-16