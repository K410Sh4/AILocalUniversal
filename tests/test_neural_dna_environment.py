# Copyright © 2026 K410Sh4. All rights reserved.
# SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary

import math

import pytest

from neural_dna.environment import CueCalibration, CueEvidence, ReactionNorm


def train(calibration, predicted, realized, count):
    for _ in range(count):
        calibration = calibration.observe(CueEvidence(predicted, realized))
    return calibration


def test_no_evidence_uses_conservative_plasticity_and_reserve():
    result = ReactionNorm().express(CueCalibration(), 1.0)
    assert result.plasticity == 0.1
    assert result.diversity_reserve == 0.8
    assert result.signed_evidence == 0.0


def test_reliable_cue_increases_plasticity_and_reduces_reserve():
    calibration = train(CueCalibration(), "wet", "wet", 30)
    result = ReactionNorm().express(calibration, 0.8)
    assert result.plasticity > 0.8
    assert result.diversity_reserve < 0.2


def test_unreliable_cue_does_not_drive_plasticity():
    calibration = train(CueCalibration(), "wet", "dry", 30)
    result = ReactionNorm().express(calibration, 0.8)
    assert result.plasticity == 0.1
    assert result.diversity_reserve > 0.6


def test_low_volatility_does_not_overallocate_diversity():
    result = ReactionNorm().express(CueCalibration(), 0.0)
    assert result.diversity_reserve == 0.05


def test_forgetting_adapts_after_cue_reliability_reverses():
    calibration = train(CueCalibration(retention=0.98), "wet", "wet", 30)
    before = ReactionNorm().express(calibration, 0.8)
    calibration = train(calibration, "wet", "dry", 60)
    after = ReactionNorm().express(calibration, 0.8)
    assert before.plasticity > 0.8
    assert after.plasticity == 0.1
    assert after.diversity_reserve > before.diversity_reserve


def test_full_retention_freezes_old_evidence():
    calibration = train(CueCalibration(retention=1.0), "a", "a", 10)
    after = train(calibration, "a", "b", 10)
    assert after.reliability == 0.5


@pytest.mark.parametrize("bad", [-0.1, 1.1, math.nan, math.inf, -math.inf])
def test_reaction_norm_rejects_invalid_volatility(bad):
    with pytest.raises(ValueError):
        ReactionNorm().express(CueCalibration(), bad)


@pytest.mark.parametrize("bad", [-1.0, math.nan, math.inf])
def test_calibration_rejects_invalid_evidence_counts(bad):
    with pytest.raises(ValueError):
        CueCalibration(successes=bad)


def test_calibration_confidence_grows_with_evidence():
    empty = CueCalibration()
    trained = train(empty, "x", "x", 20)
    assert trained.confidence > empty.confidence


def test_reaction_expression_is_bounded():
    calibration = train(CueCalibration(), "x", "x", 100)
    result = ReactionNorm().express(calibration, 1.0)
    assert 0 <= result.plasticity <= 1
    assert 0 <= result.diversity_reserve <= 1
