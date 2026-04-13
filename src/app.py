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

AXIS_INDEX = {"x": 0, "y": 1, "z": 2}
AXIS_LABELS = {"x": "Lateral (x)", "y": "Long (y)", "z": "Vertical (z)"}
DEFAULT_UNCERTAINTY_TEMPLATE = {
    "u_id": 1.0,
    "u_sur": 2.0,
    "u_reg": 1.0,
    "u_intra": 1.0,
    "u_mod": 0.5,
}


def _apply_default_uncertainty_template() -> None:
    """Populate uncertainty widgets with the default demo template."""
    for axis_key in ("x", "y", "z"):
        for field_name, field_value in DEFAULT_UNCERTAINTY_TEMPLATE.items():
            st.session_state[f"{field_name}_{axis_key}"] = field_value


def _coerce_float(value: object) -> float:
    """Return a numeric value from an editor cell, defaulting blanks to zero."""
    if pd.isna(value):
        return 0.0
    if isinstance(value, str) and not value.strip():
        return 0.0
    return float(value)


def _normalize_extra_points(editor_df: pd.DataFrame) -> list[dict[str, float | str]]:
    """Convert editable rows into the extra-point session-state shape."""
    normalized: list[dict[str, float | str]] = []
    for row_idx, row in enumerate(editor_df.to_dict("records"), start=2):
        name_value = row.get("name")
        name = "" if pd.isna(name_value) else str(name_value).strip()
        x = _coerce_float(row.get("x"))
        y = _coerce_float(row.get("y"))
        z = _coerce_float(row.get("z"))
        has_content = bool(name) or any(value != 0.0 for value in (x, y, z))
        if not has_content:
            continue
        normalized.append({
            "name": name or f"point_{row_idx}",
            "x": x,
            "y": y,
            "z": z,
        })
    return normalized


# --- Page config ---
st.set_page_config(page_title="Setup Margin Simulator", layout="wide")
st.title("Setup Margin Allowance Simulator / セットアップマージン許容領域シミュレータ")
st.caption("Adjust the current 6DoF state, then review the limiting point and remaining margin headroom.")


# ============================================================
# Section 1: Condition Settings (Sidebar)
# ============================================================
st.sidebar.header("Simulation Inputs / 入力")

with st.sidebar.expander("1. Conditions / 条件", expanded=True):
    st.subheader("Margins / マージン (mm)")
    m_vertical = st.number_input(
        "Vertical Margin / 垂直方向", value=10.0, min_value=0.0, max_value=50.0, step=0.5, key="m_z"
    )
    m_long = st.number_input(
        "Long Margin / 長軸方向", value=10.0, min_value=0.0, max_value=50.0, step=0.5, key="m_y"
    )
    m_lateral = st.number_input(
        "Lateral Margin / 側方", value=10.0, min_value=0.0, max_value=50.0, step=0.5, key="m_x"
    )
    margin = MarginProtocol(m_x=m_lateral, m_y=m_long, m_z=m_vertical)

    safety_z = st.number_input(
        "Safety Factor z / 安全係数", value=2.0, min_value=0.0, max_value=5.0, step=0.1, key="safety_z"
    )

    unc_template = st.selectbox(
        "Uncertainty Template / 不確かさテンプレート",
        ["default", "custom"],
        index=0,
        key="unc_template",
    )
    if unc_template == "default":
        _apply_default_uncertainty_template()

    with st.expander("Uncertainty Settings / 不確かさ設定", expanded=False):
        st.caption("Use `custom` to edit values. `default` applies the baseline demo template.")
        unc_axes = {}
        inputs_disabled = unc_template != "custom"
        for label, axis_key in [("Lateral (x)", "x"), ("Long (y)", "y"), ("Vertical (z)", "z")]:
            st.markdown(f"**{label}**")
            u_id = st.number_input(
                f"U_identify ({axis_key})",
                min_value=0.0,
                step=0.1,
                key=f"u_id_{axis_key}",
                disabled=inputs_disabled,
            )
            u_sur = st.number_input(
                f"U_surrogate ({axis_key})",
                min_value=0.0,
                step=0.1,
                key=f"u_sur_{axis_key}",
                disabled=inputs_disabled,
            )
            u_reg = st.number_input(
                f"U_registration ({axis_key})",
                min_value=0.0,
                step=0.1,
                key=f"u_reg_{axis_key}",
                disabled=inputs_disabled,
            )
            u_intra = st.number_input(
                f"U_intrafraction ({axis_key})",
                min_value=0.0,
                step=0.1,
                key=f"u_intra_{axis_key}",
                disabled=inputs_disabled,
            )
            u_mod = st.number_input(
                f"U_model ({axis_key})",
                min_value=0.0,
                step=0.1,
                key=f"u_mod_{axis_key}",
                disabled=inputs_disabled,
            )
            au = AxisUncertainty(
                u_identify=u_id,
                u_surrogate=u_sur,
                u_registration=u_reg,
                u_intrafraction=u_intra,
                u_model=u_mod,
            )
            st.caption(f"Total: {au.total:.2f} mm")
            unc_axes[axis_key] = au

uncertainty = UncertaintyModel(x=unc_axes["x"], y=unc_axes["y"], z=unc_axes["z"])


# ============================================================
# Section 2: Evaluation Points (Sidebar)
# ============================================================
if "extra_points" not in st.session_state:
    st.session_state.extra_points = []

with st.sidebar.expander("2. Evaluation Points / 評価点", expanded=True):
    st.subheader("Farthest Point / 最遠点")
    fp_name = st.text_input("Name / 名前", value="farthest_1", key="fp_name")
    fp_x = st.number_input("x (Lateral) mm", value=0.0, step=1.0, key="fp_x")
    fp_y = st.number_input("y (Long) mm", value=100.0, step=1.0, key="fp_y")
    fp_z = st.number_input("z (Vertical) mm", value=50.0, step=1.0, key="fp_z")
    farthest = EvaluationPoint(name=fp_name, x=fp_x, y=fp_y, z=fp_z)
    st.caption(f"Distance from ISO: {farthest.distance_from_iso:.1f} mm")

    st.subheader("Additional Points / 追加評価点")
    st.caption("Add, edit, or delete rows directly in the table.")
    extra_points_df = pd.DataFrame(st.session_state.extra_points, columns=["name", "x", "y", "z"])
    edited_extra_points = st.data_editor(
        extra_points_df,
        hide_index=True,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "name": st.column_config.TextColumn("Name"),
            "x": st.column_config.NumberColumn("x (Lat)", step=1.0, format="%.1f"),
            "y": st.column_config.NumberColumn("y (Long)", step=1.0, format="%.1f"),
            "z": st.column_config.NumberColumn("z (Vert)", step=1.0, format="%.1f"),
        },
    )
    st.session_state.extra_points = _normalize_extra_points(edited_extra_points)

    if st.session_state.extra_points:
        extra_preview_rows = []
        for point_data in st.session_state.extra_points:
            point = EvaluationPoint(
                name=str(point_data["name"]),
                x=float(point_data["x"]),
                y=float(point_data["y"]),
                z=float(point_data["z"]),
            )
            extra_preview_rows.append({
                "Point": point.name,
                "d_iso (mm)": f"{point.distance_from_iso:.1f}",
            })
        st.dataframe(pd.DataFrame(extra_preview_rows), hide_index=True, use_container_width=True)

# Build evaluation points list
eval_points: list[EvaluationPoint] = [farthest]
for ep_data in st.session_state.extra_points:
    eval_points.append(
        EvaluationPoint(name=ep_data["name"], x=ep_data["x"], y=ep_data["y"], z=ep_data["z"])
    )


# ============================================================
# Section 3: 6DoF Simulation (Sidebar)
# ============================================================
with st.sidebar.expander("3. Current 6DoF / 現在の6DoF", expanded=True):
    vertical = st.slider("Vertical (mm)", -50.0, 50.0, 0.0, 0.1, key="sl_vert")
    longitudinal = st.slider("Long (mm)", -50.0, 50.0, 0.0, 0.1, key="sl_long")
    lateral = st.slider("Lateral (mm)", -50.0, 50.0, 0.0, 0.1, key="sl_lat")
    rotation = st.slider("Rotation (°)", -10.0, 10.0, 0.0, 0.1, key="sl_rot")
    pitch = st.slider("Pitch (°)", -10.0, 10.0, 0.0, 0.1, key="sl_pitch")
    roll = st.slider("Roll (°)", -10.0, 10.0, 0.0, 0.1, key="sl_roll")

    current_state = SetupState(
        vertical=vertical,
        longitudinal=longitudinal,
        lateral=lateral,
        rotation=rotation,
        pitch=pitch,
        roll=roll,
    )

    st.caption(
        f"Translation magnitude: {math.sqrt(lateral**2 + longitudinal**2 + vertical**2):.2f} mm"
    )

    st.subheader("Standalone Reference / 単独許容量の基準状態")
    ref_mode = st.selectbox(
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
        st.markdown("**Custom Reference / カスタム基準値**")
        ref_v = st.number_input(
            "Ref Vertical (mm)",
            value=0.0,
            min_value=TRANSLATION_SEARCH_MIN,
            max_value=TRANSLATION_SEARCH_MAX,
            step=0.1,
            key="ref_v",
        )
        ref_l = st.number_input(
            "Ref Long (mm)",
            value=0.0,
            min_value=TRANSLATION_SEARCH_MIN,
            max_value=TRANSLATION_SEARCH_MAX,
            step=0.1,
            key="ref_l",
        )
        ref_t = st.number_input(
            "Ref Lateral (mm)",
            value=0.0,
            min_value=TRANSLATION_SEARCH_MIN,
            max_value=TRANSLATION_SEARCH_MAX,
            step=0.1,
            key="ref_t",
        )
        ref_r = st.number_input(
            "Ref Rotation (°)",
            value=0.0,
            min_value=ROTATION_SEARCH_MIN,
            max_value=ROTATION_SEARCH_MAX,
            step=0.1,
            key="ref_r",
        )
        ref_p = st.number_input(
            "Ref Pitch (°)",
            value=0.0,
            min_value=ROTATION_SEARCH_MIN,
            max_value=ROTATION_SEARCH_MAX,
            step=0.1,
            key="ref_p",
        )
        ref_w = st.number_input(
            "Ref Roll (°)",
            value=0.0,
            min_value=ROTATION_SEARCH_MIN,
            max_value=ROTATION_SEARCH_MAX,
            step=0.1,
            key="ref_w",
        )
        reference_state = SetupState(
            vertical=ref_v,
            longitudinal=ref_l,
            lateral=ref_t,
            rotation=ref_r,
            pitch=ref_p,
            roll=ref_w,
        )


# ============================================================
# Computation
# ============================================================
results = judge_all(current_state, eval_points, margin, uncertainty, safety_z)
overall = is_pass(results)
worst_pt = find_worst_point(results)
worst_ax = find_worst_axis(results) if results else ""
mag = math.sqrt(lateral**2 + longitudinal**2 + vertical**2)
constraint_idx = AXIS_INDEX[worst_ax] if results and worst_ax else 0
axis_margins = (margin.m_x, margin.m_y, margin.m_z)
constraint_label = AXIS_LABELS.get(worst_ax, "")
constraint_margin = axis_margins[constraint_idx] if results else 0.0
constraint_conservative = worst_pt.conservative_displacement_mm[constraint_idx] if worst_pt else 0.0
constraint_remaining = worst_pt.margin_remaining_mm[constraint_idx] if worst_pt else 0.0
constraint_overrun = max(0.0, -constraint_remaining)
constraint_headroom = max(0.0, constraint_remaining)
max_q = worst_pt.margin_consumption_ratio[constraint_idx] if worst_pt else 0.0

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
    st.success(
        f"✅ **PASS** — Worst point `{worst_pt.point_name}` is limited by `{constraint_label}` "
        f"with {constraint_headroom:.2f} mm headroom remaining."
    )
else:
    st.error(
        f"❌ **FAIL** — Point `{worst_pt.point_name}` exceeds `{constraint_label}` by "
        f"{constraint_overrun:.2f} mm. Conservative displacement is "
        f"{constraint_conservative:.2f} mm against a {constraint_margin:.2f} mm margin."
    )

if results and worst_pt:
    summary_cols = st.columns(4)
    summary_cols[0].metric("Worst Point", worst_pt.point_name)
    summary_cols[1].metric("Constraint Axis", constraint_label)
    summary_cols[2].metric("Max Q", f"{max_q:.3f}")
    summary_cols[3].metric(
        "Headroom" if overall else "Excess",
        f"{constraint_headroom:.2f} mm" if overall else f"{constraint_overrun:.2f} mm",
    )

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

    def _allowance_df(allowances: list) -> pd.DataFrame:
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
        st.caption("Other 5 axes stay fixed at the current 6DoF values.")
        st.dataframe(_allowance_df(conditional), use_container_width=True, hide_index=True)

    with col2:
        st.markdown(f"**Standalone / 単独許容量 ({ref_mode})**")
        st.caption("Only the selected axis changes from the chosen reference state.")
        st.dataframe(_allowance_df(standalone), use_container_width=True, hide_index=True)

# --- 4.4 Detailed diagnostics ---
if results:
    with st.expander("Detailed Diagnostics / 詳細診断", expanded=False):
        if worst_pt:
            st.subheader("Reference Indicators / 参考指標 (3D)")
            ref_cols = st.columns(3)
            ref_cols[0].metric("Effective Displacement (3D)", f"{worst_pt.effective_displacement_3d_mm:.2f} mm")
            ref_cols[1].metric("Max Consumption Q", f"{max_q:.3f}")
            ref_cols[2].metric("Mag (translation norm)", f"{mag:.2f} mm")

        st.subheader("Distance vs Margin Consumption / 距離 vs マージン消費率")
        scatter_data = pd.DataFrame({
            "Point": [pr.point_name for pr in results],
            "Distance from ISO (mm)": [pr.distance_from_iso_mm for pr in results],
            "Max Q": [max(pr.margin_consumption_ratio) for pr in results],
        })
        st.scatter_chart(
            scatter_data,
            x="Distance from ISO (mm)",
            y="Max Q",
            color=None,
            use_container_width=True,
        )

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
