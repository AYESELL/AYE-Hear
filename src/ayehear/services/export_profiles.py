"""Persona Export Profiles (V2-03, HEAR-177).

Controls which protocol sections are included per target audience.
"""
from __future__ import annotations

from dataclasses import dataclass

PROFILE_CEO = "ceo"
PROFILE_OPS = "ops"
PROFILE_TEAM = "team"
PROFILE_COMPLIANCE = "compliance"

PROFILE_LABELS = {
    PROFILE_CEO: "Kurzfassung (Führungsebene)",
    PROFILE_OPS: "Operativ (Vollprotokoll)",
    PROFILE_TEAM: "Team-Protokoll",
    PROFILE_COMPLIANCE: "Compliance-Export",
}


@dataclass(frozen=True)
class ExportProfile:
    id: str
    label: str
    include_score: bool = True
    include_summary: bool = True
    include_decisions: bool = True
    include_action_items: bool = True
    include_open_questions: bool = True
    include_next_steps: bool = True
    include_risk_table: bool = True
    include_task_table: bool = True
    include_ai_disclaimer: bool = True
    include_offline_attestation: bool = False
    include_compliance_note: bool = False
    max_decisions: int | None = None
    risk_filter: str | None = None


_PROFILES: dict[str, ExportProfile] = {
    PROFILE_CEO: ExportProfile(
        id=PROFILE_CEO,
        label=PROFILE_LABELS[PROFILE_CEO],
        include_score=True,
        include_summary=False,
        include_decisions=True,
        include_action_items=False,
        include_open_questions=False,
        include_next_steps=False,
        include_risk_table=True,
        include_task_table=False,
        include_ai_disclaimer=False,
        include_offline_attestation=False,
        max_decisions=5,
        risk_filter="high",
    ),
    PROFILE_OPS: ExportProfile(
        id=PROFILE_OPS,
        label=PROFILE_LABELS[PROFILE_OPS],
        include_score=True,
        include_summary=True,
        include_decisions=True,
        include_action_items=True,
        include_open_questions=True,
        include_next_steps=True,
        include_risk_table=True,
        include_task_table=True,
        include_ai_disclaimer=True,
        include_offline_attestation=True,
        include_compliance_note=False,
    ),
    PROFILE_TEAM: ExportProfile(
        id=PROFILE_TEAM,
        label=PROFILE_LABELS[PROFILE_TEAM],
        include_score=False,
        include_summary=True,
        include_decisions=False,
        include_action_items=True,
        include_open_questions=True,
        include_next_steps=True,
        include_risk_table=False,
        include_task_table=True,
        include_ai_disclaimer=False,
        include_offline_attestation=False,
        include_compliance_note=False,
    ),
    PROFILE_COMPLIANCE: ExportProfile(
        id=PROFILE_COMPLIANCE,
        label=PROFILE_LABELS[PROFILE_COMPLIANCE],
        include_score=False,
        include_summary=True,
        include_decisions=True,
        include_action_items=True,
        include_open_questions=True,
        include_next_steps=True,
        include_risk_table=True,
        include_task_table=True,
        include_ai_disclaimer=True,
        include_offline_attestation=True,
        include_compliance_note=True,
    ),
}


def get_profile(profile_id: str) -> ExportProfile:
    """Return profile by ID. Defaults to ops if unknown."""
    if not profile_id:
        return _PROFILES[PROFILE_OPS]
    return _PROFILES.get(profile_id, _PROFILES[PROFILE_OPS])
