"""Data models for the setup margin allowance simulator.

All models follow data-model-design.md.
Coordinate system (math-design.md section 4):
  x = Lateral, y = Long, z = Vertical, origin = ISO center.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EvaluationPoint:
    """A point defined relative to ISO center for margin evaluation."""

    name: str
    x: float  # Lateral (mm)
    y: float  # Long (mm)
    z: float  # Vertical (mm)

    @property
    def distance_from_iso(self) -> float:
        """Euclidean distance from ISO center (mm). math-design section 10."""
        return math.sqrt(self.x**2 + self.y**2 + self.z**2)


@dataclass
class MarginProtocol:
    """Axis-wise setup margins (mm). math-design section 15."""

    m_x: float  # Lateral margin
    m_y: float  # Long margin
    m_z: float  # Vertical margin


@dataclass
class AxisUncertainty:
    """Uncertainty components for a single axis (mm). math-design section 12."""

    u_identify: float = 0.0
    u_surrogate: float = 0.0
    u_registration: float = 0.0
    u_intrafraction: float = 0.0
    u_model: float = 0.0

    @property
    def total(self) -> float:
        """RSS combined uncertainty. math-design section 12.4."""
        return math.sqrt(
            self.u_identify**2
            + self.u_surrogate**2
            + self.u_registration**2
            + self.u_intrafraction**2
            + self.u_model**2
        )


@dataclass
class UncertaintyModel:
    """Axis-wise uncertainty model. data-model-design section 3.4."""

    x: AxisUncertainty = field(default_factory=AxisUncertainty)  # Lateral
    y: AxisUncertainty = field(default_factory=AxisUncertainty)  # Long
    z: AxisUncertainty = field(default_factory=AxisUncertainty)  # Vertical

    @property
    def totals(self) -> tuple[float, float, float]:
        return (self.x.total, self.y.total, self.z.total)


@dataclass
class SetupState:
    """6DoF current values. math-design section 5.

    Translation units: mm.  Rotation units: deg (converted to rad internally).
    """

    vertical: float = 0.0      # z translation (mm)
    longitudinal: float = 0.0  # y translation (mm)
    lateral: float = 0.0       # x translation (mm)
    rotation: float = 0.0      # z-axis rotation (deg)
    pitch: float = 0.0         # x-axis rotation (deg)
    roll: float = 0.0          # y-axis rotation (deg)

    @classmethod
    def zero(cls) -> SetupState:
        return cls()

    def with_axis(self, axis: str, value: float) -> SetupState:
        """Return a copy with one axis replaced."""
        kwargs = {
            "vertical": self.vertical,
            "longitudinal": self.longitudinal,
            "lateral": self.lateral,
            "rotation": self.rotation,
            "pitch": self.pitch,
            "roll": self.roll,
        }
        kwargs[axis] = value
        return SetupState(**kwargs)

    def get_axis(self, axis: str) -> float:
        return getattr(self, axis)


AXIS_NAMES: list[str] = [
    "vertical",
    "longitudinal",
    "lateral",
    "rotation",
    "pitch",
    "roll",
]

TRANSLATION_AXES: set[str] = {"vertical", "longitudinal", "lateral"}
ROTATION_AXES: set[str] = {"rotation", "pitch", "roll"}


@dataclass
class PointResult:
    """Evaluation result for a single point. data-model-design section 4.1.

    Tuple order is always (x, y, z) = (Lateral, Long, Vertical).
    """

    point_name: str
    distance_from_iso_mm: float
    displacement: tuple[float, float, float]
    translation_contribution: tuple[float, float, float]
    rotation_contribution: tuple[float, float, float]
    effective_displacement_3d_mm: float
    translation_only_mm: float
    rotation_induced_mm: float
    uncertainty_mm: tuple[float, float, float]
    conservative_displacement_mm: tuple[float, float, float]
    margin_remaining_mm: tuple[float, float, float]
    axiswise_pass_fail: tuple[bool, bool, bool]
    overall_pass_fail: bool
    margin_consumption_ratio: tuple[float, float, float]


@dataclass
class AxisAllowance:
    """Allowable range for one 6DoF axis. data-model-design section 4.2."""

    axis_name: str
    current_value: float
    allowable_min: float
    allowable_max: float
    remaining_negative: float
    remaining_positive: float
    limiting_point: str
    limiting_axis: str
    status: str  # "within" / "exceeded" / "no_points"


@dataclass
class SimulationResult:
    """Overall simulation result. data-model-design section 4.3."""

    pass_fail: Optional[bool]  # None when no evaluation points
    worst_point: Optional[PointResult]
    worst_axis: str
    all_point_results: list[PointResult]
    conditional_allowances: list[AxisAllowance]
    standalone_allowances: list[AxisAllowance]
    mag_mm: float
