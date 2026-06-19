#!/usr/bin/env python
# coding: utf-8

# ECMWF AIFS（AI気象モデル）地上気圧・風・2m気温天気図描画スクリプト
# ECMWF AI-Integrated Forecast System (AIFS) の GRIB2 データを取得・描画する。
# データ取得: ECMWF Open Data（最新5日分）
# 20260619 上原政博
#
# AIFSについて:
#   - 00z/12z のみ利用可能（06z/18z は存在しない）
#   - 常に oper サブディレクトリ（scda なし）
#   - FT最大240h、6h間隔
#   - ECMWF Open Data URL: https://data.ecmwf.int/forecasts/{YYYYMMDD}/{HH}z/aifs-single/0p25/oper/
#
# 使用例:
#   python AIFS_SurfacePressure.py 2026061200 0 1          # FT=0h 1枚
#   python AIFS_SurfacePressure.py 2026061200 0 5          # FT=0,6,12,18,24h 5枚
#   python AIFS_SurfacePressure.py 2026061200 0 1 --area 108 156 5 45

import os
os.environ['PROJ_LIB'] = '/opt/anaconda3/envs/met_env_310/share/proj'  # ★importの前に設定！

from pyproj import datadir
datadir.set_data_dir(os.environ['PROJ_LIB'])

import math
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
from scipy.ndimage import maximum_filter, minimum_filter, uniform_filter

AIFS_BASE_URL = "https://data.ecmwf.int/forecasts"
HEADERS   = {"User-Agent": "Mozilla/5.0 (compatible; AIFS-Downloader/1.0)"}
DATA_DIR  = "./data/aifs"


def ensure_file_aifs(aifs_path, aifs_fn, year, month, day, hour):
    """AIFSデータファイルを確認し、なければダウンロードする。AIFSは常に oper。"""
    if os.path.exists(aifs_path):
        return True
    print(f"AIFSデータファイルが見つかりません: {aifs_fn}")
    print("ECMWF Open Data (AIFS) からダウンロードを試みます（最新5日分のみ利用可）...")
    url = f"{AIFS_BASE_URL}/{year:04d}{month:02d}{day:02d}/{hour:02d}z/aifs-single/0p25/oper/{aifs_fn}"
    dest = Path(aifs_path)
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
        print(f"ダウンロード完了: {aifs_fn} ({dest.stat().st_size/1048576:.1f} MB)")
        return True
    except requests.HTTPError as e:
        print(f"\nダウンロード失敗（HTTP {e.response.status_code}）")
        if e.response.status_code == 404:
            print("  AIFSデータが存在しません。最新5日分のみ利用可能です（00z/12zのみ）。")
        if dest.exists():
            dest.unlink()
        return False
    except requests.RequestException as e:
        print(f"\nダウンロード失敗: {e}")
        if dest.exists():
            dest.unlink()
        return False


def transform_lonlat_to_figure(lonlat, ax, proj):
    point_proj = proj.transform_point(*lonlat, ccrs.PlateCarree())
    point_pix  = ax.transData.transform(point_proj)
    point_fig  = ax.transAxes.inverted().transform(point_pix)
    return point_fig, point_pix, point_proj


def detect_peaks(image, filter_size=3, dist_cut=5.0, flag=0):
    if flag == 0:
        local_ext = maximum_filter(image, footprint=np.ones((filter_size, filter_size)), mode='constant')
        detected_peaks = np.ma.array(image, mask=~(image == local_ext))
    else:
        local_ext = minimum_filter(image, footprint=np.ones((filter_size, filter_size)), mode='constant')
        detected_peaks = np.ma.array(image, mask=~(image == local_ext))
    peaks_index = np.where((detected_peaks.mask != True))
    (x, y) = peaks_index
    size = y.size
    dist = np.full((size, size), -1.0)
    for i in range(size):
        for j in range(size):
            if i == j:
                dist[i][j] = 0.0
            elif i > j:
                d = math.sqrt((y[i]-y[j])**2 + (x[i]-x[j])**2)
                dist[i][j] = d
                dist[j][i] = d
    Kinrin, dSum = [], []
    for i in range(size):
        tmpA, distSum = [], 0.0
        for j in range(size):
            if 0.0 < dist[i][j] < dist_cut:
                tmpA.append(j)
                distSum += dist[i][j]
        dSum.append(distSum)
        Kinrin.append(tmpA)
    cutPoint = []
    for i in range(size):
        val, val_i = dSum[i], image[x[i]][y[i]]
        for k in Kinrin[i]:
            val_k = image[x[k]][y[k]]
            if flag == 0 and val_i < val_k: cutPoint.append(i); break
            if flag != 0 and val_i > val_k: cutPoint.append(i); break
            if val > dSum[k]: cutPoint.append(i); break
            if val == dSum[k] and i > k: cutPoint.append(i); break
    newx = [x[i] for i in range(size) if i not in cutPoint]
    newy = [y[i] for i in range(size) if i not in cutPoint]
    return (np.array(newx), np.array(newy))


def build_ft_list(start_ft, n_steps, step=6):
    return [start_ft + i * step for i in range(n_steps)]


def parse_args():
    parser = argparse.ArgumentParser(
        description='ECMWF AIFS GRIB2から地上気圧・風・2m気温天気図を描画する',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python AIFS_SurfacePressure.py 2026061200 0 1          # FT=0h 1枚
  python AIFS_SurfacePressure.py 2026061200 0 5          # FT=0,6,12,18,24h 5枚

  # 描画範囲・平滑化・矢羽間隔の指定:
  python AIFS_SurfacePressure.py 2026061200 0 1 --area 108 156 5 45
  python AIFS_SurfacePressure.py 2026061200 0 1 --smooth-size 15
  python AIFS_SurfacePressure.py 2026061200 0 1 --wind-step 10

デフォルト描画設定:
  --area        108 156 17 55  東経108〜156°、北緯17〜55°
  --smooth-size 10             10×10格子平均スムージング（AIFS 0.25°→約2.5°相当）
  --wind-step   5              風矢羽を5格子おき（約1.25度間隔）

AIFSについて:
  ECMWF AI-Integrated Forecast System（AI気象モデル）
  00z/12z のみ利用可能（06z/18z なし）
  FT最大240h、6h間隔

実行環境（conda の場合）:
  conda activate met_env_310
  python AIFS_SurfacePressure.py [引数]

  ※ 環境名（met_env_310）は利用者の構築状況により異なります。
     pygrib / metpy / cartopy 等が入った Python 3.10 環境であれば動作します。
"""
    )
    parser.add_argument('init_time', type=str,            help='初期時刻 YYYYMMDDHH（UTC）')
    parser.add_argument('start_ft',  type=int, nargs='?', default=0,  help='開始予報時間（時間数）')
    parser.add_argument('n_steps',   type=int, nargs='?', default=1,  help='作成する枚数（6h間隔）')
    parser.add_argument('--area', type=float, nargs=4, default=None,
                        metavar=('LON_W', 'LON_E', 'LAT_S', 'LAT_N'),
                        help='描画範囲（デフォルト: 108 156 17 55）')
    parser.add_argument('--smooth-size', type=int, default=10,
                        help='uniform_filter のサイズ（デフォルト: 10）')
    parser.add_argument('--wind-step', type=int, default=5,
                        help='風矢羽の間引きステップ（デフォルト: 5格子おき）')

    if any(a in sys.argv[1:] for a in ('?', '-?', '--?')):
        parser.print_help()
        sys.exit(0)

    return parser.parse_args()


def plot_one(i_year, i_month, i_day, i_hourZ, ft_hours, output_dir, area=None, smooth_size=10, wind_step=5):
    # AIFSは常に oper（scda なし）
    aifs_fn   = f"{i_year:04d}{i_month:02d}{i_day:02d}{i_hourZ:02d}0000-{ft_hours:d}h-oper-fc.grib2"
    aifs_path = f"{DATA_DIR}/{aifs_fn}"

    if not ensure_file_aifs(aifs_path, aifs_fn, i_year, i_month, i_day, i_hourZ):
        print(f"スキップ: FT={ft_hours}h（データ取得失敗）")
        return False

    print(f"[{ft_hours:4d}h] データ読み込み: {aifs_fn}")

    grbs    = pygrib.open(aifs_path)
    grb_msl = grbs(shortName="msl", typeOfLevel='meanSea',           level=0)[0]
    grb_10u = grbs(shortName="10u", typeOfLevel='heightAboveGround', level=10)[0]
    grb_10v = grbs(shortName="10v", typeOfLevel='heightAboveGround', level=10)[0]
    grb_2t  = grbs(shortName="2t",  typeOfLevel='heightAboveGround', level=2)[0]
    grbs.close()

    valPre, latPre, lonPre = grb_msl.data()
    val10u, lat10u, lon10u = grb_10u.data()
    val10v, lat10v, lon10v = grb_10v.data()
    val2tm, lat2tm, lon2tm = grb_2t.data()

    _s = smooth_size
    valPre = uniform_filter(valPre, size=_s)
    val10u = uniform_filter(val10u, size=_s)
    val10v = uniform_filter(val10v, size=_s)
    val2tm = uniform_filter(val2tm, size=_s)

    ds = xr.Dataset(
        {
            "Pre":         (["lat", "lon"], valPre * 0.01),
            "u_wind":      (["lat", "lon"], val10u),
            "v_wind":      (["lat", "lon"], val10v),
            "Temperature": (["lat", "lon"], val2tm),
        },
        coords={
            "time": np.array([grb_msl.validDate]),
            "lat":  np.array(latPre[:, 0]) * units('degrees_north'),
            "lon":  np.array(lonPre[0, :]) * units('degrees_east'),
        },
    )
    ds['Pre'].attrs['units']         = 'hPa'
    ds['u_wind'].attrs['units']      = 'm/s'
    ds['v_wind'].attrs['units']      = 'm/s'
    ds['Temperature'].attrs['units'] = 'K'
    ds['lat'].attrs['units']         = 'degrees_north'
    ds['lon'].attrs['units']         = 'degrees_east'

    dsp = ds.metpy.parse_cf()

    dt_i    = grb_msl.analDate
    dt_str  = (dt_i.strftime("%H00UTC%d%b%Y")).upper()
    dt_str2 = dt_i.strftime("%Y%m%d%H")

    levels_tmp0  = np.arange(-60, 60,  3)
    levels_pre0  = np.arange(860, 1100,  4)
    levels_pre0B = np.arange(860, 1100, 20)
    i_area = area if area is not None else [108, 156, 17, 55]

    proj        = ccrs.Stereographic(central_latitude=60, central_longitude=140)
    latlon_proj = ccrs.PlateCarree()
    fig = plt.figure(figsize=(10, 8))
    plt.subplots_adjust(left=0, right=1, bottom=0.06, top=0.98)
    ax = fig.add_subplot(1, 1, 1, projection=proj)
    ax.set_extent(i_area, latlon_proj)

    dsp['Temperature'] = dsp['Temperature'].metpy.convert_units(units.degC)
    ax.contour(dsp['lon'], dsp['lat'], dsp['Temperature'],
               colors='green', alpha=0.5, linewidths=1.0, levels=levels_tmp0,
               transform=latlon_proj)

    ax.contour(dsp['lon'], dsp['lat'], dsp['Pre'],
               colors='black', linewidths=1.0, levels=levels_pre0, transform=latlon_proj)
    cn_pre_b = ax.contour(dsp['lon'], dsp['lat'], dsp['Pre'],
                          colors='black', linewidths=3.0, levels=levels_pre0B, transform=latlon_proj)
    ax.clabel(cn_pre_b, levels_pre0B, fontsize=12, inline=True,
              inline_spacing=5, fmt='%i', rightside_up=True, colors='black')

    ax.coastlines(resolution='50m', linewidth=1.6)
    xticks = np.arange(0, 360.1, 10)
    yticks = np.arange(-90, 90.1, 10)
    gl = ax.gridlines(crs=ccrs.PlateCarree(), draw_labels=False, linewidth=1, alpha=0.8)
    gl.xlocator = mticker.FixedLocator(xticks)
    gl.ylocator = mticker.FixedLocator(yticks)

    wind_slice = (slice(None, None, wind_step), slice(None, None, wind_step))
    ax.barbs(dsp['lon'][wind_slice[0]], dsp['lat'][wind_slice[1]],
             dsp['u_wind'].values[wind_slice] * 1.944,
             dsp['v_wind'].values[wind_slice] * 1.944,
             length=5.5, pivot='middle', color='black', transform=latlon_proj)

    for flag, label, color in [(0, 'H', 'blue'), (1, 'L', 'red')]:
        pid = detect_peaks(dsp['Pre'].values, filter_size=10, dist_cut=8.0, flag=flag)
        for i in range(len(pid[0])):
            wlon = dsp['lon'][pid[1][i]]
            wlat = dsp['lat'][pid[0][i]]
            fig_z, _, _ = transform_lonlat_to_figure((wlon, wlat), ax, proj)
            if 0.05 < fig_z[0] < 0.95 and 0.05 < fig_z[1] < 0.95:
                ax.plot(wlon, wlat, marker='x', markersize=4, color=color, transform=latlon_proj)
                ax.text(wlon, wlat + 0.5, label, size=16, color=color, transform=latlon_proj)
                val = int(dsp['Pre'].values[pid[0][i]][pid[1][i]])
                ax.text(fig_z[0], fig_z[1] - 0.01, str(val), size=12, color=color,
                        transform=ax.transAxes,
                        verticalalignment='top', horizontalalignment='center')

    title = f"AIFS FT{ft_hours:d}h IT:{dt_str} Surface Pre, Wind, Temp"
    fig.text(0.5, 0.01, title, ha='center', va='bottom', size=15)

    os.makedirs(output_dir, exist_ok=True)
    out_fn = f"{output_dir}/{dt_str2}_FT{ft_hours:03d}h_AIFS_SurfacePressure.png"
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

    if i_hourZ not in (0, 12):
        print(f"警告: AIFS は 00z/12z のみ利用可能です（指定: {i_hourZ:02d}z）")

    ft_list = build_ft_list(args.start_ft, args.n_steps)
    print(f"初期時刻: {init_str} UTC  AIFS 地上気圧・風・2m気温")
    print(f"予報時間: FT{ft_list[0]}h〜FT{ft_list[-1]}h（{args.n_steps}枚）")
    print()

    success = 0
    for ft in ft_list:
        if plot_one(i_year, i_month, i_day, i_hourZ, ft, "./output",
                   area=args.area, smooth_size=args.smooth_size, wind_step=args.wind_step):
            success += 1
    print(f"\n完了: {success}/{args.n_steps}枚 出力先: ./output/")


if __name__ == "__main__":
    main()
