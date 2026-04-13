#!/usr/bin/env python
# coding: utf-8

# GSM FAX図 FXFE7854/7856相当: 700hPa収束・発散・850hPa気温・風 天気図描画スクリプト
# 元コード: g2e_fax78_note版.ipynb  (2023/07/23 Ryuta Kurora)
# 修正: GSM GRIB2対応・引数対応・自動DL試行・複数FT対応 20260412上原政博
#
# データ取得: 京都大学RISHサーバー（全球GSM GRIB2）
# 注意: 発散は700hPa u,v風速成分から mpcalc.divergence() で計算する

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
        description='GSM GRIB2からFAX78相当: 700hPa収束・発散・850hPa気温・風天気図を描画する',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python GSM_fax78.py 2021082300           # FT=0h 1枚
  python GSM_fax78.py 2021082300 0000 5   # FT=0,6,12,18,24h 5枚
  python GSM_fax78.py 2021082300 0100 3   # FT=24,30,36h 3枚
        """
    )
    parser.add_argument('init_time',    type=str, help='初期時刻 YYYYMMDDHH（UTC）')
    parser.add_argument('start_ft',     type=str, nargs='?', default='0000',
                        help='開始予報時間 DDHH形式（デフォルト: 0000）')
    parser.add_argument('n_steps',      type=int, nargs='?', default=1,
                        help='作成する枚数（6h間隔、デフォルト: 1）')
    parser.add_argument('--level-div',  type=int, default=700,
                        help='発散気圧面 hPa（デフォルト: 700）')
    parser.add_argument('--level-t',    type=int, default=850,
                        help='気温・風気圧面 hPa（デフォルト: 850）')
    return parser.parse_args()


def plot_one(i_year, i_month, i_day, i_hourZ, ft_ddhh, tagHpDiv, tagHp, output_dir):
    ft_hours = ddhh_to_hours(ft_ddhh)

    gsm_fn  = f"Z__C_RJTD_{i_year:04d}{i_month:02d}{i_day:02d}{i_hourZ:02d}0000_GSM_GPV_Rgl_FD{ft_ddhh:04d}_grib2.bin"
    gr_path = f"./data_gsm/{gsm_fn}"

    if not ensure_file(gr_path, gsm_fn, i_year, i_month, i_day):
        print(f"スキップ: FT={ft_hours}h（データ取得失敗）")
        return False

    print(f"[{ft_hours:4d}h] データ読み込み: {gsm_fn}")

    grbs   = pygrib.open(gr_path)
    grbWu850 = grbs(shortName="u", typeOfLevel='isobaricInhPa', level=tagHp)[0]
    grbWv850 = grbs(shortName="v", typeOfLevel='isobaricInhPa', level=tagHp)[0]
    grbTm850 = grbs(shortName="t", typeOfLevel='isobaricInhPa', level=tagHp)[0]
    grbWu700 = grbs(shortName="u", typeOfLevel='isobaricInhPa', level=tagHpDiv)[0]
    grbWv700 = grbs(shortName="v", typeOfLevel='isobaricInhPa', level=tagHpDiv)[0]
    grbs.close()

    latS, latN, lonW, lonE = -20, 80, 70, 190
    valWu850, latWu850, lonWu850 = grbWu850.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)
    valWv850, latWv850, lonWv850 = grbWv850.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)
    valTm850, latTm850, lonTm850 = grbTm850.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)
    valWu700, latWu700, lonWu700 = grbWu700.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)
    valWv700, latWv700, lonWv700 = grbWv700.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)

    # 700hPa u,v から発散を計算
    ds700 = xr.Dataset(
        {
            "u_wind": (["lat", "lon"], valWu700 * units('m/s')),
            "v_wind": (["lat", "lon"], valWv700 * units('m/s')),
        },
        coords={
            "lat": latWu700[:, 0] * units('degrees_north'),
            "lon": lonWu700[0, :] * units('degrees_east'),
        },
    )
    ds700['u_wind'].attrs['units'] = 'm/s'
    ds700['v_wind'].attrs['units'] = 'm/s'
    ds700['lat'].attrs['units']    = 'degrees_north'
    ds700['lon'].attrs['units']    = 'degrees_east'
    ds700p = ds700.metpy.parse_cf()

    valDiv = mpcalc.divergence(ds700p['u_wind'], ds700p['v_wind'])

    # 発散のスムージング
    passes, s_n = 16, 9
    valDiv_sm = mpcalc.smooth_n_point(np.array(valDiv).squeeze(), s_n, passes)

    # 850hPaデータセット
    ds = xr.Dataset(
        {
            "u_wind":      (["lat", "lon"], valWu850 * units('m/s')),
            "v_wind":      (["lat", "lon"], valWv850 * units('m/s')),
            "Temperature": (["lat", "lon"], valTm850 * units('K')),
            "div":         (["lat", "lon"], valDiv_sm),
        },
        coords={
            "time":  np.array([grbTm850.validDate]),
            "level": np.array(tagHp) * units.hPa,
            "lat":   np.array(latTm850[:, 0]) * units('degrees_north'),
            "lon":   np.array(lonTm850[0, :]) * units('degrees_east'),
        },
    )
    ds['u_wind'].attrs['units']      = 'm/s'
    ds['v_wind'].attrs['units']      = 'm/s'
    ds['Temperature'].attrs['units'] = 'K'
    ds['div'].attrs['units']         = '/s'
    ds['level'].attrs['units']       = 'hPa'
    ds['lat'].attrs['units']         = 'degrees_north'
    ds['lon'].attrs['units']         = 'degrees_east'

    dsp = ds.metpy.parse_cf()

    dt_i    = grbTm850.analDate
    dt_str  = (dt_i.strftime("%H00UTC%d%b%Y")).upper()
    dt_str2 = dt_i.strftime("%Y%m%d%H")

    levels_tmp0      = np.arange(-60, 42,  3)
    levels_tmp1      = np.arange(-60, 42, 15)
    levels_div_hat   = [-20, -10, -5, -2, 2, 5, 10]
    levels_div_color = ['red', 'orange', 'gray', 'white', 'yellow', 'skyblue']
    i_area = [108, 156, 17, 55]

    proj        = ccrs.Stereographic(central_latitude=60, central_longitude=140)
    latlon_proj = ccrs.PlateCarree()
    fig = plt.figure(figsize=(10, 8))
    plt.subplots_adjust(left=0, right=1, bottom=0.06, top=0.98)
    ax = fig.add_subplot(1, 1, 1, projection=proj)
    ax.set_extent(i_area, latlon_proj)

    # 収束・発散シェード（contourf バグ回避: 値をレベル範囲内にクリップ）
    div_ary = np.array(dsp['div'].values) * 1e5
    max_level, min_level = max(levels_div_hat), min(levels_div_hat)
    div_ary = np.clip(div_ary, min_level, max_level)

    cn_div = ax.contourf(dsp['lon'], dsp['lat'], div_ary,
                         levels_div_hat, colors=levels_div_color,
                         alpha=0.5, extend='both', transform=latlon_proj)
    ax_div = fig.add_axes([0.1, 0.1, 0.8, 0.02])
    cb = fig.colorbar(cn_div, orientation='horizontal', shrink=0.74, aspect=40,
                      pad=0.01, cax=ax_div, ticks=levels_div_hat)
    cb.set_label('Divergence (*10$^{-5}$ s$^{-1}$)')

    # 850hPa等温度線（青、3℃間隔）
    dsp['Temperature'] = dsp['Temperature'].metpy.convert_units(units.degC)
    cn_tmp0 = ax.contour(dsp['lon'], dsp['lat'], dsp['Temperature'],
                         colors='blue', linewidths=1.0, levels=levels_tmp0, transform=latlon_proj)
    ax.clabel(cn_tmp0, levels_tmp0, fontsize=8, inline=True,
              inline_spacing=5, fmt='%i', rightside_up=True, colors='blue')
    # 850hPa等温度線（青、太線15℃間隔）
    cn_tmp1 = ax.contour(dsp['lon'], dsp['lat'], dsp['Temperature'],
                         colors='blue', linewidths=2.0, levels=levels_tmp1, transform=latlon_proj)
    ax.clabel(cn_tmp1, levels_tmp1, fontsize=12, inline=True,
              inline_spacing=5, fmt='%i', rightside_up=True, colors='blue')

    # W/Cスタンプ（850hPa気温の極大/極小）
    for flag, label, color in [(0, 'W', 'red'), (1, 'C', 'blue')]:
        pid = detect_peaks(dsp['Temperature'].values, filter_size=10, dist_cut=8.0, flag=flag)
        for i in range(len(pid[0])):
            wlon = dsp['lon'][pid[1][i]]
            wlat = dsp['lat'][pid[0][i]]
            fig_z, _, _ = transform_lonlat_to_figure((wlon, wlat), ax, proj)
            if 0.05 < fig_z[0] < 0.95 and 0.05 < fig_z[1] < 0.95:
                ax.text(wlon, wlat, label, size=16, color=color,
                        ha='center', va='center', transform=latlon_proj)

    # 850hPa風矢羽
    wind_slice = (slice(None, None, 5), slice(None, None, 5))
    ax.barbs(dsp['lon'][wind_slice[0]], dsp['lat'][wind_slice[1]],
             dsp['u_wind'].values[wind_slice] * 1.944,
             dsp['v_wind'].values[wind_slice] * 1.944,
             length=5.5, pivot='middle', color='black', transform=latlon_proj)

    ax.coastlines(resolution='50m', linewidth=1.6)
    xticks = np.arange(0, 360.1, 10)
    yticks = np.arange(-90, 90.1, 10)
    gl = ax.gridlines(crs=ccrs.PlateCarree(), draw_labels=False, linewidth=1, alpha=0.8)
    gl.xlocator = mticker.FixedLocator(xticks)
    gl.ylocator = mticker.FixedLocator(yticks)

    fig.text(0.5, 0.01,
             f"GSM FT{ft_hours:d}h IT:{dt_str} {int(tagHp)}hPa Tmp, Wind  {int(tagHpDiv)}hPa Divergence(/s)",
             ha='center', va='bottom', size=15)

    os.makedirs(output_dir, exist_ok=True)
    out_fn = f"{output_dir}/{dt_str2}_FT{ft_hours:03d}h_GSM_Fax78.png"
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

    print(f"初期時刻: {init_str} UTC  {args.level_div}hPa収束・発散 / {args.level_t}hPa気温・風")
    print(f"予報時間: FT{ddhh_to_hours(start_ddhh)}h〜FT{ddhh_to_hours(ft_list[-1])}h（{args.n_steps}枚）")
    print()

    success = 0
    for ft_ddhh in ft_list:
        if plot_one(i_year, i_month, i_day, i_hourZ, ft_ddhh,
                    args.level_div, args.level_t, "./output"):
            success += 1
    print(f"\n完了: {success}/{args.n_steps}枚 出力先: ./output/")


if __name__ == "__main__":
    main()
