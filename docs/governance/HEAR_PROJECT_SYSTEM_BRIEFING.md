---
owner: AYEHEAR_ARCHITECT
status: active
updated: 2026-05-06
category: external-ai-briefing
---

# AYE Hear: Project System Briefing (for External AI Systems)

## 1) What AYE Hear Is

AYE Hear is a Windows-first desktop application for local, offline-first meeting intelligence.
It captures microphone audio, identifies speakers, transcribes speech, and generates structured meeting protocols.

Primary objective:
- Deliver practical meeting documentation support while keeping all sensitive audio and text data local.

Core promise:
- No runtime cloud dependency for core processing.

## 2) Product Goals

AYE Hear is designed to achieve five goals:

1. Privacy-first operation
- Audio and meeting artifacts remain on the local machine.
- No mandatory external API calls for core runtime behavior.

2. Operational reliability in offline environments
- Core workflows continue without internet connectivity.
- Users can run the system in controlled enterprise environments.

3. Speaker-aware transcription quality
- Speaker enrollment and confidence-based attribution are built into the workflow.
- Uncertain matches can be manually corrected.

4. Actionable protocol output
- Meetings are transformed into structured outputs (decisions, tasks, open items, risks).
- Export options are available for downstream business use.

5. Governance-ready architecture
- Architecture and quality decisions are tracked via ADRs and governance docs.

## 3) Scope and Positioning

In short:
- AYE Hear is not a cloud SaaS meeting bot.
- AYE Hear is a local desktop assistant for sensitive meeting documentation.

Out of scope for V1 baseline:
- Native integrations with online meeting platforms (for example Teams or Zoom plugins)
- Cloud sync as a mandatory runtime path
- Web dashboard as a required core interface

## 4) High-Level Architecture

AYE Hear follows an offline desktop architecture with local ML services and local persistence.

Logical layers:

1. Presentation layer
- PySide6-based Windows desktop UI
- Meeting controls, live state view, correction workflows, export triggers

2. Orchestration and application logic
- Meeting lifecycle control (start, run, finalize)
- Coordination between audio, diarization, transcription, protocol engine, and persistence

3. Audio and ML processing pipeline
- Audio capture via Windows-compatible stack
- Voice activity detection and segmentation
- Speaker embedding / matching with confidence scoring
- Local speech-to-text transcription
- Local protocol extraction logic

4. Persistence and artifact layer
- Local PostgreSQL storage for meetings, speakers, transcript/protocol entities
- Local runtime artifacts and export files (for example Markdown/DOCX/PDF)

5. Packaging and runtime environment
- Windows installer/distribution workflow
- Runtime bootstrap and migration handling

## 5) Core Technical Building Blocks

Technology orientation (current architecture baseline):

- GUI: PySide6 (Qt6)
- Runtime language: Python 3.11+
- Audio capture: WASAPI-compatible path
- Voice activity handling: local VAD pipeline
- Speaker processing: local embeddings and similarity matching
- Speech-to-text: Faster-Whisper (local)
- Protocol intelligence: local LLM runtime pattern (Ollama-based architecture intent)
- Persistence: PostgreSQL (local deployment model)
- Export: Markdown, DOCX, PDF support in product architecture

## 6) End-to-End Functional Flow

Typical flow:

1. Meeting setup
- User sets meeting metadata and participants.
- Audio source is selected/validated.

2. Speaker enrollment (pre-meeting path)
- Participants provide short voice samples.
- System stores local voice references.

3. Live meeting processing
- Audio is captured continuously.
- Segments are diarized and transcribed.
- Speaker labels are assigned with confidence values.
- Protocol structure is incrementally updated.

4. Review and correction
- User reviews uncertain attributions.
- Manual correction is available before finalization.

5. Finalization and export
- Final protocol is approved.
- Artifacts are exported and retained locally.

## 7) Privacy and Security Model

Design assumptions:

- Offline-first is a hard architectural principle.
- Data ownership stays with the local operator.
- Sensitive meeting data should not require external transmission.

Security-relevant controls in architecture intent:

- Confidence scoring and manual override for speaker attribution
- Local persistence boundaries and retention controls
- Governance and change tracking through ADRs and quality gates

## 8) Governance and Decision Framework

AYE Hear is run with explicit architecture governance.

Authoritative governance mechanisms:

- ADR series in docs/adr/
- Product baseline in docs/PRODUCT_FOUNDATION.md
- Workflow and quality gate definitions in docs/governance/

Important principle:
- Significant architecture changes should be documented via ADR updates before implementation rollout.

## 9) Repository Structure (Conceptual)

Main areas used by external contributors and AI systems:

- src/
- Application code, UI, services, models, storage

- tests/
- Automated test coverage for behavior and regressions

- config/
- Runtime defaults and environment-specific configuration

- docs/
- Product foundation, architecture decisions, governance, release evidence

- build/ and deployment-evidence/
- Packaging records and operational validation artifacts

## 10) How an External AI System Should Work with This Project

Recommended working method:

1. Start with product and architecture authority
- Read docs/PRODUCT_FOUNDATION.md
- Read docs/adr/README.md and relevant ADRs

2. Respect hard constraints
- Preserve offline-first behavior
- Avoid introducing cloud-only runtime dependencies
- Keep speaker confidence and manual correction paths intact

3. Align with governance
- Propose design changes with explicit rationale
- Map technical changes to existing ADR principles
- Keep tests and quality gates in scope

4. Treat privacy as first-order requirement
- Prefer local processing and local storage paths
- Avoid any feature that silently externalizes meeting data

## 11) Short Glossary

- Offline-first: Core product behavior does not depend on external services.
- Speaker enrollment: Pre-meeting voice sample capture for later attribution.
- Diarization: Segmentation and speaker turn detection in audio.
- Protocol engine: Logic that transforms transcript streams into structured meeting outcomes.
- ADR: Architecture Decision Record used for governance and traceability.

## 12) Source References

Primary references for this briefing:

- docs/PRODUCT_FOUNDATION.md
- docs/adr/README.md
- docs/adr/0001-ayehear-product-architecture.md
- docs/adr/0002-windows-desktop-app-stack.md
- README.md
