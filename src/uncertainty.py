"""Uncertainty composition and conservative displacement computation.

Formulas follow math-design.md sections 12, 14.
"""

from __future__ import annotations

import math

from .models import AxisUncertainty, UncertaintyModel


def compute_axis_uncertainty(axis_unc: AxisUncertainty) -> float:
    """RSS combination for a single axis. math-design section 12.4."""
    return axis_unc.total


def compute_all_uncertainties(model: UncertaintyModel) -> tuple[float, float, float]:
    """RSS uncertainties for all three axes (x, y, z)."""
    return model.totals


def conservative_displacement(
    abs_displacement_k: float,
    uncertainty_k: float,
    z: float,
) -> float:
    """C_i,k = |Δp_i,k| + z * U_k. math-design section 14.1.

    Note: abs_displacement_k should already be abs() of the displacement component.
    """
    return abs_displacement_k + z * uncertainty_k


def margin_remaining(conservative_k: float, margin_k: float) -> float:
    """R_i,k = M_k - C_i,k. math-design section 17.1."""
    return margin_k - conservative_k


def margin_consumption_ratio(conservative_k: float, margin_k: float) -> float:
    """Q_i,k = C_i,k / M_k. math-design section 17.2.

    Returns 0 when both conservative displacement and margin are zero, and inf
    when the margin is zero but conservative displacement is non-zero.
    """
    if margin_k == 0.0:
        if conservative_k == 0.0:
            return 0.0
        return math.inf
    return conservative_k / margin_k
