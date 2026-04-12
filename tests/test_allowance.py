"""Tests for allowance.py — allowable range search.

Test cases follow test-design.md section 7.
"""

import math

import pytest

from src.allowance import (
    find_all_conditional_allowances,
    find_all_standalone_allowances,
    find_allowable_range,
)
from src.models import (
    AxisUncertainty,
    EvaluationPoint,
    MarginProtocol,
    SetupState,
    UncertaintyModel,
)


def _uniform_unc(val: float) -> UncertaintyModel:
    au = AxisUncertainty(u_identify=val)
    return UncertaintyModel(x=au, y=au, z=au)


class TestStandaloneAllowance:
    """A-1, A-2, A-4, A-6."""

    def test_a1_translation_symmetric(self):
        """A-1: Pure translation, symmetric allowance.

        C_x = |lateral| + z*U_x ≤ M_x
        |lateral| ≤ M_x - z*U_x = 10 - 2*1 = 8
        → allowable: [-8, +8]
        """
        points = [EvaluationPoint("p", 0, 0, 100)]
        margin = MarginProtocol(m_x=10.0, m_y=10.0, m_z=10.0)
        unc = _uniform_unc(1.0)

        result = find_allowable_range(
            "lateral", SetupState.zero(), points, margin, unc, 2.0
        )

        assert result.status == "within"
        assert abs(result.allowable_min - (-8.0)) < 0.02
        assert abs(result.allowable_max - 8.0) < 0.02

    def test_a2_rotation_allowance(self):
        """A-2: Rotation allowance for point on x-axis.

        Point at [100, 0, 0]. Rotation (z-axis) causes y-displacement.
        C_y = |100*sin(θ)| + z*U_y ≤ M_y
        100*sin(θ) ≤ 10 - 2*1 = 8
        sin(θ) ≤ 0.08 → θ ≤ arcsin(0.08) ≈ 4.588°
        """
        points = [EvaluationPoint("p", 100, 0, 0)]
        margin = MarginProtocol(m_x=10.0, m_y=10.0, m_z=10.0)
        unc = _uniform_unc(1.0)

        result = find_allowable_range(
            "rotation", SetupState.zero(), points, margin, unc, 2.0
        )

        expected_max = math.degrees(math.asin(0.08))  # ≈ 4.588°
        assert result.status == "within"
        assert abs(result.allowable_max - expected_max) < 0.01

    def test_a4_no_points(self):
        """A-4: No evaluation points → no_points status."""
        margin = MarginProtocol(m_x=10.0, m_y=10.0, m_z=10.0)
        result = find_allowable_range(
            "lateral", SetupState.zero(), [], margin, _uniform_unc(1.0), 2.0
        )

        assert result.status == "no_points"

    def test_a6_precision(self):
        """A-6: Verify precision matches tolerance (0.01mm for translation)."""
        points = [EvaluationPoint("p", 0, 0, 100)]
        margin = MarginProtocol(m_x=10.0, m_y=10.0, m_z=10.0)
        unc = _uniform_unc(1.0)

        result = find_allowable_range(
            "lateral", SetupState.zero(), points, margin, unc, 2.0
        )

        # Theoretical: ±8.0 mm
        assert abs(result.allowable_max - 8.0) <= 0.01
        assert abs(result.allowable_min - (-8.0)) <= 0.01


class TestConditionalAllowance:
    """A-3, A-5."""

    def test_a3_already_fail(self):
        """A-3: Current state already fails → exceeded."""
        points = [EvaluationPoint("p", 0, 0, 100)]
        margin = MarginProtocol(m_x=10.0, m_y=10.0, m_z=5.0)
        unc = _uniform_unc(1.0)
        state = SetupState(vertical=10.0)  # C_z = 10 + 2 = 12 > 5

        result = find_allowable_range(
            "vertical", state, points, margin, unc, 2.0
        )

        assert result.status == "exceeded"
        assert result.allowable_min == 10.0
        assert result.allowable_max == 10.0
        assert result.remaining_negative == 0.0
        assert result.remaining_positive == 0.0

    def test_a5_conditional_narrower_with_rotation(self):
        """A-5: With non-zero rotation, conditional allowance is narrower than standalone.

        When rotation is present, it already consumes margin at distant points,
        so the remaining allowance for translation is smaller.
        """
        points = [EvaluationPoint("p", 100, 0, 0)]
        margin = MarginProtocol(m_x=10.0, m_y=10.0, m_z=10.0)
        unc = _uniform_unc(1.0)

        # Standalone (zero_based): rotation=0
        standalone = find_allowable_range(
            "lateral", SetupState.zero(), points, margin, unc, 2.0
        )

        # Conditional: rotation=3° already present (consumes some margin)
        state_with_rot = SetupState(rotation=3.0)
        conditional = find_allowable_range(
            "lateral", state_with_rot, points, margin, unc, 2.0
        )

        # Conditional range should be narrower or equal (rotation adds displacement)
        standalone_width = standalone.allowable_max - standalone.allowable_min
        conditional_width = conditional.allowable_max - conditional.allowable_min
        assert conditional_width <= standalone_width + 0.02  # small tolerance


class TestAllAxes:

    def test_all_conditional(self):
        """find_all_conditional_allowances returns 6 results."""
        points = [EvaluationPoint("p", 50, 50, 50)]
        margin = MarginProtocol(m_x=10.0, m_y=10.0, m_z=10.0)
        state = SetupState()

        results = find_all_conditional_allowances(state, points, margin, _uniform_unc(1.0), 2.0)
        assert len(results) == 6
        axis_names = [r.axis_name for r in results]
        assert "vertical" in axis_names
        assert "rotation" in axis_names

    def test_all_standalone_zero(self):
        """find_all_standalone_allowances with zero_based returns 6 results."""
        points = [EvaluationPoint("p", 50, 50, 50)]
        margin = MarginProtocol(m_x=10.0, m_y=10.0, m_z=10.0)

        results = find_all_standalone_allowances(
            SetupState.zero(), points, margin, _uniform_unc(1.0), 2.0
        )
        assert len(results) == 6
        for r in results:
            assert r.status == "within"
