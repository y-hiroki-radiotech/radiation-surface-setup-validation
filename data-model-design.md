# データモデル設計書

## 1. 文書目的

本書は、許容領域シミュレータで使用する全データモデルを定義する。  
各モデルのフィールド、型、単位、制約、算出値の計算式、モデル間の関係を記述する。

参照:
- math-design.md（数理設計書）
- requirements-spec.md（要件定義書）セクション 8, 12

## 2. 座標系マッピング

### 2.1 UI 表示名と内部座標の対応

| UI 表示名 | 内部変数名 | 座標軸 | 単位 | 種別 |
|-----------|-----------|--------|------|------|
| Vertical | vertical | z | mm | 並進 |
| Long | longitudinal | y | mm | 並進 |
| Lateral | lateral | x | mm | 並進 |
| Rotation | rotation | z 軸まわり | deg (内部 rad) | 回転 |
| Pitch | pitch | x 軸まわり | deg (内部 rad) | 回転 |
| Roll | roll | y 軸まわり | deg (内部 rad) | 回転 |

### 2.2 マージンと座標軸の対応

| UI マージン名 | 内部変数名 | 座標軸 | 対応する並進 |
|--------------|-----------|--------|------------|
| M_lateral | m_x | x | Lateral |
| M_long | m_y | y | Long |
| M_vertical | m_z | z | Vertical |

### 2.3 並進ベクトルの構成順序

math-design.md セクション 6 より:

`T = [lateral, longitudinal, vertical]^T = [x, y, z]^T`

## 3. 入力モデル

### 3.1 EvaluationPoint

評価点。ISO センターを原点とする座標で定義する。

| フィールド | 型 | 単位 | 制約 | 説明 |
|-----------|-----|------|------|------|
| name | str | — | 空文字不可、一意 | 点名 |
| x | float | mm | — | Lateral 座標 |
| y | float | mm | — | Long 座標 |
| z | float | mm | — | Vertical 座標 |

算出値:
- `distance_from_iso: float (mm)` = `sqrt(x² + y² + z²)`（math-design セクション 10）

### 3.2 MarginProtocol

軸別セットアップマージン。

| フィールド | 型 | 単位 | 制約 | 説明 |
|-----------|-----|------|------|------|
| m_x | float | mm | ≥ 0 | Lateral マージン |
| m_y | float | mm | ≥ 0 | Long マージン |
| m_z | float | mm | ≥ 0 | Vertical マージン |

注記:
- マージン = 0 は許容するが、不確かさ > 0 の場合は常に Fail となる
- UI では Vertical / Long / Lateral の順で表示し、内部で m_z / m_y / m_x に変換する

### 3.3 AxisUncertainty

1 軸分の不確かさ成分。

| フィールド | 型 | 単位 | 制約 | 説明 |
|-----------|-----|------|------|------|
| u_identify | float | mm | ≥ 0 | 装置測定不確かさ |
| u_surrogate | float | mm | ≥ 0 | 体表面と標的位置の乖離 |
| u_registration | float | mm | ≥ 0 | ROI 設定不確かさ |
| u_intrafraction | float | mm | ≥ 0 | 治療中の体動・呼吸 |
| u_model | float | mm | ≥ 0 | 幾何モデル簡略化 |

算出値:
- `total: float (mm)` = `sqrt(u_identify² + u_surrogate² + u_registration² + u_intrafraction² + u_model²)`（math-design セクション 12.4）

### 3.4 UncertaintyModel

軸別不確かさの集合。

| フィールド | 型 | 説明 |
|-----------|-----|------|
| x | AxisUncertainty | Lateral 軸の不確かさ |
| y | AxisUncertainty | Long 軸の不確かさ |
| z | AxisUncertainty | Vertical 軸の不確かさ |

算出値:
- `totals: tuple[float, float, float]` = `(x.total, y.total, z.total)`

### 3.5 SetupState

6DoF 現在値。スライダーの値をそのまま保持する。

| フィールド | 型 | 単位 | 説明 |
|-----------|-----|------|------|
| vertical | float | mm | Vertical 並進 |
| longitudinal | float | mm | Long 並進 |
| lateral | float | mm | Lateral 並進 |
| rotation | float | deg | z 軸まわり回転 |
| pitch | float | deg | x 軸まわり回転 |
| roll | float | deg | y 軸まわり回転 |

メソッド:
- `to_translation_vector() -> ndarray(3,)`: `[lateral, longitudinal, vertical]`（math-design セクション 6）
- `zero() -> SetupState`: 全フィールド 0 の状態を返すクラスメソッド

単独許容量の基準状態としても同型を使用する。

### 3.6 SafetyFactor

| フィールド | 型 | 制約 | 説明 |
|-----------|-----|------|------|
| z | float | ≥ 0 | 安全係数 |

代表値: 1.0, 1.96, 2.0（math-design セクション 13）

## 4. 出力モデル

### 4.1 PointResult

1 評価点に対する判定結果。

| フィールド | 型 | 単位 | 算出元 | 説明 |
|-----------|-----|------|--------|------|
| point_name | str | — | 入力 | 評価点名 |
| distance_from_iso_mm | float | mm | `\|\|p_i\|\|_2` | ISO からの距離 |
| displacement | tuple[float, float, float] | mm | `Δp_i = T + (R-I)p_i` | 軸別変位 (Δx, Δy, Δz) |
| translation_contribution | tuple[float, float, float] | mm | `T` | 並進寄与 |
| rotation_contribution | tuple[float, float, float] | mm | `(R-I)p_i` | 回転寄与 |
| effective_displacement_3d_mm | float | mm | `\|\|Δp_i\|\|_2` | 3D 実効変位 |
| translation_only_mm | float | mm | `\|\|T\|\|_2` | 並進のみの大きさ |
| rotation_induced_mm | float | mm | `\|\|(R-I)p_i\|\|_2` | 回転起因の大きさ |
| uncertainty_mm | tuple[float, float, float] | mm | `(U_x, U_y, U_z)` | 軸別総合不確かさ |
| conservative_displacement_mm | tuple[float, float, float] | mm | `C_i,k = abs(Δp_i,k) + z×U_k` | 軸別保守的変位 |
| margin_remaining_mm | tuple[float, float, float] | mm | `R_i,k = M_k - C_i,k` | 軸別残余マージン |
| axiswise_pass_fail | tuple[bool, bool, bool] | — | `C_i,k ≤ M_k` | 軸別 Pass/Fail |
| overall_pass_fail | bool | — | 全軸 Pass | 総合判定 |
| margin_consumption_ratio | tuple[float, float, float] | — | `Q_i,k = C_i,k / M_k` | 軸別消費率 |

数式参照: math-design セクション 8, 9, 14, 16, 17

タプルの順序はすべて `(x, y, z)` = `(Lateral, Long, Vertical)` とする。

### 4.2 AxisAllowance

1 軸の許容量。

| フィールド | 型 | 単位 | 説明 |
|-----------|-----|------|------|
| axis_name | str | — | 軸名（"vertical", "longitudinal", "lateral", "rotation", "pitch", "roll"） |
| current_value | float | mm or deg | 現在値 |
| allowable_min | float | mm or deg | 許容最小値 |
| allowable_max | float | mm or deg | 許容最大値 |
| remaining_negative | float | mm or deg | `current_value - allowable_min` |
| remaining_positive | float | mm or deg | `allowable_max - current_value` |
| limiting_point | str | — | 制約を与える評価点名 |
| limiting_axis | str | — | 制約を与える座標軸（"x", "y", "z"） |
| status | str | — | "within" / "exceeded" / "no_points" |

数式参照: math-design セクション 19, 20

### 4.3 SimulationResult

シミュレーション全体の結果。

| フィールド | 型 | 説明 |
|-----------|-----|------|
| pass_fail | bool | 全体判定 |
| worst_point | PointResult | 最悪点の結果 |
| worst_axis | str | ボトルネック軸（max Q_i,k の軸名） |
| all_point_results | list[PointResult] | 全評価点の結果 |
| conditional_allowances | list[AxisAllowance] | 条件付き許容量（6 軸） |
| standalone_allowances | list[AxisAllowance] | 単独許容量（6 軸） |
| mag_mm | float | 参考指標 `sqrt(lateral² + longitudinal² + vertical²)` |

数式参照: math-design セクション 16.3, 18

## 5. モデル間の関係

```
入力:
  EvaluationPoint[] ──┐
  SetupState ─────────┤
  MarginProtocol ─────┼──→ [計算エンジン] ──→ SimulationResult
  UncertaintyModel ───┤                          ├── pass_fail
  SafetyFactor ───────┘                          ├── worst_point: PointResult
                                                  ├── all_point_results: PointResult[]
                                                  ├── conditional_allowances: AxisAllowance[]
                                                  ├── standalone_allowances: AxisAllowance[]
                                                  └── mag_mm

単独許容量の基準状態:
  SetupState（zero / current / custom）──→ standalone_allowances の計算に使用
```

## 6. 制約と検証規則

### 6.1 入力値の制約

| 対象 | 制約 | 違反時の処理 |
|------|------|------------|
| 評価点名 | 空文字不可、重複不可 | UI でバリデーションエラー |
| マージン値 | ≥ 0 | UI でバリデーションエラー |
| 不確かさ値 | ≥ 0 | UI でバリデーションエラー |
| 安全係数 z | ≥ 0 | UI でバリデーションエラー |
| 並進スライダー | ±50 mm | スライダー範囲で制限 |
| 回転スライダー | ±10° | スライダー範囲で制限 |

### 6.2 算出値の検証

| 対象 | 検証内容 |
|------|---------|
| distance_from_iso | ≥ 0 |
| margin_consumption_ratio | M_k = 0 の場合は inf として扱う |
| overall_pass_fail | axiswise_pass_fail の全 AND と一致する |
