"""Action-Item Quality Engine (HEAR-105 / V2-01).

Deterministic, offline-only evaluation of extracted action items.
Checks: owner presence, due-date presence, verb strength, measurability,
and dependency clarity.

No external model or network call is made here.  The same input always
produces the same score and the same reason labels.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

class ScoreReason(str, Enum):
    """Stable reason codes – never change these strings; UI/tests reference them."""
    MISSING_OWNER = "missing_owner"
    MISSING_DUE_DATE = "missing_due_date"
    WEAK_VERB = "weak_verb"
    LOW_MEASURABILITY = "low_measurability"
    UNCLEAR_DEPENDENCY = "unclear_dependency"


@dataclass
class ActionItemQuality:
    """Result of scoring a single action-item text."""
    score: int                               # 0-100, higher = better quality
    reasons: list[ScoreReason]               # stable codes for all quality gaps
    needs_sharpening: bool                   # True when score < SHARPENING_THRESHOLD
    hints: list[str]                         # human-readable, localised improvement hints


# ---------------------------------------------------------------------------
# Internal helpers – pattern libraries
# ---------------------------------------------------------------------------

# Owner patterns: personal pronouns, role nouns, named-person cues
_OWNER_PATTERNS_DE = re.compile(
    r"\b("
    r"ich|wir|du|er|sie|es|ihr|"
    r"team|gruppe|abteilung|bereich|"
    r"herr|frau|dr\.|prof\.|"
    r"[A-ZÄÖÜ][a-zäöüß]+ (?:wird|soll|kümmert sich|übernimmt|erstellt|prüft|sendet)"
    r")\b",
    re.IGNORECASE,
)
_OWNER_PATTERNS_EN = re.compile(
    r"\b("
    r"i|we|you|he|she|they|"
    r"team|group|department|division|"
    r"mr\.|ms\.|dr\.|"
    r"[A-Z][a-z]+ (?:will|shall|must|should|is responsible|takes care|sends|creates|checks)"
    r")\b",
    re.IGNORECASE,
)
_OWNER_PATTERNS_FR = re.compile(
    r"\b("
    r"je|nous|tu|il|elle|ils|elles|"
    r"équipe|groupe|département|"
    r"m\.|mme\.|"
    r"[A-ZÉÀÂ][a-zéàâùèê]+ (?:va|doit|devra|s'occupe|crée|vérifie)"
    r")\b",
    re.IGNORECASE,
)

# Due-date patterns (ISO dates, relative dates, weekday references)
_DUE_DATE_PATTERNS = re.compile(
    r"\b("
    r"\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}|"         # 15.04.2026 / 15-04-26
    r"\d{4}-\d{2}-\d{2}|"                            # 2026-04-15
    r"(?:bis|by|avant le|until|spätestens)\b[^.]{0,30}|"  # "bis 15. April"
    r"(?:montag|dienstag|mittwoch|donnerstag|freitag|samstag|sonntag)|"
    r"(?:monday|tuesday|wednesday|thursday|friday)|"
    r"(?:lundi|mardi|mercredi|jeudi|vendredi)|"
    r"(?:nächste (?:woche|monat)|next (?:week|month)|la semaine (?:prochaine))|"
    r"end of (?:week|month|quarter)|"
    r"(?:q[1-4]|KW\s*\d{1,2})"
    r")\b",
    re.IGNORECASE,
)

# Strong action verbs indicate executable, specific tasks
_STRONG_VERB_PATTERNS = re.compile(
    r"\b("
    # German – use verb stems so conjugated forms match (erstell\w* → erstelle/erstellt/erstellen)
    r"erstell\w*|schreib\w*|send\w*|schick\w*|prüf\w*|test\w*|implementier\w*|"
    r"deploy\w*|review\w*|freigeb\w*|genehmig\w*|kontaktier\w*|einlad\w*|"
    r"abschließ\w*|fertigstell\w*|liefer\w*|übermittel\w*|vorstell\w*|präsentier\w*|"
    # English
    r"create|write|send|check|test|implement|deploy|review|approve|contact|"
    r"invite|finalize|complete|deliver|submit|present|resolve|fix|update|"
    r"schedule|arrange|coordinate|prepare|publish|document|"
    # French
    r"créer|écrire|envoyer|vérifier|tester|implémenter|déployer|réviser|"
    r"approuver|contacter|inviter|finaliser|livrer|soumettre|présenter"
    r")\b",
    re.IGNORECASE,
)

# Weak / vague action verbs that do not specify a concrete outcome
_WEAK_VERB_PATTERNS = re.compile(
    r"\b("
    r"kümmer\w*|anseh\w*|anschau\w*|irgendwie|mach\w*|tu\w*|schau\w*|klär\w*|besprech\w*|"
    r"look into|take care|handle|do|make|talk about|discuss|figure out|"
    r"regard\w*|s'occup\w*|fair\w*|voir|discut\w*"
    r")\b",
    re.IGNORECASE,
)

# Measurability cues: numbers, KPIs, thresholds, deliverable nouns
# Note: trailing \b omitted because % is a non-word char and breaks boundary matching
_MEASURABILITY_PATTERNS = re.compile(
    r"(?:"
    r"\b\d+\s*%|"                                               # percentages: 20%
    r"\b\d+\s*(?:stück|einheiten|items|units|pièces)\b|"        # count with unit
    r"\b(?:version|v)\s*\d|"                                    # version references
    r"\b(?:report|bericht|liste|tabelle|document|dokument|ticket|issue|pr|pull request)\b|"
    r"\b(?:dashboard|prototype|prototyp|mockup|demo|poc|proof[- ]of[- ]concept)\b"
    r")",
    re.IGNORECASE,
)

# Dependency cues (only weak when the dependency target is vague)
_DEPENDENCY_VAGUE_PATTERNS = re.compile(
    r"\b("
    r"abhängig von|depends on|en fonction de"
    r")\b"
    r"(?![^.]{1,50}(?:\bteam\b|\bherr\b|\bfrau\b|\b[A-Z]\w+\b))",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Localised label/hint tables
# ---------------------------------------------------------------------------

_HINTS: dict[str, dict[ScoreReason, str]] = {
    "Deutsch": {
        ScoreReason.MISSING_OWNER: (
            "Eigentümer fehlt – wer ist verantwortlich? Namen oder Rolle ergänzen."
        ),
        ScoreReason.MISSING_DUE_DATE: (
            "Fälligkeitsdatum fehlt – bis wann soll die Aufgabe erledigt sein?"
        ),
        ScoreReason.WEAK_VERB: (
            "Schwaches Verb – konkretes Handlungsverb ergänzen "
            "(z. B. 'erstellen', 'senden', 'prüfen')."
        ),
        ScoreReason.LOW_MEASURABILITY: (
            "Ergebnis unklar – messbare Lieferleistung oder Zielgröße ergänzen."
        ),
        ScoreReason.UNCLEAR_DEPENDENCY: (
            "Abhängigkeit unklar – auf welches Team oder welche Person wird verwiesen?"
        ),
    },
    "English": {
        ScoreReason.MISSING_OWNER: (
            "Owner missing – who is responsible? Add a name or role."
        ),
        ScoreReason.MISSING_DUE_DATE: (
            "Due date missing – by when should this be completed?"
        ),
        ScoreReason.WEAK_VERB: (
            "Weak verb – use a specific action verb "
            "(e.g. 'create', 'send', 'review')."
        ),
        ScoreReason.LOW_MEASURABILITY: (
            "Unclear outcome – add a measurable deliverable or target."
        ),
        ScoreReason.UNCLEAR_DEPENDENCY: (
            "Dependency unclear – which team or person is referenced?"
        ),
    },
    "Francais": {
        ScoreReason.MISSING_OWNER: (
            "Responsable manquant – qui est en charge ? Ajouter un nom ou un rôle."
        ),
        ScoreReason.MISSING_DUE_DATE: (
            "Date limite manquante – pour quand cette tâche doit-elle être complétée ?"
        ),
        ScoreReason.WEAK_VERB: (
            "Verbe trop vague – utiliser un verbe d'action précis "
            "(ex. 'créer', 'envoyer', 'vérifier')."
        ),
        ScoreReason.LOW_MEASURABILITY: (
            "Résultat peu clair – ajouter un livrable mesurable ou un objectif chiffré."
        ),
        ScoreReason.UNCLEAR_DEPENDENCY: (
            "Dépendance floue – quelle équipe ou personne est référencée ?"
        ),
    },
}

# Score weights per dimension (must sum to 100)
_WEIGHTS: dict[ScoreReason, int] = {
    ScoreReason.MISSING_OWNER: 30,
    ScoreReason.MISSING_DUE_DATE: 20,
    ScoreReason.WEAK_VERB: 25,
    ScoreReason.LOW_MEASURABILITY: 20,
    ScoreReason.UNCLEAR_DEPENDENCY: 5,
}

SHARPENING_THRESHOLD = 75  # items below this score are flagged "needs_sharpening"


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class ActionItemQualityEngine:
    """Score individual action-item texts deterministically.

    Language controls hint localisation only; scoring semantics are identical
    across all supported languages.
    """

    def __init__(self, language: str = "Deutsch") -> None:
        self._language = language
        self._hints = _HINTS.get(language, _HINTS["Deutsch"])
        self._owner_pattern = {
            "Deutsch": _OWNER_PATTERNS_DE,
            "English": _OWNER_PATTERNS_EN,
            "Francais": _OWNER_PATTERNS_FR,
        }.get(language, _OWNER_PATTERNS_DE)

    def score(self, text: str) -> ActionItemQuality:
        """Evaluate a single action-item text.

        Returns an ActionItemQuality with a score 0-100, reason codes for
        every quality gap found, and localised sharpening hints.
        """
        reasons: list[ScoreReason] = []

        if not self._has_owner(text):
            reasons.append(ScoreReason.MISSING_OWNER)
        if not self._has_due_date(text):
            reasons.append(ScoreReason.MISSING_DUE_DATE)
        if not self._has_strong_verb(text):
            reasons.append(ScoreReason.WEAK_VERB)
        if not self._is_measurable(text):
            reasons.append(ScoreReason.LOW_MEASURABILITY)
        if self._has_unclear_dependency(text):
            reasons.append(ScoreReason.UNCLEAR_DEPENDENCY)

        # Compute score by subtracting weight for each failing check
        score = 100 - sum(_WEIGHTS[r] for r in reasons)
        score = max(0, score)

        hints = [self._hints[r] for r in reasons]
        return ActionItemQuality(
            score=score,
            reasons=reasons,
            needs_sharpening=score < SHARPENING_THRESHOLD,
            hints=hints,
        )

    def score_many(self, texts: list[str]) -> list[ActionItemQuality]:
        """Score a list of action items and return results in the same order."""
        return [self.score(t) for t in texts]

    # ------------------------------------------------------------------
    # Private check methods
    # ------------------------------------------------------------------

    def _has_owner(self, text: str) -> bool:
        return bool(self._owner_pattern.search(text))

    @staticmethod
    def _has_due_date(text: str) -> bool:
        return bool(_DUE_DATE_PATTERNS.search(text))

    @staticmethod
    def _has_strong_verb(text: str) -> bool:
        # Presence of a strong verb and no weak-verb override
        has_strong = bool(_STRONG_VERB_PATTERNS.search(text))
        has_weak = bool(_WEAK_VERB_PATTERNS.search(text))
        # Only pass when an explicit strong action verb is present.
        # A text with no verb at all (has_strong=False, has_weak=False) is also flagged.
        return has_strong

    @staticmethod
    def _is_measurable(text: str) -> bool:
        return bool(_MEASURABILITY_PATTERNS.search(text))

    @staticmethod
    def _has_unclear_dependency(text: str) -> bool:
        return bool(_DEPENDENCY_VAGUE_PATTERNS.search(text))
