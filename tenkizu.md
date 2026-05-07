# tenkizu — 天気図作成ツール（GSM / ECMWF）

## 概要

黒良さんのNote をベースに整備した天気図作成ツール。  
GSM（全球モデル）および ECMWF GRIB2 データをダウンロードし、  
各種高層・地上天気図を PNG 出力する。GSM/ECMWF 合計 16 種類の描画スクリプトと  
一括生成スクリプト・PowerPoint 自動生成スクリプト・レポート生成スクリプト3本を収録。

**プロジェクトパス**: `/Users/masahiro/projects/tenkizu/`  
**GitHubリポジトリ**: `https://github.com/masauehr/tenkizu`  
**開発メモ**: `development_notes.md`（詳細な改修経緯を記録）

---

## ファイル構成

### 天気図描画スクリプト（現行版）

| ファイル | 種別 | 描画内容 | 出力ファイル名パターン |
|--------|------|---------|-------------------|
| `GSM_tenkizu500hPa.py` | GSM | 500hPa 等高度線・相対渦度・H/L スタンプ | `*_500hPa_Height_VORT.png` |
| `GSM_QVector850hPa.py` | GSM | 850hPa Q ベクター発散・気温・高度 | `*_850hPa_QVector.png` |
| `GSM_Jet300hPa.py` | GSM | 300hPa ジェット（等風速線）・非地衡風・発散 | `*_300hPa_Jet.png` |
| `GSM_Instability.py` | GSM | 不安定域（SEPT－maxEPT 差）・上層気温 | `*_Instability.png` |
| `GSM_CrossSection.py` | GSM | 鉛直断面図（ポテンシャル温位・EPT・風） | `*_CrossSection.png` |
| `GSM_fax57.py` | GSM | FAX57相当: 500hPa 気温・700hPa 湿数(T-Td) | `*_GSM_Fax57.png` |
| `GSM_fax78.py` | GSM | FAX78相当: 700hPa 発散・850hPa 気温・風 | `*_GSM_Fax78.png` |
| `GSM_faxSrfPre.py` | GSM | 地上気圧・10m 風・2m 気温 | `*_GSM_SurfacePressure.png` |
| `GSM_EPT850hPa.py` | GSM | 850hPa 相当温位・風矢羽 | `*_GSM_850hPa_EPT.png` |
| `ECM_tenkizu500hPa.py` | ECM | 500hPa 等高度線・相対渦度・H/L スタンプ | `*_ECM_500hPa_Height_VORT.png` |
| `ECM_EPT850hPa.py` | ECM | 850hPa 相当温位・風矢羽 | `*_ECM_850hPa_EPT.png` |
| `ECM_Fax57.py` | ECM | FAX57: 500hPa 気温・700hPa 湿数(T-Td) | `*_ECM_Fax57.png` |
| `ECM_Fax78.py` | ECM | FAX78: 700hPa 収束・発散・850hPa 気温・風 | `*_ECM_Fax78.png` |
| `ECM_SurfacePressure.py` | ECM | 地上気圧・10m 風・2m 気温（±TCWV/TP） | `*_ECM_SurfacePressure.png` |
| `GSM_100hPa.py` | GSM | 100hPa（または任意気圧面）等高度線・ISOTAC・風矢羽 | `*_GSM_{lev}hPa_Height_Wind.png` |
| `ECM_100hPa.py` | ECM | 100hPa（または任意気圧面）等高度線・ISOTAC・風矢羽 | `*_ECM_{lev}hPa_Height_Wind.png` |

### その他スクリプト

| ファイル | 役割 |
|--------|------|
| `run_gsm_auto.py` | **GSM系: 最新データ自動検索・全9スクリプト一括実行** |
| `run_ecm_auto.py` | **ECM系: 最新データ自動検索・全5スクリプト一括実行** |
| `run_all_charts.sh` | 全16スクリプトを一括実行（init_time手動指定）。デフォルトはGSMのみ、`--ecm` でECM追加 |
| `upper_wind_report.py` | 指定気圧面の上層天気図を生成し `reports/` に MD+PNG をまとめる。`--push` で GitHub push |
| `jet_front_report.py` | 上層風・鉛直断面・850hPa相当温位・地上気圧のジェット・前線解析レポートを生成。`--push` で GitHub push |
| `jet_front_wide_report.py` | 上層風・850hPa相当温位のみの広域版レポートを生成。描画領域を拡大した「ジェット・前線解析（広域）」を `reports/{init_str}-wide/` に出力。`--avg_steps N` で予報時間軸の平均天気図に対応 |
| `jet_front_ave_report.py` | 複数初期時刻（12h間隔で遡る）のFT=0h解析値を平均した天気図を生成。梅雨入り等の平均場把握に有効。出力先: `reports/{init_str}-ave/` |
| `synop_report.py` | 総観天気図（Jet300hPa・Fax57・Fax78・EPT850hPa・地上気圧）のレポートを生成。`--ecm` でECM追加、`--push` で GitHub push |
| `make_pptx.py` | PNG → PowerPoint 自動生成（主要7グループ） |
| `make_pptx2.py` | PNG → PowerPoint 自動生成（残り3グループ） |
| `samples/` | 全種別サンプルPNG 14枚 + PowerPoint 1ファイル（GitHub閲覧用） |
| `kurora_tenkizu.py` | GSM 500hPa 天気図（旧メイン版・互換維持） |
| `download_gsm.py` | GSM GRIB2 事前ダウンロード専用 |
| `run_pipeline.sh` | ダウンロード→`kurora_tenkizu.py` の旧パイプライン |
| `reports/` | レポート保存先（`reports/{init_str}/{スクリプト名}_{FTラベル}.md`） |
| `data_gsm/` | GSM GRIB2 データ格納ディレクトリ（Git 除外） |
| `data/ecm/` | ECMWF GRIB2 データ格納ディレクトリ（Git 除外） |
| `output/` | PNG 出力先（Git 除外） |

---

## 実行環境

```bash
conda activate met_env_310  # Python 3.10
```

---

## 引数の共通仕様

全スクリプトで引数順序を統一。`start_ft` と `n_steps` は省略可能。

```
python <スクリプト名> INIT_TIME [START_FT [N_STEPS [その他オプション]]]
```

| 引数 | 説明 | 省略時デフォルト |
|------|------|----------------|
| `INIT_TIME` | 初期時刻 YYYYMMDDHH（UTC）**必須** | — |
| `START_FT` | 開始予報時間。GSM=DDHH形式、ECM=時間数 | GSM:`0000` / ECM:`0` |
| `N_STEPS` | 作成する枚数（6h 間隔） | `1` |

**GSM の DDHH 形式**: DD=日数・HH=時間数。FT(時間数) = DD×24 + HH

| DDHH | FT |
|------|-----|
| `0000` | 0h（初期値） |
| `0006` | 6h |
| `0100` | 24h（1日後） |
| `0112` | 36h |
| `0200` | 48h（2日後） |

---

## 自動データ取得＆一括生成（推奨）

最新の init_time を自動検索してデータ取得・全スクリプトを一括実行するスクリプト。  
通常の運用はこちらを使うことを推奨。

### `run_gsm_auto.py` — GSM系自動実行

RISHサーバーのディレクトリ一覧を確認して最新の init_time を特定し、全9本のGSMスクリプトを実行する。  
初期時刻から3時間以内のデータは未公開としてスキップする。

```bash
python run_gsm_auto.py                                             # 最新データ、FT=0,12,24,36,48h
python run_gsm_auto.py --steps 5                                  # 最新データ、FT=0,6,12,18,24h
python run_gsm_auto.py --init-time 2026041200                     # 初期時刻を手動指定
python run_gsm_auto.py --init-time 2026041200 --start-ft 0100 --steps 3  # FT=24,30,36h
```

| オプション | 説明 | デフォルト |
|-----------|------|-----------|
| `--init-time` | 初期時刻 YYYYMMDDHH（省略時は自動検索） | 自動 |
| `--steps` | 連続枚数（6h間隔。省略時はkeyモード） | keyモード |
| `--start-ft` | 開始予報時間（DDHH形式、`--steps` 使用時） | `0000` |

### `run_ecm_auto.py` — ECM系自動実行

ECMWF Open Dataサーバーへの HEAD リクエストで最新の init_time を特定し、全5本のECMスクリプトを実行する。  
初期時刻から4時間以内のデータは未公開としてスキップする。

```bash
python run_ecm_auto.py                              # 最新データ、FT=0,12,24,36,48h
python run_ecm_auto.py --steps 5                   # FT=0,6,12,18,24h
python run_ecm_auto.py --init-time 2026041200      # 初期時刻を手動指定
python run_ecm_auto.py --tcwv                      # 地上気圧図に可降水量シェードを追加
python run_ecm_auto.py --tp                        # 地上気圧図に積算降水量シェード（FT>0のみ）
```

| オプション | 説明 | デフォルト |
|-----------|------|-----------|
| `--init-time` | 初期時刻 YYYYMMDDHH（省略時は自動検索） | 自動 |
| `--steps` | 連続枚数（6h間隔。省略時はkeyモード） | keyモード |
| `--start-ft` | 開始予報時間（時間数、`--steps` 使用時） | `0` |
| `--tcwv` | 可降水量シェードを追加（ECM_SurfacePressure.py のみ） | なし |
| `--tp` | 積算降水量シェードを追加（FT>0必須） | なし |

> **ECMWF Open Data は最新約5日分のみ無償**。過去データは Copernicus CDS API が必要。

---

## 一括生成スクリプト `run_all_charts.sh`

全 14 スクリプトを順に実行する（init_time を手動指定する場合に使用）。引数順は個別スクリプトと同一。

```bash
bash run_all_charts.sh INIT_TIME [START_FT_DDHH [N_STEPS|key]]
```

| N_STEPS | 動作 |
|---------|------|
| 数値（例: `5`） | 開始FTから6h間隔でN枚 |
| `key` | FT=0,12,24,36,48h の固定5枚（START_FT は無視） |

```bash
bash run_all_charts.sh 2026040700              # FT=0h GSMのみ1枚
bash run_all_charts.sh 2026040700 0000 5       # FT=0,6,12,18,24h GSMのみ5枚
bash run_all_charts.sh 2026040700 0100 3       # FT=24,30,36h GSMのみ3枚
bash run_all_charts.sh 2026040700 0000 key     # FT=0,12,24,36,48h GSMのみ5枚（keyモード）
bash run_all_charts.sh 2026040700 0000 5 --ecm # FT=0,6,12,18,24h GSM+ECM5枚
```

- `--ecm` を付けるとECM系スクリプトも実行（省略時はGSMのみ。ECMファイルは100MB超のため通常は省略推奨）
- `START_FT_DDHH` は DDHH 形式で統一。ECM 系は内部で時間数へ自動変換される
- いずれかのスクリプトがエラーになっても残りは継続実行される

---

## GSM 系スクリプトの使い方

データ取得元: **京都大学 RISH サーバー**（自動ダウンロード対応）

### GSM_tenkizu500hPa.py — 500hPa 高度・渦度

```bash
python GSM_tenkizu500hPa.py INIT_TIME [START_FT [N_STEPS [LEVEL]]]
```

```bash
python GSM_tenkizu500hPa.py 2026040700            # FT=0h 1枚
python GSM_tenkizu500hPa.py 2026040700 0000 5     # FT=0〜24h 5枚
python GSM_tenkizu500hPa.py 2026040700 0100 3 500 # FT=24〜36h 500hPa 3枚
```

描画要素: 等高度線（60m/300m間隔）・5820/5400gpm 特定線・渦度シェード・渦度等値線・H/L スタンプ・渦度ピーク(+/-)

### GSM_QVector850hPa.py — 850hPa Q ベクター

```bash
python GSM_QVector850hPa.py INIT_TIME [START_FT [N_STEPS [LEVEL]]]
```

描画要素: Q ベクター発散シェード（bwr_r）・等温度線（灰色破線）・等高度線・Q ベクター矢印

### GSM_Jet300hPa.py — 300hPa ジェット

```bash
python GSM_Jet300hPa.py INIT_TIME [START_FT [N_STEPS [LEVEL]]]
```

描画要素: 収束・発散シェード（coolwarm）・等風速線（blue、40〜300kt）・等高度線・非地衡風矢羽

### GSM_Instability.py — 不安定域分布

```bash
python GSM_Instability.py INIT_TIME [START_FT [N_STEPS [PRE_TOP [PRE_LOW]]]]
```

```bash
python GSM_Instability.py 2026040700 0000 1 300 850  # 上層300hPa・下層850hPa（デフォルト）
```

描画要素: SEPT[上層] − maxEPT[下層〜1000hPa] シェード（jet_r）・上層気温等値線（赤一点鎖線）

### GSM_CrossSection.py — 鉛直断面図

```bash
python GSM_CrossSection.py INIT_TIME [START_FT [N_STEPS]] [--lat-s 45] [--lat-e 25] [--lon-s 130] [--lon-e 130] [--flag-wind 1]
```

```bash
python GSM_CrossSection.py 2026040700 0000 1 --lat-s 45 --lat-e 25 --lon-s 130 --lon-e 140
```

描画要素: ポテンシャル温位（黒）・EPT（赤）・断面方向風速（青）・風矢羽・発散シェード・インセット地図

### GSM_fax57.py — FAX57相当（500hPa 気温・700hPa 湿数）

```bash
python GSM_fax57.py INIT_TIME [START_FT [N_STEPS]]
```

```bash
python GSM_fax57.py 2026041200            # FT=0h 1枚
python GSM_fax57.py 2026041200 0000 5    # FT=0〜24h 5枚
```

描画要素: 700hPa T-Td シェード・等値線・500hPa 等温度線（blue）・-30°C 線（purple）・W/C スタンプ

### GSM_fax78.py — FAX78相当（850hPa 気温・風・700hPa 発散）

```bash
python GSM_fax78.py INIT_TIME [START_FT [N_STEPS]] [--level-div 700] [--level-t 850]
```

```bash
python GSM_fax78.py 2026041200            # FT=0h 1枚
python GSM_fax78.py 2026041200 0000 5    # FT=0〜24h 5枚
```

描画要素: 700hPa 収束・発散シェード（u/v から計算）・850hPa 等温度線（blue）・風矢羽・W/C スタンプ  
**注意**: GSM Rgl に発散変数(`d`)がないため、`mpcalc.divergence()` で u/v から算出する。

### GSM_faxSrfPre.py — 地上気圧・風・2m 気温

```bash
python GSM_faxSrfPre.py INIT_TIME [START_FT [N_STEPS]]
```

```bash
python GSM_faxSrfPre.py 2026041200            # FT=0h 1枚
python GSM_faxSrfPre.py 2026041200 0000 5    # FT=0〜24h 5枚
```

描画要素: MSL 等圧線（4hPa/20hPa 太線）・10m 風矢羽・2m 等温度線（緑）・H/L スタンプ（気圧値付き）  
**注意**: GSM Rgl には可降水量(tcwv/pwat)・積算降水量(tp)が含まれないため非対応。

---

## ECMWF 系スクリプトの使い方

データ取得元: **ECMWF Open Data**（最新約5日分のみ無償）  
過去データは Copernicus CDS API（`https://cds.climate.copernicus.eu`）が必要。

`START_FT` は **時間数**（例: `0`, `6`, `24`）。

### ECM_EPT850hPa.py — 850hPa 相当温位・風

```bash
python ECM_EPT850hPa.py INIT_TIME [START_FT [N_STEPS [LEVEL]]] [--area LON_W LON_E LAT_S LAT_N]
```

描画要素: 相当温位シェード（jet カラーマップ）・相当温位等値線（細線/太線）・風矢羽  
**`--area`**: 描画範囲を上書き指定（デフォルト: 115〜151°E, 20〜50°N）

### ECM_Fax57.py — FAX57（500hPa 気温・700hPa 湿数）

```bash
python ECM_Fax57.py INIT_TIME [START_FT [N_STEPS]]
```

描画要素: 700hPa T-Td シェード・等値線・500hPa 等温度線（blue）・-30°C 線（purple）・W/C スタンプ

### ECM_Fax78.py — FAX78（700hPa 収束発散・850hPa 気温・風）

```bash
python ECM_Fax78.py INIT_TIME [START_FT [N_STEPS]] [--level-div 700] [--level-t 850]
```

描画要素: 700hPa 収束・発散シェード・850hPa 等温度線（blue）・風矢羽・W/C スタンプ

### ECM_SurfacePressure.py — 地上気圧・風・2m 気温

```bash
python ECM_SurfacePressure.py INIT_TIME [START_FT [N_STEPS]] [--tcwv] [--tp]
```

```bash
python ECM_SurfacePressure.py 2026040712 0 5 --tcwv   # 可降水量シェードあり
python ECM_SurfacePressure.py 2026040712 6 3 --tp     # 積算降水量シェードあり（FT>0必須）
```

描画要素: MSL 等圧線（4hPa/20hPa 太線）・10m 風矢羽・2m 等温度線（緑）・H/L スタンプ（気圧値付き）  
オプション: `--tcwv` 可降水量シェード / `--tp` 積算降水量シェード

---

## 上層風天気図スクリプト（GSM_100hPa.py / ECM_100hPa.py）

100hPa を標準とする上層等高度線・ISOTAC・風矢羽天気図。`level` 引数で 50hPa などの気圧面にも対応。

- **ISOTAC**: 20kt 間隔のカラー塗り（YlOrRd）+ 青等風速線
- **等高度線**: 120m 間隔（黒線）
- **風矢羽**: m/s → ノット変換済み
- **表示域**: 84〜156°E, 17〜55°N（ステレオ投影）※ `--area` で変更可
- **平滑化**: ECM版のみ 3×3 uniform_filter を適用（0.25°格子を GSM 並みに平滑化）
- **`--area LON_W LON_E LAT_S LAT_N`**: 描画範囲を上書き指定（`jet_front_wide_report.py` がこのオプションで広域領域を渡す）

### GSM_100hPa.py

```bash
python GSM_100hPa.py INIT_TIME [START_FT_DDHH [N_STEPS [LEVEL]]]
```

```bash
python GSM_100hPa.py 2026041200            # 100hPa FT=0h 1枚
python GSM_100hPa.py 2026041200 0000 5     # 100hPa FT=0〜24h 5枚
python GSM_100hPa.py 2026041200 0100 3 50  # 50hPa FT=24〜36h 3枚
```

出力: `output/{dt}_FT{FFF}h_GSM_{level}hPa_Height_Wind.png`

### ECM_100hPa.py

```bash
python ECM_100hPa.py INIT_TIME [START_FT_H [N_STEPS [LEVEL]]]
```

```bash
python ECM_100hPa.py 2026041200 0 1        # 100hPa FT=0h 1枚
python ECM_100hPa.py 2026041200 0 5        # 100hPa FT=0〜24h 5枚
python ECM_100hPa.py 2026041200 24 3 50    # 50hPa FT=24〜36h 3枚
```

出力: `output/{dt}_FT{FFF}h_ECM_{level}hPa_Height_Wind.png`

> **注意**: ECMファイルは 100MB 超。50MB 未満のファイルは不完全と判定し自動削除・再ダウンロードする。

---

## 上層天気図レポート生成（upper_wind_report.py）

指定した気圧面の上層天気図（GSM/ECM）を生成し、`reports/{init_str}/` に PNG + `upper_wind_report.md` をまとめて GitHub push するスクリプト。

```bash
python upper_wind_report.py INIT_TIME [start_ft] [n_steps] [--levels ...] [--ecm] [--push]
```

| 引数 | 形式 | デフォルト | 説明 |
|---|---|---|---|
| `init_time` | YYYYMMDDHH | 必須 | 初期時刻（UTC） |
| `start_ft` | DDHH | `0000` | 開始予報時間 |
| `n_steps` | 整数 | `1` | 枚数（6h間隔） |
| `--levels` | 整数 複数可 | `100` | 気圧面 hPa（複数指定可） |
| `--ecm` | フラグ | なし | ECMWFも実行（省略時はGSMのみ） |
| `--push` | フラグ | なし | GitHub へ git push（省略時はローカル保存のみ） |

```bash
python upper_wind_report.py 2026041200                               # 100hPa GSMのみ FT=0h
python upper_wind_report.py 2026041200 0000 5                        # 100hPa GSMのみ 5枚
python upper_wind_report.py 2026041200 --ecm                         # 100hPa GSM+ECM FT=0h
python upper_wind_report.py 2026041200 --levels 100 50               # 100+50hPa GSMのみ
python upper_wind_report.py 2026041200 0000 5 --levels 100 50 --ecm  # 複数面・GSM+ECM
python upper_wind_report.py 2026041200 0000 5 --push                 # 生成後 GitHub push
```

生成物:
- `reports/{init_str}/upper_wind_report_{FTラベル}.md`（気圧面 → モデル → FT の階層構造）
  - 例: `upper_wind_report_FT0.md`（1枚）、`upper_wind_report_FT0-24.md`（5枚）
- `reports/{init_str}/*.png`（PNG コピー）

同一 init_str で再実行した場合、変更がなければコミット・プッシュをスキップ（エラーにならない）。

---

## ジェット・前線解析レポート生成（jet_front_report.py）

上層風・鉛直断面・850hPa相当温位・地上気圧を組み合わせ、  
ジェット気流と前線の関係を一覧できる Markdown レポートを生成して GitHub push するスクリプト。

**使用するスクリプト（内部で自動実行）:**

| スクリプト | 内容 | ECM対応 |
|---|---|---|
| `GSM_100hPa.py` / `ECM_100hPa.py` | 上層風（指定気圧面の等高度線・ISOTAC・風矢羽） | `--ecm` 時 |
| `GSM_CrossSection.py` | 鉛直断面図（ポテンシャル温位・EPT・風） | GSMのみ |
| `GSM_EPT850hPa.py` / `ECM_EPT850hPa.py` | 850hPa 相当温位・風矢羽（前線帯の把握） | `--ecm` 時 |
| `GSM_faxSrfPre.py` / `ECM_SurfacePressure.py` | 地上気圧・10m風・2m気温 | `--ecm` 時 |

```bash
python jet_front_report.py INIT_TIME [start_ft] [n_steps] [--levels ...] [--ecm] [--push]
                           [--lat-s 度] [--lat-e 度] [--lon-s 度] [--lon-e 度]
```

| 引数 | 形式 | デフォルト | 説明 |
|---|---|---|---|
| `INIT_TIME` | YYYYMMDDHH | 必須 | 初期時刻（UTC） |
| `start_ft` | DDHH | `0000` | 開始予報時間 |
| `n_steps` | 整数 | `1` | 枚数（6h間隔） |
| `--levels` | 整数 複数可 | `100` | 上層風の気圧面 hPa |
| `--ecm` | フラグ | なし | ECMWFも実行 |
| `--push` | フラグ | なし | GitHub へ git push（省略時はローカル保存のみ） |
| `--lat-s` | 度 | `45` | 断面図 北端緯度 |
| `--lat-e` | 度 | `25` | 断面図 南端緯度 |
| `--lon-s` | 度 | `130` | 断面図 西端経度 |
| `--lon-e` | 度 | `130` | 断面図 東端経度（lon-s=lon-eで経線断面） |

```bash
python jet_front_report.py 2026041200                               # GSMのみ FT=0h
python jet_front_report.py 2026041200 0000 5                        # GSMのみ 5枚
python jet_front_report.py 2026041200 --ecm                         # GSM+ECM FT=0h
python jet_front_report.py 2026041200 --levels 100 50               # 上層風を100+50hPa
python jet_front_report.py 2026041200 0000 5 --ecm --levels 100 50
python jet_front_report.py 2026041200 --lat-s 45 --lat-e 25 --lon-s 125 --lon-e 135
python jet_front_report.py 2026041200 0000 5 --push                 # 生成後 GitHub push
```

断面図の凡例: カラー=発散（赤/青系）、等温位線（黒）、等相当温位線（赤）、断面に沿った等風速線（青）、風矢羽（黒）

生成物: `reports/{init_str}/jet_front_report_{FTラベル}.md`

---

## ジェット・前線解析（広域）レポート生成（jet_front_wide_report.py）

`jet_front_report.py` の広域版。**上層風・850hPa相当温位のみ**（断面図・地上気圧は除外）を広い描画範囲で生成する。  
出力先は `reports/{init_str}-wide/`、Markdownタイトルは「ジェット・前線解析（広域）」。

**描画範囲（固定）:**

| 層 | lonW | lonE | latS | latN | 東西幅 | 南北幅 |
|---|------|------|------|------|--------|--------|
| 上層 | 70°E | 180°E | -12°N | 30°N | 110° | 42° |
| 850hPa | 97°E | 169°E | -2.5°N | 42.5°N | 72° | 45° |

**使用するスクリプト（内部で自動実行）:**

| スクリプト | 内容 | ECM対応 |
|---|---|---|
| `GSM_100hPa.py` / `ECM_100hPa.py` | 上層風（`--area` で広域範囲を指定） | `--ecm` 時 |
| `GSM_EPT850hPa.py` / `ECM_EPT850hPa.py` | 850hPa 相当温位・風矢羽（`--area` で広域範囲を指定） | `--ecm` 時 |

```bash
python jet_front_wide_report.py INIT_TIME [start_ft] [n_steps] [--levels ...] [--ecm] [--push]
```

| 引数 | 形式 | デフォルト | 説明 |
|---|---|---|---|
| `INIT_TIME` | YYYYMMDDHH | 必須 | 初期時刻（UTC） |
| `start_ft` | DDHH | `0000` | 開始予報時間 |
| `n_steps` | 整数 | `1` | 枚数（6h間隔） |
| `--levels` | 整数 複数可 | `100` | 上層風の気圧面 hPa |
| `--ecm` | フラグ | なし | ECMWFも実行 |
| `--push` | フラグ | なし | GitHub へ git push（省略時はローカル保存のみ） |

```bash
python jet_front_wide_report.py 2026041200                         # GSMのみ FT=0h
python jet_front_wide_report.py 2026041200 0000 5                  # GSMのみ 5枚
python jet_front_wide_report.py 2026041200 --ecm                   # GSM+ECM FT=0h
python jet_front_wide_report.py 2026041200 --levels 100 50         # 100+50hPa
python jet_front_wide_report.py 2026041200 0000 5 --push           # 生成後 GitHub push
python jet_front_wide_report.py 2026041200 0000 3 --avg_steps 4    # FT0-18h, FT24-42h, FT48-66h 平均 3枚
python jet_front_wide_report.py 2026041200 0000 1 --levels 100 50 --ecm --avg_steps 4  # 50+100hPa 平均 GSM+ECM
```

生成物: `reports/{init_str}-wide/jet_front_wide_report_{FTラベル}.md`

> #### 沖縄地方の梅雨入り判断への活用
>
> **`jet_front_wide_report.py` は沖縄地方の梅雨入りを判断する際に特に有効なスクリプト。**  
> 沖縄地方の梅雨入りは、モンスーン気流の活発化とともに上層の流場が大きく変化することで特徴づけられる。  
> 具体的には **100hPa・50hPa の南西風（モンスーンジェット）の強化** が梅雨入りの目安のひとつとされており、  
> `--levels 100 50` を指定することで 2気圧面の変化を同時に確認できる。  
> 広域描画領域（70〜180°E, -12〜30°N）によりインド洋〜西太平洋にかけての上層流場全体を俯瞰でき、  
> モンスーン域全体の変化を捉えるのに適している。  
> `--avg_steps 4` などを組み合わせて予報時間軸で平均することで、ノイズを除去した平均的な流場の変化も確認できる。

---

## ジェット・前線解析（広域・時間平均）レポート生成（jet_front_ave_report.py）

`jet_front_wide_report.py` の時間軸平均版。**同一の広域描画領域**（上層: 70〜180°E, -12〜30°N / 850hPa: 97〜169°E, -2.5〜42.5°N）を使用し、  
指定した最新初期時刻から12時間ごとに遡った複数の初期時刻の **FT=0h（解析値）** を平均した天気図を生成する。  
瞬間場ではなく「平均場」を表すため、総観スケールの場の変化を滑らかに把握する用途に適する。  
出力先は `reports/{init_str}-ave/`。

**`jet_front_wide_report.py` との比較:**

| | `jet_front_wide_report.py` | `jet_front_ave_report.py` |
|---|---|---|
| 平均の軸 | 予報時間軸（同一init_timeの複数FT） | 時間軸（複数init_timeのFT=0h） |
| データ | 予報値（FT > 0 を含む） | 解析値（FT = 0h のみ） |
| 用途 | 予報シナリオの変化確認 | 現在の平均場・気候場的な変化確認 |

```bash
python jet_front_ave_report.py INIT_TIME [n_days] [--levels ...] [--ecm] [--push]
```

| 引数 | 形式 | デフォルト | 説明 |
|---|---|---|---|
| `INIT_TIME` | YYYYMMDDHH | 必須 | 最新の初期時刻（UTC、00 or 12 のみ） |
| `n_days` | 整数 | `1` | 平均日数（12h間隔 2個 = 1日） |
| `--levels` | 整数 複数可 | `100` | 上層風の気圧面 hPa |
| `--ecm` | フラグ | なし | ECMWFも実行（省略時はGSMのみ） |
| `--push` | フラグ | なし | GitHub へ git push（省略時はローカル保存のみ） |

```bash
python jet_front_ave_report.py 2026050600           # GSMのみ 1日(2個)平均
python jet_front_ave_report.py 2026050600 3         # GSMのみ 3日(6個)平均
python jet_front_ave_report.py 2026050600 3 --ecm   # GSM+ECM 3日平均
python jet_front_ave_report.py 2026050600 3 --levels 100 50        # 50+100hPa 3日平均
python jet_front_ave_report.py 2026050600 3 --levels 100 50 --ecm  # GSM+ECM 50+100hPa 3日平均
python jet_front_ave_report.py 2026050600 5 --push  # 5日平均・生成後 GitHub push
```

出力ファイル名:
- `output/{YYYYMMDDHH}_AVG{n}d_GSM_{lev}hPa_Height_Wind.png`
- `output/{YYYYMMDDHH}_AVG{n}d_GSM_850hPa_EPT.png`

生成物: `reports/{init_str}-ave/jet_front_ave_report_{n}d.md`

> #### 沖縄地方の梅雨入り判断への活用
>
> **`jet_front_ave_report.py` は沖縄地方の梅雨入り前後の上層場変化を定量的に把握するのに特に有効。**  
> 梅雨入りを判断する際には、直前数日間の解析値（FT=0h）を平均することで、一時的な擾乱の影響を除いた  
> 「平均的な上層場」を確認できる。  
> **100hPa・50hPa は沖縄地方の梅雨入りの目安となる気圧面であり**、モンスーンジェットの強化（南西風の卓越）が  
> この高度で最初に現れることが多い。`--levels 100 50` を指定して5〜7日平均（`n_days=5` 〜 `7`）を確認することで、  
> 梅雨入りに向けた上層場のシフトを捉えやすくなる。  
> ECMWF Open Data は最新5日分のみ利用可能なため、長期平均には GSM（RISHアーカイブ）を使用すること。

---

## 総観天気図レポート生成（synop_report.py）

Jet300hPa・Fax57（500/700hPa）・Fax78（700/850hPa）・850hPa相当温位・地上気圧を組み合わせ、  
総観スケールの天気解析に必要なチャートセットを一括生成して Markdown レポートにまとめるスクリプト。

**使用するスクリプト（内部で自動実行）:**

| スクリプト | 内容 | ECM対応 |
|---|---|---|
| `GSM_Jet300hPa.py` | 300hPa ジェット（等風速線・非地衡風） | GSMのみ |
| `ECM_100hPa.py`（level=300） | 300hPa 高度・風矢羽（ECM版） | `--ecm` 時 |
| `GSM_fax57.py` / `ECM_Fax57.py` | 500hPa気温・700hPa湿数 | `--ecm` 時 |
| `GSM_fax78.py` / `ECM_Fax78.py` | 700hPa発散・850hPa気温・風 | `--ecm` 時 |
| `GSM_EPT850hPa.py` / `ECM_EPT850hPa.py` | 850hPa 相当温位・風矢羽 | `--ecm` 時 |
| `GSM_faxSrfPre.py` / `ECM_SurfacePressure.py` | 地上気圧・10m風・2m気温 | `--ecm` 時 |

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
python synop_report.py 2026041200 0000 5 --ecm  # GSM+ECM 5枚
python synop_report.py 2026041200 0000 5 --push # 生成後 GitHub push
```

生成物: `reports/{init_str}/synop_report_{FTラベル}.md`

**MDの章構成:**
1. Jet 300hPa（GSM: Isotach・非地衡風 / ECM: 高度・風矢羽）
2. 500/700hPa（等高度線・渦度・風）
3. 700/850hPa（等高度線・相当温位・風）
4. 850hPa 相当温位・風矢羽
5. 地上気圧・10m風・2m気温

> **注意**: Jet の GSM版（`GSM_Jet300hPa.py`）と ECM版（`ECM_100hPa.py level=300`）は描画内容が異なる。  
> GSM版は Isotach + 非地衡風矢羽、ECM版は等高度線 + 風矢羽。

---

## データソース

### GSM（気象庁 全球モデル）

| 項目 | 内容 |
|------|------|
| 提供元 | 京都大学生存圏研究所 (RISH) データベース |
| URL | `http://database.rish.kyoto-u.ac.jp/arch/jmadata/data/gpv/original/` |
| 更新頻度 | 1日2回（00UTC・12UTC） |
| 利用可能期間 | 過去データも無償（長期アーカイブあり） |
| 水平解像度 | 約13km（0.125°） |
| 予報時間 | 0〜264h（〜72h: 6h間隔、72h〜: 12h間隔） |

**ファイル名形式**:
```
Z__C_RJTD_{YYYYMMDDHH}0000_GSM_GPV_Rgl_FD{DDHH}_grib2.bin
```

- `Rgl`: 全球（Regional global）
- `FD{DDHH}`: FT[h] = DD×24 + HH

**Rglファイル収録変数（実データで確認済み）**:

| 収録あり | 収録なし |
|---------|---------|
| 気圧面: `gh`,`t`,`u`,`v`,`w`,`r`（17レベル） | 可降水量（tcwv/pwat） |
| 地表: `prmsl`,`sp`,`10u`,`10v`,`2t`,`2r` | 積算降水量（tp） |
| 雲量: `hcc`,`lcc`,`mcc` | |

### ECMWF（欧州中期予報センター）

| 項目 | 内容 |
|------|------|
| 提供元 | ECMWF Open Data（無償公開） |
| URL | `https://data.ecmwf.int/forecasts/{YYYYMMDD}/{HH}z/ifs/0p25/{oper\|scda}/` |
| 更新頻度 | 1日4回（00/06/12/18UTC） |
| 利用可能期間 | **最新約5日分のみ無償**。過去データは Copernicus CDS API が必要 |
| 水平解像度 | 約9km（0.25°） |
| 予報時間 | 0〜240h |
| ライセンス | CC BY 4.0 |

**ファイル名形式**:
```
{YYYYMMDDHH}0000-{FT}h-oper-fc.grib2   # 00/12UTC 初期値
{YYYYMMDDHH}0000-{FT}h-scda-fc.grib2   # 06/18UTC 初期値
```

**過去データの取得**:  
5日以上前のデータは ECMWF Open Data からは取得不可。  
Copernicus CDS API（`https://cds.climate.copernicus.eu`）を利用する。

---

## GSM と ECMWF の比較

| 項目 | GSM | ECMWF |
|------|-----|-------|
| 開発・提供 | 気象庁（JMA） | 欧州中期予報センター |
| 水平解像度 | 約13km | 約9km |
| 更新頻度 | 2回/日 | 4回/日 |
| 無償取得範囲 | 過去全期間（RISHアーカイブ） | **最新5日分のみ** |
| 地表面変数 | 限定的（tcwv/tp等なし） | 豊富（tcwv・tp・skt等あり） |

**使い分け指針:**
- **過去事例解析** → GSM（RISHで長期アーカイブ取得可）
- **最新予報の高精度解析** → ECMWF（解像度高く地表面変数も豊富）
- **可降水量・積算降水量の表示** → ECMWF のみ（`ECM_SurfacePressure.py` の `--tcwv`/`--tp`）

---

## 出力ファイル名

```
output/{YYYYMMDDHH}_FT{FFF}h_{種別}.png
```

| スクリプト | 出力例 |
|-----------|--------|
| `GSM_tenkizu500hPa.py` | `2026041300_FT000h_500hPa_Height_VORT.png` |
| `GSM_QVector850hPa.py` | `2026041300_FT000h_850hPa_QVector.png` |
| `GSM_Jet300hPa.py` | `2026041300_FT000h_300hPa_Jet.png` |
| `GSM_Instability.py` | `2026041300_FT000h_Instability.png` |
| `GSM_CrossSection.py` | `2026041300_FT000h_CrossSection.png` |
| `GSM_fax57.py` | `2026041300_FT000h_GSM_Fax57.png` |
| `GSM_fax78.py` | `2026041300_FT000h_GSM_Fax78.png` |
| `GSM_faxSrfPre.py` | `2026041300_FT000h_GSM_SurfacePressure.png` |
| `GSM_EPT850hPa.py` | `2026041300_FT000h_GSM_850hPa_EPT.png` |
| `ECM_tenkizu500hPa.py` | `2026041300_FT000h_ECM_500hPa_Height_VORT.png` |
| `ECM_EPT850hPa.py` | `2026041300_FT000h_ECM_850hPa_EPT.png` |
| `ECM_Fax57.py` | `2026041300_FT000h_ECM_Fax57.png` |
| `ECM_Fax78.py` | `2026041300_FT000h_ECM_Fax78.png` |
| `ECM_SurfacePressure.py` | `2026041300_FT000h_ECM_SurfacePressure.png` |
| `GSM_100hPa.py` | `2026041300_FT000h_GSM_100hPa_Height_Wind.png` |
| `ECM_100hPa.py` | `2026041300_FT000h_ECM_100hPa_Height_Wind.png` |

---

## PowerPoint 自動生成

PNG を PowerPoint スライドに自動貼り付けするスクリプト。  
Pillow でピクセルサイズを取得しアスペクト比を保持、セル内中央配置。  
スライドサイズは 4:3 標準（10×7.5インチ）。

```bash
python make_pptx.py INIT_TIME [--output ファイル名.pptx]
python make_pptx2.py INIT_TIME [--output ファイル名.pptx]
```

### `make_pptx.py` — 主要7グループ

| スライドグループ | モード | 上段 | 下段/内容 |
|--------------|------|------|---------|
| GSM: 500hPa渦度 / 地上気圧 | 2×2 | 500hPa_Height_VORT | GSM_SurfacePressure |
| GSM: Fax57 / Fax78 | 2×2 | GSM_Fax57 | GSM_Fax78 |
| GSM: 300hPaジェット / Qベクター | 2×2 | 300hPa_Jet | 850hPa_QVec |
| GSM: 850hPa相当温位 | 4in1 | FT=12,24,36,48h を1枚に2×2配置 | — |
| ECM: 500hPa渦度 / 地上気圧 | 2×2 | ECM_500hPa_Height_VORT | ECM_SurfacePressure |
| ECM: Fax57 / Fax78 | 2×2 | ECM_Fax57 | ECM_Fax78 |
| ECM: 850hPa相当温位 | 4in1 | FT=12,24,36,48h を1枚に2×2配置 | — |

### `make_pptx2.py` — 補完3グループ

| スライドグループ | モード | 内容 |
|--------------|------|------|
| 300hPaジェット / Fax57 | 2×2 | 上段: 300hPa_Jet / 下段: GSM_Fax57 |
| 大気不安定域 / 850hPa相当温位 | 2×2 | 上段: Instability / 下段: GSM_850hPa_EPT |
| 鉛直断面図 | 1×2 | CrossSection（1行2列・全高使用） |

---

## 画面表示について

全スクリプトはデフォルトで**画像保存のみ**実行し終了する。  
画面表示（`plt.show()`）を有効にしたい場合は、各スクリプトの該当行のコメントを外す。

```python
# plt.show()  # 画面表示する場合はコメントアウトを外す  ← この行を有効化
plt.close()
```

---

## 更新履歴

| 日付 | 内容 |
|------|------|
| 2026-04-08 | 初版作成。`kurora_tenkizu.py` 引数対応改修、`download_gsm.py`/`run_pipeline.sh` 新規作成 |
| 2026-04-09 | `GSM_tenkizu500hPa.py` ほかGSM系4本・ECMWF系4本の天気図スクリプトを追加 |
| 2026-04-09 | `run_all_charts.sh` 一括生成スクリプト追加 |
| 2026-04-09 | 全スクリプトの `start_ft`・`n_steps` を省略可能に変更（デフォルト: 0/`0000`・1） |
| 2026-04-09 | `plt.show()` をコメントアウト化（画像保存のみに変更） |
| 2026-04-09 | 一括スクリプトの引数順を個別スクリプトと統一（第2引数=START_FT、第3引数=N_STEPS） |
| 2026-04-12 | GSM版FAX天気図3本を追加（`GSM_fax57.py`・`GSM_fax78.py`・`GSM_faxSrfPre.py`） |
| 2026-04-12 | `run_all_charts.sh` に `key` モード追加（FT=0,12,24,36,48h の固定5枚生成） |
| 2026-04-12 | `run_gsm_auto.py`・`run_ecm_auto.py` を追加（最新データ自動検索・一括生成） |
| 2026-04-13 | `GSM_EPT850hPa.py`・`ECM_tenkizu500hPa.py` を追加（計14スクリプト） |
| 2026-04-13 | GSM/ECM 出力ファイル名の衝突を解消（`GSM_`/`ECM_` プレフィックス付与） |
| 2026-04-13 | `make_pptx.py`・`make_pptx2.py` を追加（PNG → PowerPoint 自動生成） |
| 2026-04-13 | `samples/` ディレクトリを追加（全種別サンプルPNG 14枚 + PowerPoint 1ファイルを GitHub にアップロード） |
| 2026-04-28 | `GSM_100hPa.py`・`ECM_100hPa.py` を追加（上層等高度線・ISOTAC・風矢羽。level引数で任意気圧面に対応） |
| 2026-04-28 | `upper_wind_report.py` を追加（複数気圧面対応・GitHub自動push・`upper_wind_report.md` 生成） |
| 2026-04-28 | `run_all_charts.sh` に `--ecm` フラグを追加（デフォルトGSMのみ、`--ecm` でECM追加実行） |
| 2026-04-28 | `jet_front_report.py` を追加（上層風・断面図・850hPa EPT・地上気圧のジェット・前線解析レポート） |
| 2026-04-28 | `synop_report.py` を追加（Jet300hPa・Fax57・Fax78・EPT850hPa・地上気圧の総観天気図レポート、ECM対応） |
| 2026-04-28 | `upper_wind_report.py` / `jet_front_report.py` / `synop_report.py` に `--push` フラグ追加（デフォルトはローカル保存のみ） |
| 2026-04-28 | レポートMDファイル名にFTラベルを付与（例: `synop_report_FT0-24.md`）。同一init_strで複数FT範囲の共存が可能に |
| 2026-04-28 | `GSM_CrossSection.py` のバグ修正（出力ファイル名が有効時刻になっていた問題を初期時刻に修正） |
| 2026-05-01 | `GSM_100hPa.py`・`ECM_100hPa.py`・`GSM_EPT850hPa.py`・`ECM_EPT850hPa.py` に `--area LON_W LON_E LAT_S LAT_N` 引数を追加（描画範囲の外部指定が可能に） |
| 2026-05-01 | `jet_front_wide_report.py` を追加（上層風＋850hPa相当温位の広域版レポート。鉛直断面図・地上気圧は除外。出力先: `reports/{init_str}-wide/`） |
| 2026-05-07 | `GSM_100hPa.py`・`ECM_100hPa.py`・`GSM_EPT850hPa.py`・`ECM_EPT850hPa.py` に `--avg_steps N` 引数を追加（予報時間軸の平均天気図生成に対応） |
| 2026-05-07 | `jet_front_wide_report.py` に `--avg_steps N` 引数を追加（start_ftから6h間隔でN個を平均した天気図セット生成に対応） |
| 2026-05-07 | `jet_front_ave_report.py` を新規作成（複数初期時刻のFT=0h時間平均天気図生成。梅雨入り等の平均場把握に有効） |
