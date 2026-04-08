#!/usr/bin/env python
# coding: utf-8

# GSM 500hPa天気図（高度・相対渦度）描画スクリプト
# 元コード: 黒良さんのNote (https://note.com/rkurora/n/n200fdd8f1aa1)
# 修正: 引数対応・出力先対応 20260408上原政博

import os
os.environ['PROJ_LIB'] = '/opt/anaconda3/envs/met_env_310/share/proj'  # ★importの前に設定！

from pyproj import datadir, CRS
datadir.set_data_dir(os.environ['PROJ_LIB'])

import math
import pygrib
import xarray as xr
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import matplotlib.path as mpath
import cartopy.crs as ccrs
import datetime
import sys
import argparse
from pathlib import Path
import requests

import metpy.calc as mpcalc
from metpy.units import units
from scipy.ndimage import maximum_filter, minimum_filter  # 新形式に修正済み

# RISHサーバーのベースURL
BASE_URL = "http://database.rish.kyoto-u.ac.jp/arch/jmadata/data/gpv/original"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; GSM-Downloader/1.0)"}


def ensure_file(gr_path: str, gr_fn: str, year: int, month: int, day: int) -> bool:
    """
    データファイルが存在しない場合、RISHサーバーから自動ダウンロードする。

    Returns:
        成功時 True、失敗時 False
    """
    if os.path.exists(gr_path):
        return True

    print(f"データファイルが見つかりません: {gr_fn}")
    print(f"RISHサーバーからダウンロードを試みます...")

    url = f"{BASE_URL}/{year}/{month:02d}/{day:02d}/{gr_fn}"
    dest = Path(gr_path)
    dest.parent.mkdir(parents=True, exist_ok=True)

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
                        print(f"\r  {pct:.1f}% ({downloaded/(1024*1024):.1f}/{total/(1024*1024):.1f} MB)",
                              end="", flush=True)
            print()
        size_mb = dest.stat().st_size / (1024 * 1024)
        print(f"ダウンロード完了: {gr_fn} ({size_mb:.1f} MB)")
        return True
    except requests.HTTPError as e:
        print(f"\nダウンロード失敗（HTTP {e.response.status_code}）: {url}")
        if dest.exists():
            dest.unlink()
        return False
    except requests.RequestException as e:
        print(f"\nダウンロード失敗: {e}")
        if dest.exists():
            dest.unlink()
        return False


def parse_args():
    """コマンドライン引数を解析する"""
    parser = argparse.ArgumentParser(
        description='GSM GPV GRIB2データから500hPa天気図（高度・相対渦度）を描画する',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python kurora_tenkizu.py 2017121012          # 2017/12/10 12UTC 初期値
  python kurora_tenkizu.py 2017121012 0018     # FT18h（18時間後）
  python kurora_tenkizu.py 2017121012 0100     # FT24h（1日後）
  python kurora_tenkizu.py 2017121012 0000 500 # 500hPa（デフォルト）

引数説明:
  init_time   : 初期時刻 YYYYMMDDHH（UTC）例: 2017121012
  forecast_time: 予報時間 DDHH形式（DD=日数, HH=時間）例: 0000=FT0h, 0018=FT18h, 0100=FT24h
  level       : 気圧面 hPa（デフォルト: 500）
        """
    )
    parser.add_argument('init_time', type=str,
                        help='初期時刻 YYYYMMDDHH（UTC）例: 2017121012')
    parser.add_argument('forecast_time', type=str, nargs='?', default='0000',
                        help='予報時間 DDHH形式（デフォルト: 0000=初期値）')
    parser.add_argument('level', type=int, nargs='?', default=500,
                        help='気圧面 hPa（デフォルト: 500）')
    return parser.parse_args()


def ft_to_hours(ft_str):
    """DDHH形式の予報時間を時間数に変換する"""
    ft_int = int(ft_str)
    dd = ft_int // 100
    hh = ft_int % 100
    return dd * 24 + hh


def main():
    args = parse_args()

    # 引数を解析
    init_str = args.init_time
    if len(init_str) != 10:
        print(f"エラー: init_time は YYYYMMDDHH の10桁で指定してください（例: 2017121012）")
        sys.exit(1)

    i_year  = int(init_str[0:4])
    i_month = int(init_str[4:6])
    i_day   = int(init_str[6:8])
    i_hourZ = int(init_str[8:10])
    i_ft    = int(args.forecast_time)
    tagHp   = args.level

    # 予報時間（時間数）を計算
    ft_hours = ft_to_hours(args.forecast_time)

    # データ格納フォルダ
    data_fld = "./data_gsm/"

    # GRIB2ファイル名を構築
    gsm_fn_t = "Z__C_RJTD_{0:4d}{1:02d}{2:02d}{3:02d}0000_GSM_GPV_Rgl_FD{4:04d}_grib2.bin"
    gr_fn = gsm_fn_t.format(i_year, i_month, i_day, i_hourZ, i_ft)
    gr_path = data_fld + gr_fn

    # ファイルが存在しない場合は自動ダウンロード
    if not ensure_file(gr_path, gr_fn, i_year, i_month, i_day):
        print(f"エラー: データの取得に失敗しました。")
        sys.exit(1)

    print(f"データ読み込み: {gr_fn}")

    # データOpen
    grbs = pygrib.open(gr_path)

    # データ取得
    grbHt = grbs(shortName="gh", typeOfLevel='isobaricInhPa', level=tagHp)[0]
    grbWu = grbs(shortName="u",  typeOfLevel='isobaricInhPa', level=tagHp)[0]
    grbWv = grbs(shortName="v",  typeOfLevel='isobaricInhPa', level=tagHp)[0]

    grbs.close()

    # GPVの切り出し領域の指定：(lonW,latS)-(lonE,latN)の矩形
    latS = -20
    latN =  80
    lonW =  70
    lonE = 190

    # データ切り出し
    valHt, latHt, lonHt = grbHt.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)
    valWu, latWu, lonWu = grbWu.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)
    valWv, latWv, lonWv = grbWv.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)

    # xarrayデータセットを作成（渦度計算用）
    ds = xr.Dataset(
        {
            "Geopotential_height": (["lat", "lon"], valHt),
            "u_wind":              (["lat", "lon"], valWu),
            "v_wind":              (["lat", "lon"], valWv),
        },
        coords={
            "level": [tagHp],
            "lat":   latHt[:, 0],
            "lon":   lonHt[0, :],
            "time":  [grbHt.validDate],
        },
    )
    ds['Geopotential_height'].attrs['units'] = 'm'
    ds['u_wind'].attrs['units']  = 'm/s'
    ds['v_wind'].attrs['units']  = 'm/s'
    ds['level'].attrs['units']   = 'hPa'
    ds['lat'].attrs['units']     = 'degrees_north'
    ds['lon'].attrs['units']     = 'degrees_east'

    # 相対渦度を計算
    ds['vorticity'] = mpcalc.vorticity(ds['u_wind'], ds['v_wind'])

    # 図法指定（気象庁の数値予報資料と同じ図法）
    proj = ccrs.Stereographic(central_latitude=60, central_longitude=140)
    latlon_proj = ccrs.PlateCarree()

    # 地図の描画範囲
    areaAry = [108, 156, 17, 55]  # 極東

    # 等値線の間隔
    levels_ht  = np.arange(4800, 6000,  60)   # 高度 60m間隔（実線）
    levels_ht2 = np.arange(4800, 6000, 300)   # 高度 300m間隔（太線）
    levels_vr  = np.arange(-0.0002, 0.0002, 0.00004)  # 渦度 4e-5毎

    # 渦度のハッチ設定
    levels_h_vr = [0.0, 0.00008, 1.0]  # 0.0以上: 灰色、8e-5以上: 赤
    colors_h_vr = ['0.9', 'red']
    alpha_h_vr  = 0.3

    # 緯度・経度線の間隔
    dlon, dlat = 10, 10

    # タイトル文字列用
    dt_i   = grbHt.analDate
    dt_str = (dt_i.strftime("%H00UTC%d%b%Y")).upper()
    dt_str2 = dt_i.strftime("%Y%m%d%H")

    # 描画開始
    fig = plt.figure(figsize=(10, 8))
    plt.subplots_adjust(left=0, right=1, bottom=0.06, top=0.98)

    ax = fig.add_subplot(1, 1, 1, projection=proj)
    ax.set_extent(areaAry, latlon_proj)

    # 500hPa 相対渦度ハッチ（0.0以上: 灰色、8e-5以上: 赤）
    cn_relv_hatch2 = ax.contourf(
        ds['lon'], ds['lat'], ds['vorticity'],
        levels_h_vr, colors=colors_h_vr,
        alpha=alpha_h_vr, transform=latlon_proj
    )

    # 500hPa 相対渦度等値線（4e-5毎、負は破線）
    cn_relv = ax.contour(
        ds['lon'], ds['lat'], ds['vorticity'],
        levels_vr, colors='black', linewidths=1.0, transform=latlon_proj
    )

    # 500hPa 等高度線（60m毎、実線）
    cn_hgt = ax.contour(
        ds['lon'], ds['lat'], ds['Geopotential_height'],
        colors='black', linewidths=1.2, levels=levels_ht, transform=latlon_proj
    )
    ax.clabel(cn_hgt, levels_ht, fontsize=15, inline=True,
              inline_spacing=5, fmt='%i', rightside_up=True)

    # 500hPa 等高度線（300m毎、太線）
    cn_hgt2 = ax.contour(
        ds['lon'], ds['lat'], ds['Geopotential_height'],
        colors='black', linewidths=1.5, levels=levels_ht2, transform=latlon_proj
    )
    ax.clabel(cn_hgt2, fontsize=15, inline=True,
              inline_spacing=0, fmt='%i', rightside_up=True)

    # 5820gpm 高度線（茶色・一点鎖線）
    cn5820 = ax.contour(
        ds['lon'], ds['lat'], ds['Geopotential_height'],
        colors='brown', linestyles='dashdot',
        linewidths=1.2, levels=[5820], transform=latlon_proj
    )

    # 5400gpm 高度線（青色・一点鎖線）
    cn5400 = ax.contour(
        ds['lon'], ds['lat'], ds['Geopotential_height'],
        colors='blue', linestyles='dashdot',
        linewidths=1.2, levels=[5400], transform=latlon_proj
    )

    # 海岸線
    ax.coastlines(resolution='50m')

    # グリッド線
    xticks = np.arange(0, 360.1, dlon)
    yticks = np.arange(-90, 90.1, dlat)
    gl = ax.gridlines(crs=ccrs.PlateCarree(), draw_labels=False, linewidth=1, alpha=0.8)
    gl.xlocator = mticker.FixedLocator(xticks)
    gl.ylocator = mticker.FixedLocator(yticks)

    # タイトル
    fig.text(
        0.5, 0.01,
        f"GSM FT{ft_hours:d}h IT:{dt_str} {tagHp}hPa Height(m),VORT",
        ha='center', va='bottom', size=18
    )

    # 出力先ディレクトリを作成
    output_dir = "./output"
    os.makedirs(output_dir, exist_ok=True)

    # PNG出力
    out_fn = f"{output_dir}/{dt_str2}_FT{ft_hours:03d}h_{tagHp}hPa_Height_VORT.png"
    plt.savefig(out_fn, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"出力: {out_fn}")


if __name__ == "__main__":
    main()
