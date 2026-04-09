"""Speaker enrollment, profile matching and diarization pipeline (HEAR-012/014).

Implements the two-stage pipeline from ADR-0003:
  Stage 1: Voice enrollment (pre-meeting) — extracts 768-dim embeddings.
  Stage 2: Diarization + identification (during recording) — segment matching.

Confidence classification (ADR-0003):
  >= 0.85 -> high    (auto-assigned, no review required)
  0.65-0.84 -> medium (queued for manual review / uncertain)
  < 0.65 -> low     (marked 'Unknown Speaker', mandatory correction)
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ayehear.storage.repositories import (
        ParticipantRepository,
        SpeakerProfileRepository,
    )

import logging

logger = logging.getLogger(__name__)

# ADR-0003 cosine similarity thresholds
HIGH_CONFIDENCE_THRESHOLD: float = 0.85
MEDIUM_CONFIDENCE_THRESHOLD: float = 0.65


@dataclass(slots=True)
class SpeakerMatch:
    speaker_name: str
    confidence: float
    status: str
    profile_id: str | None = None
    requires_review: bool = False


@dataclass
class EnrollmentResult:
    participant_id: str
    display_name: str
    profile_id: str
    embedding_dim: int
    success: bool
    error: str | None = None


class SpeakerManager:
    """Manages speaker profiles and implements ADR-0003 pipeline logic.

    The class is intentionally decoupled from the storage layer so it can
    be tested without a database connection (pass None as repos in unit tests).
    """

    def __init__(
        self,
        high_confidence_threshold: float = 0.85,
        medium_confidence_threshold: float = 0.65,
        profile_repo: "SpeakerProfileRepository | None" = None,
        participant_repo: "ParticipantRepository | None" = None,
    ) -> None:
        self.high_confidence_threshold = high_confidence_threshold
        self.medium_confidence_threshold = medium_confidence_threshold
        self._profiles = profile_repo
        self._participants = participant_repo

    # ------------------------------------------------------------------
    # Stage 1: Enrollment (HEAR-012)
    # ------------------------------------------------------------------

    def enroll(
        self,
        participant_id: str,
        display_name: str,
        audio_samples: list[float],
    ) -> EnrollmentResult:
        """Extract voice embedding from samples and persist a speaker profile.

        In production, audio_samples are passed from AudioCaptureService.
        The embedding extractor is a deterministic stub until pyannote is wired.
        """
        embedding = self._extract_embedding(audio_samples)

        if self._profiles is None or self._participants is None:
            # Offline / unit-test path — no DB required
            return EnrollmentResult(
                participant_id=participant_id,
                display_name=display_name,
                profile_id="stub-profile-id",
                embedding_dim=len(embedding),
                success=True,
            )

        try:
            profile = self._profiles.upsert(
                display_name=display_name,
                embedding_vector=embedding,
                embedding_version="v1",
            )
            self._participants.mark_enrolled(participant_id, profile.id)
            logger.info("Enrolled speaker '%s' with profile %s", display_name, profile.id)
            return EnrollmentResult(
                participant_id=participant_id,
                display_name=display_name,
                profile_id=profile.id,
                embedding_dim=len(embedding),
                success=True,
            )
        except Exception as exc:
            logger.error("Enrollment failed for '%s': %s", display_name, exc)
            return EnrollmentResult(
                participant_id=participant_id,
                display_name=display_name,
                profile_id="",
                embedding_dim=0,
                success=False,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # Stage 2: Segment attribution (HEAR-014)
    # ------------------------------------------------------------------

    def score_match(self, speaker_name: str, confidence: float) -> SpeakerMatch:
        """Classify a raw cosine score per ADR-0003 thresholds.

        ADR-0003 §4: a confidence below the medium threshold must NOT result in
        a named speaker assignment — low-confidence segments are labelled
        'Unknown Speaker' and flagged for mandatory manual review.
        """
        if confidence >= self.high_confidence_threshold:
            resolved_name = speaker_name
            status = "high"
            requires_review = False
        elif confidence >= self.medium_confidence_threshold:
            resolved_name = speaker_name
            status = "medium"
            requires_review = True
        else:
            # ADR-0003: below medium threshold → no implicit speaker assignment
            resolved_name = "Unknown Speaker"
            status = "low"
            requires_review = True
        return SpeakerMatch(
            speaker_name=resolved_name,
            confidence=confidence,
            status=status,
            requires_review=requires_review,
        )

    def match_segment(self, segment_embedding: list[float]) -> SpeakerMatch:
        """Find the best enrolled speaker match for a diarized audio segment.

        Low-confidence results MUST NOT be auto-finalized (ADR-0003 §4).
        Returns 'Unknown Speaker' when no profiles are loaded or all scores
        fall below the low-confidence threshold.
        """
        if self._profiles is None:
            return SpeakerMatch(
                speaker_name="Unknown Speaker",
                confidence=0.0,
                status="low",
                requires_review=True,
            )

        profiles = self._profiles.list_all()
        best_score = 0.0
        best_profile = None

        for profile in profiles:
            if not profile.embedding_vector:
                continue
            score = self._cosine_similarity(segment_embedding, profile.embedding_vector)
            if score > best_score:
                best_score = score
                best_profile = profile

        if best_profile is None:
            return SpeakerMatch(
                speaker_name="Unknown Speaker",
                confidence=0.0,
                status="low",
                requires_review=True,
            )

        match = self.score_match(best_profile.display_name, best_score)
        match.profile_id = best_profile.id
        return match

    def match_intro_to_participant(
        self,
        introduction_text: str,
        participant_display_names: list[str],
    ) -> SpeakerMatch:
        """Match spoken self-introduction text to a known participant list.

        Used before diarization is active — e.g. during enrollment phase.
        Falls back to fuzzy string comparison when no embedding is available.
        """
        normalized_intro = self._normalize_text(introduction_text)
        if not normalized_intro or not participant_display_names:
            return self.score_match("Unknown Speaker", 0.0)

        best_name = "Unknown Speaker"
        best_score = 0.0
        intro_tokens = normalized_intro.split()

        for participant_name in participant_display_names:
            aliases = self._build_aliases(participant_name)
            for alias in aliases:
                alias_tokens = alias.split()
                if not alias_tokens:
                    continue

                token_overlap = sum(1 for token in alias_tokens if token in intro_tokens)
                overlap_score = token_overlap / len(alias_tokens)
                fuzzy_score = SequenceMatcher(None, alias, normalized_intro).ratio()
                score = max(overlap_score, fuzzy_score * 0.9)

                if score > best_score:
                    best_score = score
                    best_name = participant_name

        return self.score_match(best_name, min(best_score, 1.0))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_embedding(audio_samples: list[float]) -> list[float]:
        """Deterministic stub returning a 768-dim unit vector.

        Replace with real pyannote/SpeakerEmbedding inference in production.
        The method signature is stable so tests can mock without ML deps.
        """
        dim = 768
        if not audio_samples:
            return [0.0] * dim

        base = sum(audio_samples) / len(audio_samples)
        vec = [(base + i * 0.001) % 1.0 for i in range(dim)]
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        if len(a) != len(b) or not a:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)

    def _build_aliases(self, participant_name: str) -> list[str]:
        normalized_name = self._normalize_text(participant_name)
        parts = [part for part in normalized_name.split() if part]
        if not parts:
            return []
        aliases = {normalized_name, parts[-1]}
        if len(parts) >= 2:
            aliases.add(f"{parts[0]} {parts[-1]}")
            aliases.add(parts[0])
        return [alias for alias in aliases if alias]

    def _normalize_text(self, value: str) -> str:
        normalized = value.strip().lower()
        normalized = re.sub(r"[^a-zA-Z0-9\s]", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized
