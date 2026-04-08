#!/usr/bin/env pwsh
<#
.SYNOPSIS
    AYE Hear Phase 1 Architecture Task Batch — Quick Importer
    
.DESCRIPTION
    Imports all 5 architecture foundational tasks (HEAR-001 through HEAR-005) 
    into Task-CLI system for AYEHEAR_ARCHITECT.
    
    Minimum requirements:
    - PowerShell 5.1+ (Windows)
    - Task-CLI loaded: Import-Module 'G:\Repo\platform-tools\tools\task-cli\task-cli.psd1' -Force
    
.EXAMPLE
    # Run from G:\Repo\aye-hear
    & .\tools\scripts\Import-HEAR-Phase1-Architecture-Batch.ps1
    
.AUTHOR
    AYEHEAR_ARCHITECT
    
.DATE
    2026-04-08
#>

[CmdletBinding(SupportsShouldProcess)]
param(
    [switch]$DryRun,
    [switch]$NoVerify
)

# ============================================================================
# PHASE 0: VALIDATION
# ============================================================================

Write-Host "╔════════════════════════════════════════════════════════════════════╗"
Write-Host "║ AYE Hear Phase 1 Architecture — Task Batch Import Utility          ║"
Write-Host "║ Batch ID: hear-phase1-architecture                                 ║"
Write-Host "║ Created: 2026-04-08                                                ║"
Write-Host "╚════════════════════════════════════════════════════════════════════╝"
Write-Host ""

# Validate location
$repoRoot = Get-Location
if (-not (Test-Path "$repoRoot\.git")) {
    Write-Error "❌ Not in an AYE Hear git repository. Ensure you're in G:\Repo\aye-hear"
    exit 1
}

Write-Host "📍 Repository: $repoRoot"
Write-Host "✓ Git repository detected"
Write-Host ""

# Validate Task-CLI
try {
    $null = Get-Command Get-Task -ErrorAction Stop
    Write-Host "✓ Task-CLI module loaded"
}
catch {
    Write-Host "⚠️  Task-CLI not found. Attempting to load..."
    Import-Module 'G:\Repo\platform-tools\tools\task-cli\task-cli.psd1' -Force -ErrorAction Stop | Out-Null
    Write-Host "✓ Task-CLI loaded"
}

Write-Host ""

# ============================================================================
# PHASE 1: DEFINE ARCHITECTURE BATCH TASKS
# ============================================================================

Write-Host "📋 Defining 5 Architecture Foundation Tasks..."
Write-Host ""

$architectureBatch = @(
    @{
        Title       = "ADR Ratification: 0001-0005"
        Role        = "AYEHEAR_ARCHITECT"
        Priority    = "high"
        Type        = "TASK"
        StoryPoints = 5
        Description = @"
Review and formally ratify all 5 core ADRs (0001-0005):
- ADR-0001: Product Architecture (offline-first, Windows desktop, no cloud)
- ADR-0002: Windows Desktop App Stack (PySide6, Python, PostgreSQL, Ollama)
- ADR-0003: Speaker Identification (confidence scoring, manual override)
- ADR-0004: Audio Capture & Preprocessing (WASAPI, 16 kHz, Silero VAD)
- ADR-0005: Meeting Protocol Engine (LLM, aggregation, drafting)

Validate: structure, PostgreSQL-only mandate, offline-first alignment, observability requirements, cross-references.
Update docs/adr/README.md index with all 5 ADRs marked as "Accepted".

AC: All 5 ADRs reviewed, no conflicting DB fallback mentions, index updated, pnpm docs:validate passes.
"@
    },
    @{
        Title       = "PostgreSQL Runtime Decision on Windows"
        Role        = "AYEHEAR_ARCHITECT"
        Priority    = "high"
        Type        = "TASK"
        StoryPoints = 8
        Description = @"
Make explicit architectural decision on PostgreSQL deployment for local Windows development and production.

Decision Options:
1. Bundled PostgreSQL (simplest, largest installer)
2. Managed Service Prerequisite (smallest installer, highest user friction)
3. Installer-Managed Setup (moderate complexity, good UX)
4. Container-Assisted (dev-only Docker/Podman, production uses 1-3)

Evaluate: user friction, installer size, offline-first viability, dev environment requirements, multi-OS support.

Create ADR-0006 documenting decision, include deployment topology diagram and PostgreSQL version lock (e.g., 16+).
Decision unblocks AYEHEAR_DEVELOPER persistence implementation.

AC: ADR-0006 Accepted, deployment model chosen, topology diagram included, PG version lock decided, docs/adr/README.md updated.
"@
    },
    @{
        Title       = "Persistence Contract & Schema Approval"
        Role        = "AYEHEAR_ARCHITECT"
        Priority    = "high"
        Type        = "TASK"
        StoryPoints = 8
        Description = @"
Define and approve canonical persistence contract for PostgreSQL schema.

Canonical Entities:
1. meetings — Session metadata, timestamps, title, participant list
2. participants — Speaker profiles enrolled in meeting
3. speaker_profiles — Persistent speaker embeddings (768-dim pgvector) + metadata
4. transcript_segments — Recognized speech (speaker_id, time, text, confidence)
5. protocol_snapshots — Timestamped protocol revisions (content, LLM used)
6. protocol_action_items — Extracted action items (description, assignee, status, due_date)

Create docs/architecture/PERSISTENCE_CONTRACT.md with:
- Entity-relationship diagram (Mermaid/text)
- SQL data types, constraints, indexes
- pgvector strategy for speaker embeddings
- Lifecycle flow (meeting creation → enrollment → transcription → protocol)
- PII handling + encryption justification

AYEHEAR_SECURITY must review before implementation.

AC: Contract doc created, ER diagram, all 6 entities defined, pgvector usage documented, SECURITY review complete, no hardcoded secrets.
"@
    },
    @{
        Title       = "System Boundary Definition"
        Role        = "AYEHEAR_ARCHITECT"
        Priority    = "high"
        Type        = "TASK"
        StoryPoints = 8
        Description = @"
Define clear subsystem boundaries and service contracts.

Subsystems:
1. Audio Pipeline — Capture (WASAPI) → Preprocessing (16kHz, VAD) → Transcription (Whisper)
2. Speaker Identification — Enrollment → Similarity Matching (pgvector) → Diarization
3. Meeting Protocol Engine — Transcript aggregation → LLM (Ollama) → Action extraction → Drafting
4. UI Shell & Storage Facade — Qt UI → Storage adapter (PostgreSQL) → Orchestration

Define: service-to-service communication (sync/async, queue/direct), data ownership per service, error handling & fallback, threading model, config passing.

Create docs/architecture/SYSTEM_BOUNDARIES.md with component architecture diagram, inter-service contracts (signatures, error types), thread safety per subsystem, testing boundaries.

AC: Boundaries doc, 4 subsystems defined, service patterns specified, data ownership clear, error handling documented, component diagram included, QA has test isolation strategy.
"@
    },
    @{
        Title       = "Implementation Order & Developer Roadmap"
        Role        = "AYEHEAR_ARCHITECT"
        Priority    = "high"
        Type        = "TASK"
        StoryPoints = 5
        Description = @"
Based on decisions from HEAR-001 through HEAR-004, define canonical implementation order.

Implementation Sequence (10 steps):
1. PostgreSQL Connection Module
2. ORM Models (Speaker, Meeting, TranscriptSegment, ProtocolSnapshot, ActionItem)
3. Storage Layer (PostgreSQLStore data access layer)
4. Audio Capture Service (real WASAPI integration, testing harness)
5. Speaker Enrollment Flow (UI + persistence)
6. Transcription Integration (Whisper → storage)
7. Diarization & Speaker Matching (pyannote + pgvector queries)
8. Protocol Engine (LLM drafting → storage)
9. UI Completion (transcript review, corrections, protocol editing)
10. End-to-End Testing (full meeting lifecycle)

Dependency Constraints: Tasks 1-3 must complete before 4-8 start. Tasks 4-9 can run parallel where possible.

Create docs/governance/HEAR_DEVELOPER_ROADMAP.md with:
- All 10 implementation blocks
- Clear dependency mapping
- Per-block acceptance criteria
- Parallelization opportunities
- Risk assessment for critical paths
- Estimated critical path timeline

AC: Roadmap created, dependencies mapped, parallelization identified, risks documented, Phase 1B tasks prepared, all subsystems have clear next tasks.
"@
    }
)

# ============================================================================
# PHASE 2: DISPLAY TASK SUMMARY
# ============================================================================

Write-Host "📊 Task Summary:"
Write-Host ""
$architectureBatch | ForEach-Object {
    $taskNum = $architectureBatch.IndexOf($_) + 1
    Write-Host "  [$taskNum/5] $($_.Title)"
    Write-Host "        Role: $($_.Role) | Priority: $($_.Priority) | SP: $($_.StoryPoints)"
    Write-Host ""
}

# ============================================================================
# PHASE 3: IMPORT OR DRY-RUN
# ============================================================================

if ($DryRun) {
    Write-Host "🔍 DRY-RUN MODE: Tasks not created (preview only)"
    Write-Host ""
    Write-Host "This would create:"
    Write-Host "  - Batch ID: hear-phase1-architecture"
    Write-Host "  - Created By: AYEHEAR_ARCHITECT"
    Write-Host "  - Task Count: 5"
    Write-Host "  - Total Story Points: 34 (5+8+8+8+5)"
    Write-Host ""
    Write-Host "To import for real, run without -DryRun flag:"
    Write-Host "  & .\Import-HEAR-Phase1-Architecture-Batch.ps1"
    exit 0
}

Write-Host "📤 Creating Task Batch in Task-CLI..."
Write-Host ""

try {
    $result = New-TaskBatch -Tasks $architectureBatch `
        -BatchId "hear-phase1-architecture" `
        -CreatedByRole "AYEHEAR_ARCHITECT" `
        -ErrorAction Stop

    if ($result) {
        Write-Host "✓ Batch Created:"
        Write-Host "  - Batch ID: hear-phase1-architecture"
        Write-Host "  - Tasks Created: $($result.Count)"
        Write-Host ""
    }
}
catch {
    Write-Error "❌ Failed to create task batch: $_"
    exit 1
}

# ============================================================================
# PHASE 4: VERIFICATION
# ============================================================================

if (-not $NoVerify) {
    Write-Host "🔍 Verifying Task Creation..."
    Write-Host ""
    
    $createdTasks = @()
    1..5 | ForEach-Object {
        $taskId = "HEAR-$('{0:D3}' -f $_)"
        try {
            $task = Get-Task -Id $taskId -ErrorAction SilentlyContinue
            if ($task) {
                $createdTasks += $task
                Write-Host "  ✓ $taskId created (Status: $($task.Status))"
            }
            else {
                Write-Host "  ⚠️  $taskId not found (may take a moment to sync)"
            }
        }
        catch {
            Write-Host "  ⚠️  $taskId verification skipped"
        }
    }
    
    Write-Host ""
}

# ============================================================================
# PHASE 5: NEXT STEPS
# ============================================================================

Write-Host "✨ Import Complete!"
Write-Host ""
Write-Host "📌 Next Steps for AYEHEAR_ARCHITECT:"
Write-Host ""
Write-Host "1. Verify tasks in Task-CLI:"
Write-Host "   Get-Task -Role AYEHEAR_ARCHITECT -Status OPEN | Format-Table Id, Title"
Write-Host ""
Write-Host "2. Start HEAR-001 (ADR Ratification):"
Write-Host "   Start-Task -Id HEAR-001 -Force"
Write-Host ""
Write-Host "3. Follow the 8-Phase Workflow in each task (see HEAR_PHASE1_TASKPAKET_AKTIVIERUNGSANLEITUNG.md)"
Write-Host ""
Write-Host "4. Complete tasks in dependency order:"
Write-Host "   HEAR-001 ↓"
Write-Host "   ├─ HEAR-002 (PostgreSQL Runtime)"
Write-Host "   ├─ HEAR-003 (Persistence Contract)"
Write-Host "   ├─ HEAR-004 (System Boundaries)"
Write-Host "   └──→ HEAR-005 (Roadmap — final gate)"
Write-Host ""
Write-Host "💡 Parallel Opportunities: HEAR-002, 003, 004 can run after HEAR-001"
Write-Host ""
Write-Host "📚 Reference Documentation:"
Write-Host "  - docs/governance/HEAR_PHASE1_ARCHITECTURE_TASKBATCH.md (full specs)"
Write-Host "  - docs/governance/HEAR_PHASE1_TASKPAKET_AKTIVIERUNGSANLEITUNG.md (German guide)"
Write-Host "  - docs/governance/AYEHEAR_ARCHITECT_HANDOFF.md (architect handoff)"
Write-Host "  - docs/adr/README.md (all ADRs)"
Write-Host ""
Write-Host "═════════════════════════════════════════════════════════════════════"
Write-Host "Batch Ready: hear-phase1-architecture ✓"
Write-Host "═════════════════════════════════════════════════════════════════════"
