"""Tests for HEAR-069: Replace Stub Speaker Embedding with Production Backend (B2).

Covers:
- No deterministic stub in production path (_embed_mfcc replaces the old formula)
- MFCC-based embedding is non-trivial (not zeros, not identical for different inputs)
- Same audio produces identical embedding (deterministic for same input, as expected)
- Different audio samples produce meaningfully different embeddings
- Empty audio returns zero vector
- Result is always 768-dim unit vector
- Confidence classification thresholds remain ADR-aligned (unchanged)
- Unknown Speaker fallback semantics preserved
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from ayehear.services.speaker_manager import (
    HIGH_CONFIDENCE_THRESHOLD,
    MEDIUM_CONFIDENCE_THRESHOLD,
    SpeakerManager,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SR = 16_000  # 16 kHz


def _sine_wave(freq_hz: float, duration_s: float = 1.0, amplitude: float = 0.5) -> list[float]:
    """Generate a pure sine wave as a list of float32 samples."""
    t = np.linspace(0, duration_s, int(_SR * duration_s), endpoint=False)
    return (amplitude * np.sin(2 * np.pi * freq_hz * t)).astype(np.float32).tolist()


def _noise(duration_s: float = 1.0, seed: int = 42) -> list[float]:
    """Gaussian noise with a fixed seed."""
    rng = np.random.default_rng(seed)
    return rng.standard_normal(int(_SR * duration_s)).astype(np.float32).tolist()


# ---------------------------------------------------------------------------
# Structural guarantees
# ---------------------------------------------------------------------------


def test_extract_embedding_returns_768_dims_for_normal_audio() -> None:
    audio = _sine_wave(440.0)
    vec = SpeakerManager._extract_embedding(audio)
    assert len(vec) == 768


def test_extract_embedding_returns_768_dims_for_empty_audio() -> None:
    vec = SpeakerManager._extract_embedding([])
    assert len(vec) == 768


def test_extract_embedding_empty_audio_is_all_zeros() -> None:
    vec = SpeakerManager._extract_embedding([])
    assert all(v == 0.0 for v in vec)


def test_extract_embedding_result_is_unit_vector_for_speech_like_audio() -> None:
    """Non-trivial audio must produce a unit-norm embedding."""
    audio = _noise(duration_s=0.5)
    vec = SpeakerManager._extract_embedding(audio)
    norm = math.sqrt(sum(v * v for v in vec))
    assert abs(norm - 1.0) < 1e-5, f"Expected unit vector, got norm={norm:.6f}"


def test_extract_embedding_returns_float_list() -> None:
    audio = _sine_wave(200.0, duration_s=0.3)
    vec = SpeakerManager._extract_embedding(audio)
    assert isinstance(vec, list)
    assert all(isinstance(v, float) for v in vec)


# ---------------------------------------------------------------------------
# Non-determinism: different audio must produce different embeddings
# ---------------------------------------------------------------------------


def test_different_audio_produces_different_embeddings() -> None:
    """MFCC embedding must differ for spectrally different inputs (not a stub)."""
    audio_low = _sine_wave(200.0)   # 200 Hz sine
    audio_high = _sine_wave(4000.0)  # 4 kHz sine

    vec_low = SpeakerManager._extract_embedding(audio_low)
    vec_high = SpeakerManager._extract_embedding(audio_high)

    similarity = sum(a * b for a, b in zip(vec_low, vec_high))
    # Two spectrally very different signals must have cosine similarity < 0.99
    assert similarity < 0.99, (
        f"Embeddings for 200 Hz and 4000 Hz sine are too similar (cos={similarity:.4f}); "
        "this suggests the embedding is not reflecting real spectral content."
    )


def test_same_audio_produces_identical_embedding() -> None:
    """Identical audio samples must yield bit-identical embeddings (determinism for same input)."""
    audio = _noise(duration_s=1.0, seed=7)
    vec1 = SpeakerManager._extract_embedding(audio)
    vec2 = SpeakerManager._extract_embedding(audio)
    assert vec1 == vec2


def test_noise_and_silence_produce_different_embeddings() -> None:
    silence = [0.0] * _SR
    noise = _noise(duration_s=1.0, seed=13)

    vec_silence = SpeakerManager._extract_embedding(silence)
    vec_noise = SpeakerManager._extract_embedding(noise)

    # Silence and noise have different spectral profiles
    if all(v == 0.0 for v in vec_silence):
        # Silence returned zero vector — noise must be non-zero
        assert any(v != 0.0 for v in vec_noise)
    else:
        similarity = sum(a * b for a, b in zip(vec_silence, vec_noise))
        assert similarity < 0.99


# ---------------------------------------------------------------------------
# No deterministic stub formula
# ---------------------------------------------------------------------------


def test_embedding_not_based_on_audio_mean() -> None:
    """The old stub computed vec[i] = (mean + i*0.001) % 1.0.  Verify this formula is gone."""
    # Audio with known mean = 0.5
    audio = [0.5] * _SR
    vec = SpeakerManager._extract_embedding(audio)

    # Old stub would produce deterministic values based on mean alone.
    # Two different audios with the same mean but different spectra must differ.
    audio_shifted = [0.5 + 0.001 * math.sin(2 * math.pi * i / 100) for i in range(_SR)]
    vec_shifted = SpeakerManager._extract_embedding(audio_shifted)

    # They have the same mean (approx.) but different spectral content.
    same_mean_audio_1 = [0.5] * _SR
    same_mean_audio_2 = _sine_wave(440.0, duration_s=1.0, amplitude=0.5)
    # Adjust mean of audio_2 to 0.5
    arr2 = np.array(same_mean_audio_2, dtype=np.float32)
    arr2 = arr2 - arr2.mean() + 0.5
    same_mean_audio_2_adj = arr2.tolist()

    v1 = SpeakerManager._extract_embedding(same_mean_audio_1)
    v2 = SpeakerManager._extract_embedding(same_mean_audio_2_adj)

    similarity = sum(a * b for a, b in zip(v1, v2))
    assert similarity < 0.999, (
        "Embeddings with same mean but different spectra should differ. "
        "This suggests the deterministic stub is still active."
    )


# ---------------------------------------------------------------------------
# ADR-0003 confidence thresholds (must remain unchanged after B2)
# ---------------------------------------------------------------------------


def test_score_match_thresholds_unchanged_high() -> None:
    sm = SpeakerManager()
    result = sm.score_match("Speaker A", HIGH_CONFIDENCE_THRESHOLD)
    assert result.status == "high"
    assert result.requires_review is False


def test_score_match_thresholds_unchanged_medium() -> None:
    sm = SpeakerManager()
    result = sm.score_match("Speaker A", 0.75)
    assert result.status == "medium"
    assert result.requires_review is True


def test_score_match_thresholds_unchanged_low() -> None:
    sm = SpeakerManager()
    result = sm.score_match("Speaker A", 0.50)
    assert result.status == "low"
    assert result.speaker_name == "Unknown Speaker"
    assert result.requires_review is True


def test_score_match_boundary_at_medium_threshold() -> None:
    sm = SpeakerManager()
    result = sm.score_match("Speaker A", MEDIUM_CONFIDENCE_THRESHOLD)
    assert result.status == "medium"


# ---------------------------------------------------------------------------
# Unknown Speaker fallback (no profiles registered)
# ---------------------------------------------------------------------------


def test_match_segment_returns_unknown_when_no_profiles() -> None:
    """Without enrolled profiles, match_segment must return Unknown Speaker."""
    sm = SpeakerManager()
    audio = _noise(duration_s=0.5)
    embedding = SpeakerManager._extract_embedding(audio)
    result = sm.match_segment(embedding)
    assert result.speaker_name == "Unknown Speaker"
    assert result.status == "low"
    assert result.requires_review is True


def test_enroll_with_mfcc_embedding_produces_768_dim_profile() -> None:
    """Enrolling with real MFCC embedding must produce a 768-dim profile."""
    sm = SpeakerManager()  # no repos — offline path
    audio = _noise(duration_s=1.0, seed=99)
    result = sm.enroll("p-001", "Speaker Test", audio)
    assert result.success is True
    assert result.embedding_dim == 768


def test_two_different_enrollments_use_different_embeddings() -> None:
    """Two different audio samples enrolled under different names must differ."""
    sm = SpeakerManager()
    audio_a = _sine_wave(300.0)
    audio_b = _sine_wave(3000.0)
    emb_a = SpeakerManager._extract_embedding(audio_a)
    emb_b = SpeakerManager._extract_embedding(audio_b)
    # Cosine similarity < 0.99 (spectrally distinct)
    sim = sum(a * b for a, b in zip(emb_a, emb_b))
    assert sim < 0.99


# ---------------------------------------------------------------------------
# embed_mfcc direct tests
# ---------------------------------------------------------------------------


def test_embed_mfcc_returns_768_dim() -> None:
    audio = _noise(duration_s=0.25, seed=1)
    vec = SpeakerManager._embed_mfcc(audio)
    assert len(vec) == 768


def test_embed_mfcc_is_unit_vector() -> None:
    audio = _sine_wave(1000.0, duration_s=0.5)
    vec = SpeakerManager._embed_mfcc(audio)
    norm = math.sqrt(sum(v * v for v in vec))
    assert abs(norm - 1.0) < 1e-5


def test_embed_mfcc_empty_returns_zeros() -> None:
    vec = SpeakerManager._embed_mfcc([])
    assert len(vec) == 768
    assert all(v == 0.0 for v in vec)


def test_embed_mfcc_very_short_audio_does_not_crash() -> None:
    """Audio shorter than one frame must be handled gracefully."""
    vec = SpeakerManager._embed_mfcc([0.1] * 50)
    assert len(vec) == 768
