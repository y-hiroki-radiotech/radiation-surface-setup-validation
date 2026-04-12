"""Tests for geometry.py — rotation matrices and displacement calculations.

Test cases follow test-design.md sections 3-4.
"""

import math

import numpy as np
import pytest

from src.geometry import (
    build_rotation_matrix,
    build_translation_vector,
    compute_all_displacements,
    compute_displacement,
    decompose_displacement,
    deg_to_rad,
)
from src.models import EvaluationPoint, SetupState


# --- Sanity Checks (math-design 23) ---

class TestSanityChecks:
    """SC-1 through SC-4 from test-design.md section 3."""

    def test_sc1_zero_input(self):
        """SC-1: All 6DoF = 0 → Δp = [0,0,0] for any point."""
        state = SetupState.zero()
        for p in [
            EvaluationPoint("a", 10, 20, 30),
            EvaluationPoint("b", -50, 0, 100),
            EvaluationPoint("c", 0, 0, 0),
        ]:
            disp = compute_displacement(state, p)
            np.testing.assert_allclose(disp, [0, 0, 0], atol=1e-10)

    def test_sc2_translation_only(self):
        """SC-2: Rotation=0 → all points get same displacement = T."""
        state = SetupState(vertical=3.0, longitudinal=2.0, lateral=1.0)
        expected = [1.0, 2.0, 3.0]  # T = [lateral, long, vertical]
        for p in [
            EvaluationPoint("a", 50, 80, 120),
            EvaluationPoint("b", 0, 0, 0),
            EvaluationPoint("c", -30, 70, 10),
        ]:
            disp = compute_displacement(state, p)
            np.testing.assert_allclose(disp, expected, atol=1e-10)

    def test_sc3_origin_fixed_point(self):
        """SC-3: Translation=0, point at origin → Δp = [0,0,0]."""
        state = SetupState(rotation=5.0, pitch=3.0, roll=-2.0)
        p = EvaluationPoint("origin", 0, 0, 0)
        disp = compute_displacement(state, p)
        np.testing.assert_allclose(disp, [0, 0, 0], atol=1e-10)

    def test_sc4_far_point_larger_rotation(self):
        """SC-4: Farther point gets larger rotation-induced displacement.

        Points must not lie on the rotation axis (z-axis for Rotation).
        """
        state = SetupState(rotation=2.0)
        p_near = EvaluationPoint("near", 50, 0, 0)
        p_far = EvaluationPoint("far", 100, 0, 0)

        _, rot_near = decompose_displacement(state, p_near)
        _, rot_far = decompose_displacement(state, p_far)

        assert np.linalg.norm(rot_far) > np.linalg.norm(rot_near)


# --- Rotation Matrix Tests ---

class TestRotationMatrix:
    """G-1 through G-6 from test-design.md section 4.1."""

    def test_g1_identity(self):
        """G-1: Zero rotation → identity matrix."""
        R = build_rotation_matrix(0, 0, 0)
        np.testing.assert_allclose(R, np.eye(3), atol=1e-10)

    def test_g2_z_axis_90(self):
        """G-2: Rotation=90° → R_z(90°)."""
        R = build_rotation_matrix(90, 0, 0)
        expected = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]], dtype=float)
        np.testing.assert_allclose(R, expected, atol=1e-10)

    def test_g3_x_axis_90(self):
        """G-3: Pitch=90° → R_x(90°)."""
        R = build_rotation_matrix(0, 90, 0)
        expected = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], dtype=float)
        np.testing.assert_allclose(R, expected, atol=1e-10)

    def test_g4_y_axis_90(self):
        """G-4: Roll=90° → R_y(90°)."""
        R = build_rotation_matrix(0, 0, 90)
        expected = np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]], dtype=float)
        np.testing.assert_allclose(R, expected, atol=1e-10)

    def test_g5_orthogonality(self):
        """G-5: R^T @ R ≈ I."""
        R = build_rotation_matrix(3.5, -2.1, 1.8)
        np.testing.assert_allclose(R.T @ R, np.eye(3), atol=1e-10)

    def test_g6_determinant(self):
        """G-6: det(R) ≈ 1."""
        R = build_rotation_matrix(3.5, -2.1, 1.8)
        assert abs(np.linalg.det(R) - 1.0) < 1e-10


# --- Displacement Tests ---

class TestDisplacement:
    """G-7 through G-10 from test-design.md section 4.2-4.3."""

    def test_g7_translation_only(self):
        """G-7: Rotation=0 → Δp = T for any point."""
        state = SetupState(lateral=5.0, longitudinal=-3.0, vertical=2.0)
        p = EvaluationPoint("test", 10, 20, 30)
        disp = compute_displacement(state, p)
        np.testing.assert_allclose(disp, [5.0, -3.0, 2.0], atol=1e-10)

    def test_g8_small_angle_approximation(self):
        """G-8: Small rotation ≈ distance × angle(rad)."""
        state = SetupState(rotation=1.0)  # 1° z-axis rotation
        # Point on x-axis: rotation around z moves it in y
        p = EvaluationPoint("test", 100, 0, 0)
        _, rot = decompose_displacement(state, p)
        rot_magnitude = np.linalg.norm(rot)

        approx = 100 * deg_to_rad(1.0)  # ≈ 1.745 mm
        assert abs(rot_magnitude - approx) / approx < 0.01  # <1% error

    def test_g9_decomposition_consistency(self):
        """G-9: trans + rot = total displacement."""
        state = SetupState(vertical=2.0, rotation=3.0, pitch=1.0, roll=-1.5)
        p = EvaluationPoint("test", 50, 30, 80)
        trans, rot = decompose_displacement(state, p)
        total = compute_displacement(state, p)
        np.testing.assert_allclose(trans + rot, total, atol=1e-10)

    def test_g10_rotation_order(self):
        """G-10: Verify R = R_z @ R_x @ R_y produces correct result."""
        state = SetupState(rotation=10, pitch=5, roll=3)
        p = EvaluationPoint("test", 50, 30, 20)

        # Manual computation
        tr = deg_to_rad(10)
        tp = deg_to_rad(5)
        tw = deg_to_rad(3)

        Rz = np.array([[math.cos(tr), -math.sin(tr), 0],
                        [math.sin(tr), math.cos(tr), 0],
                        [0, 0, 1]])
        Rx = np.array([[1, 0, 0],
                        [0, math.cos(tp), -math.sin(tp)],
                        [0, math.sin(tp), math.cos(tp)]])
        Ry = np.array([[math.cos(tw), 0, math.sin(tw)],
                        [0, 1, 0],
                        [-math.sin(tw), 0, math.cos(tw)]])

        R_expected = Rz @ Rx @ Ry
        T = np.array([0, 0, 0])
        pv = np.array([50.0, 30.0, 20.0])
        expected_disp = T + (R_expected - np.eye(3)) @ pv

        actual = compute_displacement(state, p)
        np.testing.assert_allclose(actual, expected_disp, atol=1e-10)

    def test_compute_all(self):
        """compute_all_displacements returns same as individual calls."""
        state = SetupState(vertical=1.0, rotation=2.0)
        points = [
            EvaluationPoint("a", 10, 20, 30),
            EvaluationPoint("b", -5, 15, 0),
        ]
        all_disp = compute_all_displacements(state, points)
        for i, pt in enumerate(points):
            single = compute_displacement(state, pt)
            np.testing.assert_allclose(all_disp[i], single, atol=1e-10)


class TestTranslationVector:

    def test_order(self):
        """T = [lateral, longitudinal, vertical]."""
        state = SetupState(vertical=3.0, longitudinal=2.0, lateral=1.0)
        T = build_translation_vector(state)
        np.testing.assert_array_equal(T, [1.0, 2.0, 3.0])
