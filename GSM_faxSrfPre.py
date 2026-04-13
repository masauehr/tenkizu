#!/usr/bin/env python
# coding: utf-8

# GSM 地上気圧・風・2m気温天気図描画スクリプト
# 元コード: g2e_faxSrfPre_note版.ipynb  (2025/07/23 Ryuta Kurora)
# 修正: GSM GRIB2対応・引数対応・自動DL試行・複数FT対応 20260412上原政博
#
# データ取得: 京都大学RISHサーバー（全球GSM GRIB2）
#
# 表示要素: 地上気圧（等圧線）、10m風（矢羽）、2m気温（等温線）、H/Lスタンプ
#
# 注意: GSM Rglファイルには可降水量（tcwv/pwat）・積算降水量（tp）は含まれないため非対応。

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
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import sys
import argparse
from pathlib import Path
import requests

import metpy.calc as mpcalc
from metpy.units import units
from scipy.ndimage import maximum_filter, minimum_filter

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


def ddhh_to_hours(ddhh):
    return (ddhh // 100) * 24 + (ddhh % 100)

def hours_to_ddhh(hours):
    return (hours // 24) * 100 + (hours % 24)

def build_ft_list(start_ddhh, n_steps):
    start_h = ddhh_to_hours(start_ddhh)
    return [hours_to_ddhh(start_h + i * 6) for i in range(n_steps)]


def parse_args():
    parser = argparse.ArgumentParser(
        description='GSM GRIB2から地上気圧・風・2m気温天気図を描画する',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python GSM_faxSrfPre.py 2021082300           # FT=0h 1枚
  python GSM_faxSrfPre.py 2021082300 0000 5   # FT=0,6,12,18,24h 5枚
  python GSM_faxSrfPre.py 2021082300 0100 3   # FT=24,30,36h 3枚
        """
    )
    parser.add_argument('init_time', type=str,            help='初期時刻 YYYYMMDDHH（UTC）')
    parser.add_argument('start_ft',  type=str, nargs='?', default='0000',
                        help='開始予報時間 DDHH形式（デフォルト: 0000）')
    parser.add_argument('n_steps',   type=int, nargs='?', default=1,
                        help='作成する枚数（6h間隔、デフォルト: 1）')
    return parser.parse_args()


def plot_one(i_year, i_month, i_day, i_hourZ, ft_ddhh, output_dir):
    ft_hours = ddhh_to_hours(ft_ddhh)

    gsm_fn  = f"Z__C_RJTD_{i_year:04d}{i_month:02d}{i_day:02d}{i_hourZ:02d}0000_GSM_GPV_Rgl_FD{ft_ddhh:04d}_grib2.bin"
    gr_path = f"./data_gsm/{gsm_fn}"

    if not ensure_file(gr_path, gsm_fn, i_year, i_month, i_day):
        print(f"スキップ: FT={ft_hours}h（データ取得失敗）")
        return False

    print(f"[{ft_hours:4d}h] データ読み込み: {gsm_fn}")

    grbs    = pygrib.open(gr_path)
    grb_msl = grbs(shortName="prmsl", typeOfLevel='meanSea',           level=0)[0]
    grb_10u = grbs(shortName="10u",   typeOfLevel='heightAboveGround', level=10)[0]
    grb_10v = grbs(shortName="10v",   typeOfLevel='heightAboveGround', level=10)[0]
    grb_2t  = grbs(shortName="2t",    typeOfLevel='heightAboveGround', level=2)[0]
    grbs.close()

    valPre,  latPre,  lonPre  = grb_msl.data()
    val10u,  lat10u,  lon10u  = grb_10u.data()
    val10v,  lat10v,  lon10v  = grb_10v.data()
    val2tm,  lat2tm,  lon2tm  = grb_2t.data()

    ds = xr.Dataset(
        {
            "Pre":         (["lat", "lon"], valPre  * 0.01),  # Pa → hPa
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
    i_area = [108, 156, 17, 55]

    proj        = ccrs.Stereographic(central_latitude=60, central_longitude=140)
    latlon_proj = ccrs.PlateCarree()
    fig = plt.figure(figsize=(10, 8))
    plt.subplots_adjust(left=0, right=1, bottom=0.06, top=0.98)
    ax = fig.add_subplot(1, 1, 1, projection=proj)
    ax.set_extent(i_area, latlon_proj)

    # 2m等温度線（緑）
    dsp['Temperature'] = dsp['Temperature'].metpy.convert_units(units.degC)
    ax.contour(dsp['lon'], dsp['lat'], dsp['Temperature'],
               colors='green', alpha=0.5, linewidths=1.0, levels=levels_tmp0,
               transform=latlon_proj)

    # 等圧線（細線 4hPa間隔）
    ax.contour(dsp['lon'], dsp['lat'], dsp['Pre'],
               colors='black', linewidths=1.0, levels=levels_pre0, transform=latlon_proj)
    # 等圧線（太線 20hPa間隔 + ラベル）
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

    # 10m風矢羽
    wind_slice = (slice(None, None, 5), slice(None, None, 5))
    ax.barbs(dsp['lon'][wind_slice[0]], dsp['lat'][wind_slice[1]],
             dsp['u_wind'].values[wind_slice] * 1.944,
             dsp['v_wind'].values[wind_slice] * 1.944,
             length=5.5, pivot='middle', color='black', transform=latlon_proj)

    # H/Lスタンプ（気圧値付き）
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
             f"GSM FT{ft_hours:d}h IT:{dt_str} Surface Pre, Wind, 2m Temp",
             ha='center', va='bottom', size=15)

    os.makedirs(output_dir, exist_ok=True)
    out_fn = f"{output_dir}/{dt_str2}_FT{ft_hours:03d}h_GSM_SurfacePressure.png"
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

    start_ddhh = int(args.start_ft)
    ft_list    = build_ft_list(start_ddhh, args.n_steps)

    print(f"初期時刻: {init_str} UTC  地上気圧・風・2m気温")
    print(f"予報時間: FT{ddhh_to_hours(start_ddhh)}h〜FT{ddhh_to_hours(ft_list[-1])}h（{args.n_steps}枚）")
    print()

    success = 0
    for ft_ddhh in ft_list:
        if plot_one(i_year, i_month, i_day, i_hourZ, ft_ddhh, "./output"):
            success += 1
    print(f"\n完了: {success}/{args.n_steps}枚 出力先: ./output/")


if __name__ == "__main__":
    main()
