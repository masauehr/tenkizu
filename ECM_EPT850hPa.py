#!/usr/bin/env python
# coding: utf-8

# ECMWF 850hPa 相当温位・風 天気図描画スクリプト
# 元コード: g2e_ept_note版.ipynb  (2023/07/26 Ryuta Kurora)
# 修正: 引数対応・自動DL試行・複数FT対応 20260409上原政博
#
# データ取得について:
#   ECMWFデータは以下の方法で取得可能:
#   1. ECMWF Open Data（最新5日分のみ無償）
#      URL: https://data.ecmwf.int/forecasts/{YYYYMMDD}/{HH}z/ifs/0p25/{oper|scda}/
#   2. Copernicus CDS API（過去データ、要登録）
#      https://cds.climate.copernicus.eu/

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
import cartopy.feature as cfeature
import sys
import argparse
from pathlib import Path
import requests

import metpy.calc as mpcalc
from metpy.units import units
from scipy.ndimage import uniform_filter

# ECMWF Open Data ベースURL
ECM_BASE_URL = "https://data.ecmwf.int/forecasts"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ECM-Downloader/1.0)"}
DATA_DIR = "./data/ecm"


def ensure_file_ecm(ecm_path, ecm_fn, year, month, day, hour):
    """
    ECMWFデータファイルが存在しない場合、ECMWF Open Dataからダウンロードを試みる。
    注意: ECMWF Open Dataは最新5日分のみ無償公開。過去データはCDS APIが必要。
    """
    if os.path.exists(ecm_path):
        return True

    print(f"ECMWFデータファイルが見つかりません: {ecm_fn}")
    print("ECMWF Open Dataからダウンロードを試みます（最新5日分のみ利用可）...")

    # oper（00/12UTC）か scda（06/18UTC）かを判定
    sub_dir = "oper" if hour in (0, 12) else "scda"
    url = f"{ECM_BASE_URL}/{year:04d}{month:02d}{day:02d}/{hour:02d}z/ifs/0p25/{sub_dir}/{ecm_fn}"

    dest = Path(ecm_path)
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
        print(f"ダウンロード完了: {ecm_fn} ({dest.stat().st_size/1048576:.1f} MB)")
        return True
    except requests.HTTPError as e:
        print(f"\nダウンロード失敗（HTTP {e.response.status_code}）")
        if e.response.status_code == 404:
            print("  データが存在しません。過去データはCDS API (https://cds.climate.copernicus.eu) を利用してください。")
        if dest.exists():
            dest.unlink()
        return False
    except requests.RequestException as e:
        print(f"\nダウンロード失敗: {e}")
        if dest.exists():
            dest.unlink()
        return False


def build_ft_list(start_ft, n_steps, step=6):
    """start_ftからn_steps個のFTリスト（時間）を生成する（デフォルト6h間隔）"""
    return [start_ft + i * step for i in range(n_steps)]


def parse_args():
    parser = argparse.ArgumentParser(
        description='ECMWF GRIB2から850hPa相当温位・風天気図を描画する',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python ECM_EPT850hPa.py 2023052318 0 1     # FT=0h 1枚
  python ECM_EPT850hPa.py 2023052318 0 5     # FT=0,6,12,18,24h 5枚
  python ECM_EPT850hPa.py 2023052312 0 3 850 # 850hPa

引数説明:
  init_time: 初期時刻 YYYYMMDDHH（UTC）
  start_ft : 開始予報時間（時間数）例: 0, 12, 24
  n_steps  : 作成する枚数（6h間隔）
  level    : 気圧面 hPa（省略可、デフォルト: 850）
        """
    )
    parser.add_argument('init_time', type=str, help='初期時刻 YYYYMMDDHH（UTC）')
    parser.add_argument('start_ft',  type=int, nargs='?', default=0, help='開始予報時間（時間数）例: 0, 12, 24')
    parser.add_argument('n_steps',   type=int, nargs='?', default=1, help='作成する枚数（6h間隔）')
    parser.add_argument('level',     type=int, nargs='?', default=850, help='気圧面 hPa（デフォルト: 850）')
    return parser.parse_args()


def plot_one(i_year, i_month, i_day, i_hourZ, ft_hours, tagHp, output_dir):
    # ECMWFファイル名を構築
    if i_hourZ in (0, 12):
        ecm_fn = f"{i_year:04d}{i_month:02d}{i_day:02d}{i_hourZ:02d}0000-{ft_hours:d}h-oper-fc.grib2"
    else:
        ecm_fn = f"{i_year:04d}{i_month:02d}{i_day:02d}{i_hourZ:02d}0000-{ft_hours:d}h-scda-fc.grib2"
    ecm_path = f"{DATA_DIR}/{ecm_fn}"

    if not ensure_file_ecm(ecm_path, ecm_fn, i_year, i_month, i_day, i_hourZ):
        print(f"スキップ: FT={ft_hours}h（データ取得失敗）")
        return False

    print(f"[{ft_hours:4d}h] データ読み込み: {ecm_fn}")

    grbs  = pygrib.open(ecm_path)
    grbHt = grbs(shortName="gh", typeOfLevel='isobaricInhPa', level=tagHp)[0]
    grbWu = grbs(shortName="u",  typeOfLevel='isobaricInhPa', level=tagHp)[0]
    grbWv = grbs(shortName="v",  typeOfLevel='isobaricInhPa', level=tagHp)[0]
    grbTm = grbs(shortName="t",  typeOfLevel='isobaricInhPa', level=tagHp)[0]
    grbRh = grbs(shortName="r",  typeOfLevel='isobaricInhPa', level=tagHp)[0]
    grbs.close()

    latS, latN, lonW, lonE = -20, 80, 70, 190
    valHt, latHt, lonHt = grbHt.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)
    valWu, latWu, lonWu = grbWu.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)
    valWv, latWv, lonWv = grbWv.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)
    valTm, latTm, lonTm = grbTm.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)
    valRh, latRh, lonRh = grbRh.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)

    # ECM(0.25°)をGSM並みの粗さに平滑化（3×3格子平均）
    _s = 3
    valHt = uniform_filter(valHt, size=_s)
    valWu = uniform_filter(valWu, size=_s)
    valWv = uniform_filter(valWv, size=_s)
    valTm = uniform_filter(valTm, size=_s)
    valRh = uniform_filter(valRh, size=_s)

    ds = xr.Dataset(
        {
            "Geopotential_height": (["lat", "lon"], valHt),
            "u_wind":              (["lat", "lon"], valWu),
            "v_wind":              (["lat", "lon"], valWv),
            "Temperature":         (["lat", "lon"], valTm),
            "RelativHumidity":     (["lat", "lon"], valRh * 0.01),
        },
        coords={
            "time":  np.array([grbHt.validDate]),
            "level": np.array(tagHp) * units.hPa,
            "lat":   np.array(latHt[:, 0]) * units('degrees_north'),
            "lon":   np.array(lonHt[0, :]) * units('degrees_east'),
        },
    )
    ds['Geopotential_height'].attrs['units'] = 'm'
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

    dt_i    = grbHt.analDate
    dt_str  = (dt_i.strftime("%H00UTC%d%b%Y")).upper()
    dt_str2 = dt_i.strftime("%Y%m%d%H")

    # 相当温位等値線設定
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
    # EPT等値線（太線）
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
             f"ECM FT{ft_hours:d}h IT:{dt_str} {tagHp}hPa EPT(K), Wind",
             ha='center', va='bottom', size=15)

    os.makedirs(output_dir, exist_ok=True)
    out_fn = f"{output_dir}/{dt_str2}_FT{ft_hours:03d}h_ECM_{tagHp}hPa_EPT.png"
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

    ft_list = build_ft_list(args.start_ft, args.n_steps)

    print(f"初期時刻: {init_str} UTC  気圧面: {args.level}hPa")
    print(f"予報時間: FT{ft_list[0]}h〜FT{ft_list[-1]}h（{args.n_steps}枚）")
    print()

    success = 0
    for ft in ft_list:
        if plot_one(i_year, i_month, i_day, i_hourZ, ft, args.level, "./output"):
            success += 1
    print(f"\n完了: {success}/{args.n_steps}枚 出力先: ./output/")


if __name__ == "__main__":
    main()
