#!/usr/bin/env python
# coding: utf-8

# ジェット・前線解析 複数初期時刻比較レポート生成スクリプト
# ave_report と wide_report の結果を横に並べて比較するMDファイルを生成
#
# 使用例:
#   python jet_front_compare_report.py 2026050600 2026050512           # AVE+WIDE 2初期時刻比較
#   python jet_front_compare_report.py 2026050600 2026050512 2026050500 # 3初期時刻比較
#   python jet_front_compare_report.py 2026050600 2026050512 --ave-only  # AVEのみ比較
#   python jet_front_compare_report.py 2026050600 2026050512 --wide-only # WIDEのみ比較
#
# 作成: 20260610 上原政博

import os
import sys
import subprocess
import shutil
import argparse
from pathlib import Path
from datetime import datetime
import re


_SCRIPT_DIR = Path(__file__).parent


def parse_args():
    parser = argparse.ArgumentParser(
        description="複数初期時刻の ave/wide レポートを比較",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python jet_front_compare_report.py 2026050600 2026050512
  python jet_front_compare_report.py 2026050600 2026050512 2026050500
  python jet_front_compare_report.py 2026050600 2026050512 --ave-only
  python jet_front_compare_report.py 2026050600 2026050512 --levels 100 200
  python jet_front_compare_report.py 2026050600 2026050512 --ecm --push
        """)
    parser.add_argument("init_times", nargs="+", help="初期時刻（YYYYMMDDHH）2～3個")
    parser.add_argument("--ave-only", action="store_true", help="AVEレポートのみ")
    parser.add_argument("--wide-only", action="store_true", help="WIDEレポートのみ")
    parser.add_argument("--levels", nargs="+", type=int, default=[50, 100, 200],
                        help="上層気圧面（hPa）デフォルト: 50 100 200")
    parser.add_argument("--ecm", action="store_true", help="ECMWFも実行")
    parser.add_argument("--push", action="store_true", help="GitHub push する")

    return parser.parse_args()


def validate_init_time(init_time_str):
    if not re.match(r'^\d{10}$', init_time_str):
        raise ValueError(f"初期時刻形式が不正: {init_time_str}（YYYYMMDDHH形式）")
    return init_time_str


def format_datetime(init_time_str):
    """YYYYMMDDHH → YYYY/MM/DD HHUTCに変換"""
    year, month, day, hour = int(init_time_str[:4]), int(init_time_str[4:6]), \
                              int(init_time_str[6:8]), int(init_time_str[8:10])
    return f"{year}/{month:02d}/{day:02d} {hour:02d}UTC"


def run_report_script(script_name, init_time, n_days=1, ecm_flag=""):
    """レポートスクリプトを実行"""
    python_cmd = "python3" if shutil.which("python3") else "python"
    cmd = f"{python_cmd} {script_name} {init_time} {n_days} {ecm_flag}".strip()
    print(f"実行: {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=_SCRIPT_DIR)
    return result.returncode == 0


def find_images_in_report(report_dir, prefix, report_type="ave"):
    """レポートディレクトリから画像ファイル一覧を取得

    AVE: {YYYYMMDDHH}_AVG{n}d_GSM_{level}hPa_*
    WIDE: {YYYYMMDDHH}_FT*_GSM_{level}hPa_*

    複数バージョンがある場合は最短期間を優先
    """
    if not report_dir.exists():
        return {}

    images = {}
    png_files = list(report_dir.glob("*.png"))

    if report_type == "ave":
        # AVE型: 複数ある場合は _AVG1d_ → _AVG2d_ ... の順で優先
        candidates = {
            "upper_50": [],
            "upper_100": [],
            "upper_200": [],
            "upper_300": [],
            "ept850": []
        }

        for png_file in png_files:
            name = png_file.name
            if "300hPa" in name and "Height_Wind" in name:
                candidates["upper_300"].append(name)
            elif "200hPa" in name and "Height_Wind" in name:
                candidates["upper_200"].append(name)
            elif "100hPa" in name and "Height_Wind" in name:
                candidates["upper_100"].append(name)
            elif "50hPa" in name and "Height_Wind" in name:
                candidates["upper_50"].append(name)
            elif "850hPa_EPT" in name:
                candidates["ept850"].append(name)

        # 各キーについて、最短期間（1d, 2d, ... の順）を選択
        for key, names in candidates.items():
            if names:
                # _AVGnd_ の n が最小のものを選択
                sorted_names = sorted(names, key=lambda x: int(x.split("_AVG")[1].split("d_")[0]) if "_AVG" in x else 999)
                images[key] = sorted_names[0]

    else:
        # WIDE型: 複数ある場合は最初（FT=0からの範囲が短い）のものを選択
        candidates = {
            "upper_50": [],
            "upper_100": [],
            "upper_200": [],
            "upper_300": [],
            "ept850": []
        }

        for png_file in png_files:
            name = png_file.name
            if "_avg2_" not in name:  # avg2=FT000-006h を優先
                continue

            if "300hPa" in name and "Height_Wind" in name:
                candidates["upper_300"].append(name)
            elif "200hPa" in name and "Height_Wind" in name:
                candidates["upper_200"].append(name)
            elif "100hPa" in name and "Height_Wind" in name:
                candidates["upper_100"].append(name)
            elif "50hPa" in name and "Height_Wind" in name:
                candidates["upper_50"].append(name)
            elif "850hPa_EPT" in name:
                candidates["ept850"].append(name)

        # 最初のものを選択
        for key, names in candidates.items():
            if names:
                images[key] = names[0]

    return images


def build_comparison_md(init_times, report_types, levels, ecm_flag):
    """比較用MDファイルを構築（横に並べたレイアウト）"""
    lines = []

    # タイトル
    init_str_list = "_".join(init_times)
    lines.append("# ジェット・前線解析 複数初期時刻比較レポート")
    lines.append("")
    lines.append(f"**対象初期時刻**: {', '.join([format_datetime(it) for it in init_times])}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ---- AVE報告 ----
    if "ave" in report_types:
        lines.append("## AVE報告（複数日平均）")
        lines.append("")

        # 上層風
        lines.append(f"### 上層風（{', '.join([f'{lev}hPa' for lev in levels])}）")
        lines.append("")

        for lev in levels:
            lines.append(f"#### {lev}hPa")
            lines.append("")

            # 初期時刻をヘッダーに
            header = "| " + " | ".join([format_datetime(it) for it in init_times]) + " |"
            lines.append(header)
            lines.append("|" + "|".join(["---"] * len(init_times)) + "|")

            # 画像を1行に並べる
            row_cells = []
            for init_time in init_times:
                report_dir = _SCRIPT_DIR / "reports" / f"{init_time}-ave"
                images = find_images_in_report(report_dir, init_time, report_type="ave")

                key = f"upper_{lev}"
                if key in images:
                    img_name = images[key]
                    rel_path = f"../{init_time}-ave/{img_name}"
                    row_cells.append(f"![{lev}hPa]({rel_path})")
                else:
                    row_cells.append("（画像なし）")

            lines.append("| " + " | ".join(row_cells) + " |")
            lines.append("")

        # 850hPa相当温位
        lines.append("#### 850hPa 相当温位・風矢羽")
        lines.append("")

        header = "| " + " | ".join([format_datetime(it) for it in init_times]) + " |"
        lines.append(header)
        lines.append("|" + "|".join(["---"] * len(init_times)) + "|")

        row_cells = []
        for init_time in init_times:
            report_dir = _SCRIPT_DIR / "reports" / f"{init_time}-ave"
            images = find_images_in_report(report_dir, init_time, report_type="ave")

            if "ept850" in images:
                img_name = images["ept850"]
                rel_path = f"../{init_time}-ave/{img_name}"
                row_cells.append(f"![EPT850]({rel_path})")
            else:
                row_cells.append("（画像なし）")

        lines.append("| " + " | ".join(row_cells) + " |")
        lines.append("")
        lines.append("---")
        lines.append("")

    # ---- WIDE報告 ----
    if "wide" in report_types:
        lines.append("## WIDE報告（広域）")
        lines.append("")

        # 上層風
        lines.append(f"### 上層風（{', '.join([f'{lev}hPa' for lev in levels])}）")
        lines.append("")

        for lev in levels:
            lines.append(f"#### {lev}hPa")
            lines.append("")

            header = "| " + " | ".join([format_datetime(it) for it in init_times]) + " |"
            lines.append(header)
            lines.append("|" + "|".join(["---"] * len(init_times)) + "|")

            row_cells = []
            for init_time in init_times:
                report_dir = _SCRIPT_DIR / "reports" / f"{init_time}-wide"
                images = find_images_in_report(report_dir, init_time, report_type="wide")

                key = f"upper_{lev}"
                if key in images:
                    img_name = images[key]
                    rel_path = f"../{init_time}-wide/{img_name}"
                    row_cells.append(f"![{lev}hPa]({rel_path})")
                else:
                    row_cells.append("（画像なし）")

            lines.append("| " + " | ".join(row_cells) + " |")
            lines.append("")

        # 850hPa相当温位
        lines.append("#### 850hPa 相当温位・風矢羽")
        lines.append("")

        header = "| " + " | ".join([format_datetime(it) for it in init_times]) + " |"
        lines.append(header)
        lines.append("|" + "|".join(["---"] * len(init_times)) + "|")

        row_cells = []
        for init_time in init_times:
            report_dir = _SCRIPT_DIR / "reports" / f"{init_time}-wide"
            images = find_images_in_report(report_dir, init_time, report_type="wide")

            if "ept850" in images:
                img_name = images["ept850"]
                rel_path = f"../{init_time}-wide/{img_name}"
                row_cells.append(f"![EPT850]({rel_path})")
            else:
                row_cells.append("（画像なし）")

        lines.append("| " + " | ".join(row_cells) + " |")
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def main():
    # ヘルプ表示（引数に ?/-?/--? が含まれている場合）
    if len(sys.argv) > 1 and sys.argv[1] in ('?', '-?', '--?'):
        print("""
ジェット・前線解析 複数初期時刻比較レポート

使用方法:
  python jet_front_compare_report.py INIT_TIME1 INIT_TIME2 [INIT_TIME3] [オプション]

引数:
  INIT_TIME1, INIT_TIME2, [INIT_TIME3]
                           初期時刻（YYYYMMDDHH）2～3個を指定

オプション:
  --levels LEVEL [LEVEL...]
                         上層気圧面（hPa）デフォルト: 50 100 200
  --ave-only             AVEレポートのみを生成
  --wide-only            WIDEレポートのみを生成
  --ecm                  ECMWF (ECM) も実行（デフォルト: GSMのみ）
  --push                 生成後 GitHub へ push（デフォルト: スキップ）

使用例:
  python jet_front_compare_report.py 2026050600 2026050512
    → 2初期時刻の AVE+WIDE 比較レポート（50/100/200hPa）

  python jet_front_compare_report.py 2026050600 2026050512 2026050500
    → 3初期時刻の AVE+WIDE 比較レポート（50/100/200hPa）

  python jet_front_compare_report.py 2026050600 2026050512 --levels 100 200
    → 100/200hPa のみ比較

  python jet_front_compare_report.py 2026050600 2026050512 --ave-only
    → AVEレポートのみ比較

  python jet_front_compare_report.py 2026050600 2026050512 --wide-only --ecm
    → WIDEレポートのみ、GSM+ECMWF で比較

出力:
  reports/compare_INIT_TIME1_INIT_TIME2[_INIT_TIME3]/compare_report.md

特徴:
  ・比較画像は横に並べたテーブル形式で表示
  ・ファイルがない場合は自動的に各レポートを生成
        """)
        sys.exit(0)

    args = parse_args()

    # 初期時刻の検証
    if len(args.init_times) < 2 or len(args.init_times) > 3:
        print("エラー: 初期時刻は2個～3個指定してください")
        sys.exit(1)

    init_times = []
    for init_time in args.init_times:
        try:
            init_times.append(validate_init_time(init_time))
        except ValueError as e:
            print(f"エラー: {e}")
            sys.exit(1)

    # レポートタイプの決定
    report_types = []
    if args.ave_only:
        report_types = ["ave"]
    elif args.wide_only:
        report_types = ["wide"]
    else:
        report_types = ["ave", "wide"]

    # ECM フラグ
    ecm_flag = "--ecm" if args.ecm else ""

    print(f"{'='*60}")
    print(f" ジェット・前線解析 複数初期時刻比較レポート")
    print(f"{'='*60}")
    print(f"\n初期時刻: {', '.join(init_times)}")
    print(f"レポートタイプ: {', '.join(report_types)}")
    print(f"上層気圧面: {', '.join([f'{lev}hPa' for lev in args.levels])}")
    if args.ecm:
        print(f"ECMWF: 対応")
    print()

    # ---- 各レポートスクリプトを実行（ファイルがない場合） ----
    for init_time in init_times:
        print(f"\n{'─'*60}")
        print(f" {format_datetime(init_time)}")
        print(f"{'─'*60}")

        if "ave" in report_types:
            report_dir = _SCRIPT_DIR / "reports" / f"{init_time}-ave"
            if not report_dir.exists() or not list(report_dir.glob("*.png")):
                print("\n[1/2] AVE報告を生成中（ファイルなし）...")
                if not run_report_script("jet_front_ave_report.py", init_time, n_days=1, ecm_flag=ecm_flag):
                    print(f"警告: AVE報告の生成に失敗 ({init_time})")
            else:
                print("[1/2] AVE報告: 既存ファイルを使用")

        if "wide" in report_types:
            report_dir = _SCRIPT_DIR / "reports" / f"{init_time}-wide"
            if not report_dir.exists() or not list(report_dir.glob("*.png")):
                print("\n[2/2] WIDE報告を生成中（ファイルなし）...")
                if not run_report_script("jet_front_wide_report.py", init_time, ecm_flag=ecm_flag):
                    print(f"警告: WIDE報告の生成に失敗 ({init_time})")
            else:
                print("[2/2] WIDE報告: 既存ファイルを使用")

    # ---- 比較MDファイルを生成 ----
    print(f"\n{'='*60}")
    print(f" 比較レポートを生成中...")
    print(f"{'='*60}\n")

    md_content = build_comparison_md(init_times, report_types, args.levels, ecm_flag)

    # 出力ディレクトリ
    init_str = "_".join(init_times)
    compare_dir = _SCRIPT_DIR / "reports" / f"compare_{init_str}"
    compare_dir.mkdir(parents=True, exist_ok=True)

    md_name = "compare_report.md"
    md_path = compare_dir / md_name
    md_path.write_text(md_content, encoding="utf-8")

    print(f"MDファイル生成: reports/compare_{init_str}/{md_name}")

    # ---- git add → commit → push（--push 指定時のみ）----
    if not args.push:
        print("\nGitHub push はスキップ（--push を付けると実行）")
    else:
        print("\n--- GitHub へアップロード ---")
        rel_path = f"reports/compare_{init_str}"

        # git add
        cmd = f"git add {rel_path}"
        print(f"実行: {cmd}")
        result = subprocess.run(cmd, shell=True, cwd=_SCRIPT_DIR)
        if result.returncode != 0:
            print("エラー: git add 失敗")
            sys.exit(1)

        # 変更があるか確認
        result = subprocess.run("git diff --staged --quiet", shell=True, cwd=_SCRIPT_DIR)
        if result.returncode == 0:
            print("変更なし: 既にアップロード済みです（コミット・プッシュをスキップ）")
        else:
            # git commit
            commit_msg = f"report: ジェット・前線解析 複数初期時刻比較レポート ({init_str})"
            cmd = f'git commit -m "{commit_msg}"'
            print(f"実行: {cmd}")
            result = subprocess.run(cmd, shell=True, cwd=_SCRIPT_DIR)
            if result.returncode != 0:
                print("エラー: git commit 失敗")
                sys.exit(1)

            # git push
            cmd = "git push"
            print(f"実行: {cmd}")
            result = subprocess.run(cmd, shell=True, cwd=_SCRIPT_DIR)
            if result.returncode != 0:
                print("push 失敗。30秒待ってリトライします...")
                import time
                time.sleep(30)
                result = subprocess.run(cmd, shell=True, cwd=_SCRIPT_DIR)
            if result.returncode != 0:
                print("エラー: git push 失敗（手動で 'git push' を実行してください）")
                sys.exit(1)

    print(f"\n{'='*60}")
    print(f" 完了")
    print(f" レポート: reports/compare_{init_str}/{md_name}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
