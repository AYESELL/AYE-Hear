"""Decision Risk Radar (V2-02, HEAR-176).

Deterministic risk scoring for protocol decisions. No LLM or external service.

Risk Rules (4 indicators, each worth 1 point):

| Indicator                | Risk Points |
|--------------------------|-------------|
| No owner detectable      | +1          |
| No due date / deadline   | +1          |
| Dependency keywords      | +1          |
| Risk/uncertainty keywords| +1          |

Traffic-light mapping:
  0       → RISK_LOW   (🟢)
  1–2     → RISK_MEDIUM (🟡)
  3–4     → RISK_HIGH  (🔴)
"""
from __future__ import annotations

import re

from ayehear.i18n import resolve_language

RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"

EMOJI_MAP = {
    RISK_LOW: "\U0001f7e2",     # 🟢
    RISK_MEDIUM: "\U0001f7e1",  # 🟡
    RISK_HIGH: "\U0001f534",    # 🔴
}

LABEL_MAP = {
    RISK_LOW: "Niedrig",
    RISK_MEDIUM: "Mittel",
    RISK_HIGH: "Hoch",
}

LABEL_MAP_BY_LANGUAGE = {
    "de": {
        RISK_LOW: "Niedrig",
        RISK_MEDIUM: "Mittel",
        RISK_HIGH: "Hoch",
    },
    "en": {
        RISK_LOW: "Low",
        RISK_MEDIUM: "Medium",
        RISK_HIGH: "High",
    },
}

# Compiled patterns – all case-insensitive
# Only context-anchored ownership signals count.
# Plain German capitalized nouns (Budget, Schnittstelle, …) are excluded
# to avoid false positives from German capitalisation rules.
_OWNER_PATTERN = re.compile(
    r"(?:"
    r"durch\s+[A-ZÄÖÜ][a-zäöüß]+"   # "durch Max" / "durch Julia"
    r"|von\s+[A-ZÄÖÜ][a-zäöüß]+"    # "von Thomas" (responsibility transfer)
    r"|[A-ZÄÖÜ][a-zäöüß]+\s*:"      # "Max:" (assignee prefix)
    r"|Verantwortlich\s*:"           # "Verantwortlich: Max"
    r"|Zuständig\s*:"                # "Zuständig: Julia"
    r")",
    re.IGNORECASE,
)

_DATE_PATTERN = re.compile(
    r"(?:"
    r"\d{1,2}\.\d{1,2}"          # DD.MM or DD.MM.YYYY
    r"|bis\s"                     # "bis " followed by anything
    r"|nächste\s+woche"
    r"|nächsten\s+\w+"
    r"|morgen"
    r"|heute"
    r")",
    re.IGNORECASE,
)

_DEPENDENCY_KEYWORDS = re.compile(
    r"\b(?:abhängig|abh[äa]ngigkeit|wenn|sobald|falls|vorausgesetzt|bedingt\s+durch)\b",
    re.IGNORECASE,
)

_RISK_KEYWORDS = re.compile(
    r"\b(?:unklar|offen|ggf\.|eventuell|möglicherweise|fraglich|unsicher|tbd|tbc)\b",
    re.IGNORECASE,
)

INDICATOR_LABELS = {
    "no_owner": "Kein Eigentümer",
    "no_date": "Kein Datum",
    "dependency": "Abhängigkeit",
    "risk_keyword": "Risikobegriff",
}

INDICATOR_LABELS_BY_LANGUAGE = {
    "de": {
        "no_owner": "Kein Eigentümer",
        "no_date": "Kein Datum",
        "dependency": "Abhängigkeit",
        "risk_keyword": "Risikobegriff",
    },
    "en": {
        "no_owner": "No owner",
        "no_date": "No date",
        "dependency": "Dependency",
        "risk_keyword": "Risk keyword",
    },
}

_INDICATOR_KEY_BY_LABEL = {
    label: key
    for lang_map in INDICATOR_LABELS_BY_LANGUAGE.values()
    for key, label in lang_map.items()
}


def get_risk_label_map(language: str | None = None) -> dict[str, str]:
    """Return a localized risk-label map keyed by risk level."""
    resolved = resolve_language(language)
    return LABEL_MAP_BY_LANGUAGE.get(resolved, LABEL_MAP_BY_LANGUAGE["de"])


def localize_indicators(indicators: list[str], language: str | None = None) -> list[str]:
    """Translate indicator labels to the requested language.

    Unknown labels are returned unchanged.
    """
    resolved = resolve_language(language)
    target = INDICATOR_LABELS_BY_LANGUAGE.get(resolved, INDICATOR_LABELS_BY_LANGUAGE["de"])

    translated: list[str] = []
    for indicator in indicators:
        key = _INDICATOR_KEY_BY_LABEL.get(indicator)
        if key is None:
            translated.append(indicator)
            continue
        translated.append(target.get(key, indicator))
    return translated


def score_decision(decision_text: str) -> dict:
    """Score a single decision text and return a risk assessment dict.

    Args:
        decision_text: Plain-text description of a decision.

    Returns:
        ``{"risk_level": str, "risk_points": int, "indicators": list[str]}``
        where ``risk_level`` is one of :data:`RISK_LOW`, :data:`RISK_MEDIUM`,
        :data:`RISK_HIGH`, ``risk_points`` is 0–4, and ``indicators`` is a
        (possibly empty) list of human-readable indicator labels.
    """
    if not decision_text or not decision_text.strip():
        return {"risk_level": RISK_LOW, "risk_points": 0, "indicators": []}

    text = decision_text.strip()
    points = 0
    indicators: list[str] = []

    if not _OWNER_PATTERN.search(text):
        points += 1
        indicators.append(INDICATOR_LABELS["no_owner"])

    if not _DATE_PATTERN.search(text):
        points += 1
        indicators.append(INDICATOR_LABELS["no_date"])

    if _DEPENDENCY_KEYWORDS.search(text):
        points += 1
        indicators.append(INDICATOR_LABELS["dependency"])

    if _RISK_KEYWORDS.search(text):
        points += 1
        indicators.append(INDICATOR_LABELS["risk_keyword"])

    if points == 0:
        level = RISK_LOW
    elif points <= 2:
        level = RISK_MEDIUM
    else:
        level = RISK_HIGH

    return {"risk_level": level, "risk_points": points, "indicators": indicators}


def get_high_risk_decisions(decisions: list[str]) -> list[dict]:
    """Return scored entries for medium and high risk decisions only.

    Args:
        decisions: List of plain-text decision strings.

    Returns:
        List of ``{"text": str, "risk_level": str, "indicators": list[str]}``
        dicts, in the same order as the input, filtered to medium/high only.
    """
    result: list[dict] = []
    for text in decisions:
        assessed = score_decision(text)
        if assessed["risk_level"] in (RISK_MEDIUM, RISK_HIGH):
            result.append(
                {
                    "text": text,
                    "risk_level": assessed["risk_level"],
                    "indicators": assessed["indicators"],
                }
            )
    return result
