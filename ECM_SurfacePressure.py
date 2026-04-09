#!/usr/bin/env python
# coding: utf-8

# ECMWF 地上気圧・風・2m気温天気図描画スクリプト
# 元コード: g2e_faxSrfPre_note版.ipynb  (2025/07/23 Ryuta Kurora)
# 修正: 引数対応・自動DL試行・複数FT対応 20260409上原政博
#
# データ取得: ECMWF Open Data（最新5日分）または CDS API（過去データ）
#
# 表示要素: 地上気圧（等圧線）、10m風（矢羽）、2m気温（等温線）
#           オプション: 可降水量シェード(--tcwv)、積算降水量シェード(--tp)

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

ECM_BASE_URL = "https://data.ecmwf.int/forecasts"
HEADERS  = {"User-Agent": "Mozilla/5.0 (compatible; ECM-Downloader/1.0)"}
DATA_DIR = "./data/ecm"


def ensure_file_ecm(ecm_path, ecm_fn, year, month, day, hour):
    if os.path.exists(ecm_path):
        return True
    print(f"ECMWFデータファイルが見つかりません: {ecm_fn}")
    print("ECMWF Open Dataからダウンロードを試みます（最新5日分のみ利用可）...")
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
        description='ECMWF GRIB2から地上気圧・風・2m気温天気図を描画する',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python ECM_SurfacePressure.py 2023052312 0 1          # FT=0h 1枚
  python ECM_SurfacePressure.py 2023052312 0 5          # FT=0,6,12,18,24h 5枚
  python ECM_SurfacePressure.py 2023052312 0 5 --tcwv   # 可降水量シェードあり
  python ECM_SurfacePressure.py 2023052312 6 3 --tp     # 積算降水量シェードあり（FT>0必須）
        """
    )
    parser.add_argument('init_time', type=str,            help='初期時刻 YYYYMMDDHH（UTC）')
    parser.add_argument('start_ft',  type=int, nargs='?', default=0,            help='開始予報時間（時間数）')
    parser.add_argument('n_steps',   type=int, nargs='?', default=1,            help='作成する枚数（6h間隔）')
    parser.add_argument('--tcwv',    action='store_true', help='可降水量（TCWV）シェードを表示する')
    parser.add_argument('--tp',      action='store_true', help='積算降水量シェードを表示する（FT>0のみ有効）')
    return parser.parse_args()


def plot_one(i_year, i_month, i_day, i_hourZ, ft_hours, disp_tcwv, disp_tp, output_dir):
    if i_hourZ in (0, 12):
        ecm_fn = f"{i_year:04d}{i_month:02d}{i_day:02d}{i_hourZ:02d}0000-{ft_hours:d}h-oper-fc.grib2"
    else:
        ecm_fn = f"{i_year:04d}{i_month:02d}{i_day:02d}{i_hourZ:02d}0000-{ft_hours:d}h-scda-fc.grib2"
    ecm_path = f"{DATA_DIR}/{ecm_fn}"

    if not ensure_file_ecm(ecm_path, ecm_fn, i_year, i_month, i_day, i_hourZ):
        print(f"スキップ: FT={ft_hours}h（データ取得失敗）")
        return False

    print(f"[{ft_hours:4d}h] データ読み込み: {ecm_fn}")

    grbs     = pygrib.open(ecm_path)
    grb_msl  = grbs(shortName="msl",  typeOfLevel='meanSea',            level=0)[0]
    grb_10u  = grbs(shortName="10u",  typeOfLevel='heightAboveGround',  level=10)[0]
    grb_10v  = grbs(shortName="10v",  typeOfLevel='heightAboveGround',  level=10)[0]
    grb_2t   = grbs(shortName="2t",   typeOfLevel='heightAboveGround',  level=2)[0]
    grb_tcwv = grbs(shortName="tcwv", typeOfLevel='entireAtmosphere',   level=0)[0]
    if ft_hours > 0:
        grb_tp = grbs(shortName="tp", typeOfLevel='surface', level=0)[0]
    grbs.close()

    valPre,  latPre,  lonPre  = grb_msl.data()
    val10u,  lat10u,  lon10u  = grb_10u.data()
    val10v,  lat10v,  lon10v  = grb_10v.data()
    val2tm,  lat2tm,  lon2tm  = grb_2t.data()
    valTcwv, latTcwv, lonTcwv = grb_tcwv.data()
    if ft_hours > 0:
        valPrc, latPrc, lonPrc = grb_tp.data()

    # データセット構築
    data_vars = {
        "Pre":         (["lat", "lon"], valPre  * 0.01),
        "u_wind":      (["lat", "lon"], val10u),
        "v_wind":      (["lat", "lon"], val10v),
        "Temperature": (["lat", "lon"], val2tm),
        "Tcwv":        (["lat", "lon"], valTcwv),
    }
    if ft_hours > 0:
        data_vars["Precipitation"] = (["lat", "lon"], valPrc * 1000)

    ds = xr.Dataset(
        data_vars,
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
    ds['Tcwv'].attrs['units']        = 'kg/m/m'
    ds['lat'].attrs['units']         = 'degrees_north'
    ds['lon'].attrs['units']         = 'degrees_east'
    if ft_hours > 0:
        ds['Precipitation'].attrs['units'] = 'mm'

    dsp = ds.metpy.parse_cf()

    dt_i    = grb_msl.analDate
    dt_str  = (dt_i.strftime("%H00UTC%d%b%Y")).upper()
    dt_str2 = dt_i.strftime("%Y%m%d%H")

    levels_tmp0  = np.arange(-60, 60,  3)
    levels_pre0  = np.arange(860, 1100,  4)
    levels_pre0B = np.arange(860, 1100, 20)
    i_area = [108, 156, 17, 55]

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

    # 可降水量シェード
    if disp_tcwv:
        tcwv_levels = [0, 1, 5, 10, 20, 30, 40, 50, 60, 70, 80]
        tcwv_colors = ['white', 'cyan', 'palegreen', 'lime', 'yellow', 'orange',
                       'darkorange', 'red', 'mediumpurple', 'darkviolet', 'black']
        tcwv_f = ax.contourf(dsp['lon'], dsp['lat'], dsp['Tcwv'],
                             tcwv_levels, colors=tcwv_colors,
                             alpha=0.4, extend='both', transform=latlon_proj)
        ax.contour(dsp['lon'], dsp['lat'], dsp['Tcwv'],
                   np.arange(10, 200, 10), colors='red', linewidths=1, transform=latlon_proj)
        ax_tcwv = fig.add_axes([0.1, 0.1, 0.8, 0.02])
        cb_tcwv = fig.colorbar(tcwv_f, orientation='horizontal', shrink=0.74,
                               aspect=40, pad=0.01, cax=ax_tcwv)
        cb_tcwv.set_label('TCWV (kg/m/m)')

    # 積算降水量シェード
    if disp_tp and ft_hours > 0:
        prc_levels = [0, 1, 10, 20, 30, 40, 60, 80, 100]
        prc_colors = ['white', 'cyan', 'palegreen', 'lime', 'yellow', 'orange', 'darkorange', 'red']
        prc_f = ax.contourf(dsp['lon'], dsp['lat'], dsp['Precipitation'],
                            prc_levels, colors=prc_colors,
                            alpha=0.4, extend='both', transform=latlon_proj)
        ax.contour(dsp['lon'], dsp['lat'], dsp['Precipitation'],
                   np.arange(10, 200, 10), colors='red', linewidths=1, transform=latlon_proj)
        ax_prc = fig.add_axes([0.1, 0.1, 0.8, 0.02])
        fig.colorbar(prc_f, orientation='horizontal', shrink=0.74,
                     aspect=40, pad=0.01, cax=ax_prc)

    # 2m等温度線
    dsp['Temperature'] = dsp['Temperature'].metpy.convert_units(units.degC)
    ax.contour(dsp['lon'], dsp['lat'], dsp['Temperature'],
               colors='green', alpha=0.5, linewidths=1.0, levels=levels_tmp0,
               transform=latlon_proj)

    # 等圧線（細線）
    ax.contour(dsp['lon'], dsp['lat'], dsp['Pre'],
               colors='black', linewidths=1.0, levels=levels_pre0, transform=latlon_proj)
    # 等圧線（太線 + ラベル）
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

    # タイトル
    if disp_tp and ft_hours > 0:
        title = f"ECM FT{ft_hours:d}h IT:{dt_str} Surface Pre, Wind, Temp, Total Precipitation(FT0-)"
    elif disp_tcwv:
        title = f"ECM FT{ft_hours:d}h IT:{dt_str} Surface Pre, Wind, Temp, Total Column Water vapor"
    else:
        title = f"ECM FT{ft_hours:d}h IT:{dt_str} Surface Pre, Wind, Temp"
    fig.text(0.5, 0.01, title, ha='center', va='bottom', size=15)

    os.makedirs(output_dir, exist_ok=True)
    out_fn = f"{output_dir}/{dt_str2}_FT{ft_hours:03d}h_SurfacePressure.png"
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
    opts = []
    if args.tcwv: opts.append("TCWV")
    if args.tp:   opts.append("TP")
    opt_str = f"  追加要素: {','.join(opts)}" if opts else ""
    print(f"初期時刻: {init_str} UTC  地上気圧・風・2m気温{opt_str}")
    print(f"予報時間: FT{ft_list[0]}h〜FT{ft_list[-1]}h（{args.n_steps}枚）")
    print()

    success = 0
    for ft in ft_list:
        if plot_one(i_year, i_month, i_day, i_hourZ, ft, args.tcwv, args.tp, "./output"):
            success += 1
    print(f"\n完了: {success}/{args.n_steps}枚 出力先: ./output/")


if __name__ == "__main__":
    main()
