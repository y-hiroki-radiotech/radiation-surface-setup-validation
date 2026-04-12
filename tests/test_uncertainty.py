"""Tests for uncertainty.py — RSS composition and conservative displacement.

Test cases follow test-design.md section 5.
"""

import math

import pytest

from src.models import AxisUncertainty, UncertaintyModel
from src.uncertainty import (
    compute_all_uncertainties,
    compute_axis_uncertainty,
    conservative_displacement,
    margin_consumption_ratio,
    margin_remaining,
)


class TestRSSComposition:
    """U-1 through U-3."""

    def test_u1_typical(self):
        """U-1: Typical RSS composition."""
        au = AxisUncertainty(
            u_identify=1.0, u_surrogate=2.0, u_registration=1.0,
            u_intrafraction=1.0, u_model=0.5,
        )
        expected = math.sqrt(1 + 4 + 1 + 1 + 0.25)  # sqrt(7.25) ≈ 2.6926
        assert abs(compute_axis_uncertainty(au) - expected) < 1e-4

    def test_u2_all_zero(self):
        """U-2: All zero → total = 0."""
        au = AxisUncertainty()
        assert compute_axis_uncertainty(au) == 0.0

    def test_u3_single_component(self):
        """U-3: Single non-zero component."""
        au = AxisUncertainty(u_identify=3.0)
        assert compute_axis_uncertainty(au) == 3.0

    def test_all_uncertainties(self):
        """compute_all_uncertainties returns tuple for 3 axes."""
        model = UncertaintyModel(
            x=AxisUncertainty(u_identify=1.0),
            y=AxisUncertainty(u_identify=2.0),
            z=AxisUncertainty(u_identify=3.0),
        )
        result = compute_all_uncertainties(model)
        assert result == (1.0, 2.0, 3.0)


class TestConservativeDisplacement:
    """U-4 through U-5."""

    def test_u4_positive(self):
        """U-4: C = |5.0| + 2.0 * 2.5 = 10.0."""
        assert conservative_displacement(5.0, 2.5, 2.0) == 10.0

    def test_u5_negative_input(self):
        """U-5: abs(-5.0) + 2.0 * 2.5 = 10.0. Note: caller must pass abs()."""
        assert conservative_displacement(5.0, 2.5, 2.0) == 10.0

    def test_zero_uncertainty(self):
        """Zero uncertainty → C = |disp|."""
        assert conservative_displacement(3.5, 0.0, 2.0) == 3.5

    def test_zero_safety_factor(self):
        """z=0 → C = |disp|."""
        assert conservative_displacement(3.5, 2.0, 0.0) == 3.5


class TestMarginMetrics:

    def test_remaining_pass(self):
        """Remaining margin when passing."""
        assert margin_remaining(5.0, 10.0) == 5.0

    def test_remaining_fail(self):
        """Negative remaining when failing."""
        assert margin_remaining(12.0, 10.0) == -2.0

    def test_ratio_normal(self):
        """Normal consumption ratio."""
        assert margin_consumption_ratio(5.0, 10.0) == 0.5

    def test_ratio_exceed(self):
        """Ratio > 1 when exceeded."""
        assert margin_consumption_ratio(12.0, 10.0) == 1.2

    def test_ratio_zero_margin(self):
        """Zero margin → inf."""
        assert margin_consumption_ratio(1.0, 0.0) == math.inf
