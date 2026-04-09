#!/usr/bin/env python
# coding: utf-8

# GSM 850hPa Q-vector発散・気温・高度 天気図描画スクリプト
# 元コード: note4.ipynb
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
        description='GSM GRIB2から850hPa Q-vector発散・気温・高度天気図を描画する',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python GSM_QVector850hPa.py 2021082300 0000 1     # 初期値1枚
  python GSM_QVector850hPa.py 2021082300 0000 5     # FT0h〜FT24h 5枚
  python GSM_QVector850hPa.py 2021082300 0100 3 850 # FT24h〜FT36h 3枚
        """
    )
    parser.add_argument('init_time', type=str, help='初期時刻 YYYYMMDDHH（UTC）')
    parser.add_argument('start_ft',  type=str, help='開始予報時間 DDHH形式')
    parser.add_argument('n_steps',   type=int, help='作成する枚数（6h間隔）')
    parser.add_argument('level',     type=int, nargs='?', default=850, help='気圧面 hPa（デフォルト: 850）')
    return parser.parse_args()


def plot_one(i_year, i_month, i_day, i_hourZ, ft_ddhh, tagHp, output_dir):
    ft_hours = ddhh_to_hours(ft_ddhh)

    gsm_fn_t = "Z__C_RJTD_{0:04d}{1:02d}{2:02d}{3:02d}0000_GSM_GPV_Rgl_FD{4:04d}_grib2.bin"
    gr_fn   = gsm_fn_t.format(i_year, i_month, i_day, i_hourZ, ft_ddhh)
    gr_path = f"./data_gsm/{gr_fn}"

    if not ensure_file(gr_path, gr_fn, i_year, i_month, i_day):
        print(f"スキップ: FT={ft_hours}h（データ取得失敗）")
        return False

    print(f"[{ft_hours:4d}h] データ読み込み: {gr_fn}")

    grbs  = pygrib.open(gr_path)
    grbHt = grbs(shortName="gh", typeOfLevel='isobaricInhPa', level=tagHp)[0]
    grbWu = grbs(shortName="u",  typeOfLevel='isobaricInhPa', level=tagHp)[0]
    grbWv = grbs(shortName="v",  typeOfLevel='isobaricInhPa', level=tagHp)[0]
    grbTm = grbs(shortName="t",  typeOfLevel='isobaricInhPa', level=tagHp)[0]
    grbs.close()

    # スムージングパラメータ
    passes  = 16
    passesT = 8
    s_n     = 9

    latS, latN, lonW, lonE = -20, 80, 70, 190
    valHt, latHt, lonHt = grbHt.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)
    valWu, latWu, lonWu = grbWu.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)
    valWv, latWv, lonWv = grbWv.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)
    valTm, latTm, lonTm = grbTm.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)

    # スムージング
    valHt_sm = mpcalc.smooth_n_point(valHt.squeeze(), s_n, passes)  * units("gpm")
    valTm_sm = mpcalc.smooth_n_point(valTm.squeeze(), s_n, passesT) * units("K")

    ds = xr.Dataset(
        {
            "Geopotential_height": (["lat", "lon"], valHt_sm),
            "u_wind":              (["lat", "lon"], valWu),
            "v_wind":              (["lat", "lon"], valWv),
            "Temperature":         (["lat", "lon"], valTm_sm),
        },
        coords={
            "level": [tagHp],
            "lat":   latHt[:, 0],
            "lon":   lonHt[0, :],
            "time":  [grbHt.validDate],
        },
    )
    ds['Geopotential_height'].attrs['units'] = 'm'
    ds['u_wind'].attrs['units']  = 'm/s'
    ds['v_wind'].attrs['units']  = 'm/s'
    ds['Temperature'].attrs['units'] = 'K'
    ds['level'].attrs['units']   = 'hPa'
    ds['lat'].attrs['units']     = 'degrees_north'
    ds['lon'].attrs['units']     = 'degrees_east'

    dsp = ds.metpy.parse_cf()
    dsp['ug'], dsp['vg'] = mpcalc.geostrophic_wind(dsp['Geopotential_height'])
    dsp['u_qv'], dsp['v_qv'] = mpcalc.q_vector(
        dsp['ug'], dsp['vg'], dsp['Temperature'], tagHp * units.hPa)
    dsp['q_div'] = mpcalc.divergence(dsp['u_qv'], dsp['v_qv'])

    dt_i    = grbHt.analDate
    dt_str  = (dt_i.strftime("%H00UTC%d%b%Y")).upper()
    dt_str2 = dt_i.strftime("%Y%m%d%H")

    # 等値線設定
    clevs_qdiv = list(range(-30, -4, 5)) + list(range(-2, 3, 4)) + list(range(5, 31, 5))
    clevs_tmpc = np.arange(-39, 42, 3)
    clevs_hght = np.arange(0, 8000, 30)
    i_area     = [115, 151, 20, 50]

    proj        = ccrs.Stereographic(central_latitude=60, central_longitude=140)
    latlon_proj = ccrs.PlateCarree()
    fig = plt.figure(figsize=(10, 8))
    plt.subplots_adjust(left=0, right=1, bottom=0.06, top=0.98)
    ax = fig.add_subplot(1, 1, 1, projection=proj)
    ax.set_extent(i_area, latlon_proj)
    ax.coastlines(resolution='50m')
    xticks = np.arange(0, 360.1, 10)
    yticks = np.arange(-90, 90.1, 10)
    gl = ax.gridlines(crs=ccrs.PlateCarree(), draw_labels=False, linewidth=1, alpha=0.8)
    gl.xlocator = mticker.FixedLocator(xticks)
    gl.ylocator = mticker.FixedLocator(yticks)

    # Q-vector発散シェード
    cf = ax.contourf(dsp['lon'], dsp['lat'], dsp['q_div'] * 1e18, clevs_qdiv,
                     cmap=plt.cm.bwr_r, extend='both', transform=latlon_proj)
    ax_reld = fig.add_axes([0.1, 0.1, 0.8, 0.02])
    cb = plt.colorbar(cf, orientation='horizontal', shrink=0.74, aspect=40,
                      pad=0.01, cax=ax_reld, ticks=clevs_qdiv)
    cb.set_label('Q-Vector Div. (*10$^{18}$ m s$^{-1}$ kg$^{-1}$)')

    # 気温（灰色破線）
    dsp['Temperature'] = dsp['Temperature'].metpy.convert_units(units.degC)
    cn_tmp = ax.contour(dsp['lon'], dsp['lat'], dsp['Temperature'],
                        colors='gray', alpha=0.6, linestyles='dashed',
                        linewidths=1.2, levels=clevs_tmpc, transform=latlon_proj)
    ax.clabel(cn_tmp, clevs_tmpc, fontsize=15, inline=True,
              inline_spacing=5, fmt='%i', rightside_up=True)

    # 等高度線
    cs = ax.contour(dsp['lon'], dsp['lat'], dsp['Geopotential_height'],
                    clevs_hght, colors='black', transform=latlon_proj)
    plt.clabel(cs, fmt='%d')

    # Q-vector矢印
    wind_slice = (slice(None, None, 3), slice(None, None, 3))
    q = ax.quiver(dsp['lon'][wind_slice[0]], dsp['lat'][wind_slice[1]],
                  dsp['u_qv'].values[wind_slice], dsp['v_qv'].values[wind_slice],
                  pivot='mid', color='black', scale=1e-11, scale_units='inches',
                  transform=latlon_proj)
    ax.quiverkey(q, X=0.82, Y=-0.016, U=1e-11,
                 label='1*10$^{-11}$ m$^{2}$ kg s$^{-1}$', labelpos='E',
                 fontproperties={'size': 11})

    fig.text(0.5, 0.01,
             f"GSM FT{ft_hours:d}h IT:{dt_str} {tagHp}hPa Heights, Temp, Q-Vector, Q-Vector Div",
             ha='center', va='bottom', size=15)

    os.makedirs(output_dir, exist_ok=True)
    out_fn = f"{output_dir}/{dt_str2}_FT{ft_hours:03d}h_{tagHp}hPa_QVec.png"
    plt.savefig(out_fn, dpi=150, bbox_inches='tight')
    print(f"[{ft_hours:4d}h] 出力: {out_fn}")
    plt.show()
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
    tagHp   = args.level

    start_ddhh = int(args.start_ft)
    ft_list    = build_ft_list(start_ddhh, args.n_steps)

    print(f"初期時刻: {init_str} UTC  気圧面: {tagHp}hPa")
    print(f"予報時間: FT{ddhh_to_hours(start_ddhh)}h〜FT{ddhh_to_hours(ft_list[-1])}h（{args.n_steps}枚）")
    print()

    success = 0
    for ft_ddhh in ft_list:
        if plot_one(i_year, i_month, i_day, i_hourZ, ft_ddhh, tagHp, "./output"):
            success += 1
    print(f"\n完了: {success}/{args.n_steps}枚 出力先: ./output/")


if __name__ == "__main__":
    main()
