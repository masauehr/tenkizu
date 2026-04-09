#!/usr/bin/env python
# coding: utf-8

# GSM 300hPa ジェット・非地衡風・発散 天気図描画スクリプト
# 元コード: note5.ipynb
# 修正: 引数対応・自動DL・複数FT対応 20260409上原政博

import os
os.environ['PROJ_LIB'] = '/opt/anaconda3/envs/met_env_310/share/proj'  # ★importの前に設定！

from pyproj import datadir, CRS
datadir.set_data_dir(os.environ['PROJ_LIB'])

import pygrib
import xarray as xr
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import cartopy.crs as ccrs
import sys
import argparse
from pathlib import Path
import requests

import metpy.calc as mpcalc
from metpy.units import units

BASE_URL = "http://database.rish.kyoto-u.ac.jp/arch/jmadata/data/gpv/original"
HEADERS  = {"User-Agent": "Mozilla/5.0 (compatible; GSM-Downloader/1.0)"}


def ensure_file(gr_path, gr_fn, year, month, day):
    if os.path.exists(gr_path):
        return True
    print(f"データファイルが見つかりません: {gr_fn}")
    print("RISHサーバーからダウンロードを試みます...")
    url  = f"{BASE_URL}/{year}/{month:02d}/{day:02d}/{gr_fn}"
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
                        print(f"\r  {downloaded/total*100:.1f}% ({downloaded/1048576:.1f}/{total/1048576:.1f} MB)",
                              end="", flush=True)
            print()
        print(f"ダウンロード完了: {gr_fn} ({dest.stat().st_size/1048576:.1f} MB)")
        return True
    except requests.HTTPError as e:
        print(f"\nダウンロード失敗（HTTP {e.response.status_code}）: {url}")
        if dest.exists(): dest.unlink()
        return False
    except requests.RequestException as e:
        print(f"\nダウンロード失敗: {e}")
        if dest.exists(): dest.unlink()
        return False


def ddhh_to_hours(ddhh):
    return (ddhh // 100) * 24 + (ddhh % 100)

def hours_to_ddhh(hours):
    return (hours // 24) * 100 + (hours % 24)

def build_ft_list(start_ddhh, n_steps):
    start_h = ddhh_to_hours(start_ddhh)
    return [hours_to_ddhh(start_h + i * 6) for i in range(n_steps)]


def parse_args():
    parser = argparse.ArgumentParser(
        description='GSM GRIB2から300hPaジェット・非地衡風・発散天気図を描画する',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python GSM_Jet300hPa.py 2021100100 0000 1     # 初期値1枚
  python GSM_Jet300hPa.py 2021100100 0000 5     # FT0h〜FT24h 5枚
  python GSM_Jet300hPa.py 2021100100 0100 3 300 # FT24h〜FT36h 3枚
        """
    )
    parser.add_argument('init_time', type=str, help='初期時刻 YYYYMMDDHH（UTC）')
    parser.add_argument('start_ft',  type=str, help='開始予報時間 DDHH形式')
    parser.add_argument('n_steps',   type=int, help='作成する枚数（6h間隔）')
    parser.add_argument('level',     type=int, nargs='?', default=300, help='気圧面 hPa（デフォルト: 300）')
    return parser.parse_args()


def plot_one(i_year, i_month, i_day, i_hourZ, ft_ddhh, tagHp, output_dir):
    ft_hours = ddhh_to_hours(ft_ddhh)

    gsm_fn_t = "Z__C_RJTD_{0:04d}{1:02d}{2:02d}{3:02d}0000_GSM_GPV_Rgl_FD{4:04d}_grib2.bin"
    gr_fn   = gsm_fn_t.format(i_year, i_month, i_day, i_hourZ, ft_ddhh)
    gr_path = f"./data_gsm/{gr_fn}"

    if not ensure_file(gr_path, gr_fn, i_year, i_month, i_day):
        print(f"スキップ: FT={ft_hours}h（データ取得失敗）")
        return False

    print(f"[{ft_hours:4d}h] データ読み込み: {gr_fn}")

    grbs  = pygrib.open(gr_path)
    grbHt = grbs(shortName="gh", typeOfLevel='isobaricInhPa', level=tagHp)[0]
    grbWu = grbs(shortName="u",  typeOfLevel='isobaricInhPa', level=tagHp)[0]
    grbWv = grbs(shortName="v",  typeOfLevel='isobaricInhPa', level=tagHp)[0]
    grbs.close()

    latS, latN, lonW, lonE = -20, 80, 70, 190
    valHt, latHt, lonHt = grbHt.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)
    valWu, latWu, lonWu = grbWu.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)
    valWv, latWv, lonWv = grbWv.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)

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

    dsp = ds.metpy.parse_cf()
    dsp['wind_speed'] = mpcalc.wind_speed(dsp['u_wind'], dsp['v_wind'])
    dsp['uag'], dsp['vag'] = mpcalc.ageostrophic_wind(
        dsp['Geopotential_height'], dsp['u_wind'], dsp['v_wind'])
    dsp['conv'] = mpcalc.divergence(dsp['u_wind'], dsp['v_wind'])
    dsp['wind_speed'] = dsp['wind_speed'].metpy.convert_units('knots')
    dsp['uag'] = dsp['uag'].metpy.convert_units('knots')
    dsp['vag'] = dsp['vag'].metpy.convert_units('knots')

    dt_i    = grbHt.analDate
    dt_str  = (dt_i.strftime("%H00UTC%d%b%Y")).upper()
    dt_str2 = dt_i.strftime("%Y%m%d%H")

    # 等高度線間隔
    if   tagHp < 400: dd_hgt = 120
    elif tagHp < 700: dd_hgt = 60
    else:             dd_hgt = 30

    levels_reld = [-10, -5, -2, -1, 1, 2, 5, 10]
    levels_ws   = np.arange(40, 300, 20)
    i_area      = [115, 151, 20, 50]

    proj        = ccrs.Stereographic(central_latitude=60, central_longitude=140)
    latlon_proj = ccrs.PlateCarree()
    fig = plt.figure(figsize=(10, 8))
    plt.subplots_adjust(left=0, right=1, bottom=0.06, top=0.98)
    ax = fig.add_subplot(1, 1, 1, projection=proj)
    ax.set_extent(i_area, latlon_proj)
    ax.coastlines(resolution='50m')
    xticks = np.arange(0, 360.1, 10)
    yticks = np.arange(-90, 90.1, 10)
    gl = ax.gridlines(crs=ccrs.PlateCarree(), draw_labels=False, linewidth=1, alpha=0.8)
    gl.xlocator = mticker.FixedLocator(xticks)
    gl.ylocator = mticker.FixedLocator(yticks)

    # 収束・発散シェード
    cn_reld = ax.contourf(dsp['lon'], dsp['lat'], dsp['conv'].values * 1e5,
                          levels_reld, cmap="coolwarm", extend='both',
                          transform=latlon_proj)
    ax_reld = fig.add_axes([0.1, 0.1, 0.8, 0.02])
    cb_reld = fig.colorbar(cn_reld, orientation='horizontal', shrink=0.74,
                           aspect=40, pad=0.01, cax=ax_reld)
    cb_reld.set_label('Div. (*10$^{-5}$ s$^{-1}$)')

    # 等風速線
    cn_ws = ax.contour(dsp['lon'], dsp['lat'], dsp['wind_speed'].values,
                       colors='blue', linewidths=1.5, levels=levels_ws,
                       transform=latlon_proj)
    ax.clabel(cn_ws, fontsize=18, inline=True, colors='blue',
              inline_spacing=5, fmt='%i', rightside_up=True)

    # 等高度線
    dataHgt  = dsp['Geopotential_height']
    min_hgt  = int(dataHgt.min() / dd_hgt) * dd_hgt
    levels_hgt = np.arange(min_hgt, dataHgt.max() + dd_hgt, dd_hgt)
    cn_hgt = ax.contour(dsp['lon'], dsp['lat'], dsp['Geopotential_height'],
                        colors='black', linewidths=1.5, levels=levels_hgt,
                        transform=latlon_proj)
    ax.clabel(cn_hgt, levels_hgt, fontsize=18, inline=True, colors='black',
              inline_spacing=5, fmt='%i', rightside_up=True)

    # 非地衡風矢羽
    wind_slice0 = slice(None, None, 3)
    wind_slice2 = (slice(None, None, 3), slice(None, None, 3))
    ax.barbs(dsp['lon'][wind_slice0], dsp['lat'][wind_slice0],
             dsp['uag'].values[wind_slice2], dsp['vag'].values[wind_slice2],
             length=5.5, pivot='middle', color='black', transform=latlon_proj)

    fig.text(0.5, 0.01,
             f"GSM FT{ft_hours:d}h IT:{dt_str} {tagHp}hPa Heights, Div, ISOTAC, Ageostrophic Wind",
             ha='center', va='bottom', size=15)

    os.makedirs(output_dir, exist_ok=True)
    out_fn = f"{output_dir}/{dt_str2}_FT{ft_hours:03d}h_{tagHp}hPa_Jet.png"
    plt.savefig(out_fn, dpi=150, bbox_inches='tight')
    print(f"[{ft_hours:4d}h] 出力: {out_fn}")
    # plt.show()  # 画面表示する場合はコメントアウトを外す
    plt.close()
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
    tagHp   = args.level

    start_ddhh = int(args.start_ft)
    ft_list    = build_ft_list(start_ddhh, args.n_steps)

    print(f"初期時刻: {init_str} UTC  気圧面: {tagHp}hPa")
    print(f"予報時間: FT{ddhh_to_hours(start_ddhh)}h〜FT{ddhh_to_hours(ft_list[-1])}h（{args.n_steps}枚）")
    print()

    success = 0
    for ft_ddhh in ft_list:
        if plot_one(i_year, i_month, i_day, i_hourZ, ft_ddhh, tagHp, "./output"):
            success += 1
    print(f"\n完了: {success}/{args.n_steps}枚 出力先: ./output/")


if __name__ == "__main__":
    main()
