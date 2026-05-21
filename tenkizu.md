# tenkizu — 天気図作成ツール（GSM / ECMWF）

## 概要

黒良さんのNote をベースに整備した天気図作成ツール。  
GSM（全球モデル）および ECMWF GRIB2 データをダウンロードし、  
各種高層・地上天気図を PNG 出力する。GSM/ECMWF 合計 16 種類の描画スクリプトと  
一括生成スクリプト・PowerPoint 自動生成スクリプト・レポート生成スクリプト5本・エマグラム描画スクリプト1本を収録。

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
| `jet_front_report.py` | 上層風・鉛直断面・850hPa相当温位・地上気圧のジェット・前線解析レポートを生成。`--push` で GitHub push |
| `jet_front_wide_report.py` | 上層風・850hPa相当温位のみの広域版レポートを生成。描画領域を拡大した「ジェット・前線解析（広域）」を `reports/{init_str}-wide/` に出力。`--avg_steps N` で予報時間軸の平均天気図に対応 |
| `jet_front_ave_report.py` | 複数初期時刻（12h間隔で遡る）のFT=0h解析値を平均した天気図を生成。梅雨入り等の平均場把握に有効。出力先: `reports/{init_str}-ave/` |
| `upper_wind_report.py` | 指定気圧面の上層天気図を生成し `reports/` に MD+PNG をまとめる。`--push` で GitHub push |
| `synop_report.py` | 総観天気図（Jet300hPa・Fax57・Fax78・EPT850hPa・地上気圧）のレポートを生成。`--ecm` でECM追加、`--charts` で種別指定、`--push` で GitHub push |
| `emagram.py` | **エマグラム・温位エマグラム描画**。Wyoming高層ゾンデデータを取得し、エマグラム（CAPE/CIN・ホドグラフ付き）と温位エマグラム（θ/θe/θes/θw）をPNG出力。`--report` でMarkdownレポート生成、`--push` でGitHub push |
| `GRIB2_Emagram.py` | GSM/ECMWFのGRIB2から任意緯度・経度の格子点エマグラム・温位エマグラムを作図。`--start-ft`/`--steps`/`--interval` で複数FTを連続作図。`--push` でGitHub push |
| `JRA55_Emagram.py` | JRA-55 NetCDFから任意緯度・経度の格子点エマグラム・温位エマグラムを作図。`--push` でGitHub push |
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
| `N_STEPS` | 作成する枚数またはプリセット名（`12h` / `24h`） | `1` |
| `--interval N` | FT間隔 時間数（プリセット指定時は無視） | `6` |

**時間プリセット（N_STEPS に指定可能）:**

| プリセット | FT一覧 | 枚数 | 用途 |
|-----------|--------|------|------|
| `12h` | 0, 12, 24, 36, 48h | 5枚 | 短期予報チェック（12h間隔） |
| `24h` | 0, 24, 48, 72, 96, 120h | 6枚 | 中期予報チェック（24h間隔） |

**GSM の DDHH 形式**: DD=日数・HH=時間数。FT(時間数) = DD×24 + HH

| DDHH | FT |
|------|-----|
| `0000` | 0h（初期値） |
| `0006` | 6h |
| `0100` | 24h（1日後） |
| `0112` | 36h |
| `0200` | 48h（2日後） |

---

## レポート生成スクリプト

5本のレポートスクリプトが利用可能。いずれも `reports/{init_str}/` に PNG と Markdown を生成し、`--push` 指定時に GitHub へ push する。

### 上層天気図レポート生成（upper_wind_report.py）

指定した気圧面の上層天気図（GSM/ECM）を生成し、`reports/{init_str}/` に PNG + `upper_wind_report.md` をまとめて GitHub push するスクリプト。

```bash
python upper_wind_report.py INIT_TIME [start_ft] [n_steps] [--interval N] [--levels ...] [--ecm] [--push]
```

| 引数 | 形式 | デフォルト | 説明 |
|---|---|---|---|
| `init_time` | YYYYMMDDHH | 必須 | 初期時刻（UTC） |
| `start_ft` | DDHH | `0000` | 開始予報時間 |
| `n_steps` | 整数 / `12h` / `24h` | `1` | 枚数またはプリセット |
| `--interval` | 時間数 | `6` | FT間隔（プリセット指定時は無視） |
| `--levels` | 整数 複数可 | `100` | 気圧面 hPa（複数指定可） |
| `--ecm` | フラグ | なし | ECMWFも実行（省略時はGSMのみ） |
| `--push` | フラグ | なし | GitHub へ git push（省略時はローカル保存のみ） |

```bash
python upper_wind_report.py 2026041200                                # 100hPa GSMのみ FT=0h
python upper_wind_report.py 2026041200 0000 5                         # 100hPa GSMのみ 5枚（6h間隔）
python upper_wind_report.py 2026041200 0000 12h                       # 12hプリセット（FT=0〜48h）
python upper_wind_report.py 2026041200 0000 24h                       # 24hプリセット（FT=0〜120h）
python upper_wind_report.py 2026041200 0000 5 --interval 12           # 12h間隔 5枚
python upper_wind_report.py 2026041200 --ecm                          # 100hPa GSM+ECM FT=0h
python upper_wind_report.py 2026041200 --levels 100 50                # 100+50hPa GSMのみ
python upper_wind_report.py 2026041200 0000 12h --levels 100 50 --ecm # 複数面・GSM+ECM
python upper_wind_report.py 2026041200 0000 5 --push                  # 生成後 GitHub push
```

生成物:
- `reports/{init_str}/upper_wind_report_{FTラベル}.md`（気圧面 → モデル → FT の階層構造）
  - 例: `upper_wind_report_FT0.md`（1枚）、`upper_wind_report_FT0-24.md`（5枚）
- `reports/{init_str}/*.png`（PNG コピー）

同一 init_str で再実行した場合、変更がなければコミット・プッシュをスキップ（エラーにならない）。

---

### ジェット・前線解析レポート生成（jet_front_report.py）

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
python jet_front_report.py INIT_TIME [start_ft] [n_steps] [--interval N] [--levels ...] [--ecm] [--push]
                           [--lat-s 度] [--lat-e 度] [--lon-s 度] [--lon-e 度]
```

| 引数 | 形式 | デフォルト | 説明 |
|---|---|---|---|
| `INIT_TIME` | YYYYMMDDHH | 必須 | 初期時刻（UTC） |
| `start_ft` | DDHH | `0000` | 開始予報時間 |
| `n_steps` | 整数 / `12h` / `24h` | `1` | 枚数またはプリセット |
| `--interval` | 時間数 | `6` | FT間隔（プリセット指定時は無視） |
| `--levels` | 整数 複数可 | `100` | 上層風の気圧面 hPa |
| `--ecm` | フラグ | なし | ECMWFも実行 |
| `--push` | フラグ | なし | GitHub へ git push（省略時はローカル保存のみ） |
| `--lat-s` | 度 | `45` | 断面図 北端緯度 |
| `--lat-e` | 度 | `25` | 断面図 南端緯度 |
| `--lon-s` | 度 | `130` | 断面図 西端経度 |
| `--lon-e` | 度 | `130` | 断面図 東端経度（lon-s=lon-eで経線断面） |

```bash
python jet_front_report.py 2026041200                               # GSMのみ FT=0h
python jet_front_report.py 2026041200 0000 5                        # GSMのみ 5枚（6h間隔）
python jet_front_report.py 2026041200 0000 12h                      # 12hプリセット（FT=0〜48h）
python jet_front_report.py 2026041200 0000 24h                      # 24hプリセット（FT=0〜120h）
python jet_front_report.py 2026041200 0000 5 --interval 12          # 12h間隔 5枚
python jet_front_report.py 2026041200 --ecm                         # GSM+ECM FT=0h
python jet_front_report.py 2026041200 --levels 100 50               # 上層風を100+50hPa
python jet_front_report.py 2026041200 0000 12h --ecm --levels 100 50
python jet_front_report.py 2026041200 --lat-s 45 --lat-e 25 --lon-s 125 --lon-e 135
python jet_front_report.py 2026041200 0000 5 --push                 # 生成後 GitHub push
```

断面図の凡例: カラー=発散（赤/青系）、等温位線（黒）、等相当温位線（赤）、断面に沿った等風速線（青）、風矢羽（黒）

生成物: `reports/{init_str}/jet_front_report_{FTラベル}.md`

---

### ジェット・前線解析（広域）レポート生成（jet_front_wide_report.py）

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
python jet_front_wide_report.py INIT_TIME [start_ft] [n_steps] [--interval N] [--levels ...] [--ecm] [--avg_steps N] [--push]
```

| 引数 | 形式 | デフォルト | 説明 |
|---|---|---|---|
| `INIT_TIME` | YYYYMMDDHH | 必須 | 初期時刻（UTC） |
| `start_ft` | DDHH | `0000` | 開始予報時間 |
| `n_steps` | 整数 / `12h` / `24h` | `1` | 枚数またはプリセット（`--avg_steps` 指定時は整数のみ） |
| `--interval` | 時間数 | `6` | FT間隔（プリセット指定時・`--avg_steps` 指定時は無視） |
| `--levels` | 整数 複数可 | `100` | 上層風の気圧面 hPa |
| `--ecm` | フラグ | なし | ECMWFも実行 |
| `--avg_steps` | 整数 | `1` | 平均する FT 個数（6h 間隔で N 個を平均して 1 枚出力） |
| `--push` | フラグ | なし | GitHub へ git push（省略時はローカル保存のみ） |

```bash
python jet_front_wide_report.py 2026041200                           # GSMのみ FT=0h
python jet_front_wide_report.py 2026041200 0000 5                    # GSMのみ 5枚（6h間隔）
python jet_front_wide_report.py 2026041200 0000 12h                  # 12hプリセット（FT=0〜48h）
python jet_front_wide_report.py 2026041200 0000 5 --interval 12      # 12h間隔 5枚
python jet_front_wide_report.py 2026041200 --ecm                     # GSM+ECM FT=0h
python jet_front_wide_report.py 2026041200 --levels 100 50           # 100+50hPa
python jet_front_wide_report.py 2026041200 0000 5 --push             # 生成後 GitHub push
python jet_front_wide_report.py 2026041200 0000 3 --avg_steps 4      # FT0-18h, FT24-42h, FT48-66h 平均 3枚
python jet_front_wide_report.py 2026041200 0000 1 --levels 100 50 --ecm --avg_steps 4  # 50+100hPa 平均 GSM+ECM
```

生成物: `reports/{init_str}-wide/jet_front_wide_report_{FTラベル}.md`

> #### 沖縄地方の梅雨入り判断への活用
>
> **`jet_front_wide_report.py` は沖縄地方の梅雨入りを判断する際に特に有効なスクリプト。**  
> 沖縄地方の梅雨入りは上層の流場変化と密接に関連しており、以下の2気圧面が目安となる。  
> - **100hPa**: チベット高気圧の発達・張り出しに伴い、沖縄付近で**北寄りの風**に変わることが梅雨入りの目安。  
> - **50hPa**: 準2年振動（QBO）などと関連し、**東風（東寄りの風）** が卓越することが梅雨入りの目安。  
>
> `--levels 100 50` を指定することで 2気圧面の変化を同時に確認できる。  
> 広域描画領域（70〜180°E, -12〜30°N）によりチベット高気圧の状態とその張り出し方向を俯瞰でき、  
> 梅雨入りに向けた流場の変化を捉えるのに適している。  
> `--avg_steps 4` などを組み合わせて予報時間軸で平均することで、ノイズを除去した平均的な流場の変化も確認できる。

---

### ジェット・前線解析（広域・時間平均）レポート生成（jet_front_ave_report.py）

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
> **100hPa・50hPa は沖縄地方の梅雨入りの目安となる気圧面：**
> - **100hPa**: チベット高気圧の発達・張り出しに伴い、沖縄付近で**北寄りの風**となることが目安。  
> - **50hPa**: **東風（東寄りの風）** が卓越することが目安。  
>
> `--levels 100 50` を指定して5〜7日平均（`n_days=5` 〜 `7`）を確認することで、  
> 梅雨入りに向けた上層場のシフトを捉えやすくなる。  
> ECMWF Open Data は最新5日分のみ利用可能なため、長期平均には GSM（RISHアーカイブ）を使用すること。

---

### 総観天気図レポート生成（synop_report.py）

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
python synop_report.py INIT_TIME [start_ft] [n_steps] [--interval N] [--charts ...] [--ecm] [--push]
```

| 引数 | 形式 | デフォルト | 説明 |
|---|---|---|---|
| `INIT_TIME` | YYYYMMDDHH | 必須 | 初期時刻（UTC） |
| `start_ft` | DDHH | `0000` | 開始予報時間 |
| `n_steps` | 整数 / `12h` / `24h` | `1` | 枚数またはプリセット |
| `--interval` | 時間数 | `6` | FT間隔（プリセット指定時は無視） |
| `--charts` | `jet` `fax57` `fax78` `ept` `srf` 複数可 | 全て | 描画する種別 |
| `--ecm` | フラグ | なし | ECMWFも実行（Jetは `ECM_100hPa.py level=300` を使用） |
| `--push` | フラグ | なし | GitHub へ git push（省略時はローカル保存のみ） |

**`--charts` 選択肢:**

| 値 | 内容 |
|----|------|
| `jet` | GSM Jet 300hPa（Isotach・非地衡風・高度） |
| `fax57` | GSM/ECM 500/700hPa（等高度線・渦度・風） |
| `fax78` | GSM/ECM 700/850hPa（等高度線・相当温位・風） |
| `ept` | GSM/ECM 850hPa 相当温位・風矢羽 |
| `srf` | GSM/ECM 地上気圧・10m風・2m気温 |

```bash
python synop_report.py 2026041200                              # GSMのみ FT=0h（全種別）
python synop_report.py 2026041200 0000 5                       # GSMのみ 5枚（6h間隔）
python synop_report.py 2026041200 0000 12h                     # 12hプリセット（FT=0〜48h）
python synop_report.py 2026041200 0000 24h                     # 24hプリセット（FT=0〜120h）
python synop_report.py 2026041200 0000 5 --interval 12         # 12h間隔 5枚
python synop_report.py 2026041200 --ecm                        # GSM+ECM FT=0h
python synop_report.py 2026041200 --charts jet fax57           # jet と fax57 のみ
python synop_report.py 2026041200 0000 12h --ecm --charts ept srf  # プリセット＋種別指定
python synop_report.py 2026041200 0000 5 --ecm --push          # GSM+ECM 5枚 → GitHub push
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

### エマグラム・温位エマグラム描画（emagram.py）

Wyoming Upper Air データベースから高層ゾンデ観測を取得し、エマグラムと温位エマグラムをPNG出力するスクリプト。`--report` でMarkdownレポートを生成し、`--push` でGitHubへ自動pushできる。

**エマグラム描画要素:**

| 要素 | 内容 |
|------|------|
| 温度・露点温度 | 赤線・緑線 |
| 風矢羽 | 全層 |
| パーセルプロファイル | 850hPa以下で最大相当温位の気塊を持ち上げ |
| CAPE/CIN | シェード（赤/青） |
| 乾燥断熱線・湿潤断熱線・等混合比線 | 補助線 |
| ホドグラフ | 右上インセット（高度カラー） |

**温位エマグラム描画要素:**

| 要素 | 内容 |
|------|------|
| θ（温位） | 黒線 |
| θe（相当温位） | 緑線 |
| θes（飽和相当温位） | 赤線 |
| θw（飽和温位） | 紫線 |
| 等飽和混合比線 | 青点線（横軸:温位） |
| 横軸範囲 | データの実測値から自動決定（10K単位・5Kマージン） |
| 高度上限 | 100hPa |

```bash
python emagram.py [--date YYYYMMDDHH] [--site 地点名] [--id STATION_ID]
                  [--mode {both,emagram,pt}] [--report] [--push] [--no-save] [--show]
```

| 引数 | 説明 | デフォルト |
|------|------|-----------|
| `--date` | 観測日時（UTC）例: `2024051200` | 現在UTC-6h以前の直近00/12UTC |
| `--site` | 地点名 | 石垣島 |
| `--id` | WMO地点番号（`--site` より優先） | — |
| `--mode` | `both` / `emagram` / `pt` | `both` |
| `--report` | `reports/{tag}/` にPNG+MD生成 | なし |
| `--push` | git add → commit → push（`--report` 必須） | なし |
| `--no-save` | PNG保存スキップ（`--report` 時は無効） | なし |
| `--show` | 画面表示（GUI必要） | なし |

**対応地点（`--site` に指定する地点名）:**

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

※台湾地点はWyoming Upper Airデータベース未収録のため取得不可の場合あり

```bash
python emagram.py                                      # 石垣島 直近時刻 両図
python emagram.py --date 2024051200                    # 石垣島 指定日時
python emagram.py --site 南大東島                       # 南大東島 直近時刻
python emagram.py --site 館野 --mode emagram           # 館野 エマグラムのみ
python emagram.py --site 名瀬 --mode pt                # 名瀬 温位エマグラムのみ
python emagram.py --site 石垣島 --report               # レポート生成のみ
python emagram.py --site 石垣島 --report --push        # レポート生成 + GitHub push
python emagram.py --id 47807 --report --push           # WMO番号直接指定でpush
```

**生成物（`--report` 指定時）:**
- `reports/{YYYYMMDDHH}_{station_id}/emagram_report.md`
- `reports/{YYYYMMDDHH}_{station_id}/{tag}_emagram.png`
- `reports/{YYYYMMDDHH}_{station_id}/{tag}_pt_emagram.png`

**データソース:** Wyoming Upper Air (https://weather.uwyo.edu/)  
**必要ライブラリ:** `siphon`（`pip install siphon` でインストール）

---

## 自動データ取得＆一括生成（推奨）

最新の init_time を自動検索してデータ取得・全スクリプトを一括実行するスクリプト。  
通常の運用はこちらを使うことを推奨。

### `run_gsm_auto.py` — GSM系自動実行

RISHサーバーのディレクトリ一覧を確認して最新の init_time を特定し、全9本のGSMスクリプトを実行する。  
初期時刻から3時間以内のデータは未公開としてスキップする。

```bash
python run_gsm_auto.py                                             # 最新データ、FT=0,12,24,36,48h（12hプリセット）
python run_gsm_auto.py --steps 5                                  # 最新データ、FT=0,6,12,18,24h
python run_gsm_auto.py --init-time 2026041200                     # 初期時刻を手動指定
python run_gsm_auto.py --init-time 2026041200 --start-ft 0100 --steps 3  # FT=24,30,36h
```

| オプション | 説明 | デフォルト |
|-----------|------|-----------|
| `--init-time` | 初期時刻 YYYYMMDDHH（省略時は自動検索） | 自動 |
| `--steps` | 連続枚数（6h間隔。省略時は12hプリセット） | 12hプリセット |
| `--start-ft` | 開始予報時間（DDHH形式、`--steps` 使用時） | `0000` |

### `run_ecm_auto.py` — ECM系自動実行

ECMWF Open Dataサーバーへの HEAD リクエストで最新の init_time を特定し、全5本のECMスクリプトを実行する。  
初期時刻から4時間以内のデータは未公開としてスキップする。

```bash
python run_ecm_auto.py                              # 最新データ、FT=0,12,24,36,48h（12hプリセット）
python run_ecm_auto.py --steps 5                   # FT=0,6,12,18,24h
python run_ecm_auto.py --init-time 2026041200      # 初期時刻を手動指定
python run_ecm_auto.py --tcwv                      # 地上気圧図に可降水量シェードを追加
python run_ecm_auto.py --tp                        # 地上気圧図に積算降水量シェード（FT>0のみ）
```

| オプション | 説明 | デフォルト |
|-----------|------|-----------|
| `--init-time` | 初期時刻 YYYYMMDDHH（省略時は自動検索） | 自動 |
| `--steps` | 連続枚数（6h間隔。省略時は12hプリセット） | 12hプリセット |
| `--start-ft` | 開始予報時間（時間数、`--steps` 使用時） | `0` |
| `--tcwv` | 可降水量シェードを追加（ECM_SurfacePressure.py のみ） | なし |
| `--tp` | 積算降水量シェードを追加（FT>0必須） | なし |

> **ECMWF Open Data は最新約5日分のみ無償**。過去データは Copernicus CDS API が必要。

---

## 一括生成スクリプト `run_all_charts.sh`

全 16 スクリプトを順に実行する（init_time を手動指定する場合に使用）。引数順は個別スクリプトと同一。

```bash
bash run_all_charts.sh INIT_TIME [START_FT_DDHH [N_STEPS|12h|24h]] [--ecm] [--interval N]
```

| N_STEPS | 動作 |
|---------|------|
| 数値（例: `5`） | 開始FTから `--interval` 間隔でN枚（デフォルト6h間隔） |
| `12h` | FT=0,12,24,36,48h の固定5枚（START_FT は無視） |
| `24h` | FT=0,24,48,72,96,120h の固定6枚（START_FT は無視） |

```bash
bash run_all_charts.sh 2026040700                       # FT=0h GSMのみ1枚
bash run_all_charts.sh 2026040700 0000 5                # FT=0,6,12,18,24h GSMのみ5枚
bash run_all_charts.sh 2026040700 0100 3                # FT=24,30,36h GSMのみ3枚
bash run_all_charts.sh 2026040700 0000 12h              # FT=0,12,24,36,48h GSMのみ5枚（12hプリセット）
bash run_all_charts.sh 2026040700 0000 24h              # FT=0,24,48,72,96,120h GSMのみ6枚（24hプリセット）
bash run_all_charts.sh 2026040700 0000 5 --interval 12  # 12h間隔 5枚
bash run_all_charts.sh 2026040700 0000 5 --ecm          # FT=0,6,12,18,24h GSM+ECM5枚
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

## 平均化処理のコード解説

### 2種類の平均化モード

| モード | 対象スクリプト | 平均の軸 | データ種別 |
|--------|-------------|---------|----------|
| 予報時間軸平均（`--avg_steps N`） | `GSM/ECM_100hPa.py`・`GSM/ECM_EPT850hPa.py` | 同一 init_time の N 個の FT（6h 間隔） | 予報値（FT ≥ 0） |
| 時間軸平均（`n_days`） | `jet_front_ave_report.py` | 異なる init_time の FT=0h（12h 間隔） | 解析値（FT = 0h のみ） |

---

### 予報時間軸平均（`--avg_steps N`）

各描画スクリプトの `plot_avg(batch_start_h, avg_steps, ...)` 関数で実装されている。

**① FTリスト生成**

```python
ft_list = [batch_start_h + i * 6 for i in range(avg_steps)]
# 例: batch_start_h=0, avg_steps=4 → [0, 6, 12, 18]
```

**② 各FTのGRIB2を読み込んでリストに積む**

```python
for ft_h in ft_list:
    # GRIB2 から gh / u / v を読み込む
    valHt_all.append(_valHt)
    valWu_all.append(_valWu)
    valWv_all.append(_valWv)
```

**③ axis=0 方向（FT軸）で算術平均**

```python
valHt = np.mean(valHt_all, axis=0)
valWu = np.mean(valWu_all, axis=0)
valWv = np.mean(valWv_all, axis=0)
```

**④ 複数バッチ（`n_steps > 1`）の場合**

`main()` 側でバッチ番号 `step_i` をインクリメントして呼び出す。バッチ開始 FT は `avg_steps` 分ずつずれ、バッチ間に重複はない。

```python
for step_i in range(args.n_steps):
    batch_start_h = start_ft_h + step_i * (6 * avg_steps)
    plot_avg(..., batch_start_h, avg_steps, ...)
# 例: start_ft=0, avg_steps=4, n_steps=3
#   step_i=0 → batch_start=0  (FT 0, 6, 12, 18h)
#   step_i=1 → batch_start=24 (FT 24, 30, 36, 42h)
#   step_i=2 → batch_start=48 (FT 48, 54, 60, 66h)
```

`jet_front_wide_report.py` はサブプロセス経由で `--avg_steps N` を透過的に各描画スクリプトに渡す。

```python
avg_arg = f"--avg_steps {avg_steps}" if avg_steps > 1 else ""
run_python(f"GSM_100hPa.py {init_str} {start_ft} {n_steps} {lev} {area_arg} {avg_arg}", ...)
```

---

### ECM版の平滑化タイミング

ECM の格子間隔（0.25°）は GSM（0.125°）より粗く天気図がざらつくため、各ファイル読み込み直後に `scipy.ndimage.uniform_filter(size=3)`（3×3 格子平均）を適用してから、平均処理のリストに積む。

```python
# ECM_100hPa.py / ECM_EPT850hPa.py の plot_avg 内
_valHt = uniform_filter(_valHt, size=3)   # 平均前に平滑化
_valWu = uniform_filter(_valWu, size=3)
_valWv = uniform_filter(_valWv, size=3)

valHt_all.append(_valHt)                  # 平滑済みデータを積む
```

**平均後ではなく各ファイル読み込み直後に適用**することで、各 FT の格子スケールノイズが平均値に影響しないようにしている。`plot_one`（通常1枚描画）でも同じ位置で適用されており、処理の一貫性がある。

---

### EPT の平均化（物理的に正しい手順）

相当温位（EPT）は気温（T）と相対湿度（RH）の**非線形関数**である。そのため「各FTの EPT を先に計算してから平均する」と、平均場の EPT が過大・過小評価されやすい。  
実装では「**T と RH を先に平均してから EPT を計算**」する手順を採用している。

```python
# GSM_EPT850hPa.py / ECM_EPT850hPa.py の plot_avg 内

# ❶ 各FTから T, RH, u, v の生データを収集
for ft_h in ft_list:
    ...
    valTm_all.append(_valTm)   # 気温 [K]
    valRh_all.append(_valRh)   # 相対湿度 [%]

# ❷ T と RH を算術平均（EPT 計算の前）
valTm = np.mean(valTm_all, axis=0)
valRh = np.mean(valRh_all, axis=0)

# ❸ 平均済み T, RH から MetPy で露点温度 → EPT を計算
dsp['dewpoint_temperature'] = mpcalc.dewpoint_from_relative_humidity(
    dsp['Temperature'], dsp['RelativHumidity'])
dsp['Equivalent_Potential_temperature'] = mpcalc.equivalent_potential_temperature(
    dsp['level'], dsp['Temperature'], dsp['dewpoint_temperature'])
```

---

### 時間軸平均（`jet_front_ave_report.py`）

**① 初期時刻リスト生成**

```python
def build_init_times(newest_dt, n_days):
    n_steps = n_days * 2           # 1日 = 12h×2個
    return [newest_dt - timedelta(hours=i * 12) for i in range(n_steps)]
# 例: newest_dt=2026050600, n_days=3 → 6個（新しい順）
#   [050600, 050512, 050500, 050412, 050400, 050312]
```

**② 各 init_time の FT=0h ファイルだけを読み込む**

```python
def plot_gsm_100hpa_avg(init_times, ...):
    for dt in init_times:
        # FD0000 固定（FT=0h のみ）
        gr_fn = f"Z__C_RJTD_{dt.strftime('%Y%m%d%H')}0000_GSM_GPV_Rgl_FD0000_grib2.bin"
        # 読み込み → リストに追加
        valHt_all.append(_valHt)
        ...

    valHt = np.mean(valHt_all, axis=0)   # init_time 方向の算術平均
```

`--avg_steps` との本質的な違いは **FD0000（FT=0h）だけを使う**点にある。

**③ タイトルへの期間表示**

```python
period_str = f"{init_times[-1].strftime('%Y%m%d%H')}〜{init_times[0].strftime('%Y%m%d%H')}UTC"
# 例: "2026050312〜2026050600UTC"

f"GSM {n_days}day avg (FT=0h×{len(init_times)}) {period_str} {tagHp}hPa ..."
```

平均に使った初期時刻の範囲を図のタイトルに明示し、どの期間の平均場かを一目でわかるようにしている。

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

## JRA-55 再解析データによる天気図作成

JRA-55 は予報値ではなく再解析値であるため、GSM/ECMWF 系スクリプトの `INIT_TIME + FT` ではなく、解析対象時刻 `YYYYMMDDHH` を直接指定する。  
対応時刻は 00/06/12/18UTC の4回/日。

### 認証情報

JRA-55取得用の ID/password は `jra55_config.ini` に記述する。  
このファイルは `.gitignore` により GitHub にはアップロードされない。

```ini
[jra55]
user = your_user_id
password = your_password
```

雛形:

```bash
cp jra55_config.example.ini jra55_config.ini
```

### JRA-55総観天気図レポート

`jra55_synop_report.py` は `synop_report.py` のJRA-55版で、複数のPNG天気図を生成し、Markdownに埋め込む。

```bash
python jra55_synop_report.py DATE [--hour H] [--charts ...] [--push]
```

| 引数 | 説明 | デフォルト |
|------|------|----------|
| `DATE` | `YYYYMMDD` または `YYYYMMDDHH`（UTC） | 必須 |
| `--hour H` | `YYYYMMDD` 指定時のUTC時刻。`0/6/12/18` のみ | `0` |
| `--charts` | `jet fax57 fax78 ept srf` から作成対象を指定 | 全図 |
| `--data-dir` | JRA-55 NetCDF保存先 | `./data/Jra55` |
| `--output-dir` | 一時PNG保存先 | `./output` |
| `--config` | 認証設定ファイル | `./jra55_config.ini` |
| `--push` | 生成したMarkdown/PNGとスクリプト変更をGitHubへpush | なし |

例:

```bash
python jra55_synop_report.py 19590915
python jra55_synop_report.py 1959091512 --charts jet srf
python jra55_synop_report.py 19590915 --push
```

生成される図:

| chart | 内容 |
|-------|------|
| `jet` | 300hPa 等風速・発散・非地衡風 |
| `fax57` | 500hPa気温・700hPa湿数 |
| `fax78` | 700hPa発散・850hPa気温・850hPa風 |
| `ept` | 850hPa相当温位・850hPa風 |
| `srf` | 海面更正気圧・地上風・地上気温 |

出力先:

```text
reports/{YYYYMMDDHH}-jra55-synop/jra55_synop_report_{YYYYMMDDHH}.md
reports/{YYYYMMDDHH}-jra55-synop/{YYYYMMDDHH}_JRA55_*.png
```

### JRA-55 300hPaジェット単図

300hPaジェット・上層発散のみを作成する場合:

```bash
python JRA55_JetDivergence.py YYYYMMDDHH
python JRA55_JetDivergence.py 1961071518 --level 300
```

レポート化する場合:

```bash
python jra55_jet_report.py 1961071518
python jra55_jet_report.py 1961071518 --push
```

### JRA-55内部スクリプト

| スクリプト | 役割 |
|-----------|------|
| `JRA55_JetDivergence.py` | 300hPaなど任意気圧面の高度・等風速・発散・非地衡風を描画 |
| `JRA55_SynopCharts.py` | `jet/fax57/fax78/ept/srf` の各PNGを生成 |
| `jra55_jet_report.py` | 300hPaジェット単図のMarkdownレポート生成 |
| `jra55_synop_report.py` | JRA-55総観天気図セットのMarkdownレポート生成 |

### 使用するJRA-55データ

| 図 | 主な変数 | ファイル種別 |
|----|----------|------------|
| `jet` | `HGT`, `UGRD`, `VGRD`, `RELD` 300hPa | 等圧面・月別 |
| `fax57` | `TMP` 500hPa, `TMP/RH` 700hPa | 等圧面・月別 |
| `fax78` | `RELD` 700hPa, `TMP/UGRD/VGRD` 850hPa | 等圧面・月別 |
| `ept` | `TMP/RH/UGRD/VGRD` 850hPa | 等圧面・月別 |
| `srf` | `PRMSL_msl`, `UGRD_fhg`, `VGRD_fhg`, `TMP_fhg` | 地上・年別 |

RISH上の代表的なパス:

```text
https://database.rish.kyoto-u.ac.jp/arch/jra55/data/isobaric_1.25d/HGT/YYYY/HGT_YYYYMM.nc
https://database.rish.kyoto-u.ac.jp/arch/jra55/data/isobaric_1.25d/TMP/YYYY/TMP_YYYYMM.nc
https://database.rish.kyoto-u.ac.jp/arch/jra55/data/isobaric_1.25d/RH/YYYY/RH_YYYYMM.nc
https://database.rish.kyoto-u.ac.jp/arch/jra55/data/isobaric_1.25d/surf/PRMSL/PRMSL_msl_YYYY.nc
```

ローカル保存:

```text
data/Jra55/
```

注意:

- 初回実行では月別・年別NetCDFを自動取得するため時間がかかる。
- 取得済みファイルは `data/Jra55/` から再利用される。
- `data/Jra55/`, `output/`, `.cache/`, `.matplotlib/`, `jra55_config.ini` はGit管理対象外。
- JRA-55の地上変数はファイル内変数名が `PRMSL_msl`, `UGRD_fhg` のようにサフィックス付きである。
- 1959年9月15日00UTCのテスト出力例は `reports/1959091500-jra55-synop/` にある。

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
| 2026-05-10 | 全レポートスクリプト・`run_all_charts.sh` に時間プリセット（`12h`/`24h`）と `--interval` オプションを追加 |
| 2026-05-10 | `synop_report.py` に `--charts` オプション追加（描画種別の個別選択。旧 `--keys` から改称） |
| 2026-05-10 | `run_all_charts.sh` のプリセット名を `key` → `12h`/`24h` に改称、`24h` プリセット（FT=0〜120h）を追加 |
| 2026-05-10 | マニュアル（README.md・tenkizu.md）を再編成: レポートスクリプトを前方に移動、引数仕様を最新化 |
| 2026-05-12 | `emagram.py` 新規作成: Wyoming高層ゾンデデータによるエマグラム・温位エマグラム描画。石垣島デフォルト・全国13地点対応。`--report`/`--push` でMarkdownレポート+GitHub push。温位エマグラム横軸自動スケール・高度上限100hPa |
| 2026-05-13 | JRA-55再解析データ対応を追加。`JRA55_JetDivergence.py`・`JRA55_SynopCharts.py`・`jra55_jet_report.py`・`jra55_synop_report.py` により、300hPa単図と総観天気図セットのMarkdownレポート生成・GitHub pushに対応 |
| 2026-05-13 | `GRIB2_Emagram.py`・`JRA55_Emagram.py` 新規作成。GSM/ECMWFのGRIB2およびJRA-55 NetCDFから任意格子点のエマグラム・温位エマグラムを作図。`--start-ft`/`--steps`/`--interval` で複数FT連続作図、`--push` でGitHub push対応 |
| 2026-05-21 | `GRIB2_Emagram.py` バグ修正: `--push` 指定時にGitHubへ push されない問題を修正。`push_report` 内の `git diff --staged --quiet`（ステージングエリア全体を確認）を `git diff --staged --name-only -- <output_dir>`（output_dir以下のみ確認）に変更。ステージングされたファイル名を画面に出力するようにした |
