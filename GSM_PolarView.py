#!/usr/bin/env python
# coding: utf-8

# GSM 北半球極座標天気図描画スクリプト
# NorthPolarStereo 投影（北極中心）で等高度線・風速シェードを描画する
# ジェット気流の蛇行（ブロッキング・トラフ・リッジ）確認用
# 対応気圧面: 200, 250, 300, 500, 700, 850 hPa
# 20260611 上原政博

import os
os.environ['PROJ_LIB'] = '/opt/anaconda3/envs/met_env_310/share/proj'  # ★importの前に設定！

from pyproj import datadir
datadir.set_data_dir(os.environ['PROJ_LIB'])

import pygrib
import matplotlib
# macOS のヒラギノフォントを優先し、日本語文字が豆腐にならないようにする
matplotlib.rcParams['font.family'] = ['Hiragino Sans', 'Hiragino Maru Gothic Pro',
                                       'AppleGothic', 'sans-serif']
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.colors as mcolors
import matplotlib.lines as mlines
import numpy as np
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from cartopy.util import add_cyclic_point
import sys
import argparse
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
import requests
import xarray as xr
from scipy.ndimage import maximum_filter, minimum_filter

BASE_URL = "http://database.rish.kyoto-u.ac.jp/arch/jmadata/data/gpv/original"
HEADERS  = {"User-Agent": "Mozilla/5.0 (compatible; GSM-Downloader/1.0)"}
GSM_FN_T = "Z__C_RJTD_{year:04d}{month:02d}{day:02d}{hour:02d}0000_GSM_GPV_Rgl_FD{ft:04d}_grib2.bin"

# 気圧面別の等高度線設定 (最小値, 最大値, 細線間隔, 太線間隔) [m]
HGT_SETTINGS = {
    200: dict(cmin=11400, cmax=12900, ci=60, ci_thick=300),
    250: dict(cmin=10200, cmax=11700, ci=60, ci_thick=300),
    300: dict(cmin= 8700, cmax=10200, ci=60, ci_thick=300),
    500: dict(cmin= 4800, cmax= 6000, ci=60, ci_thick=300),
    700: dict(cmin= 2700, cmax= 3300, ci=30, ci_thick=150),
    850: dict(cmin= 1200, cmax= 1800, ci=30, ci_thick=150),
}

# 気圧面別の気温コンター設定 (最小値, 最大値) [°C]  ※間隔は --temp-ci で上書き可
TEMP_SETTINGS = {
    200: dict(tmin=-80, tmax=-20),
    250: dict(tmin=-75, tmax=-20),
    300: dict(tmin=-70, tmax=-15),
    500: dict(tmin=-55, tmax= 10),
    700: dict(tmin=-40, tmax= 25),
    850: dict(tmin=-25, tmax= 35),
}
TEMP_CI_DEFAULT = 3  # デフォルト気温間隔 [°C]

# 気圧面別の風速シェード設定 (最小値, 最大値, ステップ) [m/s]
WIND_SETTINGS = {
    200: (20, 130, 10),
    250: (20, 120, 10),
    300: (20, 100, 10),
    500: (10,  60, 10),
    700: ( 5,  40,  5),
    850: ( 5,  30,  5),
}


# ---------------------------------------------------------------------------
# ユーティリティ
# ---------------------------------------------------------------------------

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

def build_ft_list(start_ddhh, n_steps, interval_h=6):
    start_h = ddhh_to_hours(start_ddhh)
    return [hours_to_ddhh(start_h + i * interval_h) for i in range(n_steps)]


# ---------------------------------------------------------------------------
# データ読み込み
# ---------------------------------------------------------------------------

def load_field(dt, ft_ddhh, level_hpa, lat_min):
    """GRIBから1タイムステップ分の高度・風速データを読み込む。失敗時は None。"""
    gr_fn   = GSM_FN_T.format(year=dt.year, month=dt.month, day=dt.day,
                               hour=dt.hour, ft=ft_ddhh)
    gr_path = f"./data_gsm/{gr_fn}"
    if not ensure_file(gr_path, gr_fn, dt.year, dt.month, dt.day):
        return None

    print(f"  読み込み: {gr_fn}")
    grbs  = pygrib.open(gr_path)
    grbHt = grbs(shortName="gh", typeOfLevel='isobaricInhPa', level=level_hpa)[0]
    grbWu = grbs(shortName="u",  typeOfLevel='isobaricInhPa', level=level_hpa)[0]
    grbWv = grbs(shortName="v",  typeOfLevel='isobaricInhPa', level=level_hpa)[0]
    grbT  = grbs(shortName="t",  typeOfLevel='isobaricInhPa', level=level_hpa)[0]
    grbs.close()

    valHt, latArr, lonArr = grbHt.data(lat1=lat_min, lat2=90, lon1=0, lon2=360)
    valWu, _,      _      = grbWu.data(lat1=lat_min, lat2=90, lon1=0, lon2=360)
    valWv, _,      _      = grbWv.data(lat1=lat_min, lat2=90, lon1=0, lon2=360)
    valT,  _,      _      = grbT.data( lat1=lat_min, lat2=90, lon1=0, lon2=360)

    return {
        'valHt':     valHt,
        'valT':      valT - 273.15,   # K → ℃
        'wind':      np.sqrt(valWu**2 + valWv**2),
        'lats':      latArr[:, 0],
        'lons':      lonArr[0, :],
        'analDate':  grbHt.analDate,
        'validDate': grbHt.validDate,
    }


# ---------------------------------------------------------------------------
# 描画
# ---------------------------------------------------------------------------

def make_anom_cmap():
    """高度偏差用カラーマップ（青←負偏差 / 白=平年並み / 正偏差→赤）"""
    colors = [
        '#6699EE',  # 青紫（大負偏差）
        '#55AAFF',  # 青
        '#88CCFF',  # 中青
        '#BBDDFF',  # 薄青
        '#DDEEFF',  # 極薄青
        '#FFFFFF',  # 白（平年並み）
        '#FFF5CC',  # 極薄黄
        '#FFE080',  # 黄
        '#FFBB55',  # 橙
        '#FF7744',  # 赤橙
        '#EE4422',  # 赤（大正偏差）
    ]
    return mcolors.LinearSegmentedColormap.from_list('anom_hgt', colors, N=256)


def load_climo_hgt(month, level_hpa, lat_min, climo_dir):
    """NCEP LTM から対象月・気圧面の高度平年値を読み込む。
    Returns: xr.DataArray(lat, lon) — lat 昇順・lon 0〜360°
    """
    nc_path = Path(climo_dir) / "hgt.mon.ltm.1991-2020.nc"
    if not nc_path.exists():
        raise FileNotFoundError(
            f"平年値ファイルが見つかりません: {nc_path}\n"
            "  先に python make_ncep_climo.py を実行してください。"
        )
    try:
        ds = xr.open_dataset(nc_path, engine='netcdf4')
    except ImportError:
        raise ImportError(
            "netcdf4 が見つかりません。以下を実行してください:\n"
            "  conda install -n met_env_310 netcdf4"
        )
    da = (ds['hgt']
          .isel(time=month - 1)
          .sel(level=level_hpa, method='nearest'))
    ds.close()
    # lat を昇順に並べ直し、lat_min 以北に絞る
    da = da.sortby('lat').sel(lat=slice(lat_min, 90))
    return da


def make_wind_cmap():
    """ジェット風速用カラーマップ（白→水色→青→緑→黄→橙→赤）"""
    clist = [
        (1.00, 1.00, 1.00),
        (0.70, 0.95, 1.00),
        (0.20, 0.80, 1.00),
        (0.00, 0.55, 1.00),
        (0.20, 0.75, 0.30),
        (1.00, 1.00, 0.10),
        (1.00, 0.70, 0.00),
        (1.00, 0.40, 0.00),
        (1.00, 0.00, 0.00),
        (0.60, 0.00, 0.00),
    ]
    return mcolors.LinearSegmentedColormap.from_list('wind_polar', clist, N=256)


def find_extrema(data, size=50):
    """高度・気温場の局所極大・極小の格子インデックスを返す。
    size: 近傍サイズ（格子数）。GSM 1.25度格子では size=30 ≈ 37度近傍。
    Returns: (maxima_idx, minima_idx) — shape (N,2) の ndarray (row, col)
    """
    pad = size // 2 + 1
    mx = maximum_filter(data, size=size)
    mn = minimum_filter(data, size=size)
    maxima = (data == mx)
    minima = (data == mn)
    # 端のアーティファクトを除去
    maxima[:pad, :] = False;  maxima[-pad:, :] = False
    minima[:pad, :] = False;  minima[-pad:, :] = False
    return np.argwhere(maxima), np.argwhere(minima)


def draw_and_save(valHt, wind, lats, lons, level_hpa, lat_min, central_lon,
                  no_wind, title_line1, title_line2, out_path, climo_da=None, valT=None,
                  temp_ci=None, hl_size=50):
    """平均化済みデータから天気図を描画してファイルに保存する。
    climo_da が指定されれば風速シェードの代わりに高度偏差シェードを描画する。
    """
    hcfg = HGT_SETTINGS.get(level_hpa, HGT_SETTINGS[500])
    wcfg = WIND_SETTINGS.get(level_hpa, WIND_SETTINGS[300])

    lev_hgt  = np.arange(hcfg['cmin'], hcfg['cmax'] + 1,        hcfg['ci'])
    lev_hgt2 = np.arange(hcfg['cmin'], hcfg['cmax'] + 1, hcfg['ci_thick'])
    wmin, wmax, wstep = wcfg
    lev_wind = np.arange(wmin, wmax + 1, wstep)

    valHt_c, lons_c = add_cyclic_point(valHt, coord=lons)
    wind_c,  _      = add_cyclic_point(wind,  coord=lons)

    proj    = ccrs.NorthPolarStereo(central_longitude=central_lon)
    ll_proj = ccrs.PlateCarree()

    fig = plt.figure(figsize=(10, 10))
    plt.subplots_adjust(left=0.02, right=0.98, bottom=0.08, top=0.93)
    ax = fig.add_subplot(1, 1, 1, projection=proj)
    ax.set_extent([-180, 180, lat_min, 90], crs=ll_proj)

    ax.add_feature(cfeature.OCEAN, facecolor='#D8EFFC', zorder=0)
    ax.add_feature(cfeature.LAND,  facecolor='#F5F2E8', zorder=0)

    if climo_da is not None:
        # 高度偏差シェーディング（NCEP LTM との差）
        climo_interp = climo_da.interp(
            lat=xr.DataArray(lats, dims='lat'),
            lon=xr.DataArray(lons, dims='lon'),
            method='linear',
        ).values
        anom   = valHt - climo_interp
        anom_c, _ = add_cyclic_point(anom, coord=lons)
        lev_anom  = np.arange(-120, 121, 30)
        cmap_a = make_anom_cmap()
        norm_a = mcolors.BoundaryNorm(lev_anom, ncolors=cmap_a.N, clip=True)
        cf = ax.contourf(lons_c, lats, anom_c, levels=lev_anom,
                         cmap=cmap_a, norm=norm_a, transform=ll_proj,
                         extend='both', alpha=0.65, zorder=1)
        cbar = plt.colorbar(cf, ax=ax, orientation='horizontal',
                            pad=0.03, shrink=0.65, aspect=35)
        cbar.set_label(f'{level_hpa} hPa 高度偏差 [m]  (vs NCEP LTM 1991-2020)', fontsize=11)
        cbar.set_ticks(lev_anom)
        cbar.ax.tick_params(labelsize=9)

    elif not no_wind:
        cmap = make_wind_cmap()
        norm = mcolors.BoundaryNorm(lev_wind, ncolors=cmap.N, extend='max')
        cf   = ax.contourf(lons_c, lats, wind_c, levels=lev_wind,
                           cmap=cmap, norm=norm, transform=ll_proj,
                           extend='max', alpha=0.80, zorder=1)
        cbar = plt.colorbar(cf, ax=ax, orientation='horizontal',
                            pad=0.03, shrink=0.65, aspect=35)
        cbar.set_label(f'{level_hpa} hPa 風速 [m/s]', fontsize=11)
        cbar.set_ticks(lev_wind[::2])
        cbar.ax.tick_params(labelsize=9)

    cn = ax.contour(lons_c, lats, valHt_c, levels=lev_hgt,
                    colors='black', linewidths=0.8, transform=ll_proj, zorder=2)
    ax.clabel(cn, lev_hgt, fontsize=8, inline=True, inline_spacing=2,
              fmt='%i', rightside_up=True)

    cn2 = ax.contour(lons_c, lats, valHt_c, levels=lev_hgt2,
                     colors='black', linewidths=2.0, transform=ll_proj, zorder=2)
    ax.clabel(cn2, fontsize=10, inline=True, inline_spacing=2,
              fmt='%i', rightside_up=True)

    # H / L マーク（高度極大・極小）
    h_idx, l_idx = find_extrema(valHt, size=hl_size)
    _hl_kw = dict(transform=ll_proj, ha='center', va='center', zorder=6,
                  bbox=dict(boxstyle='round,pad=0.15', facecolor='white',
                            alpha=0.65, edgecolor='none'))
    for j, i in h_idx:
        ax.text(lons[i], lats[j], 'H', fontsize=15, fontweight='bold',
                color='#0033CC', **_hl_kw)
    for j, i in l_idx:
        ax.text(lons[i], lats[j], 'L', fontsize=15, fontweight='bold',
                color='#CC0000', **_hl_kw)

    # 気温コンター（点線・赤）＋ W/C マーク（気温極大・極小）
    if valT is not None:
        tcfg = TEMP_SETTINGS.get(level_hpa, TEMP_SETTINGS[500])
        ci = temp_ci if temp_ci is not None else TEMP_CI_DEFAULT
        t_start = int(np.ceil(tcfg['tmin'] / ci)) * ci  # 0基準の倍数に揃える
        lev_temp = np.arange(t_start, tcfg['tmax'] + 1, ci)
        valT_c, _ = add_cyclic_point(valT, coord=lons)
        ct = ax.contour(lons_c, lats, valT_c, levels=lev_temp,
                        colors='#CC0000', linewidths=0.8, linestyles='dashed',
                        transform=ll_proj, zorder=2)
        # ラベルは2本おき・単位付き
        ax.clabel(ct, lev_temp[::2], fontsize=7, inline=True, inline_spacing=1,
                  fmt='%i℃', rightside_up=True)
        # W（暖域極大）/ C（寒域極小）マーク — 薄い表示
        w_idx, c_idx = find_extrema(valT, size=hl_size)
        _w_kw = dict(transform=ll_proj, ha='center', va='center', zorder=6, alpha=0.65)
        _c_kw = dict(transform=ll_proj, ha='center', va='center', zorder=6, alpha=0.82)
        for j, i in w_idx:
            ax.text(lons[i], lats[j], 'W', fontsize=12, fontweight='normal',
                    color='#CC4400', **_w_kw)
        for j, i in c_idx:
            ax.text(lons[i], lats[j], 'C', fontsize=12, fontweight='normal',
                    color='#3355CC', **_c_kw)
        # 凡例（画像左下）
        temp_handle = mlines.Line2D([], [], color='#CC0000', linewidth=1.2,
                                    linestyle='dashed',
                                    label=f'気温  {ci}℃ 間隔 [℃]')
        ax.legend(handles=[temp_handle], loc='lower left', fontsize=9,
                  framealpha=0.85, edgecolor='#999999')

    ax.coastlines(resolution='50m', linewidth=0.8, color='#222222', zorder=3)
    ax.add_feature(cfeature.BORDERS, linewidth=0.4, linestyle=':', color='#555555', zorder=3)

    lat_min_tick = int(lat_min // 10) * 10 + 10
    gl = ax.gridlines(draw_labels=False, linewidth=0.5, color='gray',
                      alpha=0.6, linestyle='--', zorder=4)
    gl.xlocator = mticker.FixedLocator(np.arange(-180, 181, 30))
    gl.ylocator = mticker.FixedLocator(np.arange(lat_min_tick, 91, 10))

    label_lon      = (central_lon + 180) % 360
    label_lon_disp = label_lon if label_lon <= 180 else label_lon - 360
    for lat_lbl in range(lat_min_tick, 90, 10):
        ax.text(label_lon_disp, lat_lbl + 0.8, f'{lat_lbl}°N', transform=ll_proj,
                fontsize=8, color='#444444', ha='center', va='bottom', zorder=5)

    for lon_lbl in range(0, 360, 30):
        lon_disp  = lon_lbl if lon_lbl <= 180 else lon_lbl - 360
        lon_label = f'{abs(lon_disp)}°{"E" if lon_disp >= 0 else "W"}'
        ax.text(lon_disp, lat_min + 0.5, lon_label, transform=ll_proj,
                fontsize=8, color='#444444', ha='center', va='bottom', zorder=5)

    ax.set_title(f"{title_line1}\n{title_line2}", fontsize=10, loc='left')

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  → {out_path}")


# ---------------------------------------------------------------------------
# 描画モード
# ---------------------------------------------------------------------------

def plot_single(dt_init, ft_ddhh, level_hpa, lat_min, central_lon, no_wind, output_dir,
                climo_da=None, temp_ci=None, hl_size=50):
    """通常モード: 1FTを1枚描画"""
    ft_hours = ddhh_to_hours(ft_ddhh)
    data = load_field(dt_init, ft_ddhh, level_hpa, lat_min)
    if data is None:
        print(f"スキップ: FT={ft_hours}h（データ取得失敗）")
        return None

    hcfg = HGT_SETTINGS.get(level_hpa, HGT_SETTINGS[500])
    ft_d = ft_hours // 24
    ft_h = ft_hours % 24
    if climo_da is not None:
        shade_label = f'Shading: {level_hpa}hPa 高度偏差 [m]'
    elif not no_wind:
        shade_label = f'Shading: {level_hpa}hPa 風速 [m/s]'
    else:
        shade_label = '等高度線のみ'
    t1 = (f"Z{level_hpa} (GSM FORECAST)  Init: {data['analDate'].strftime('%Y/%m/%d %HZ')}  "
          f"FT={ft_d}day{ft_h:02d}h  Valid: {data['validDate'].strftime('%Y/%m/%d %HZ')}")
    t2 = (f"Contour: {hcfg['ci']}m (thin), {hcfg['ci_thick']}m (thick)  "
          f"{shade_label}  NH ({lat_min:.0f}°N–90°N)  central lon: {central_lon:.0f}°E")

    out_fn   = f"{dt_init.strftime('%Y%m%d%H')}_FT{ft_ddhh:04d}_{level_hpa}hPa_Polar.png"
    out_path = Path(output_dir) / out_fn
    draw_and_save(data['valHt'], data['wind'], data['lats'], data['lons'],
                  level_hpa, lat_min, central_lon, no_wind, t1, t2, out_path,
                  climo_da=climo_da, valT=data.get('valT'), temp_ci=temp_ci, hl_size=hl_size)
    return out_path


def plot_avg_init(dt_latest, n_avg, level_hpa, lat_min, central_lon, no_wind, output_dir,
                  climo_da=None, temp_ci=None, hl_size=50):
    """過去n_avg日のFT=0000解析値を平均して1枚描画する"""
    print(f"[過去{n_avg}日平均] {dt_latest.strftime('%Y%m%d%H')} を最新として FT=0000 を平均")
    fields, dates = [], []
    for delta in range(n_avg):
        dt = dt_latest - timedelta(days=delta)
        data = load_field(dt, 0, level_hpa, lat_min)
        if data is not None:
            fields.append(data)
            dates.append(dt)
        else:
            print(f"  ⚠ {dt.strftime('%Y%m%d%H')} 取得失敗（スキップ）")

    if not fields:
        print("  有効データなし。スキップ。")
        return None

    n_ok      = len(fields)
    valHt_avg = np.mean([f['valHt'] for f in fields], axis=0)
    wind_avg  = np.mean([f['wind']  for f in fields], axis=0)
    valT_avg  = np.mean([f['valT']  for f in fields], axis=0)

    hcfg       = HGT_SETTINGS.get(level_hpa, HGT_SETTINGS[500])
    date_range = f"{dates[-1].strftime('%Y/%m/%d')}–{dates[0].strftime('%Y/%m/%d')}"
    if climo_da is not None:
        shade_label = f'Shading: {level_hpa}hPa 高度偏差 [m]（{n_ok}日平均）'
    elif not no_wind:
        shade_label = f'Shading: {level_hpa}hPa 風速 [m/s]（{n_ok}日平均）'
    else:
        shade_label = f'等高度線のみ（{n_ok}日平均）'
    t1 = f"Z{level_hpa} (GSM ANALYSIS {n_ok}日平均)  期間: {date_range}"
    t2 = (f"Contour: {hcfg['ci']}m (thin), {hcfg['ci_thick']}m (thick)  "
          f"{shade_label}  NH ({lat_min:.0f}°N–90°N)  central lon: {central_lon:.0f}°E")

    out_fn   = f"{dt_latest.strftime('%Y%m%d%H')}_AVG{n_ok}d_{level_hpa}hPa_Polar.png"
    out_path = Path(output_dir) / out_fn
    draw_and_save(valHt_avg, wind_avg, fields[0]['lats'], fields[0]['lons'],
                  level_hpa, lat_min, central_lon, no_wind, t1, t2, out_path,
                  climo_da=climo_da, valT=valT_avg, temp_ci=temp_ci, hl_size=hl_size)
    return out_path


def plot_avg_ft(dt_init, start_ddhh, n_avg, interval_h,
                level_hpa, lat_min, central_lon, no_wind, output_dir,
                climo_da=None, temp_ci=None, hl_size=50):
    """start_ftからn_avg枚分のFTを平均して1枚描画する"""
    ft_list = build_ft_list(start_ddhh, n_avg, interval_h)
    ft_h0   = ddhh_to_hours(ft_list[0])
    ft_hN   = ddhh_to_hours(ft_list[-1])
    print(f"[FT平均] FT={ft_h0}h〜{ft_hN}h ({n_avg}枚, {interval_h}h間隔) を平均")

    fields = []
    for ft_ddhh in ft_list:
        data = load_field(dt_init, ft_ddhh, level_hpa, lat_min)
        if data is not None:
            fields.append(data)
        else:
            print(f"  ⚠ FT={ddhh_to_hours(ft_ddhh)}h 取得失敗（スキップ）")

    if not fields:
        print("  有効データなし。スキップ。")
        return None

    n_ok      = len(fields)
    valHt_avg = np.mean([f['valHt'] for f in fields], axis=0)
    wind_avg  = np.mean([f['wind']  for f in fields], axis=0)
    valT_avg  = np.mean([f['valT']  for f in fields], axis=0)

    hcfg = HGT_SETTINGS.get(level_hpa, HGT_SETTINGS[500])
    if climo_da is not None:
        shade_label = f'Shading: {level_hpa}hPa 高度偏差 [m]（FT{ft_h0}–{ft_hN}h平均）'
    elif not no_wind:
        shade_label = f'Shading: {level_hpa}hPa 風速 [m/s]（FT{ft_h0}–{ft_hN}h平均）'
    else:
        shade_label = '等高度線のみ（FT平均）'
    t1 = (f"Z{level_hpa} (GSM FORECAST FT平均)  Init: {dt_init.strftime('%Y/%m/%d %HZ')}  "
          f"FT={ft_h0}–{ft_hN}h ({n_ok}枚平均)")
    t2 = (f"Contour: {hcfg['ci']}m (thin), {hcfg['ci_thick']}m (thick)  "
          f"{shade_label}  NH ({lat_min:.0f}°N–90°N)  central lon: {central_lon:.0f}°E")

    out_fn   = f"{dt_init.strftime('%Y%m%d%H')}_AVGFT{ft_h0:03d}-{ft_hN:03d}_{level_hpa}hPa_Polar.png"
    out_path = Path(output_dir) / out_fn
    draw_and_save(valHt_avg, wind_avg, fields[0]['lats'], fields[0]['lons'],
                  level_hpa, lat_min, central_lon, no_wind, t1, t2, out_path,
                  climo_da=climo_da, valT=valT_avg, temp_ci=temp_ci, hl_size=hl_size)
    return out_path


# ---------------------------------------------------------------------------
# Markdown生成 / GitHub push
# ---------------------------------------------------------------------------

def generate_markdown(image_paths, init_time_str, level_hpa, mode_desc, md_path):
    """画像への相対リンクを含む Markdown ファイルを生成する"""
    lines = [
        f"# GSM 北半球極座標天気図  {init_time_str}",
        "",
        f"- **気圧面**: {level_hpa} hPa",
        f"- **モード**: {mode_desc}",
        "",
        "---",
        "",
    ]
    for p in image_paths:
        p = Path(p)
        lines += [f"## {p.stem}", "", f"![{p.stem}]({p.name})", ""]

    md_path = Path(md_path)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(lines), encoding='utf-8')
    print(f"Markdown生成: {md_path}")
    return md_path


def push_to_github(paths, commit_msg):
    """指定ファイルを git add → commit → push する"""
    str_paths = [str(p) for p in paths]
    for cmd in (
        ['git', 'add'] + str_paths,
        ['git', 'commit', '-m', commit_msg],
        ['git', 'push'],
    ):
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            label = ' '.join(cmd[:2])
            print(f"{label} 失敗:\n{r.stderr.strip()}")
            return False
        if cmd[1] == 'commit':
            print(f"コミット: {commit_msg}")
    print("GitHub push 完了")
    return True


# ---------------------------------------------------------------------------
# 引数解析
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description='GSM GRIB2から北半球極座標天気図（等高度線・風速シェード）を描画する',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例（通常モード）:
  python GSM_PolarView.py 2021082300                      # 500hPa FT=0h 1枚
  python GSM_PolarView.py 2021082300 0000 5              # 500hPa FT=0〜24h (6h間隔)
  python GSM_PolarView.py 2021082300 0000 1 --level 300  # 300hPa FT=0h
  python GSM_PolarView.py 2021082300 0000 4 --level 300 --interval 24

使用例（平均モード）:
  python GSM_PolarView.py 2021082300 --avg-init 5        # 過去5日FT=0000平均
  python GSM_PolarView.py 2021082300 0000 --avg-ft 4     # FT=0/6/12/18h 4枚平均
  python GSM_PolarView.py 2021082300 0000 --avg-ft 4 --interval 24  # FT=0/24/48/72h 4枚平均

使用例（平年偏差シェード）:
  python GSM_PolarView.py 2021082300 --climo                  # 偏差シェード（事前に make_ncep_climo.py 実行要）
  python GSM_PolarView.py 2021082300 --avg-init 5 --climo     # 過去5日平均 + 偏差シェード

使用例（GitHub push）:
  python GSM_PolarView.py 2021082300 --avg-init 5 --push
  python GSM_PolarView.py 2021082300 0000 5 --push

  対応気圧面: 200, 250, 300, 500, 700, 850 hPa

実行環境（conda の場合）:
  conda activate met_env_310
  python GSM_PolarView.py [引数]
"""
    )
    parser.add_argument('init_time',    type=str,   help='初期時刻 YYYYMMDDHH（UTC）')
    parser.add_argument('start_ft',     type=str,   nargs='?', default='0000',
                        help='開始予報時間 DDHH形式（デフォルト: 0000）')
    parser.add_argument('n_steps',      type=int,   nargs='?', default=1,
                        help='通常モードで作成する枚数（デフォルト: 1）')
    parser.add_argument('--level',      type=int,   default=500,
                        choices=[200, 250, 300, 500, 700, 850],
                        help='気圧面 hPa（デフォルト: 500）')
    parser.add_argument('--interval',   type=int,   default=6,
                        help='FT間隔 時間数（デフォルト: 6）')
    parser.add_argument('--lat-min',    type=float, default=20.0,
                        help='描画範囲の最小緯度（デフォルト: 20°N）')
    parser.add_argument('--central-lon', type=float, default=140.0,
                        help='中央経線（デフォルト: 140°E、日本が下になる）')
    parser.add_argument('--no-wind',    action='store_true',
                        help='風速シェードを表示しない（等高度線のみ）')
    parser.add_argument('--temp-ci',   type=int,   default=None,
                        help=f'気温コンター間隔 °C（デフォルト: {TEMP_CI_DEFAULT}）')
    parser.add_argument('--output',     type=str,   default='./output',
                        help='出力ディレクトリ（--push 時は reports/ 配下に自動設定）')

    avg_group = parser.add_mutually_exclusive_group()
    avg_group.add_argument('--avg-init', type=int, default=0, metavar='N',
                           help='過去N日のFT=0000解析値を平均して1枚描画（N>=2）')
    avg_group.add_argument('--avg-ft',   type=int, default=0, metavar='N',
                           help='start_ftからN枚分のFTを平均して1枚描画（N>=2）')

    parser.add_argument('--hl-size',   type=int,   default=25,
                        help='H/L・W/C マーク検出の近傍サイズ（格子数, デフォルト: 50 ≈ 62°）')
    parser.add_argument('--push', action='store_true',
                        help='生成画像+MDを reports/ に保存して git push する')
    parser.add_argument('--climo', action='store_true',
                        help='風速シェードの代わりに NCEP LTM との高度偏差シェードを表示する')
    parser.add_argument('--climo-dir', type=str, default='./data/ncep_climo',
                        help='平年値 NetCDF の保存先（デフォルト: ./data/ncep_climo）')

    if any(a in sys.argv[1:] for a in ('?', '-?', '--?')):
        parser.print_help()
        sys.exit(0)

    return parser.parse_args()


# ---------------------------------------------------------------------------
# メイン
# ---------------------------------------------------------------------------

def main():
    args = parse_args()

    init_str = args.init_time
    dt_init  = datetime(int(init_str[:4]), int(init_str[4:6]),
                        int(init_str[6:8]), int(init_str[8:10]))

    level      = args.level
    lat_min    = args.lat_min
    central_lon = args.central_lon
    no_wind    = args.no_wind
    interval_h = args.interval
    temp_ci    = args.temp_ci  # None の場合は draw_and_save 内でデフォルト値を使用
    hl_size    = args.hl_size

    # --push 時は reports/ 配下に保存
    if args.push:
        tag = (f"AVG{args.avg_init}d" if args.avg_init
               else f"AVGFT" if args.avg_ft
               else f"FT{args.start_ft}")
        output_dir = Path(f"./reports/{init_str}-polar-{tag}-{level}hPa")
    else:
        output_dir = Path(args.output)

    print(f"初期時刻: {init_str} UTC  気圧面: {level} hPa")

    # 平年値の読み込み（--climo 指定時のみ。月は有効時刻の月を使用）
    climo_da = None
    if args.climo:
        # 平均モードの場合は init_time の月、通常モードは start_ft の有効時刻の月
        if args.avg_init >= 2:
            climo_month = dt_init.month
        elif args.avg_ft >= 2:
            mid_ft_h = ddhh_to_hours(int(args.start_ft)) + (args.avg_ft - 1) * interval_h // 2
            climo_month = (dt_init + timedelta(hours=mid_ft_h)).month
        else:
            ft_h = ddhh_to_hours(int(args.start_ft))
            climo_month = (dt_init + timedelta(hours=ft_h)).month
        print(f"平年値読み込み: {climo_month}月  ({args.climo_dir})")
        climo_da = load_climo_hgt(climo_month, level, lat_min, args.climo_dir)

    image_paths = []

    # --- 過去N日平均モード ---
    if args.avg_init >= 2:
        print(f"モード: 過去{args.avg_init}日平均")
        p = plot_avg_init(dt_init, args.avg_init, level, lat_min,
                          central_lon, no_wind, output_dir, climo_da=climo_da, temp_ci=temp_ci,
                          hl_size=hl_size)
        if p:
            image_paths.append(p)

    # --- FT平均モード ---
    elif args.avg_ft >= 2:
        print(f"モード: FT平均 ({args.avg_ft}枚)")
        p = plot_avg_ft(dt_init, int(args.start_ft), args.avg_ft, interval_h,
                        level, lat_min, central_lon, no_wind, output_dir, climo_da=climo_da, temp_ci=temp_ci,
                        hl_size=hl_size)
        if p:
            image_paths.append(p)

    # --- 通常モード ---
    else:
        print(f"モード: 通常 ({args.n_steps}枚)")
        ft_list = build_ft_list(int(args.start_ft), args.n_steps, interval_h)
        print(f"FT一覧: {[ddhh_to_hours(ft) for ft in ft_list]}h")
        for ft_ddhh in ft_list:
            p = plot_single(dt_init, ft_ddhh, level, lat_min,
                            central_lon, no_wind, output_dir, climo_da=climo_da, temp_ci=temp_ci,
                            hl_size=hl_size)
            if p:
                image_paths.append(p)

    print(f"\n生成画像: {len(image_paths)} 枚")

    if not image_paths:
        print("画像が生成されませんでした。終了します。")
        return

    # --- GitHub push ---
    if args.push:
        if args.avg_init >= 2:
            mode_desc = f"過去{args.avg_init}日 FT=0000 平均"
        elif args.avg_ft >= 2:
            mode_desc = f"FT平均 ({args.avg_ft}枚, {interval_h}h間隔)"
        else:
            mode_desc = f"通常予報 {args.n_steps}枚 ({interval_h}h間隔)"

        md_path = output_dir / "polar_report.md"
        generate_markdown(image_paths, init_str, level, mode_desc, md_path)

        commit_msg = f"report: 極座標天気図 {init_str} {level}hPa {mode_desc}"
        push_to_github(image_paths + [md_path], commit_msg)
    else:
        print(f"→ {output_dir}/")


if __name__ == '__main__':
    main()
