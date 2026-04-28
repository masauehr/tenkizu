#!/usr/bin/env python
# coding: utf-8

# 100hPa 天気図レポート生成・GitHub アップロードスクリプト
# GSM/ECMWF の 100hPa 高度・風矢羽 天気図を生成し、
# reports/{INIT_TIME}/ にPNG+MDを配置して git push する
#
# 使用例:
#   python make_100hpa_report.py 2026041200          # GSMのみ FT=0h 1枚
#   python make_100hpa_report.py 2026041200 0000 5   # GSMのみ FT=0,6,12,18,24h 5枚
#   python make_100hpa_report.py 2026041200 0100 3   # GSMのみ FT=24,30,36h 3枚
#   python make_100hpa_report.py 2026041200 --ecm    # GSM+ECM FT=0h 1枚
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
        description='100hPa天気図レポートを生成してGitHubにアップロードする',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python make_100hpa_report.py 2026041200              # GSMのみ FT=0h 1枚
  python make_100hpa_report.py 2026041200 0000 5       # GSMのみ FT=0,6,12,18,24h 5枚
  python make_100hpa_report.py 2026041200 0100 3       # GSMのみ FT=24,30,36h 3枚
  python make_100hpa_report.py 2026041200 --ecm        # GSM+ECM FT=0h 1枚
  python make_100hpa_report.py 2026041200 0000 5 --ecm # GSM+ECM FT=0,6,12,18,24h 5枚
        """
    )
    parser.add_argument('init_time',   type=str, help='初期時刻 YYYYMMDDHH（UTC）')
    parser.add_argument('start_ft',    type=str, nargs='?', default='0000',
                        help='開始予報時間 DDHH形式（デフォルト: 0000）')
    parser.add_argument('n_steps',     type=int, nargs='?', default=1,
                        help='作成する枚数（6h間隔、デフォルト: 1）')
    parser.add_argument('--ecm',       action='store_true',
                        help='ECMWFも実行する（省略時はGSMのみ）')
    return parser.parse_args()


def run_python(script, script_dir):
    """conda環境でPythonスクリプトを実行する"""
    cmd = (
        "source $(conda info --base)/etc/profile.d/conda.sh && "
        "conda activate met_env_310 && "
        f"python {script}"
    )
    result = subprocess.run(cmd, shell=True, cwd=script_dir,
                            text=True, executable='/bin/bash')
    return result.returncode == 0


def run_git(cmd, cwd):
    """gitコマンドを実行して結果を表示する"""
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

    script_dir = Path(__file__).parent.resolve()
    output_dir = script_dir / "output"
    report_dir = script_dir / "reports" / init_str
    report_dir.mkdir(parents=True, exist_ok=True)

    with_ecm   = args.ecm
    model_label = "GSM+ECM" if with_ecm else "GSMのみ"

    print(f"{'='*55}")
    print(f" 100hPa 天気図レポート生成 [{model_label}]")
    print(f" 初期時刻: {init_str} UTC  開始FT: {start_ft_h}h  枚数: {n_steps}")
    print(f"{'='*55}\n")

    # ---- GSM 100hPa 天気図生成 ----
    print("--- GSM 100hPa ---")
    gsm_ok = run_python(
        f"GSM_100hPa.py {init_str} {args.start_ft} {n_steps}",
        script_dir
    )
    if not gsm_ok:
        print("警告: GSM_100hPa.py でエラーが発生しました")

    # ---- ECM 100hPa 天気図生成（--ecm 指定時のみ実行）----
    if not with_ecm:
        print("\n--- ECM 100hPa: スキップ（--ecm 未指定）---")
        ecm_ok = False
    else:
        print("\n--- ECM 100hPa ---")
        ecm_ok = run_python(
            f"ECM_100hPa.py {init_str} {start_ft_h} {n_steps}",
            script_dir
        )
        if not ecm_ok:
            print("警告: ECM_100hPa.py でエラーが発生しました")

    # ---- 生成PNG を reports/ にコピー ----
    dt_str2  = f"{i_year:04d}{i_month:02d}{i_day:02d}{i_hourZ:02d}"
    ft_list  = [start_ft_h + i * 6 for i in range(n_steps)]

    copied = {"gsm": [], "ecm": []}
    print(f"\n--- PNG を reports/{init_str}/ にコピー ---")
    for ft_h in ft_list:
        gsm_png = output_dir / f"{dt_str2}_FT{ft_h:03d}h_GSM_100hPa_Height_Wind.png"
        ecm_png = output_dir / f"{dt_str2}_FT{ft_h:03d}h_ECM_100hPa_Height_Wind.png"
        for src, key in [(gsm_png, "gsm"), (ecm_png, "ecm")]:
            if src.exists():
                dst = report_dir / src.name
                shutil.copy2(src, dst)
                copied[key].append((ft_h, src.name))
                print(f"  {src.name}")
            else:
                print(f"  ※ 見つかりません: {src.name}")

    if not copied["gsm"] and not copied["ecm"]:
        print("エラー: コピーするPNGがありません。処理を中断します。")
        sys.exit(1)

    # ---- Markdown レポート生成 ----
    dt_obj     = datetime(i_year, i_month, i_day, i_hourZ)
    dt_display = dt_obj.strftime("%Y/%m/%d %HUTC")

    lines = [
        "# 100hPa 天気図レポート",
        "",
        f"**初期時刻**: {dt_display}",
        "",
        "---",
        "",
    ]

    if copied["gsm"]:
        lines += ["## GSM 100hPa 高度・風矢羽", ""]
        for ft_h, fname in copied["gsm"]:
            lines += [
                f"### FT={ft_h}h",
                "",
                f"![GSM 100hPa FT={ft_h}h](./{fname})",
                "",
            ]

    if copied["ecm"]:
        lines += ["## ECMWF 100hPa 高度・風矢羽", ""]
        for ft_h, fname in copied["ecm"]:
            lines += [
                f"### FT={ft_h}h",
                "",
                f"![ECM 100hPa FT={ft_h}h](./{fname})",
                "",
            ]

    md_path = report_dir / "100hPa_report.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nMDファイル生成: reports/{init_str}/100hPa_report.md")

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
        commit_msg = f"report: 100hPa天気図レポート追加 ({init_str})"
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
    print(f" レポート: reports/{init_str}/100hPa_report.md")
    print(f"{'='*55}")


if __name__ == "__main__":
    main()
