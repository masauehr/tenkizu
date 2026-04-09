#!/usr/bin/env python
# coding: utf-8

# GSM 不安定域分布（飽和相当温位 - 下層最大相当温位差・上層気温）天気図描画スクリプト
# 元コード: note8.ipynb
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
        description='GSM GRIB2から不安定域分布（SEPT-maxEPT差・上層気温）天気図を描画する',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python GSM_Instability.py 2021081318 0000 1          # 初期値1枚
  python GSM_Instability.py 2021081318 0000 5          # FT0h〜FT24h 5枚
  python GSM_Instability.py 2021081318 0000 1 300 850  # 上層300hPa・下層850hPa指定

引数説明:
  init_time: 初期時刻 YYYYMMDDHH（UTC）
  start_ft : 開始予報時間 DDHH形式
  n_steps  : 作成する枚数（6h間隔）
  pre_top  : 上層気圧面 hPa（省略可、デフォルト: 300）
  pre_low  : 下層Top気圧面 hPa（省略可、デフォルト: 850）
        """
    )
    parser.add_argument('init_time', type=str, help='初期時刻 YYYYMMDDHH（UTC）')
    parser.add_argument('start_ft',  type=str, nargs='?', default='0000', help='開始予報時間 DDHH形式')
    parser.add_argument('n_steps',   type=int, nargs='?', default=1, help='作成する枚数（6h間隔）')
    parser.add_argument('pre_top',   type=int, nargs='?', default=300, help='上層気圧面 hPa（デフォルト: 300）')
    parser.add_argument('pre_low',   type=int, nargs='?', default=850, help='下層Top気圧面 hPa（デフォルト: 850）')
    return parser.parse_args()


def plot_one(i_year, i_month, i_day, i_hourZ, ft_ddhh, preTop, preLow, output_dir):
    ft_hours = ddhh_to_hours(ft_ddhh)

    gsm_fn_t = "Z__C_RJTD_{0:04d}{1:02d}{2:02d}{3:02d}0000_GSM_GPV_Rgl_FD{4:04d}_grib2.bin"
    gr_fn   = gsm_fn_t.format(i_year, i_month, i_day, i_hourZ, ft_ddhh)
    gr_path = f"./data_gsm/{gr_fn}"

    if not ensure_file(gr_path, gr_fn, i_year, i_month, i_day):
        print(f"スキップ: FT={ft_hours}h（データ取得失敗）")
        return False

    print(f"[{ft_hours:4d}h] データ読み込み: {gr_fn}")

    grbs  = pygrib.open(gr_path)
    # preLow以下 または preTopのデータを一括読み込み
    grbHt = grbs(shortName="gh", typeOfLevel='isobaricInhPa',
                 level=lambda l: l >= preLow or l == preTop)
    grbTm = grbs(shortName="t",  typeOfLevel='isobaricInhPa',
                 level=lambda l: l >= preLow or l == preTop)
    grbRh = grbs(shortName="r",  typeOfLevel='isobaricInhPa',
                 level=lambda l: l >= preLow or l == preTop)
    dt_i    = grbHt[0].analDate
    grbs.close()

    # 3次元データ化
    lats2, lons2 = grbHt[0].latlons()
    lats   = lats2[:, 0]
    lons   = lons2[0, :]
    levels = np.array([g['level'] for g in grbHt])
    indexes = np.argsort(levels)[::-1]
    x, y   = grbHt[0].values.shape

    cubeHt = np.zeros([len(levels), x, y])
    cubeTm = np.zeros([len(levels), x, y])
    cubeRh = np.zeros([len(levels), x, y])
    for i in range(len(levels)):
        cubeHt[i, :, :] = grbHt[indexes[i]].values
        cubeTm[i, :, :] = grbTm[indexes[i]].values
        cubeRh[i, :, :] = grbRh[indexes[i]].values

    ds = xr.Dataset(
        {
            "Geopotential_height": (["level", "lat", "lon"], cubeHt * units.meter),
            "temperature":         (["level", "lat", "lon"], cubeTm * units('K')),
            "relative_humidity":   (["level", "lat", "lon"], cubeRh * units('%')),
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
    ds['level'].attrs['units']             = 'hPa'
    ds['lat'].attrs['units']               = 'degrees_north'
    ds['lon'].attrs['units']               = 'degrees_east'

    # 露点温度・相当温位・飽和相当温位を計算
    ds['dewpoint_temperature'] = mpcalc.dewpoint_from_relative_humidity(
        ds['temperature'], ds['relative_humidity'])
    ds['dewpoint_temperature'].attrs['units'] = 'K'
    ds['ept']  = mpcalc.equivalent_potential_temperature(
        ds['level'] * units('hPa'), ds['temperature'], ds['dewpoint_temperature'])
    ds['ept'].attrs['units']  = 'K'
    ds['sept'] = mpcalc.saturation_equivalent_potential_temperature(
        ds['level'], ds['temperature'])
    ds['sept'].attrs['units'] = 'K'

    # 下層の最大EPTをds['ept'][0]に代入
    for i in np.arange(len(levels) - 2):
        for j in np.arange(len(lats)):
            for k in np.arange(len(lons)):
                e0 = ds['ept'][0].values[j][k]
                e1 = ds['ept'][i + 1].values[j][k]
                if e1 > e0:
                    ds['ept'][0].values[j][k] = e1

    dsp = ds.metpy.parse_cf()

    dt_str  = (dt_i.strftime("%H00UTC%d%b%Y")).upper()
    dt_str2 = dt_i.strftime("%Y%m%d%H")
    areaAry = [115, 151, 20, 50]

    proj        = ccrs.Stereographic(central_latitude=60, central_longitude=140)
    latlon_proj = ccrs.PlateCarree()
    fig = plt.figure(figsize=(10, 8))
    plt.subplots_adjust(left=0, right=1, bottom=0.06, top=0.98)
    ax = fig.add_subplot(1, 1, 1, projection=proj)
    ax.set_extent(areaAry, latlon_proj)

    # SEPT[preTop] - maxEPT シェード
    cnf_dept = ax.contourf(dsp['lon'], dsp['lat'],
                           dsp['sept'][len(levels) - 1] - dsp['ept'][0],
                           np.arange(-12, 12, 3), cmap="jet_r", extend='both',
                           transform=latlon_proj)
    ax_ept = fig.add_axes([0.1, 0.1, 0.8, 0.02])
    fig.colorbar(cnf_dept, orientation='horizontal', shrink=0.74,
                 aspect=40, pad=0.01, cax=ax_ept)

    # 上層気温（赤一点鎖線）
    levels_tmp = np.arange(-60, 30, 3)
    cn_tmpTop = ax.contour(dsp['lon'], dsp['lat'],
                           dsp['temperature'][len(levels) - 1] - 273.15 * units('K'),
                           colors='red', linewidths=1.0, linestyles='dashdot',
                           levels=levels_tmp, transform=latlon_proj)
    ax.clabel(cn_tmpTop, levels_tmp, fontsize=12, inline=True,
              inline_spacing=5, colors='red', fmt='%i', rightside_up=True)

    ax.coastlines(resolution='50m')
    xticks = np.arange(0, 360.1, 10)
    yticks = np.arange(-90, 90.1, 10)
    gl = ax.gridlines(crs=ccrs.PlateCarree(), draw_labels=False, linewidth=1, alpha=0.8)
    gl.xlocator = mticker.FixedLocator(xticks)
    gl.ylocator = mticker.FixedLocator(yticks)

    fig.text(0.5, 0.01,
             f"GSM FT{ft_hours:d}h IT:{dt_str} {int(preTop)}hPa Tmp, SEPT[{int(preTop)}] - maxEPT[{int(preLow)}-1000]",
             ha='center', va='bottom', size=15)

    os.makedirs(output_dir, exist_ok=True)
    out_fn = f"{output_dir}/{dt_str2}_FT{ft_hours:03d}h_Instability.png"
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

    print(f"初期時刻: {init_str} UTC  上層: {args.pre_top}hPa  下層Top: {args.pre_low}hPa")
    print(f"予報時間: FT{ddhh_to_hours(start_ddhh)}h〜FT{ddhh_to_hours(ft_list[-1])}h（{args.n_steps}枚）")
    print()

    success = 0
    for ft_ddhh in ft_list:
        if plot_one(i_year, i_month, i_day, i_hourZ, ft_ddhh, args.pre_top, args.pre_low, "./output"):
            success += 1
    print(f"\n完了: {success}/{args.n_steps}枚 出力先: ./output/")


if __name__ == "__main__":
    main()
