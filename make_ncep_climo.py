#!/usr/bin/env python
# coding: utf-8

# NCEP/NCAR 再解析 月別平年値（LTM）ダウンロードスクリプト
# NOAA PSL から 1991-2020 年の月別平年値 NetCDF（3ファイル・計 ~25 MB）を取得する
# 取得変数: hgt（高度）, uwnd（東西風）, vwnd（南北風）
# 取得後は GSM_PolarView.py の --climo オプションで偏差シェードに使用する
# 20260611 上原政博

import argparse
import sys
from pathlib import Path

import requests
import xarray as xr

BASE_URL = "https://downloads.psl.noaa.gov/Datasets/ncep.reanalysis/Monthlies/pressure"
HEADERS  = {"User-Agent": "Mozilla/5.0 (compatible; NCEP-Climo-DL/1.0)"}

LTM_FILES = [
    "hgt.mon.ltm.1991-2020.nc",
    "uwnd.mon.ltm.1991-2020.nc",
    "vwnd.mon.ltm.1991-2020.nc",
]


def download_file(url, dest_path, force=False):
    """1ファイルをダウンロードする。既存ファイルは force=True のときのみ上書き。"""
    if dest_path.exists() and dest_path.stat().st_size > 0 and not force:
        print(f"  スキップ（既存）: {dest_path.name}  "
              f"({dest_path.stat().st_size / 1048576:.1f} MB)")
        return True

    tmp = dest_path.with_suffix(dest_path.suffix + ".part")
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with requests.get(url, headers=HEADERS, stream=True, timeout=180) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            done  = 0
            with tmp.open("wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    f.write(chunk)
                    done += len(chunk)
                    if total:
                        print(f"\r  {done / total * 100:5.1f}%  "
                              f"({done / 1048576:.1f} / {total / 1048576:.1f} MB)  ",
                              end="", flush=True)
        print()
        tmp.replace(dest_path)
        print(f"  完了: {dest_path.name}  ({dest_path.stat().st_size / 1048576:.1f} MB)")
        return True

    except requests.HTTPError as e:
        if tmp.exists(): tmp.unlink()
        print(f"\n  失敗 HTTP {e.response.status_code}: {url}")
        return False
    except requests.RequestException as e:
        if tmp.exists(): tmp.unlink()
        print(f"\n  失敗: {e}")
        return False


def print_info(path):
    """ダウンロードしたファイルの変数・気圧面・時刻数を表示する"""
    try:
        ds = xr.open_dataset(path)
        # データ変数（座標変数を除く）を取得
        data_vars = [v for v in ds.data_vars
                     if v not in ("time_bnds", "climatology_bounds")]
        for vname in data_vars:
            da = ds[vname]
            lev = (da.coords.get("level")
                   or da.coords.get("pressure")
                   or da.coords.get("lev"))
            t   = da.coords.get("time")
            print(f"    変数: {vname}  shape: {tuple(da.shape)}")
            if lev is not None:
                print(f"    気圧面 ({len(lev)}層): {list(lev.values.astype(int))} hPa")
            if t is not None:
                print(f"    時刻数: {len(t)} ステップ（月別平年値 = 12か月）")
        ds.close()
    except Exception as e:
        print(f"    内容確認失敗: {e}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="NOAA PSL から NCEP/NCAR 月別平年値（LTM 1991-2020）を取得する",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python make_ncep_climo.py                       # 未取得ファイルのみダウンロード
  python make_ncep_climo.py --force               # 強制再ダウンロード
  python make_ncep_climo.py --output-dir ./climo  # 保存先を変更

出力先（デフォルト）: data/ncep_climo/
  hgt.mon.ltm.1991-2020.nc  （高度場、~8 MB）
  uwnd.mon.ltm.1991-2020.nc （東西風、~8 MB）
  vwnd.mon.ltm.1991-2020.nc （南北風、~8 MB）

データ仕様:
  ソース  : NCEP/NCAR Reanalysis (NOAA PSL)
  期間    : 1991-2020 年（WMO 標準平年値期間）
  解像度  : 2.5° 格子（144 × 73 点）
  気圧面  : 17 層（1000〜10 hPa、300/500 hPa 含む）
  変数名  : hgt [m], uwnd [m/s], vwnd [m/s]
  時刻軸  : 12 ステップ（1〜12 月の平年値）

実行環境（conda の場合）:
  conda activate met_env   # または met_env_310
  python make_jra55_climo.py
"""
    )
    parser.add_argument("--output-dir", default="./data/ncep_climo",
                        help="保存先ディレクトリ（デフォルト: ./data/ncep_climo）")
    parser.add_argument("--force", action="store_true",
                        help="既存ファイルがあっても再ダウンロードする")

    if any(a in sys.argv[1:] for a in ("?", "-?", "--?")):
        parser.print_help()
        sys.exit(0)

    return parser.parse_args()


def main():
    args  = parse_args()
    out_dir = Path(args.output_dir)

    print(f"保存先: {out_dir}")
    print(f"対象  : {', '.join(LTM_FILES)}")
    print()

    ok = 0
    for fname in LTM_FILES:
        url  = f"{BASE_URL}/{fname}"
        dest = out_dir / fname
        print(f"[{fname}]")
        if download_file(url, dest, force=args.force):
            print_info(dest)
            ok += 1
        print()

    print(f"完了: {ok}/{len(LTM_FILES)} ファイル → {out_dir}/")
    if ok == len(LTM_FILES):
        print("\nすべて取得済み。GSM_PolarView.py の --climo オプションで偏差図を描画できます。")


if __name__ == "__main__":
    main()
