#!/usr/bin/env python
# coding: utf-8

# GSM + ECMWF 地上気圧天気図 比較レポートスクリプト
# 既存の GSM_faxSrfPre.py / ECM_SurfacePressure.py を実行し、
# 生成された PNG を reports/{init_str}/ にコピーして
# FTごとに GSM/ECM を横並びテーブルで表示する Markdown を生成する。
# --push で git push まで行う。
#
# 使用例:
#   python ECM_GSM_SurfacePressure.py 2026052712                  # FT=0h（GSM+ECM）
#   python ECM_GSM_SurfacePressure.py 2026052712 0000 3           # FT=0,6,12h 3枚
#   python ECM_GSM_SurfacePressure.py 2026052712 0000 12h         # 12hプリセット
#   python ECM_GSM_SurfacePressure.py 2026052712 --gsm            # GSMのみ FT=0h
#   python ECM_GSM_SurfacePressure.py 2026052712 --ecm            # ECMWFのみ FT=0h
#   python ECM_GSM_SurfacePressure.py 2026052712 0000 3 --push    # pushあり

import sys
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

PRESETS = {
    "12h": {"interval": 12, "n_steps": 5},   # FT=0,12,24,36,48h
    "24h": {"interval": 24, "n_steps": 6},   # FT=0,24,48,72,96,120h
}


def ddhh_to_hours(ddhh):
    return (ddhh // 100) * 24 + (ddhh % 100)


def hours_to_ddhh(h):
    return (h // 24) * 100 + (h % 24)


def parse_args():
    import argparse
    preset_list = ", ".join(
        f"{k}（{v['interval']}h間隔×{v['n_steps']}枚）" for k, v in PRESETS.items()
    )
    parser = argparse.ArgumentParser(
        description="GSM+ECMWF 地上気圧天気図を FT ごとに横並び比較する Markdown を生成する",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python ECM_GSM_SurfacePressure.py 2026052712                  # FT=0h（GSM+ECM）
  python ECM_GSM_SurfacePressure.py 2026052712 0000 3           # FT=0,6,12h 3枚
  python ECM_GSM_SurfacePressure.py 2026052712 0000 12h         # 12hプリセット
  python ECM_GSM_SurfacePressure.py 2026052712 --gsm            # GSMのみ FT=0h
  python ECM_GSM_SurfacePressure.py 2026052712 --ecm            # ECMWFのみ FT=0h
  python ECM_GSM_SurfacePressure.py 2026052712 0000 3 --push    # pushあり

ECM描画設定（固定値）:
  --area        108 156 5 45   東経108〜156°、北緯5〜45°
  --smooth-size 10             10×10格子平均スムージング（ECM 0.25°→約2.5°相当）
  --wind-step   10             風矢羽を10格子おき（約2.5度間隔）
        """
    )
    parser.add_argument("init_time", type=str,
                        help="初期時刻 YYYYMMDDHH（UTC）")
    parser.add_argument("start_ft", type=str, nargs="?", default="0000",
                        help="開始予報時間 DDHH形式（デフォルト: 0000）")
    parser.add_argument("n_steps", type=str, nargs="?", default="1",
                        help=f"枚数（デフォルト: 1）またはプリセット名 [{preset_list}]")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--gsm", action="store_true",
                            help="GSMのみ実行（デフォルトは両モデル）")
    mode_group.add_argument("--ecm", action="store_true",
                            help="ECMWFのみ実行（デフォルトは両モデル）")
    parser.add_argument("--push", action="store_true",
                        help="GitHub へ git push する（省略時はローカル保存のみ）")

    # ? / -? / --? でヘルプ表示
    if any(a in sys.argv[1:] for a in ('?', '-?', '--?')):
        parser.print_help()
        sys.exit(0)

    return parser.parse_args()


def run_python(script, args_str, script_dir):
    cmd = (
        "source $(conda info --base)/etc/profile.d/conda.sh && "
        "conda activate met_env_310 && "
        f"python {script} {args_str}"
    )
    result = subprocess.run(cmd, shell=True, cwd=script_dir,
                            text=True, executable="/bin/bash")
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


def copy_png(src, report_dir, label):
    if src.exists():
        shutil.copy2(src, report_dir / src.name)
        print(f"  {src.name}")
        return src.name
    else:
        print(f"  ※ 見つかりません: {src.name} ({label})")
        return None


def main():
    args = parse_args()
    init_str = args.init_time

    if len(init_str) != 10:
        print("エラー: init_time は YYYYMMDDHH の10桁で指定してください")
        sys.exit(1)

    run_gsm = not args.ecm
    run_ecm = not args.gsm

    start_ddhh = int(args.start_ft)
    start_hours = ddhh_to_hours(start_ddhh)

    if args.n_steps in PRESETS:
        n_steps = PRESETS[args.n_steps]["n_steps"]
        interval = PRESETS[args.n_steps]["interval"]
    else:
        n_steps = int(args.n_steps)
        interval = 6

    ft_end = start_hours + (n_steps - 1) * interval
    ft_list_h = [start_hours + i * interval for i in range(n_steps)]

    if n_steps == 1:
        ft_label = f"FT{start_hours}"
    elif interval == 6:
        ft_label = f"FT{start_hours}-{ft_end}"
    else:
        ft_label = f"FT{start_hours}-{ft_end}_{interval}h"

    script_dir = Path(__file__).parent.resolve()
    output_dir = script_dir / "output"
    report_dir = script_dir / "reports" / init_str
    report_dir.mkdir(parents=True, exist_ok=True)

    model_label = "GSMのみ" if args.gsm else ("ECMWFのみ" if args.ecm else "GSM+ECM")
    print("=" * 60)
    print(f" 地上気圧比較レポート [{model_label}]")
    print(f" 初期時刻: {init_str}  FT: {start_hours}〜{ft_end}h  {n_steps}枚  {interval}h間隔")
    print("=" * 60)

    # ---- Step 1: PNG 生成 ----
    print("\n--- Step 1: PNG 生成 ---")
    for ft_h in ft_list_h:
        ft_ddhh = hours_to_ddhh(ft_h)
        if run_gsm:
            ok = run_python("GSM_faxSrfPre.py",
                            f"{init_str} {ft_ddhh:04d} 1 --area 108 156 5 45",
                            str(script_dir))
            if not ok:
                print(f"  警告: GSM_faxSrfPre.py FT={ft_h}h でエラーが発生しました")
        if run_ecm:
            ok = run_python("ECM_SurfacePressure.py",
                            f"{init_str} {ft_h} 1 --area 108 156 5 45 --smooth-size 10 --wind-step 10",
                            str(script_dir))
            if not ok:
                print(f"  警告: ECM_SurfacePressure.py FT={ft_h}h でエラーが発生しました")

    # ---- Step 2: PNG を reports/ にコピー ----
    print(f"\n--- Step 2: PNG を reports/{init_str}/ にコピー ---")
    collected_gsm = {}
    collected_ecm = {}

    for ft_h in ft_list_h:
        if run_gsm:
            src = output_dir / f"{init_str}_FT{ft_h:03d}h_GSM_SurfacePressure.png"
            fname = copy_png(src, report_dir, f"GSM FT={ft_h}h")
            if fname:
                collected_gsm[ft_h] = fname
        if run_ecm:
            src = output_dir / f"{init_str}_FT{ft_h:03d}h_ECM_SurfacePressure.png"
            fname = copy_png(src, report_dir, f"ECM FT={ft_h}h")
            if fname:
                collected_ecm[ft_h] = fname

    if not collected_gsm and not collected_ecm:
        print("エラー: コピーするPNGがありません。処理を中断します。")
        sys.exit(1)

    # ---- Step 3: Markdown 生成 ----
    i_year, i_month, i_day, i_hourZ = (
        int(init_str[0:4]), int(init_str[4:6]),
        int(init_str[6:8]), int(init_str[8:10])
    )
    dt_init = datetime(i_year, i_month, i_day, i_hourZ)
    dt_display = dt_init.strftime("%Y/%m/%d %HUTC")

    lines = [
        "# 地上気圧 GSM/ECMWF 比較レポート",
        "",
        f"**初期時刻**: {dt_display}",
        "",
        "---",
        "",
        "## 地上気圧・10m風・2m気温",
        "",
    ]

    for ft_h in sorted(set(collected_gsm) | set(collected_ecm)):
        g = collected_gsm.get(ft_h)
        e = collected_ecm.get(ft_h)
        valid_jst = dt_init + timedelta(hours=ft_h + 9)
        jst_label = f"{valid_jst.month}/{valid_jst.day} {valid_jst.hour}時JST"
        lines += [f"#### FT={ft_h}h ({jst_label})", ""]
        if g and e:
            lines += [
                "| GSM | ECMWF |",
                "|:---:|:---:|",
                f"| ![GSM FT={ft_h}h](./{g}) | ![ECMWF FT={ft_h}h](./{e}) |",
                "",
            ]
        elif g:
            lines += [f"![GSM FT={ft_h}h](./{g})", ""]
        else:
            lines += [f"![ECMWF FT={ft_h}h](./{e})", ""]

    md_name = f"srf_comparison_{ft_label}.md"
    md_path = report_dir / md_name
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nMDファイル生成: reports/{init_str}/{md_name}")

    # ---- --push 処理 ----
    if not args.push:
        print("\nGitHub push はスキップ（--push を付けると実行）")
    else:
        print("\n--- GitHub へアップロード ---")
        rel_path = f"reports/{init_str}"
        rc = run_git(f"add {rel_path}", str(script_dir))
        if rc != 0:
            print("エラー: git add 失敗")
            sys.exit(1)

        staged = subprocess.run("git diff --staged --quiet", shell=True, cwd=str(script_dir))
        if staged.returncode == 0:
            print("変更なし: 既にアップロード済み（コミット・プッシュをスキップ）")
        else:
            commit_msg = f"report: 地上気圧比較レポート {model_label} {ft_label} ({init_str})"
            rc = run_git(f'commit -m "{commit_msg}"', str(script_dir))
            if rc != 0:
                print("エラー: git commit 失敗")
                sys.exit(1)

            run_git("config http.postBuffer 524288000", str(script_dir))
            rc = run_git("push", str(script_dir))
            if rc != 0:
                print("push 失敗。30秒待ってリトライします...")
                import time
                time.sleep(30)
                rc = run_git("push", str(script_dir))
            if rc != 0:
                print("エラー: git push 失敗（手動で 'git push' を実行してください）")
                sys.exit(1)
            print("  push OK")

    print(f"\n{'='*55}")
    print(f" 完了")
    print(f" レポート: reports/{init_str}/{md_name}")
    print(f"{'='*55}")


if __name__ == "__main__":
    main()
