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
  python jet_front_compare_report.py 2026050600 2026050512 --wide-only
        """)
    parser.add_argument("init_times", nargs="+", help="初期時刻（YYYYMMDDHH）2～3個")
    parser.add_argument("--ave-only", action="store_true", help="AVEレポートのみ")
    parser.add_argument("--wide-only", action="store_true", help="WIDEレポートのみ")
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
    """
    if not report_dir.exists():
        return {}

    images = {}
    png_files = list(report_dir.glob("*.png"))

    # 初回（または単一）のファイルを優先するため、FT/AVG の値で分類
    if report_type == "ave":
        # AVE型: 複数解像度がある場合は最初のFTを選択
        for png_file in sorted(png_files):
            name = png_file.name
            if "300hPa" in name and "upper_300" not in images:
                images["upper_300"] = name
            elif "200hPa" in name and "upper_200" not in images:
                images["upper_200"] = name
            elif "100hPa" in name and "Height_Wind" in name and "upper_100" not in images:
                images["upper_100"] = name
            elif "50hPa" in name and "upper_50" not in images:
                images["upper_50"] = name
            elif "850hPa_EPT" in name and "ept850" not in images:
                images["ept850"] = name
    else:
        # WIDE型: 複数ある場合は最初（FT=0からの範囲が短い）のものを選択
        for png_file in sorted(png_files):
            name = png_file.name
            if "_avg2_" not in name:  # avg2=FT000-006h を優先
                continue

            if "300hPa" in name and "upper_300" not in images:
                images["upper_300"] = name
            elif "200hPa" in name and "upper_200" not in images:
                images["upper_200"] = name
            elif "100hPa" in name and "Height_Wind" in name and "upper_100" not in images:
                images["upper_100"] = name
            elif "50hPa" in name and "upper_50" not in images:
                images["upper_50"] = name
            elif "850hPa_EPT" in name and "ept850" not in images:
                images["ept850"] = name

    return images


def build_comparison_md(init_times, report_types, ecm_flag):
    """比較用MDファイルを構築"""
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
        lines.append("### 上層風（300hPa + 200hPa + 100hPa）")
        lines.append("")

        for lev in [300, 200, 100]:
            lines.append(f"#### {lev}hPa")
            lines.append("")
            lines.append(f"| 初期時刻 | 画像 |")
            lines.append("|---------|------|")

            for init_time in init_times:
                report_dir = _SCRIPT_DIR / "reports" / f"{init_time}-ave"
                images = find_images_in_report(report_dir, init_time, report_type="ave")

                key = f"upper_{lev}"
                if key in images:
                    img_name = images[key]
                    rel_path = f"../{init_time}-ave/{img_name}"
                    dt_fmt = format_datetime(init_time)
                    lines.append(f"| {dt_fmt} | ![{lev}hPa]({rel_path}) |")
                else:
                    lines.append(f"| {format_datetime(init_time)} | （画像なし） |")

            lines.append("")

        # 850hPa相当温位
        lines.append("### 850hPa 相当温位・風矢羽")
        lines.append("")
        lines.append("| 初期時刻 | 画像 |")
        lines.append("|---------|------|")

        for init_time in init_times:
            report_dir = _SCRIPT_DIR / "reports" / f"{init_time}-ave"
            images = find_images_in_report(report_dir, init_time, report_type="ave")

            if "ept850" in images:
                img_name = images["ept850"]
                rel_path = f"../{init_time}-ave/{img_name}"
                lines.append(f"| {format_datetime(init_time)} | ![EPT850]({rel_path}) |")
            else:
                lines.append(f"| {format_datetime(init_time)} | （画像なし） |")

        lines.append("")
        lines.append("---")
        lines.append("")

    # ---- WIDE報告 ----
    if "wide" in report_types:
        lines.append("## WIDE報告（広域）")
        lines.append("")

        # 上層風
        lines.append("### 上層風（100hPa）")
        lines.append("")
        lines.append("| 初期時刻 | 画像 |")
        lines.append("|---------|------|")

        for init_time in init_times:
            report_dir = _SCRIPT_DIR / "reports" / f"{init_time}-wide"
            images = find_images_in_report(report_dir, init_time, report_type="wide")

            if "upper_100" in images:
                img_name = images["upper_100"]
                rel_path = f"../{init_time}-wide/{img_name}"
                lines.append(f"| {format_datetime(init_time)} | ![100hPa]({rel_path}) |")
            else:
                lines.append(f"| {format_datetime(init_time)} | （画像なし） |")

        lines.append("")

        # 850hPa相当温位
        lines.append("### 850hPa 相当温位・風矢羽")
        lines.append("")
        lines.append("| 初期時刻 | 画像 |")
        lines.append("|---------|------|")

        for init_time in init_times:
            report_dir = _SCRIPT_DIR / "reports" / f"{init_time}-wide"
            images = find_images_in_report(report_dir, init_time, report_type="wide")

            if "ept850" in images:
                img_name = images["ept850"]
                rel_path = f"../{init_time}-wide/{img_name}"
                lines.append(f"| {format_datetime(init_time)} | ![EPT850]({rel_path}) |")
            else:
                lines.append(f"| {format_datetime(init_time)} | （画像なし） |")

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
  --ave-only             AVEレポートのみを生成
  --wide-only            WIDEレポートのみを生成
  --ecm                  ECMWF (ECM) も実行（デフォルト: GSMのみ）
  --push                 生成後 GitHub へ push（デフォルト: スキップ）

使用例:
  python jet_front_compare_report.py 2026050600 2026050512
    → 2初期時刻の AVE+WIDE 比較レポートを生成

  python jet_front_compare_report.py 2026050600 2026050512 2026050500
    → 3初期時刻の AVE+WIDE 比較レポートを生成

  python jet_front_compare_report.py 2026050600 2026050512 --ave-only
    → AVEレポートのみ比較

  python jet_front_compare_report.py 2026050600 2026050512 --wide-only --ecm
    → WIDEレポートのみ、GSM+ECMWF で比較

出力:
  reports/compare_INIT_TIME1_INIT_TIME2[_INIT_TIME3]/compare_report.md
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
    if args.ecm:
        print(f"ECMWF: 対応")
    print()

    # ---- 各レポートスクリプトを実行 ----
    for init_time in init_times:
        print(f"\n{'─'*60}")
        print(f" {format_datetime(init_time)}")
        print(f"{'─'*60}")

        if "ave" in report_types:
            print("\n[1/2] AVE報告を生成中...")
            if not run_report_script("jet_front_ave_report.py", init_time, n_days=1, ecm_flag=ecm_flag):
                print(f"警告: AVE報告の生成に失敗 ({init_time})")

        if "wide" in report_types:
            print("\n[2/2] WIDE報告を生成中...")
            if not run_report_script("jet_front_wide_report.py", init_time, ecm_flag=ecm_flag):
                print(f"警告: WIDE報告の生成に失敗 ({init_time})")

    # ---- 比較MDファイルを生成 ----
    print(f"\n{'='*60}")
    print(f" 比較レポートを生成中...")
    print(f"{'='*60}\n")

    md_content = build_comparison_md(init_times, report_types, ecm_flag)

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
