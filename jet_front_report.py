#!/usr/bin/env python
# coding: utf-8

# ジェット・前線解析レポート生成・GitHub アップロードスクリプト
# 上層風（GSM_100hPa）・鉛直断面（GSM_CrossSection）・
# 850hPa相当温位（GSM/ECM_EPT850hPa）・地上気圧（GSM_faxSrfPre / ECM_SurfacePressure）
# を組み合わせ、reports/{INIT_TIME}/ に PNG+MD を配置して git push する
#
# 使用例:
#   python jet_front_report.py 2026041200                    # GSMのみ FT=0h 1枚
#   python jet_front_report.py 2026041200 0000 5             # GSMのみ 5枚（6h間隔）
#   python jet_front_report.py 2026041200 0000 12h           # 12hプリセット（FT=0〜48h）
#   python jet_front_report.py 2026041200 0000 24h           # 24hプリセット（FT=0〜120h）
#   python jet_front_report.py 2026041200 0000 5 --interval 12   # 12h間隔 5枚
#   python jet_front_report.py 2026041200 --ecm              # GSM+ECM FT=0h 1枚
#   python jet_front_report.py 2026041200 --levels 100 50    # 上層風を100+50hPa
#   python jet_front_report.py 2026041200 --lat-s 45 --lat-e 25 --lon-s 125 --lon-e 135
#
# 作成: 20260428 上原政博

import os
import sys
import subprocess
import shutil
import argparse
from pathlib import Path
from datetime import datetime
import requests

# 時間プリセット
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
        description='ジェット・前線解析レポートを生成してGitHubにアップロードする',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python jet_front_report.py 2026041200                          # GSMのみ FT=0h 1枚
  python jet_front_report.py 2026041200 0000 5                   # GSMのみ 5枚（6h間隔）
  python jet_front_report.py 2026041200 0000 12h                 # 12hプリセット（FT=0〜48h）
  python jet_front_report.py 2026041200 0000 24h                 # 24hプリセット（FT=0〜120h）
  python jet_front_report.py 2026041200 0000 5 --interval 12     # 12h間隔 5枚
  python jet_front_report.py 2026041200 --ecm                    # GSM+ECM FT=0h 1枚
  python jet_front_report.py 2026041200 --levels 100 50          # 上層風を100+50hPa
  python jet_front_report.py 2026041200 0000 12h --ecm --levels 100 50
  python jet_front_report.py 2026041200 --lat-s 45 --lat-e 25 --lon-s 125 --lon-e 135
        """
    )
    parser.add_argument('init_time', type=str, help='初期時刻 YYYYMMDDHH（UTC）')
    parser.add_argument('start_ft',  type=str, nargs='?', default='0000',
                        help='開始予報時間 DDHH形式（デフォルト: 0000）')
    parser.add_argument('n_steps',   type=str, nargs='?', default='1',
                        help=f'作成する枚数（デフォルト: 1）またはプリセット名 [{preset_list}]')
    parser.add_argument('--interval', type=int, default=6,
                        help='FT間隔 時間数（デフォルト: 6）。プリセット指定時は無視される')
    parser.add_argument('--levels',  type=int, nargs='+', default=[100],
                        help='上層風の気圧面 hPa（複数指定可、デフォルト: 100）')
    parser.add_argument('--ecm',     action='store_true',
                        help='ECMWFも実行する（省略時はGSMのみ）')
    parser.add_argument('--push',    action='store_true',
                        help='GitHub へ git push する（省略時はローカル保存のみ）')
    # 鉛直断面の端点（GSM_CrossSection.py のデフォルトと合わせる）
    parser.add_argument('--lat-s',   type=float, default=45,
                        help='断面図 北端緯度（デフォルト: 45°N）')
    parser.add_argument('--lat-e',   type=float, default=25,
                        help='断面図 南端緯度（デフォルト: 25°N）')
    parser.add_argument('--lon-s',   type=float, default=130,
                        help='断面図 西端経度（デフォルト: 130°E）')
    parser.add_argument('--lon-e',   type=float, default=130,
                        help='断面図 東端経度（デフォルト: 130°E）')

    # ? / -? / --? でヘルプ表示
    if any(a in sys.argv[1:] for a in ('?', '-?', '--?')):
        parser.print_help()
        sys.exit(0)

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


GSM_BASE_URL = "http://database.rish.kyoto-u.ac.jp/arch/jmadata/data/gpv/original"
ECM_BASE_URL = "https://data.ecmwf.int/forecasts"
HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; DataChecker/1.0)"}


def check_data_files(init_str, ft_list_h, run_gsm, run_ecm):
    """各サーバーに必要なGRIB2ファイルが存在するか HEAD リクエストで確認する。"""
    i_year  = int(init_str[0:4])
    i_month = int(init_str[4:6])
    i_day   = int(init_str[6:8])
    i_hourZ = int(init_str[8:10])
    ecm_sub = "oper" if i_hourZ in (0, 12) else "scda"

    missing = []
    for ft_h in ft_list_h:
        if run_gsm:
            ft_ddhh = hours_to_ddhh(ft_h)
            fn  = f"Z__C_RJTD_{init_str}0000_GSM_GPV_Rgl_FD{ft_ddhh:04d}_grib2.bin"
            url = f"{GSM_BASE_URL}/{i_year}/{i_month:02d}/{i_day:02d}/{fn}"
            try:
                r = requests.head(url, headers=HTTP_HEADERS, timeout=15)
                if r.status_code == 200:
                    print(f"  GSM FT={ft_h:3d}h: OK")
                else:
                    print(f"  GSM FT={ft_h:3d}h: NG (HTTP {r.status_code})")
                    missing.append(f"    {url}")
            except requests.RequestException as e:
                print(f"  GSM FT={ft_h:3d}h: NG (接続エラー: {e})")
                missing.append(f"    {url}")

        if run_ecm:
            fn  = f"{init_str}0000-{ft_h}h-{ecm_sub}-fc.grib2"
            url = (f"{ECM_BASE_URL}/{i_year:04d}{i_month:02d}{i_day:02d}"
                   f"/{i_hourZ:02d}z/ifs/0p25/{ecm_sub}/{fn}")
            try:
                r = requests.head(url, headers=HTTP_HEADERS, timeout=15)
                if r.status_code == 200:
                    print(f"  ECM FT={ft_h:3d}h: OK")
                else:
                    print(f"  ECM FT={ft_h:3d}h: NG (HTTP {r.status_code})")
                    missing.append(f"    {url}")
            except requests.RequestException as e:
                print(f"  ECM FT={ft_h:3d}h: NG (接続エラー: {e})")
                missing.append(f"    {url}")

    if missing:
        print("\nエラー: 以下のファイルがサーバーに存在しません。処理を中止します。")
        for m in missing:
            print(m)
        return False
    return True


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
    raw_steps  = args.n_steps
    if raw_steps in PRESETS:
        interval = PRESETS[raw_steps]["interval"]
        n_steps  = PRESETS[raw_steps]["n_steps"]
    else:
        n_steps  = int(raw_steps)
        interval = args.interval

    start_ft_h = ddhh_to_hours(start_ddhh)
    end_ft_h   = start_ft_h + (n_steps - 1) * interval
    ft_list    = [start_ft_h + i * interval for i in range(n_steps)]

    script_dir = Path(__file__).parent.resolve()
    output_dir = script_dir / "output"
    report_dir = script_dir / "reports" / init_str
    report_dir.mkdir(parents=True, exist_ok=True)

    level_label = "+".join(f"{l}hPa" for l in levels)
    model_label = "GSM+ECM" if with_ecm else "GSMのみ"
    if n_steps == 1:
        ft_label = f"FT{start_ft_h}"
    elif interval == 6:
        ft_label = f"FT{start_ft_h}-{end_ft_h}"
    else:
        ft_label = f"FT{start_ft_h}-{end_ft_h}_{interval}h"

    # 断面図の端点ラベル
    cs_args = (f"--lat-s {args.lat_s} --lat-e {args.lat_e} "
               f"--lon-s {args.lon_s} --lon-e {args.lon_e}")
    if args.lon_s == args.lon_e:
        cs_label = f"{args.lat_s:.0f}°N〜{args.lat_e:.0f}°N / {args.lon_s:.0f}°E（経線断面）"
    else:
        cs_label = (f"{args.lat_s:.0f}°N,{args.lon_s:.0f}°E〜"
                    f"{args.lat_e:.0f}°N,{args.lon_e:.0f}°E")

    print(f"{'='*60}")
    print(f" ジェット・前線解析レポート [{model_label}] 上層風:{level_label}")
    print(f" 初期時刻: {init_str} UTC  開始FT: {start_ft_h}h  枚数: {n_steps}  間隔: {interval}h")
    print(f" 断面図: {cs_label}")
    print(f"{'='*60}\n")

    # ---- Step 0: データファイル確認 ----
    print("--- Step 0: データファイル確認 ---")
    if not check_data_files(init_str, ft_list, True, with_ecm):
        sys.exit(1)
    print("  全ファイル確認OK\n")

    # ---- FT ごとに 1 枚ずつ各スクリプトを実行 ----
    for ft_h in ft_list:
        ft_str = f"{hours_to_ddhh(ft_h):04d}"
        print(f"=== FT={ft_h}h ===")

        # 上層風
        for lev in levels:
            print(f"  --- GSM {lev}hPa 上層風 ---")
            ok = run_python(f"GSM_100hPa.py {init_str} {ft_str} 1 {lev}", script_dir)
            if not ok:
                print(f"  警告: GSM_100hPa.py (level={lev}) でエラーが発生しました")
            if with_ecm:
                print(f"  --- ECM {lev}hPa 上層風 ---")
                ok = run_python(f"ECM_100hPa.py {init_str} {ft_h} 1 {lev}", script_dir)
                if not ok:
                    print(f"  警告: ECM_100hPa.py (level={lev}) でエラーが発生しました")

        # 鉛直断面図
        print(f"  --- GSM 鉛直断面図 ---")
        ok = run_python(f"GSM_CrossSection.py {init_str} {ft_str} 1 {cs_args}", script_dir)
        if not ok:
            print("  警告: GSM_CrossSection.py でエラーが発生しました")

        # 850hPa 相当温位
        print(f"  --- GSM 850hPa 相当温位 ---")
        ok = run_python(f"GSM_EPT850hPa.py {init_str} {ft_str} 1", script_dir)
        if not ok:
            print("  警告: GSM_EPT850hPa.py でエラーが発生しました")
        if with_ecm:
            print(f"  --- ECM 850hPa 相当温位 ---")
            ok = run_python(f"ECM_EPT850hPa.py {init_str} {ft_h} 1", script_dir)
            if not ok:
                print("  警告: ECM_EPT850hPa.py でエラーが発生しました")

        # 地上気圧
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

    # 収集構造: section → ft_h → fname
    collected = {
        "upper_gsm":  {lev: {} for lev in levels},
        "upper_ecm":  {lev: {} for lev in levels},
        "cross":      {},
        "ept_gsm":    {},
        "ept_ecm":    {},
        "srf_gsm":    {},
        "srf_ecm":    {},
    }

    print(f"--- PNG を reports/{init_str}/ にコピー ---")
    for ft_h in ft_list:
        # 上層風
        for lev in levels:
            src = output_dir / f"{dt_str2}_FT{ft_h:03d}h_GSM_{lev}hPa_Height_Wind.png"
            fname = copy_png(src, report_dir, f"GSM {lev}hPa 上層風 FT={ft_h}h")
            if fname:
                collected["upper_gsm"][lev][ft_h] = fname

            if with_ecm:
                src = output_dir / f"{dt_str2}_FT{ft_h:03d}h_ECM_{lev}hPa_Height_Wind.png"
                fname = copy_png(src, report_dir, f"ECM {lev}hPa 上層風 FT={ft_h}h")
                if fname:
                    collected["upper_ecm"][lev][ft_h] = fname

        # 鉛直断面
        src = output_dir / f"{dt_str2}_FT{ft_h:03d}h_CrossSection.png"
        fname = copy_png(src, report_dir, f"断面図 FT={ft_h}h")
        if fname:
            collected["cross"][ft_h] = fname

        # 850hPa EPT
        src = output_dir / f"{dt_str2}_FT{ft_h:03d}h_GSM_850hPa_EPT.png"
        fname = copy_png(src, report_dir, f"GSM EPT850 FT={ft_h}h")
        if fname:
            collected["ept_gsm"][ft_h] = fname

        if with_ecm:
            src = output_dir / f"{dt_str2}_FT{ft_h:03d}h_ECM_850hPa_EPT.png"
            fname = copy_png(src, report_dir, f"ECM EPT850 FT={ft_h}h")
            if fname:
                collected["ept_ecm"][ft_h] = fname

        # 地上気圧
        src = output_dir / f"{dt_str2}_FT{ft_h:03d}h_GSM_SurfacePressure.png"
        fname = copy_png(src, report_dir, f"GSM 地上 FT={ft_h}h")
        if fname:
            collected["srf_gsm"][ft_h] = fname

        if with_ecm:
            src = output_dir / f"{dt_str2}_FT{ft_h:03d}h_ECM_SurfacePressure.png"
            fname = copy_png(src, report_dir, f"ECM 地上 FT={ft_h}h")
            if fname:
                collected["srf_ecm"][ft_h] = fname

    any_copied = any([
        any(collected["upper_gsm"][lev] for lev in levels),
        collected["cross"],
        collected["ept_gsm"],
        collected["srf_gsm"],
    ])
    if not any_copied:
        print("エラー: コピーするPNGがありません。処理を中断します。")
        sys.exit(1)

    # ---- Markdown レポート生成 ----
    dt_obj     = datetime(i_year, i_month, i_day, i_hourZ)
    dt_display = dt_obj.strftime("%Y/%m/%d %HUTC")

    lines = [
        "# ジェット・前線解析レポート",
        "",
        f"**初期時刻**: {dt_display}  **断面**: {cs_label}",
        "",
        "---",
        "",
    ]

    # 上層風
    lines += [f"## 上層風（{level_label}）", ""]
    for lev in levels:
        if collected["upper_gsm"][lev]:
            lines += [f"### GSM {lev}hPa", ""]
            for ft_h, fname in sorted(collected["upper_gsm"][lev].items()):
                lines += [f"#### FT={ft_h}h", "", f"![GSM {lev}hPa FT={ft_h}h](./{fname})", ""]
        if collected["upper_ecm"][lev]:
            lines += [f"### ECMWF {lev}hPa", ""]
            for ft_h, fname in sorted(collected["upper_ecm"][lev].items()):
                lines += [f"#### FT={ft_h}h", "", f"![ECM {lev}hPa FT={ft_h}h](./{fname})", ""]
    lines += ["---", ""]

    # 鉛直断面
    if collected["cross"]:
        lines += [f"## 鉛直断面図（{cs_label}）", ""]
        lines += ["*(GSM。ポテンシャル温位・相当温位・風・発散)*", ""]
        for ft_h, fname in sorted(collected["cross"].items()):
            lines += [
                f"### FT={ft_h}h",
                "",
                f"![断面図 FT={ft_h}h](./{fname})",
                "",
                "*カラー: 発散（正値が赤系、負値は青系）、"
                "等温位線（黒）、等相当温位線（赤）、断面に沿った等風速線（青）、風矢羽（黒）*",
                "",
            ]
        lines += ["---", ""]

    # 850hPa EPT
    lines += ["## 850hPa 相当温位・風矢羽", ""]
    if collected["ept_gsm"]:
        lines += ["### GSM", ""]
        for ft_h, fname in sorted(collected["ept_gsm"].items()):
            lines += [f"#### FT={ft_h}h", "", f"![GSM EPT850 FT={ft_h}h](./{fname})", ""]
    if collected["ept_ecm"]:
        lines += ["### ECMWF", ""]
        for ft_h, fname in sorted(collected["ept_ecm"].items()):
            lines += [f"#### FT={ft_h}h", "", f"![ECM EPT850 FT={ft_h}h](./{fname})", ""]
    lines += ["---", ""]

    # 地上気圧
    lines += ["## 地上気圧・10m風・2m気温", ""]
    if collected["srf_gsm"]:
        lines += ["### GSM", ""]
        for ft_h, fname in sorted(collected["srf_gsm"].items()):
            lines += [f"#### FT={ft_h}h", "", f"![GSM 地上 FT={ft_h}h](./{fname})", ""]
    if collected["srf_ecm"]:
        lines += ["### ECMWF", ""]
        for ft_h, fname in sorted(collected["srf_ecm"].items()):
            lines += [f"#### FT={ft_h}h", "", f"![ECM 地上 FT={ft_h}h](./{fname})", ""]
    lines += ["---", ""]

    md_name = f"jet_front_report_{ft_label}.md"
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
            commit_msg = f"report: ジェット・前線解析レポート追加 {ft_label} ({init_str})"
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
    print(f" レポート: reports/{init_str}/{md_name}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
