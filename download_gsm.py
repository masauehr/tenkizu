#!/usr/bin/env python
# coding: utf-8

# GSM GPV GRIB2データ ダウンロードスクリプト
# データ提供元: 京都大学生存圏研究所 (RISH) データベース
# URL: http://database.rish.kyoto-u.ac.jp/arch/jmadata/data/gpv/original/
# 20260408 上原政博

import os
import sys
import argparse
import requests
from datetime import datetime, timedelta
from pathlib import Path
from bs4 import BeautifulSoup

# ダウンロード先ディレクトリ
DATA_DIR = "./data_gsm"

# RISHサーバーのベースURL
BASE_URL = "http://database.rish.kyoto-u.ac.jp/arch/jmadata/data/gpv/original"

# User-Agentヘッダー（接続リセット対策）
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; GSM-Downloader/1.0)"}

# GSM全球モデルのファイル名パターン
# 例: Z__C_RJTD_20171210120000_GSM_GPV_Rgl_FD0000_grib2.bin
GSM_FN_TEMPLATE = "Z__C_RJTD_{year:04d}{month:02d}{day:02d}{hour:02d}0000_GSM_GPV_Rgl_FD{ft:04d}_grib2.bin"

# 全球モデルの予報時間リスト（DDHH形式）
# FD0000（初期値）〜FD0600（6日後0時）まで
# 0〜72h: 6h間隔、72〜264h: 12h間隔
FT_LIST_6H  = [0, 6, 12, 18]  # 1日目（0-18h、6h間隔）
FT_LIST_DAY = list(range(100, 601, 12)) + \
              [d * 100 + h for d in range(1, 6) for h in [0, 12]] + \
              [600]


def build_ft_list():
    """
    GSM全球モデルの予報時間リスト（DDHH形式）を生成する。
    0〜72h: 6h間隔 → FD0000, 0006, 0012, 0018, 0100, 0106, 0112, 0118, ...
    84h以降: 12h間隔 → FD0200, 0212, 0300, ...
    """
    ft_list = []
    # 0〜72h（3日間）: 6h間隔
    for day in range(4):
        for hour in [0, 6, 12, 18]:
            ft_list.append(day * 100 + hour)
    # 84h〜264h（3.5〜11日）: 12h間隔
    for day in range(4, 12):
        for hour in [0, 12]:
            ddhh = day * 100 + hour
            if ddhh <= 1100:
                ft_list.append(ddhh)
    return sorted(set(ft_list))


def list_gsm_files(date: datetime, hour: int):
    """
    指定日・時刻のRISHサーバー上のGSMファイル一覧を取得する。

    Args:
        date: 対象日（datetime）
        hour: 初期時刻（0 or 12 UTC）

    Returns:
        ファイル名のリスト（GSM全球Rgl形式のみ）
    """
    url = f"{BASE_URL}/{date.year}/{date.month:02d}/{date.day:02d}/"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  サーバーへの接続に失敗しました: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    files = []
    init_str = f"{date.year:04d}{date.month:02d}{date.day:02d}{hour:02d}0000"
    for a in soup.find_all("a"):
        fn = a.get("href", "")
        # 全球モデル（Rgl）のみ対象
        if fn.startswith(f"Z__C_RJTD_{init_str}_GSM_GPV_Rgl_") and fn.endswith("_grib2.bin"):
            files.append(fn)
    return sorted(files)


def download_file(filename: str, date: datetime):
    """
    指定ファイルをRISHサーバーからダウンロードする。

    Args:
        filename: ダウンロードするファイル名
        date: 対象日（datetime、URL構築用）

    Returns:
        成功時: True、失敗時: False
    """
    url = f"{BASE_URL}/{date.year}/{date.month:02d}/{date.day:02d}/{filename}"
    dest = Path(DATA_DIR) / filename

    # 既存ファイルがあればスキップ
    if dest.exists():
        size_mb = dest.stat().st_size / (1024 * 1024)
        print(f"  スキップ（既存）: {filename} ({size_mb:.1f} MB)")
        return True

    print(f"  ダウンロード中: {filename}")
    try:
        with requests.get(url, headers=HEADERS, stream=True, timeout=120) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            downloaded = 0
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        pct = downloaded / total * 100
                        print(f"\r    {pct:.1f}% ({downloaded/(1024*1024):.1f}/{total/(1024*1024):.1f} MB)",
                              end="", flush=True)
            print()
        size_mb = dest.stat().st_size / (1024 * 1024)
        print(f"  完了: {filename} ({size_mb:.1f} MB)")
        return True
    except requests.RequestException as e:
        print(f"\n  ダウンロード失敗: {e}")
        if dest.exists():
            dest.unlink()  # 不完全なファイルを削除
        return False


def download_date(date: datetime, hour: int, ft_list=None):
    """
    指定日・時刻のGSMデータをダウンロードする。

    Args:
        date: 対象日（datetime）
        hour: 初期時刻（0 or 12 UTC）
        ft_list: ダウンロードするFT（DDHH形式）のリスト。Noneなら全て。

    Returns:
        ダウンロード成功件数
    """
    print(f"\n=== {date.strftime('%Y/%m/%d')} {hour:02d}UTC のGSMデータをダウンロード ===")

    # サーバー上のファイル一覧を取得
    server_files = list_gsm_files(date, hour)
    if not server_files:
        print(f"  対象ファイルが見つかりませんでした。")
        return 0

    print(f"  サーバー上のファイル数: {len(server_files)}")

    # ft_listが指定されている場合は絞り込む
    if ft_list is not None:
        init_str = f"{date.year:04d}{date.month:02d}{date.day:02d}{hour:02d}0000"
        target_files = []
        for ft in ft_list:
            fn = GSM_FN_TEMPLATE.format(
                year=date.year, month=date.month, day=date.day, hour=hour, ft=ft
            )
            if fn in server_files:
                target_files.append(fn)
        server_files = target_files
        print(f"  対象ファイル数（FT絞り込み後）: {len(server_files)}")

    # ダウンロード実行
    success_count = 0
    for fn in server_files:
        if download_file(fn, date):
            success_count += 1

    print(f"\n  完了: {success_count}/{len(server_files)} ファイル")
    return success_count


def main():
    parser = argparse.ArgumentParser(
        description='京都大学RISHサーバーからGSM GPV GRIB2データをダウンロードする',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python download_gsm.py                          # 最新の利用可能なデータを自動検索
  python download_gsm.py --date 20171210          # 指定日（00UTC・12UTC両方）
  python download_gsm.py --date 20171210 --hour 12 # 指定日・時刻
  python download_gsm.py --start 20171208 --end 20171210  # 期間指定
  python download_gsm.py --date 20171210 --ft 0000 0018 0100  # FT指定
        """
    )
    parser.add_argument('--date', type=str,
                        help='対象日 YYYYMMDD（省略時は最新を自動検索）')
    parser.add_argument('--hour', type=int, choices=[0, 12], default=None,
                        help='初期時刻 UTC（省略時は0と12の両方）')
    parser.add_argument('--start', type=str,
                        help='期間指定の開始日 YYYYMMDD（--end と組み合わせて使用）')
    parser.add_argument('--end', type=str,
                        help='期間指定の終了日 YYYYMMDD')
    parser.add_argument('--ft', type=str, nargs='+',
                        help='ダウンロードするFT（DDHH形式、省略時は全て）例: 0000 0012 0100')
    args = parser.parse_args()

    # ダウンロード先ディレクトリを作成
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)

    # FTリスト
    ft_list = [int(ft) for ft in args.ft] if args.ft else None

    # 時刻リスト
    hours = [args.hour] if args.hour is not None else [0, 12]

    # 対象日のリストを作成
    date_list = []

    if args.start and args.end:
        # 期間指定
        start = datetime.strptime(args.start, "%Y%m%d")
        end   = datetime.strptime(args.end,   "%Y%m%d")
        d = start
        while d <= end:
            date_list.append(d)
            d += timedelta(days=1)
    elif args.date:
        # 日付指定
        date_list.append(datetime.strptime(args.date, "%Y%m%d"))
    else:
        # 自動検索（最近7日間を遡る）
        print("最新の利用可能なデータを検索中...")
        today = datetime.utcnow()
        for delta in range(7):
            d = today - timedelta(days=delta)
            for h in hours:
                files = list_gsm_files(d, h)
                if files:
                    print(f"  見つかりました: {d.strftime('%Y/%m/%d')} {h:02d}UTC ({len(files)}ファイル)")
                    date_list.append(d)
                    break
            if date_list:
                break
        if not date_list:
            print("  利用可能なデータが見つかりませんでした。--date オプションで日付を指定してください。")
            sys.exit(1)

    # ダウンロード実行
    total_success = 0
    for date in date_list:
        for h in hours:
            total_success += download_date(date, h, ft_list)

    print(f"\n=== 全処理完了: 合計 {total_success} ファイル ===")
    print(f"保存先: {os.path.abspath(DATA_DIR)}")


if __name__ == "__main__":
    main()
