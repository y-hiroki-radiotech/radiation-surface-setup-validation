"""Allowable range search via bisection.

Implements standalone and conditional allowance search.
Algorithm follows algorithm-design.md sections 8-9 and math-design.md sections 19-21.
"""

from __future__ import annotations

from .decision import find_worst_axis, find_worst_point, is_pass, judge_all
from .models import (
    ROTATION_AXES,
    TRANSLATION_AXES,
    AxisAllowance,
    EvaluationPoint,
    MarginProtocol,
    SetupState,
    UncertaintyModel,
)

# Search range defaults (math-design 21.2)
TRANSLATION_SEARCH_MIN = -50.0  # mm
TRANSLATION_SEARCH_MAX = 50.0   # mm
ROTATION_SEARCH_MIN = -10.0     # deg
ROTATION_SEARCH_MAX = 10.0      # deg

# Coarse step sizes (algorithm-design 8.4)
TRANSLATION_COARSE_STEP = 0.5   # mm
ROTATION_COARSE_STEP = 0.1      # deg

# Bisection tolerances (math-design 21.4)
TRANSLATION_TOLERANCE = 0.01    # mm
ROTATION_TOLERANCE = 0.001      # deg

# Safety limit on bisection iterations
MAX_BISECT_ITERATIONS = 50


def _get_search_params(axis: str) -> tuple[float, float, float, float]:
    """Return (search_min, search_max, coarse_step, tolerance) for an axis."""
    if axis in TRANSLATION_AXES:
        return (
            TRANSLATION_SEARCH_MIN,
            TRANSLATION_SEARCH_MAX,
            TRANSLATION_COARSE_STEP,
            TRANSLATION_TOLERANCE,
        )
    return (
        ROTATION_SEARCH_MIN,
        ROTATION_SEARCH_MAX,
        ROTATION_COARSE_STEP,
        ROTATION_TOLERANCE,
    )


def _validate_search_origin(axis: str, current_value: float, search_min: float, search_max: float) -> None:
    """Reject a base value that lies outside the supported search domain."""
    if search_min <= current_value <= search_max:
        return

    raise ValueError(
        f"{axis}={current_value} is outside the supported search range "
        f"[{search_min}, {search_max}]"
    )


def _test_pass(
    axis: str,
    value: float,
    base_state: SetupState,
    points: list[EvaluationPoint],
    margin: MarginProtocol,
    uncertainty: UncertaintyModel,
    z: float,
) -> bool:
    """Test whether setting axis=value (other axes from base_state) gives Pass."""
    test_state = base_state.with_axis(axis, value)
    results = judge_all(test_state, points, margin, uncertainty, z)
    return is_pass(results) is True


def _find_limiting_info(
    axis: str,
    value: float,
    base_state: SetupState,
    points: list[EvaluationPoint],
    margin: MarginProtocol,
    uncertainty: UncertaintyModel,
    z: float,
) -> tuple[str, str]:
    """Find the limiting point and axis at a given boundary value."""
    test_state = base_state.with_axis(axis, value)
    results = judge_all(test_state, points, margin, uncertainty, z)
    wp = find_worst_point(results)
    wa = find_worst_axis(results)
    return (wp.point_name if wp else "", wa)


def _bisect(
    axis: str,
    u_pass: float,
    u_fail: float,
    base_state: SetupState,
    points: list[EvaluationPoint],
    margin: MarginProtocol,
    uncertainty: UncertaintyModel,
    z: float,
    tolerance: float,
) -> float:
    """Bisection search between a Pass value and a Fail value.

    Returns the Pass-side boundary. algorithm-design section 8.5.
    """
    for _ in range(MAX_BISECT_ITERATIONS):
        if abs(u_pass - u_fail) <= tolerance:
            break
        u_mid = (u_pass + u_fail) / 2.0
        if _test_pass(axis, u_mid, base_state, points, margin, uncertainty, z):
            u_pass = u_mid
        else:
            u_fail = u_mid
    return u_pass


def _search_boundary(
    axis: str,
    start: float,
    limit: float,
    step: float,
    base_state: SetupState,
    points: list[EvaluationPoint],
    margin: MarginProtocol,
    uncertainty: UncertaintyModel,
    z: float,
    tolerance: float,
) -> float | None:
    """Coarse search from start toward limit, then bisect at the Pass→Fail boundary.

    Returns the boundary value (Pass side), or None if the entire range is Pass.
    """
    prev = start
    current = start + step

    # Walk toward the limit
    while (step > 0 and current <= limit) or (step < 0 and current >= limit):
        if not _test_pass(axis, current, base_state, points, margin, uncertainty, z):
            # Found Pass→Fail transition between prev and current
            return _bisect(
                axis, prev, current, base_state, points, margin, uncertainty, z, tolerance
            )
        prev = current
        current += step

    # Check the limit itself
    if not _test_pass(axis, limit, base_state, points, margin, uncertainty, z):
        return _bisect(
            axis, prev, limit, base_state, points, margin, uncertainty, z, tolerance
        )

    # Entire range is Pass
    return None


def find_allowable_range(
    axis: str,
    base_state: SetupState,
    points: list[EvaluationPoint],
    margin: MarginProtocol,
    uncertainty: UncertaintyModel,
    z: float,
) -> AxisAllowance:
    """Find the allowable range for one axis, holding other axes at base_state.

    Used for both conditional allowance (base=current) and standalone allowance
    (base=reference).  algorithm-design sections 8-9.
    """
    search_min, search_max, coarse_step, tolerance = _get_search_params(axis)
    current_value = base_state.get_axis(axis)
    _validate_search_origin(axis, current_value, search_min, search_max)

    # Edge case: no evaluation points
    if not points:
        return AxisAllowance(
            axis_name=axis,
            current_value=current_value,
            allowable_min=search_min,
            allowable_max=search_max,
            remaining_negative=current_value - search_min,
            remaining_positive=search_max - current_value,
            limiting_point="",
            limiting_axis="",
            status="no_points",
        )

    # Check if current state already fails
    if not _test_pass(axis, current_value, base_state, points, margin, uncertainty, z):
        lp, la = _find_limiting_info(
            axis, current_value, base_state, points, margin, uncertainty, z
        )
        return AxisAllowance(
            axis_name=axis,
            current_value=current_value,
            allowable_min=current_value,
            allowable_max=current_value,
            remaining_negative=0.0,
            remaining_positive=0.0,
            limiting_point=lp,
            limiting_axis=la,
            status="exceeded",
        )

    # Search positive direction
    boundary_pos = _search_boundary(
        axis, current_value, search_max, coarse_step, base_state,
        points, margin, uncertainty, z, tolerance,
    )
    allowable_max = boundary_pos if boundary_pos is not None else search_max

    # Search negative direction
    boundary_neg = _search_boundary(
        axis, current_value, search_min, -coarse_step, base_state,
        points, margin, uncertainty, z, tolerance,
    )
    allowable_min = boundary_neg if boundary_neg is not None else search_min

    # Find limiting info at the tighter boundary
    tighter_side = allowable_max if (allowable_max - current_value) <= (current_value - allowable_min) else allowable_min
    lp, la = _find_limiting_info(
        axis, tighter_side, base_state, points, margin, uncertainty, z
    )

    return AxisAllowance(
        axis_name=axis,
        current_value=current_value,
        allowable_min=allowable_min,
        allowable_max=allowable_max,
        remaining_negative=current_value - allowable_min,
        remaining_positive=allowable_max - current_value,
        limiting_point=lp,
        limiting_axis=la,
        status="within",
    )


def find_all_conditional_allowances(
    state: SetupState,
    points: list[EvaluationPoint],
    margin: MarginProtocol,
    uncertainty: UncertaintyModel,
    z: float,
) -> list[AxisAllowance]:
    """Conditional allowances for all 6 axes. math-design section 20."""
    from .models import AXIS_NAMES
    return [
        find_allowable_range(axis, state, points, margin, uncertainty, z)
        for axis in AXIS_NAMES
    ]


def find_all_standalone_allowances(
    reference_state: SetupState,
    points: list[EvaluationPoint],
    margin: MarginProtocol,
    uncertainty: UncertaintyModel,
    z: float,
) -> list[AxisAllowance]:
    """Standalone allowances for all 6 axes. math-design section 19.

    reference_state determines the fixed values for the other 5 axes.
    For zero_based mode, pass SetupState.zero().
    For current_based mode, pass the current SetupState.
    For custom mode, pass the user-specified SetupState.
    """
    from .models import AXIS_NAMES
    return [
        find_allowable_range(axis, reference_state, points, margin, uncertainty, z)
        for axis in AXIS_NAMES
    ]
