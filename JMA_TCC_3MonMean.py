#!/usr/bin/env python
# coding: utf-8

# 気象庁 東京気候センター（TCC）3か月平均天候図 自動ダウンロードスクリプト
# 新規作成 20260915 上原政博
# 20260915 海面水温（3か月平均・平年偏差）対応追加
# 20260915 降水量平年比（季節、CLIMAT観測ベース）対応追加
# 20260915 Markdownレポート生成・GitHub push（--push）対応追加
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
#   （要素ごとにデータ提供開始年月が異なる）
#
# 重要: --yyyymm の意味は要素グループによって異なる（実画像のキャプションで実測確認済み）。
#   - z500/t850/psi*/chi*（気候システム監視系）: yyyymm は3か月の「終了月」
#       例: 202603 を指定 → 実際は Jan.2026-Mar.2026（1〜3月）の平均
#   - sst/ssta・gprt（海面水温・降水量平年比）: yyyymm は3か月の「中央月」
#       例: 202607 を指定 → 実際は Jun.2026-Aug.2026（6〜8月）の平均
#   このズレはTCCサイト側の仕様であり本スクリプトの不具合ではない。build_report() が
#   要素ごとに正しい期間を計算して画像に注記する。
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
import shutil
import argparse
import subprocess
import requests
from pathlib import Path

# ダウンロード先ディレクトリ
DATA_DIR = "./data/tcc"
# レポート（Markdown+画像）出力先ディレクトリ。GitHub push対象はこちらのみ。
REPORTS_DIR = "./reports"

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
#   date_mode: yyyymm の意味。"end"=3か月の終了月 / "center"=3か月の中央月（実測確認済み）
#   label: 説明（日本語）
ELEMENTS = {
    "z500":   {"source": "clisys", "kind0": "extr", "kind1": "psnh",   "date_mode": "end", "label": "500hPa高度・平年偏差（北半球）"},
    "t850":   {"source": "clisys", "kind0": "extr", "kind1": "psnh",   "date_mode": "end", "label": "850hPa気温・平年偏差（北半球）"},
    "psi850": {"source": "clisys", "kind0": "trop", "kind1": "lalogl", "date_mode": "end", "label": "850hPa流線関数・平年偏差（熱帯）"},
    "psi200": {"source": "clisys", "kind0": "trop", "kind1": "lalogl", "date_mode": "end", "label": "200hPa流線関数・平年偏差（熱帯）"},
    "chi850": {"source": "clisys", "kind0": "trop", "kind1": "lalogl", "date_mode": "end", "label": "850hPa速度ポテンシャル・発散風（熱帯）"},
    "chi200": {"source": "clisys", "kind0": "trop", "kind1": "lalogl", "date_mode": "end", "label": "200hPa速度ポテンシャル・発散風（熱帯）"},
    "sst":    {"source": "sst", "elm": "sst_sea-gl_color",  "date_mode": "center", "label": "海面水温（3か月平均・実況値）"},
    "ssta":   {"source": "sst", "elm": "ssta_sea-gl_color", "date_mode": "center", "label": "海面水温・平年偏差（3か月平均）"},
    "gprt":   {"source": "seasonal", "elm": "gprt", "date_mode": "center", "label": "降水量平年比（季節、%、地上観測点）"},
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
    要素コード・対象年月・hist/normからTCC画像URLを組み立てる。

    Args:
        elem: 要素コード（ELEMENTSのキー）
        yyyymm: 対象年月 YYYYMM。意味は要素の date_mode で異なる
            （"end"=3か月の終了月、例: 202603 は1〜3月平均。"center"=3か月の中央月）
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
        成功時: (保存先Path, 実際に取得できた年月YYYYMM) のタプル
        失敗時（404等）: None
    """
    info = ELEMENTS[elem]
    if info["source"] == "seasonal" and int(yyyymm[4:6]) not in SEASONAL_VALID_MONTHS:
        print(f"  スキップ: {info['label']} は中央月が1,4,7,10月のいずれかである必要があります "
              f"[{yyyymm}]（例: 202604 = 3〜5月平均）")
        return None

    url, fn = build_url(elem, yyyymm, kind2)
    dest = Path(output_dir) / yyyymm / fn

    if dest.exists():
        print(f"  スキップ（既存）: {fn}")
        return dest, yyyymm

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
            return None
        with open(dest, "wb") as f:
            f.write(r.content)
        print(f"  完了: {fn}  ({ELEMENTS[elem]['label']})")
        return dest, yyyymm
    except requests.RequestException as e:
        print(f"  ダウンロード失敗: {e}")
        return None


def season_label(yyyymm: str, date_mode: str = "center"):
    """
    YYYYMM から '2026年6〜8月' 形式の実際の3か月期間ラベルを作る。
    date_mode="center": yyyymmは中央月（前後1か月を加える）。
    date_mode="end":    yyyymmは終了月（2か月前から加える）。
    """
    y, m = int(yyyymm[:4]), int(yyyymm[4:6])
    if date_mode == "end":
        y1, m1 = y, m
        m0 = m - 2
        y0 = y
        while m0 < 1:
            m0 += 12
            y0 -= 1
    else:
        y0, m0 = (y, m - 1) if m > 1 else (y - 1, 12)
        y1, m1 = (y, m + 1) if m < 12 else (y + 1, 1)
    if y0 == y1:
        return f"{y0}年{m0}〜{m1}月"
    return f"{y0}年{m0}月〜{y1}年{m1}月"


# レポート内で要素をグルーピングするための表示順・見出し
ELEMENT_GROUPS = [
    ("気候システム監視（500hPa高度・850hPa気温・流線関数・速度ポテンシャル）",
     ["z500", "t850", "psi850", "psi200", "chi850", "chi200"]),
    ("海面水温", ["sst", "ssta"]),
    ("降水量平年比", ["gprt"]),
]

SOURCE_LINKS = [
    "[気候システム監視 / 3-Month Mean Figures]"
    "(https://ds.data.jma.go.jp/tcc/tcc/products/clisys/figures/db_hist_3mon_tcc.html)",
    "[El Nino Monitoring / Oceanographic Condition]"
    "(https://ds.data.jma.go.jp/tcc/tcc/products/elnino/ocean/index_tcc.html)",
    "[World Climate / Seasonal Climate Maps]"
    "(https://ds.data.jma.go.jp/tcc/tcc/products/climate/climfig/?tm=seasonal&el=gprt)",
]


def run_git(cmd: str, cwd: Path):
    print(f"$ git {cmd}")
    result = subprocess.run(f"git {cmd}", shell=True, cwd=cwd, capture_output=True, text=True)
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip())
    return result.returncode


def build_report(yyyymm: str, kind2: str, results: dict, push: bool):
    """
    1年月分のダウンロード結果からMarkdownレポートを生成し、reports/tcc_{yyyymm}/ に
    画像とともに配置する。--push 指定時は git add/commit/push まで行う。

    Args:
        yyyymm: 要求した基準年月（意味は要素ごとに異なる。season_label参照）
        kind2: 'hist' または 'norm'
        results: {要素コード: (画像Path, 実際に取得できた年月)} の辞書（成功分のみ）
        push: True なら GitHub へ push する
    """
    report_dir = Path(REPORTS_DIR) / f"tcc_{yyyymm}"
    report_dir.mkdir(parents=True, exist_ok=True)

    lines = [
        "# TCC 3か月平均天候図レポート",
        "",
        f"**基準年月**: {yyyymm}",
        f"**種別**: {'平年値（norm）' if kind2 == 'norm' else '実況値＋平年偏差（hist）'}"
        "　※ 海面水温・降水量平年比はこの区別を持たず常に同一画像",
        "",
        "気象庁 東京気候センター（TCC）が公開する季節予報の基本場資料。",
        "※ 実際の3か月期間は要素グループによって基準年月の意味が異なる"
        "（気候システム監視系＝終了月／海面水温・降水量平年比＝中央月）ため、"
        "各画像の見出しに実期間を明記している。",
        "",
        "---",
        "",
    ]

    for group_title, elems in ELEMENT_GROUPS:
        avail = [e for e in elems if e in results]
        if not avail:
            continue
        lines += [f"## {group_title}", ""]
        for elem in avail:
            src, actual_yyyymm = results[elem]
            img_name = src.name
            shutil.copy2(src, report_dir / img_name)
            label = ELEMENTS[elem]["label"]
            date_mode = ELEMENTS[elem]["date_mode"]
            period = season_label(actual_yyyymm, date_mode)
            note = "" if actual_yyyymm == yyyymm else f"（データ確定の都合により{actual_yyyymm}基準で代替）"
            lines += [f"### {label}{note}", "", f"**対象期間**: {period}", "",
                      f"![{label}](./{img_name})", ""]

    lines += ["---", "", "## 出典", ""] + [f"- {link}" for link in SOURCE_LINKS]

    md_name = "tcc_3monmean_report.md"
    md_path = report_dir / md_name
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nMDファイル生成: reports/tcc_{yyyymm}/{md_name}")

    if not push:
        print("GitHub push はスキップ（--push を付けると実行）")
        return

    print("\n--- GitHub へアップロード ---")
    script_dir = Path(__file__).parent.resolve()
    rel_path = f"reports/tcc_{yyyymm}"

    rc = run_git(f"add {rel_path}", script_dir)
    if rc != 0:
        print("エラー: git add 失敗")
        return

    staged = subprocess.run("git diff --staged --quiet", shell=True, cwd=script_dir)
    if staged.returncode == 0:
        print("変更なし: 既にアップロード済みです（コミット・プッシュをスキップ）")
        return

    commit_msg = f"report: TCC3か月平均天候図レポート追加 ({yyyymm})"
    rc = run_git(f'commit -m "{commit_msg}"', script_dir)
    if rc != 0:
        print("エラー: git commit 失敗")
        return

    rc = run_git("push", script_dir)
    if rc != 0:
        print("push 失敗。30秒待ってリトライします...")
        import time
        time.sleep(30)
        rc = run_git("push", script_dir)
    if rc != 0:
        print("エラー: git push 失敗（手動で 'git push' を実行してください）")


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
  python JMA_TCC_3MonMean.py --yyyymm 202603             # z500等は終了月扱い→2026年1〜3月平均
  python JMA_TCC_3MonMean.py --yyyymm 202603 202606      # 複数年月まとめて指定
  python JMA_TCC_3MonMean.py --yyyymm 202603 --elements z500 t850  # 要素を絞り込み
  python JMA_TCC_3MonMean.py --yyyymm 202603 --norm      # 平年値（hist ではなく norm）を取得
  python JMA_TCC_3MonMean.py --yyyymm 202607 --elements sst ssta   # sstは中央月扱い→6〜8月平均
  python JMA_TCC_3MonMean.py --yyyymm 202604 --elements gprt       # gprtも中央月扱い→3〜5月平均
  python JMA_TCC_3MonMean.py --yyyymm 202603 --push      # reports/ にMDレポート生成しGitHub push

重要: --yyyymm の意味は要素グループで異なる（実画像で実測確認済み。詳細はレポートの各画像見出しに明記）。
  z500/t850/psi*/chi* : yyyymm を3か月の「終了月」として扱う（202603 → 1〜3月）
  sst/ssta/gprt        : yyyymm を3か月の「中央月」として扱う（202607 → 6〜8月）

対応要素:
  z500   500hPa高度・平年偏差（北半球）             [終了月指定] [提供開始: 1947年9月〜]
  t850   850hPa気温・平年偏差（北半球）             [終了月指定] [提供開始: 1947年9月〜]
  psi850 850hPa流線関数・平年偏差（熱帯）           [終了月指定] [提供開始: 1947年9月〜]
  psi200 200hPa流線関数・平年偏差（熱帯）           [終了月指定] [提供開始: 1947年9月〜]
  chi850 850hPa速度ポテンシャル・発散風（熱帯）     [終了月指定] [提供開始: 1947年9月〜]
  chi200 200hPa速度ポテンシャル・発散風（熱帯）     [終了月指定] [提供開始: 1947年9月〜]
  sst    海面水温（3か月平均・実況値）              [中央月指定] [提供開始: 1970年2月〜]
  ssta   海面水温・平年偏差（3か月平均）            [中央月指定] [提供開始: 1970年2月〜]
  gprt   降水量平年比（季節、%、地上観測点）        [中央月指定] [直近8シーズン（約2年分）程度のみ]

注意:
  取得できるのはGIF画像（等値線・シェード図・観測点シンボル図）であり、
  格子点数値データ（GRIB/NetCDF）ではない。
  sst/ssta/gprt は kind2（hist/norm）の概念を持たないため、--norm 指定は無視される。
  gprt は気象庁の季節区分（3-5/6-8/9-11/12-2月）に基づくため、
  中央月は 1,4,7,10月 のいずれかを指定すること（それ以外はスキップされる）。

データ提供期間: 要素ごとに異なる（上記参照）。

レポート出力:
  ダウンロードに1件でも成功すると、年月ごとに reports/tcc_{yyyymm}/tcc_3monmean_report.md
  （画像埋め込み済みMarkdown）を自動生成する（--no-report で無効化可）。
  --push を付けると reports/tcc_{yyyymm}/ のみを git add/commit/push してGitHubに公開する。
"""
    )
    parser.add_argument("--yyyymm", type=str, nargs="+", default=None,
                        help="対象年月 YYYYMM。意味は要素グループで異なる"
                             "（z500等=終了月／sst・gprt=中央月、詳細はヘルプ本文参照）。"
                             "複数指定可。省略時は最新月を自動検索")
    parser.add_argument("--elements", type=str, nargs="+", choices=ALL_ELEMENTS, default=ALL_ELEMENTS,
                        help=f"ダウンロードする要素（省略時は全て）: {', '.join(ALL_ELEMENTS)}")
    parser.add_argument("--norm", action="store_true",
                        help="平年値（norm）を取得する（省略時は実況値＋平年偏差 hist）")
    parser.add_argument("--output-dir", default=DATA_DIR, help=f"保存先ディレクトリ（デフォルト: {DATA_DIR}）")
    parser.add_argument("--push", action="store_true",
                        help="生成したレポート（reports/tcc_{yyyymm}/）をGitHubへ git push する（省略時はローカル保存のみ）")
    parser.add_argument("--no-report", action="store_true",
                        help="Markdownレポートを生成しない（data/tcc/ へのダウンロードのみ行う）")

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
        results = {}
        for elem in args.elements:
            total += 1
            result = download_one(elem, yyyymm, kind2, args.output_dir)
            if result:
                success += 1
                results[elem] = result

        if results and not args.no_report:
            build_report(yyyymm, kind2, results, args.push)

    print(f"\n=== 全処理完了: {success}/{total} ファイル ===")
    print(f"保存先: {os.path.abspath(args.output_dir)}")


if __name__ == "__main__":
    main()
