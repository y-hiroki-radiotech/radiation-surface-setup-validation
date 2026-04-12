"""Tests for decision.py — Pass/Fail judgment and worst point extraction.

Test cases follow test-design.md sections 6, 8.
"""

import math

import pytest

from src.decision import find_worst_axis, find_worst_point, is_pass, judge_all
from src.models import (
    AxisUncertainty,
    EvaluationPoint,
    MarginProtocol,
    PointResult,
    SetupState,
    UncertaintyModel,
)


def _zero_unc() -> UncertaintyModel:
    return UncertaintyModel()


def _uniform_unc(val: float) -> UncertaintyModel:
    au = AxisUncertainty(u_identify=val)
    return UncertaintyModel(x=au, y=au, z=au)


class TestJudgment:
    """D-1 through D-5."""

    def test_d1_clear_pass(self):
        """D-1: C < M → Pass."""
        state = SetupState(lateral=5.0)
        points = [EvaluationPoint("a", 0, 0, 0)]
        margin = MarginProtocol(m_x=10.0, m_y=10.0, m_z=10.0)
        results = judge_all(state, points, margin, _zero_unc(), 0.0)

        assert results[0].overall_pass_fail is True
        assert results[0].margin_remaining_mm[0] == 5.0  # 10 - 5
        assert results[0].margin_consumption_ratio[0] == 0.5

    def test_d2_clear_fail(self):
        """D-2: C > M → Fail."""
        state = SetupState(lateral=12.0)
        points = [EvaluationPoint("a", 0, 0, 0)]
        margin = MarginProtocol(m_x=10.0, m_y=10.0, m_z=10.0)
        results = judge_all(state, points, margin, _zero_unc(), 0.0)

        assert results[0].axiswise_pass_fail[0] is False
        assert results[0].overall_pass_fail is False

    def test_d3_boundary_pass(self):
        """D-3: C == M → Pass (boundary is inclusive)."""
        state = SetupState(lateral=10.0)
        points = [EvaluationPoint("a", 0, 0, 0)]
        margin = MarginProtocol(m_x=10.0, m_y=10.0, m_z=10.0)
        results = judge_all(state, points, margin, _zero_unc(), 0.0)

        assert results[0].axiswise_pass_fail[0] is True

    def test_d4_boundary_exceed(self):
        """D-4: C slightly > M → Fail."""
        state = SetupState(lateral=10.001)
        points = [EvaluationPoint("a", 0, 0, 0)]
        margin = MarginProtocol(m_x=10.0, m_y=10.0, m_z=10.0)
        results = judge_all(state, points, margin, _zero_unc(), 0.0)

        assert results[0].axiswise_pass_fail[0] is False

    def test_d5_zero_margin(self):
        """D-5: M=0, any C>0 → Fail, Q=inf."""
        state = SetupState()
        points = [EvaluationPoint("a", 0, 0, 0)]
        margin = MarginProtocol(m_x=0.0, m_y=10.0, m_z=10.0)
        unc = _uniform_unc(1.0)
        results = judge_all(state, points, margin, unc, 1.0)

        assert results[0].axiswise_pass_fail[0] is False
        assert results[0].margin_consumption_ratio[0] == math.inf

    def test_zero_margin_zero_displacement_stays_consistent(self):
        """Zero margin with zero conservative displacement stays on the pass boundary."""
        state = SetupState()
        points = [EvaluationPoint("a", 0, 0, 0)]
        margin = MarginProtocol(m_x=0.0, m_y=10.0, m_z=10.0)
        results = judge_all(state, points, margin, _zero_unc(), 0.0)

        assert results[0].axiswise_pass_fail[0] is True
        assert results[0].margin_consumption_ratio[0] == 0.0


class TestWorstPoint:
    """D-6 through D-8."""

    def test_d6_worst_extraction(self):
        """D-6: Correct worst point and axis."""
        # Create PointResults directly for targeted testing
        pr_a = PointResult(
            point_name="A", distance_from_iso_mm=100,
            displacement=(0, 0, 0), translation_contribution=(0, 0, 0),
            rotation_contribution=(0, 0, 0),
            effective_displacement_3d_mm=0, translation_only_mm=0, rotation_induced_mm=0,
            uncertainty_mm=(0, 0, 0), conservative_displacement_mm=(5, 6, 7),
            margin_remaining_mm=(5, 4, 3),
            axiswise_pass_fail=(True, True, True), overall_pass_fail=True,
            margin_consumption_ratio=(0.5, 0.6, 0.7),
        )
        pr_b = PointResult(
            point_name="B", distance_from_iso_mm=80,
            displacement=(0, 0, 0), translation_contribution=(0, 0, 0),
            rotation_contribution=(0, 0, 0),
            effective_displacement_3d_mm=0, translation_only_mm=0, rotation_induced_mm=0,
            uncertainty_mm=(0, 0, 0), conservative_displacement_mm=(3, 9, 4),
            margin_remaining_mm=(7, 1, 6),
            axiswise_pass_fail=(True, True, True), overall_pass_fail=True,
            margin_consumption_ratio=(0.3, 0.9, 0.4),
        )
        pr_c = PointResult(
            point_name="C", distance_from_iso_mm=60,
            displacement=(0, 0, 0), translation_contribution=(0, 0, 0),
            rotation_contribution=(0, 0, 0),
            effective_displacement_3d_mm=0, translation_only_mm=0, rotation_induced_mm=0,
            uncertainty_mm=(0, 0, 0), conservative_displacement_mm=(8, 2, 3),
            margin_remaining_mm=(2, 8, 7),
            axiswise_pass_fail=(True, True, True), overall_pass_fail=True,
            margin_consumption_ratio=(0.8, 0.2, 0.3),
        )

        results = [pr_a, pr_b, pr_c]
        worst = find_worst_point(results)
        assert worst.point_name == "B"  # max Q = 0.9

        axis = find_worst_axis(results)
        assert axis == "y"  # B's y-axis has Q=0.9

    def test_d7_all_pass(self):
        """D-7: All points pass → overall pass."""
        state = SetupState(lateral=1.0)
        points = [
            EvaluationPoint("a", 0, 0, 0),
            EvaluationPoint("b", 10, 0, 0),
            EvaluationPoint("c", 0, 10, 0),
        ]
        margin = MarginProtocol(m_x=10.0, m_y=10.0, m_z=10.0)
        results = judge_all(state, points, margin, _zero_unc(), 0.0)

        assert is_pass(results) is True

    def test_d8_one_fail(self):
        """D-8: One point fails → overall fail."""
        state = SetupState(lateral=12.0)
        points = [
            EvaluationPoint("ok", 0, 0, 0),
            EvaluationPoint("fail", 0, 0, 0),
        ]
        margin = MarginProtocol(m_x=10.0, m_y=10.0, m_z=10.0)
        results = judge_all(state, points, margin, _zero_unc(), 0.0)

        assert is_pass(results) is False

    def test_no_points(self):
        """No evaluation points → None."""
        results = judge_all(SetupState(), [], MarginProtocol(10, 10, 10), _zero_unc(), 0)
        assert is_pass(results) is None


class TestScenarios:
    """S-1 through S-4 from test-design.md section 8."""

    def test_s1_translation_only(self):
        """S-1: Translation only, zero uncertainty."""
        state = SetupState(vertical=3.0, longitudinal=2.0, lateral=1.0)
        points = [EvaluationPoint("p", 50, 80, 120)]
        margin = MarginProtocol(m_x=10, m_y=10, m_z=10)
        results = judge_all(state, points, margin, _zero_unc(), 0.0)

        pr = results[0]
        assert abs(pr.displacement[0] - 1.0) < 1e-6
        assert abs(pr.displacement[1] - 2.0) < 1e-6
        assert abs(pr.displacement[2] - 3.0) < 1e-6
        assert pr.overall_pass_fail is True

    def test_s3_uncertainty_causes_fail(self):
        """S-3: Zero displacement but uncertainty causes fail."""
        state = SetupState()
        points = [EvaluationPoint("p", 0, 0, 100)]
        margin = MarginProtocol(m_x=10, m_y=10, m_z=3.0)
        unc = _uniform_unc(2.0)
        results = judge_all(state, points, margin, unc, 2.0)

        pr = results[0]
        # C_z = 0 + 2.0 * 2.0 = 4.0 > 3.0
        assert pr.axiswise_pass_fail[2] is False
        assert pr.overall_pass_fail is False

    def test_s4_margin_boundary_pass(self):
        """S-4: Exactly at margin boundary → Pass."""
        state = SetupState(lateral=5.0)
        points = [EvaluationPoint("p", 0, 0, 100)]
        margin = MarginProtocol(m_x=8.0, m_y=10, m_z=10)
        unc = UncertaintyModel(
            x=AxisUncertainty(u_identify=1.5),
            y=AxisUncertainty(),
            z=AxisUncertainty(),
        )
        results = judge_all(state, points, margin, unc, 2.0)

        pr = results[0]
        # C_x = 5.0 + 2.0 * 1.5 = 8.0 == M_x = 8.0 → Pass
        assert pr.axiswise_pass_fail[0] is True
