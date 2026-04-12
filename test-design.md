# テスト設計書

## 1. 文書目的

本書は、許容領域シミュレータのテスト方針、テスト観点、具体的テストケースを定義する。

参照:
- math-design.md（数理設計書）セクション 23
- algorithm-design.md（アルゴリズム設計書）
- data-model-design.md（データモデル設計書）

## 2. テスト分類

| 分類 | 対象 | ファイル |
|------|------|---------|
| Sanity Check | math-design 23 の基本性質 | test_geometry.py |
| 単体テスト | 各モジュールの関数 | test_geometry.py, test_uncertainty.py, test_decision.py, test_allowance.py |
| 境界値テスト | マージン境界、ゼロ、極端な値 | 各テストファイル |
| シナリオテスト | 臨床的に意味のある条件の組み合わせ | test_decision.py, test_allowance.py |

## 3. Sanity Check（math-design セクション 23）

### SC-1: ゼロ入力（math-design 23.1）

```
条件: 全 6 軸 = 0
評価点: 任意の p_i
期待: Δp_i = [0, 0, 0]
```

### SC-2: 並進のみ（math-design 23.2）

```
条件: rotation = pitch = roll = 0, vertical = 3.0, longitudinal = 2.0, lateral = 1.0
評価点: 複数の異なる点
期待: ∀i: Δp_i = [1.0, 2.0, 3.0]（= T = [lateral, long, vertical]）
```

### SC-3: 原点の不動点（math-design 23.3）

```
条件: vertical = longitudinal = lateral = 0, 回転は任意（例: rotation = 5.0°）
評価点: p = [0, 0, 0]
期待: Δp = [0, 0, 0]
```

### SC-4: 遠位点依存（math-design 23.4）

```
条件: rotation = 2.0°, pitch = 0, roll = 0, 並進 = 0
評価点: p_near = [0, 0, 50], p_far = [0, 0, 100]
期待: ||Δp_far^rot|| > ||Δp_near^rot||
```

## 4. geometry.py のテスト

### 4.1 回転行列

#### G-1: 単位行列

```
条件: rotation = pitch = roll = 0
期待: R = I（3×3 単位行列）
許容誤差: 1e-10
```

#### G-2: z 軸 90° 回転

```
条件: rotation = 90°, pitch = 0, roll = 0
期待: R_z(90°) = [[0, -1, 0], [1, 0, 0], [0, 0, 1]]
許容誤差: 1e-10
```

#### G-3: x 軸 90° 回転

```
条件: rotation = 0, pitch = 90°, roll = 0
期待: R_x(90°) = [[1, 0, 0], [0, 0, -1], [0, 1, 0]]
許容誤差: 1e-10
```

#### G-4: y 軸 90° 回転

```
条件: rotation = 0, pitch = 0, roll = 90°
期待: R_y(90°) = [[0, 0, 1], [0, 1, 0], [-1, 0, 0]]
許容誤差: 1e-10
```

#### G-5: 回転行列の直交性

```
条件: rotation = 3.5°, pitch = -2.1°, roll = 1.8°
期待: R^T @ R ≈ I
許容誤差: 1e-10
```

#### G-6: 回転行列の行列式

```
条件: 任意の回転角
期待: det(R) ≈ 1.0
許容誤差: 1e-10
```

### 4.2 変位計算

#### G-7: 並進のみの変位

```
条件: lateral = 5.0, longitudinal = -3.0, vertical = 2.0, 回転 = 0
評価点: p = [10, 20, 30]
期待: Δp = [5.0, -3.0, 2.0]（全点同一）
```

#### G-8: 小角回転での近似一致

```
条件: rotation = 1.0°, 並進 = 0
評価点: p = [0, 0, 100]（z 軸上 100mm）
期待:
  - 回転変位の大きさ ≈ 100 × 1.0 × π/180 ≈ 1.745 mm
  - 厳密計算との差 < 0.1%
```

#### G-9: 寄与分離の整合性

```
条件: 任意の 6DoF
評価点: 任意の p
期待: translation_contribution + rotation_contribution = displacement
許容誤差: 1e-10
```

### 4.3 合成回転順序

#### G-10: 回転順序の確認

```
条件: rotation = 10°, pitch = 5°, roll = 3°
評価点: p = [50, 30, 20]
検証:
  R = R_z(10°) @ R_x(5°) @ R_y(3°)
  Δp = [lateral, long, vertical] + (R - I) @ p
  手計算値と一致すること
```

## 5. uncertainty.py のテスト

#### U-1: RSS 合成

```
条件: u_identify = 1.0, u_surrogate = 2.0, u_registration = 1.0, u_intrafraction = 1.0, u_model = 0.5
期待: total = sqrt(1 + 4 + 1 + 1 + 0.25) = sqrt(7.25) ≈ 2.6926
許容誤差: 1e-4
```

#### U-2: 全ゼロ

```
条件: 全成分 = 0
期待: total = 0.0
```

#### U-3: 単一成分

```
条件: u_identify = 3.0, 他 = 0
期待: total = 3.0
```

#### U-4: 保守的変位

```
条件: displacement_k = 5.0, U_k = 2.5, z = 2.0
期待: C = abs(5.0) + 2.0 × 2.5 = 10.0
```

#### U-5: 負の変位の保守的変位

```
条件: displacement_k = -5.0, U_k = 2.5, z = 2.0
期待: C = abs(-5.0) + 2.0 × 2.5 = 10.0
```

## 6. decision.py のテスト

#### D-1: 明確な Pass

```
条件: C_i,k = 5.0, M_k = 10.0
期待: pass = True, R_i,k = 5.0, Q_i,k = 0.5
```

#### D-2: 明確な Fail

```
条件: C_i,k = 12.0, M_k = 10.0
期待: pass = False, R_i,k = -2.0, Q_i,k = 1.2
```

#### D-3: 境界ちょうど（Pass）

```
条件: C_i,k = 10.0, M_k = 10.0
期待: pass = True, R_i,k = 0.0, Q_i,k = 1.0
```

#### D-4: 境界わずかに超過（Fail）

```
条件: C_i,k = 10.001, M_k = 10.0
期待: pass = False
```

#### D-5: マージン = 0

```
条件: C_i,k = 0.5, M_k = 0.0
期待: pass = False, Q_i,k = inf
```

#### D-6: 最悪点抽出

```
条件:
  point_A: Q = (0.5, 0.6, 0.7)
  point_B: Q = (0.3, 0.9, 0.4)
  point_C: Q = (0.8, 0.2, 0.3)
期待:
  worst_point = point_B（max Q = 0.9）
  worst_axis = y
```

#### D-7: 全体判定（全 Pass）

```
条件: 3 点すべて overall_pass_fail = True
期待: pass_all = True
```

#### D-8: 全体判定（1 点 Fail）

```
条件: 2 点 Pass, 1 点 Fail
期待: pass_all = False
```

## 7. allowance.py のテスト

#### A-1: 並進のみ・対称な許容量

```
条件:
  評価点: p = [0, 0, 100]
  マージン: M_x = M_y = M_z = 10.0
  不確かさ: 全軸 U = 1.0, z = 2.0
  基準状態: 全軸 = 0

lateral 軸の単独許容量を探索:
  C = abs(lateral) + 2.0 × 1.0 = abs(lateral) + 2.0
  C ≤ 10.0 → abs(lateral) ≤ 8.0
  期待: allowable_min ≈ -8.0, allowable_max ≈ +8.0
  許容誤差: 0.01 mm
```

#### A-2: 回転の許容量

```
条件:
  評価点: p = [100, 0, 0]（x 軸上 100mm）
  マージン: M_y = 10.0
  不確かさ: U_y = 1.0, z = 2.0
  基準状態: 全軸 = 0

rotation (z 軸まわり) の単独許容量を探索:
  Δy ≈ 100 × sin(θ_r) → C_y ≈ 100 × sin(θ_r) + 2.0
  100 × sin(θ_r) + 2.0 ≤ 10.0 → sin(θ_r) ≤ 0.08 → θ_r ≤ ≈ 4.59°
  期待: allowable_max ≈ +4.59°（厳密値との差 < 0.01°）
```

#### A-3: 既に Fail の場合

```
条件:
  評価点: p = [0, 0, 100]
  マージン: M_z = 5.0
  不確かさ: U_z = 1.0, z = 2.0
  vertical = 10.0（C_z = 10.0 + 2.0 = 12.0 > 5.0）

期待:
  status = "exceeded"
  allowable_min = allowable_max = 10.0
  remaining = 0.0
```

#### A-4: 評価点なしの場合

```
条件: 評価点 = []
期待:
  status = "no_points"
  allowable_min = 探索下限
  allowable_max = 探索上限
```

#### A-5: 条件付き許容量が単独より狭い

```
条件:
  評価点: p = [100, 0, 0]
  基準状態: zero_based
  現在値: vertical = 5.0, 他 = 0

vertical 軸:
  単独許容量 > 条件付き許容量 であること（他軸の影響がない分、単独の方が広い）
```

注記: vertical は並進なので、他の並進軸が 0 であれば単独と条件付きは同じになる場合がある。回転軸が非ゼロのときにこの差が明確になる。

#### A-6: 二分探索の精度

```
条件: A-1 と同じ
検証:
  - allowable_max と理論値 8.0 の差 ≤ 0.01 mm
  - allowable_min と理論値 -8.0 の差 ≤ 0.01 mm
```

## 8. シナリオテスト

### S-1: 並進のみ、回転ゼロ

```
条件:
  vertical = 3.0, longitudinal = 2.0, lateral = 1.0
  rotation = pitch = roll = 0
  評価点: p = [50, 80, 120]
  マージン: M_x = 10, M_y = 10, M_z = 10
  不確かさ: 全 0, z = 0

期待:
  Δp = [1.0, 2.0, 3.0]（全点同一）
  C = [1.0, 2.0, 3.0]
  Q = [0.1, 0.2, 0.3]
  pass_all = True
```

### S-2: 回転のみ、遠位点で Fail

```
条件:
  全並進 = 0
  rotation = 5.0°
  評価点: p = [0, 0, 150]（z 軸上 150mm）
  マージン: M_x = 10, M_y = 10, M_z = 10
  不確かさ: 全 0, z = 0

期待:
  回転変位 ≈ 150 × sin(5°) ≈ 13.1 mm
  → x 方向に約 -13.1 mm（z 軸まわり回転なので y 成分のみ影響...）
  ※ 正確には R_z(5°) で p = [0, 0, 150] を回転すると z 軸上なので変位 = 0
  → p を [150, 0, 0] に変更して検証:
  R_z(5°) @ [150, 0, 0] = [150cos5°, 150sin5°, 0] ≈ [149.43, 13.08, 0]
  Δp ≈ [-0.57, 13.08, 0]
  C_y = 13.08 > M_y = 10 → Fail
```

### S-3: 不確かさで Fail になるケース

```
条件:
  全 6 軸 = 0
  評価点: p = [0, 0, 100]
  マージン: M_z = 3.0
  不確かさ: U_z = 2.0, z = 2.0
  C_z = 0 + 2.0 × 2.0 = 4.0 > 3.0

期待: Fail（変位ゼロでも不確かさで超過）
```

### S-4: マージンぎりぎりの Pass

```
条件:
  lateral = 5.0, 他 = 0
  評価点: p = [0, 0, 100]
  マージン: M_x = 8.0
  不確かさ: U_x = 1.5, z = 2.0
  C_x = 5.0 + 2.0 × 1.5 = 8.0 ≤ 8.0

期待: Pass（境界上は Pass）
```

## 9. テスト実行方法

```
# 全テスト実行
pytest tests/ -v

# モジュール別実行
pytest tests/test_geometry.py -v
pytest tests/test_uncertainty.py -v
pytest tests/test_decision.py -v
pytest tests/test_allowance.py -v

# sanity check のみ
pytest tests/test_geometry.py -v -k "sanity"
```

## 10. 許容誤差の基準

| 対象 | 許容誤差 |
|------|---------|
| 回転行列の要素 | 1e-10 |
| 変位計算 (mm) | 1e-6 |
| 不確かさ合成 (mm) | 1e-6 |
| 許容量探索・並進 (mm) | 0.01 |
| 許容量探索・回転 (°) | 0.001 |
| 小角近似との比較 | 1%（概算確認用） |
