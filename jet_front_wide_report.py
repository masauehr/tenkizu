#!/usr/bin/env python
# coding: utf-8

# ジェット・前線解析（広域）生成・GitHub アップロードスクリプト
# jet_front_report.py の広域版: 上層風（GSM/ECM 100hPa）・850hPa相当温位のみ。
# 描画領域は通常版の中心を固定して東西2倍・南北1.5倍に拡大し、
# さらに北側1/3を南側に振り替えて南方向にシフトしている。
#   上層   : 通常[84,156,17,55] → ワイド[70,180,-12,30]（東西110°、南北42°）
#   850hPa : 通常[115,151,20,50] → ワイド[97,169,-2.5,42.5]（東西72°、南北45°）
#
# 使用例:
#   python jet_front_wide_report.py 2026041200                    # GSMのみ FT=0h 1枚
#   python jet_front_wide_report.py 2026041200 0000 5             # GSMのみ 5枚（6h間隔）
#   python jet_front_wide_report.py 2026041200 0000 12h           # 12hプリセット（FT=0〜48h）
#   python jet_front_wide_report.py 2026041200 0000 24h           # 24hプリセット（FT=0〜120h）
#   python jet_front_wide_report.py 2026041200 0000 5 --interval 12   # 12h間隔 5枚
#   python jet_front_wide_report.py 2026041200 --ecm              # GSM+ECM FT=0h 1枚
#   python jet_front_wide_report.py 2026041200 --levels 100 50    # 上層風を100+50hPa
#   python jet_front_wide_report.py 2026041200 0000 5 --ecm --levels 100 50
#   python jet_front_wide_report.py 2026041200 0000 3 --avg_steps 4   # FT0-18h, FT24-42h, FT48-66h 平均 3枚
#   ※ --avg_steps 使用時はプリセット・--interval は無効（6h固定）
#
# 作成: 20260501 上原政博（jet_front_report.py をベースに改良）

import os
import sys
import subprocess
import shutil
import argparse
from pathlib import Path
from datetime import datetime

# ワイド版描画領域 [lonW, lonE, latS, latN]
# 東西2倍・南北1.5倍（中心固定）→ さらに北側1/3を南側に振り替え
AREA_UPPER = [70, 180, -12, 30]  # 上層: lonW=70 lonE=180 latS=-12 latN=30
AREA_EPT   = [97, 169,  -2.5, 42.5]  # 850hPa: 東西72°、南北45°（南寄り）

# 時間プリセット（avg_steps == 1 のときのみ有効）
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
        description='ジェット・前線解析（広域）（上層+850hPa）を生成してGitHubにアップロードする',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python jet_front_wide_report.py 2026041200                         # GSMのみ FT=0h 1枚
  python jet_front_wide_report.py 2026041200 0000 5                  # GSMのみ 5枚（6h間隔）
  python jet_front_wide_report.py 2026041200 0000 12h                # 12hプリセット（FT=0〜48h）
  python jet_front_wide_report.py 2026041200 0000 24h                # 24hプリセット（FT=0〜120h）
  python jet_front_wide_report.py 2026041200 0000 5 --interval 12    # 12h間隔 5枚
  python jet_front_wide_report.py 2026041200 --ecm                   # GSM+ECM FT=0h 1枚
  python jet_front_wide_report.py 2026041200 --levels 100 50         # 上層風を100+50hPa
  python jet_front_wide_report.py 2026041200 0000 5 --ecm --levels 100 50
  python jet_front_wide_report.py 2026041200 0000 3 --avg_steps 4    # 平均モード（6h固定）
        """
    )
    parser.add_argument('init_time', type=str, help='初期時刻 YYYYMMDDHH（UTC）')
    parser.add_argument('start_ft',  type=str, nargs='?', default='0000',
                        help='開始予報時間 DDHH形式（デフォルト: 0000）')
    parser.add_argument('n_steps',   type=str, nargs='?', default='1',
                        help=f'作成する枚数（デフォルト: 1）またはプリセット名 [{preset_list}]。avg_steps使用時は数値のみ')
    parser.add_argument('--interval', type=int, default=6,
                        help='FT間隔 時間数（デフォルト: 6）。プリセット指定時・avg_steps使用時は無視される')
    parser.add_argument('--levels',  type=int, nargs='+', default=[100],
                        help='上層風の気圧面 hPa（複数指定可、デフォルト: 100）')
    parser.add_argument('--ecm',     action='store_true',
                        help='ECMWFも実行する（省略時はGSMのみ）')
    parser.add_argument('--push',      action='store_true',
                        help='GitHub へ git push する（省略時はローカル保存のみ）')
    parser.add_argument('--avg_steps', type=int, default=1,
                        help='平均するFT個数（1=平均なし、n指定時は6h間隔でn個を平均して1枚、デフォルト: 1）')
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


def area_str(area):
    """area リストをコマンドライン引数文字列に変換する"""
    return " ".join(str(v) for v in area)


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
    levels     = args.levels
    with_ecm   = args.ecm
    avg_steps  = args.avg_steps

    # avg_steps > 1 の場合はプリセット・--interval 無効（6h固定）
    raw_steps  = args.n_steps
    if avg_steps > 1:
        n_steps  = int(raw_steps)
        interval = 6
    elif raw_steps in PRESETS:
        interval = PRESETS[raw_steps]["interval"]
        n_steps  = PRESETS[raw_steps]["n_steps"]
    else:
        n_steps  = int(raw_steps)
        interval = args.interval

    start_ft_h = ddhh_to_hours(start_ddhh)
    end_ft_h   = start_ft_h + (n_steps - 1) * interval

    script_dir = Path(__file__).parent.resolve()
    output_dir = script_dir / "output"
    report_dir = script_dir / "reports" / (init_str + "-wide")
    report_dir.mkdir(parents=True, exist_ok=True)

    level_label = "+".join(f"{l}hPa" for l in levels)
    model_label = "GSM+ECM" if with_ecm else "GSMのみ"
    if avg_steps > 1:
        end_ft_h_avg = start_ft_h + (n_steps - 1) * 6 * avg_steps + (avg_steps - 1) * 6
        ft_label = f"FT{start_ft_h}-{end_ft_h_avg}_avg{avg_steps}"
    elif n_steps == 1:
        ft_label = f"FT{start_ft_h}"
    elif interval == 6:
        ft_label = f"FT{start_ft_h}-{end_ft_h}"
    else:
        ft_label = f"FT{start_ft_h}-{end_ft_h}_{interval}h"

    upper_area_arg = f"--area {area_str(AREA_UPPER)}"
    ept_area_arg   = f"--area {area_str(AREA_EPT)}"
    avg_arg        = f"--avg_steps {avg_steps}" if avg_steps > 1 else ""

    avg_info = f"  平均: {avg_steps}ステップ/枚" if avg_steps > 1 else f"  間隔: {interval}h"
    print(f"{'='*60}")
    print(f" ジェット・前線解析（広域） [{model_label}] 上層風:{level_label}")
    print(f" 初期時刻: {init_str} UTC  開始FT: {start_ft_h}h  枚数: {n_steps}{avg_info}")
    print(f" 上層域: {AREA_UPPER}  850hPa域: {AREA_EPT}")
    print(f"{'='*60}\n")

    # ---- スクリプト実行 ----
    if avg_steps > 1:
        # 平均モード: n_steps をまとめて渡す（6h固定）
        for lev in levels:
            print(f"--- GSM {lev}hPa 上層風 (ワイド) ---")
            ok = run_python(
                f"GSM_100hPa.py {init_str} {args.start_ft} {n_steps} {lev} {upper_area_arg} {avg_arg}",
                script_dir
            )
            if not ok:
                print(f"警告: GSM_100hPa.py (level={lev}) でエラーが発生しました")
            if with_ecm:
                print(f"\n--- ECM {lev}hPa 上層風 (ワイド) ---")
                ok = run_python(
                    f"ECM_100hPa.py {init_str} {start_ft_h} {n_steps} {lev} {upper_area_arg} {avg_arg}",
                    script_dir
                )
                if not ok:
                    print(f"警告: ECM_100hPa.py (level={lev}) でエラーが発生しました")
            print()

        print("--- GSM 850hPa 相当温位 (ワイド) ---")
        ok = run_python(
            f"GSM_EPT850hPa.py {init_str} {args.start_ft} {n_steps} {ept_area_arg} {avg_arg}",
            script_dir
        )
        if not ok:
            print("警告: GSM_EPT850hPa.py でエラーが発生しました")
        if with_ecm:
            print("\n--- ECM 850hPa 相当温位 (ワイド) ---")
            ok = run_python(
                f"ECM_EPT850hPa.py {init_str} {start_ft_h} {n_steps} {ept_area_arg} {avg_arg}",
                script_dir
            )
            if not ok:
                print("警告: ECM_EPT850hPa.py でエラーが発生しました")
        print()
    else:
        # 通常モード: FT ごとに 1 枚ずつ実行
        ft_list = [start_ft_h + i * interval for i in range(n_steps)]
        for ft_h in ft_list:
            ft_str = f"{hours_to_ddhh(ft_h):04d}"
            print(f"=== FT={ft_h}h ===")
            for lev in levels:
                print(f"  --- GSM {lev}hPa 上層風 (ワイド) ---")
                ok = run_python(
                    f"GSM_100hPa.py {init_str} {ft_str} 1 {lev} {upper_area_arg}",
                    script_dir
                )
                if not ok:
                    print(f"  警告: GSM_100hPa.py (level={lev}) でエラーが発生しました")
                if with_ecm:
                    print(f"  --- ECM {lev}hPa 上層風 (ワイド) ---")
                    ok = run_python(
                        f"ECM_100hPa.py {init_str} {ft_h} 1 {lev} {upper_area_arg}",
                        script_dir
                    )
                    if not ok:
                        print(f"  警告: ECM_100hPa.py (level={lev}) でエラーが発生しました")

            print(f"  --- GSM 850hPa 相当温位 (ワイド) ---")
            ok = run_python(
                f"GSM_EPT850hPa.py {init_str} {ft_str} 1 {ept_area_arg}",
                script_dir
            )
            if not ok:
                print("  警告: GSM_EPT850hPa.py でエラーが発生しました")
            if with_ecm:
                print(f"  --- ECM 850hPa 相当温位 (ワイド) ---")
                ok = run_python(
                    f"ECM_EPT850hPa.py {init_str} {ft_h} 1 {ept_area_arg}",
                    script_dir
                )
                if not ok:
                    print("  警告: ECM_EPT850hPa.py でエラーが発生しました")
            print()

    # ---- 生成PNG を reports/{init_str}-wide/ にコピー ----
    dt_str2 = f"{i_year:04d}{i_month:02d}{i_day:02d}{i_hourZ:02d}"

    # 平均モード: バッチ開始FTリスト、通常モード: 各FTリスト
    if avg_steps > 1:
        batch_starts = [start_ft_h + i * 6 * avg_steps for i in range(n_steps)]
    else:
        batch_starts = [start_ft_h + i * interval for i in range(n_steps)]

    collected = {
        "upper_gsm": {lev: {} for lev in levels},
        "upper_ecm": {lev: {} for lev in levels},
        "ept_gsm":   {},
        "ept_ecm":   {},
    }

    print(f"--- PNG を reports/{init_str}-wide/ にコピー ---")
    for ft_h in batch_starts:
        if avg_steps > 1:
            batch_end_h = ft_h + (avg_steps - 1) * 6
            avg_label   = f"FT{ft_h:03d}-{batch_end_h:03d}h_avg{avg_steps}"
        else:
            avg_label = None

        for lev in levels:
            if avg_label:
                src = output_dir / f"{dt_str2}_{avg_label}_GSM_{lev}hPa_Height_Wind.png"
                label = f"GSM {lev}hPa 上層風 {avg_label}"
            else:
                src = output_dir / f"{dt_str2}_FT{ft_h:03d}h_GSM_{lev}hPa_Height_Wind.png"
                label = f"GSM {lev}hPa 上層風 FT={ft_h}h"
            fname = copy_png(src, report_dir, label)
            if fname:
                collected["upper_gsm"][lev][ft_h] = fname

            if with_ecm:
                if avg_label:
                    src = output_dir / f"{dt_str2}_{avg_label}_ECM_{lev}hPa_Height_Wind.png"
                    label = f"ECM {lev}hPa 上層風 {avg_label}"
                else:
                    src = output_dir / f"{dt_str2}_FT{ft_h:03d}h_ECM_{lev}hPa_Height_Wind.png"
                    label = f"ECM {lev}hPa 上層風 FT={ft_h}h"
                fname = copy_png(src, report_dir, label)
                if fname:
                    collected["upper_ecm"][lev][ft_h] = fname

        if avg_label:
            src = output_dir / f"{dt_str2}_{avg_label}_GSM_850hPa_EPT.png"
            label = f"GSM EPT850 {avg_label}"
        else:
            src = output_dir / f"{dt_str2}_FT{ft_h:03d}h_GSM_850hPa_EPT.png"
            label = f"GSM EPT850 FT={ft_h}h"
        fname = copy_png(src, report_dir, label)
        if fname:
            collected["ept_gsm"][ft_h] = fname

        if with_ecm:
            if avg_label:
                src = output_dir / f"{dt_str2}_{avg_label}_ECM_850hPa_EPT.png"
                label = f"ECM EPT850 {avg_label}"
            else:
                src = output_dir / f"{dt_str2}_FT{ft_h:03d}h_ECM_850hPa_EPT.png"
                label = f"ECM EPT850 FT={ft_h}h"
            fname = copy_png(src, report_dir, label)
            if fname:
                collected["ept_ecm"][ft_h] = fname

    any_copied = any([
        any(collected["upper_gsm"][lev] for lev in levels),
        collected["ept_gsm"],
    ])
    if not any_copied:
        print("エラー: コピーするPNGがありません。処理を中断します。")
        sys.exit(1)

    # ---- Markdown レポート生成 ----
    dt_obj     = datetime(i_year, i_month, i_day, i_hourZ)
    dt_display = dt_obj.strftime("%Y/%m/%d %HUTC")

    lines = [
        "# ジェット・前線解析（広域）",
        "",
        f"**初期時刻**: {dt_display}",
        "",
        f"*(描画領域: 上層 lonW={AREA_UPPER[0]} lonE={AREA_UPPER[1]} latS={AREA_UPPER[2]} latN={AREA_UPPER[3]}、"
        f"850hPa lonW={AREA_EPT[0]} lonE={AREA_EPT[1]} latS={AREA_EPT[2]} latN={AREA_EPT[3]})*",
        "",
        "---",
        "",
    ]

    def ft_heading(ft_h):
        if avg_steps > 1:
            return f"FT={ft_h:03d}-{ft_h + (avg_steps - 1) * 6:03d}h (avg{avg_steps})"
        return f"FT={ft_h}h"

    # 上層風
    lines += [f"## 上層風（{level_label}）", ""]
    for lev in levels:
        if collected["upper_gsm"][lev]:
            lines += [f"### GSM {lev}hPa", ""]
            for ft_h, fname in sorted(collected["upper_gsm"][lev].items()):
                hdg = ft_heading(ft_h)
                lines += [f"#### {hdg}", "", f"![GSM {lev}hPa {hdg}](./{fname})", ""]
        if collected["upper_ecm"][lev]:
            lines += [f"### ECMWF {lev}hPa", ""]
            for ft_h, fname in sorted(collected["upper_ecm"][lev].items()):
                hdg = ft_heading(ft_h)
                lines += [f"#### {hdg}", "", f"![ECM {lev}hPa {hdg}](./{fname})", ""]
    lines += ["---", ""]

    # 850hPa EPT
    lines += ["## 850hPa 相当温位・風矢羽", ""]
    if collected["ept_gsm"]:
        lines += ["### GSM", ""]
        for ft_h, fname in sorted(collected["ept_gsm"].items()):
            hdg = ft_heading(ft_h)
            lines += [f"#### {hdg}", "", f"![GSM EPT850 {hdg}](./{fname})", ""]
    if collected["ept_ecm"]:
        lines += ["### ECMWF", ""]
        for ft_h, fname in sorted(collected["ept_ecm"].items()):
            hdg = ft_heading(ft_h)
            lines += [f"#### {hdg}", "", f"![ECM EPT850 {hdg}](./{fname})", ""]
    lines += ["---", ""]

    md_name = f"jet_front_wide_report_{ft_label}.md"
    md_path = report_dir / md_name
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nMDファイル生成: reports/{init_str}-wide/{md_name}")

    # ---- git add → commit → push（--push 指定時のみ）----
    if not args.push:
        print("\nGitHub push はスキップ（--push を付けると実行）")
    else:
        print("\n--- GitHub へアップロード ---")
        rel_path = f"reports/{init_str}-wide"

        rc = run_git(f"add {rel_path}", script_dir)
        if rc != 0:
            print("エラー: git add 失敗")
            sys.exit(1)

        staged = subprocess.run("git diff --staged --quiet", shell=True, cwd=script_dir)
        if staged.returncode == 0:
            print("変更なし: 既にアップロード済みです（コミット・プッシュをスキップ）")
        else:
            commit_msg = f"report: ジェット・前線解析（広域）追加 {ft_label} ({init_str})"
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

    print(f"\n{'='*60}")
    print(f" 完了")
    print(f" レポート: reports/{init_str}-wide/{md_name}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
