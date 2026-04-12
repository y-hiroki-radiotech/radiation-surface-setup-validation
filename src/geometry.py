"""Geometric computations: rotation matrices and point displacements.

All formulas follow math-design.md sections 6-9.
Coordinate system: x=Lateral, y=Long, z=Vertical, origin=ISO.
Rotation order: R = R_z(rotation) @ R_x(pitch) @ R_y(roll)  (section 7.5).
"""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray

from .models import EvaluationPoint, SetupState


def deg_to_rad(deg: float) -> float:
    """Convert degrees to radians. math-design section 7.3."""
    return deg * math.pi / 180.0


def _rotation_x(theta: float) -> NDArray[np.float64]:
    """R_x(theta). math-design section 7.4."""
    c, s = math.cos(theta), math.sin(theta)
    return np.array([
        [1.0, 0.0, 0.0],
        [0.0, c, -s],
        [0.0, s, c],
    ])


def _rotation_y(theta: float) -> NDArray[np.float64]:
    """R_y(theta). math-design section 7.4."""
    c, s = math.cos(theta), math.sin(theta)
    return np.array([
        [c, 0.0, s],
        [0.0, 1.0, 0.0],
        [-s, 0.0, c],
    ])


def _rotation_z(theta: float) -> NDArray[np.float64]:
    """R_z(theta). math-design section 7.4."""
    c, s = math.cos(theta), math.sin(theta)
    return np.array([
        [c, -s, 0.0],
        [s, c, 0.0],
        [0.0, 0.0, 1.0],
    ])


def build_rotation_matrix(
    rotation_deg: float,
    pitch_deg: float,
    roll_deg: float,
) -> NDArray[np.float64]:
    """Build composite rotation matrix R = R_z(r) @ R_x(p) @ R_y(w).

    math-design section 7.5.
    """
    theta_r = deg_to_rad(rotation_deg)
    theta_p = deg_to_rad(pitch_deg)
    theta_w = deg_to_rad(roll_deg)
    return _rotation_z(theta_r) @ _rotation_x(theta_p) @ _rotation_y(theta_w)


def build_translation_vector(state: SetupState) -> NDArray[np.float64]:
    """T = [lateral, longitudinal, vertical] = [x, y, z]. math-design section 6."""
    return np.array([state.lateral, state.longitudinal, state.vertical])


def compute_displacement(
    state: SetupState,
    point: EvaluationPoint,
) -> NDArray[np.float64]:
    """Displacement vector Δp_i = T + (R - I) p_i. math-design section 8.2."""
    R = build_rotation_matrix(state.rotation, state.pitch, state.roll)
    T = build_translation_vector(state)
    p = np.array([point.x, point.y, point.z])
    return T + (R - np.eye(3)) @ p


def compute_all_displacements(
    state: SetupState,
    points: list[EvaluationPoint],
) -> list[NDArray[np.float64]]:
    """Compute displacements for all evaluation points.

    Rotation matrix is built once and shared across all points.
    """
    R = build_rotation_matrix(state.rotation, state.pitch, state.roll)
    T = build_translation_vector(state)
    R_minus_I = R - np.eye(3)
    results = []
    for pt in points:
        p = np.array([pt.x, pt.y, pt.z])
        results.append(T + R_minus_I @ p)
    return results


def decompose_displacement(
    state: SetupState,
    point: EvaluationPoint,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Separate displacement into translation and rotation contributions.

    Returns (translation_contribution, rotation_contribution).
    math-design section 9.
    """
    R = build_rotation_matrix(state.rotation, state.pitch, state.roll)
    T = build_translation_vector(state)
    p = np.array([point.x, point.y, point.z])
    rot_contrib = (R - np.eye(3)) @ p
    return T, rot_contrib
