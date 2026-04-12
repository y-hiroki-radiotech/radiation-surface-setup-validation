"""Streamlit UI for the setup margin allowance simulator.

Layout follows ui-design.md.
"""

from __future__ import annotations

import math

import streamlit as st
import pandas as pd

from src.models import (
    AxisUncertainty,
    EvaluationPoint,
    MarginProtocol,
    SetupState,
    SimulationResult,
    UncertaintyModel,
)
from src.decision import find_worst_axis, find_worst_point, is_pass, judge_all
from src.allowance import (
    ROTATION_SEARCH_MAX,
    ROTATION_SEARCH_MIN,
    TRANSLATION_SEARCH_MAX,
    TRANSLATION_SEARCH_MIN,
    find_all_conditional_allowances,
    find_all_standalone_allowances,
)

# --- Page config ---
st.set_page_config(page_title="Setup Margin Simulator", layout="wide")
st.title("Setup Margin Allowance Simulator / セットアップマージン許容領域シミュレータ")


# ============================================================
# Section 1: Condition Settings (Sidebar)
# ============================================================
st.sidebar.header("Condition Settings / 条件設定")

st.sidebar.subheader("Margins / マージン (mm)")
m_vertical = st.sidebar.number_input(
    "Vertical Margin / 垂直方向", value=10.0, min_value=0.0, max_value=50.0, step=0.5, key="m_z"
)
m_long = st.sidebar.number_input(
    "Long Margin / 長軸方向", value=10.0, min_value=0.0, max_value=50.0, step=0.5, key="m_y"
)
m_lateral = st.sidebar.number_input(
    "Lateral Margin / 側方", value=10.0, min_value=0.0, max_value=50.0, step=0.5, key="m_x"
)
margin = MarginProtocol(m_x=m_lateral, m_y=m_long, m_z=m_vertical)

# Safety factor
safety_z = st.sidebar.number_input(
    "Safety Factor z / 安全係数", value=2.0, min_value=0.0, max_value=5.0, step=0.1, key="safety_z"
)

# Uncertainty
with st.sidebar.expander("Uncertainty Settings / 不確かさ設定"):
    unc_axes = {}
    for label, axis_key in [("Lateral (x)", "x"), ("Long (y)", "y"), ("Vertical (z)", "z")]:
        st.markdown(f"**{label}**")
        u_id = st.number_input(f"U_identify ({axis_key})", value=1.0, min_value=0.0, step=0.1, key=f"u_id_{axis_key}")
        u_sur = st.number_input(f"U_surrogate ({axis_key})", value=2.0, min_value=0.0, step=0.1, key=f"u_sur_{axis_key}")
        u_reg = st.number_input(f"U_registration ({axis_key})", value=1.0, min_value=0.0, step=0.1, key=f"u_reg_{axis_key}")
        u_intra = st.number_input(f"U_intrafraction ({axis_key})", value=1.0, min_value=0.0, step=0.1, key=f"u_intra_{axis_key}")
        u_mod = st.number_input(f"U_model ({axis_key})", value=0.5, min_value=0.0, step=0.1, key=f"u_mod_{axis_key}")
        au = AxisUncertainty(u_identify=u_id, u_surrogate=u_sur, u_registration=u_reg, u_intrafraction=u_intra, u_model=u_mod)
        st.caption(f"Total: {au.total:.2f} mm")
        unc_axes[axis_key] = au

uncertainty = UncertaintyModel(x=unc_axes["x"], y=unc_axes["y"], z=unc_axes["z"])


# ============================================================
# Section 2: Evaluation Points (Sidebar)
# ============================================================
st.sidebar.header("Evaluation Points / 評価点設定")

# Farthest point
st.sidebar.subheader("Farthest Point / 最遠点")
fp_name = st.sidebar.text_input("Name / 名前", value="farthest_1", key="fp_name")
fp_x = st.sidebar.number_input("x (Lateral) mm", value=0.0, step=1.0, key="fp_x")
fp_y = st.sidebar.number_input("y (Long) mm", value=100.0, step=1.0, key="fp_y")
fp_z = st.sidebar.number_input("z (Vertical) mm", value=50.0, step=1.0, key="fp_z")
farthest = EvaluationPoint(name=fp_name, x=fp_x, y=fp_y, z=fp_z)
st.sidebar.caption(f"Distance from ISO: {farthest.distance_from_iso:.1f} mm")

# Additional points
st.sidebar.subheader("Additional Points / 追加評価点")
if "extra_points" not in st.session_state:
    st.session_state.extra_points = []

if st.sidebar.button("+ Add Point / 点を追加"):
    idx = len(st.session_state.extra_points) + 2
    st.session_state.extra_points.append(
        {"name": f"point_{idx}", "x": 0.0, "y": 0.0, "z": 0.0}
    )

remove_idx = None
for i, ep_data in enumerate(st.session_state.extra_points):
    with st.sidebar.container():
        cols = st.sidebar.columns([3, 1])
        with cols[0]:
            st.markdown(f"**Point {i + 2}**")
        with cols[1]:
            if st.button("🗑", key=f"rm_{i}"):
                remove_idx = i

        ep_data["name"] = st.sidebar.text_input("Name", value=ep_data["name"], key=f"ep_name_{i}")
        ep_data["x"] = st.sidebar.number_input("x mm", value=ep_data["x"], step=1.0, key=f"ep_x_{i}")
        ep_data["y"] = st.sidebar.number_input("y mm", value=ep_data["y"], step=1.0, key=f"ep_y_{i}")
        ep_data["z"] = st.sidebar.number_input("z mm", value=ep_data["z"], step=1.0, key=f"ep_z_{i}")
        pt = EvaluationPoint(name=ep_data["name"], x=ep_data["x"], y=ep_data["y"], z=ep_data["z"])
        st.sidebar.caption(f"Distance: {pt.distance_from_iso:.1f} mm")

if remove_idx is not None:
    st.session_state.extra_points.pop(remove_idx)
    st.rerun()

# Build evaluation points list
eval_points: list[EvaluationPoint] = [farthest]
for ep_data in st.session_state.extra_points:
    eval_points.append(
        EvaluationPoint(name=ep_data["name"], x=ep_data["x"], y=ep_data["y"], z=ep_data["z"])
    )


# ============================================================
# Section 3: 6DoF Simulation (Sidebar)
# ============================================================
st.sidebar.header("6DoF Simulation / シミュレーション")

vertical = st.sidebar.slider("Vertical (mm)", -50.0, 50.0, 0.0, 0.1, key="sl_vert")
longitudinal = st.sidebar.slider("Long (mm)", -50.0, 50.0, 0.0, 0.1, key="sl_long")
lateral = st.sidebar.slider("Lateral (mm)", -50.0, 50.0, 0.0, 0.1, key="sl_lat")
rotation = st.sidebar.slider("Rotation (°)", -10.0, 10.0, 0.0, 0.1, key="sl_rot")
pitch = st.sidebar.slider("Pitch (°)", -10.0, 10.0, 0.0, 0.1, key="sl_pitch")
roll = st.sidebar.slider("Roll (°)", -10.0, 10.0, 0.0, 0.1, key="sl_roll")

current_state = SetupState(
    vertical=vertical,
    longitudinal=longitudinal,
    lateral=lateral,
    rotation=rotation,
    pitch=pitch,
    roll=roll,
)

# Standalone reference mode
st.sidebar.subheader("Standalone Reference / 単独許容量の基準状態")
ref_mode = st.sidebar.selectbox(
    "Mode / モード",
    ["zero_based", "current_based", "custom"],
    index=0,
    key="ref_mode",
)

if ref_mode == "zero_based":
    reference_state = SetupState.zero()
elif ref_mode == "current_based":
    reference_state = current_state
else:
    st.sidebar.markdown("**Custom Reference / カスタム基準値**")
    ref_v = st.sidebar.number_input(
        "Ref Vertical (mm)",
        value=0.0,
        min_value=TRANSLATION_SEARCH_MIN,
        max_value=TRANSLATION_SEARCH_MAX,
        step=0.1,
        key="ref_v",
    )
    ref_l = st.sidebar.number_input(
        "Ref Long (mm)",
        value=0.0,
        min_value=TRANSLATION_SEARCH_MIN,
        max_value=TRANSLATION_SEARCH_MAX,
        step=0.1,
        key="ref_l",
    )
    ref_t = st.sidebar.number_input(
        "Ref Lateral (mm)",
        value=0.0,
        min_value=TRANSLATION_SEARCH_MIN,
        max_value=TRANSLATION_SEARCH_MAX,
        step=0.1,
        key="ref_t",
    )
    ref_r = st.sidebar.number_input(
        "Ref Rotation (°)",
        value=0.0,
        min_value=ROTATION_SEARCH_MIN,
        max_value=ROTATION_SEARCH_MAX,
        step=0.1,
        key="ref_r",
    )
    ref_p = st.sidebar.number_input(
        "Ref Pitch (°)",
        value=0.0,
        min_value=ROTATION_SEARCH_MIN,
        max_value=ROTATION_SEARCH_MAX,
        step=0.1,
        key="ref_p",
    )
    ref_w = st.sidebar.number_input(
        "Ref Roll (°)",
        value=0.0,
        min_value=ROTATION_SEARCH_MIN,
        max_value=ROTATION_SEARCH_MAX,
        step=0.1,
        key="ref_w",
    )
    reference_state = SetupState(
        vertical=ref_v, longitudinal=ref_l, lateral=ref_t,
        rotation=ref_r, pitch=ref_p, roll=ref_w,
    )


# ============================================================
# Computation
# ============================================================
results = judge_all(current_state, eval_points, margin, uncertainty, safety_z)
overall = is_pass(results)
worst_pt = find_worst_point(results)
worst_ax = find_worst_axis(results) if results else ""
mag = math.sqrt(lateral**2 + longitudinal**2 + vertical**2)

conditional = find_all_conditional_allowances(current_state, eval_points, margin, uncertainty, safety_z)
standalone = find_all_standalone_allowances(reference_state, eval_points, margin, uncertainty, safety_z)

sim_result = SimulationResult(
    pass_fail=overall,
    worst_point=worst_pt,
    worst_axis=worst_ax,
    all_point_results=results,
    conditional_allowances=conditional,
    standalone_allowances=standalone,
    mag_mm=mag,
)


# ============================================================
# Section 4: Results (Main area)
# ============================================================

# --- 4.1 Overall judgment header ---
if not eval_points:
    st.warning("⚠️ Please add evaluation points. / 評価点を入力してください。")
elif overall is True:
    st.success(f"✅ **PASS** — Worst Point: {worst_pt.point_name}, Constraint Axis: {worst_ax}, "
               f"Max Q: {max(worst_pt.margin_consumption_ratio):.3f}, Mag: {mag:.1f} mm")
else:
    st.error(f"❌ **FAIL** — Worst Point: {worst_pt.point_name}, Constraint Axis: {worst_ax}, "
             f"Max Q: {max(worst_pt.margin_consumption_ratio):.3f}, Mag: {mag:.1f} mm")

# --- 4.2 Point results table ---
if results:
    st.subheader("Point Results / 評価点別結果")
    axis_labels = ["x (Lat)", "y (Long)", "z (Vert)"]
    rows = []
    for pr in results:
        row = {
            "Point": pr.point_name,
            "d_iso (mm)": f"{pr.distance_from_iso_mm:.1f}",
        }
        for k, al in enumerate(axis_labels):
            row[f"Δ{al}"] = f"{pr.displacement[k]:.2f}"
            row[f"C_{al}"] = f"{pr.conservative_displacement_mm[k]:.2f}"
            row[f"Q_{al}"] = f"{pr.margin_consumption_ratio[k]:.3f}"
        row["Status"] = "✅" if pr.overall_pass_fail else "❌"
        rows.append(row)

    df_points = pd.DataFrame(rows)
    st.dataframe(df_points, use_container_width=True, hide_index=True)

# --- 4.3 Allowance tables ---
if results:
    st.subheader("Allowable Ranges / 許容量")
    col1, col2 = st.columns(2)

    def _allowance_df(allowances: list, title: str) -> pd.DataFrame:
        rows = []
        for a in allowances:
            unit = "°" if a.axis_name in ("rotation", "pitch", "roll") else "mm"
            rows.append({
                "Axis": a.axis_name,
                "Current": f"{a.current_value:.2f} {unit}",
                "Min": f"{a.allowable_min:.2f} {unit}",
                "Max": f"{a.allowable_max:.2f} {unit}",
                "Rem(-)": f"{a.remaining_negative:.2f}",
                "Rem(+)": f"{a.remaining_positive:.2f}",
                "Limit Pt": a.limiting_point,
                "Limit Ax": a.limiting_axis,
                "Status": a.status,
            })
        return pd.DataFrame(rows)

    with col1:
        st.markdown("**Conditional / 条件付き許容量**")
        st.dataframe(_allowance_df(conditional, "Conditional"), use_container_width=True, hide_index=True)

    with col2:
        st.markdown(f"**Standalone / 単独許容量 ({ref_mode})**")
        st.dataframe(_allowance_df(standalone, "Standalone"), use_container_width=True, hide_index=True)

# --- 4.4 Reference indicators ---
if results and worst_pt:
    st.subheader("Reference Indicators / 参考指標 (3D)")
    ref_cols = st.columns(3)
    ref_cols[0].metric("Effective Displacement (3D)", f"{worst_pt.effective_displacement_3d_mm:.2f} mm")
    ref_cols[1].metric("Max Consumption Q", f"{max(worst_pt.margin_consumption_ratio):.3f}")
    ref_cols[2].metric("Mag (translation norm)", f"{mag:.2f} mm")

# --- 4.5 Scatter plot: distance vs max Q ---
if results:
    st.subheader("Distance vs Margin Consumption / 距離 vs マージン消費率")
    scatter_data = pd.DataFrame({
        "Point": [pr.point_name for pr in results],
        "Distance from ISO (mm)": [pr.distance_from_iso_mm for pr in results],
        "Max Q": [max(pr.margin_consumption_ratio) for pr in results],
    })
    chart = st.scatter_chart(
        scatter_data,
        x="Distance from ISO (mm)",
        y="Max Q",
        color=None,
        use_container_width=True,
    )

# --- 4.6 Contribution breakdown ---
if results:
    st.subheader("Contribution Breakdown / 寄与分離")
    contrib_rows = []
    for pr in results:
        contrib_rows.append({
            "Point": pr.point_name,
            "Translation (mm)": pr.translation_only_mm,
            "Rotation (mm)": pr.rotation_induced_mm,
        })
    df_contrib = pd.DataFrame(contrib_rows)
    st.bar_chart(df_contrib.set_index("Point"), use_container_width=True)
