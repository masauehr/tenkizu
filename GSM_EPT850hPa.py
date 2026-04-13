#!/usr/bin/env python
# coding: utf-8

# GSM 850hPa 相当温位・風 天気図描画スクリプト
# ECM_EPT850hPa.py のGSM版: pygrib(RISHサーバーGRIB2)からデータを読み込む
# 作成: 20260413 上原政博

import os
os.environ['PROJ_LIB'] = '/opt/anaconda3/envs/met_env_310/share/proj'

from pyproj import datadir, CRS
datadir.set_data_dir(os.environ['PROJ_LIB'])

import pygrib
import xarray as xr
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import cartopy.crs as ccrs
import cartopy.feature as cfeature
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
        description='GSM GRIB2から850hPa相当温位・風天気図を描画する',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python GSM_EPT850hPa.py 2026041200           # FT=0h 1枚
  python GSM_EPT850hPa.py 2026041200 0000 5   # FT=0,6,12,18,24h 5枚
  python GSM_EPT850hPa.py 2026041200 0012 1   # FT=12h 1枚
        """
    )
    parser.add_argument('init_time', type=str, help='初期時刻 YYYYMMDDHH（UTC）')
    parser.add_argument('start_ft',  type=str, nargs='?', default='0000',
                        help='開始予報時間 DDHH形式（デフォルト: 0000）')
    parser.add_argument('n_steps',   type=int, nargs='?', default=1,
                        help='作成する枚数（6h間隔、デフォルト: 1）')
    parser.add_argument('level',     type=int, nargs='?', default=850,
                        help='気圧面 hPa（デフォルト: 850）')
    return parser.parse_args()


def plot_one(i_year, i_month, i_day, i_hourZ, ft_ddhh, tagHp, output_dir):
    ft_hours = ddhh_to_hours(ft_ddhh)

    gr_fn   = f"Z__C_RJTD_{i_year:04d}{i_month:02d}{i_day:02d}{i_hourZ:02d}0000_GSM_GPV_Rgl_FD{ft_ddhh:04d}_grib2.bin"
    gr_path = f"./data_gsm/{gr_fn}"

    if not ensure_file(gr_path, gr_fn, i_year, i_month, i_day):
        print(f"スキップ: FT={ft_hours}h（データ取得失敗）")
        return False

    print(f"[{ft_hours:4d}h] データ読み込み: {gr_fn}")

    grbs  = pygrib.open(gr_path)
    grbWu = grbs(shortName="u", typeOfLevel='isobaricInhPa', level=tagHp)[0]
    grbWv = grbs(shortName="v", typeOfLevel='isobaricInhPa', level=tagHp)[0]
    grbTm = grbs(shortName="t", typeOfLevel='isobaricInhPa', level=tagHp)[0]
    grbRh = grbs(shortName="r", typeOfLevel='isobaricInhPa', level=tagHp)[0]
    grbs.close()

    latS, latN, lonW, lonE = -20, 80, 70, 190
    valWu, latWu, lonWu = grbWu.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)
    valWv, latWv, lonWv = grbWv.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)
    valTm, latTm, lonTm = grbTm.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)
    valRh, latRh, lonRh = grbRh.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)

    ds = xr.Dataset(
        {
            "u_wind":          (["lat", "lon"], valWu * units('m/s')),
            "v_wind":          (["lat", "lon"], valWv * units('m/s')),
            "Temperature":     (["lat", "lon"], valTm * units('K')),
            "RelativHumidity": (["lat", "lon"], valRh * 0.01),
        },
        coords={
            "time":  np.array([grbTm.validDate]),
            "level": np.array(tagHp) * units.hPa,
            "lat":   np.array(latTm[:, 0]) * units('degrees_north'),
            "lon":   np.array(lonTm[0, :]) * units('degrees_east'),
        },
    )
    ds['u_wind'].attrs['units']          = 'm/s'
    ds['v_wind'].attrs['units']          = 'm/s'
    ds['Temperature'].attrs['units']     = 'K'
    ds['RelativHumidity'].attrs['units'] = ''
    ds['level'].attrs['units']           = 'hPa'
    ds['lat'].attrs['units']             = 'degrees_north'
    ds['lon'].attrs['units']             = 'degrees_east'

    dsp = ds.metpy.parse_cf()
    dsp['dewpoint_temperature'] = mpcalc.dewpoint_from_relative_humidity(
        dsp['Temperature'], dsp['RelativHumidity'])
    dsp['Equivalent_Potential_temperature'] = mpcalc.equivalent_potential_temperature(
        dsp['level'], dsp['Temperature'], dsp['dewpoint_temperature'])

    dt_i    = grbTm.analDate
    dt_str  = (dt_i.strftime("%H00UTC%d%b%Y")).upper()
    dt_str2 = dt_i.strftime("%Y%m%d%H")

    levels_ept0  = np.arange(270, 390,  3)
    levels_ept0i = np.arange(270, 390,  3)
    levels_ept1  = np.arange(270, 390, 15)
    levels_eptf  = np.arange(270, 360,  3)
    i_area = [115, 151, 20, 50]

    states_provinces = cfeature.NaturalEarthFeature(
        category='cultural', name='admin_1_states_provinces_lines', scale='50m', facecolor='none')
    country_borders = cfeature.NaturalEarthFeature(
        category='cultural', name='admin_0_countries', scale='50m', facecolor='none')

    proj        = ccrs.Stereographic(central_latitude=60, central_longitude=140)
    latlon_proj = ccrs.PlateCarree()
    fig = plt.figure(figsize=(10, 8))
    plt.subplots_adjust(left=0, right=1, bottom=0.06, top=0.98)
    ax = fig.add_subplot(1, 1, 1, projection=proj)
    ax.set_extent(i_area, latlon_proj)

    # EPTシェード
    cnf_ept = ax.contourf(dsp['lon'], dsp['lat'], dsp['Equivalent_Potential_temperature'],
                          levels_eptf, cmap="jet", extend='both', transform=latlon_proj)
    ax_ept = fig.add_axes([0.1, 0.1, 0.8, 0.02])
    fig.colorbar(cnf_ept, orientation='horizontal', shrink=0.74,
                 aspect=40, pad=0.01, cax=ax_ept)

    # EPT等値線（細線）
    cn_ept0 = ax.contour(dsp['lon'], dsp['lat'], dsp['Equivalent_Potential_temperature'],
                         colors='black', linewidths=0.3, levels=levels_ept0, transform=latlon_proj)
    ax.clabel(cn_ept0, levels_ept0i, fontsize=8, inline=True,
              inline_spacing=5, fmt='%i', rightside_up=True, colors='black')
    # EPT等値線（太線15K間隔）
    cn_ept1 = ax.contour(dsp['lon'], dsp['lat'], dsp['Equivalent_Potential_temperature'],
                         colors='black', linewidths=1.0, levels=levels_ept1, transform=latlon_proj)
    ax.clabel(cn_ept1, levels_ept1, fontsize=12, inline=True,
              inline_spacing=5, fmt='%i', rightside_up=True, colors='black')

    ax.coastlines(resolution='50m', linewidth=1.6)
    xticks = np.arange(0, 360, 10)
    yticks = np.arange(-90, 90.1, 10)
    gl = ax.gridlines(crs=ccrs.PlateCarree(), draw_labels=False, linewidth=1, alpha=0.8)
    gl.xlocator = mticker.FixedLocator(xticks)
    gl.ylocator = mticker.FixedLocator(yticks)

    # 風矢羽
    wind_slice = (slice(None, None, 5), slice(None, None, 5))
    ax.barbs(dsp['lon'][wind_slice[0]], dsp['lat'][wind_slice[1]],
             dsp['u_wind'].values[wind_slice] * 1.944,
             dsp['v_wind'].values[wind_slice] * 1.944,
             length=5.5, pivot='middle', color='black', transform=latlon_proj)

    fig.text(0.5, 0.01,
             f"GSM FT{ft_hours:d}h IT:{dt_str} {tagHp}hPa EPT(K), Wind",
             ha='center', va='bottom', size=15)

    os.makedirs(output_dir, exist_ok=True)
    out_fn = f"{output_dir}/{dt_str2}_FT{ft_hours:03d}h_GSM_{tagHp}hPa_EPT.png"
    plt.savefig(out_fn, dpi=150, bbox_inches='tight')
    print(f"[{ft_hours:4d}h] 出力: {out_fn}")
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

    start_ddhh = int(args.start_ft)
    ft_list    = build_ft_list(start_ddhh, args.n_steps)

    print(f"初期時刻: {init_str} UTC  気圧面: {args.level}hPa")
    print(f"予報時間: FT{ddhh_to_hours(start_ddhh)}h〜FT{ddhh_to_hours(ft_list[-1])}h（{args.n_steps}枚）")
    print()

    success = 0
    for ft_ddhh in ft_list:
        if plot_one(i_year, i_month, i_day, i_hourZ, ft_ddhh, args.level, "./output"):
            success += 1
    print(f"\n完了: {success}/{args.n_steps}枚 出力先: ./output/")


if __name__ == "__main__":
    main()
