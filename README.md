# tenkizu — 天気図作成ツール（GSM / ECMWF）

黒良さんのNote（https://note.com/rkurora/n/n200fdd8f1aa1 ）他をベースに、  
GSM（全球スペクトルモデル）や ECMWF GRIB2 データから各種高層・地上天気図を作成するツールです。

---

## 概要

- **対応データ**: 気象庁 GSM（全球モデル）・ECMWF（欧州中期予報センターモデル）
- **図法**: ステレオ投影（中心: 60°N, 140°E）
- **描画領域**: 108〜156°E, 17〜55°N（極東域）
- **出力形式**: PNG（DPI 150, 10×8 インチ）
- **実行環境**: Python 3.10（conda 環境 `met_env_310`）

---

## データソース

### GSM（気象庁 全球スペクトルモデル）

| 項目 | 内容 |
|------|------|
| 提供元 | 京都大学生存圏研究所 (RISH) データベース |
| URL | `http://database.rish.kyoto-u.ac.jp/arch/jmadata/data/gpv/original/` |
| 更新頻度 | 1日2回（00UTC・12UTC） |
| 利用可能期間 | 過去データも無償で取得可（長期アーカイブあり） |
| ファイル形式 | GRIB2（`.bin` 拡張子） |
| 水平解像度 | 約20km（0.2° × 0.25°） |
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
| 水平解像度 | 約20km | 約9km（より高精度） |
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
├── ECM_EPT850hPa.py        # ECMWF 850hPa相当温位
├── ECM_Fax57.py            # ECMWF FAX57（500hPa気温・700hPa湿数）
├── ECM_Fax78.py            # ECMWF FAX78（850hPa気温・風・700hPa発散）
├── ECM_SurfacePressure.py  # ECMWF 地上気圧（±可降水量/積算降水量）
├── run_all_charts.sh       # 全12スクリプト一括実行
├── kurora_tenkizu.py       # 旧メイン版（互換維持）
├── download_gsm.py         # GSM GRIB2事前ダウンロード専用
├── run_pipeline.sh         # ダウンロード→旧メイン版 パイプライン
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
pip install beautifulsoup4
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
| `GSM_fax57.py` | `2026041200_FT000h_Fax57.png` |
| `GSM_fax78.py` | `2026041200_FT000h_Fax78.png` |
| `GSM_faxSrfPre.py` | `2026041200_FT000h_SurfacePressure.png` |
| `ECM_EPT850hPa.py` | `2026041200_FT000h_850hPa_EPT.png` |
| `ECM_Fax57.py` | `2026041200_FT000h_Fax57.png` |
| `ECM_Fax78.py` | `2026041200_FT000h_Fax78.png` |
| `ECM_SurfacePressure.py` | `2026041200_FT000h_SurfacePressure.png` |

---

## 画面表示について

全スクリプトはデフォルトで**画像保存のみ**実行し終了する。  
画面表示（ウィンドウ表示）を有効にしたい場合は各スクリプトの該当行のコメントを外す。

```python
# plt.show()  # ← この行を有効化
plt.close()
```

---

## 参考

- 黒良さんのNote（GSM 500hPa天気図）: https://note.com/rkurora/n/n200fdd8f1aa1
- RISHデータベース: http://database.rish.kyoto-u.ac.jp/arch/jmadata/
- 気象業務支援センター サンプルデータ: https://www.jmbsc.or.jp/jp/online/c-onlineGsample.html#sample413
- ECMWF Open Data: https://www.ecmwf.int/en/forecasts/datasets/open-data
- Copernicus CDS（過去ECMWFデータ）: https://cds.climate.copernicus.eu
