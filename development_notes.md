# 開発メモ — tenkizu プロジェクト

Claude Codeとのやりとりで構築・改修した内容を記録する。

---

## プロジェクト作成の経緯（2026-04-08）

### 参考プロジェクト

`/Users/masahiro/projects/ageostrophic` を参考に構築。  
ageostrophicプロジェクトは京都大学RISHの**EPSW**（週間アンサンブル予報）GRIB2を使い、  
300hPa非地衡風・高度・発散の天気図を生成するツール。

### 出発点

`/Users/masahiro/projects/tenkizu/` には以下が既存だった：
- `kurora_tenkizu.py` — 黒良さんのNoteをベースにしたGSM 500hPa天気図スクリプト（Notebook変換版）
- `kurora_tenkizu.ipynb` — 元となるJupyter Notebook
- `data_gsm/` — サンプルGRIB2データ（2017/12/10 12UTC等）

`kurora_tenkizu.py` は日時・予報時間がハードコードされており、`plt.show()` のみで保存機能がなかった。

---

## 実施した改修・新規作成

### 1. kurora_tenkizu.py の改修

**改修前の課題:**
- 日時・予報時間がスクリプト内にハードコード
- `plt.show()` のみで PNG 保存なし
- データファイルがなければエラーで停止

**改修内容（3段階）:**

#### 第1段階: 引数対応・PNG保存対応
- `argparse` でコマンドライン引数を受け取るように変更
- 引数: `init_time`（YYYYMMDDHH）, `forecast_time`（DDHH）, `level`（hPa）
- `plt.show()` → `plt.savefig("output/...")` に変更
- `output/` ディレクトリを自動作成

#### 第2段階: データ自動ダウンロード機能の追加
- `ensure_file()` 関数を追加
- 指定されたGRIB2ファイルが `data_gsm/` にない場合、RISHサーバーから自動取得
- ストリーミングダウンロード（65KBチャンク、進捗表示付き）
- HTTP エラー・接続エラー時はファイルを削除してFalseを返す

#### 第3段階: 複数FT一括描画（n_steps引数の追加）
- 引数を `init_time start_ft n_steps [level]` に変更
- `build_ft_list(start_ddhh, n_steps)` で開始FTから6h間隔のFTリストを生成
- 描画ロジックを `plot_one()` 関数に切り出し
- `main()` でリストをループし複数PNGを連続生成
- ダウンロード失敗のFTはスキップして続行

#### 第4段階: 画面表示の追加
- `plt.savefig()` → `print()` → `plt.show()` → `plt.close()` の順に変更
- PNG保存後に各FTの天気図をウィンドウ表示してから次へ進む

### 2. download_gsm.py の新規作成（ageostrophicの download_epsw.py を参考）

- RISHサーバーのディレクトリをスクレイピングしてGSMファイル一覧を取得
- 既存ファイルはスキップ
- `--date`, `--hour`, `--start`, `--end`, `--ft` オプションに対応
- 自動検索モード（引数なし）: 最近7日間を遡って最新データを探す

### 3. run_pipeline.sh の新規作成

- `download_gsm.py` → `kurora_tenkizu.py` を一括実行
- 複数のcondaパスに自動対応

### 4. ドキュメント整備

- `README.md`: 使い方・FD形式の説明・描画仕様・出力ファイル名仕様
- `CLAUDE.md`: Claude Code向けプロジェクト説明
- `.gitignore`: `data_gsm/`, `output/` 等を除外

---

## コマンドライン引数の最終仕様

```
python kurora_tenkizu.py <init_time> <start_ft> <n_steps> [level]
```

| 引数 | 型 | 説明 | 例 |
|------|----|------|----|
| `init_time` | str | 初期時刻 YYYYMMDDHH（UTC） | `2017121012` |
| `start_ft` | str | 最初の予報時間 DDHH形式 | `0000`, `0100` |
| `n_steps` | int | 作成する枚数（6h間隔） | `1`, `5` |
| `level` | int | 気圧面 hPa（省略可） | `500`（デフォルト） |

**使用例:**
```bash
python kurora_tenkizu.py 2017121012 0000 1   # 初期値1枚
python kurora_tenkizu.py 2017121012 0000 5   # FT0h〜FT24h（5枚）
python kurora_tenkizu.py 2017121012 0100 3   # FT24h〜FT36h（3枚）
```

---

## DDHH形式について

GSMファイル名の `FD{DDHH}` は `DD=日数、HH=時間` を組み合わせた形式。  
**FT（時間数）= DD × 24 + HH**

| FD値 | FT |
|------|----|
| `0000` | 0h（初期値） |
| `0006` | 6h |
| `0018` | 18h |
| `0100` | 24h |
| `0112` | 36h |
| `0200` | 48h |
| `0300` | 72h |

---

## 設計上の判断

- **6h固定ステップ**: GSMデータは0〜72hが6h間隔、72h以降は12h間隔だが、  
  ステップ間隔は固定6hとし、ファイルがなければ自動DLを試みてスキップする設計にした。
- **描画ロジックの分離**: `plot_one()` 関数に切り出すことで、ループ処理と描画の責務を分離。
- **データ自動取得**: `download_gsm.py` を別途実行しなくても `kurora_tenkizu.py` 単体で動作完結する。

---

## Git履歴

| コミット | 内容 |
|--------|------|
| `5f9c936` | 初期コミット: プロジェクト全体の整備 |
| `0522a96` | データ未存在時の自動ダウンロード機能追加 |
| `f66ecf8` | n_steps引数追加・複数FT一括描画対応 |
| `ffdd522` | PNG保存後に画面表示（plt.show）を追加 |
