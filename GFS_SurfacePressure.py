#!/usr/bin/env python
# coding: utf-8

# GFS 地上気圧・風・2m気温天気図描画スクリプト
# データ取得: NOAA NOMADS filter（地表面変数のみ、数MB）
#             https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl
#
# 表示要素: 地上気圧（等圧線）、10m風（矢羽）、2m気温（等温線）、H/Lスタンプ
#
# 使用例:
#   python GFS_SurfacePressure.py 2026052812                   # FT=0h 1枚
#   python GFS_SurfacePressure.py 2026052812 0 5               # FT=0,6,12,18,24h 5枚
#   python GFS_SurfacePressure.py 2026052812 0 1 --area 108 156 5 45
#   python GFS_SurfacePressure.py 2026052812 0 1 --smooth-size 5 --wind-step 10
#
# 注意:
#   - GFS は 00/06/12/18 UTC 初期化、3h間隔で FT=384h まで
#   - NOMADS には直近 ~10 日分のみ保存
#   - start_ft は時間数（整数）で指定（ECM と同形式）

import os
os.environ['PROJ_LIB'] = '/opt/anaconda3/envs/met_env_310/share/proj'

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

GFS_NOMADS_FILTER = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
GFS_NOMADS_PUB    = "https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod"
HEADERS           = {"User-Agent": "Mozilla/5.0 (compatible; GFS-Downloader/1.0)"}
DATA_DIR          = "./data/gfs"


def gfs_local_path(init_str, ft_h):
    """ローカル保存パスを返す。"""
    return Path(DATA_DIR) / f"gfs_{init_str}_f{ft_h:03d}_srf.grib2"


def ensure_file_gfs(init_str, ft_h):
    """ローカルにあれば True 返却、なければ NOMADS filter から DL する。"""
    dest = gfs_local_path(init_str, ft_h)
    if dest.exists() and dest.stat().st_size > 10_000:
        return True

    i_year  = int(init_str[0:4])
    i_month = int(init_str[4:6])
    i_day   = int(init_str[6:8])
    i_hourZ = int(init_str[8:10])
    date_str = f"{i_year:04d}{i_month:02d}{i_day:02d}"
    fn       = f"gfs.t{i_hourZ:02d}z.pgrb2.0p25.f{ft_h:03d}"

    params = {
        "file":                   fn,
        "dir":                    f"/gfs.{date_str}/{i_hourZ:02d}/atmos",
        "var_PRMSL":              "on",
        "var_TMP":                "on",
        "var_UGRD":               "on",
        "var_VGRD":               "on",
        "lev_mean_sea_level":     "on",
        "lev_2_m_above_ground":   "on",
        "lev_10_m_above_ground":  "on",
    }

    print(f"GFSデータをNOMADS filterからDL中: {fn} (FT={ft_h}h)")
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with requests.get(GFS_NOMADS_FILTER, params=params,
                          headers=HEADERS, stream=True, timeout=300) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            downloaded = 0
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        print(f"\r  {downloaded/total*100:.1f}% ({downloaded/1048576:.1f} MB)",
                              end="", flush=True)
            print()
        # サイズが異常に小さい場合（404等のHTML応答）は失敗扱い
        if dest.stat().st_size < 10_000:
            print(f"  ダウンロード失敗（ファイルが小さすぎる: {dest.stat().st_size} bytes）")
            print("  NOMADS にデータが存在しない可能性があります（直近 ~10 日分のみ）")
            dest.unlink()
            return False
        print(f"  完了: {dest.name} ({dest.stat().st_size/1048576:.1f} MB)")
        return True
    except requests.HTTPError as e:
        print(f"\n  ダウンロード失敗（HTTP {e.response.status_code}）")
        if dest.exists():
            dest.unlink()
        return False
    except requests.RequestException as e:
        print(f"\n  ダウンロード失敗: {e}")
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


def parse_args():
    parser = argparse.ArgumentParser(
        description='GFS GRIB2から地上気圧・風・2m気温天気図を描画する',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python GFS_SurfacePressure.py 2026052812 0 1                               # FT=0h 1枚
  python GFS_SurfacePressure.py 2026052812 0 5                               # FT=0,6,12,18,24h 5枚
  python GFS_SurfacePressure.py 2026052812 0 1 --area 108 156 5 45           # 描画範囲指定
  python GFS_SurfacePressure.py 2026052812 0 1 --smooth-size 5 --wind-step 10

デフォルト描画設定:
  --area        108 156 17 55  東経108〜156°、北緯17〜55°
  --smooth-size 5              5×5格子平均スムージング（GFS 0.25°→約1.25°相当）
  --wind-step   10             風矢羽を10格子おき（約2.5度間隔）

GFS データ:
  - NOAA NOMADS filter から地表面変数のみ DL（数 MB）
  - 直近 ~10 日分のみ利用可
  - 初期時刻: 00/06/12/18 UTC、3h間隔で FT=384h まで

実行環境（conda の場合）:
  conda activate met_env_310
  python GFS_SurfacePressure.py [引数]

  ※ 環境名（met_env_310）は利用者の構築状況により異なります。
     pygrib / metpy / cartopy 等が入った Python 3.10 環境であれば動作します。
"""
    )
    parser.add_argument('init_time',  type=str,            help='初期時刻 YYYYMMDDHH（UTC）')
    parser.add_argument('start_ft',   type=int, nargs='?', default=0,
                        help='開始予報時間（時間数、デフォルト: 0）')
    parser.add_argument('n_steps',    type=int, nargs='?', default=1,
                        help='作成する枚数（デフォルト: 1、間隔は --interval で指定）')
    parser.add_argument('--interval', type=int, default=6,
                        help='FT間隔 時間数（デフォルト: 6）')
    parser.add_argument('--area', type=float, nargs=4, default=None,
                        metavar=('LON_W', 'LON_E', 'LAT_S', 'LAT_N'),
                        help='描画範囲（デフォルト: 108 156 17 55）')
    parser.add_argument('--smooth-size', type=int, default=5,
                        help='uniform_filter のサイズ（デフォルト: 5）')
    parser.add_argument('--wind-step', type=int, default=10,
                        help='風矢羽の間引きステップ（デフォルト: 10格子おき）')

    if any(a in sys.argv[1:] for a in ('?', '-?', '--?')):
        parser.print_help()
        sys.exit(0)

    return parser.parse_args()


def plot_one(init_str, ft_h, output_dir, area=None, smooth_size=5, wind_step=10):
    i_year  = int(init_str[0:4])
    i_month = int(init_str[4:6])
    i_day   = int(init_str[6:8])
    i_hourZ = int(init_str[8:10])

    if not ensure_file_gfs(init_str, ft_h):
        print(f"  スキップ: FT={ft_h}h（データ取得失敗）")
        return False

    grib_path = str(gfs_local_path(init_str, ft_h))
    print(f"  [{ft_h:4d}h] データ読み込み: {Path(grib_path).name}")

    grbs = pygrib.open(grib_path)

    # MSLP: GFS では shortName="prmsl" (WMO param 1) を試み、なければ "mslet"
    try:
        grb_msl = grbs(shortName="prmsl", typeOfLevel='meanSea', level=0)[0]
    except Exception:
        grb_msl = grbs(shortName="mslet", typeOfLevel='meanSea', level=0)[0]

    grb_10u = grbs(shortName="10u", typeOfLevel='heightAboveGround', level=10)[0]
    grb_10v = grbs(shortName="10v", typeOfLevel='heightAboveGround', level=10)[0]
    grb_2t  = grbs(shortName="2t",  typeOfLevel='heightAboveGround', level=2)[0]
    grbs.close()

    valPre, latPre, lonPre = grb_msl.data()
    val10u, _,     _       = grb_10u.data()
    val10v, _,     _       = grb_10v.data()
    val2tm, _,     _       = grb_2t.data()

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
    gl = ax.gridlines(crs=ccrs.PlateCarree(), draw_labels=False, linewidth=1, alpha=0.8)
    gl.xlocator = mticker.FixedLocator(np.arange(0, 360.1, 10))
    gl.ylocator = mticker.FixedLocator(np.arange(-90, 90.1, 10))

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

    fig.text(0.5, 0.01,
             f"GFS FT{ft_h:d}h IT:{dt_str} Surface Pre, Wind, 2m Temp",
             ha='center', va='bottom', size=15)

    os.makedirs(output_dir, exist_ok=True)
    out_fn = f"{output_dir}/{dt_str2}_FT{ft_h:03d}h_GFS_SurfacePressure.png"
    plt.savefig(out_fn, dpi=150, bbox_inches='tight')
    print(f"  [{ft_h:4d}h] 出力: {out_fn}")
    plt.close()
    return True


def main():
    args = parse_args()
    init_str = args.init_time
    if len(init_str) != 10:
        print("エラー: init_time は YYYYMMDDHH の10桁で指定してください")
        sys.exit(1)

    ft_list = [args.start_ft + i * args.interval for i in range(args.n_steps)]

    print(f"GFS 地上気圧・風・2m気温")
    print(f"初期時刻: {init_str} UTC  FT: {ft_list[0]}h〜{ft_list[-1]}h  {args.n_steps}枚")
    print()

    success = 0
    for ft_h in ft_list:
        if plot_one(init_str, ft_h, "./output",
                    area=args.area,
                    smooth_size=args.smooth_size,
                    wind_step=args.wind_step):
            success += 1
    print(f"\n完了: {success}/{args.n_steps}枚  出力先: ./output/")


if __name__ == "__main__":
    main()
