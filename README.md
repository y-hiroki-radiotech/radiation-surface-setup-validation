# 許容領域シミュレータ / Setup Margin Allowance Simulator

放射線治療の体表面位置照合装置 **IDENTIFY** の 6DoF 情報を用いて、セットアップマージンに対する許容領域を評価する Streamlit アプリ。

## 概要 / Overview

IDENTIFY が出力する 6DoF（Vertical / Long / Lateral / Rotation / Pitch / Roll）を剛体変換として扱い、ISO センター基準の評価点群での実効変位を計算。不確かさを加味した保守的変位がセットアップマージン内に収まるかを判定するとともに、各軸の許容範囲（単独・条件付き）を数値探索で求める。

## 機能 / Features

- **現在状態判定**: 6DoF スライダーを動かすと Pass / Fail をリアルタイム更新
- **Fail理由の要約**: 最悪点、制約軸、余裕量または超過量を最上段で即時表示
- **条件付き許容量**: 現在値を固定したまま、各軸があとどこまで動けるかを二分探索
- **単独許容量**: 基準状態（ゼロ / 現在値 / カスタム）を固定した理論的許容範囲
- **評価点の表編集**: 追加評価点をテーブル形式で直接追加・編集・削除
- **不確かさテンプレート**: `default` と `custom` を切り替えて詳細入力を簡略化
- **寄与分離**: 並進寄与と回転寄与を分離表示
- **詳細診断**: 散布図や寄与分離を折りたたみ表示で確認

## 数理モデル / Math Model

座標系（`math-design.md` より）:

| 軸 | 対応 |
|----|------|
| x | Lateral |
| y | Long |
| z | Vertical |

変位計算:

```
Δp_i = T + (R - I) p_i
R = R_z(rotation) @ R_x(pitch) @ R_y(roll)
T = [lateral, longitudinal, vertical]
```

判定条件:

```
C_i,k = |Δp_i,k| + z × U_k ≤ M_k  （全点・全軸）
```

## セットアップ / Setup

[uv](https://docs.astral.sh/uv/) が必要です。

```bash
# 依存関係のインストール
uv sync

# アプリ起動
uv run streamlit run src/app.py

# テスト実行
uv run pytest tests/ -v
```

## UIの使い方 / UI Flow

サイドバーは 3 つの入力ブロックに整理されています。

- **Conditions / 条件**: マージン、安全係数、不確かさテンプレートを設定
- **Evaluation Points / 評価点**: 最遠点を設定し、追加点は表形式で編集
- **Current 6DoF / 現在の6DoF**: 現在値スライダーと単独許容量の基準状態を設定

メイン画面では、最上段に Pass / Fail と制約要因の要約、その下に評価点別結果表と許容量表を表示します。散布図や寄与分離は `Detailed Diagnostics / 詳細診断` にまとめています。

## ディレクトリ構成 / Structure

```
.
├── src/
│   ├── models.py       # データモデル（SetupState, EvaluationPoint, PointResult 等）
│   ├── geometry.py     # 回転行列・変位計算
│   ├── uncertainty.py  # RSS 合成・保守的変位
│   ├── decision.py     # Pass/Fail 判定・最悪点抽出
│   ├── allowance.py    # 二分探索による許容量探索
│   └── app.py          # Streamlit UI
├── tests/
│   ├── test_geometry.py
│   ├── test_uncertainty.py
│   ├── test_decision.py
│   └── test_allowance.py
├── requirements-spec.md    # 要件定義書
├── math-design.md          # 数理設計書
├── data-model-design.md    # データモデル設計書
├── algorithm-design.md     # アルゴリズム設計書
├── ui-design.md            # UI 設計書
├── test-design.md          # テスト設計書
└── pyproject.toml
```

## 注意事項 / Disclaimer

本システムは体表面情報を用いた代理評価であり、真の標的位置を直接保証するものではありません。臨床判断は放射線治療医および医学物理士によるレビューが必要です。

> This tool uses surface surrogate information and does not directly guarantee the true target position. Clinical decisions require review by a radiation oncologist and medical physicist.
