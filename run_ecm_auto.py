#!/usr/bin/env python
# coding: utf-8

# ECMWF 最新データ自動検索・ダウンロード・全ECM天気図一括生成スクリプト
# ECMWF Open Data サーバーを検索して最新のinit_timeを特定し、全ECMスクリプトを実行する。
# 20260412 上原政博
#
# 注意:
#   ECMWF Open Data は最新約5日分のみ無償で取得可能。
#   過去データは Copernicus CDS API（https://cds.climate.copernicus.eu）が必要。
#
# 使用例:
#   python run_ecm_auto.py                    # 最新データでFT=0,12,24,36,48h（keyモード）
#   python run_ecm_auto.py --steps 5          # FT=0,6,12,18,24h（連続5枚、6h間隔）
#   python run_ecm_auto.py --init-time 2026041200  # 初期時刻を手動指定
#   python run_ecm_auto.py --tcwv             # 地上気圧図に可降水量シェードを追加

import os
import sys
import subprocess
import argparse
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ['PROJ_LIB'] = '/opt/anaconda3/envs/met_env_310/share/proj'

ECM_BASE_URL = "https://data.ecmwf.int/forecasts"
HEADERS      = {"User-Agent": "Mozilla/5.0 (compatible; ECM-Downloader/1.0)"}

# keyモード: FT=0,12,24,36,48h（時間数）
KEY_FTS_H = [0, 12, 24, 36, 48]

# 実行するECM系スクリプトとその説明
ECM_SCRIPTS = [
    ("ECM_tenkizu500hPa.py",   "ECMWF 500hPa高度・渦度"),
    ("ECM_EPT850hPa.py",       "ECMWF 850hPa 相当温位・風"),
    ("ECM_Fax57.py",           "ECMWF FAX57 500hPa気温・700hPa湿数"),
    ("ECM_Fax78.py",           "ECMWF FAX78 850hPa気温・風・700hPa発散"),
    ("ECM_SurfacePressure.py", "ECMWF 地上気圧・風・2m気温"),
]


def find_latest_init_time():
    """
    ECMWF Open Dataサーバーへの HEAD リクエストで
    最新の利用可能な init_time を検索して返す（YYYYMMDDHH形式）。
    ECMWF Open Data は初期時刻から約4〜5時間後に公開される。
    最新5日分のみ利用可能。
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    for days_back in range(6):
        d = now - timedelta(days=days_back)
        for hour in [12, 0]:
            candidate = d.replace(hour=hour, minute=0, second=0, microsecond=0)
            # データ公開まで初期時刻から約4時間かかるため、それ以前はスキップ
            if (now - candidate).total_seconds() < 4 * 3600:
                continue

            year, month, day = candidate.year, candidate.month, candidate.day
            fn  = f"{year:04d}{month:02d}{day:02d}{hour:02d}0000-0h-oper-fc.grib2"
            url = f"{ECM_BASE_URL}/{year:04d}{month:02d}{day:02d}/{hour:02d}z/ifs/0p25/oper/{fn}"
            try:
                r = requests.head(url, headers=HEADERS, timeout=15, allow_redirects=True)
                if r.status_code == 200:
                    return f"{year:04d}{month:02d}{day:02d}{hour:02d}"
                # 404 以外のエラー（5xx等）は接続エラーとしてスキップ
                if r.status_code not in (404, 403):
                    print(f"  接続エラー (HTTP {r.status_code}): {url}")
            except requests.RequestException as e:
                print(f"  接続エラー: {e}")
                continue

    return None


def run_one(script, label, init_time, ft_h, extra_args=None):
    """スクリプトを1FTぶん実行する。"""
    print(f"  [FT={ft_h:3d}h]", end="  ", flush=True)
    cmd = [sys.executable, script, init_time, str(ft_h), "1"]
    if extra_args:
        cmd.extend(extra_args)
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        print(f"    ※ {label} FT={ft_h}h でエラー（スキップ）")


def parse_args():
    parser = argparse.ArgumentParser(
        description="ECMWF最新データを自動検索・ダウンロード・全ECM天気図を一括生成する",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python run_ecm_auto.py                     # 最新データ、FT=0,12,24,36,48h（keyモード）
  python run_ecm_auto.py --steps 5           # 最新データ、FT=0,6,12,18,24h（連続5枚）
  python run_ecm_auto.py --tcwv              # 地上気圧図に可降水量シェードを追加
  python run_ecm_auto.py --tp                # 地上気圧図に積算降水量シェードを追加（FT>0のみ有効）
  python run_ecm_auto.py --init-time 2026041200         # 初期時刻手動指定
  python run_ecm_auto.py --init-time 2026041200 --start-ft 24 --steps 3  # FT=24,30,36h
        """,
    )
    parser.add_argument(
        "--init-time", type=str, default=None,
        help="初期時刻 YYYYMMDDHH（省略時は自動検索）",
    )
    parser.add_argument(
        "--steps", type=int, default=None,
        help="連続枚数（6h間隔。省略時はkeyモード: FT=0,12,24,36,48h）",
    )
    parser.add_argument(
        "--start-ft", type=int, default=0,
        help="--steps 使用時の開始予報時間（時間数、デフォルト: 0）",
    )
    parser.add_argument(
        "--tcwv", action="store_true",
        help="ECM_SurfacePressure.py に --tcwv を渡す（可降水量シェード）",
    )
    parser.add_argument(
        "--tp", action="store_true",
        help="ECM_SurfacePressure.py に --tp を渡す（積算降水量シェード、FT>0のみ有効）",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # スクリプトのあるディレクトリを作業ディレクトリに設定
    script_dir = Path(__file__).parent.resolve()
    os.chdir(script_dir)

    print("=" * 50)
    print("ECMWF 自動天気図生成")
    print("  ※ ECMWF Open Data は最新約5日分のみ無償")
    print("=" * 50)

    # init_time の決定
    if args.init_time:
        if len(args.init_time) != 10:
            print("エラー: --init-time は YYYYMMDDHH の10桁で指定してください")
            sys.exit(1)
        init_time = args.init_time
        print(f"初期時刻（手動指定）: {init_time} UTC")
    else:
        print("ECMWF Open Dataサーバーで最新データを検索中...")
        init_time = find_latest_init_time()
        if not init_time:
            print("エラー: 利用可能なECMWFデータが見つかりませんでした。")
            print("  最新5日分のみ無償。過去データは --init-time 手動指定 + CDS API が必要です。")
            sys.exit(1)
        print(f"最新の初期時刻: {init_time} UTC")

    # FTリストの決定
    if args.steps is not None:
        ft_h_list = [args.start_ft + i * 6 for i in range(args.steps)]
        mode_str  = f"連続{args.steps}枚（FT={ft_h_list[0]}〜{ft_h_list[-1]}h, 6h間隔）"
    else:
        ft_h_list = KEY_FTS_H
        mode_str  = "keyモード（FT=0,12,24,36,48h）"

    # ECM_SurfacePressure.py への追加オプション
    srf_extra = []
    if args.tcwv:
        srf_extra.append("--tcwv")
    if args.tp:
        srf_extra.append("--tp")

    print(f"モード    : {mode_str}")
    if srf_extra:
        print(f"追加オプション: {' '.join(srf_extra)}（地上気圧図のみ）")
    print(f"出力先    : {script_dir}/output/")
    print()

    # 各スクリプトを実行
    success_scripts = 0
    for script, label in ECM_SCRIPTS:
        print(f"---------- {label} ----------")
        # ECM_SurfacePressure.py のみ追加オプションを渡す
        extra = srf_extra if script == "ECM_SurfacePressure.py" else None
        for ft_h in ft_h_list:
            # --tp は FT=0 には意味がないため警告を出してスキップ
            if "--tp" in (extra or []) and ft_h == 0:
                print(f"  [FT={ft_h:3d}h]  ※ --tp はFT=0では無効のためスキップ")
                continue
            run_one(script, label, init_time, ft_h, extra)
        success_scripts += 1
        print()

    print("=" * 50)
    print(f"完了: {success_scripts}/{len(ECM_SCRIPTS)} スクリプト")
    print(f"出力先: {script_dir}/output/")
    print("=" * 50)


if __name__ == "__main__":
    main()
