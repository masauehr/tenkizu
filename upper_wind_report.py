#!/usr/bin/env python
# coding: utf-8

# 上層天気図レポート生成・GitHub アップロードスクリプト
# GSM/ECMWF の指定気圧面 高度・風矢羽 天気図を生成し、
# reports/{INIT_TIME}/ にPNG+MDを配置して git push する
#
# 使用例:
#   python upper_wind_report.py 2026041200                        # 100hPa GSMのみ FT=0h 1枚
#   python upper_wind_report.py 2026041200 0000 5                 # 100hPa GSMのみ 5枚
#   python upper_wind_report.py 2026041200 --ecm                  # 100hPa GSM+ECM FT=0h 1枚
#   python upper_wind_report.py 2026041200 --levels 100 50        # 100+50hPa GSMのみ FT=0h
#   python upper_wind_report.py 2026041200 0000 5 --levels 100 50 --ecm  # 複数面・複数FT・GSM+ECM
#
# 作成: 20260428 上原政博

import os
import sys
import subprocess
import shutil
import argparse
from pathlib import Path
from datetime import datetime


def ddhh_to_hours(ddhh):
    return (ddhh // 100) * 24 + (ddhh % 100)


def parse_args():
    parser = argparse.ArgumentParser(
        description='上層天気図レポートを生成してGitHubにアップロードする',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python upper_wind_report.py 2026041200                          # 100hPa GSMのみ FT=0h 1枚
  python upper_wind_report.py 2026041200 0000 5                   # 100hPa GSMのみ 5枚
  python upper_wind_report.py 2026041200 --ecm                    # 100hPa GSM+ECM FT=0h 1枚
  python upper_wind_report.py 2026041200 --levels 100 50          # 100+50hPa GSMのみ FT=0h
  python upper_wind_report.py 2026041200 0000 5 --levels 100 50 --ecm  # 複数面・GSM+ECM 5枚
        """
    )
    parser.add_argument('init_time',  type=str, help='初期時刻 YYYYMMDDHH（UTC）')
    parser.add_argument('start_ft',   type=str, nargs='?', default='0000',
                        help='開始予報時間 DDHH形式（デフォルト: 0000）')
    parser.add_argument('n_steps',    type=int, nargs='?', default=1,
                        help='作成する枚数（6h間隔、デフォルト: 1）')
    parser.add_argument('--levels',   type=int, nargs='+', default=[100],
                        help='描画する気圧面 hPa（複数指定可、デフォルト: 100）')
    parser.add_argument('--ecm',      action='store_true',
                        help='ECMWFも実行する（省略時はGSMのみ）')
    return parser.parse_args()


def run_python(script, script_dir):
    cmd = (
        "source $(conda info --base)/etc/profile.d/conda.sh && "
        "conda activate met_env_310 && "
        f"python {script}"
    )
    result = subprocess.run(cmd, shell=True, cwd=script_dir,
                            text=True, executable='/bin/bash')
    return result.returncode == 0


def run_git(cmd, cwd):
    print(f"$ git {cmd}")
    result = subprocess.run(f"git {cmd}", shell=True, cwd=cwd,
                            capture_output=True, text=True)
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip())
    return result.returncode


def main():
    args = parse_args()
    init_str = args.init_time
    if len(init_str) != 10:
        print("エラー: init_time は YYYYMMDDHH の10桁で指定してください")
        sys.exit(1)

    i_year  = int(init_str[0:4])
    i_month = int(init_str[4:6])
    i_day   = int(init_str[6:8])
    i_hourZ = int(init_str[8:10])

    start_ddhh = int(args.start_ft)
    n_steps    = args.n_steps
    start_ft_h = ddhh_to_hours(start_ddhh)
    levels     = args.levels
    with_ecm   = args.ecm

    script_dir = Path(__file__).parent.resolve()
    output_dir = script_dir / "output"
    report_dir = script_dir / "reports" / init_str
    report_dir.mkdir(parents=True, exist_ok=True)

    level_label = "+".join(f"{l}hPa" for l in levels)
    model_label = "GSM+ECM" if with_ecm else "GSMのみ"

    print(f"{'='*55}")
    print(f" 上層天気図レポート生成 [{model_label}] [{level_label}]")
    print(f" 初期時刻: {init_str} UTC  開始FT: {start_ft_h}h  枚数: {n_steps}")
    print(f"{'='*55}\n")

    # ---- 気圧面ごとに GSM / ECM を実行 ----
    for lev in levels:
        print(f"--- GSM {lev}hPa ---")
        ok = run_python(
            f"GSM_100hPa.py {init_str} {args.start_ft} {n_steps} {lev}",
            script_dir
        )
        if not ok:
            print(f"警告: GSM_100hPa.py (level={lev}) でエラーが発生しました")

        if not with_ecm:
            print(f"\n--- ECM {lev}hPa: スキップ（--ecm 未指定）---")
        else:
            print(f"\n--- ECM {lev}hPa ---")
            ok = run_python(
                f"ECM_100hPa.py {init_str} {start_ft_h} {n_steps} {lev}",
                script_dir
            )
            if not ok:
                print(f"警告: ECM_100hPa.py (level={lev}) でエラーが発生しました")
        print()

    # ---- 生成PNG を reports/ にコピー ----
    dt_str2 = f"{i_year:04d}{i_month:02d}{i_day:02d}{i_hourZ:02d}"
    ft_list = [start_ft_h + i * 6 for i in range(n_steps)]

    # copied[level] = {"gsm": [(ft_h, fname), ...], "ecm": [...]}
    copied = {lev: {"gsm": [], "ecm": []} for lev in levels}
    print(f"--- PNG を reports/{init_str}/ にコピー ---")
    for lev in levels:
        for ft_h in ft_list:
            gsm_png = output_dir / f"{dt_str2}_FT{ft_h:03d}h_GSM_{lev}hPa_Height_Wind.png"
            ecm_png = output_dir / f"{dt_str2}_FT{ft_h:03d}h_ECM_{lev}hPa_Height_Wind.png"
            for src, key in [(gsm_png, "gsm"), (ecm_png, "ecm")]:
                if src.exists():
                    dst = report_dir / src.name
                    shutil.copy2(src, dst)
                    copied[lev][key].append((ft_h, src.name))
                    print(f"  {src.name}")
                else:
                    print(f"  ※ 見つかりません: {src.name}")

    any_copied = any(
        copied[lev][m] for lev in levels for m in ("gsm", "ecm")
    )
    if not any_copied:
        print("エラー: コピーするPNGがありません。処理を中断します。")
        sys.exit(1)

    # ---- Markdown レポート生成 ----
    dt_obj     = datetime(i_year, i_month, i_day, i_hourZ)
    dt_display = dt_obj.strftime("%Y/%m/%d %HUTC")

    lines = [
        f"# 上層天気図レポート ({level_label})",
        "",
        f"**初期時刻**: {dt_display}",
        "",
        "---",
        "",
    ]

    for lev in levels:
        lines += [f"## {lev}hPa 高度・風矢羽", ""]

        if copied[lev]["gsm"]:
            lines += [f"### GSM {lev}hPa", ""]
            for ft_h, fname in copied[lev]["gsm"]:
                lines += [
                    f"#### FT={ft_h}h",
                    "",
                    f"![GSM {lev}hPa FT={ft_h}h](./{fname})",
                    "",
                ]

        if copied[lev]["ecm"]:
            lines += [f"### ECMWF {lev}hPa", ""]
            for ft_h, fname in copied[lev]["ecm"]:
                lines += [
                    f"#### FT={ft_h}h",
                    "",
                    f"![ECM {lev}hPa FT={ft_h}h](./{fname})",
                    "",
                ]

        lines += ["---", ""]

    md_path = report_dir / "upper_wind_report.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nMDファイル生成: reports/{init_str}/upper_wind_report.md")

    # ---- git add → commit → push ----
    print("\n--- GitHub へアップロード ---")
    rel_path = f"reports/{init_str}"

    rc = run_git(f"add {rel_path}", script_dir)
    if rc != 0:
        print("エラー: git add 失敗")
        sys.exit(1)

    # ステージングに差分があるか確認（なければコミット不要）
    staged = subprocess.run("git diff --staged --quiet", shell=True, cwd=script_dir)
    if staged.returncode == 0:
        print("変更なし: 既にアップロード済みです（コミット・プッシュをスキップ）")
    else:
        commit_msg = f"report: 上層天気図レポート追加 {level_label} ({init_str})"
        rc = run_git(f'commit -m "{commit_msg}"', script_dir)
        if rc != 0:
            print("エラー: git commit 失敗")
            sys.exit(1)

        # PNG が大きいため postBuffer を 500MB に拡張してからプッシュ
        run_git("config http.postBuffer 524288000", script_dir)

        rc = run_git("push", script_dir)
        if rc != 0:
            print("push 失敗。30秒待ってリトライします...")
            import time
            time.sleep(30)
            rc = run_git("push", script_dir)
        if rc != 0:
            print("エラー: git push 失敗（手動で 'git push' を実行してください）")
            sys.exit(1)

    print(f"\n{'='*55}")
    print(f" 完了")
    print(f" レポート: reports/{init_str}/upper_wind_report.md")
    print(f"{'='*55}")


if __name__ == "__main__":
    main()
