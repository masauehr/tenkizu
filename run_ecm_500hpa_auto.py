#!/usr/bin/env python3
# coding: utf-8

# ECMWF 500hPa高度・渦度 単体自動生成スクリプト
# ECMWF Open Dataサーバーで最新init_timeを自動検索して ECM_tenkizu500hPa.py を実行する。
# 20260413 上原政博
#
# 使用例:
#   python run_ecm_500hpa_auto.py                              # 最新データ、keyモード（FT=0,12,24,36,48h）
#   python run_ecm_500hpa_auto.py --steps 5                   # 最新データ、FT=0〜24h 連続5枚
#   python run_ecm_500hpa_auto.py --init-time 2026041200      # 初期時刻を手動指定
#   python run_ecm_500hpa_auto.py --init-time 2026041200 --start-ft 24 --steps 3  # FT=24,30,36h

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

KEY_FTS_H = [0, 12, 24, 36, 48]   # FT=0,12,24,36,48h（時間数）


def find_latest_init_time():
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for days_back in range(6):
        d = now - timedelta(days=days_back)
        for hour in [12, 0]:
            candidate = d.replace(hour=hour, minute=0, second=0, microsecond=0)
            if (now - candidate).total_seconds() < 4 * 3600:
                continue
            year, month, day = candidate.year, candidate.month, candidate.day
            fn  = f"{year:04d}{month:02d}{day:02d}{hour:02d}0000-0h-oper-fc.grib2"
            url = f"{ECM_BASE_URL}/{year:04d}{month:02d}{day:02d}/{hour:02d}z/ifs/0p25/oper/{fn}"
            try:
                r = requests.head(url, headers=HEADERS, timeout=15, allow_redirects=True)
                if r.status_code == 200:
                    return f"{year:04d}{month:02d}{day:02d}{hour:02d}"
                if r.status_code not in (404, 403):
                    print(f"  接続エラー (HTTP {r.status_code}): {url}")
            except requests.RequestException as e:
                print(f"  接続エラー: {e}")
    return None


def parse_args():
    parser = argparse.ArgumentParser(
        description="ECMWF 500hPa高度・渦度を自動取得・生成する",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python run_ecm_500hpa_auto.py                              # 最新データ、keyモード
  python run_ecm_500hpa_auto.py --steps 5                   # FT=0,6,12,18,24h 連続5枚
  python run_ecm_500hpa_auto.py --init-time 2026041200      # 初期時刻を手動指定
  python run_ecm_500hpa_auto.py --init-time 2026041200 --start-ft 24 --steps 3
        """,
    )
    parser.add_argument("--init-time",  type=str, default=None,
                        help="初期時刻 YYYYMMDDHH（省略時は自動検索）")
    parser.add_argument("--steps",      type=int, default=None,
                        help="連続枚数（6h間隔。省略時はkeyモード: FT=0,12,24,36,48h）")
    parser.add_argument("--start-ft",   type=int, default=0,
                        help="--steps 使用時の開始予報時間（時間数、デフォルト: 0）")
    return parser.parse_args()


def main():
    args = parse_args()
    script_dir = Path(__file__).parent.resolve()
    os.chdir(script_dir)

    print("=" * 50)
    print("ECMWF 500hPa高度・渦度 自動生成")
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

    print(f"モード  : {mode_str}")
    print(f"出力先  : {script_dir}/output/")
    print()

    print("---------- ECMWF 500hPa 高度・渦度 ----------")
    for ft_h in ft_h_list:
        print(f"  [FT={ft_h:3d}h]", end="  ", flush=True)
        result = subprocess.run(
            [sys.executable, "ECM_tenkizu500hPa.py", init_time, str(ft_h), "1"],
            capture_output=False,
        )
        if result.returncode != 0:
            print(f"    ※ FT={ft_h}h でエラー（スキップ）")

    print()
    print("=" * 50)
    print(f"完了  出力先: {script_dir}/output/")
    print("=" * 50)


if __name__ == "__main__":
    main()
