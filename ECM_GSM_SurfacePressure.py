#!/usr/bin/env python
# coding: utf-8

# GSM / ECMWF / GFS 地上気圧天気図 比較レポートスクリプト
# 既存の GSM_faxSrfPre.py / ECM_SurfacePressure.py / GFS_SurfacePressure.py を実行し、
# 生成された PNG を reports/{init_str}/ にコピーして
# FTごとに横並びテーブルで表示する Markdown を生成する。
# --push で git push まで行う。
#
# 使用例:
#   python ECM_GSM_SurfacePressure.py 2026052712                          # FT=0h（GSM+ECM+GFS）
#   python ECM_GSM_SurfacePressure.py 2026052712 0000 3                   # FT=0,6,12h 3枚
#   python ECM_GSM_SurfacePressure.py 2026052712 0000 3 --interval 12     # 12h間隔 3枚
#   python ECM_GSM_SurfacePressure.py 2026052712 0000 12h                 # 12hプリセット
#   python ECM_GSM_SurfacePressure.py 2026052712 --gsm                    # GSMのみ FT=0h
#   python ECM_GSM_SurfacePressure.py 2026052712 --ecm                    # ECMWFのみ FT=0h
#   python ECM_GSM_SurfacePressure.py 2026052712 --gfs                    # GFSのみ FT=0h
#   python ECM_GSM_SurfacePressure.py 2026052712 0000 3 --push            # pushあり

import sys
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
import requests

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
        description="GSM/ECMWF/GFS 地上気圧天気図を FT ごとに横並び比較する Markdown を生成する",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python ECM_GSM_SurfacePressure.py 2026052712                          # FT=0h（GSM+ECM+GFS）
  python ECM_GSM_SurfacePressure.py 2026052712 0000 3                   # FT=0,6,12h 3枚
  python ECM_GSM_SurfacePressure.py 2026052712 0000 3 --interval 12     # 12h間隔 3枚
  python ECM_GSM_SurfacePressure.py 2026052712 0000 12h                 # 12hプリセット
  python ECM_GSM_SurfacePressure.py 2026052712 --gsm                    # GSMのみ FT=0h
  python ECM_GSM_SurfacePressure.py 2026052712 --ecm                    # ECMWFのみ FT=0h
  python ECM_GSM_SurfacePressure.py 2026052712 --gfs                    # GFSのみ FT=0h
  python ECM_GSM_SurfacePressure.py 2026052712 0000 3 --push            # pushあり

描画設定（固定値）:
  --area        108 156 5 45   東経108〜156°、北緯5〜45°（全モデル共通）
  ECM: --smooth-size 10 --wind-step 10
  GFS: --smooth-size 5  --wind-step 10
        """
    )
    parser.add_argument("init_time", type=str,
                        help="初期時刻 YYYYMMDDHH（UTC）")
    parser.add_argument("start_ft", type=str, nargs="?", default="0000",
                        help="開始予報時間 DDHH形式（デフォルト: 0000）")
    parser.add_argument("n_steps", type=str, nargs="?", default="1",
                        help=f"枚数（デフォルト: 1）またはプリセット名 [{preset_list}]")
    parser.add_argument("--interval", type=int, default=6,
                        help="FT間隔 時間数（デフォルト: 6）。プリセット指定時は無視される")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--gsm", action="store_true",
                            help="GSMのみ実行（デフォルトは全モデル）")
    mode_group.add_argument("--ecm", action="store_true",
                            help="ECMWFのみ実行（デフォルトは全モデル）")
    mode_group.add_argument("--gfs", action="store_true",
                            help="GFSのみ実行（デフォルトは全モデル）")
    parser.add_argument("--push", action="store_true",
                        help="GitHub へ git push する（省略時はローカル保存のみ）")

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


GSM_BASE_URL     = "http://database.rish.kyoto-u.ac.jp/arch/jmadata/data/gpv/original"
ECM_BASE_URL     = "https://data.ecmwf.int/forecasts"
GFS_NOMADS_PUB   = "https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod"
HTTP_HEADERS     = {"User-Agent": "Mozilla/5.0 (compatible; DataChecker/1.0)"}


def check_data_files(init_str, ft_list_h, run_gsm, run_ecm, run_gfs):
    """ローカルファイルを優先確認し、なければサーバー HEAD リクエストで存在確認する。"""
    script_dir = Path(__file__).parent.resolve()
    i_year  = int(init_str[0:4])
    i_month = int(init_str[4:6])
    i_day   = int(init_str[6:8])
    i_hourZ = int(init_str[8:10])
    ecm_sub = "oper" if i_hourZ in (0, 12) else "scda"
    date_str = f"{i_year:04d}{i_month:02d}{i_day:02d}"

    missing = []
    for ft_h in ft_list_h:
        if run_gsm:
            ft_ddhh = hours_to_ddhh(ft_h)
            fn    = f"Z__C_RJTD_{init_str}0000_GSM_GPV_Rgl_FD{ft_ddhh:04d}_grib2.bin"
            local = script_dir / "data_gsm" / fn
            if local.exists():
                print(f"  GSM FT={ft_h:3d}h: OK (ローカル)")
            else:
                url = f"{GSM_BASE_URL}/{i_year}/{i_month:02d}/{i_day:02d}/{fn}"
                try:
                    r = requests.head(url, headers=HTTP_HEADERS, timeout=15)
                    if r.status_code == 200:
                        print(f"  GSM FT={ft_h:3d}h: OK (サーバー)")
                    else:
                        print(f"  GSM FT={ft_h:3d}h: NG (HTTP {r.status_code})")
                        missing.append(f"    {url}")
                except requests.RequestException as e:
                    print(f"  GSM FT={ft_h:3d}h: NG (接続エラー: {e})")
                    missing.append(f"    {url}")

        if run_ecm:
            fn    = f"{init_str}0000-{ft_h}h-{ecm_sub}-fc.grib2"
            local = script_dir / "data" / "ecm" / fn
            if local.exists():
                print(f"  ECM FT={ft_h:3d}h: OK (ローカル)")
            else:
                url = (f"{ECM_BASE_URL}/{i_year:04d}{i_month:02d}{i_day:02d}"
                       f"/{i_hourZ:02d}z/ifs/0p25/{ecm_sub}/{fn}")
                try:
                    r = requests.head(url, headers=HTTP_HEADERS, timeout=15)
                    if r.status_code == 200:
                        print(f"  ECM FT={ft_h:3d}h: OK (サーバー)")
                    else:
                        print(f"  ECM FT={ft_h:3d}h: NG (HTTP {r.status_code})")
                        missing.append(f"    {url}")
                except requests.RequestException as e:
                    print(f"  ECM FT={ft_h:3d}h: NG (接続エラー: {e})")
                    missing.append(f"    {url}")

        if run_gfs:
            gfs_fn    = f"gfs.t{i_hourZ:02d}z.pgrb2.0p25.f{ft_h:03d}"
            local     = script_dir / "data" / "gfs" / f"gfs_{init_str}_f{ft_h:03d}_srf.grib2"
            if local.exists() and local.stat().st_size > 10_000:
                print(f"  GFS FT={ft_h:3d}h: OK (ローカル)")
            else:
                url = f"{GFS_NOMADS_PUB}/gfs.{date_str}/{i_hourZ:02d}/atmos/{gfs_fn}"
                try:
                    r = requests.head(url, headers=HTTP_HEADERS, timeout=15)
                    if r.status_code == 200:
                        print(f"  GFS FT={ft_h:3d}h: OK (サーバー)")
                    else:
                        print(f"  GFS FT={ft_h:3d}h: NG (HTTP {r.status_code})")
                        missing.append(f"    {url}")
                except requests.RequestException as e:
                    print(f"  GFS FT={ft_h:3d}h: NG (接続エラー: {e})")
                    missing.append(f"    {url}")

    if missing:
        print("\nエラー: 以下のファイルがサーバーに存在しません。処理を中止します。")
        for m in missing:
            print(m)
        return False
    return True


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

    # モデル選択: 単独指定があればそのモデルのみ、なければ全モデル
    run_gsm = args.gsm or (not args.ecm and not args.gfs)
    run_ecm = args.ecm or (not args.gsm and not args.gfs)
    run_gfs = args.gfs or (not args.gsm and not args.ecm)

    start_ddhh  = int(args.start_ft)
    start_hours = ddhh_to_hours(start_ddhh)

    if args.n_steps in PRESETS:
        n_steps  = PRESETS[args.n_steps]["n_steps"]
        interval = PRESETS[args.n_steps]["interval"]
    else:
        n_steps  = int(args.n_steps)
        interval = args.interval

    ft_end    = start_hours + (n_steps - 1) * interval
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

    active = []
    if run_gsm: active.append("GSM")
    if run_ecm: active.append("ECM")
    if run_gfs: active.append("GFS")
    model_label = "+".join(active)

    print("=" * 60)
    print(f" 地上気圧比較レポート [{model_label}]")
    print(f" 初期時刻: {init_str}  FT: {start_hours}〜{ft_end}h  {n_steps}枚  {interval}h間隔")
    print("=" * 60)

    # ---- Step 0: データファイル存在確認 ----
    print("\n--- Step 0: データファイル確認 ---")
    if not check_data_files(init_str, ft_list_h, run_gsm, run_ecm, run_gfs):
        sys.exit(1)
    print("  全ファイル確認OK")

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
        if run_gfs:
            ok = run_python("GFS_SurfacePressure.py",
                            f"{init_str} {ft_h} 1 --area 108 156 5 45 --smooth-size 5 --wind-step 10",
                            str(script_dir))
            if not ok:
                print(f"  警告: GFS_SurfacePressure.py FT={ft_h}h でエラーが発生しました")

    # ---- Step 2: PNG を reports/ にコピー ----
    print(f"\n--- Step 2: PNG を reports/{init_str}/ にコピー ---")
    collected_gsm = {}
    collected_ecm = {}
    collected_gfs = {}

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
        if run_gfs:
            src = output_dir / f"{init_str}_FT{ft_h:03d}h_GFS_SurfacePressure.png"
            fname = copy_png(src, report_dir, f"GFS FT={ft_h}h")
            if fname:
                collected_gfs[ft_h] = fname

    if not collected_gsm and not collected_ecm and not collected_gfs:
        print("エラー: コピーするPNGがありません。処理を中断します。")
        sys.exit(1)

    # ---- Step 3: Markdown 生成 ----
    i_year, i_month, i_day, i_hourZ = (
        int(init_str[0:4]), int(init_str[4:6]),
        int(init_str[6:8]), int(init_str[8:10])
    )
    dt_init    = datetime(i_year, i_month, i_day, i_hourZ)
    dt_display = dt_init.strftime("%Y/%m/%d %HUTC")

    lines = [
        "# 地上気圧 GSM/ECMWF/GFS 比較レポート",
        "",
        f"**初期時刻**: {dt_display}",
        "",
        "---",
        "",
        "## 地上気圧・10m風・2m気温",
        "",
    ]

    all_fts = sorted(set(collected_gsm) | set(collected_ecm) | set(collected_gfs))
    for ft_h in all_fts:
        g = collected_gsm.get(ft_h)
        e = collected_ecm.get(ft_h)
        f = collected_gfs.get(ft_h)
        valid_jst = dt_init + timedelta(hours=ft_h + 9)
        jst_label = f"{valid_jst.month}/{valid_jst.day} {valid_jst.hour}時JST"
        lines += [f"#### FT={ft_h}h ({jst_label})", ""]

        # 実際に揃っている画像のみ列として出す
        headers = []
        imgs    = []
        if g: headers.append("GSM");   imgs.append(f"![GSM FT={ft_h}h](./{g})")
        if e: headers.append("ECMWF"); imgs.append(f"![ECMWF FT={ft_h}h](./{e})")
        if f: headers.append("GFS");   imgs.append(f"![GFS FT={ft_h}h](./{f})")

        if len(headers) > 1:
            lines += [
                "| " + " | ".join(headers) + " |",
                "|" + "|".join([":---:"] * len(headers)) + "|",
                "| " + " | ".join(imgs) + " |",
                "",
            ]
        elif len(headers) == 1:
            lines += [imgs[0], ""]

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
