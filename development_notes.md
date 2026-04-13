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

---

## GSM版FAX天気図3本の追加（2026-04-12）

### 追加の背景

ECMWFの同等スクリプト（`ECM_Fax57.py`, `ECM_Fax78.py`, `ECM_SurfacePressure.py`）は既存だったが、  
GSM版がなかったため、ECMWFノートブック版（`g2e_fax57_note版.py` 等）の表示要素設定と  
`GSM_tenkizu500hPa.py` のデータ取得構造を組み合わせてGSM版を新規作成した。

### 作成したスクリプト

#### GSM_fax57.py — FAX57相当（500hPa気温・700hPa湿数）

- **取得変数**: `t`（500hPa）・`t`/`r`（700hPa）
- **描画要素**:
  - 700hPa T-Tdシェード（0/3/6/18K区切り、緑/灰/白/黄）+ 等値線（灰色3K間隔）
  - 500hPa等温度線（青、3℃間隔・太線15℃間隔）
  - -30℃線（紫）
  - W/Cスタンプ（500hPa気温の極大/極小）

#### GSM_fax78.py — FAX78相当（850hPa気温・風・700hPa発散）

- **取得変数**: `u`/`v`/`t`（850hPa）・`u`/`v`（700hPa）
- **発散の算出**: GSM Rglに`d`変数がないため、700hPa u/vから `mpcalc.divergence()` で計算
  - スムージング: 9点平滑化 16回繰り返し（ECM版と同一）
- **描画要素**:
  - 700hPa収束・発散シェード（赤/橙/灰/白/黄/水色、×10⁻⁵s⁻¹）
  - 850hPa等温度線（青、3℃・太線15℃間隔）
  - 850hPa風矢羽
  - W/Cスタンプ（850hPa気温の極大/極小）
- **引数**: `--level-div`（発散面、デフォルト700hPa）・`--level-t`（気温・風面、デフォルト850hPa）

#### GSM_faxSrfPre.py — 地上気圧・風・2m気温

- **取得変数**: `prmsl`（meanSea）・`10u`/`10v`・`2t`
- **描画要素**:
  - 等圧線（黒細線4hPa間隔・太線20hPa間隔＋ラベル）
  - 2m等温度線（緑、3℃間隔）
  - 10m風矢羽
  - H/Lスタンプ（気圧値付き）

### GSM Rglファイルの収録変数調査結果

実データ（2026-04-12 00UTC）で確認した結果:

| 収録あり | 収録なし |
|---------|---------|
| 気圧面: `gh`,`t`,`u`,`v`,`w`,`r`（10〜1000hPa 17レベル） | 可降水量（`tcwv`/`pwat`） |
| 地表: `prmsl`(meanSea), `sp`(surface) | 積算降水量（`tp`） |
| 高度: `10u`,`10v`(10m), `2t`,`2r`(2m) | |
| 雲量: `hcc`,`lcc`,`mcc` | |

→ `GSM_faxSrfPre.py` では `--tcwv`/`--tp` オプションを廃止（ECM版との差異）。

### run_all_charts.sh への追加とkeyモード実装（2026-04-12）

**追加内容:**
- 新規3スクリプトをGSM系として追加（計8本→合計12本）
- `N_STEPS` 引数に `key` を指定できる**keyモード**を追加

**keyモードの動作:**

| N_STEPS指定 | 生成するFT |
|------------|-----------|
| 数値（例: `5`） | 開始FTから6h間隔でN枚 |
| `key` | FT=0,12,24,36,48h の固定5枚 |

```bash
bash run_all_charts.sh 2026041200 0000 key   # FT=0,12,24,36,48h 全スクリプト実行
```

keyモード実装方法: bash内で `KEY_FTS_DDHH=(0000 0012 0100 0112 0200)` の配列をループし、  
各FTについて `n_steps=1` で個別スクリプトを呼び出す方式。

---

## GSM/ECM自動データ取得＆一括生成スクリプトの追加（2026-04-12）

### 背景

`run_all_charts.sh` では init_time を手動指定する必要があった。  
最新データを自動で検索・取得・描画まで一括実行できるPythonスクリプトを追加した。

### run_gsm_auto.py

**機能**: RISHサーバーを検索して最新のGSM init_timeを自動特定し、全8本のGSMスクリプトを実行。

**init_time 自動検索ロジック**:
- 現在UTC時刻から最大4日分遡って確認
- 各日の12UTC・00UTC を優先度順に試行
- 初期時刻から3時間以内はデータ未公開として除外
- RISHサーバーのディレクトリHTMLを `BeautifulSoup` でパースし `FD0000` ファイルの存在を確認

**実行スクリプト一覧**:
```python
GSM_SCRIPTS = [
    "GSM_tenkizu500hPa.py", "GSM_QVector850hPa.py", "GSM_Jet300hPa.py",
    "GSM_Instability.py",   "GSM_CrossSection.py",  "GSM_fax57.py",
    "GSM_fax78.py",         "GSM_faxSrfPre.py",     "GSM_EPT850hPa.py",
]
```

**引数**: `--init-time`（手動指定）, `--steps`（連続枚数）, `--start-ft`（開始DDHH）

### run_ecm_auto.py

**機能**: ECMWF Open Dataサーバーを検索して最新のECM init_timeを自動特定し、全5本のECMスクリプトを実行。

**init_time 自動検索ロジック**:
- 現在UTC時刻から最大6日分遡って確認（ECMは5日分公開）
- 各日の12UTC・00UTC を優先度順に試行
- 初期時刻から4時間以内はデータ未公開として除外（ECMはGSMより公開が遅い）
- `requests.head()` で `FD=0h` ファイルの HTTP 200 を確認

**実行スクリプト一覧**:
```python
ECM_SCRIPTS = [
    "ECM_tenkizu500hPa.py", "ECM_EPT850hPa.py", "ECM_Fax57.py",
    "ECM_Fax78.py",         "ECM_SurfacePressure.py",
]
```

**引数**: `--init-time`, `--steps`, `--start-ft`, `--tcwv`, `--tp`  
`--tcwv`/`--tp` は `ECM_SurfacePressure.py` にのみ渡す。`--tp` は FT=0 を自動スキップ。

### 設計上の判断

- **FT形式の差異**: GSMはDDHH形式（例: `0100`=24h）、ECMは時間数（例: `24`）。  
  keyモードのFTリストも形式に合わせて別定義 (`KEY_FTS_DDHH = [0, 12, 100, 112, 200]` / `KEY_FTS_H = [0, 12, 24, 36, 48]`)。
- **subprocess.run() の引数**: 各描画スクリプトへ `[sys.executable, script, init_time, ft, "1"]` の形で渡す。  
  n_steps=1 固定でFTをループし、エラー時は次のFTに継続する。
- **作業ディレクトリ**: `os.chdir(Path(__file__).parent.resolve())` でスクリプトのあるディレクトリに移動してから実行。

---

## GSM 850hPa相当温位・ECM 500hPa渦度追加 / ファイル名衝突解消 / PPTX自動生成（2026-04-13）

### 1. ファイル名衝突問題の発見と解消

`run_all_charts.sh` は GSM → ECM の順でスクリプトを実行するが、  
同名の出力ファイルが `output/` に存在すると ECM が GSM を上書きしていた。

**衝突していたファイル名:**

| スクリプト | 修正前 | 修正後 |
|-----------|--------|--------|
| `GSM_fax57.py` | `*_Fax57.png` | `*_GSM_Fax57.png` |
| `GSM_fax78.py` | `*_Fax78.png` | `*_GSM_Fax78.png` |
| `GSM_faxSrfPre.py` | `*_SurfacePressure.png` | `*_GSM_SurfacePressure.png` |
| `ECM_EPT850hPa.py` | `*_850hPa_EPT.png` | `*_ECM_850hPa_EPT.png` |
| `ECM_Fax57.py` | `*_Fax57.png` | `*_ECM_Fax57.png` |
| `ECM_Fax78.py` | `*_Fax78.png` | `*_ECM_Fax78.png` |
| `ECM_SurfacePressure.py` | `*_SurfacePressure.png` | `*_ECM_SurfacePressure.png` |

### 2. 新規スクリプト作成

#### GSM_EPT850hPa.py

- `ECM_EPT850hPa.py` をベースに、データ取得を `ensure_file()` + RISHサーバーに変更
- 読み込み変数: `u`, `v`, `t`, `r`（850hPa）
- MetPy で露点温度 → 相当温位を計算
- 出力: `*_GSM_850hPa_EPT.png`

#### ECM_tenkizu500hPa.py

- `GSM_tenkizu500hPa.py` をベースに、データ取得を `ensure_file_ecm()` + ECMWF Open Dataに変更
- 読み込み変数: `gh`（500hPa）、`u`/`v` → MetPy で渦度計算
- 出力: `*_ECM_500hPa_Height_VORT.png`

### 3. run_all_charts.sh の更新

新スクリプト2本を追加し、計14スクリプト構成に変更:
- GSM系 9本: 既存8本 + `GSM_EPT850hPa.py`
- ECM系 5本: 既存4本 + `ECM_tenkizu500hPa.py`

### 4. PNG → PowerPoint 自動生成スクリプト

#### make_pptx.py

`output/` 内の PNG を PowerPoint スライドに自動貼り付け。  
Pillow でピクセルサイズを取得してアスペクト比を保持、セル内中央配置。

| スライドグループ | モード | 内容 |
|--------------|------|------|
| GSM: 500hPa渦度/地上気圧 | 2×2 | 2FT × 2種類 = 4画像/スライド |
| GSM: Fax57/Fax78 | 2×2 | 同上 |
| GSM: 300hPaジェット/Qベクター | 2×2 | 同上 |
| GSM: 850hPa相当温位 | 4in1 | FT=12,24,36,48h を2×2配置 |
| ECM: 500hPa渦度/地上気圧 | 2×2 | 同上 |
| ECM: Fax57/Fax78 | 2×2 | 同上 |
| ECM: 850hPa相当温位 | 4in1 | FT=12,24,36,48h を2×2配置 |

スライドサイズ: 4:3 標準（10×7.5インチ）

#### make_pptx2.py

残り画像種別の補完スクリプト。

| スライドグループ | モード | 内容 |
|--------------|------|------|
| 300hPaジェット/Fax57 | 2×2 | 同上 |
| 大気不安定域/850hPa相当温位 | 2×2 | 同上 |
| 鉛直断面図 | 1×2 | 縦長画像を1行2列（全高使用） |

#### スライドモードの設計

- `"2x2"`: 1スライドに 2FT × 上下2種類 = 4セル
- `"4in1"`: ft_filter=[12,24,36,48] の固定4枚を同一スライドに2×2配置
- `"1x2"`: 1行2列（鉛直断面図などの縦長画像向け）

### 5. samples/ ディレクトリ

全出力種別のサンプル画像（PNG 14枚 + PowerPoint 1ファイル）を `samples/` に配置し GitHub にアップロード。  
いずれも 2026-04-12 12UTC 初期値 FT=0h（相当温位のみ FT=12h）を使用。

| ファイル | 内容 |
|---------|------|
| `sample_500hPa_Height_VORT.png` | GSM 500hPa等高度線・渦度 |
| `sample_850hPa_QVec.png` | GSM 850hPa Qベクター |
| `sample_300hPa_Jet.png` | GSM 300hPa ジェット |
| `sample_Instability.png` | GSM 不安定域分布 |
| `sample_CrossSection.png` | GSM 鉛直断面図 |
| `sample_GSM_Fax57.png` | GSM FAX57相当 |
| `sample_GSM_Fax78.png` | GSM FAX78相当 |
| `sample_GSM_SurfacePressure.png` | GSM 地上気圧 |
| `sample_GSM_850hPa_EPT.png` | GSM 850hPa相当温位 |
| `sample_ECM_500hPa_Height_VORT.png` | ECMWF 500hPa等高度線・渦度 |
| `sample_ECM_850hPa_EPT.png` | ECMWF 850hPa相当温位 |
| `sample_ECM_Fax57.png` | ECMWF FAX57相当 |
| `sample_ECM_Fax78.png` | ECMWF FAX78相当 |
| `sample_ECM_SurfacePressure.png` | ECMWF 地上気圧 |
| `sample_tenkizu_2026041212.pptx` | PowerPoint サンプル（make_pptx.py 生成、17スライド） |

`make_pptx.py` は PPTX 生成時に `output/` 内の PNG を参照するため、  
`samples/` の PPTX は参照先として `output/` が必要（生成済みファイルとして配置）。
