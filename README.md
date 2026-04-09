# tenkizu — GSM 500hPa天気図作成ツール

黒良さんのNote（https://note.com/rkurora/n/n200fdd8f1aa1 ）をベースに、  
GSM（全球スペクトルモデル）GRIB2データから500hPa天気図を作成するツールです。

---

## 概要

- **データソース**: 気象庁 GSM GPV（全球モデル）
- **データ提供元**: 京都大学生存圏研究所 (RISH) データベース  
  `http://database.rish.kyoto-u.ac.jp/arch/jmadata/data/gpv/original/`
- **描画内容**: 500hPa 等高度線・相対渦度（ハッチング付き）
- **図法**: ステレオ投影（中心: 60°N, 140°E）
- **描画領域**: 108〜156°E, 17〜55°N（極東）

---

## ディレクトリ構成

```
tenkizu/
├── kurora_tenkizu.py    # 天気図描画スクリプト（メイン）
├── download_gsm.py      # GSM GRIB2データ ダウンロードスクリプト
├── run_pipeline.sh      # ダウンロード→描画 パイプラインスクリプト
├── README.md            # このファイル
├── CLAUDE.md            # Claude Code用ドキュメント
├── .gitignore           # Git除外設定
├── data_gsm/            # GSM GRIB2データ格納先（Gitから除外）
└── output/              # 生成天気図PNG出力先（Gitから除外）
```

---

## セットアップ

### 必要ライブラリ

`met_env_310`（Python 3.10のConda環境）に以下を導入:

```bash
conda create -n met_env_310 python=3.10
conda activate met_env_310
conda install -c conda-forge pygrib xarray metpy matplotlib cartopy requests
pip install beautifulsoup4
```

| ライブラリ      | 用途                         |
|---------------|------------------------------|
| `pygrib`      | GRIB2ファイル読み込み・データ抽出 |
| `xarray`      | データセット管理               |
| `metpy`       | 気象計算（相対渦度等）          |
| `matplotlib`  | 図表描画                      |
| `cartopy`     | 地図投影・海岸線               |
| `requests`    | HTTPダウンロード               |
| `beautifulsoup4` | HTMLパース（ファイルリスト取得）|

---

## 使い方

### データダウンロード

```bash
conda activate met_env_310

# 最新データを自動検索してダウンロード
python download_gsm.py

# 日付を指定してダウンロード（00UTC・12UTC両方）
python download_gsm.py --date 20171210

# 日付と初期時刻を指定
python download_gsm.py --date 20171210 --hour 12

# 期間指定
python download_gsm.py --start 20171208 --end 20171210

# FT（予報時間）を絞ってダウンロード
python download_gsm.py --date 20171210 --ft 0000 0012 0100
```

### 天気図描画

```bash
# 2017/12/10 12UTC 初期値（FT=0h）
python kurora_tenkizu.py 2017121012

# 18時間後の予報（FT=18h）
python kurora_tenkizu.py 2017121012 0018

# 1日後の予報（FT=24h）
python kurora_tenkizu.py 2017121012 0100

# 3日後12時間後の予報（FT=84h）
python kurora_tenkizu.py 2017121012 0312
```

**引数:**

| 引数 | 説明 | 例 |
|------|------|----|
| `init_time` | 初期時刻 YYYYMMDDHH (UTC) | `2017121012` |
| `forecast_time` | 予報時間 DDHH形式（省略可、デフォルト: `0000`）| `0018`, `0100` |
| `level` | 気圧面 hPa（省略可、デフォルト: `500`）| `500`, `300` |

**FD形式（予報時間）の見方:**

| FD値 | 予報時間 |
|------|---------|
| `0000` | FT=0h（初期値） |
| `0006` | FT=6h |
| `0018` | FT=18h |
| `0100` | FT=24h（1日後） |
| `0112` | FT=36h |
| `0200` | FT=48h（2日後） |
| `0300` | FT=72h（3日後） |

### パイプライン実行

```bash
# ダウンロードから描画まで一括実行
bash run_pipeline.sh

# 日付を指定して一括実行
bash run_pipeline.sh --date 20171210 --hour 12
```

---

## 描画内容の仕様

| 要素 | 表現 | 設定値 |
|------|------|--------|
| 等高度線（実線） | 黒細線 | 60m間隔（4800〜6000m） |
| 等高度線（太線） | 黒太線 | 300m間隔 |
| 5820gpm線 | 茶色一点鎖線 | 固定 |
| 5400gpm線 | 青色一点鎖線 | 固定 |
| 相対渦度（灰色） | 塗りつぶし | 0以上（透過率30%） |
| 相対渦度（赤） | 塗りつぶし | 8×10⁻⁵以上 |
| 相対渦度（等値線） | 黒実線 | 4×10⁻⁵間隔 |
| 海岸線 | 黒線 | 50m分解能 |
| グリッド線 | グレー | 10°間隔 |

---

## 出力ファイル

```
output/{YYYYMMDDHH}_FT{FFF}h_{LLL}hPa_Height_VORT.png
```

例: `output/2017121012_FT000h_500hPa_Height_VORT.png`

- DPI: 150
- サイズ: 10×8インチ
- tight_bbox

---

## 参考

- 黒良さんのNote: https://note.com/rkurora/n/n200fdd8f1aa1
- 気象業務支援センター サンプルデータ: https://www.jmbsc.or.jp/jp/online/c-onlineGsample.html#sample413
- RISHデータベース: http://database.rish.kyoto-u.ac.jp/arch/jmadata/
