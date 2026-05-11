"""Meeting ROI Score calculator (V2-04, HEAR-175).

Deterministic, offline-only. No LLM or external service required.

Score formula (three equally-weighted components, each 0–33 points, max 100):

Komponente 1 — Entscheidungsqualität (0–33 Punkte):
    decisions = snapshot_content.get("decisions", [])
    0 decisions  → 0 Punkte
    1–2          → 15 Punkte
    3–5          → 25 Punkte
    6+           → 33 Punkte

Komponente 2 — Action-Item-Qualität (0–33 Punkte):
    action_items = snapshot_content.get("action_items", [])
    For each item: +1 if owner name detectable (Colon-split or Capitalised word before colon),
                   +1 if due date pattern (\\d{1,2}\\.\\d{1,2}) present.
    score = (sum_points / max_possible_points) * 33  (capped)
    0 action items → 0 Punkte

Komponente 3 — Vollständigkeit des Protokolls (0–33 Punkte):
    Sections checked: summary, decisions, action_items, open_questions, next_steps
    Each non-empty section: +6 Punkte (max 30) + 3 bonus if all five sections present = 33

Total: int(k1 + k2 + k3), capped at 100.
"""
from __future__ import annotations

import re

# Pattern: date in German notation, e.g. "3.4." or "15.12." or "01.12.2026"
_DATE_PATTERN = re.compile(r"\b\d{1,2}\.\d{1,2}")

# Pattern: word starting with uppercase (potential name) followed by colon
_OWNER_PATTERN = re.compile(r"\b[A-ZÄÖÜ][a-zäöüß]+.*?:")


def _component_decisions(decisions: list[str]) -> tuple[int, list[str], list[str]]:
    """Return (score, positive_drivers, negative_drivers) for decision quality."""
    n = len(decisions)
    if n == 0:
        return 0, [], ["Keine Entscheidungen getroffen"]
    elif n <= 2:
        return 15, [f"{n} Entscheidung{'en' if n > 1 else ''} getroffen"], []
    elif n <= 5:
        return 25, [f"{n} Entscheidungen getroffen"], []
    else:
        return 33, [f"{n} Entscheidungen getroffen"], []


def _component_action_items(action_items: list[str]) -> tuple[int, list[str], list[str]]:
    """Return (score, positive_drivers, negative_drivers) for action-item quality."""
    if not action_items:
        return 0, [], ["Keine Aufgaben erfasst"]

    total_possible = len(action_items) * 2
    earned = 0
    has_all_owners = True
    has_all_dates = True

    for item in action_items:
        has_owner = bool(_OWNER_PATTERN.search(item)) or (":" in item)
        has_date = bool(_DATE_PATTERN.search(item))
        if has_owner:
            earned += 1
        else:
            has_all_owners = False
        if has_date:
            earned += 1
        else:
            has_all_dates = False

    ratio = earned / total_possible if total_possible > 0 else 0
    score = int(round(ratio * 33))

    positives: list[str] = []
    negatives: list[str] = []

    if has_all_owners:
        positives.append("Alle Aufgaben haben Verantwortliche")
    else:
        negatives.append("Nicht alle Aufgaben haben Verantwortliche")

    if has_all_dates:
        positives.append("Alle Aufgaben haben Fälligkeitsdaten")
    else:
        negatives.append("Keine Aufgaben mit Fälligkeitsdatum")

    return score, positives, negatives


def _component_completeness(content: dict) -> tuple[int, list[str], list[str]]:
    """Return (score, positive_drivers, negative_drivers) for protocol completeness."""
    sections = {
        "summary": content.get("summary", []),
        "decisions": content.get("decisions", []),
        "action_items": content.get("action_items", []),
        "open_questions": content.get("open_questions", []),
        "next_steps": content.get("next_steps", []),
    }

    _LABELS = {
        "summary": "Zusammenfassung",
        "decisions": "Entscheidungen",
        "action_items": "Aufgaben",
        "open_questions": "Offene Punkte",
        "next_steps": "Nächste Schritte",
    }

    filled = [k for k, v in sections.items() if v]
    n_filled = len(filled)

    score = min(n_filled * 6, 30)
    if n_filled == 5:
        score = 33

    positives: list[str] = []
    negatives: list[str] = []

    if n_filled == 5:
        positives.append("Alle Protokollabschnitte befüllt")
    elif n_filled >= 3:
        positives.append(f"{n_filled} von 5 Protokollabschnitten befüllt")

    empty = [k for k, v in sections.items() if not v]
    for k in empty:
        negatives.append(f"{_LABELS[k]} fehlt")

    return score, positives, negatives


def calculate_roi_score(snapshot_content: dict) -> dict:
    """Return score dict with keys: score, drivers_positive, drivers_negative, components.

    Parameters
    ----------
    snapshot_content:
        dict with optional keys: summary, decisions, action_items, open_questions, next_steps.
        Each value is expected to be a list[str]. Missing keys default to empty list.

    Returns
    -------
    dict with:
        score (int): 0–100
        drivers_positive (list[str]): top positive drivers (up to 3)
        drivers_negative (list[str]): top negative drivers (up to 3)
        components (dict): {decisions: int, action_items: int, completeness: int}
    """
    if not isinstance(snapshot_content, dict):
        snapshot_content = {}

    decisions = snapshot_content.get("decisions") or []
    action_items = snapshot_content.get("action_items") or []

    k1, pos1, neg1 = _component_decisions(decisions)
    k2, pos2, neg2 = _component_action_items(action_items)
    k3, pos3, neg3 = _component_completeness(snapshot_content)

    total = min(int(k1 + k2 + k3), 100)

    all_positives = pos1 + pos2 + pos3
    all_negatives = neg1 + neg2 + neg3

    return {
        "score": total,
        "drivers_positive": all_positives[:3],
        "drivers_negative": all_negatives[:3],
        "components": {
            "decisions": k1,
            "action_items": k2,
            "completeness": k3,
        },
    }
