from ayehear.services.speaker_manager import SpeakerManager


def test_speaker_match_thresholds() -> None:
    service = SpeakerManager()

    assert service.score_match("Anna", 0.9).status == "high"
    assert service.score_match("Anna", 0.7).status == "medium"
    assert service.score_match("Anna", 0.2).status == "low"
