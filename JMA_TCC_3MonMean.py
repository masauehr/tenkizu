#!/usr/bin/env python
# coding: utf-8

# 気象庁 東京気候センター（TCC）3か月平均天候図 自動ダウンロードスクリプト
# 新規作成 20260915 上原政博
# 20260915 海面水温（3か月平均・平年偏差）対応追加
# 20260915 降水量平年比（季節、CLIMAT観測ベース）対応追加
#
# データソース:
#   気候システム監視 / 3-Month Mean Figures（500hPa高度・850hPa気温・流線関数・速度ポテンシャル）
#     https://ds.data.jma.go.jp/tcc/tcc/products/clisys/figures/db_hist_3mon_tcc.html
#     （画像配信元: https://www.data.jma.go.jp/cpd/db/diag/ ）
#   El Nino Monitoring / Figures of Oceanographic Condition（3か月平均海面水温）
#     https://ds.data.jma.go.jp/tcc/tcc/products/elnino/ocean/index_tcc.html
#     （画像配信元: https://www.data.jma.go.jp/cpd/data/elnino/clmrep/fig/ ）
#   World Climate / Seasonal Climate Maps（季節降水量平年比、CLIMAT地上観測ベース）
#     https://ds.data.jma.go.jp/tcc/tcc/products/climate/climfig/?tm=seasonal&el=gprt
#     （画像配信元: https://ds.data.jma.go.jp/tcc/tcc/products/climate/db_JP/monitor/seasonal/ ）
#
# 対応要素: 500hPa高度、850hPa気温、850/200hPa流線関数、850/200hPa速度ポテンシャル、
#           海面水温（実況値・平年偏差）、降水量平年比（季節）
#   （いずれも3か月平均＝中央月指定。要素ごとにデータ提供開始年月が異なる）
#
# 注意:
#   - 取得できるのはGIF画像（等値線・シェード図・観測点シンボル図）であり、格子点数値データ
#     （GRIB/NetCDF）ではない。
#   - 海面水温（sst/ssta）・降水量平年比（gprt）は kind2（hist/norm）の概念を持たず、
#     --norm 指定は無視される。
#   - 降水量平年比（gprt）は気象庁の季節区分（3-5月/6-8月/9-11月/12-2月）に基づくため、
#     中央月は 1,4,7,10月 のいずれかを指定する（他の月を指定すると404になる）。
#     また直近8シーズン（約2年分）程度しか提供されていない模様。

import os
import sys
import argparse
import requests
from pathlib import Path

# ダウンロード先ディレクトリ
DATA_DIR = "./data/tcc"

# 画像配信元ベースURL
#   clisys系（www.data.jma.go.jp/gmd/... は /cpd/... へ301リダイレクトされるため直接指定）
BASE_URL_CLISYS = "https://www.data.jma.go.jp/cpd/db/diag"
#   海面水温（El Nino Monitoring / Oceanographic Condition）
BASE_URL_SST = "https://www.data.jma.go.jp/cpd/data/elnino/clmrep/fig"
#   降水量平年比（World Climate / Seasonal Climate Maps）
BASE_URL_SEASONAL = "https://ds.data.jma.go.jp/tcc/tcc/products/climate/db_JP/monitor/seasonal"

# User-Agentヘッダー（接続リセット対策）
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TCC-3MonMean-Downloader/1.0)"}

# 対応要素定義
#   source: "clisys"（気候システム監視、kind0/kind1/kind2階層あり）
#           / "sst"（海面水温、年月直下）
#           / "seasonal"（季節降水量平年比、開始月-終了月直下）
#   kind0: extr（北半球等）/ trop（熱帯）※ source="clisys" のみ
#   kind1: psnh（北半球）/ lalogl（熱帯）※ source="clisys" のみ
#   elm:   サーバー上の要素名 ※ source="sst"/"seasonal" のみ
#   label: 説明（日本語）
ELEMENTS = {
    "z500":   {"source": "clisys", "kind0": "extr", "kind1": "psnh",   "label": "500hPa高度・平年偏差（北半球）"},
    "t850":   {"source": "clisys", "kind0": "extr", "kind1": "psnh",   "label": "850hPa気温・平年偏差（北半球）"},
    "psi850": {"source": "clisys", "kind0": "trop", "kind1": "lalogl", "label": "850hPa流線関数・平年偏差（熱帯）"},
    "psi200": {"source": "clisys", "kind0": "trop", "kind1": "lalogl", "label": "200hPa流線関数・平年偏差（熱帯）"},
    "chi850": {"source": "clisys", "kind0": "trop", "kind1": "lalogl", "label": "850hPa速度ポテンシャル・発散風（熱帯）"},
    "chi200": {"source": "clisys", "kind0": "trop", "kind1": "lalogl", "label": "200hPa速度ポテンシャル・発散風（熱帯）"},
    "sst":    {"source": "sst", "elm": "sst_sea-gl_color",  "label": "海面水温（3か月平均・実況値）"},
    "ssta":   {"source": "sst", "elm": "ssta_sea-gl_color", "label": "海面水温・平年偏差（3か月平均）"},
    "gprt":   {"source": "seasonal", "elm": "gprt", "label": "降水量平年比（季節、%、地上観測点）"},
}
ALL_ELEMENTS = list(ELEMENTS.keys())


def yyyymm_to_season_range(yyyymm: str):
    """
    中央月 YYYYMM から季節降水量ページの日付文字列（YYMMYYMM、前月-翌月）を作る。
    例: 202604（4月中央=3〜5月） -> "26032605"
    """
    y, m = int(yyyymm[:4]), int(yyyymm[4:6])
    y0, m0 = y, m - 1
    if m0 < 1:
        m0 += 12
        y0 -= 1
    y1, m1 = y, m + 1
    if m1 > 12:
        m1 -= 12
        y1 += 1
    return f"{y0 % 100:02d}{m0:02d}{y1 % 100:02d}{m1:02d}"


def build_url(elem: str, yyyymm: str, kind2: str):
    """
    要素コード・対象年月（3か月平均の中央月）・hist/normからTCC画像URLを組み立てる。

    Args:
        elem: 要素コード（ELEMENTSのキー）
        yyyymm: 対象年月 YYYYMM（3か月平均の中央月。例: 202603 は1〜3月平均）
        kind2: 'hist'（実況値＋平年偏差）または 'norm'（平年値）。source="sst"/"seasonal" では無視される。

    Returns:
        (URL, ファイル名) のタプル
    """
    info = ELEMENTS[elem]
    yy, mm = yyyymm[:4], yyyymm[4:6]

    if info["source"] == "sst":
        fn = f"{elem}_{yy}{mm}.gif"
        url = f"{BASE_URL_SST}/{yy}/{mm}/{info['elm']}.gif"
    elif info["source"] == "seasonal":
        date_str = yyyymm_to_season_range(yyyymm)
        fn = f"{elem}_{yy}{mm}.gif"
        url = f"{BASE_URL_SEASONAL}/{info['elm']}{date_str}.gif"
    else:
        fn = f"{info['kind1']}_3mon_{kind2}_{elem}_{yy}{mm}.gif"
        url = f"{BASE_URL_CLISYS}/{yy}/{info['kind0']}/{info['kind1']}/3mon/{kind2}/{elem}/{fn}"
    return url, fn


def shift_yyyymm(yyyymm: str, delta_months: int):
    """対象年月 YYYYMM を delta_months か月分ずらす。"""
    y, m = int(yyyymm[:4]), int(yyyymm[4:6])
    m += delta_months
    while m < 1:
        m += 12
        y -= 1
    while m > 12:
        m -= 12
        y += 1
    return f"{y:04d}{m:02d}"


# 降水量平年比（gprt）が存在する中央月（気象庁の季節区分: 3-5/6-8/9-11/12-2月の中央月）
SEASONAL_VALID_MONTHS = {1, 4, 7, 10}


def download_one(elem: str, yyyymm: str, kind2: str, output_dir: str, allow_fallback: bool = True):
    """
    指定要素・年月の画像を1枚ダウンロードする。
    要素によってデータ確定タイミングが異なり自動検索した年月では404になることがあるため、
    404時は1か月前へ1回だけ自動フォールバックする（allow_fallback=True の場合）。

    Returns:
        成功時: True、失敗時（404等）: False
    """
    info = ELEMENTS[elem]
    if info["source"] == "seasonal" and int(yyyymm[4:6]) not in SEASONAL_VALID_MONTHS:
        print(f"  スキップ: {info['label']} は中央月が1,4,7,10月のいずれかである必要があります "
              f"[{yyyymm}]（例: 202604 = 3〜5月平均）")
        return False

    url, fn = build_url(elem, yyyymm, kind2)
    dest = Path(output_dir) / yyyymm / fn

    if dest.exists():
        print(f"  スキップ（既存）: {fn}")
        return True

    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        if r.status_code != 200 or not r.content:
            if allow_fallback:
                prev_yyyymm = shift_yyyymm(yyyymm, -1)
                print(f"  未確定（HTTP {r.status_code}）: {ELEMENTS[elem]['label']} [{yyyymm}] "
                      f"→ 1か月前（{prev_yyyymm}）で再試行")
                return download_one(elem, prev_yyyymm, kind2, output_dir, allow_fallback=False)
            print(f"  取得失敗（HTTP {r.status_code}）: {ELEMENTS[elem]['label']} [{yyyymm}]")
            return False
        with open(dest, "wb") as f:
            f.write(r.content)
        print(f"  完了: {fn}  ({ELEMENTS[elem]['label']})")
        return True
    except requests.RequestException as e:
        print(f"  ダウンロード失敗: {e}")
        return False


def find_latest_yyyymm(kind2: str, probe_elem: str = "z500"):
    """
    現在時刻から遡り、実際にデータが存在する最新の対象年月（YYYYMM）を自動検索する。
    """
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    y, m = now.year, now.month
    for _ in range(6):  # 直近6か月分を遡って探索
        yyyymm = f"{y:04d}{m:02d}"
        url, _ = build_url(probe_elem, yyyymm, kind2)
        try:
            r = requests.head(url, headers=HEADERS, timeout=15, allow_redirects=True)
            if r.status_code == 200:
                return yyyymm
        except requests.RequestException:
            pass
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return None


def parse_args():
    parser = argparse.ArgumentParser(
        description="東京気候センター（TCC）3か月平均天候図（500hPa高度/850hPa気温/流線関数/速度ポテンシャル/海面水温/降水量平年比）をまとめてダウンロードする",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python JMA_TCC_3MonMean.py                            # 最新の対象年月を自動検索し全要素DL
  python JMA_TCC_3MonMean.py --yyyymm 202603             # 2026年1〜3月平均（中央月=202603）
  python JMA_TCC_3MonMean.py --yyyymm 202603 202606      # 複数年月まとめて指定
  python JMA_TCC_3MonMean.py --yyyymm 202603 --elements z500 t850  # 要素を絞り込み
  python JMA_TCC_3MonMean.py --yyyymm 202603 --norm      # 平年値（hist ではなく norm）を取得
  python JMA_TCC_3MonMean.py --yyyymm 202607 --elements sst ssta   # 海面水温（実況値・平年偏差）
  python JMA_TCC_3MonMean.py --yyyymm 202604 --elements gprt       # 降水量平年比（3〜5月平均）

対応要素:
  z500   500hPa高度・平年偏差（北半球）             [提供開始: 1947年9月〜]
  t850   850hPa気温・平年偏差（北半球）             [提供開始: 1947年9月〜]
  psi850 850hPa流線関数・平年偏差（熱帯）           [提供開始: 1947年9月〜]
  psi200 200hPa流線関数・平年偏差（熱帯）           [提供開始: 1947年9月〜]
  chi850 850hPa速度ポテンシャル・発散風（熱帯）     [提供開始: 1947年9月〜]
  chi200 200hPa速度ポテンシャル・発散風（熱帯）     [提供開始: 1947年9月〜]
  sst    海面水温（3か月平均・実況値）              [提供開始: 1970年2月〜]
  ssta   海面水温・平年偏差（3か月平均）            [提供開始: 1970年2月〜]
  gprt   降水量平年比（季節、%、地上観測点）        [直近8シーズン（約2年分）程度のみ]

注意:
  取得できるのはGIF画像（等値線・シェード図・観測点シンボル図）であり、
  格子点数値データ（GRIB/NetCDF）ではない。
  sst/ssta/gprt は kind2（hist/norm）の概念を持たないため、--norm 指定は無視される。
  gprt は気象庁の季節区分（3-5/6-8/9-11/12-2月）に基づくため、
  中央月は 1,4,7,10月 のいずれかを指定すること（それ以外はスキップされる）。

データ提供期間: 要素ごとに異なる（上記参照）。3か月平均の中央月で指定する。
"""
    )
    parser.add_argument("--yyyymm", type=str, nargs="+", default=None,
                        help="対象年月 YYYYMM（3か月平均の中央月）。複数指定可。省略時は最新月を自動検索")
    parser.add_argument("--elements", type=str, nargs="+", choices=ALL_ELEMENTS, default=ALL_ELEMENTS,
                        help=f"ダウンロードする要素（省略時は全て）: {', '.join(ALL_ELEMENTS)}")
    parser.add_argument("--norm", action="store_true",
                        help="平年値（norm）を取得する（省略時は実況値＋平年偏差 hist）")
    parser.add_argument("--output-dir", default=DATA_DIR, help=f"保存先ディレクトリ（デフォルト: {DATA_DIR}）")

    if any(a in sys.argv[1:] for a in ("?", "-?", "--?")):
        parser.print_help()
        sys.exit(0)

    return parser.parse_args()


def main():
    args = parse_args()
    kind2 = "norm" if args.norm else "hist"

    if args.yyyymm:
        yyyymm_list = args.yyyymm
    else:
        print("最新の対象年月を自動検索中...")
        latest = find_latest_yyyymm(kind2, probe_elem=args.elements[0])
        if latest is None:
            print("エラー: 最新データが見つかりませんでした。--yyyymm で年月を指定してください。")
            sys.exit(1)
        print(f"  見つかりました: {latest}")
        yyyymm_list = [latest]

    total, success = 0, 0
    for yyyymm in yyyymm_list:
        print(f"\n=== {yyyymm}（{kind2}）===")
        for elem in args.elements:
            total += 1
            if download_one(elem, yyyymm, kind2, args.output_dir):
                success += 1

    print(f"\n=== 全処理完了: {success}/{total} ファイル ===")
    print(f"保存先: {os.path.abspath(args.output_dir)}")


if __name__ == "__main__":
    main()
