# tenkizu — 天気図作成ツール（GSM / ECMWF）

詳しくは [tenkizu.md](tenkizu.md) を参照。

黒良さんのNote（https://note.com/rkurora/n/n200fdd8f1aa1 ）他をベースに、  
GSM（全球モデル）・ECMWF GRIB2 データから各種高層・地上天気図を作成するツール。  
高層ゾンデデータからエマグラム・温位エマグラムも描画できる。

---

## 概要

- **対応データ**: GSM（RISH、過去全期間無償）・ECMWF（Open Data、最新5日分のみ無償）・Wyoming高層ゾンデ
- **描画スクリプト**: 16種類（GSM 10本・ECM 6本）＋エマグラム1本
- **レポート生成**: 5本（Markdown+PNG → `reports/` に保存、`--push` でGitHub push）
- **実行環境**: Python 3.10（conda 環境 `met_env_310`）

---

## ファイル構成

```
tenkizu/
├── emagram.py              # エマグラム・温位エマグラム（Wyoming高層ゾンデ）
├── GSM_tenkizu500hPa.py    # GSM 500hPa等高度線・渦度
├── GSM_QVector850hPa.py    # GSM 850hPa Qベクター
├── GSM_Jet300hPa.py        # GSM 300hPa ジェット
├── GSM_Instability.py      # GSM 不安定域分布
├── GSM_CrossSection.py     # GSM 鉛直断面図
├── GSM_fax57.py            # GSM FAX57相当（500hPa気温・700hPa湿数）
├── GSM_fax78.py            # GSM FAX78相当（850hPa気温・風・700hPa発散）
├── GSM_faxSrfPre.py        # GSM 地上気圧・10m風・2m気温
├── GSM_EPT850hPa.py        # GSM 850hPa 相当温位・風矢羽
├── GSM_100hPa.py           # GSM 任意気圧面 等高度線・ISOTAC・風矢羽
├── ECM_tenkizu500hPa.py    # ECMWF 500hPa等高度線・渦度
├── ECM_EPT850hPa.py        # ECMWF 850hPa相当温位
├── ECM_Fax57.py            # ECMWF FAX57
├── ECM_Fax78.py            # ECMWF FAX78
├── ECM_SurfacePressure.py  # ECMWF 地上気圧（±可降水量/積算降水量）
├── ECM_100hPa.py           # ECMWF 任意気圧面 等高度線・ISOTAC・風矢羽
├── jet_front_report.py     # レポート: 上層風・断面図・EPT850・地上気圧
├── jet_front_wide_report.py# レポート: 広域上層風＋850hPa（--avg_steps 対応）
├── jet_front_ave_report.py # レポート: 複数初期時刻FT=0h時間平均（梅雨入り判断）
├── upper_wind_report.py    # レポート: 上層天気図（任意気圧面）
├── synop_report.py         # レポート: 総観天気図（Jet・Fax57・Fax78・EPT・地上）
├── run_gsm_auto.py         # GSM系: 最新データ自動検索・一括生成
├── run_ecm_auto.py         # ECM系: 最新データ自動検索・一括生成
├── run_all_charts.sh       # 全16スクリプト一括実行
├── make_pptx.py            # PNG → PowerPoint 自動生成（主要7グループ）
├── make_pptx2.py           # PNG → PowerPoint 自動生成（補完3グループ）
├── download_gsm.py         # GSM GRIB2事前ダウンロード専用
├── kurora_tenkizu.py       # 旧メイン版（互換維持）
├── run_pipeline.sh         # 旧パイプライン
├── samples/                # 各種別サンプルPNG（GitHub閲覧用）
├── reports/                # レポート保存先
├── data_gsm/               # GSM GRIB2データ（Gitから除外）
├── data/ecm/               # ECMWF GRIB2データ（Gitから除外）
└── output/                 # 生成天気図PNG（Gitから除外）
```

---

## セットアップ

```bash
conda create -n met_env_310 python=3.10
conda activate met_env_310
conda install -c conda-forge pygrib xarray metpy matplotlib cartopy requests
pip install beautifulsoup4 python-pptx siphon
```

---

## 使い方

### 引数の共通仕様（天気図描画スクリプト共通）

```
python <スクリプト名> INIT_TIME [START_FT [N_STEPS]] [オプション]
```

| 引数 | 説明 | デフォルト |
|------|------|----------|
| `INIT_TIME` | 初期時刻 YYYYMMDDHH（UTC）**必須** | — |
| `START_FT` | 開始予報時間。**GSM=DDHH形式**・**ECM=時間数** | GSM:`0000` / ECM:`0` |
| `N_STEPS` | 枚数またはプリセット（`12h` / `24h`） | `1` |
| `--interval N` | FT間隔 時間数（プリセット指定時は無視） | `6` |

**時間プリセット:**

| プリセット | FT一覧 | 枚数 |
|-----------|--------|------|
| `12h` | 0, 12, 24, 36, 48h | 5枚 |
| `24h` | 0, 24, 48, 72, 96, 120h | 6枚 |

---

### 自動実行（推奨）

最新 init_time を自動検索してデータ取得・一括生成する。

```bash
# GSM系（RISHサーバーから自動DL）
python run_gsm_auto.py                                              # 最新 12hプリセット
python run_gsm_auto.py --steps 5                                   # 最新 FT=0〜24h
python run_gsm_auto.py --init-time 2026041200                      # init_time指定
python run_gsm_auto.py --init-time 2026041200 --start-ft 0100 --steps 3

# ECMWF系（Open Dataから自動DL、最新5日分のみ）
python run_ecm_auto.py                                             # 最新 12hプリセット
python run_ecm_auto.py --steps 5
python run_ecm_auto.py --init-time 2026041200
python run_ecm_auto.py --tcwv                                      # 可降水量シェード追加
python run_ecm_auto.py --tp                                        # 積算降水量シェード追加（FT>0必須）
```

---

### レポート生成スクリプト

`reports/{init_str}/` に PNG + Markdown を生成。`--push` で GitHub へ push。

#### emagram.py — エマグラム・温位エマグラム

Wyoming Upper Air データベースから高層ゾンデを取得し描画する。

```bash
python emagram.py [--date YYYYMMDDHH] [--site 地点名] [--id WMO番号]
                  [--mode {both,emagram,pt}] [--report] [--push] [--show]
```

| 引数 | デフォルト | 説明 |
|------|-----------|------|
| `--date` | 現在UTC-6h以前の直近00/12UTC | 観測日時（UTC） |
| `--site` | 石垣島 | 地点名（下記一覧参照） |
| `--id` | — | WMO地点番号（`--site` より優先） |
| `--mode` | `both` | `both` / `emagram` / `pt` |
| `--report` | なし | `reports/{tag}/` にPNG+MD生成 |
| `--push` | なし | git add → commit → push（`--report` 必須） |

**対応地点:**

| 地点 | WMO番号 | 地域 |
|------|---------|------|
| 石垣島（デフォルト） | 47918 | 南西諸島 |
| 南大東島 | 47945 | 南西諸島 |
| 名瀬 | 47909 | 南西諸島 |
| 鹿児島 | 47827 | 九州 |
| 福岡 | 47807 | 九州 |
| 潮岬 | 47778 | 近畿 |
| 館野 | 47646 | 関東 |
| 八丈島 | 47678 | 関東 |
| 輪島 | 47600 | 北陸 |
| 秋田 | 47582 | 東北 |
| 稚内 | 47401 | 北海道 |
| 花蓮 | 46699 | 台湾※ |
| 台北 | 46692 | 台湾※ |

※台湾地点はWyomingデータベース未収録のため取得不可の場合あり

```bash
python emagram.py                                   # 石垣島 直近時刻 両図
python emagram.py --date 2024051200                 # 日時指定
python emagram.py --site 南大東島                   # 地点変更
python emagram.py --site 館野 --mode emagram        # エマグラムのみ
python emagram.py --site 名瀬 --mode pt             # 温位エマグラムのみ
python emagram.py --site 石垣島 --report            # レポート生成
python emagram.py --site 石垣島 --report --push     # レポート生成 + GitHub push
```

生成物: `reports/{YYYYMMDDHH}_{station_id}/emagram_report.md` + PNG 2枚

---

#### jet_front_report.py — ジェット・前線解析レポート

```bash
python jet_front_report.py INIT_TIME [start_ft] [n_steps] [--interval N]
                           [--levels ...] [--ecm] [--push]
                           [--lat-s N] [--lat-e N] [--lon-s N] [--lon-e N]
```

```bash
python jet_front_report.py 2026041200                           # GSMのみ FT=0h
python jet_front_report.py 2026041200 0000 12h                  # 12hプリセット
python jet_front_report.py 2026041200 0000 5 --interval 12      # 12h間隔 5枚
python jet_front_report.py 2026041200 --ecm --levels 100 50     # GSM+ECM 100+50hPa
python jet_front_report.py 2026041200 --lat-s 45 --lat-e 25 --lon-s 125 --lon-e 135
python jet_front_report.py 2026041200 0000 5 --push
```

生成物: `reports/{init_str}/jet_front_report_{FTラベル}.md`

---

#### jet_front_wide_report.py — ジェット・前線解析（広域）レポート

上層風＋850hPa相当温位を広域描画範囲（上層: 70〜180°E / 850hPa: 97〜169°E）で生成。  
`--avg_steps N` で複数FTの平均天気図にも対応。

```bash
python jet_front_wide_report.py INIT_TIME [start_ft] [n_steps] [--interval N]
                                [--levels ...] [--ecm] [--avg_steps N] [--push]
```

```bash
python jet_front_wide_report.py 2026041200                           # GSMのみ FT=0h
python jet_front_wide_report.py 2026041200 0000 12h                  # 12hプリセット
python jet_front_wide_report.py 2026041200 --levels 100 50           # 100+50hPa
python jet_front_wide_report.py 2026041200 0000 3 --avg_steps 4      # 4FT平均×3枚
python jet_front_wide_report.py 2026041200 0000 5 --push
```

> **沖縄梅雨入り目安**: `--levels 100 50` を指定。100hPa: チベット高気圧張り出しで沖縄付近が**北寄りの風**、50hPa: **東風**が卓越。

生成物: `reports/{init_str}-wide/jet_front_wide_report_{FTラベル}.md`

---

#### jet_front_ave_report.py — ジェット・前線解析（時間平均）レポート

複数初期時刻の FT=0h（解析値）を時間平均して描画。梅雨入り等の平均場把握に有効。

```bash
python jet_front_ave_report.py INIT_TIME [n_days] [--levels ...] [--ecm] [--push]
```

```bash
python jet_front_ave_report.py 2026050600                               # 1日(2個)平均
python jet_front_ave_report.py 2026050600 3                             # 3日(6個)平均
python jet_front_ave_report.py 2026050600 5 --levels 100 50 --ecm --push
```

> ECMWFは最新5日分のみ。長期平均にはGSM（RISHアーカイブ）を使用すること。

生成物: `reports/{init_str}-ave/jet_front_ave_report_{n}d.md`

---

#### upper_wind_report.py — 上層天気図レポート

```bash
python upper_wind_report.py INIT_TIME [start_ft] [n_steps] [--interval N]
                            [--levels ...] [--ecm] [--push]
```

```bash
python upper_wind_report.py 2026041200                                # 100hPa FT=0h
python upper_wind_report.py 2026041200 0000 12h --levels 100 50 --ecm
python upper_wind_report.py 2026041200 0000 5 --push
```

生成物: `reports/{init_str}/upper_wind_report_{FTラベル}.md`

---

#### synop_report.py — 総観天気図レポート

Jet300hPa・Fax57・Fax78・EPT850hPa・地上気圧を一括生成。

```bash
python synop_report.py INIT_TIME [start_ft] [n_steps] [--interval N]
                       [--charts jet fax57 fax78 ept srf] [--ecm] [--push]
```

```bash
python synop_report.py 2026041200                               # 全種別 FT=0h
python synop_report.py 2026041200 0000 12h                      # 12hプリセット
python synop_report.py 2026041200 --ecm --charts ept srf        # 種別指定+ECM
python synop_report.py 2026041200 0000 5 --ecm --push
```

生成物: `reports/{init_str}/synop_report_{FTラベル}.md`

---

### 一括生成（全16スクリプト）

```bash
bash run_all_charts.sh INIT_TIME [START_FT_DDHH [N_STEPS|12h|24h]] [--ecm] [--interval N]
```

```bash
bash run_all_charts.sh 2026041200                          # FT=0h 各1枚
bash run_all_charts.sh 2026041200 0000 5                   # FT=0,6,12,18,24h
bash run_all_charts.sh 2026041200 0000 12h                 # 12hプリセット
bash run_all_charts.sh 2026041200 0000 24h                 # 24hプリセット
bash run_all_charts.sh 2026041200 0000 5 --ecm             # GSM+ECM
```

---

### GSM系個別スクリプト

起動時に `data_gsm/` になければ自動でRISHサーバーからダウンロード。

| スクリプト | 主な描画要素 |
|-----------|------------|
| `GSM_tenkizu500hPa.py` | 等高度線(60m/300m)・渦度シェード・H/L |
| `GSM_QVector850hPa.py` | Qベクター発散・等温度線・等高度線 |
| `GSM_Jet300hPa.py` | 等風速線・非地衡風・収束発散シェード |
| `GSM_Instability.py` | 不安定域(SEPT−maxEPT差)シェード・上層気温 |
| `GSM_CrossSection.py` | ポテンシャル温位・EPT・風の鉛直断面 |
| `GSM_fax57.py` | 500hPa等温度線(青)・700hPa T-Tdシェード・W/C |
| `GSM_fax78.py` | 850hPa等温度線・風矢羽・700hPa発散シェード・W/C |
| `GSM_faxSrfPre.py` | 等圧線(4/20hPa)・10m風矢羽・2m等温度線・H/L |
| `GSM_EPT850hPa.py` | 850hPa相当温位シェード・等値線・風矢羽 |
| `GSM_100hPa.py` | 任意気圧面 等高度線・ISOTAC・風矢羽 |

```bash
python GSM_fax57.py 2026041200            # FT=0h 1枚
python GSM_fax57.py 2026041200 0000 5    # FT=0〜24h 5枚
python GSM_100hPa.py 2026041200 0000 5 50  # 50hPa 5枚
python GSM_CrossSection.py 2026041200 0000 1 --lat-s 45 --lat-e 25 --lon-s 130 --lon-e 140
```

---

### ECMWF系個別スクリプト

最新約5日分のみ無償。`START_FT` は**時間数**で指定。

| スクリプト | 主な描画要素 |
|-----------|------------|
| `ECM_tenkizu500hPa.py` | 等高度線(60m/300m)・渦度シェード・H/L |
| `ECM_EPT850hPa.py` | 850hPa相当温位シェード・等値線・風矢羽 |
| `ECM_Fax57.py` | 500hPa等温度線(青)・700hPa T-Tdシェード・W/C |
| `ECM_Fax78.py` | 850hPa等温度線・風矢羽・700hPa発散シェード・W/C |
| `ECM_SurfacePressure.py` | 等圧線・10m風矢羽・2m等温度線・H/L（±TCWV/TP） |
| `ECM_100hPa.py` | 任意気圧面 等高度線・ISOTAC・風矢羽 |

```bash
python ECM_Fax57.py 2026041200 0 5
python ECM_SurfacePressure.py 2026041200 0 5 --tcwv   # 可降水量シェード
python ECM_SurfacePressure.py 2026041200 6 3 --tp     # 積算降水量（FT>0必須）
python ECM_100hPa.py 2026041200 0 5 50                # 50hPa 5枚
```

---

### データ事前ダウンロード（GSM）

```bash
python download_gsm.py                        # 最新を自動検索
python download_gsm.py --date 20171210        # 指定日（00/12UTC両方）
python download_gsm.py --date 20171210 --hour 12
python download_gsm.py --start 20171208 --end 20171210
python download_gsm.py --date 20171210 --ft 0000 0012 0100
```

---

## 出力ファイル

| スクリプト | 出力パス |
|-----------|--------|
| GSM/ECM 天気図スクリプト | `output/{YYYYMMDDHH}_FT{FFF}h_{種別}.png` |
| `emagram.py`（通常） | `output/emagram/{YYYYMMDDHH}_{station_id}_emagram.png` |
| `emagram.py`（`--report`） | `reports/{YYYYMMDDHH}_{station_id}/emagram_report.md` + PNG |
| レポートスクリプト | `reports/{init_str}/{スクリプト名}_{FTラベル}.md` + PNG |

---

## JRA-55 天気図作成

JRA-55 再解析データ（京都大学RISHアーカイブ）から、過去事例の解析時刻ベースの天気図を作成できる。  
GSM/ECMWF の予報時間 `FT` とは異なり、JRA-55 は `YYYYMMDDHH` の解析時刻を直接指定する。

### 認証設定

JRA-55 データ取得用の ID/password は `jra55_config.ini` に保存する。  
このファイルは `.gitignore` で除外され、GitHub には push されない。

```ini
[jra55]
user = your_user_id
password = your_password
```

雛形は `jra55_config.example.ini` にある。

### JRA-55 総観天気図レポート

`synop_report.py` と同様に、複数の天気図PNGを生成し、Markdownに埋め込む。

```bash
python jra55_synop_report.py DATE [--hour H] [--charts ...] [--push]
```

| 引数 | 説明 | デフォルト |
|------|------|----------|
| `DATE` | `YYYYMMDD` または `YYYYMMDDHH`（UTC） | 必須 |
| `--hour H` | `YYYYMMDD` 指定時の解析時刻。`0/6/12/18` のみ | `0` |
| `--charts` | 作成する図種。`jet fax57 fax78 ept srf` から選択 | 全図 |
| `--data-dir` | JRA-55 NetCDF 保存先 | `./data/Jra55` |
| `--output-dir` | 一時PNG出力先 | `./output` |
| `--config` | 認証設定ファイル | `./jra55_config.ini` |
| `--push` | MarkdownとPNGを commit/push | なし |

```bash
python jra55_synop_report.py 19590915
python jra55_synop_report.py 1959091512 --charts jet srf
python jra55_synop_report.py 19590915 --push
```

生成する図:

| chart | 内容 | 出力PNG |
|-------|------|--------|
| `jet` | 300hPa 等風速・発散・非地衡風 | `{YYYYMMDDHH}_JRA55_300hPa_Jet_Divergence.png` |
| `fax57` | 500hPa気温・700hPa湿数 | `{YYYYMMDDHH}_JRA55_Fax57.png` |
| `fax78` | 700hPa発散・850hPa気温風 | `{YYYYMMDDHH}_JRA55_Fax78.png` |
| `ept` | 850hPa相当温位・風 | `{YYYYMMDDHH}_JRA55_850hPa_EPT.png` |
| `srf` | 地上気圧・地上風・地上気温 | `{YYYYMMDDHH}_JRA55_SurfacePressure.png` |

レポート出力先:

```text
reports/{YYYYMMDDHH}-jra55-synop/jra55_synop_report_{YYYYMMDDHH}.md
```

### JRA-55 300hPa ジェット単図

300hPa のジェット気流・上層発散だけを作成する場合は `JRA55_JetDivergence.py` を直接実行する。

```bash
python JRA55_JetDivergence.py 1961071518
python JRA55_JetDivergence.py 1961071518 --level 300 --data-dir data/Jra55
```

### JRA-55 技術情報

使用データ:

| 用途 | 変数 | RISH配下 |
|------|------|----------|
| 上層高度 | `HGT` | `data/isobaric_1.25d/HGT/{YYYY}/HGT_{YYYYMM}.nc` |
| 上層風 | `UGRD`, `VGRD` | `data/isobaric_1.25d/{UGRD,VGRD}/{YYYY}/...` |
| 上層発散 | `RELD` | `data/isobaric_1.25d/RELD/{YYYY}/RELD_{YYYYMM}.nc` |
| 上層気温 | `TMP` | `data/isobaric_1.25d/TMP/{YYYY}/TMP_{YYYYMM}.nc` |
| 上層相対湿度 | `RH` | `data/isobaric_1.25d/RH/{YYYY}/RH_{YYYYMM}.nc` |
| 海面更正気圧 | `PRMSL_msl` | `data/isobaric_1.25d/surf/PRMSL/PRMSL_msl_{YYYY}.nc` |
| 地上風 | `UGRD_fhg`, `VGRD_fhg` | `data/isobaric_1.25d/surf/{UGRD,VGRD}/...` |
| 地上気温 | `TMP_fhg` | `data/isobaric_1.25d/surf/TMP/TMP_fhg_{YYYY}.nc` |

ローカル保存先:

```text
data/Jra55/
├── HGT/YYYY/HGT_YYYYMM.nc
├── TMP/YYYY/TMP_YYYYMM.nc
├── RH/YYYY/RH_YYYYMM.nc
└── surf/PRMSL/PRMSL_msl_YYYY.nc
```

注意:

- JRA-55 は 00/06/12/18UTC の6時間間隔。
- 月別の等圧面データと年別の地上データを自動取得する。
- 初回実行時は NetCDF が数百MB単位でダウンロードされる。再実行時は `data/Jra55/` のローカルファイルを再利用する。
- `data/Jra55/`, `output/`, `jra55_config.ini` は `.gitignore` で除外される。
- Python環境は `met_env` を使用する。

---

## PowerPoint 自動生成

```bash
python make_pptx.py INIT_TIME   # 主要7グループ（GSM/ECM各種）
python make_pptx2.py INIT_TIME  # 補完3グループ（不安定域・断面図等）
```

---

## 更新履歴

| 日付 | 内容 |
|------|------|
| 2026-04-08 | 初版作成 |
| 2026-04-09 | GSM系5本・ECMWF系4本追加、`run_all_charts.sh` 作成 |
| 2026-04-12 | GSM版FAX天気図3本追加、`run_gsm_auto.py`・`run_ecm_auto.py` 追加 |
| 2026-04-13 | `GSM_EPT850hPa.py`・`ECM_tenkizu500hPa.py` 追加（計14スクリプト）、`make_pptx.py`/`make_pptx2.py` 追加 |
| 2026-04-28 | `GSM_100hPa.py`・`ECM_100hPa.py`・`upper_wind_report.py`・`jet_front_report.py`・`synop_report.py` 追加、`--push` フラグ追加 |
| 2026-05-01 | `--area` 引数追加（描画範囲外部指定）、`jet_front_wide_report.py` 追加 |
| 2026-05-07 | `--avg_steps N` 追加（予報時間軸平均）、`jet_front_ave_report.py` 追加 |
| 2026-05-10 | 時間プリセット（`12h`/`24h`）・`--interval`・`--charts` オプション追加 |
| 2026-05-12 | `emagram.py` 追加（Wyoming高層ゾンデ、エマグラム・温位エマグラム、`--report`/`--push` 対応） |
| 2026-05-13 | JRA-55対応を追加（`JRA55_JetDivergence.py`・`JRA55_SynopCharts.py`・`jra55_jet_report.py`・`jra55_synop_report.py`、認証設定ファイル、Markdownレポート生成） |

---

## 参考

- 黒良さんのNote: https://note.com/rkurora/n/n200fdd8f1aa1
- 黒良さんのNote（JRA-55）: https://note.com/rkurora/n/n568e9ac95e3d
- RISHデータベース: http://database.rish.kyoto-u.ac.jp/arch/jmadata/
- RISH JRA-55アーカイブ: https://database.rish.kyoto-u.ac.jp/arch/jra55/
- Wyoming Upper Air: https://weather.uwyo.edu/upperair/sounding.html
- ECMWF Open Data: https://www.ecmwf.int/en/forecasts/datasets/open-data
- Copernicus CDS（過去ECMWFデータ）: https://cds.climate.copernicus.eu
