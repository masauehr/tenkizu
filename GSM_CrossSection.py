#!/usr/bin/env python
# coding: utf-8

# GSM 鉛直断面図（温位・相当温位・収束発散・風）描画スクリプト
# 元コード: note6.ipynb
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
import cartopy.feature as cfeature
import sys
import argparse
from pathlib import Path
import requests

import metpy.calc as mpcalc
from metpy.interpolate import cross_section
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
        description='GSM GRIB2から鉛直断面図（温位・相当温位・収束発散・風）を描画する',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python GSM_CrossSection.py 2021081318 0000 1                        # 130E経線断面（デフォルト）
  python GSM_CrossSection.py 2021081318 0000 3                        # FT0h〜FT12h 3枚
  python GSM_CrossSection.py 2021081318 0000 1 --lat-s 45 --lat-e 25 --lon-s 130 --lon-e 140

引数説明:
  init_time: 初期時刻 YYYYMMDDHH（UTC）
  start_ft : 開始予報時間 DDHH形式
  n_steps  : 作成する枚数（6h間隔）
  --lat-s  : 断面始点の緯度（デフォルト: 45.0）
  --lat-e  : 断面終点の緯度（デフォルト: 25.0）
  --lon-s  : 断面始点の経度（デフォルト: 130.0）
  --lon-e  : 断面終点の経度（デフォルト: 130.0）
  --flag-wind: 0=断面平行/垂直風, 1=UV風（デフォルト: 1）
        """
    )
    parser.add_argument('init_time',   type=str, help='初期時刻 YYYYMMDDHH（UTC）')
    parser.add_argument('start_ft',    type=str, help='開始予報時間 DDHH形式')
    parser.add_argument('n_steps',     type=int, help='作成する枚数（6h間隔）')
    parser.add_argument('--lat-s',     type=float, default=45.0, dest='lat_start', help='断面始点緯度（デフォルト: 45.0）')
    parser.add_argument('--lat-e',     type=float, default=25.0, dest='lat_end',   help='断面終点緯度（デフォルト: 25.0）')
    parser.add_argument('--lon-s',     type=float, default=130.0, dest='lon_start', help='断面始点経度（デフォルト: 130.0）')
    parser.add_argument('--lon-e',     type=float, default=130.0, dest='lon_end',   help='断面終点経度（デフォルト: 130.0）')
    parser.add_argument('--flag-wind', type=int,   default=1,     dest='flag_wind', help='風の表示方法 0=断面平行/垂直 1=UV風（デフォルト: 1）')
    return parser.parse_args()


def plot_one(i_year, i_month, i_day, i_hourZ, ft_ddhh,
             f_lat_start, f_lat_end, f_lon_start, f_lon_end, flag_wind, output_dir):
    ft_hours = ddhh_to_hours(ft_ddhh)

    gsm_fn_t = "Z__C_RJTD_{0:04d}{1:02d}{2:02d}{3:02d}0000_GSM_GPV_Rgl_FD{4:04d}_grib2.bin"
    gr_fn   = gsm_fn_t.format(i_year, i_month, i_day, i_hourZ, ft_ddhh)
    gr_path = f"./data_gsm/{gr_fn}"

    if not ensure_file(gr_path, gr_fn, i_year, i_month, i_day):
        print(f"スキップ: FT={ft_hours}h（データ取得失敗）")
        return False

    print(f"[{ft_hours:4d}h] データ読み込み: {gr_fn}")

    tagHp  = 100   # 上端気圧面
    topRh  = 300   # 湿度データの上端

    grbs  = pygrib.open(gr_path)
    grbHt = grbs(shortName="gh", typeOfLevel='isobaricInhPa', level=lambda l: l >= tagHp)
    grbWu = grbs(shortName="u",  typeOfLevel='isobaricInhPa', level=lambda l: l >= tagHp)
    grbWv = grbs(shortName="v",  typeOfLevel='isobaricInhPa', level=lambda l: l >= tagHp)
    grbTm = grbs(shortName="t",  typeOfLevel='isobaricInhPa', level=lambda l: l >= tagHp)
    grbRh = grbs(shortName="r",  typeOfLevel='isobaricInhPa', level=lambda l: l >= topRh)
    dt    = grbHt[0].validDate
    grbs.close()

    lats2, lons2 = grbHt[0].latlons()
    lats     = lats2[:, 0]
    lons     = lons2[0, :]
    levels   = np.array([g['level'] for g in grbHt])
    levels_Rh = np.array([g['level'] for g in grbRh])
    indexes   = np.argsort(levels)[::-1]
    indexes_Rh = np.argsort(levels_Rh)[::-1]
    x, y     = grbHt[0].values.shape

    cubeHt = np.zeros([len(levels), x, y])
    cubeWu = np.zeros([len(levels), x, y])
    cubeWv = np.zeros([len(levels), x, y])
    cubeTm = np.zeros([len(levels), x, y])
    cubeRh = np.zeros([len(levels), x, y])
    for i in range(len(levels)):
        cubeHt[i, :, :] = grbHt[indexes[i]].values
        cubeWu[i, :, :] = grbWu[indexes[i]].values
        cubeWv[i, :, :] = grbWv[indexes[i]].values
        cubeTm[i, :, :] = grbTm[indexes[i]].values
    for i in range(len(levels_Rh)):
        cubeRh[i, :, :] = grbRh[indexes_Rh[i]].values

    ds = xr.Dataset(
        {
            "Geopotential_height": (["level", "lat", "lon"], cubeHt * units.meter),
            "temperature":         (["level", "lat", "lon"], cubeTm * units('K')),
            "relative_humidity":   (["level", "lat", "lon"], cubeRh * units('%')),
            "u_wind":              (["level", "lat", "lon"], cubeWu * units('m/s')),
            "v_wind":              (["level", "lat", "lon"], cubeWv * units('m/s')),
        },
        coords={
            "level": levels,
            "lat":   lats,
            "lon":   lons,
            "time":  [grbHt[0].validDate],
        },
    )
    ds['Geopotential_height'].attrs['units'] = 'm'
    ds['temperature'].attrs['units']       = 'K'
    ds['relative_humidity'].attrs['units'] = '%'
    ds['u_wind'].attrs['units']            = 'm/s'
    ds['v_wind'].attrs['units']            = 'm/s'
    ds['level'].attrs['units']             = 'hPa'
    ds['lat'].attrs['units']               = 'degrees_north'
    ds['lon'].attrs['units']               = 'degrees_east'

    ds['dewpoint_temperature'] = mpcalc.dewpoint_from_relative_humidity(
        ds['temperature'], ds['relative_humidity'])
    ds['dewpoint_temperature'].attrs['units'] = 'K'
    ds['divergence'] = mpcalc.divergence(ds['u_wind'], ds['v_wind'])
    ds['dewpoint_temperature'].attrs['units'] = '1/s'
    dsp = ds.metpy.parse_cf()

    # 断面図データセット作成
    start    = (f_lat_start, f_lon_start)
    end      = (f_lat_end,   f_lon_end)
    ax_cross = 'lon' if (f_lat_start - f_lat_end)**2 <= (f_lon_start - f_lon_end)**2 else 'lat'
    cross_ds = cross_section(dsp, start, end)

    cross_ds['Potential_temperature'] = mpcalc.potential_temperature(
        cross_ds['level'] * units.hPa, cross_ds['temperature'])
    cross_ds['Equivalent_Potential_temperature'] = mpcalc.equivalent_potential_temperature(
        cross_ds['level'], cross_ds['temperature'], cross_ds['dewpoint_temperature'])
    cross_ds['u_wind'] = cross_ds['u_wind'].metpy.convert_units('knots')
    cross_ds['v_wind'] = cross_ds['v_wind'].metpy.convert_units('knots')
    cross_ds['t_wind'], cross_ds['n_wind'] = mpcalc.cross_section_components(
        cross_ds['u_wind'], cross_ds['v_wind'])

    dt_str2 = dt.strftime("%Y%m%d%H")

    # 断面図描画
    map_x_y_width_height = [0.1255, 0.572, 0.18, 0.33]
    fig = plt.figure(1, figsize=(16., 9.))
    ax  = plt.axes()

    clevs_div = [-4, -2, -1, 1, 2, 4]
    div_contour = ax.contourf(cross_ds[ax_cross], cross_ds['level'],
                              cross_ds['divergence'] * 1e5,
                              clevs_div, cmap=plt.cm.bwr, extend='both', alpha=0.7)
    fig.colorbar(div_contour)

    # 温位（黒実線）
    theta_contour = ax.contour(cross_ds[ax_cross], cross_ds['level'],
                               cross_ds['Potential_temperature'],
                               levels=np.arange(252, 450, 3), colors='k', linewidths=2)
    theta_contour.clabel(theta_contour.levels[1::2], fontsize=8, colors='k', inline=1,
                         inline_spacing=8, fmt='%i', rightside_up=True, use_clabeltext=True)

    # 相当温位（赤実線）
    etheta_contour = ax.contour(cross_ds[ax_cross], cross_ds['level'],
                                cross_ds['Equivalent_Potential_temperature'],
                                levels=np.arange(252, 450, 3), colors='r', linewidths=1)
    etheta_contour.clabel(etheta_contour.levels[1::2], fontsize=8, colors='r', inline=1,
                          inline_spacing=8, fmt='%i', rightside_up=True, use_clabeltext=True)

    # 断面平行風速（青実線）
    v_contour = ax.contour(cross_ds[ax_cross], cross_ds['level'],
                           cross_ds['t_wind'],
                           levels=np.arange(-100, 100, 5), colors='b', linewidths=1)
    v_contour.clabel(v_contour.levels[1::2], fontsize=8, colors='b', inline=1,
                     inline_spacing=8, fmt='%i', rightside_up=True, use_clabeltext=True)

    # 風矢羽
    wind_slc_vert = list(range(0, len(levels), 1))
    wind_slc_horz = slice(5, 100, 2)
    if flag_wind == 0:
        ax.barbs(cross_ds[ax_cross][wind_slc_horz], cross_ds['level'][wind_slc_vert],
                 cross_ds['t_wind'][wind_slc_vert, wind_slc_horz],
                 cross_ds['n_wind'][wind_slc_vert, wind_slc_horz], color='k')
    else:
        ax.barbs(cross_ds[ax_cross][wind_slc_horz], cross_ds['level'][wind_slc_vert],
                 cross_ds['u_wind'][wind_slc_vert, wind_slc_horz],
                 cross_ds['v_wind'][wind_slc_vert, wind_slc_horz], color='k')

    ax.set_yscale('symlog')
    ax.set_yticklabels(np.arange(1000, 200, -100))
    ax.set_ylim(cross_ds['level'].max(), 100.0)
    ax.set_yticks(np.arange(1000, 290, -100))

    # 左上の小地図（500hPa高度 + 断面位置）
    data_crs  = dsp['Geopotential_height'].metpy.cartopy_crs
    ax_inset  = fig.add_axes(map_x_y_width_height, projection=data_crs)
    ax_inset.set_extent((121.0, 151.0, 22.0, 48.0))
    ax_inset.contour(ds['lon'], ds['lat'], ds['Geopotential_height'].sel(level=500.),
                     levels=np.arange(5100, 6000, 30), cmap='inferno')
    endpoints = data_crs.transform_points(
        ccrs.Geodetic(), *np.vstack([start, end]).transpose()[::-1])
    ax_inset.scatter(endpoints[:, 0], endpoints[:, 1], c='k', zorder=2)
    ax_inset.plot(cross_ds['lon'], cross_ds['lat'], c='k', zorder=2)
    ax_inset.coastlines()
    ax_inset.set_title('')

    wind_label = 'Tangential/Normal Winds' if flag_wind == 0 else 'Winds'
    ax.set_title(
        f'GSM Cross-Section \u2013 {start} to {end} \u2013 Valid: {dt.strftime("%Y-%m-%d %H:%MZ")}\n'
        f'FT={ft_hours}h  Potential Temp (K), EPT (K), Tangent Wind Speed (knots), {wind_label} (knots), Divergence\n'
        'Inset: Cross-Section Path and 500 hPa Geopotential Height')
    ax.set_ylabel('Pressure (hPa)')
    ax.set_xlabel('Longitude (degrees east)')

    os.makedirs(output_dir, exist_ok=True)
    out_fn = f"{output_dir}/{dt_str2}_FT{ft_hours:03d}h_CrossSection.png"
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

    print(f"初期時刻: {init_str} UTC")
    print(f"断面: ({args.lat_start}N, {args.lon_start}E) → ({args.lat_end}N, {args.lon_end}E)")
    print(f"予報時間: FT{ddhh_to_hours(start_ddhh)}h〜FT{ddhh_to_hours(ft_list[-1])}h（{args.n_steps}枚）")
    print()

    success = 0
    for ft_ddhh in ft_list:
        if plot_one(i_year, i_month, i_day, i_hourZ, ft_ddhh,
                    args.lat_start, args.lat_end, args.lon_start, args.lon_end,
                    args.flag_wind, "./output"):
            success += 1
    print(f"\n完了: {success}/{args.n_steps}枚 出力先: ./output/")


if __name__ == "__main__":
    main()
