# tenkizu — TODO

## 次の目標: GSM版 ECM相当天気図の作成

ECM系スクリプト（`ECM_*.py`）を参照し、同じ描画内容をGSMデータで行うスクリプトを作成する。  
データ取得は既存の `ensure_file()` + RISHサーバーDL パターンを流用。  
引数仕様・`plot_one()`/`main()` 構造は既存GSMスクリプトと統一する。

---

### 作成予定スクリプト

| 優先 | 作成ファイル | 参照ECMスクリプト | 描画内容 |
|------|------------|-----------------|---------|
| 1 | `GSM_EPT850hPa.py` | `ECM_EPT850hPa.py` | 850hPa 相当温位シェード・等値線・風矢羽 |
| 2 | `GSM_Fax57.py` | `ECM_Fax57.py` | 500hPa 気温等値線（W/Cスタンプ）＋ 700hPa T-Td シェード |
| 3 | `GSM_Fax78.py` | `ECM_Fax78.py` | 700hPa 収束・発散シェード＋ 850hPa 気温等値線・風矢羽（W/Cスタンプ） |
| 4 | `GSM_SurfacePressure.py` | `ECM_SurfacePressure.py` | MSL等圧線・10m風矢羽・2m気温（H/Lスタンプ＋気圧値） |

---

### 各スクリプトの実装メモ

#### `GSM_EPT850hPa.py`
- ECMと同じ構造で、データ取得を `ensure_file()` (RISH) に変更
- GSMファイルから `gh`, `u`, `v`, `t`, `r` (850hPa) を読み込む
- 相当温位の計算: `mpcalc.equivalent_potential_temperature()` を使用
- `ECM_EPT850hPa.py` との差分はデータ取得部分のみの見込み

#### `GSM_Fax57.py`
- `ECM_Fax57.py` を参照
- 500hPa: 気温（`t`）→ W/Cスタンプ（`detect_peaks`）
- 700hPa: 気温（`t`）・相対湿度（`r`）→ `mpcalc.dewpoint_from_relative_humidity()` で T-Td を計算
- 2つの気圧面のデータを1ファイルから同時に読み込む

#### `GSM_Fax78.py`
- `ECM_Fax78.py` を参照
- 700hPa: 発散（`d`）→ スムージング → 収束・発散シェード
  - GSMファイルに発散（shortName=`d`）が含まれるか要確認
  - 含まれない場合は `u`, `v` から `mpcalc.divergence()` で計算
- 850hPa: 気温（`t`）・U/V 風 → 等温度線・風矢羽・W/Cスタンプ

#### `GSM_SurfacePressure.py`
- `ECM_SurfacePressure.py` を参照
- GSMファイルから読み込む変数:
  - MSL気圧: `prmsl`（typeOfLevel=`meanSea`）または `msl`
  - 10m U/V 風: `10u`, `10v`（typeOfLevel=`heightAboveGround`, level=10）
  - 2m 気温: `2t`（typeOfLevel=`heightAboveGround`, level=2）
  - ※ GSMにTCWV/TPが含まれるか要確認
- ショートネームがECMと異なる可能性があるため `pygrib` でキー確認が必要

---

### 完了後の作業

- [ ] `run_all_charts.sh` に4本を追加（GSM系の末尾）
- [ ] `pc_docs/manuals/automation/tenkizu.md` を更新
- [ ] GitHub に push

---

## 完了済み

- [x] `GSM_tenkizu500hPa.py` — 500hPa 高度・渦度・H/L スタンプ（2026-04-09）
- [x] `GSM_QVector850hPa.py` — 850hPa Q ベクター発散・気温・高度（2026-04-09）
- [x] `GSM_Jet300hPa.py` — 300hPa ジェット・非地衡風・発散（2026-04-09）
- [x] `GSM_Instability.py` — 不安定域分布（SEPT−maxEPT・上層気温）（2026-04-09）
- [x] `GSM_CrossSection.py` — 鉛直断面図（2026-04-09）
- [x] `ECM_EPT850hPa.py` — ECMWF 850hPa 相当温位・風（2026-04-09）
- [x] `ECM_Fax57.py` — ECMWF FAX57 500hPa気温・700hPa湿数（2026-04-09）
- [x] `ECM_Fax78.py` — ECMWF FAX78 700hPa収束・発散・850hPa気温・風（2026-04-09）
- [x] `ECM_SurfacePressure.py` — ECMWF 地上気圧・風・2m気温（2026-04-09）
- [x] `run_all_charts.sh` — 全スクリプト一括実行（2026-04-09）
- [x] 全スクリプトの引数省略対応（start_ft・n_steps デフォルト化）（2026-04-09）
- [x] 一括スクリプトの引数順を個別スクリプトと統一（2026-04-09）
