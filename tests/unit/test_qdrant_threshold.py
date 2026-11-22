"""Selección determinista del umbral con criterios fijados."""

from secguard_advisor.retrieval.calibration import choose_threshold


def test_separated_scores_choose_the_highest_valid_threshold() -> None:
    choice = choose_threshold([0.72, 0.81, 0.67], [0.12, 0.31, 0.44])

    assert choice.satisfied
    assert choice.threshold == 0.67
    assert choice.missed_relevant == 0
    assert choice.accepted_non_relevant == 0
    assert choice.relevant_min == 0.67
    assert choice.non_relevant_max == 0.44


def test_overlap_records_failure_instead_of_inventing_success() -> None:
    choice = choose_threshold([0.60, 0.70], [0.55, 0.75])

    assert not choice.satisfied
    assert choice.missed_relevant >= 0
    assert choice.accepted_non_relevant >= 0


def test_empty_inputs_are_not_a_valid_calibration() -> None:
    choice = choose_threshold([], [])

    assert not choice.satisfied
    assert choice.threshold == 0.0
