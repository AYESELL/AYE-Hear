---
status: accepted
context_date: 2026-04-17
decision_owner: AYEHEAR_ARCHITECT
related_tasks: HEAR-093, HEAR-096
supersedes: null
---

# ADR-0012: Protocol Language Configuration

## Context

AYE Hear uses a local LLM (Ollama/Mistral) to generate structured meeting protocols from
live transcripts. The LLM prompt previously used English-only phrasing, causing the
generated protocol to be written in English even when the meeting was conducted in German.

A fix (commit 8483d65) hardcoded German as the only output language. This resolves the
V1 default case but is insufficient for multi-language use (international teams,
EN/FR-speaking participants).

Two configuration strategies were considered for HEAR-093:

1. **Global setting** — Language set once in `config/default.yaml`, same for all meetings.
2. **Per-meeting runtime selection** — Language chosen in the Meeting Setup panel before
   each meeting starts, stored in `RuntimeConfig` for the duration of that meeting.

## Decision

**Per-meeting runtime selection** is adopted as the V1 design.

**Rationale:**
- Language of a meeting is a meeting-level property, not an installation-level property.
  Two consecutive meetings may be in different languages.
- Setting language before the meeting start (not mid-meeting) is low complexity and
  maps naturally to the existing Meeting Setup panel pattern.
- Per-meeting selection avoids a config-file round-trip for multilingual users.
- Storing in `RuntimeConfig` (in-memory for the session) keeps the model clean:
  no database write required for this setting.

**V1 scope boundary:**
- Language **cannot** be changed after "Start Meeting" is clicked.
- No mid-meeting language switch in V1 (avoids protocol coherence issues).
- Persisting language choice per-meeting-record in the DB is deferred to V2.

## Design Contract

### RuntimeConfig extension

`ProtocolSettings` in `src/ayehear/models/runtime.py` gains one field:

```python
class ProtocolSettings(BaseModel):
    update_interval_seconds: int = 45
    minimum_confidence: float = 0.65
    meeting_modes: list[str] = Field(default_factory=lambda: ["internal", "external"])
    protocol_language: str = "de"          # NEW — per-meeting, set in UI
    supported_languages: list[str] = Field(  # NEW — informational / for UI
        default_factory=lambda: ["de", "en", "fr"]
    )
```

### UI contract

The Meeting Setup panel (`window.py`) gains a `QComboBox`:
- Label: "Protokollsprache / Protocol Language"
- Options: `Deutsch (de)`, `English (en)`, `Français (fr)`
- Default: `Deutsch (de)`
- Disabled once meeting starts (enforces no mid-meeting switch)
- On selection change: writes `RuntimeConfig.protocol.protocol_language`

### ProtocolEngine call contract

`ProtocolEngine.generate()` already holds a reference to `RuntimeConfig`.
The Ollama prompt builder reads `self._config.protocol.protocol_language` and
selects the appropriate prompt template:

| Language code | Instruction in prompt |
|---|---|
| `de` | `Antworte ausschließlich auf Deutsch.` |
| `en` | `Respond exclusively in English.` |
| `fr` | `Réponds exclusivement en français.` |

No other component receives the language setting directly.

### config/default.yaml

The default is documented but not actively read at runtime (RuntimeConfig carries it):

```yaml
protocol:
  protocol_language: de        # V1 default, DE only at install time
  supported_languages:
    - de
    - en
    - fr
```

## Alternatives Considered

| Option | Rejected reason |
|---|---|
| Global config only | Does not support per-meeting language selection |
| Store language in PostgreSQL per-meeting | Over-engineered for V1; DB write for a transient UI setting |
| Auto-detect language from transcript | Unreliable for short transcripts; deferred to V2 |
| Support mid-meeting language switch | Protocol coherence risk; deferred to V2 |

## Consequences

**Positive:**
- Developer (HEAR-093) has unambiguous contracts for model, UI, and engine layers
- German remains V1 default — no regression for existing installations
- Clean separation: language is a meeting-scoped setting, not a system setting

**Negative:**
- Language selection requires a UI control in Meeting Setup (small UI scope increase)
- No language persistence per meeting in DB until V2

## Phase-3 Gate: Architect Sign-off

HEAR-093 implementation may start after this ADR is merged.

Implementation checklist for AYEHEAR_DEVELOPER:
- [ ] `ProtocolSettings.protocol_language: str = "de"` added to `runtime.py`
- [ ] `QComboBox` added to Meeting Setup panel, wired to `RuntimeConfig`
- [ ] Combo disabled on meeting start
- [ ] `ProtocolEngine._build_prompt()` uses language from config
- [ ] `config/default.yaml` updated
- [ ] Tests: language propagates from config to prompt text (no live Ollama required)
