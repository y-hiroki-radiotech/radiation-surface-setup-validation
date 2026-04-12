"""Pass/Fail judgment, worst point extraction, and constraint identification.

Formulas follow math-design.md sections 16-18.
Algorithm follows algorithm-design.md sections 6-7.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from .geometry import build_rotation_matrix, build_translation_vector
from .models import (
    EvaluationPoint,
    MarginProtocol,
    PointResult,
    SetupState,
    UncertaintyModel,
)
from .uncertainty import (
    conservative_displacement,
    margin_consumption_ratio,
    margin_remaining,
)


def evaluate_point(
    state: SetupState,
    point: EvaluationPoint,
    margin: MarginProtocol,
    uncertainty: UncertaintyModel,
    z: float,
    R: np.ndarray,
    T: np.ndarray,
) -> PointResult:
    """Evaluate a single point against margins.

    R and T are pre-computed and shared across all points for efficiency.
    """
    p = np.array([point.x, point.y, point.z])
    R_minus_I = R - np.eye(3)

    # Displacement (math-design 8.2)
    rot_contrib = R_minus_I @ p
    disp = T + rot_contrib

    # Norms (math-design 9.3-9.4)
    eff_3d = float(np.linalg.norm(disp))
    trans_only = float(np.linalg.norm(T))
    rot_induced = float(np.linalg.norm(rot_contrib))

    # Uncertainty (axis-wise RSS)
    u = uncertainty.totals  # (U_x, U_y, U_z)
    margins = (margin.m_x, margin.m_y, margin.m_z)

    # Per-axis conservative displacement, remaining, ratio, pass/fail
    cons = tuple(
        conservative_displacement(abs(disp[k]), u[k], z) for k in range(3)
    )
    rem = tuple(margin_remaining(cons[k], margins[k]) for k in range(3))
    ratio = tuple(
        margin_consumption_ratio(cons[k], margins[k]) for k in range(3)
    )
    axis_pf = tuple(bool(cons[k] <= margins[k]) for k in range(3))

    return PointResult(
        point_name=point.name,
        distance_from_iso_mm=point.distance_from_iso,
        displacement=(float(disp[0]), float(disp[1]), float(disp[2])),
        translation_contribution=(float(T[0]), float(T[1]), float(T[2])),
        rotation_contribution=(
            float(rot_contrib[0]),
            float(rot_contrib[1]),
            float(rot_contrib[2]),
        ),
        effective_displacement_3d_mm=eff_3d,
        translation_only_mm=trans_only,
        rotation_induced_mm=rot_induced,
        uncertainty_mm=u,
        conservative_displacement_mm=cons,
        margin_remaining_mm=rem,
        axiswise_pass_fail=axis_pf,
        overall_pass_fail=all(axis_pf),
        margin_consumption_ratio=ratio,
    )


def judge_all(
    state: SetupState,
    points: list[EvaluationPoint],
    margin: MarginProtocol,
    uncertainty: UncertaintyModel,
    z: float,
) -> list[PointResult]:
    """Evaluate all points. algorithm-design section 6.4."""
    if not points:
        return []

    R = build_rotation_matrix(state.rotation, state.pitch, state.roll)
    T = build_translation_vector(state)

    return [
        evaluate_point(state, pt, margin, uncertainty, z, R, T) for pt in points
    ]


def find_worst_point(results: list[PointResult]) -> Optional[PointResult]:
    """Find the point with the highest margin consumption.

    worst = argmax_i max(Q_i,x, Q_i,y, Q_i,z).  math-design section 18.
    """
    if not results:
        return None

    worst = results[0]
    worst_q = max(worst.margin_consumption_ratio)

    for pr in results[1:]:
        q = max(pr.margin_consumption_ratio)
        if q > worst_q:
            worst = pr
            worst_q = q

    return worst


def find_worst_axis(results: list[PointResult]) -> str:
    """Find the axis with the highest Q across all points.

    math-design section 17.3.  Returns axis label: "x", "y", or "z".
    """
    axis_labels = ("x", "y", "z")
    best_axis = "x"
    best_q = -math.inf

    for pr in results:
        for k, label in enumerate(axis_labels):
            if pr.margin_consumption_ratio[k] > best_q:
                best_q = pr.margin_consumption_ratio[k]
                best_axis = label

    return best_axis


def is_pass(results: list[PointResult]) -> Optional[bool]:
    """Overall pass/fail.  None if no points. math-design section 16.3."""
    if not results:
        return None
    return all(pr.overall_pass_fail for pr in results)
