# CLAUDE.md — tenkizu プロジェクト

## プロジェクト概要

GSM（全球モデル）・ECMWF・JRA-55 再解析データから各種高層・地上天気図およびエマグラムを生成するツール群。  
黒良さんのNoteをベースに開発・拡張（上原政博）。

---

## Python 実行環境

| 環境名 | 用途 |
|--------|------|
| `met_env_310`（Python 3.10） | GSM/ECM 系スクリプト（pygrib を使うため） |
| `met_env`（Python 3.10） | JRA-55 系スクリプト（xarray/NetCDF ベース） |

```bash
conda activate met_env_310   # GSM/ECM 系
conda activate met_env       # JRA-55 系
```

**必要ライブラリ**: pygrib, xarray, metpy, matplotlib, cartopy, requests, beautifulsoup4, siphon, python-pptx  
**PROJ_LIBパス**: `/opt/anaconda3/envs/met_env_310/share/proj`（GSM/ECMスクリプト内で設定済み）

---

## ファイル構成と役割

### 天気図描画スクリプト（GSM系）

| ファイル | 役割 |
|--------|------|
| `GSM_tenkizu500hPa.py` | 500hPa等高度線・渦度シェード |
| `GSM_QVector850hPa.py` | 850hPa Qベクター発散 |
| `GSM_Jet300hPa.py` | 300hPa ジェット・発散 |
| `GSM_Instability.py` | 不安定域分布 |
| `GSM_CrossSection.py` | 鉛直断面図（ポテンシャル温位・EPT・風） |
| `GSM_fax57.py` | FAX57相当（500hPa気温・700hPa湿数） |
| `GSM_fax78.py` | FAX78相当（850hPa気温・風・700hPa発散） |
| `GSM_faxSrfPre.py` | 地上気圧・10m風・2m気温 |
| `GSM_EPT850hPa.py` | 850hPa相当温位・風矢羽 |
| `GSM_100hPa.py` | 任意気圧面 等高度線・ISOTAC・風矢羽 |
| `GSM_PolarView.py` | 北半球極座標天気図（NorthPolarStereo、等高度線・風速シェード、ジェット蛇行確認用、`--level`/`--lat-min`/`--no-wind`/`--avg-init`/`--avg-ft`/`--push` 対応） |
| `make_ncep_climo.py` | NOAA PSL から NCEP/NCAR 月別平年値 LTM（1991-2020）を取得（3ファイル・計 ~25 MB、`data/ncep_climo/` に保存） |

### 天気図描画スクリプト（ECMWF系）

| ファイル | 役割 |
|--------|------|
| `ECM_tenkizu500hPa.py` | 500hPa等高度線・渦度シェード |
| `ECM_EPT850hPa.py` | 850hPa相当温位・風矢羽 |
| `ECM_Fax57.py` | FAX57相当 |
| `ECM_Fax78.py` | FAX78相当 |
| `ECM_SurfacePressure.py` | 地上気圧（±可降水量/積算降水量） |
| `ECM_100hPa.py` | 任意気圧面 等高度線・ISOTAC・風矢羽 |

### 天気図描画スクリプト（AIFS系）

| ファイル | 役割 |
|--------|------|
| `AIFS_SurfacePressure.py` | ECMWF AI気象モデル（AIFS-single）地上気圧・風・2m気温。`data/aifs/` へDL・00z/12zのみ |
| `AIFS_ENS_SurfacePressure.py` | AIFS-ENS コントロールメンバー（cf）地上気圧・風・2m気温。`data/aifs-ens/` へDL・全初期時刻対応・~85MB/FT |

### 天気図描画スクリプト（GFS系）

| ファイル | 役割 |
|--------|------|
| `GFS_SurfacePressure.py` | 地上気圧・10m風・2m気温（NOMADS filter DL、`--area`/`--smooth-size`/`--wind-step` 対応） |

### 天気図描画スクリプト（JRA-55系）

| ファイル | 役割 |
|--------|------|
| `JRA55_SynopCharts.py` | 総観天気図セット（jet/fax57/fax78/ept/srf） |
| `JRA55_JetDivergence.py` | 300hPa ジェット・上層発散 |
| `JRA55_Emagram.py` | 任意地点のエマグラム・温位エマグラム（NetCDF） |

### エマグラム描画スクリプト

| ファイル | データソース | 役割 |
|--------|------------|------|
| `emagram.py` | Wyoming高層ゾンデ | エマグラム・温位エマグラム（WMO地点指定） |
| `JRA55_Emagram.py` | JRA-55 NetCDF | 任意格子点のエマグラム・温位エマグラム（再解析） |
| `GRIB2_Emagram.py` | GSM/ECM GRIB2 | 任意格子点のエマグラム・温位エマグラム（現業モデル） |

### 解析雨量描画スクリプト

| ファイル | 役割 |
|--------|------|
| `JMA_AnalysisRain.py` | 気象庁解析雨量（1kmメッシュ）降水強度分布図。GRIB2ローカルテンプレート・ランレングス圧縮を自前パーサーでデコード（pygrib非対応のため）。自動DL未対応、`data/jmara/` へ手動配置 |

### レポート生成スクリプト

| ファイル | 役割 |
|--------|------|
| `jet_front_report.py` | ジェット・前線解析レポート（PNG+Markdown） |
| `jet_front_wide_report.py` | 広域ジェット・前線解析レポート（平均天気図対応） |
| `jet_front_ave_report.py` | 複数初期時刻平均レポート（梅雨入り判断） |
| `upper_wind_report.py` | 上層天気図レポート |
| `synop_report.py` | 総観天気図レポート（GSM/ECM） |
| `typhoon-multi.py` | 地上気圧マルチモデル比較レポート（GSM/ECM/GFS、`--area` で描画範囲指定） |
| `jra55_synop_report.py` | 総観天気図レポート（JRA-55） |
| `jra55_jet_report.py` | ジェット・上層発散レポート（JRA-55） |

### 自動実行・ユーティリティ

| ファイル | 役割 |
|--------|------|
| `run_gsm_auto.py` | GSM系: 最新 init_time 自動検索・一括生成 |
| `run_ecm_auto.py` | ECM系: 最新 init_time 自動検索・一括生成 |
| `run_all_charts.sh` | 全スクリプト一括実行 |
| `download_gsm.py` | GSM GRIB2 事前ダウンロード専用 |
| `make_pptx.py` | PNG → PowerPoint 自動生成（主要グループ） |
| `make_pptx2.py` | PNG → PowerPoint 自動生成（補完グループ） |
| `kurora_tenkizu.py` | 旧メイン版（互換維持） |
| `run_pipeline.sh` | 旧パイプライン |

### 設定・データディレクトリ

| パス | 内容 |
|------|------|
| `jra55_config.ini` | JRA-55 認証情報（Gitから除外） |
| `jra55_config.example.ini` | 認証設定の雛形（ダミー値） |
| `data_gsm/` | GSM GRIB2データ（Gitから除外） |
| `data/ecm/` | ECMWF GRIB2データ（Gitから除外） |
| `data/aifs/` | AIFS-single GRIB2データ（Gitから除外）。`{YYYYMMDDHH}0000-{FT}h-oper-fc.grib2` |
| `data/aifs-ens/` | AIFS-ENS GRIB2データ（Gitから除外）。`{YYYYMMDDHH}0000-{FT}h-enfo-cf.grib2`（cfのみ） |
| `data/gfs/` | GFS GRIB2データ（Gitから除外）。`gfs_{YYYYMMDDHH}_f{FFF:03d}_srf.grib2` |
| `data/Jra55/` | JRA-55 NetCDFキャッシュ（Gitから除外） |
| `data/jmara/` | 解析雨量GRIB2データ（Gitから除外）。`Z__C_RJTD_{YYYYMMDDHHMM}00_SRF_GPV_Ggis1km_Prr60lv_ANAL_grib2.bin`。自動DL未対応・手動配置 |
| `output/` | 生成天気図PNG（Gitから除外） |
| `reports/` | レポート保存先（PNG+Markdown） |

---

## GSMファイル命名規則

```
Z__C_RJTD_{YYYYMMDD}{HH}0000_GSM_GPV_Rgl_FD{DDHH}_grib2.bin
```

- `FD{DDHH}`: 予報時間（DD=日数、HH=時間数）
  - `FD0000` = FT=0h、`FD0018` = FT=18h、`FD0100` = FT=24h、`FD0112` = FT=36h
- **FT計算式**: `FT[h] = DD × 24 + HH`

---

## スクリプト引数の共通仕様

### GSM/ECM 天気図スクリプト共通

```
python <スクリプト名> INIT_TIME [START_FT [N_STEPS]] [オプション]
```

| 引数 | 説明 | デフォルト |
|------|------|----------|
| `INIT_TIME` | 初期時刻 YYYYMMDDHH（UTC）**必須** | — |
| `START_FT` | 開始予報時間。**GSM=DDHH形式**・**ECM=時間数** | GSM:`0000` / ECM:`0` |
| `N_STEPS` | 枚数またはプリセット（`12h` / `24h`） | `1` |
| `--interval N` | FT間隔 時間数 | `6` |
| `--ecm` | ECMWFも実行（GSM+ECM） | なし |
| `--ecm-only` | ECMWFのみ実行（GSMをスキップ）※レポートスクリプトのみ | なし |

### JRA-55 スクリプト共通

JRA-55 は予報モデルではなく再解析データのため、「初期時刻＋予報時間」ではなく「有効時刻（解析時刻）」を指定する。  
有効時刻は 00/06/12/18UTC の6時間間隔。

```
python JRA55_SynopCharts.py   VALID_TIME [--charts ...] [オプション]
python JRA55_JetDivergence.py VALID_TIME [--level hPa] [オプション]
```

### エマグラムスクリプト共通

JRA-55 と GRIB2 のエマグラムは、`--start-ft/--steps/--interval` で複数FTを連続作図できる。  
省略時は `reports/` 以下に PNG + Markdown レポートを自動生成する。

### ヘルプ表示（全スクリプト共通）

引数に `?`・`-?`・`--?` のいずれかを渡すと、そのスクリプトの引数一覧・使用例を表示して終了する。

```bash
python GSM_fax57.py ?
python ECM_SurfacePressure.py -?
python synop_report.py --?
```

---

## JRA-55 認証設定

JRA-55 データのダウンロードには 京大RISH の認証が必要。

```ini
# jra55_config.ini（.gitignoreで除外済み）
[jra55]
user = your_user_id
password = your_password
```

または環境変数で指定可能:

```bash
export JRA55_USER=your_user_id
export JRA55_PASSWORD=your_password
```

雛形: `jra55_config.example.ini`

---

## データソース

| データ | URL | 備考 |
|--------|-----|------|
| GSM GRIB2 | `http://database.rish.kyoto-u.ac.jp/arch/jmadata/data/gpv/original/` | RISH・全期間無償 |
| JRA-55 NetCDF | `https://database.rish.kyoto-u.ac.jp/arch/jra55/data/isobaric_1.25d` | RISH・認証必要 |
| ECMWF Open Data | `https://data.ecmwf.int/forecasts` | 最新5日分のみ無償 |
| GFS（NOMADS filter） | `https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl` | 最新約10日分無償 |
| Wyoming ゾンデ | `https://weather.uwyo.edu/upperair/sounding.html` | `emagram.py` 使用 |

### 各国全球モデル 取得可否まとめ

| モデル | 無償リアルタイムGRIB2 | 取得しやすさ |
|--------|:--------------------:|:----------:|
| GSM（日本） | ✓ 京大RISH | ◎ |
| GFS（米国） | ✓ NOMADS | ◎ |
| ECMWF（欧州） | ✓ Open Data（5日分） | ○ |
| UKMET（英国） | ✗ | ✗ |
| CFS（米国・季節） | ✓ NOMADS | △ |
| GEM（カナダ） | ✓ MSC Datamart | △ |

JRA-55（再解析）: 無償・認証必要・リアルタイムなし・1958年〜（実装済み）

---

## 開発履歴

| 日付 | 内容 |
|------|------|
| 2026-04-08 | `kurora_tenkizu.py` CLI化・`download_gsm.py` 新規作成 |
| 2026-04-09〜13 | GSM系10本・ECM系6本追加、レポート・PPTX生成 |
| 2026-04-28〜05-10 | `upper_wind_report.py`・`jet_front_*_report.py`・時間プリセット追加 |
| 2026-05-12 | `emagram.py` 新規作成（Wyoming高層ゾンデ） |
| 2026-05-13 | JRA-55対応追加（`JRA55_SynopCharts.py`・`JRA55_JetDivergence.py`・レポートスクリプト） |
| 2026-05-13 | `JRA55_Emagram.py`・`GRIB2_Emagram.py` 新規作成（エマグラム全データ源対応） |
| 2026-05-29 | `GFS_SurfacePressure.py` 新規作成（NOMADS filter DL、地上気圧描画） |
| 2026-05-29 | `ECM_GSM_SurfacePressure.py` → `typhoon-multi.py` にリネーム。GFS対応・`--area` 追加 |
| 2026-06-11 | `GSM_PolarView.py` 新規作成（北半球極座標天気図、NorthPolarStereo投影、等高度線+風速シェード、過去N日平均・FT平均・GitHub push対応） |
| 2026-06-11 | `make_ncep_climo.py` 新規作成→NCEP LTM版に置き換え（NOAA PSL から hgt/uwnd/vwnd LTM 3ファイル取得、計 ~25 MB） |
| 2026-06-19 | `AIFS_SurfacePressure.py` 新規作成（ECMWF AIFS AI気象モデル対応、`data/aifs/` へDL・00z/12zのみ） |
| 2026-06-19 | `typhoon-multi.py` に `--aifs` / `--aifs-ens` / `--all` フラグ追加（AIFS・AIFS-ENS対応） |
| 2026-06-19 | `AIFS_ENS_SurfacePressure.py` 新規作成（AIFS-ENS cfコントロールメンバー対応、00/06/12/18z 全初期時刻）|
| 2026-06-19 | `run_ecm_auto.py` に `--aifs` / `--aifs-only` フラグ追加・`find_latest_init_time(model=)` 対応 |
| 2026-08-10 | `JMA_AnalysisRain.py` 新規作成（気象庁解析雨量1kmメッシュ描画。pygrib非対応のGRIB2ローカルテンプレート・ランレングス圧縮を自前パーサーでデコード。自動DL未対応、`data/jmara/` に手動配置） |
