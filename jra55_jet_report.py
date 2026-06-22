#!/usr/bin/env python
# coding: utf-8

# JRA-55 ジェット・上層発散天気図レポート生成・GitHub アップロードスクリプト
#
# 使用例:
#   python jra55_jet_report.py 19590915
#   python jra55_jet_report.py 1959091512 --level 300
#   python jra55_jet_report.py 19590915 --hours 0 6 12 18 --push

import argparse
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="JRA-55のジェット気流・上層発散天気図を生成し、Markdownレポート化する",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python jra55_jet_report.py 19590915
  python jra55_jet_report.py 1959091512 --level 300
  python jra55_jet_report.py 19590915 --hours 0 6 12 18 --push

実行環境（conda の場合）:
  conda activate met_env
  python jra55_jet_report.py [引数]

  ※ 環境名（met_env）は利用者の構築状況により異なります。
     xarray / metpy / cartopy 等が入った Python 3.10 環境であれば動作します。
""",
    )
    parser.add_argument("date", help="対象日時 YYYYMMDD または YYYYMMDDHH（UTC）")
    parser.add_argument("--hours", type=int, nargs="+", default=None, help="YYYYMMDD指定時の作成時刻 UTC")
    parser.add_argument("--level", type=int, default=300, help="気圧面 hPa（デフォルト: 300）")
    parser.add_argument("--data-dir", default="./data/Jra55", help="JRA-55 NetCDF保存先")
    parser.add_argument("--output-dir", default="./output", help="一時PNG出力先")
    parser.add_argument("--config", default="./jra55_config.ini", help="JRA-55認証設定ファイル")
    parser.add_argument("--push", action="store_true", help="GitHubへ git push する")

    # ? / -? / --? でヘルプ表示
    if any(a in sys.argv[1:] for a in ('?', '-?', '--?')):
        parser.print_help()
        sys.exit(0)

    return parser.parse_args()


def parse_valid_times(date_arg, hours):
    if len(date_arg) == 10 and date_arg.isdigit():
        valid = datetime.strptime(date_arg, "%Y%m%d%H")
        if valid.hour not in (0, 6, 12, 18):
            raise ValueError("時刻は 00/06/12/18 UTC のいずれかを指定してください")
        return [valid]

    if len(date_arg) == 8 and date_arg.isdigit():
        base = datetime.strptime(date_arg, "%Y%m%d")
        use_hours = hours if hours is not None else [0]
        invalid = [h for h in use_hours if h not in (0, 6, 12, 18)]
        if invalid:
            raise ValueError(f"--hours は 0/6/12/18 のみ指定できます: {invalid}")
        return [base.replace(hour=h) for h in use_hours]

    raise ValueError("date は YYYYMMDD または YYYYMMDDHH で指定してください")


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


def copy_png(src, report_dir):
    if not src.exists():
        print(f"  ※ 見つかりません: {src.name}")
        return None
    dst = report_dir / src.name
    shutil.copy2(src, dst)
    print(f"  {src.name}")
    return src.name


def main():
    args = parse_args()
    try:
        valid_times = parse_valid_times(args.date, args.hours)
    except ValueError as exc:
        print(f"エラー: {exc}")
        sys.exit(2)

    script_dir = Path(__file__).parent.resolve()
    output_dir = script_dir / args.output_dir
    date_label = valid_times[0].strftime("%Y%m%d")
    if len(valid_times) == 1:
        report_label = valid_times[0].strftime("%Y%m%d%H")
        time_label = valid_times[0].strftime("%HUTC")
    else:
        report_label = date_label
        time_label = ",".join(v.strftime("%HUTC") for v in valid_times)
    report_dir = script_dir / "reports" / f"{report_label}-jra55"
    report_dir.mkdir(parents=True, exist_ok=True)

    print(f"{'=' * 58}")
    print(" JRA-55 ジェット・上層発散レポート生成")
    print(f" 対象: {date_label} {time_label}  気圧面: {args.level}hPa")
    print(f"{'=' * 58}\n")

    copied = []
    for valid in valid_times:
        valid_str = valid.strftime("%Y%m%d%H")
        print(f"=== {valid_str} UTC ===")
        command = (
            f"JRA55_JetDivergence.py {valid_str} "
            f"--level {args.level} "
            f"--data-dir {args.data_dir} "
            f"--output-dir {args.output_dir} "
            f"--config {args.config}"
        )
        if not run_python(command, script_dir):
            print(f"エラー: JRA55_JetDivergence.py で失敗しました: {valid_str}")
            sys.exit(1)

        png = output_dir / f"{valid_str}_JRA55_{args.level}hPa_Jet_Divergence.png"
        print(f"--- PNG を reports/{report_dir.name}/ にコピー ---")
        fname = copy_png(png, report_dir)
        if fname:
            copied.append((valid, fname))
        print()

    if not copied:
        print("エラー: コピーするPNGがありません。処理を中断します。")
        sys.exit(1)

    title_date = valid_times[0].strftime("%Y/%m/%d")
    lines = [
        f"# JRA-55 ジェット・上層発散天気図 ({args.level}hPa)",
        "",
        f"**対象日**: {title_date}",
        f"**時刻**: {time_label}",
        "",
        "---",
        "",
        "## Jet / Divergence",
        "",
    ]
    for valid, fname in copied:
        valid_display = valid.strftime("%Y/%m/%d %HUTC")
        lines += [
            f"### {valid_display}",
            "",
            f"![JRA-55 {args.level}hPa Jet Divergence {valid.strftime('%Y%m%d%H')}](./{fname})",
            "",
        ]

    md_name = f"jra55_jet_report_{report_label}_{args.level}hPa.md"
    md_path = report_dir / md_name
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"MDファイル生成: reports/{report_dir.name}/{md_name}")

    if not args.push:
        print("\nGitHub push はスキップ（--push を付けると実行）")
    else:
        print("\n--- GitHub へアップロード ---")
        paths = [
            ".gitignore",
            "JRA55_JetDivergence.py",
            "jra55_jet_report.py",
            "jra55_config.example.ini",
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
            commit_msg = f"report: JRA-55 jet divergence {report_label} {args.level}hPa"
            rc = run_git(f'commit -m "{commit_msg}"', script_dir)
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
