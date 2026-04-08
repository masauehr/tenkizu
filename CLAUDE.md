# CLAUDE.md — tenkizu プロジェクト

## プロジェクト概要

黒良さんのNoteをベースにしたGSM 500hPa天気図作成ツール。  
GSM（全球スペクトルモデル）GRIB2データを京都大学RISHサーバーからダウンロードし、  
500hPa等高度線・相対渦度の天気図を生成する。

---

## ファイル構成と役割

| ファイル | 役割 |
|--------|------|
| `kurora_tenkizu.py` | **天気図描画メインスクリプト**。引数でinit_time/FT/気圧面を指定してPNG出力 |
| `download_gsm.py` | **GSMデータダウンロードスクリプト**。RISHサーバーから全球GSM GRIB2を取得 |
| `run_pipeline.sh` | **パイプライン**。ダウンロード→描画を一括実行 |
| `data_gsm/` | GSM GRIB2データ保存先（Gitから除外） |
| `output/` | 生成天気図PNG保存先（Gitから除外） |

---

## GSMファイル命名規則

```
Z__C_RJTD_{YYYYMMDD}{HH}0000_GSM_GPV_Rgl_FD{DDHH}_grib2.bin
```

- `Rgl`: 全球（Regional global）
- `FD{DDHH}`: 予報時間（DD=日数、HH=時間数）
  - `FD0000` = FT=0h（初期値）
  - `FD0018` = FT=18h
  - `FD0100` = FT=24h（DD=1日、HH=0時間）
  - `FD0112` = FT=36h

**FT計算式**: `FT[h] = DD × 24 + HH`

---

## 実行環境

- **Python環境**: `conda activate met_env_310`（Python 3.10）
- **必要ライブラリ**: pygrib, xarray, metpy, matplotlib, cartopy, requests, beautifulsoup4
- **PROJ_LIBパス**: `/opt/anaconda3/envs/met_env_310/share/proj`（kurora_tenkizu.py内で設定済み）

---

## スクリプト引数仕様

### kurora_tenkizu.py

```
python kurora_tenkizu.py <init_time> [forecast_time] [level]
```

- `init_time`: 初期時刻 YYYYMMDDHH（UTC）例: `2017121012`
- `forecast_time`: 予報時間 DDHH形式（デフォルト: `0000`）
- `level`: 気圧面 hPa（デフォルト: `500`）

### download_gsm.py

```
python download_gsm.py [--date YYYYMMDD] [--hour {0,12}]
                       [--start YYYYMMDD] [--end YYYYMMDD]
                       [--ft FT [FT ...]]
```

---

## 描画要素

| 要素 | 表現 |
|------|------|
| 500hPa等高度線 | 黒細線60m間隔、太線300m間隔 |
| 5820gpm線 | 茶色一点鎖線 |
| 5400gpm線 | 青色一点鎖線 |
| 相対渦度 | 灰色/赤ハッチ + 黒等値線 |
| 図法 | ステレオ投影 中心60°N/140°E |
| 領域 | 108-156°E, 17-55°N |

---

## データソース

- **URL**: `http://database.rish.kyoto-u.ac.jp/arch/jmadata/data/gpv/original/{YYYY}/{MM}/{DD}/`
- **提供元**: 京都大学生存圏研究所 (RISH)
- **ファイル種類**: `Rgl`（全球）のみ使用（`Rjp`=日本域は対象外）
- **初期時刻**: 00UTC・12UTC（1日2回）

---

## 開発履歴

- `kurora_tenkizu.ipynb` → `kurora_tenkizu.py` に変換（上原政博）
- コマンドライン引数対応・PNG出力対応に改修（20260408 上原政博）
- `download_gsm.py` 新規作成（20260408 上原政博）
