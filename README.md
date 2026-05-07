# tenkizu — 天気図作成ツール（GSM / ECMWF）

詳しくは [tenkizu.md](tenkizu.md) を参照。

黒良さんのNote（https://note.com/rkurora/n/n200fdd8f1aa1 ）他をベースに、  
GSM（全球モデル）や ECMWF GRIB2 データから各種高層・地上天気図を作成するツールです。

---

## 概要

- **対応データ**: 気象庁 GSM（全球モデル）・ECMWF（欧州中期予報センターモデル）
- **スクリプト数**: 描画スクリプト 16 種類（GSM 11本・ECM 6本）＋レポート生成スクリプト 3本
- **図法**: ステレオ投影（中心: 60°N, 140°E）
- **描画領域**: 108〜156°E, 17〜55°N（極東域）
- **出力形式**: PNG（DPI 150, 10×8 インチ）
- **実行環境**: Python 3.10（conda 環境 `met_env_310`）

---

## データソース

### GSM（気象庁 全球モデル）

| 項目 | 内容 |
|------|------|
| 提供元 | 京都大学生存圏研究所 (RISH) データベース |
| URL | `http://database.rish.kyoto-u.ac.jp/arch/jmadata/data/gpv/original/` |
| 更新頻度 | 1日2回（00UTC・12UTC） |
| 利用可能期間 | 過去データも無償で取得可（長期アーカイブあり） |
| ファイル形式 | GRIB2（`.bin` 拡張子） |
| 水平解像度 | 約13km（0.125°） |
| 予報時間 | 0〜264h（〜72h: 6h間隔、72h〜: 12h間隔） |

**ファイル名形式:**
```
Z__C_RJTD_{YYYYMMDDHH}0000_GSM_GPV_Rgl_FD{DDHH}_grib2.bin
```

- `Rgl`: 全球（Regional global）
- `FD{DDHH}`: 予報時間（DD=日数、HH=時間数）  
  例: `FD0000`=FT0h, `FD0018`=FT18h, `FD0100`=FT24h, `FD0112`=FT36h

**FT計算式**: `FT[h] = DD × 24 + HH`

| FD値 | FT |
|------|----|
| `0000` | 0h（初期値） |
| `0006` | 6h |
| `0012` | 12h |
| `0018` | 18h |
| `0100` | 24h（1日後） |
| `0112` | 36h |
| `0200` | 48h（2日後） |
| `0300` | 72h（3日後） |

**GSM GRIB2（Rglファイル）収録変数:**

| 変数 | レベル | 内容 |
|------|--------|------|
| `gh`, `t`, `u`, `v`, `w`, `r` | isobaricInhPa（10〜1000hPa 17レベル） | ジオポテンシャル高度・気温・風・鉛直流・相対湿度 |
| `prmsl` | meanSea | 海面更正気圧 |
| `sp` | surface | 地上気圧 |
| `10u`, `10v` | heightAboveGround (10m) | 10m風速 |
| `2t`, `2r` | heightAboveGround (2m) | 2m気温・相対湿度 |
| `hcc`, `lcc`, `mcc` | surface | 上・中・下層雲量 |

> 可降水量(tcwv/pwat)・積算降水量(tp)は **Rglファイルには含まれない**。

---

### ECMWF（欧州中期予報センター）

| 項目 | 内容 |
|------|------|
| 提供元 | ECMWF Open Data（無償公開） |
| URL | `https://data.ecmwf.int/forecasts/{YYYYMMDD}/{HH}z/ifs/0p25/{oper\|scda}/` |
| 更新頻度 | 1日4回（00/06/12/18UTC） |
| 利用可能期間 | **最新約5日分のみ無償**。過去データは Copernicus CDS API が必要 |
| ファイル形式 | GRIB2（`.grib2` 拡張子） |
| 水平解像度 | 約9km（0.25°） |
| 予報時間 | 0〜240h（〜144h: 3h間隔、144h〜: 6h間隔） |

**ファイル名形式:**
```
{YYYYMMDDHH}0000-{FT}h-oper-fc.grib2   # 00/12UTC 初期値
{YYYYMMDDHH}0000-{FT}h-scda-fc.grib2   # 06/18UTC 初期値
```

---

## GSM と ECMWF の比較

| 項目 | GSM | ECMWF |
|------|-----|-------|
| 開発・提供 | 気象庁（JMA） | 欧州中期予報センター（ECMWF） |
| 水平解像度 | 約13km | 約9km |
| 予報時間 | 〜264h | 〜240h |
| 更新頻度 | 2回/日（00/12UTC） | 4回/日（00/06/12/18UTC） |
| 無償取得 | 過去データも含めて無償（RISHアーカイブ） | **最新5日分のみ**無償 |
| 過去データ | RISHサーバーから長期取得可 | CDS API（有料アカウント等が必要な場合あり） |
| 地表面変数 | 限定的（tcwv/tp等なし） | 豊富（tcwv・tp・skt等あり） |
| 利用規約 | 気象庁利用規約 | CC BY 4.0 ライセンス |

**用途の使い分け:**
- **過去事例解析**: GSM（RISHアーカイブで長期データ取得可）
- **最新予報の高精度解析**: ECMWF（解像度が高く、地表面変数も豊富）
- **可降水量・積算降水量の表示**: ECMWF のみ対応（`ECM_SurfacePressure.py` で `--tcwv`/`--tp` オプション）

---

## ファイル構成

```
tenkizu/
├── GSM_tenkizu500hPa.py    # GSM 500hPa等高度線・渦度（旧メイン版の後継）
├── GSM_QVector850hPa.py    # GSM 850hPa Qベクター
├── GSM_Jet300hPa.py        # GSM 300hPa ジェット
├── GSM_Instability.py      # GSM 不安定域分布
├── GSM_CrossSection.py     # GSM 鉛直断面図
├── GSM_fax57.py            # GSM FAX57相当（500hPa気温・700hPa湿数）
├── GSM_fax78.py            # GSM FAX78相当（850hPa気温・風・700hPa発散）
├── GSM_faxSrfPre.py        # GSM 地上気圧・10m風・2m気温
├── GSM_EPT850hPa.py        # GSM 850hPa 相当温位・風矢羽
├── ECM_tenkizu500hPa.py    # ECMWF 500hPa等高度線・渦度
├── ECM_EPT850hPa.py        # ECMWF 850hPa相当温位
├── ECM_Fax57.py            # ECMWF FAX57（500hPa気温・700hPa湿数）
├── ECM_Fax78.py            # ECMWF FAX78（850hPa気温・風・700hPa発散）
├── ECM_SurfacePressure.py  # ECMWF 地上気圧（±可降水量/積算降水量）
├── GSM_100hPa.py           # GSM 100hPa（任意気圧面）等高度線・ISOTAC・風矢羽
├── ECM_100hPa.py           # ECMWF 100hPa（任意気圧面）等高度線・ISOTAC・風矢羽
├── upper_wind_report.py      # 上層天気図レポート生成（--push でGitHub push、MDにFTラベル付き）
├── jet_front_report.py       # ジェット・前線解析レポート生成（--push でGitHub push）
├── jet_front_wide_report.py  # 広域ジェット・前線解析レポート（上層風＋850hPa EPT、--avg_steps で予報時間平均対応）
├── jet_front_ave_report.py   # 時間平均ジェット・前線解析レポート（複数初期時刻FT=0h平均、梅雨入り判断に有効）
├── synop_report.py           # 総観天気図レポート生成（Jet・Fax57・Fax78・EPT850・地上気圧、--ecm でECM追加）
├── make_pptx.py            # PNG → PowerPoint 自動生成（GSM/ECM 主要7グループ）
├── make_pptx2.py           # PNG → PowerPoint 自動生成（残り3グループ）
├── run_all_charts.sh       # 全16スクリプト一括実行（--ecmでECM追加、デフォルトGSMのみ）
├── run_gsm_auto.py         # GSM系：最新データ自動検索・一括生成
├── run_ecm_auto.py         # ECM系：最新データ自動検索・一括生成
├── kurora_tenkizu.py       # 旧メイン版（互換維持）
├── download_gsm.py         # GSM GRIB2事前ダウンロード専用
├── run_pipeline.sh         # ダウンロード→旧メイン版 パイプライン
├── samples/                # 各種別サンプルPNG（GitHub閲覧用）
├── reports/                # レポート保存先（reports/{init_str}/{スクリプト名}_{FTラベル}.md）
├── data_gsm/               # GSM GRIB2データ格納先（Gitから除外）
├── data/ecm/               # ECMWF GRIB2データ格納先（Gitから除外）
└── output/                 # 生成天気図PNG出力先（Gitから除外）
```

---

## セットアップ

```bash
conda create -n met_env_310 python=3.10
conda activate met_env_310
conda install -c conda-forge pygrib xarray metpy matplotlib cartopy requests
pip install beautifulsoup4 python-pptx
```

| ライブラリ | 用途 |
|-----------|------|
| `pygrib` | GRIB2ファイル読み込み・データ抽出 |
| `xarray` | データセット管理 |
| `metpy` | 気象計算（渦度・発散・相当温位等） |
| `matplotlib` | 図表描画 |
| `cartopy` | 地図投影・海岸線 |
| `requests` | HTTPダウンロード |
| `beautifulsoup4` | HTMLパース（ファイルリスト取得） |
| `python-pptx` | PowerPointファイル生成 |
| `Pillow` | 画像サイズ取得（アスペクト比計算） |

---

## 使い方

### 引数の共通仕様

全スクリプトで引数順序を統一。`start_ft` 以降は省略可能。

```
python <スクリプト名> INIT_TIME [START_FT [N_STEPS [その他]]]
```

| 引数 | 説明 | デフォルト |
|------|------|----------|
| `INIT_TIME` | 初期時刻 YYYYMMDDHH（UTC）**必須** | — |
| `START_FT` | 開始予報時間。**GSM=DDHH形式**、**ECM=時間数** | GSM:`0000` / ECM:`0` |
| `N_STEPS` | 作成する枚数（6h間隔） | `1` |

---

### 一括生成（全スクリプト）

```bash
bash run_all_charts.sh INIT_TIME [START_FT_DDHH [N_STEPS|key]]
```

```bash
bash run_all_charts.sh 2026041200              # FT=0h 各1枚
bash run_all_charts.sh 2026041200 0000 5       # FT=0,6,12,18,24h 各5枚
bash run_all_charts.sh 2026041200 0100 3       # FT=24,30,36h 各3枚
bash run_all_charts.sh 2026041200 0000 key     # FT=0,12,24,36,48h 各5枚（keyモード）
```

`key` を指定すると FT=0/12/24/36/48h の5枚を生成する（`START_FT` は無視）。  
ECM 系スクリプトへの引数変換（DDHH → 時間数）は内部で自動処理される。

---

### GSM 系スクリプト（データ: RISHサーバーから自動DL）

起動時にデータが `data_gsm/` になければ自動でダウンロードを試みる。

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

```bash
# 共通の実行形式（例）
python GSM_fax57.py 2026041200            # FT=0h 1枚
python GSM_fax57.py 2026041200 0000 5    # FT=0〜24h 5枚
python GSM_fax78.py 2026041200 0000 key  # ※keyはrun_all_charts.sh専用
```

---

### ECMWF 系スクリプト（データ: ECMWF Open Dataから自動DL）

最新約5日分のみ無償取得可能。起動時に `data/ecm/` になければ自動でダウンロードを試みる。  
過去データは Copernicus CDS API（`https://cds.climate.copernicus.eu`）を利用。

`START_FT` は **時間数**（例: `0`, `6`, `24`）で指定する。

| スクリプト | 主な描画要素 |
|-----------|------------|
| `ECM_tenkizu500hPa.py` | 等高度線(60m/300m)・渦度シェード・H/L |
| `ECM_EPT850hPa.py` | 850hPa相当温位シェード・等値線・風矢羽 |
| `ECM_Fax57.py` | 500hPa等温度線(青)・700hPa T-Tdシェード・W/C |
| `ECM_Fax78.py` | 850hPa等温度線・風矢羽・700hPa発散シェード・W/C |
| `ECM_SurfacePressure.py` | 等圧線・10m風矢羽・2m等温度線・H/L（±TCWV/TP） |

```bash
python ECM_Fax57.py 2026041200 0 1          # FT=0h 1枚
python ECM_Fax57.py 2026041200 0 5          # FT=0,6,12,18,24h 5枚
python ECM_SurfacePressure.py 2026041200 0 5 --tcwv   # 可降水量シェードあり
python ECM_SurfacePressure.py 2026041200 6 3 --tp     # 積算降水量（FT>0必須）
```

---

### 自動データ取得＆一括生成（推奨）

最新の init_time を自動検索してデータ取得・全スクリプトを一括実行するスクリプト。

#### GSM系: `run_gsm_auto.py`

RISHサーバーのディレクトリ一覧を確認して最新の init_time を特定し、全9本のGSMスクリプトを実行する。

```bash
python run_gsm_auto.py                              # 最新データ、FT=0,12,24,36,48h（keyモード）
python run_gsm_auto.py --steps 5                   # 最新データ、FT=0,6,12,18,24h（連続5枚）
python run_gsm_auto.py --init-time 2026041200      # 初期時刻を手動指定
python run_gsm_auto.py --init-time 2026041200 --start-ft 0100 --steps 3  # FT=24,30,36h
```

| オプション | 説明 | デフォルト |
|-----------|------|-----------|
| `--init-time` | 初期時刻 YYYYMMDDHH（省略時は自動検索） | 自動 |
| `--steps` | 連続枚数（6h間隔。省略時はkeyモード） | keyモード |
| `--start-ft` | 開始予報時間（DDHH形式、`--steps` 使用時） | `0000` |

#### ECMWF系: `run_ecm_auto.py`

ECMWF Open Dataサーバーへの HEAD リクエストで最新の init_time を特定し、全5本のECMスクリプトを実行する。

```bash
python run_ecm_auto.py                              # 最新データ、FT=0,12,24,36,48h（keyモード）
python run_ecm_auto.py --steps 5                   # 最新データ、FT=0,6,12,18,24h（連続5枚）
python run_ecm_auto.py --init-time 2026041200      # 初期時刻を手動指定
python run_ecm_auto.py --tcwv                      # 地上気圧図に可降水量シェードを追加
python run_ecm_auto.py --tp                        # 地上気圧図に積算降水量シェードを追加（FT>0のみ）
```

| オプション | 説明 | デフォルト |
|-----------|------|-----------|
| `--init-time` | 初期時刻 YYYYMMDDHH（省略時は自動検索） | 自動 |
| `--steps` | 連続枚数（6h間隔。省略時はkeyモード） | keyモード |
| `--start-ft` | 開始予報時間（時間数、`--steps` 使用時） | `0` |
| `--tcwv` | `ECM_SurfacePressure.py` に可降水量シェードを追加 | なし |
| `--tp` | `ECM_SurfacePressure.py` に積算降水量シェードを追加（FT>0必須） | なし |

> **ECMWF Open Data は最新約5日分のみ無償**。過去データは Copernicus CDS API が必要。

---

### GSM データ事前ダウンロード

`download_gsm.py` で `data_gsm/` にデータを事前取得できる（各スクリプト起動時の自動DLと同等）。

```bash
python download_gsm.py                        # 最新データを自動検索
python download_gsm.py --date 20171210        # 指定日（00/12UTC両方）
python download_gsm.py --date 20171210 --hour 12
python download_gsm.py --start 20171208 --end 20171210
python download_gsm.py --date 20171210 --ft 0000 0012 0100
```

---

## 上層天気図レポート生成（upper_wind_report.py）

指定した気圧面の上層天気図（GSM・必要に応じてECMWF）を生成し、  
`reports/{init_str}/` に PNG と Markdown レポートをまとめて GitHub へ push するスクリプト。

### 処理の流れ

1. `GSM_100hPa.py` を呼び出して指定気圧面の天気図を生成（`output/` に PNG 出力）
2. `--ecm` 指定時は `ECM_100hPa.py` も実行
3. 生成された PNG を `reports/{init_str}/` にコピー
4. 気圧面→モデル→FT の階層構造で `upper_wind_report_{FTラベル}.md` を生成
5. `--push` 指定時のみ `git add → commit → push`（同一再実行時は変更なしをスキップ）

### 引数

```bash
python upper_wind_report.py INIT_TIME [start_ft] [n_steps] [--levels レベル...] [--ecm] [--push]
```

| 引数 | 形式 | デフォルト | 説明 |
|---|---|---|---|
| `INIT_TIME` | YYYYMMDDHH | 必須 | 初期時刻（UTC） |
| `start_ft` | DDHH | `0000` | 開始予報時間（GSMのDDHH形式） |
| `n_steps` | 整数 | `1` | 作成枚数（6h間隔） |
| `--levels` | 整数 複数可 | `100` | 気圧面 hPa（複数指定可） |
| `--ecm` | フラグ | なし | ECMWFも実行（省略時はGSMのみ） |
| `--push` | フラグ | なし | GitHub へ git push（省略時はローカル保存のみ） |

### 使用例

```bash
python upper_wind_report.py 2026041200                               # 100hPa GSMのみ FT=0h
python upper_wind_report.py 2026041200 0000 5                        # 100hPa GSMのみ 5枚
python upper_wind_report.py 2026041200 --ecm                         # 100hPa GSM+ECM FT=0h
python upper_wind_report.py 2026041200 --levels 100 50               # 100+50hPa GSMのみ
python upper_wind_report.py 2026041200 0000 5 --levels 100 50 --ecm  # 複数面・GSM+ECM
python upper_wind_report.py 2026041200 0000 5 --push                 # 生成後 GitHub push
```

### 生成物

```
reports/
└── {init_str}/
    ├── upper_wind_report_FT0.md               # 1枚の場合
    ├── upper_wind_report_FT0-24.md            # 5枚（FT=0〜24h）の場合
    ├── {dt}_FT{FFF}h_GSM_{lev}hPa_Height_Wind.png
    └── {dt}_FT{FFF}h_ECM_{lev}hPa_Height_Wind.png  # --ecm 時のみ
```

---

## ジェット・前線解析（広域）レポート生成（jet_front_wide_report.py）

上層風（指定気圧面）と 850hPa 相当温位を**広域描画範囲**で一括生成し Markdown レポートにまとめるスクリプト。  
`jet_front_report.py` から鉛直断面図・地上気圧を除いた広域版。`--avg_steps N` で複数 FT の平均天気図にも対応。

**描画範囲（固定）:**

| 層 | lonW | lonE | latS | latN |
|---|------|------|------|------|
| 上層 | 70°E | 180°E | -12°N | 30°N |
| 850hPa | 97°E | 169°E | -2.5°N | 42.5°N |

```bash
python jet_front_wide_report.py INIT_TIME [start_ft] [n_steps] [--levels ...] [--ecm] [--avg_steps N] [--push]
```

| 引数 | 形式 | デフォルト | 説明 |
|---|---|---|---|
| `INIT_TIME` | YYYYMMDDHH | 必須 | 初期時刻（UTC） |
| `start_ft` | DDHH | `0000` | 開始予報時間 |
| `n_steps` | 整数 | `1` | 出力枚数（6h間隔） |
| `--levels` | 整数 複数可 | `100` | 上層風の気圧面 hPa |
| `--ecm` | フラグ | なし | ECMWFも実行 |
| `--avg_steps` | 整数 | `1` | 平均する FT 個数（N 指定時: start_ft から N 個を 6h 間隔で平均して 1 枚出力） |
| `--push` | フラグ | なし | GitHub へ git push（省略時はローカル保存のみ） |

```bash
python jet_front_wide_report.py 2026041200                          # GSMのみ FT=0h
python jet_front_wide_report.py 2026041200 0000 5                   # GSMのみ 5枚（FT=0〜24h）
python jet_front_wide_report.py 2026041200 --ecm                    # GSM+ECM FT=0h
python jet_front_wide_report.py 2026041200 --levels 100 50          # 100hPa + 50hPa
python jet_front_wide_report.py 2026041200 0000 3 --avg_steps 4     # FT0-18h, FT24-42h, FT48-66h 各平均 3枚
python jet_front_wide_report.py 2026041200 0000 1 --levels 100 50 --ecm --avg_steps 4  # 50+100hPa 平均 GSM+ECM
python jet_front_wide_report.py 2026041200 0000 5 --push            # 生成後 GitHub push
```

生成物: `reports/{init_str}-wide/jet_front_wide_report_{FTラベル}.md`

> **沖縄地方の梅雨入り判断への活用:**  
> `--levels 100 50` を指定することで以下の2気圧面の変化を同時に確認できる。  
> - **100hPa**: チベット高気圧の発達・張り出しに伴い、沖縄付近で**北寄りの風**となることが梅雨入りの目安。  
> - **50hPa**: **東風（東寄りの風）** が卓越することが梅雨入りの目安。

---

## ジェット・前線解析（広域・時間平均）レポート生成（jet_front_ave_report.py）

指定した最新初期時刻から 12 時間ごとに遡った複数の初期時刻の **FT=0h（解析値）** を平均した天気図を生成するスクリプト。  
`jet_front_wide_report.py` と同じ広域描画範囲を使用し、瞬間場ではなく「平均場」を出力する。

**`jet_front_wide_report.py` との違い:**

| | `jet_front_wide_report.py` | `jet_front_ave_report.py` |
|---|---|---|
| 平均の軸 | 予報時間軸（同一 init_time の複数 FT） | 時間軸（複数 init_time の FT=0h） |
| データ種別 | 予報値（FT > 0 を含む） | 解析値（FT = 0h のみ） |
| 用途 | 予報シナリオの変化確認 | 現在の平均場・気候場的な変化確認 |

```bash
python jet_front_ave_report.py INIT_TIME [n_days] [--levels ...] [--ecm] [--push]
```

| 引数 | 形式 | デフォルト | 説明 |
|---|---|---|---|
| `INIT_TIME` | YYYYMMDDHH | 必須 | 最新の初期時刻（UTC、00 or 12 のみ） |
| `n_days` | 整数 | `1` | 平均日数（12h 間隔 2個 = 1日） |
| `--levels` | 整数 複数可 | `100` | 上層風の気圧面 hPa |
| `--ecm` | フラグ | なし | ECMWFも実行（省略時はGSMのみ） |
| `--push` | フラグ | なし | GitHub へ git push（省略時はローカル保存のみ） |

```bash
python jet_front_ave_report.py 2026050600                               # GSMのみ 1日(2個)平均
python jet_front_ave_report.py 2026050600 3                             # GSMのみ 3日(6個)平均
python jet_front_ave_report.py 2026050600 3 --ecm                       # GSM+ECM 3日平均
python jet_front_ave_report.py 2026050600 3 --levels 100 50             # 50+100hPa 3日平均
python jet_front_ave_report.py 2026050600 3 --levels 100 50 --ecm       # GSM+ECM 50+100hPa 3日平均
python jet_front_ave_report.py 2026050600 5 --push                      # 5日平均・生成後 GitHub push
```

生成物: `reports/{init_str}-ave/jet_front_ave_report_{n}d.md`

> **沖縄地方の梅雨入り判断への活用:**  
> `--levels 100 50` を指定して 5〜7日平均（`n_days=5`〜`7`）を確認することで梅雨入り前後の上層場変化を把握しやすい。  
> - **100hPa**: チベット高気圧の発達・張り出しに伴い、沖縄付近で**北寄りの風**となることが目安。  
> - **50hPa**: **東風（東寄りの風）** が卓越することが目安。  
> ECMWF は最新 5 日分のみ利用可能なため、長期平均には GSM（RISHアーカイブ）を使用すること。

---

## 総観天気図レポート生成（synop_report.py）

Jet300hPa・Fax57・Fax78・850hPa相当温位・地上気圧を組み合わせた  
総観スケール解析用チャートセットを一括生成し Markdown レポートにまとめるスクリプト。

```bash
python synop_report.py INIT_TIME [start_ft] [n_steps] [--ecm] [--push]
```

| 引数 | 形式 | デフォルト | 説明 |
|---|---|---|---|
| `INIT_TIME` | YYYYMMDDHH | 必須 | 初期時刻（UTC） |
| `start_ft` | DDHH | `0000` | 開始予報時間 |
| `n_steps` | 整数 | `1` | 枚数（6h間隔） |
| `--ecm` | フラグ | なし | ECMWFも実行（Jetは `ECM_100hPa.py level=300` を使用） |
| `--push` | フラグ | なし | GitHub へ git push（省略時はローカル保存のみ） |

```bash
python synop_report.py 2026041200               # GSMのみ FT=0h
python synop_report.py 2026041200 0000 5        # GSMのみ 5枚
python synop_report.py 2026041200 --ecm         # GSM+ECM FT=0h
python synop_report.py 2026041200 0000 5 --ecm --push  # GSM+ECM 5枚 → GitHub push
```

生成物: `reports/{init_str}/synop_report_{FTラベル}.md`

MDの章構成: Jet 300hPa → 500/700hPa → 700/850hPa → 850hPa相当温位 → 地上気圧（各章にGSM/ECM節）

> Jet の GSM版（Isotach+非地衡風）と ECM版（高度+風矢羽）は描画内容が異なる。

---

## 出力ファイル

```
output/{YYYYMMDDHH}_FT{FFF}h_{種別}.png
```

| スクリプト | 出力例 |
|-----------|--------|
| `GSM_tenkizu500hPa.py` | `2026041200_FT000h_500hPa_Height_VORT.png` |
| `GSM_QVector850hPa.py` | `2026041200_FT000h_850hPa_QVector.png` |
| `GSM_Jet300hPa.py` | `2026041200_FT000h_300hPa_Jet.png` |
| `GSM_Instability.py` | `2026041200_FT000h_Instability.png` |
| `GSM_CrossSection.py` | `2026041200_FT000h_CrossSection.png` |
| `GSM_fax57.py` | `2026041200_FT000h_GSM_Fax57.png` |
| `GSM_fax78.py` | `2026041200_FT000h_GSM_Fax78.png` |
| `GSM_faxSrfPre.py` | `2026041200_FT000h_GSM_SurfacePressure.png` |
| `GSM_EPT850hPa.py` | `2026041200_FT000h_GSM_850hPa_EPT.png` |
| `ECM_tenkizu500hPa.py` | `2026041200_FT000h_ECM_500hPa_Height_VORT.png` |
| `ECM_EPT850hPa.py` | `2026041200_FT000h_ECM_850hPa_EPT.png` |
| `ECM_Fax57.py` | `2026041200_FT000h_ECM_Fax57.png` |
| `ECM_Fax78.py` | `2026041200_FT000h_ECM_Fax78.png` |
| `ECM_SurfacePressure.py` | `2026041200_FT000h_ECM_SurfacePressure.png` |
| `GSM_100hPa.py` | `2026041200_FT000h_GSM_100hPa_Height_Wind.png` |
| `ECM_100hPa.py` | `2026041200_FT000h_ECM_100hPa_Height_Wind.png` |

---

## PowerPoint 自動生成

`output/` 内の PNG を PowerPoint ファイルに自動貼り付けするスクリプト。  
画像はアスペクト比を保ったままセル内に収める（Pillow でピクセルサイズ取得）。

```bash
python make_pptx.py INIT_TIME [--output ファイル名.pptx]
python make_pptx2.py INIT_TIME [--output ファイル名.pptx]
```

### `make_pptx.py` — 主要グループ（7グループ）

| スライドグループ | モード | 上段 | 下段 |
|--------------|------|------|------|
| GSM: 500hPa渦度 / 地上気圧 | 2×2 | 500hPa_Height_VORT | GSM_SurfacePressure |
| GSM: Fax57 / Fax78 | 2×2 | GSM_Fax57 | GSM_Fax78 |
| GSM: 300hPaジェット / 850hPa Qベクター | 2×2 | 300hPa_Jet | 850hPa_QVec |
| GSM: 850hPa相当温位 | 4in1 | FT=12/24/36/48h を1枚に4配置 | — |
| ECM: 500hPa渦度 / 地上気圧 | 2×2 | ECM_500hPa_Height_VORT | ECM_SurfacePressure |
| ECM: Fax57 / Fax78 | 2×2 | ECM_Fax57 | ECM_Fax78 |
| ECM: 850hPa相当温位 | 4in1 | FT=12/24/36/48h を1枚に4配置 | — |

スライドサイズ: 4:3 標準（10×7.5インチ）

### `make_pptx2.py` — 補完グループ（3グループ）

| スライドグループ | モード | 内容 |
|--------------|------|------|
| GSM: 300hPaジェット / Fax57 | 2×2 | 上段: 300hPa_Jet / 下段: GSM_Fax57 |
| GSM: 大気不安定域 / 850hPa相当温位 | 2×2 | 上段: Instability / 下段: GSM_850hPa_EPT |
| GSM: 鉛直断面図 | 1×2 | CrossSection（縦長・1行2列） |

---

## サンプル画像

`samples/` ディレクトリに全出力種別のサンプル画像（PNG 14枚 + PowerPoint 1ファイル）を収録。  
いずれも 2026-04-12 12UTC 初期値 FT=0h（相当温位は FT=12h）で生成。

| ファイル名 | 内容 |
|-----------|------|
| `sample_500hPa_Height_VORT.png` | GSM 500hPa等高度線・渦度 |
| `sample_850hPa_QVec.png` | GSM 850hPa Qベクター |
| `sample_300hPa_Jet.png` | GSM 300hPa ジェット |
| `sample_Instability.png` | GSM 大気不安定域分布 |
| `sample_CrossSection.png` | GSM 鉛直断面図 |
| `sample_GSM_Fax57.png` | GSM FAX57相当（500hPa気温・700hPa湿数） |
| `sample_GSM_Fax78.png` | GSM FAX78相当（850hPa気温・風・700hPa発散） |
| `sample_GSM_SurfacePressure.png` | GSM 地上気圧・風・2m気温 |
| `sample_GSM_850hPa_EPT.png` | GSM 850hPa相当温位・風矢羽 |
| `sample_ECM_500hPa_Height_VORT.png` | ECMWF 500hPa等高度線・渦度 |
| `sample_ECM_850hPa_EPT.png` | ECMWF 850hPa相当温位・風矢羽 |
| `sample_ECM_Fax57.png` | ECMWF FAX57相当 |
| `sample_ECM_Fax78.png` | ECMWF FAX78相当 |
| `sample_ECM_SurfacePressure.png` | ECMWF 地上気圧・風・2m気温 |
| `sample_tenkizu_2026041212.pptx` | PowerPoint サンプル（17スライド） |

---

## 画面表示について

全スクリプトはデフォルトで**画像保存のみ**実行し終了する。  
画面表示（ウィンドウ表示）を有効にしたい場合は各スクリプトの該当行のコメントを外す。

```python
# plt.show()  # ← この行を有効化
plt.close()
```

---

## 更新履歴

| 日付 | 内容 |
|------|------|
| 2026-04-08 | 初版作成。`kurora_tenkizu.py` 引数対応改修 |
| 2026-04-09 | GSM系5本・ECMWF系4本の天気図スクリプトを追加、`run_all_charts.sh` 作成 |
| 2026-04-12 | GSM版FAX天気図3本を追加（Fax57/Fax78/SurfacePressure）、keyモード実装 |
| 2026-04-12 | `run_gsm_auto.py`・`run_ecm_auto.py` を追加（最新データ自動検索・一括生成） |
| 2026-04-13 | `GSM_EPT850hPa.py`・`ECM_tenkizu500hPa.py` を追加（計14スクリプト） |
| 2026-04-13 | GSM/ECM ファイル名衝突を解消（`GSM_`/`ECM_` プレフィックスを各出力名に付与） |
| 2026-04-13 | `make_pptx.py`・`make_pptx2.py` を追加（PNG → PowerPoint 自動生成） |
| 2026-04-13 | `samples/` ディレクトリを追加（全種別サンプル画像を GitHub にアップロード） |
| 2026-04-28 | `GSM_100hPa.py`・`ECM_100hPa.py` を追加（上層等高度線・ISOTAC・風矢羽、任意気圧面対応） |
| 2026-04-28 | `upper_wind_report.py` を追加（複数気圧面・GitHub push・`upper_wind_report.md` 生成） |
| 2026-04-28 | `run_all_charts.sh` に `--ecm` フラグ追加（デフォルトGSMのみ） |
| 2026-04-28 | `jet_front_report.py` を追加（上層風・断面図・850hPa EPT・地上気圧の解析レポート） |
| 2026-04-28 | `synop_report.py` を追加（Jet300hPa・Fax57・Fax78・EPT850hPa・地上気圧の総観天気図レポート、ECM対応） |
| 2026-04-28 | 全レポートスクリプトに `--push` フラグ追加（デフォルトはローカル保存のみ。他者がクローンして実行しても誤pushしない） |
| 2026-04-28 | レポートMDファイル名にFTラベルを付与（例: `synop_report_FT0-24.md`）。同一init_str内で複数FT範囲が共存可能に |
| 2026-04-28 | `GSM_CrossSection.py` バグ修正: 出力ファイル名が有効時刻（validDate）になっていた問題を初期時刻（analDate）に修正 |
| 2026-05-01 | `GSM_100hPa.py`・`ECM_100hPa.py`・`GSM_EPT850hPa.py`・`ECM_EPT850hPa.py` に `--area` 引数を追加（描画範囲の外部指定） |
| 2026-05-01 | `jet_front_wide_report.py` を追加（上層風＋850hPa相当温位の広域版レポート） |
| 2026-05-07 | `GSM_100hPa.py`・`ECM_100hPa.py`・`GSM_EPT850hPa.py`・`ECM_EPT850hPa.py` に `--avg_steps N` 追加（予報時間軸の平均天気図生成） |
| 2026-05-07 | `jet_front_wide_report.py` に `--avg_steps N` 追加（start_ft から 6h 間隔で N 個を平均した天気図セット生成） |
| 2026-05-07 | `jet_front_ave_report.py` を新規作成（複数初期時刻 FT=0h の時間平均天気図。梅雨入り等の平均場把握に有効） |

---

## 参考

- 黒良さんのNote（GSM 500hPa天気図）: https://note.com/rkurora/n/n200fdd8f1aa1
- RISHデータベース: http://database.rish.kyoto-u.ac.jp/arch/jmadata/
- 気象業務支援センター サンプルデータ: https://www.jmbsc.or.jp/jp/online/c-onlineGsample.html#sample413
- ECMWF Open Data: https://www.ecmwf.int/en/forecasts/datasets/open-data
- Copernicus CDS（過去ECMWFデータ）: https://cds.climate.copernicus.eu
