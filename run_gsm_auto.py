#!/usr/bin/env python
# coding: utf-8

# GSM 最新データ自動検索・ダウンロード・全GSM天気図一括生成スクリプト
# RISHサーバーを検索して最新のinit_timeを特定し、全GSMスクリプトを実行する。
# 20260412 上原政博
#
# 使用例:
#   python run_gsm_auto.py                    # 最新データでFT=0,12,24,36,48h（keyモード）
#   python run_gsm_auto.py --steps 5          # FT=0,6,12,18,24h（連続5枚、6h間隔）
#   python run_gsm_auto.py --init-time 2026041200  # 初期時刻を手動指定
#   python run_gsm_auto.py --init-time 2026041200 --steps 9  # 手動指定＋連続9枚

import os
import sys
import subprocess
import argparse
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path
from bs4 import BeautifulSoup

os.environ['PROJ_LIB'] = '/opt/anaconda3/envs/met_env_310/share/proj'

BASE_URL = "http://database.rish.kyoto-u.ac.jp/arch/jmadata/data/gpv/original"
HEADERS  = {"User-Agent": "Mozilla/5.0 (compatible; GSM-Downloader/1.0)"}

# keyモード: FT=0,12,24,36,48h（DDHH形式）
KEY_FTS_DDHH = [0, 12, 100, 112, 200]

# 実行するGSM系スクリプトとその説明
GSM_SCRIPTS = [
    ("GSM_tenkizu500hPa.py", "GSM 500hPa高度・渦度"),
    ("GSM_QVector850hPa.py", "GSM 850hPa Qベクター"),
    ("GSM_Jet300hPa.py",     "GSM 300hPa ジェット"),
    ("GSM_Instability.py",   "GSM 不安定域分布"),
    ("GSM_CrossSection.py",  "GSM 鉛直断面図"),
    ("GSM_fax57.py",         "GSM FAX57 500hPa気温・700hPa湿数"),
    ("GSM_fax78.py",         "GSM FAX78 850hPa気温・風・700hPa発散"),
    ("GSM_faxSrfPre.py",     "GSM 地上気圧・風・2m気温"),
    ("GSM_EPT850hPa.py",     "GSM 850hPa 相当温位・風"),
]


def find_latest_init_time():
    """
    RISHサーバーのディレクトリ一覧を確認し、
    最新の利用可能なGSM init_timeを検索して返す（YYYYMMDDHH形式）。
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    for days_back in range(4):
        d = now - timedelta(days=days_back)
        for hour in [12, 0]:
            candidate = d.replace(hour=hour, minute=0, second=0, microsecond=0)
            # データ公開まで初期時刻から約3時間かかるため、それ以前はスキップ
            if (now - candidate).total_seconds() < 3 * 3600:
                continue

            year, month, day = candidate.year, candidate.month, candidate.day
            dir_url = f"{BASE_URL}/{year}/{month:02d}/{day:02d}/"
            try:
                resp = requests.get(dir_url, headers=HEADERS, timeout=20)
                if resp.status_code != 200:
                    continue
                # FD0000ファイルの存在を確認
                init_str = f"{year:04d}{month:02d}{day:02d}{hour:02d}0000"
                target_fn = f"Z__C_RJTD_{init_str}_GSM_GPV_Rgl_FD0000_grib2.bin"
                soup = BeautifulSoup(resp.text, "html.parser")
                links = [a.get("href", "") for a in soup.find_all("a")]
                if target_fn in links:
                    return f"{year:04d}{month:02d}{day:02d}{hour:02d}"
            except requests.RequestException as e:
                print(f"  接続エラー ({dir_url}): {e}")
                continue

    return None


def ddhh_to_hours(ddhh):
    return (ddhh // 100) * 24 + (ddhh % 100)


def hours_to_ddhh(hours):
    return (hours // 24) * 100 + (hours % 24)


def run_one(script, label, init_time, ft_ddhh):
    """スクリプトを1FTぶん実行する。"""
    ft_h = ddhh_to_hours(ft_ddhh)
    print(f"  [FT={ft_h:3d}h]", end="  ", flush=True)
    result = subprocess.run(
        [sys.executable, script, init_time, f"{ft_ddhh:04d}", "1"],
        capture_output=False,
    )
    if result.returncode != 0:
        print(f"    ※ {label} FT={ft_h}h でエラー（スキップ）")


def parse_args():
    parser = argparse.ArgumentParser(
        description="GSM最新データを自動検索・ダウンロード・全GSM天気図を一括生成する",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python run_gsm_auto.py                     # 最新データ、FT=0,12,24,36,48h（keyモード）
  python run_gsm_auto.py --steps 5           # 最新データ、FT=0,6,12,18,24h（連続5枚）
  python run_gsm_auto.py --init-time 2026041200         # 初期時刻手動指定
  python run_gsm_auto.py --init-time 2026041200 --start-ft 0100 --steps 3  # FT=24,30,36h
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
        "--start-ft", type=str, default="0000",
        help="--steps 使用時の開始予報時間 DDHH形式（デフォルト: 0000）",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # スクリプトのあるディレクトリを作業ディレクトリに設定
    script_dir = Path(__file__).parent.resolve()
    os.chdir(script_dir)

    print("=" * 50)
    print("GSM 自動天気図生成")
    print("=" * 50)

    # init_time の決定
    if args.init_time:
        if len(args.init_time) != 10:
            print("エラー: --init-time は YYYYMMDDHH の10桁で指定してください")
            sys.exit(1)
        init_time = args.init_time
        print(f"初期時刻（手動指定）: {init_time} UTC")
    else:
        print("RISHサーバーで最新GSMデータを検索中...")
        init_time = find_latest_init_time()
        if not init_time:
            print("エラー: 利用可能なGSMデータが見つかりませんでした。")
            print("  --init-time オプションで初期時刻を手動指定してください。")
            sys.exit(1)
        print(f"最新の初期時刻: {init_time} UTC")

    # FTリストの決定
    if args.steps is not None:
        start_h   = ddhh_to_hours(int(args.start_ft))
        ft_ddhh_list = [hours_to_ddhh(start_h + i * 6) for i in range(args.steps)]
        ft_h_list    = [ddhh_to_hours(d) for d in ft_ddhh_list]
        mode_str = (f"連続{args.steps}枚（FT={ft_h_list[0]}〜{ft_h_list[-1]}h, 6h間隔）")
    else:
        ft_ddhh_list = KEY_FTS_DDHH
        ft_h_list    = [ddhh_to_hours(d) for d in ft_ddhh_list]
        mode_str = "keyモード（FT=0,12,24,36,48h）"

    print(f"モード    : {mode_str}")
    print(f"出力先    : {script_dir}/output/")
    print()

    # 各スクリプトを実行
    success_scripts = 0
    for script, label in GSM_SCRIPTS:
        print(f"---------- {label} ----------")
        for ft_ddhh in ft_ddhh_list:
            run_one(script, label, init_time, ft_ddhh)
        success_scripts += 1
        print()

    print("=" * 50)
    print(f"完了: {success_scripts}/{len(GSM_SCRIPTS)} スクリプト")
    print(f"出力先: {script_dir}/output/")
    print("=" * 50)


if __name__ == "__main__":
    main()
