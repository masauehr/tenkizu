#!/usr/bin/env python
# coding: utf-8

# 総観天気図レポート生成・GitHub アップロードスクリプト
# GSM の Jet300hPa・Fax57（500/700hPa）・Fax78（700/850hPa）・
# EPT850hPa・地上気圧 を組み合わせ、
# reports/{INIT_TIME}/ に PNG+MD を配置して git push する
#
# 使用例:
#   python synop_report.py 2026041200                            # FT=0h 1枚（全種別）
#   python synop_report.py 2026041200 0000 5                     # FT=0〜24h 5枚（6h間隔）
#   python synop_report.py 2026041200 0000 5 --interval 12       # FT=0〜48h 5枚（12h間隔）
#   python synop_report.py 2026041200 --charts jet fax57          # jet と fax57 のみ
#   python synop_report.py 2026041200 0000 5 --ecm --charts ept srf
#
# 指定可能な --charts:
#   jet   … GSM Jet 300hPa（Isotach・非地衡風・高度）
#   fax57 … GSM/ECM 500/700hPa（等高度線・渦度・風）
#   fax78 … GSM/ECM 700/850hPa（等高度線・相当温位・風）
#   ept   … GSM/ECM 850hPa 相当温位・風矢羽
#   srf   … GSM/ECM 地上気圧・10m風・2m気温
#
# 作成: 20260428 上原政博

import os
import sys
import subprocess
import shutil
import argparse
from pathlib import Path
from datetime import datetime

ALL_CHARTS = ["jet", "fax57", "fax78", "ept", "srf"]

# 時間プリセット: n_steps の位置引数に名前で指定する
PRESETS = {
    "12h": {"interval": 12, "n_steps": 5},   # FT=0,12,24,36,48h
    "24h": {"interval": 24, "n_steps": 6},   # FT=0,24,48,72,96,120h
}


def ddhh_to_hours(ddhh):
    return (ddhh // 100) * 24 + (ddhh % 100)


def hours_to_ddhh(h):
    return (h // 24) * 100 + (h % 24)


def parse_args():
    preset_list = ", ".join(f"{k}（{v['interval']}h間隔×{v['n_steps']}枚）" for k, v in PRESETS.items())
    parser = argparse.ArgumentParser(
        description='総観天気図レポートを生成してGitHubにアップロードする',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python synop_report.py 2026041200                           # FT=0h 1枚（全種別）
  python synop_report.py 2026041200 0000 5                    # FT=0〜24h 5枚（6h間隔）
  python synop_report.py 2026041200 0000 12h                  # 12hプリセット（FT=0〜48h 12h間隔）
  python synop_report.py 2026041200 0000 24h                  # 24hプリセット（FT=0〜120h 24h間隔）
  python synop_report.py 2026041200 0000 5 --interval 12      # FT=0〜48h 5枚（12h間隔）
  python synop_report.py 2026041200 --charts jet fax57        # jet と fax57 のみ
  python synop_report.py 2026041200 0000 12h --ecm --charts ept srf
        """
    )
    parser.add_argument('init_time',   type=str, help='初期時刻 YYYYMMDDHH（UTC）')
    parser.add_argument('start_ft',    type=str, nargs='?', default='0000',
                        help='開始予報時間 DDHH形式（デフォルト: 0000）')
    parser.add_argument('n_steps',     type=str, nargs='?', default='1',
                        help=f'作成する枚数（デフォルト: 1）またはプリセット名 [{preset_list}]')
    parser.add_argument('--interval',  type=int, default=6,
                        help='FT間隔 時間数（デフォルト: 6）。プリセット指定時は無視される')
    parser.add_argument('--charts',    type=str, nargs='+', default=None,
                        choices=ALL_CHARTS, metavar='CHART',
                        help=f'描画する種別（複数指定可、デフォルト: 全て）。選択肢: {ALL_CHARTS}')
    parser.add_argument('--ecm',       action='store_true',
                        help='ECMWFも実行する（省略時はGSMのみ。Jetは常にGSMのみ）')
    parser.add_argument('--push',      action='store_true',
                        help='GitHub へ git push する（省略時はローカル保存のみ）')
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


def copy_png(src, report_dir, label):
    if src.exists():
        dst = report_dir / src.name
        shutil.copy2(src, dst)
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

    i_year  = int(init_str[0:4])
    i_month = int(init_str[4:6])
    i_day   = int(init_str[6:8])
    i_hourZ = int(init_str[8:10])

    start_ddhh = int(args.start_ft)
    charts     = args.charts if args.charts is not None else ALL_CHARTS
    raw_steps  = args.n_steps
    if raw_steps in PRESETS:
        interval = PRESETS[raw_steps]["interval"]
        n_steps  = PRESETS[raw_steps]["n_steps"]
    else:
        n_steps  = int(raw_steps)
        interval = args.interval
    start_ft_h = ddhh_to_hours(start_ddhh)
    end_ft_h   = start_ft_h + (n_steps - 1) * interval
    if n_steps == 1:
        ft_label = f"FT{start_ft_h}"
    elif interval == 6:
        ft_label = f"FT{start_ft_h}-{end_ft_h}"
    else:
        ft_label = f"FT{start_ft_h}-{end_ft_h}_{interval}h"
    with_ecm   = args.ecm

    script_dir = Path(__file__).parent.resolve()
    output_dir = script_dir / "output"
    report_dir = script_dir / "reports" / init_str
    report_dir.mkdir(parents=True, exist_ok=True)

    model_label = "GSM+ECM" if with_ecm else "GSMのみ"
    chart_label = "+".join(charts)

    print(f"{'='*60}")
    print(f" 総観天気図レポート生成 [{model_label}]")
    print(f" 初期時刻: {init_str} UTC  開始FT: {start_ft_h}h  枚数: {n_steps}  間隔: {interval}h")
    print(f" 種別: {chart_label}")
    print(f"{'='*60}\n")

    # ---- FT ごとに 1 枚ずつ各スクリプトを実行 ----
    ft_list = [start_ft_h + i * interval for i in range(n_steps)]

    for ft_h in ft_list:
        ft_str = f"{hours_to_ddhh(ft_h):04d}"
        print(f"=== FT={ft_h}h ===")

        if "jet" in charts:
            print(f"  --- GSM Jet 300hPa ---")
            ok = run_python(f"GSM_Jet300hPa.py {init_str} {ft_str} 1", script_dir)
            if not ok:
                print("  警告: GSM_Jet300hPa.py でエラーが発生しました")

        if "fax57" in charts:
            print(f"  --- GSM Fax57 (500/700hPa) ---")
            ok = run_python(f"GSM_fax57.py {init_str} {ft_str} 1", script_dir)
            if not ok:
                print("  警告: GSM_fax57.py でエラーが発生しました")
            if with_ecm:
                print(f"  --- ECM Fax57 (500/700hPa) ---")
                ok = run_python(f"ECM_Fax57.py {init_str} {ft_h} 1", script_dir)
                if not ok:
                    print("  警告: ECM_Fax57.py でエラーが発生しました")

        if "fax78" in charts:
            print(f"  --- GSM Fax78 (700/850hPa) ---")
            ok = run_python(f"GSM_fax78.py {init_str} {ft_str} 1", script_dir)
            if not ok:
                print("  警告: GSM_fax78.py でエラーが発生しました")
            if with_ecm:
                print(f"  --- ECM Fax78 (700/850hPa) ---")
                ok = run_python(f"ECM_Fax78.py {init_str} {ft_h} 1", script_dir)
                if not ok:
                    print("  警告: ECM_Fax78.py でエラーが発生しました")

        if "ept" in charts:
            print(f"  --- GSM 850hPa 相当温位 ---")
            ok = run_python(f"GSM_EPT850hPa.py {init_str} {ft_str} 1", script_dir)
            if not ok:
                print("  警告: GSM_EPT850hPa.py でエラーが発生しました")
            if with_ecm:
                print(f"  --- ECM 850hPa 相当温位 ---")
                ok = run_python(f"ECM_EPT850hPa.py {init_str} {ft_h} 1", script_dir)
                if not ok:
                    print("  警告: ECM_EPT850hPa.py でエラーが発生しました")

        if "srf" in charts:
            print(f"  --- GSM 地上気圧 ---")
            ok = run_python(f"GSM_faxSrfPre.py {init_str} {ft_str} 1", script_dir)
            if not ok:
                print("  警告: GSM_faxSrfPre.py でエラーが発生しました")
            if with_ecm:
                print(f"  --- ECM 地上気圧 ---")
                ok = run_python(f"ECM_SurfacePressure.py {init_str} {ft_h} 1", script_dir)
                if not ok:
                    print("  警告: ECM_SurfacePressure.py でエラーが発生しました")

        print()

    # ---- 生成PNG を reports/ にコピー ----
    dt_str2 = f"{i_year:04d}{i_month:02d}{i_day:02d}{i_hourZ:02d}"

    collected = {
        "jet":       {},
        "ecm_jet":   {},
        "fax57":     {},
        "ecm_fax57": {},
        "fax78":     {},
        "ecm_fax78": {},
        "ept":       {},
        "ecm_ept":   {},
        "srf":       {},
        "ecm_srf":   {},
    }

    print(f"--- PNG を reports/{init_str}/ にコピー ---")
    for ft_h in ft_list:
        if "jet" in charts:
            src = output_dir / f"{dt_str2}_FT{ft_h:03d}h_300hPa_Jet.png"
            fname = copy_png(src, report_dir, f"Jet300 FT={ft_h}h")
            if fname:
                collected["jet"][ft_h] = fname

        if "fax57" in charts:
            src = output_dir / f"{dt_str2}_FT{ft_h:03d}h_GSM_Fax57.png"
            fname = copy_png(src, report_dir, f"GSM Fax57 FT={ft_h}h")
            if fname:
                collected["fax57"][ft_h] = fname
            if with_ecm:
                src = output_dir / f"{dt_str2}_FT{ft_h:03d}h_ECM_Fax57.png"
                fname = copy_png(src, report_dir, f"ECM Fax57 FT={ft_h}h")
                if fname:
                    collected["ecm_fax57"][ft_h] = fname

        if "fax78" in charts:
            src = output_dir / f"{dt_str2}_FT{ft_h:03d}h_GSM_Fax78.png"
            fname = copy_png(src, report_dir, f"GSM Fax78 FT={ft_h}h")
            if fname:
                collected["fax78"][ft_h] = fname
            if with_ecm:
                src = output_dir / f"{dt_str2}_FT{ft_h:03d}h_ECM_Fax78.png"
                fname = copy_png(src, report_dir, f"ECM Fax78 FT={ft_h}h")
                if fname:
                    collected["ecm_fax78"][ft_h] = fname

        if "ept" in charts:
            src = output_dir / f"{dt_str2}_FT{ft_h:03d}h_GSM_850hPa_EPT.png"
            fname = copy_png(src, report_dir, f"GSM EPT850 FT={ft_h}h")
            if fname:
                collected["ept"][ft_h] = fname
            if with_ecm:
                src = output_dir / f"{dt_str2}_FT{ft_h:03d}h_ECM_850hPa_EPT.png"
                fname = copy_png(src, report_dir, f"ECM EPT850 FT={ft_h}h")
                if fname:
                    collected["ecm_ept"][ft_h] = fname

        if "srf" in charts:
            src = output_dir / f"{dt_str2}_FT{ft_h:03d}h_GSM_SurfacePressure.png"
            fname = copy_png(src, report_dir, f"GSM 地上 FT={ft_h}h")
            if fname:
                collected["srf"][ft_h] = fname
            if with_ecm:
                src = output_dir / f"{dt_str2}_FT{ft_h:03d}h_ECM_SurfacePressure.png"
                fname = copy_png(src, report_dir, f"ECM 地上 FT={ft_h}h")
                if fname:
                    collected["ecm_srf"][ft_h] = fname

    any_copied = any(collected[k] for k in collected)
    if not any_copied:
        print("エラー: コピーするPNGがありません。処理を中断します。")
        sys.exit(1)

    # ---- Markdown レポート生成 ----
    dt_obj     = datetime(i_year, i_month, i_day, i_hourZ)
    dt_display = dt_obj.strftime("%Y/%m/%d %HUTC")

    lines = [
        "# 総観天気図レポート",
        "",
        f"**初期時刻**: {dt_display}",
        "",
        "---",
        "",
    ]

    # Jet 300hPa（GSM: Isotach+非地衡風, ECM: 高度+風矢羽）
    if collected["jet"] or collected["ecm_jet"]:
        lines += ["## Jet 300hPa", ""]
        if collected["jet"]:
            lines += ["### GSM（Isotach・非地衡風・高度）", ""]
            for ft_h, fname in sorted(collected["jet"].items()):
                lines += [f"#### FT={ft_h}h", "", f"![GSM Jet 300hPa FT={ft_h}h](./{fname})", ""]
        if collected["ecm_jet"]:
            lines += ["### ECMWF（高度・風矢羽）", ""]
            for ft_h, fname in sorted(collected["ecm_jet"].items()):
                lines += [f"#### FT={ft_h}h", "", f"![ECM 300hPa FT={ft_h}h](./{fname})", ""]
        lines += ["---", ""]

    # GSM/ECM を並べて表示するセクション
    chart_sections = [
        ("fax57",     "ecm_fax57", "500/700hPa（等高度線・渦度・風）"),
        ("fax78",     "ecm_fax78", "700/850hPa（等高度線・相当温位・風）"),
        ("ept",       "ecm_ept",   "850hPa 相当温位・風矢羽"),
        ("srf",       "ecm_srf",   "地上気圧・10m風・2m気温"),
    ]
    for gsm_key, ecm_key, title in chart_sections:
        if collected[gsm_key] or collected[ecm_key]:
            lines += [f"## {title}", ""]
            if collected[gsm_key]:
                lines += ["### GSM", ""]
                for ft_h, fname in sorted(collected[gsm_key].items()):
                    lines += [f"#### FT={ft_h}h", "", f"![GSM {title} FT={ft_h}h](./{fname})", ""]
            if collected[ecm_key]:
                lines += ["### ECMWF", ""]
                for ft_h, fname in sorted(collected[ecm_key].items()):
                    lines += [f"#### FT={ft_h}h", "", f"![ECM {title} FT={ft_h}h](./{fname})", ""]
            lines += ["---", ""]

    md_name = f"synop_report_{ft_label}.md"
    md_path = report_dir / md_name
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nMDファイル生成: reports/{init_str}/{md_name}")

    # ---- git add → commit → push（--push 指定時のみ）----
    if not args.push:
        print("\nGitHub push はスキップ（--push を付けると実行）")
    else:
        print("\n--- GitHub へアップロード ---")
        rel_path = f"reports/{init_str}"

        rc = run_git(f"add {rel_path}", script_dir)
        if rc != 0:
            print("エラー: git add 失敗")
            sys.exit(1)

        staged = subprocess.run("git diff --staged --quiet", shell=True, cwd=script_dir)
        if staged.returncode == 0:
            print("変更なし: 既にアップロード済みです（コミット・プッシュをスキップ）")
        else:
            commit_msg = f"report: 総観天気図レポート追加 {chart_label} {ft_label} ({init_str})"
            rc = run_git(f'commit -m "{commit_msg}"', script_dir)
            if rc != 0:
                print("エラー: git commit 失敗")
                sys.exit(1)

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
    print(f" レポート: reports/{init_str}/{md_name}")
    print(f"{'='*55}")


if __name__ == "__main__":
    main()
