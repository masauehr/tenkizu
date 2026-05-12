#!/usr/bin/env python
# coding: utf-8

import argparse
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ALL_CHARTS = ["jet", "fax57", "fax78", "ept", "srf"]


def parse_args():
    parser = argparse.ArgumentParser(
        description="JRA-55総観天気図セットを生成してMarkdown化し、必要ならGitHubへpushする",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python jra55_synop_report.py 19590915
  python jra55_synop_report.py 1959091512 --charts jet srf
  python jra55_synop_report.py 19590915 --push
        """,
    )
    parser.add_argument("date", help="対象日時 YYYYMMDD または YYYYMMDDHH（UTC）")
    parser.add_argument("--hour", type=int, default=0, help="YYYYMMDD指定時のUTC時刻（0/6/12/18）")
    parser.add_argument("--charts", nargs="+", choices=ALL_CHARTS, default=ALL_CHARTS)
    parser.add_argument("--data-dir", default="./data/Jra55")
    parser.add_argument("--output-dir", default="./output")
    parser.add_argument("--config", default="./jra55_config.ini")
    parser.add_argument("--push", action="store_true")
    return parser.parse_args()


def valid_time_from_args(date_arg, hour):
    if len(date_arg) == 10 and date_arg.isdigit():
        valid = datetime.strptime(date_arg, "%Y%m%d%H")
    elif len(date_arg) == 8 and date_arg.isdigit():
        valid = datetime.strptime(date_arg, "%Y%m%d").replace(hour=hour)
    else:
        raise ValueError("date は YYYYMMDD または YYYYMMDDHH で指定してください")
    if valid.hour not in (0, 6, 12, 18):
        raise ValueError("時刻は 00/06/12/18 UTC のいずれかを指定してください")
    return valid


def run_python(command, cwd):
    cmd = (
        "source $(conda info --base)/etc/profile.d/conda.sh && "
        "conda activate met_env && "
        f"python {command}"
    )
    result = subprocess.run(cmd, shell=True, cwd=cwd, text=True, executable="/bin/bash")
    return result.returncode == 0


def run_git(command, cwd):
    print(f"$ git {command}")
    result = subprocess.run(f"git {command}", shell=True, cwd=cwd, capture_output=True, text=True)
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip())
    return result.returncode


def copy_png(src, report_dir, label):
    if not src.exists():
        print(f"  ※ 見つかりません: {src.name} ({label})")
        return None
    dst = report_dir / src.name
    shutil.copy2(src, dst)
    print(f"  {src.name}")
    return src.name


def main():
    args = parse_args()
    try:
        valid = valid_time_from_args(args.date, args.hour)
    except ValueError as exc:
        print(f"エラー: {exc}")
        sys.exit(2)

    script_dir = Path(__file__).parent.resolve()
    output_dir = script_dir / args.output_dir
    valid_str = valid.strftime("%Y%m%d%H")
    report_dir = script_dir / "reports" / f"{valid_str}-jra55-synop"
    report_dir.mkdir(parents=True, exist_ok=True)

    print(f"{'=' * 60}")
    print(" JRA-55 総観天気図レポート生成")
    print(f" 対象: {valid_str} UTC  種別: {'+'.join(args.charts)}")
    print(f"{'=' * 60}\n")

    command = (
        f"JRA55_SynopCharts.py {valid_str} "
        f"--charts {' '.join(args.charts)} "
        f"--data-dir {args.data_dir} "
        f"--output-dir {args.output_dir} "
        f"--config {args.config}"
    )
    if not run_python(command, script_dir):
        print("エラー: JRA55_SynopCharts.py で失敗しました")
        sys.exit(1)

    png_names = {
        "jet": "300hPa_Jet_Divergence",
        "fax57": "Fax57",
        "fax78": "Fax78",
        "ept": "850hPa_EPT",
        "srf": "SurfacePressure",
    }
    titles = {
        "jet": "Jet 300hPa（等風速・発散・非地衡風）",
        "fax57": "500/700hPa（500hPa気温・700hPa湿数）",
        "fax78": "700/850hPa（700hPa発散・850hPa気温風）",
        "ept": "850hPa 相当温位・風",
        "srf": "地上気圧・風・地上気温",
    }

    collected = {}
    print(f"--- PNG を reports/{report_dir.name}/ にコピー ---")
    for chart in args.charts:
        src = output_dir / f"{valid_str}_JRA55_{png_names[chart]}.png"
        fname = copy_png(src, report_dir, chart)
        if fname:
            collected[chart] = fname

    if not collected:
        print("エラー: コピーするPNGがありません。")
        sys.exit(1)

    lines = [
        "# JRA-55 総観天気図レポート",
        "",
        f"**対象時刻**: {valid.strftime('%Y/%m/%d %HUTC')}",
        "",
        "---",
        "",
    ]
    for chart in args.charts:
        if chart not in collected:
            continue
        lines += [
            f"## {titles[chart]}",
            "",
            f"![JRA-55 {titles[chart]}](./{collected[chart]})",
            "",
            "---",
            "",
        ]

    md_name = f"jra55_synop_report_{valid_str}.md"
    md_path = report_dir / md_name
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nMDファイル生成: reports/{report_dir.name}/{md_name}")

    if not args.push:
        print("\nGitHub push はスキップ（--push を付けると実行）")
    else:
        print("\n--- GitHub へアップロード ---")
        paths = [
            ".gitignore",
            "JRA55_SynopCharts.py",
            "jra55_synop_report.py",
            f"reports/{report_dir.name}",
        ]
        rc = run_git("add " + " ".join(paths), script_dir)
        if rc != 0:
            print("エラー: git add 失敗")
            sys.exit(1)
        staged = subprocess.run("git diff --staged --quiet", shell=True, cwd=script_dir)
        if staged.returncode == 0:
            print("変更なし: コミット・プッシュをスキップ")
        else:
            rc = run_git(f'commit -m "report: JRA-55 synop report {valid_str}"', script_dir)
            if rc != 0:
                print("エラー: git commit 失敗")
                sys.exit(1)
            rc = run_git("push", script_dir)
            if rc != 0:
                print("エラー: git push 失敗")
                sys.exit(1)

    print(f"\n完了: reports/{report_dir.name}/{md_name}")


if __name__ == "__main__":
    main()
