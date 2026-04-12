# アルゴリズム設計書

## 1. 文書目的

本書は、許容領域シミュレータの計算アルゴリズムを定義する。  
変位計算、判定、最悪点抽出、許容量探索の各処理の手順、入出力、エッジケースの扱いを記述する。

参照:
- math-design.md（数理設計書）
- data-model-design.md（データモデル設計書）

## 2. モジュール構成

| モジュール | 責務 | 参照セクション |
|-----------|------|--------------|
| geometry.py | 回転行列生成、変位計算、寄与分離 | 本書 3, 4 |
| uncertainty.py | RSS 合成、保守的変位算出 | 本書 5 |
| decision.py | Pass/Fail 判定、最悪点抽出 | 本書 6, 7 |
| allowance.py | 単独許容量・条件付き許容量の探索 | 本書 8, 9 |

## 3. 回転行列生成

### 3.1 入力
- rotation (deg), pitch (deg), roll (deg)

### 3.2 手順

```
1. degree → radian 変換
   θ_r = rotation × π / 180
   θ_p = pitch × π / 180
   θ_w = roll × π / 180

2. 各軸回転行列の構築
   R_x(θ_p) = [[1, 0, 0], [0, cos(θ_p), -sin(θ_p)], [0, sin(θ_p), cos(θ_p)]]
   R_y(θ_w) = [[cos(θ_w), 0, sin(θ_w)], [0, 1, 0], [-sin(θ_w), 0, cos(θ_w)]]
   R_z(θ_r) = [[cos(θ_r), -sin(θ_r), 0], [sin(θ_r), cos(θ_r), 0], [0, 0, 1]]

3. 合成
   R = R_z(θ_r) @ R_x(θ_p) @ R_y(θ_w)
```

### 3.3 出力
- R: ndarray(3, 3)

### 3.4 参照
- math-design.md セクション 7.4, 7.5

## 4. 変位計算

### 4.1 単点変位

#### 入力
- state: SetupState
- point: EvaluationPoint

#### 手順

```
1. 並進ベクトル構築
   T = [state.lateral, state.longitudinal, state.vertical]

2. 回転行列生成
   R = build_rotation_matrix(state.rotation, state.pitch, state.roll)

3. 評価点ベクトル構築
   p = [point.x, point.y, point.z]

4. 変位計算
   Δp = T + (R - I) @ p

5. 寄与分離
   trans = T
   rot = (R - I) @ p
```

#### 出力
- displacement: ndarray(3,) = (Δx, Δy, Δz)
- translation_contribution: ndarray(3,)
- rotation_contribution: ndarray(3,)

#### 参照
- math-design.md セクション 8, 9

### 4.2 全点変位

全評価点に対して 4.1 を繰り返す。回転行列 R の生成は 1 回だけ行い、全点で共有する。

## 5. 不確かさ合成

### 5.1 軸別 RSS 合成

#### 入力
- axis_uncertainty: AxisUncertainty

#### 手順

```
U_k = sqrt(u_identify² + u_surrogate² + u_registration² + u_intrafraction² + u_model²)
```

#### 出力
- U_k: float (mm)

#### 参照
- math-design.md セクション 12.4

### 5.2 保守的変位

#### 入力
- displacement_k: float（abs(Δp_i,k)）
- U_k: float
- z: float（安全係数）

#### 手順

```
C_i,k = abs(displacement_k) + z × U_k
```

#### 出力
- C_i,k: float (mm)

#### 参照
- math-design.md セクション 14.1

## 6. 判定

### 6.1 点・軸別判定

#### 入力
- C_i,k: float（保守的変位）
- M_k: float（マージン）

#### 手順

```
pass = (C_i,k <= M_k)
```

#### 出力
- pass: bool

#### 参照
- math-design.md セクション 16.1

### 6.2 点ごとの総合判定

```
pass_i = (C_i,x <= M_x) and (C_i,y <= M_y) and (C_i,z <= M_z)
```

#### 参照
- math-design.md セクション 16.2

### 6.3 全体判定

```
pass_all = all(pass_i for i in evaluation_points)
```

#### 参照
- math-design.md セクション 16.3

### 6.4 全点判定の統合処理

#### 入力
- state: SetupState
- points: list[EvaluationPoint]
- margin: MarginProtocol
- uncertainty: UncertaintyModel
- z: float

#### 手順

```
1. R = build_rotation_matrix(state.rotation, state.pitch, state.roll)
2. T = state.to_translation_vector()
3. U = (uncertainty.x.total, uncertainty.y.total, uncertainty.z.total)
4. M = (margin.m_x, margin.m_y, margin.m_z)

5. for each point p_i:
   a. Δp_i = T + (R - I) @ p_i
   b. trans = T
   c. rot = (R - I) @ p_i
   d. for each axis k in (x, y, z):
      C_i,k = abs(Δp_i[k]) + z × U[k]
      R_i,k = M[k] - C_i,k
      Q_i,k = C_i,k / M[k]  (M[k] = 0 の場合は inf)
      pass_i,k = (C_i,k <= M[k])
   e. PointResult を構築

6. pass_all = all(pr.overall_pass_fail for pr in results)
7. SimulationResult を構築
```

## 7. 最悪点・ボトルネック抽出

### 7.1 最悪点

#### 手順

```
worst_point = argmax_i max(Q_i,x, Q_i,y, Q_i,z)
```

全評価点のうち、最大マージン消費率 Q が最も大きい点を最悪点とする。

#### 参照
- math-design.md セクション 18

### 7.2 ボトルネック軸

```
worst_axis = argmax_(i,k) Q_i,k
```

全点全軸のうち Q_i,k が最大のものの軸を制約因子とする。

#### 参照
- math-design.md セクション 17.3

### 7.3 同率の場合

複数の点や軸が同率最大の場合、最初に見つかったものを採用する。

## 8. 条件付き許容量探索

### 8.1 定義

対象軸 `a` の条件付き許容量: 現在の SetupState で他 5 軸を固定し、軸 `a` のみを変化させたときの Pass 領域。

#### 参照
- math-design.md セクション 20

### 8.2 判定関数

```
G_a(u; s_current):
  s_test = s_current のコピー
  s_test の軸 a を u に設定
  全評価点に対して judge_all(s_test, ...) を実行
  return pass_all
```

### 8.3 探索手順

```
入力:
  axis: 対象軸名
  state: 現在の SetupState
  points: list[EvaluationPoint]
  margin: MarginProtocol
  uncertainty: UncertaintyModel
  z: float

手順:
  1. 現在値 u_current = state の axis 値を取得

  2. 現在状態が Fail かチェック
     if not G_a(u_current; state):
       return AxisAllowance(status="exceeded", min=u_current, max=u_current, ...)

  3. 正方向探索
     search_max = 探索上限（並進: +50mm, 回転: +10°）
     u_pos = find_boundary(u_current, search_max, +step)
     if u_pos が見つかった:
       u_max = bisect(u_pos - step, u_pos)  # Pass→Fail 境界
     else:
       u_max = search_max  # 全域 Pass

  4. 負方向探索
     search_min = 探索下限（並進: -50mm, 回転: -10°）
     u_neg = find_boundary(u_current, search_min, -step)
     if u_neg が見つかった:
       u_min = bisect(u_neg + step, u_neg)  # Fail←Pass 境界
     else:
       u_min = search_min  # 全域 Pass

  5. 制約点・制約軸の特定
     u_max の直前で最悪だった点と軸を記録

  6. AxisAllowance を構築して返す
```

### 8.4 粗探索の刻み幅

| 軸種別 | 刻み幅 |
|--------|--------|
| 並進 | 0.5 mm |
| 回転 | 0.1° |

### 8.5 二分探索

```
bisect(u_pass, u_fail):
  while abs(u_pass - u_fail) > tolerance:
    u_mid = (u_pass + u_fail) / 2
    if G_a(u_mid):
      u_pass = u_mid
    else:
      u_fail = u_mid
  return u_pass  # Pass 側の境界値を返す
```

停止条件:
- 並進: 区間幅 ≤ 0.01 mm
- 回転: 区間幅 ≤ 0.001°
- 反復数 ≤ 50（安全弁）

#### 参照
- math-design.md セクション 21.3, 21.4

### 8.6 制約点の記録

境界値が確定した時点で、その値での全点判定を実行し、最大 Q_i,k を持つ点と軸を limiting_point / limiting_axis とする。

## 9. 単独許容量探索

### 9.1 定義

対象軸 `a` の単独許容量: 基準状態で他 5 軸を固定し、軸 `a` のみを変化させたときの Pass 領域。

#### 参照
- math-design.md セクション 19

### 9.2 基準状態の 3 モード

| モード | 他 5 軸の値 | 用途 |
|--------|-----------|------|
| zero_based | すべて 0 | その軸単体の理論的許容範囲 |
| current_based | 現在のスライダー値 | 条件付き許容量と同じ（比較用） |
| custom | ユーザー指定の基準値 | 任意のシナリオ検討 |

### 9.3 判定関数

```
F_a(u; s_ref):
  s_test = s_ref のコピー
  s_test の軸 a を u に設定
  全評価点に対して judge_all(s_test, ...) を実行
  return pass_all
```

### 9.4 探索手順

条件付き許容量（セクション 8.3）と同一の手順。ただし:
- 開始値: 基準状態の軸 `a` の値（zero_based の場合は 0）
- 他 5 軸: 基準状態の値で固定

## 10. 全軸一括計算

### 10.1 手順

```
1. 条件付き許容量: 6 軸すべてについてセクション 8 を実行
2. 単独許容量: 6 軸すべてについてセクション 9 を実行
3. SimulationResult に格納
```

### 10.2 計算量の見積もり

1 軸の探索:
- 粗探索: 最大 200 ステップ（±50mm / 0.5mm 刻みの場合）
- 二分探索: 最大 50 回
- 各ステップで全点判定

全体:
- 6 軸 × 2 方向 × (粗探索 + 二分探索) × 全点数
- 評価点 10 点の場合: 概算 6 × 2 × 250 × 10 = 30,000 回の判定
- 条件付き + 単独で 60,000 回

応答性:
- NumPy のベクトル演算を活用すれば、評価点 10 点程度では実用的な時間内に完了する見込み
- 点群が 100 点以上になる場合は、行列一括演算の最適化を検討

## 11. エッジケースの処理

### 11.1 評価点が 0 個

| 処理箇所 | 動作 |
|---------|------|
| judge_all | pass_fail = None（判定不能） |
| worst_point | None |
| allowance 探索 | status = "no_points", min/max は探索範囲端 |
| UI | 「評価点を入力してください」と警告 |

### 11.2 評価点が ISO 中心 (0,0,0)

- 回転寄与 = (R-I) @ [0,0,0] = [0,0,0]
- 変位 = 並進のみ
- 正常に処理される
- UI で「この点は回転の影響を受けません」と注記

### 11.3 マージンが 0 の軸

- C_i,k = abs(Δp_i,k) + z × U_k
- U_k > 0 かつ M_k = 0 なら、全 6 軸 = 0 でも C_i,k > 0 = M_k → Fail
- Q_i,k = C_i,k / 0 = inf
- UI で「マージン 0: この軸は常に Fail」と警告

### 11.4 全 6 軸がゼロ

- Δp_i = [0,0,0]（math-design 23.1）
- C_i,k = 0 + z × U_k = z × U_k
- 不確かさ分だけマージンを消費
- 正常に判定

### 11.5 全軸で既に Fail

- 全条件付き許容量: status = "exceeded"
- UI に「現在値で全軸マージン超過」と表示

### 11.6 並進のみ（回転 = 0）

- R = I → (R-I) = 0
- Δp_i = T（全点同一変位）
- math-design 23.2 の性質

### 11.7 回転のみ（並進 = 0）

- T = [0,0,0]
- Δp_i = (R-I) @ p_i
- ISO 上の点は不動点（math-design 23.3）
