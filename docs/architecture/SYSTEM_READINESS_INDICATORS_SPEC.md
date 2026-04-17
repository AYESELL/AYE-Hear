---
owner: AYEHEAR_ARCHITECT
status: draft
updated: 2026-04-16
category: architecture-spec
---

# System Readiness Indicators - Architecture Spec

## Goal

Provide immediate and explicit runtime visibility for V1-critical system components so users, QA, and support can see whether AYE Hear is running in product-capable mode or in degraded mode before they trust the meeting workflow.

The UI must make hidden dependency failures visible, especially when the app can still launch but important capabilities are not actually available.

## Problem Statement

AYE Hear currently allows partial startup even when critical local services are missing or degraded, for example:

- runtime persistence is not connected,
- PostgreSQL bootstrap is unavailable,
- protocol drafting falls back because local Ollama is unavailable,
- enrollment cannot persist real speaker profiles,
- export or review-queue behavior is running without the intended backend path.

This creates a misleading user experience: the application appears usable while key product promises are unavailable. Users only discover the failure later through poor transcript, protocol, review, or enrollment behavior.

## Scope

In scope:

- visible system-status indicator group in the main mask
- explicit state for critical runtime dependencies
- distinction between ready, degraded, and blocked states
- short user-facing explanations for each failing component
- clear signal when testing should be stopped because product-complete behavior is impossible
- integration with existing setup panel and meeting-start flow
- test coverage for status rendering and degraded/blocking cases

Out of scope:

- fixing the underlying runtime/bootstrap issues themselves
- redesigning protocol extraction quality
- redesigning speaker identification thresholds
- replacing existing mic-level widget behavior

## ADR Alignment

- ADR-0003: Speaker identification must remain confidence-based and manually correctable. Indicators may expose enrollment or persistence readiness, but must not auto-hide uncertainty.
- ADR-0005: Protocol quality depends on the local LLM path and persisted draft path. If those are unavailable, the UI must state that protocol quality is degraded.
- ADR-0006: PostgreSQL remains the canonical local backend. Missing database connectivity is not a normal alternate mode for product-complete behavior.
- ADR-0010: Product-complete claims are forbidden when V1-critical runtime capabilities are degraded.
- ADR-0011: Runtime path resolution remains install-root-relative; indicator logic must not reintroduce hard-coded path assumptions.

## UX Contract

## Placement

Add a dedicated "System Readiness" box in the main setup area above or near meeting start controls.

The box must remain visible before, during, and after meeting start so users can diagnose failures without opening logs first.

## Required Components

The indicator group must show at least these components:

1. Database / Runtime Persistence
2. Transcript Persistence + Review Queue Backend
3. Speaker Enrollment Persistence
4. Local LLM / Protocol Engine Path
5. Audio Input Availability
6. Export Target Availability

Optional future components:

- Whisper model readiness
- Snapshot/draft persistence readiness
- Windows service health for local PostgreSQL

## Indicator States

Each component must expose one of these visible states:

1. Ready
- Visual: green indicator
- Meaning: required capability is available and the intended product path can be used

2. Degraded
- Visual: amber/yellow indicator
- Meaning: application can continue, but product quality or completeness is reduced
- Must include short reason text

3. Blocked
- Visual: red indicator
- Meaning: starting or validating the intended workflow is not meaningful because the core capability is unavailable
- Must include short reason text

4. Unknown
- Visual: neutral/gray indicator
- Meaning: status not yet determined
- Should only appear transiently during startup or refresh

## Required Semantics Per Component

### 1. Database / Runtime Persistence

Ready:
- runtime DSN resolved
- database bootstrap succeeded
- canonical repositories are connected

Blocked:
- no runtime DSN
- bootstrap failed
- app is running in local-only mode without persistence

User text examples:
- Ready: "Database connected"
- Blocked: "Database unavailable - product workflow degraded"

### 2. Transcript Persistence + Review Queue Backend

Ready:
- transcript repository connected
- low-confidence review queue can persist and reload data

Blocked:
- transcript repository missing

User text examples:
- Ready: "Review queue backend ready"
- Blocked: "Review queue not available"

### 3. Speaker Enrollment Persistence

Ready:
- speaker profile repository and participant repository are both connected
- enrollment can persist participant-to-profile linkage

Degraded:
- microphone recording works but persistence path is unavailable

Blocked:
- enrollment cannot produce persistent V1 speaker profiles

User text examples:
- Ready: "Enrollment persistence ready"
- Degraded: "Enrollment recording only - profile persistence unavailable"

### 4. Local LLM / Protocol Engine Path

Ready:
- local Ollama endpoint reachable on loopback
- configured local model path available for structured protocol extraction

Degraded:
- protocol generation will fall back to rule-based extraction

User text examples:
- Ready: "Local protocol engine ready"
- Degraded: "Ollama unavailable - rule-based protocol fallback"

This state must never be displayed as green when the protocol panel is only mirroring transcript lines or using fallback extraction.

### 5. Audio Input Availability

Ready:
- at least one capture path is selectable or Windows default microphone path is available

Blocked:
- no usable capture path can be opened

Note:
- this is distinct from live level or no-signal state handled by the mic-level widget

### 6. Export Target Availability

Ready:
- export target directory can be resolved and created

Degraded:
- export path exists only in development fallback mode when packaged expectation is unavailable

Blocked:
- export target is not writable

## Aggregate Status Rule

In addition to per-component indicators, the box must show an aggregate top-line state:

- Product Path Ready
- Product Path Degraded
- Product Path Blocked

Aggregation rule:

- If any component is Blocked and that component is required for the requested workflow, aggregate status is Blocked.
- Else if any component is Degraded, aggregate status is Degraded.
- Else aggregate status is Ready.

## Meeting-Start and Test-Abort Rules

The UI must support fast test/no-test decisions.

### Hard stop recommendation

When any of these components is Blocked, the UI must visibly recommend stopping product-complete testing:

- Database / Runtime Persistence
- Transcript Persistence + Review Queue Backend
- Speaker Enrollment Persistence

User-facing text example:

- "Critical backend missing - stop product-complete test and inspect runtime setup."

### Degraded-but-continuable recommendation

When Local LLM / Protocol Engine Path is Degraded, the UI may allow continued testing but must clearly state that protocol quality validation is not meaningful for product-complete sign-off.

User-facing text example:

- "Protocol fallback active - do not treat protocol results as product-complete evidence."

## Refresh Behavior

- Initial readiness evaluation runs during window startup.
- Readiness is refreshed when a meeting starts.
- Readiness can be refreshed manually via an explicit "Refresh Status" action or equivalent non-destructive user interaction.
- Refresh must not block the UI thread for long-running checks.

## Logging and Diagnostics

- UI indicators are advisory and user-facing.
- Detailed reasons remain in local logs.
- Indicator text must not expose secrets, DSN values, or raw transcript content.

## Implementation Guidance for AYEHEAR_DEVELOPER

- Add a compact status widget group in the setup panel.
- Use explicit color/state mapping rather than relying on free-form text only.
- Derive readiness from actual connected services and repositories, not from assumptions.
- Distinguish packaged-product path from development fallback path.
- Do not silently present degraded fallback modes as normal readiness.
- Ensure protocol fallback and no-persistence mode are visible before users start validating results.

## QA Acceptance Addendum

New QA scenarios to execute and attach evidence:

- QA-SR-01: Database connected -> indicator green
- QA-SR-02: Runtime launched without DSN -> database indicator red and aggregate status blocked
- QA-SR-03: Enrollment without persistence path -> enrollment indicator degraded or blocked with explicit reason
- QA-SR-04: Ollama unavailable -> protocol indicator degraded and fallback warning visible
- QA-SR-05: Export directory unavailable -> export indicator degraded or blocked
- QA-SR-06: Installed non-default path run -> indicators reflect real packaged runtime state, not development fallback assumptions

Evidence:

- screenshots of all readiness states
- installed runtime log excerpt for each failing state
- note whether test execution was continued or aborted
- explicit statement whether product-complete testing was valid under the observed state

## Architect Phase-2 Gate for this scope

Phase 3 implementation is approved only if:

- developer task references this UX contract explicitly,
- component list includes database, review backend, enrollment persistence, local protocol engine, audio, and export target,
- blocked versus degraded semantics are implemented explicitly,
- QA task includes installed-runtime evidence and test-abort guidance,
- no degraded fallback state is reported as product-ready in documentation or QA sign-off.