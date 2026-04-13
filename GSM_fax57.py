#!/usr/bin/env python
# coding: utf-8

# GSM FAX図 FXFE5782/5784相当: 500hPa気温・700hPa湿数（T-Td）天気図描画スクリプト
# 元コード: g2e_fax57_note版.ipynb  (2023/07/25 Ryuta Kurora)
# 修正: GSM GRIB2対応・引数対応・自動DL試行・複数FT対応 20260412上原政博
#
# データ取得: 京都大学RISHサーバー（全球GSM GRIB2）

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
        description='GSM GRIB2からFAX57相当: 500hPa気温・700hPa湿数天気図を描画する',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python GSM_fax57.py 2021082300           # FT=0h 1枚
  python GSM_fax57.py 2021082300 0000 5   # FT=0,6,12,18,24h 5枚
  python GSM_fax57.py 2021082300 0100 3   # FT=24,30,36h 3枚
        """
    )
    parser.add_argument('init_time', type=str,  help='初期時刻 YYYYMMDDHH（UTC）')
    parser.add_argument('start_ft',  type=str,  nargs='?', default='0000',
                        help='開始予報時間 DDHH形式（デフォルト: 0000）')
    parser.add_argument('n_steps',   type=int,  nargs='?', default=1,
                        help='作成する枚数（6h間隔、デフォルト: 1）')
    return parser.parse_args()


def plot_one(i_year, i_month, i_day, i_hourZ, ft_ddhh, output_dir):
    tagTmp, tagTTd = 500, 700
    ft_hours = ddhh_to_hours(ft_ddhh)

    gsm_fn  = f"Z__C_RJTD_{i_year:04d}{i_month:02d}{i_day:02d}{i_hourZ:02d}0000_GSM_GPV_Rgl_FD{ft_ddhh:04d}_grib2.bin"
    gr_path = f"./data_gsm/{gsm_fn}"

    if not ensure_file(gr_path, gsm_fn, i_year, i_month, i_day):
        print(f"スキップ: FT={ft_hours}h（データ取得失敗）")
        return False

    print(f"[{ft_hours:4d}h] データ読み込み: {gsm_fn}")

    grbs     = pygrib.open(gr_path)
    grbTm500 = grbs(shortName="t", typeOfLevel='isobaricInhPa', level=tagTmp)[0]
    grbTm700 = grbs(shortName="t", typeOfLevel='isobaricInhPa', level=tagTTd)[0]
    grbRh700 = grbs(shortName="r", typeOfLevel='isobaricInhPa', level=tagTTd)[0]
    grbs.close()

    latS, latN, lonW, lonE = -20, 80, 70, 190
    valT5, latT5, lonT5 = grbTm500.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)
    valT7, latT7, lonT7 = grbTm700.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)
    valR7, latR7, lonR7 = grbRh700.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)

    # 500hPa気温データセット
    dst = xr.Dataset(
        {"temperature": (["lat", "lon"], valT5 * units('K'))},
        coords={"level": [tagTmp], "lat": latT5[:, 0], "lon": lonT5[0, :], "time": [grbTm500.validDate]},
    )
    dst['temperature'].attrs['units'] = 'K'
    dst['level'].attrs['units'] = 'hPa'
    dst['lat'].attrs['units']   = 'degrees_north'
    dst['lon'].attrs['units']   = 'degrees_east'
    dstp = dst.metpy.parse_cf()

    # 700hPa T-Tdデータセット
    ds = xr.Dataset(
        {
            "temperature":       (["lat", "lon"], valT7 * units('K')),
            "relative_humidity": (["lat", "lon"], valR7 * units('%')),
        },
        coords={"level": [tagTTd], "lat": latT7[:, 0], "lon": lonT7[0, :], "time": [grbTm700.validDate]},
    )
    ds['temperature'].attrs['units']       = 'K'
    ds['relative_humidity'].attrs['units'] = '%'
    ds['level'].attrs['units']             = 'hPa'
    ds['lat'].attrs['units']               = 'degrees_north'
    ds['lon'].attrs['units']               = 'degrees_east'
    ds['ttd'] = ds['temperature'] - mpcalc.dewpoint_from_relative_humidity(
        ds['temperature'], ds['relative_humidity'])
    ds['ttd'].attrs['units'] = 'K'
    dsp = ds.metpy.parse_cf()

    dt_i    = grbTm500.analDate
    dt_str  = (dt_i.strftime("%H00UTC%d%b%Y")).upper()
    dt_str2 = dt_i.strftime("%Y%m%d%H")

    levels_tmp       = np.arange(-60, 42,  3)
    levels_tmp1      = np.arange(-60, 42, 15)
    levels_h_ttd     = [0, 3, 6, 18, 100]
    levels_h_ttd_col = ['green', '0.4', '1.0', 'yellow']
    levels_ttd       = np.arange(3, 30, 3)
    i_area = [108, 156, 17, 55]

    proj        = ccrs.Stereographic(central_latitude=60, central_longitude=140)
    latlon_proj = ccrs.PlateCarree()
    fig = plt.figure(figsize=(10, 8))
    plt.subplots_adjust(left=0, right=1, bottom=0.06, top=0.98)
    plt.rcParams["contour.negative_linestyle"] = 'solid'
    ax = fig.add_subplot(1, 1, 1, projection=proj)
    ax.set_extent(i_area, latlon_proj)

    # 700hPa T-Tdシェード・等値線
    cnf_ttd = ax.contourf(dsp['lon'], dsp['lat'], dsp['ttd'],
                          levels_h_ttd, colors=levels_h_ttd_col,
                          alpha=0.2, extend='both', transform=latlon_proj)
    ax.contour(dsp['lon'], dsp['lat'], dsp['ttd'],
               colors='gray', linewidths=1.0, levels=levels_ttd, transform=latlon_proj)
    ax_ttd = fig.add_axes([0.1, 0.1, 0.8, 0.02])
    fig.colorbar(cnf_ttd, orientation='horizontal', shrink=0.74, aspect=40,
                 pad=0.01, cax=ax_ttd)

    # 500hPa等温度線（青、3℃間隔）
    dstp['temperature'] = dstp['temperature'].metpy.convert_units(units.degC)
    cn_tmp = ax.contour(dstp['lon'], dstp['lat'], dstp['temperature'],
                        colors='blue', linewidths=1.5, levels=levels_tmp, transform=latlon_proj)
    ax.clabel(cn_tmp, cn_tmp.levels, fontsize=12, inline=True,
              inline_spacing=5, colors='blue', fmt='%i', rightside_up=True)
    # 500hPa等温度線（青、太線15℃間隔）
    cn_tmp1 = ax.contour(dstp['lon'], dstp['lat'], dstp['temperature'],
                         colors='blue', linewidths=2.5, levels=levels_tmp1, transform=latlon_proj)
    ax.clabel(cn_tmp1, cn_tmp1.levels, fontsize=12, inline=True,
              inline_spacing=5, fmt='%i', rightside_up=True, colors='blue')
    # -30℃は紫
    ax.contour(dstp['lon'], dstp['lat'], dstp['temperature'],
               colors='purple', linewidths=2.0, levels=[-30], transform=latlon_proj)

    # W/Cスタンプ（500hPa気温の極大/極小）
    for flag, label, color in [(0, 'W', 'red'), (1, 'C', 'purple')]:
        pid = detect_peaks(dstp['temperature'].values, filter_size=12, dist_cut=2.0, flag=flag)
        for i in range(len(pid[0])):
            wlon = dstp['lon'][pid[1][i]]
            wlat = dstp['lat'][pid[0][i]]
            fig_z, _, _ = transform_lonlat_to_figure((wlon, wlat), ax, proj)
            if 0.05 < fig_z[0] < 0.95 and 0.05 < fig_z[1] < 0.95:
                ax.text(wlon, wlat, label, size=16, color=color,
                        ha='center', va='center', transform=latlon_proj)

    ax.coastlines(resolution='50m', linewidth=1.6)
    xticks = np.arange(0, 360.1, 10)
    yticks = np.arange(-90, 90.1, 10)
    gl = ax.gridlines(crs=ccrs.PlateCarree(), draw_labels=False, linewidth=1, alpha=0.8)
    gl.xlocator = mticker.FixedLocator(xticks)
    gl.ylocator = mticker.FixedLocator(yticks)

    fig.text(0.5, 0.01,
             f"GSM FT{ft_hours:d}h IT:{dt_str} {int(tagTmp)}hPa Tmp, {int(tagTTd)}hPa T-Td",
             ha='center', va='bottom', size=18)

    os.makedirs(output_dir, exist_ok=True)
    out_fn = f"{output_dir}/{dt_str2}_FT{ft_hours:03d}h_GSM_Fax57.png"
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

    print(f"初期時刻: {init_str} UTC  500hPa気温・700hPa湿数")
    print(f"予報時間: FT{ddhh_to_hours(start_ddhh)}h〜FT{ddhh_to_hours(ft_list[-1])}h（{args.n_steps}枚）")
    print()

    success = 0
    for ft_ddhh in ft_list:
        if plot_one(i_year, i_month, i_day, i_hourZ, ft_ddhh, "./output"):
            success += 1
    print(f"\n完了: {success}/{args.n_steps}枚 出力先: ./output/")


if __name__ == "__main__":
    main()
