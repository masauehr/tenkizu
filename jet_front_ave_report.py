#!/usr/bin/env python
# coding: utf-8

# ジェット・前線解析（広域・時間平均）生成・GitHub アップロードスクリプト
# 指定した最新初期時刻から12時間ごとに遡り、各初期時刻のFT=0hデータを平均した天気図を作成。
# 例: init_time=2026050600, n_days=3 → 2026050600/0512/0500/0412/0400/0312（6個）のFT=0hを平均
#
# 使用例:
#   python jet_front_ave_report.py 2026050600              # GSMのみ 1日(2個)平均
#   python jet_front_ave_report.py 2026050600 3            # GSMのみ 3日(6個)平均
#   python jet_front_ave_report.py 2026050600 3 --ecm      # GSM+ECM 3日平均
#   python jet_front_ave_report.py 2026050600 3 --ecm-only # ECMのみ 3日平均
#   python jet_front_ave_report.py 2026050600 3 --levels 100 50 --ecm
#   python jet_front_ave_report.py 2026050600 3 --push     # 生成後 GitHub push
#
# 作成: 20260507 上原政博（jet_front_wide_report.py をベースに作成）

import os
import sys
import shutil
import subprocess
import argparse
from pathlib import Path
from datetime import datetime, timedelta

os.environ.setdefault("PROJ_LIB", "/opt/anaconda3/envs/met_env_310/share/proj")

from pyproj import datadir
datadir.set_data_dir(os.environ["PROJ_LIB"])

import requests
import pygrib
import numpy as np
import xarray as xr
import metpy.calc as mpcalc
from metpy.units import units
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from scipy.ndimage import uniform_filter

# ワイド版描画領域（jet_front_wide_report.py と同じ）
AREA_UPPER = [70, 180, -12, 30]
AREA_EPT   = [70, 180, -12, 30]  # 上層と同一範囲

BASE_URL_GSM = "http://database.rish.kyoto-u.ac.jp/arch/jmadata/data/gpv/original"
BASE_URL_ECM = "https://data.ecmwf.int/forecasts"
HEADERS      = {"User-Agent": "Mozilla/5.0 (compatible; TenkizuDownloader/1.0)"}
MIN_ECM_SIZE = 50 * 1024 * 1024

_SCRIPT_DIR = Path(__file__).parent


# ---- ダウンロード関数 ----

def ensure_gsm(gr_path, gr_fn, year, month, day):
    if os.path.exists(gr_path):
        return True
    print(f"  ダウンロード: {gr_fn}")
    url  = f"{BASE_URL_GSM}/{year}/{month:02d}/{day:02d}/{gr_fn}"
    dest = Path(gr_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with requests.get(url, headers=HEADERS, stream=True, timeout=300) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            downloaded = 0
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        print(f"\r    {downloaded/total*100:.1f}% ({downloaded/1048576:.1f} MB)", end="", flush=True)
            print()
        print(f"  完了: {gr_fn}")
        return True
    except requests.RequestException as e:
        print(f"\n  失敗: {e}")
        if dest.exists():
            dest.unlink()
        return False


def ensure_ecm(ecm_path, ecm_fn, year, month, day, hour):
    if os.path.exists(ecm_path):
        if os.path.getsize(ecm_path) >= MIN_ECM_SIZE:
            return True
        print(f"  警告: ファイルが不完全。削除して再DL: {ecm_fn}")
        os.remove(ecm_path)
    print(f"  ダウンロード: {ecm_fn}")
    sub_dir = "oper" if hour in (0, 12) else "scda"
    url     = f"{BASE_URL_ECM}/{year:04d}{month:02d}{day:02d}/{hour:02d}z/ifs/0p25/{sub_dir}/{ecm_fn}"
    dest    = Path(ecm_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with requests.get(url, headers=HEADERS, stream=True, timeout=300) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            downloaded = 0
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        print(f"\r    {downloaded/total*100:.1f}% ({downloaded/1048576:.1f} MB)", end="", flush=True)
            print()
        print(f"  完了: {ecm_fn}")
        return True
    except requests.HTTPError as e:
        print(f"\n  失敗（HTTP {e.response.status_code}）")
        if e.response.status_code == 404:
            print("  過去データはCDS API (https://cds.climate.copernicus.eu) を利用してください。")
        if dest.exists():
            dest.unlink()
        return False
    except requests.RequestException as e:
        print(f"\n  失敗: {e}")
        if dest.exists():
            dest.unlink()
        return False


# ---- 引数解析 ----

def parse_args():
    parser = argparse.ArgumentParser(
        description='複数初期時刻FT=0hを平均したジェット・前線解析（広域）を生成する',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python jet_front_ave_report.py 2026050600                # GSMのみ 1日(2個)平均
  python jet_front_ave_report.py 2026050600 3              # GSMのみ 3日(6個)平均
  python jet_front_ave_report.py 2026050600 3 --ecm        # GSM+ECM 3日平均
  python jet_front_ave_report.py 2026050600 3 --ecm-only   # ECMのみ 3日平均
  python jet_front_ave_report.py 2026050600 3 --levels 100 50
  python jet_front_ave_report.py 2026050600 3 --push

実行環境（conda の場合）:
  conda activate met_env_310
  python jet_front_ave_report.py [引数]

  ※ 環境名（met_env_310）は利用者の構築状況により異なります。
     pygrib / metpy / cartopy 等が入った Python 3.10 環境であれば動作します。
"""
    )
    parser.add_argument('init_time', type=str,
                        help='最新の初期時刻 YYYYMMDDHH（UTC、00 or 12 のみ）')
    parser.add_argument('n_days',    type=int, nargs='?', default=1,
                        help='平均日数（12h間隔で2個 = 1日、デフォルト: 1）')
    parser.add_argument('--levels',  type=int, nargs='+', default=[100],
                        help='上層風の気圧面 hPa（複数指定可、デフォルト: 100）')
    parser.add_argument('--ecm',      action='store_true',
                        help='ECMWFも実行する（GSM+ECM、省略時はGSMのみ）')
    parser.add_argument('--ecm-only', action='store_true',
                        help='ECMWFのみ実行する（GSMをスキップ）')
    parser.add_argument('--push',    action='store_true',
                        help='GitHub へ git push する（省略時はローカル保存のみ）')
    parser.add_argument('--no-isotac', action='store_true',
                        help='上層風図のISOTACシェード・等風速線を非表示にし等高度線＋矢羽のみにする')

    # ? / -? / --? でヘルプ表示
    if any(a in sys.argv[1:] for a in ('?', '-?', '--?')):
        parser.print_help()
        sys.exit(0)

    return parser.parse_args()


# ---- ユーティリティ ----

def build_init_times(newest_dt, n_days):
    """最新初期時刻から12h間隔で遡った n_days*2 個の datetime リストを返す（新しい順）"""
    n_steps = n_days * 2
    return [newest_dt - timedelta(hours=i * 12) for i in range(n_steps)]


def check_data_files(init_times, run_gsm, run_ecm):
    """ローカルファイルを優先確認し、なければサーバーHEADリクエストで存在確認する。"""
    missing = []
    for dt in init_times:
        i_str   = dt.strftime('%Y%m%d%H')
        i_year  = dt.year
        i_month = dt.month
        i_day   = dt.day
        i_hourZ = dt.hour
        ecm_sub = "oper" if i_hourZ in (0, 12) else "scda"

        if run_gsm:
            fn    = f"Z__C_RJTD_{i_str}0000_GSM_GPV_Rgl_FD0000_grib2.bin"
            local = _SCRIPT_DIR / "data_gsm" / fn
            if local.exists():
                print(f"  GSM {i_str} FT=0h: OK (ローカル)")
            else:
                url = f"{BASE_URL_GSM}/{i_year}/{i_month:02d}/{i_day:02d}/{fn}"
                try:
                    r = requests.head(url, headers=HEADERS, timeout=15)
                    if r.status_code == 200:
                        print(f"  GSM {i_str} FT=0h: OK (サーバー)")
                    else:
                        print(f"  GSM {i_str} FT=0h: NG (HTTP {r.status_code})")
                        missing.append(f"    {url}")
                except requests.RequestException as e:
                    print(f"  GSM {i_str} FT=0h: NG (接続エラー: {e})")
                    missing.append(f"    {url}")

        if run_ecm:
            fn    = f"{i_str}0000-0h-{ecm_sub}-fc.grib2"
            local = _SCRIPT_DIR / "data" / "ecm" / fn
            if local.exists():
                print(f"  ECM {i_str} FT=0h: OK (ローカル)")
            else:
                url = (f"{BASE_URL_ECM}/{i_year:04d}{i_month:02d}{i_day:02d}"
                       f"/{i_hourZ:02d}z/ifs/0p25/{ecm_sub}/{fn}")
                try:
                    r = requests.head(url, headers=HEADERS, timeout=15)
                    if r.status_code == 200:
                        print(f"  ECM {i_str} FT=0h: OK (サーバー)")
                    else:
                        print(f"  ECM {i_str} FT=0h: NG (HTTP {r.status_code})")
                        missing.append(f"    {url}")
                except requests.RequestException as e:
                    print(f"  ECM {i_str} FT=0h: NG (接続エラー: {e})")
                    missing.append(f"    {url}")

    if missing:
        print("\nエラー: 以下のファイルがサーバーに存在しません。処理を中止します。")
        for m in missing:
            print(m)
        return False
    return True


def run_git(cmd, cwd):
    print(f"$ git {cmd}")
    result = subprocess.run(f"git {cmd}", shell=True, cwd=cwd,
                            capture_output=True, text=True)
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip())
    return result.returncode


def copy_png(src, report_dir, label):
    if src.exists():
        dst = report_dir / src.name
        shutil.copy2(src, dst)
        print(f"  コピー: {src.name}")
        return src.name
    else:
        print(f"  ※ 見つかりません: {src.name} ({label})")
        return None


# ---- 描画関数 ----

def plot_gsm_100hpa_avg(init_times, tagHp, output_dir, area, newest_dt_str2, n_days, no_isotac=False):
    """複数初期時刻のFT=0h GSMデータを平均して上層風天気図を生成する"""
    valHt_all, valWu_all, valWv_all = [], [], []
    lat = lon = None

    for dt in init_times:
        gr_fn   = f"Z__C_RJTD_{dt.strftime('%Y%m%d%H')}0000_GSM_GPV_Rgl_FD0000_grib2.bin"
        gr_path = str(_SCRIPT_DIR / "data_gsm" / gr_fn)

        if not ensure_gsm(gr_path, gr_fn, dt.year, dt.month, dt.day):
            print(f"  スキップ: {dt.strftime('%Y%m%d%H')} FT=0h（データ取得失敗）")
            return False

        print(f"  [{dt.strftime('%Y%m%d%H')} FT=0h] 読み込み")
        grbs  = pygrib.open(gr_path)
        grbHt = grbs(shortName="gh", typeOfLevel='isobaricInhPa', level=tagHp)[0]
        grbWu = grbs(shortName="u",  typeOfLevel='isobaricInhPa', level=tagHp)[0]
        grbWv = grbs(shortName="v",  typeOfLevel='isobaricInhPa', level=tagHp)[0]
        grbs.close()

        latS, latN, lonW, lonE = -20, 80, 70, 190
        _valHt, latHt, lonHt = grbHt.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)
        _valWu, _, _          = grbWu.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)
        _valWv, _, _          = grbWv.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)

        valHt_all.append(_valHt)
        valWu_all.append(_valWu)
        valWv_all.append(_valWv)

        if lat is None:
            lat = latHt[:, 0]
            lon = lonHt[0, :]

    if not valHt_all:
        return False

    valHt = np.mean(valHt_all, axis=0)
    valWu = np.mean(valWu_all, axis=0)
    valWv = np.mean(valWv_all, axis=0)

    u_kt  = valWu * 1.94384
    v_kt  = valWv * 1.94384
    ws_kt = np.sqrt(u_kt**2 + v_kt**2)

    min_hgt   = int(valHt.min() / 60) * 60
    max_hgt   = int(valHt.max() / 60 + 1) * 60
    levels_ht = np.arange(min_hgt, max_hgt + 60, 60)
    levels_ws = np.arange(20, 130, 20)

    proj        = ccrs.Stereographic(central_latitude=60, central_longitude=140)
    latlon_proj = ccrs.PlateCarree()

    bottom = 0.08 if no_isotac else 0.18
    fig = plt.figure(figsize=(13, 9))
    plt.subplots_adjust(left=0, right=1, bottom=bottom, top=0.98)
    ax = fig.add_subplot(1, 1, 1, projection=proj)
    ax.set_extent(area, latlon_proj)

    ax.contourf(lon, lat, valHt, levels=levels_ht,
                cmap='RdBu_r', alpha=0.5, extend='both', transform=latlon_proj)

    if not no_isotac:
        cn_ws = ax.contourf(lon, lat, ws_kt, levels_ws, cmap='YlOrRd', extend='max',
                            alpha=0.65, transform=latlon_proj)
        cn_ws_line = ax.contour(lon, lat, ws_kt, levels_ws, colors='blue', linewidths=1.5,
                                transform=latlon_proj)
        ax.clabel(cn_ws_line, fontsize=14, inline=True, colors='blue',
                  inline_spacing=5, fmt='%i', rightside_up=True)

    cn_hgt = ax.contour(lon, lat, valHt, colors='black', linewidths=1.2, levels=levels_ht,
                        transform=latlon_proj)
    ax.clabel(cn_hgt, levels_ht[::2], fontsize=14, inline=True,
              inline_spacing=5, fmt='%i', rightside_up=True)

    lat_sl = slice(None, None, 8)
    lon_sl = slice(None, None, 8)
    ax.barbs(lon[lon_sl], lat[lat_sl],
             u_kt[lat_sl, :][:, lon_sl],
             v_kt[lat_sl, :][:, lon_sl],
             length=6, pivot='middle', color='black', transform=latlon_proj,
             sizes=dict(emptybarb=0.05))

    ax.coastlines(resolution='50m')
    gl = ax.gridlines(crs=ccrs.PlateCarree(), draw_labels=False, linewidth=1, alpha=0.8)
    gl.xlocator = mticker.FixedLocator(np.arange(0, 360.1, 10))
    gl.ylocator = mticker.FixedLocator(np.arange(-90, 90.1, 10))

    period_str = f"{init_times[-1].strftime('%Y%m%d%H')}〜{init_times[0].strftime('%Y%m%d%H')}UTC"
    title_elems = f"{tagHp}hPa Height(m), Wind(kt)" if no_isotac else f"{tagHp}hPa Height(m), ISOTAC(kt), Wind(kt)"
    title_y = 0.02 if no_isotac else 0.13
    fig.text(0.5, title_y,
             f"GSM {n_days}day avg (FT=0h×{len(init_times)}) {period_str} {title_elems}",
             ha='center', va='bottom', size=12)

    if not no_isotac:
        cb_ax = fig.add_axes([0.1, 0.04, 0.8, 0.025])
        fig.colorbar(cn_ws, cax=cb_ax, orientation='horizontal', label='Wind Speed (kt)')

    os.makedirs(output_dir, exist_ok=True)
    out_fn = f"{output_dir}/{newest_dt_str2}_AVG{n_days}d_GSM_{tagHp}hPa_Height_Wind.png"
    plt.savefig(out_fn, dpi=150, bbox_inches='tight')
    print(f"  出力: {out_fn}")
    plt.close()
    return True


def plot_ecm_100hpa_avg(init_times, tagHp, output_dir, area, newest_dt_str2, n_days, no_isotac=False):
    """複数初期時刻のFT=0h ECMデータを平均して上層風天気図を生成する"""
    data_dir = str(_SCRIPT_DIR / "data" / "ecm")
    valHt_all, valWu_all, valWv_all = [], [], []
    lat = lon = None

    for dt in init_times:
        if dt.hour in (0, 12):
            ecm_fn = f"{dt.strftime('%Y%m%d%H')}0000-0h-oper-fc.grib2"
        else:
            ecm_fn = f"{dt.strftime('%Y%m%d%H')}0000-0h-scda-fc.grib2"
        ecm_path = f"{data_dir}/{ecm_fn}"

        if not ensure_ecm(ecm_path, ecm_fn, dt.year, dt.month, dt.day, dt.hour):
            print(f"  スキップ: {dt.strftime('%Y%m%d%H')} FT=0h（データ取得失敗）")
            return False

        print(f"  [{dt.strftime('%Y%m%d%H')} FT=0h] 読み込み")
        grbs  = pygrib.open(ecm_path)
        grbHt = grbs(shortName="gh", typeOfLevel='isobaricInhPa', level=tagHp)[0]
        grbWu = grbs(shortName="u",  typeOfLevel='isobaricInhPa', level=tagHp)[0]
        grbWv = grbs(shortName="v",  typeOfLevel='isobaricInhPa', level=tagHp)[0]
        grbs.close()

        latS, latN, lonW, lonE = -20, 80, 70, 190
        _valHt, latHt, lonHt = grbHt.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)
        _valWu, _, _          = grbWu.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)
        _valWv, _, _          = grbWv.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)

        _valHt = uniform_filter(_valHt, size=3)
        _valWu = uniform_filter(_valWu, size=3)
        _valWv = uniform_filter(_valWv, size=3)

        valHt_all.append(_valHt)
        valWu_all.append(_valWu)
        valWv_all.append(_valWv)

        if lat is None:
            lat = latHt[:, 0]
            lon = lonHt[0, :]

    if not valHt_all:
        return False

    valHt = np.mean(valHt_all, axis=0)
    valWu = np.mean(valWu_all, axis=0)
    valWv = np.mean(valWv_all, axis=0)

    u_kt  = valWu * 1.94384
    v_kt  = valWv * 1.94384
    ws_kt = np.sqrt(u_kt**2 + v_kt**2)

    min_hgt   = int(valHt.min() / 60) * 60
    max_hgt   = int(valHt.max() / 60 + 1) * 60
    levels_ht = np.arange(min_hgt, max_hgt + 60, 60)
    levels_ws = np.arange(20, 130, 20)

    proj        = ccrs.Stereographic(central_latitude=60, central_longitude=140)
    latlon_proj = ccrs.PlateCarree()

    bottom = 0.08 if no_isotac else 0.18
    fig = plt.figure(figsize=(13, 9))
    plt.subplots_adjust(left=0, right=1, bottom=bottom, top=0.98)
    ax = fig.add_subplot(1, 1, 1, projection=proj)
    ax.set_extent(area, latlon_proj)

    ax.contourf(lon, lat, valHt, levels=levels_ht,
                cmap='RdBu_r', alpha=0.5, extend='both', transform=latlon_proj)

    if not no_isotac:
        cn_ws = ax.contourf(lon, lat, ws_kt, levels_ws, cmap='YlOrRd', extend='max',
                            alpha=0.65, transform=latlon_proj)
        cn_ws_line = ax.contour(lon, lat, ws_kt, levels_ws, colors='blue', linewidths=1.5,
                                transform=latlon_proj)
        ax.clabel(cn_ws_line, fontsize=14, inline=True, colors='blue',
                  inline_spacing=5, fmt='%i', rightside_up=True)

    cn_hgt = ax.contour(lon, lat, valHt, colors='black', linewidths=1.2, levels=levels_ht,
                        transform=latlon_proj)
    ax.clabel(cn_hgt, levels_ht[::2], fontsize=14, inline=True,
              inline_spacing=5, fmt='%i', rightside_up=True)

    lat_sl = slice(None, None, 12)
    lon_sl = slice(None, None, 12)
    ax.barbs(lon[lon_sl], lat[lat_sl],
             u_kt[lat_sl, :][:, lon_sl],
             v_kt[lat_sl, :][:, lon_sl],
             length=6, pivot='middle', color='black', transform=latlon_proj,
             sizes=dict(emptybarb=0.05))

    ax.coastlines(resolution='50m')
    gl = ax.gridlines(crs=ccrs.PlateCarree(), draw_labels=False, linewidth=1, alpha=0.8)
    gl.xlocator = mticker.FixedLocator(np.arange(0, 360.1, 10))
    gl.ylocator = mticker.FixedLocator(np.arange(-90, 90.1, 10))

    period_str = f"{init_times[-1].strftime('%Y%m%d%H')}〜{init_times[0].strftime('%Y%m%d%H')}UTC"
    title_elems = f"{tagHp}hPa Height(m), Wind(kt)" if no_isotac else f"{tagHp}hPa Height(m), ISOTAC(kt), Wind(kt)"
    title_y = 0.02 if no_isotac else 0.13
    fig.text(0.5, title_y,
             f"ECM {n_days}day avg (FT=0h×{len(init_times)}) {period_str} {title_elems}",
             ha='center', va='bottom', size=12)

    if not no_isotac:
        cb_ax = fig.add_axes([0.1, 0.04, 0.8, 0.025])
        fig.colorbar(cn_ws, cax=cb_ax, orientation='horizontal', label='Wind Speed (kt)')

    os.makedirs(output_dir, exist_ok=True)
    out_fn = f"{output_dir}/{newest_dt_str2}_AVG{n_days}d_ECM_{tagHp}hPa_Height_Wind.png"
    plt.savefig(out_fn, dpi=150, bbox_inches='tight')
    print(f"  出力: {out_fn}")
    plt.close()
    return True


def plot_gsm_ept850_avg(init_times, output_dir, area, newest_dt_str2, n_days):
    """複数初期時刻のFT=0h GSM 850hPa 生データを平均してEPT天気図を生成する"""
    tagHp = 850
    valWu_all, valWv_all, valTm_all, valRh_all = [], [], [], []
    lat = lon = None
    dt_i = None

    for dt in init_times:
        gr_fn   = f"Z__C_RJTD_{dt.strftime('%Y%m%d%H')}0000_GSM_GPV_Rgl_FD0000_grib2.bin"
        gr_path = str(_SCRIPT_DIR / "data_gsm" / gr_fn)

        if not ensure_gsm(gr_path, gr_fn, dt.year, dt.month, dt.day):
            print(f"  スキップ: {dt.strftime('%Y%m%d%H')} FT=0h（データ取得失敗）")
            return False

        print(f"  [{dt.strftime('%Y%m%d%H')} FT=0h] 読み込み")
        grbs  = pygrib.open(gr_path)
        grbWu = grbs(shortName="u", typeOfLevel='isobaricInhPa', level=tagHp)[0]
        grbWv = grbs(shortName="v", typeOfLevel='isobaricInhPa', level=tagHp)[0]
        grbTm = grbs(shortName="t", typeOfLevel='isobaricInhPa', level=tagHp)[0]
        grbRh = grbs(shortName="r", typeOfLevel='isobaricInhPa', level=tagHp)[0]
        grbs.close()

        latS, latN, lonW, lonE = -20, 80, 70, 190
        _valWu, latWu, lonWu = grbWu.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)
        _valWv, _, _          = grbWv.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)
        _valTm, latTm, lonTm  = grbTm.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)
        _valRh, _, _          = grbRh.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)

        valWu_all.append(_valWu)
        valWv_all.append(_valWv)
        valTm_all.append(_valTm)
        valRh_all.append(_valRh)

        if lat is None:
            lat  = latTm[:, 0]
            lon  = lonTm[0, :]
            dt_i = dt

    if not valTm_all:
        return False

    valWu = np.mean(valWu_all, axis=0)
    valWv = np.mean(valWv_all, axis=0)
    valTm = np.mean(valTm_all, axis=0)
    valRh = np.mean(valRh_all, axis=0)

    ds = xr.Dataset(
        {
            "u_wind":          (["lat", "lon"], valWu * units('m/s')),
            "v_wind":          (["lat", "lon"], valWv * units('m/s')),
            "Temperature":     (["lat", "lon"], valTm * units('K')),
            "RelativHumidity": (["lat", "lon"], valRh * 0.01),
        },
        coords={
            "time":  np.array([dt_i]),
            "level": np.array(tagHp) * units.hPa,
            "lat":   np.array(lat) * units('degrees_north'),
            "lon":   np.array(lon) * units('degrees_east'),
        },
    )
    ds['u_wind'].attrs['units']          = 'm/s'
    ds['v_wind'].attrs['units']          = 'm/s'
    ds['Temperature'].attrs['units']     = 'K'
    ds['RelativHumidity'].attrs['units'] = ''
    ds['level'].attrs['units']           = 'hPa'
    ds['lat'].attrs['units']             = 'degrees_north'
    ds['lon'].attrs['units']             = 'degrees_east'

    dsp = ds.metpy.parse_cf()
    dsp['dewpoint_temperature'] = mpcalc.dewpoint_from_relative_humidity(
        dsp['Temperature'], dsp['RelativHumidity'])
    dsp['Equivalent_Potential_temperature'] = mpcalc.equivalent_potential_temperature(
        dsp['level'], dsp['Temperature'], dsp['dewpoint_temperature'])

    levels_ept0  = np.arange(270, 390,  3)
    levels_ept0i = np.arange(270, 390,  3)
    levels_ept1  = np.arange(270, 390, 15)
    levels_eptf  = np.arange(270, 360,  3)

    proj        = ccrs.Stereographic(central_latitude=60, central_longitude=140)
    latlon_proj = ccrs.PlateCarree()
    fig = plt.figure(figsize=(10, 8))
    plt.subplots_adjust(left=0, right=1, bottom=0.06, top=0.98)
    ax = fig.add_subplot(1, 1, 1, projection=proj)
    ax.set_extent(area, latlon_proj)

    cnf_ept = ax.contourf(dsp['lon'], dsp['lat'], dsp['Equivalent_Potential_temperature'],
                          levels_eptf, cmap="jet", extend='both', transform=latlon_proj)
    ax_ept = fig.add_axes([0.1, 0.1, 0.8, 0.02])
    fig.colorbar(cnf_ept, orientation='horizontal', shrink=0.74, aspect=40, pad=0.01, cax=ax_ept)

    cn_ept0 = ax.contour(dsp['lon'], dsp['lat'], dsp['Equivalent_Potential_temperature'],
                         colors='black', linewidths=0.3, levels=levels_ept0, transform=latlon_proj)
    ax.clabel(cn_ept0, levels_ept0i, fontsize=8, inline=True, inline_spacing=5,
              fmt='%i', rightside_up=True, colors='black')
    cn_ept1 = ax.contour(dsp['lon'], dsp['lat'], dsp['Equivalent_Potential_temperature'],
                         colors='black', linewidths=1.0, levels=levels_ept1, transform=latlon_proj)
    ax.clabel(cn_ept1, levels_ept1, fontsize=12, inline=True, inline_spacing=5,
              fmt='%i', rightside_up=True, colors='black')

    ax.coastlines(resolution='50m', linewidth=1.6)
    gl = ax.gridlines(crs=ccrs.PlateCarree(), draw_labels=False, linewidth=1, alpha=0.8)
    gl.xlocator = mticker.FixedLocator(np.arange(0, 360, 10))
    gl.ylocator = mticker.FixedLocator(np.arange(-90, 90.1, 10))

    wind_slice = (slice(None, None, 5), slice(None, None, 5))
    ax.barbs(dsp['lon'][wind_slice[0]], dsp['lat'][wind_slice[1]],
             dsp['u_wind'].values[wind_slice] * 1.944,
             dsp['v_wind'].values[wind_slice] * 1.944,
             length=5.5, pivot='middle', color='black', transform=latlon_proj)

    period_str = f"{init_times[-1].strftime('%Y%m%d%H')}〜{init_times[0].strftime('%Y%m%d%H')}UTC"
    fig.text(0.5, 0.01,
             f"GSM {n_days}day avg (FT=0h×{len(init_times)}) {period_str} {tagHp}hPa EPT(K), Wind",
             ha='center', va='bottom', size=12)

    os.makedirs(output_dir, exist_ok=True)
    out_fn = f"{output_dir}/{newest_dt_str2}_AVG{n_days}d_GSM_{tagHp}hPa_EPT.png"
    plt.savefig(out_fn, dpi=150, bbox_inches='tight')
    print(f"  出力: {out_fn}")
    plt.close()
    return True


def plot_ecm_ept850_avg(init_times, output_dir, area, newest_dt_str2, n_days):
    """複数初期時刻のFT=0h ECM 850hPa 生データを平均してEPT天気図を生成する"""
    tagHp    = 850
    data_dir = str(_SCRIPT_DIR / "data" / "ecm")
    valHt_all, valWu_all, valWv_all, valTm_all, valRh_all = [], [], [], [], []
    lat = lon = None
    dt_i = None

    for dt in init_times:
        if dt.hour in (0, 12):
            ecm_fn = f"{dt.strftime('%Y%m%d%H')}0000-0h-oper-fc.grib2"
        else:
            ecm_fn = f"{dt.strftime('%Y%m%d%H')}0000-0h-scda-fc.grib2"
        ecm_path = f"{data_dir}/{ecm_fn}"

        if not ensure_ecm(ecm_path, ecm_fn, dt.year, dt.month, dt.day, dt.hour):
            print(f"  スキップ: {dt.strftime('%Y%m%d%H')} FT=0h（データ取得失敗）")
            return False

        print(f"  [{dt.strftime('%Y%m%d%H')} FT=0h] 読み込み")
        grbs  = pygrib.open(ecm_path)
        grbHt = grbs(shortName="gh", typeOfLevel='isobaricInhPa', level=tagHp)[0]
        grbWu = grbs(shortName="u",  typeOfLevel='isobaricInhPa', level=tagHp)[0]
        grbWv = grbs(shortName="v",  typeOfLevel='isobaricInhPa', level=tagHp)[0]
        grbTm = grbs(shortName="t",  typeOfLevel='isobaricInhPa', level=tagHp)[0]
        grbRh = grbs(shortName="r",  typeOfLevel='isobaricInhPa', level=tagHp)[0]
        grbs.close()

        latS, latN, lonW, lonE = -20, 80, 70, 190
        _valHt, latHt, lonHt = grbHt.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)
        _valWu, _, _          = grbWu.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)
        _valWv, _, _          = grbWv.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)
        _valTm, latTm, lonTm  = grbTm.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)
        _valRh, _, _          = grbRh.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)

        _s = 3
        _valHt = uniform_filter(_valHt, size=_s)
        _valWu = uniform_filter(_valWu, size=_s)
        _valWv = uniform_filter(_valWv, size=_s)
        _valTm = uniform_filter(_valTm, size=_s)
        _valRh = uniform_filter(_valRh, size=_s)

        valHt_all.append(_valHt)
        valWu_all.append(_valWu)
        valWv_all.append(_valWv)
        valTm_all.append(_valTm)
        valRh_all.append(_valRh)

        if lat is None:
            lat  = latHt[:, 0]
            lon  = lonHt[0, :]
            dt_i = dt

    if not valTm_all:
        return False

    valHt = np.mean(valHt_all, axis=0)
    valWu = np.mean(valWu_all, axis=0)
    valWv = np.mean(valWv_all, axis=0)
    valTm = np.mean(valTm_all, axis=0)
    valRh = np.mean(valRh_all, axis=0)

    ds = xr.Dataset(
        {
            "Geopotential_height": (["lat", "lon"], valHt),
            "u_wind":              (["lat", "lon"], valWu),
            "v_wind":              (["lat", "lon"], valWv),
            "Temperature":         (["lat", "lon"], valTm),
            "RelativHumidity":     (["lat", "lon"], valRh * 0.01),
        },
        coords={
            "time":  np.array([dt_i]),
            "level": np.array(tagHp) * units.hPa,
            "lat":   np.array(lat) * units('degrees_north'),
            "lon":   np.array(lon) * units('degrees_east'),
        },
    )
    ds['Geopotential_height'].attrs['units'] = 'm'
    ds['u_wind'].attrs['units']          = 'm/s'
    ds['v_wind'].attrs['units']          = 'm/s'
    ds['Temperature'].attrs['units']     = 'K'
    ds['RelativHumidity'].attrs['units'] = ''
    ds['level'].attrs['units']           = 'hPa'
    ds['lat'].attrs['units']             = 'degrees_north'
    ds['lon'].attrs['units']             = 'degrees_east'

    dsp = ds.metpy.parse_cf()
    dsp['dewpoint_temperature'] = mpcalc.dewpoint_from_relative_humidity(
        dsp['Temperature'], dsp['RelativHumidity'])
    dsp['Equivalent_Potential_temperature'] = mpcalc.equivalent_potential_temperature(
        dsp['level'], dsp['Temperature'], dsp['dewpoint_temperature'])

    levels_ept0  = np.arange(270, 390,  3)
    levels_ept0i = np.arange(270, 390,  3)
    levels_ept1  = np.arange(270, 390, 15)
    levels_eptf  = np.arange(270, 360,  3)

    proj        = ccrs.Stereographic(central_latitude=60, central_longitude=140)
    latlon_proj = ccrs.PlateCarree()
    fig = plt.figure(figsize=(10, 8))
    plt.subplots_adjust(left=0, right=1, bottom=0.06, top=0.98)
    ax = fig.add_subplot(1, 1, 1, projection=proj)
    ax.set_extent(area, latlon_proj)

    cnf_ept = ax.contourf(dsp['lon'], dsp['lat'], dsp['Equivalent_Potential_temperature'],
                          levels_eptf, cmap="jet", extend='both', transform=latlon_proj)
    ax_ept = fig.add_axes([0.1, 0.1, 0.8, 0.02])
    fig.colorbar(cnf_ept, orientation='horizontal', shrink=0.74, aspect=40, pad=0.01, cax=ax_ept)

    cn_ept0 = ax.contour(dsp['lon'], dsp['lat'], dsp['Equivalent_Potential_temperature'],
                         colors='black', linewidths=0.3, levels=levels_ept0, transform=latlon_proj)
    ax.clabel(cn_ept0, levels_ept0i, fontsize=8, inline=True, inline_spacing=5,
              fmt='%i', rightside_up=True, colors='black')
    cn_ept1 = ax.contour(dsp['lon'], dsp['lat'], dsp['Equivalent_Potential_temperature'],
                         colors='black', linewidths=1.0, levels=levels_ept1, transform=latlon_proj)
    ax.clabel(cn_ept1, levels_ept1, fontsize=12, inline=True, inline_spacing=5,
              fmt='%i', rightside_up=True, colors='black')

    ax.coastlines(resolution='50m', linewidth=1.6)
    gl = ax.gridlines(crs=ccrs.PlateCarree(), draw_labels=False, linewidth=1, alpha=0.8)
    gl.xlocator = mticker.FixedLocator(np.arange(0, 360, 10))
    gl.ylocator = mticker.FixedLocator(np.arange(-90, 90.1, 10))

    wind_slice = (slice(None, None, 5), slice(None, None, 5))
    ax.barbs(dsp['lon'][wind_slice[0]], dsp['lat'][wind_slice[1]],
             dsp['u_wind'].values[wind_slice] * 1.944,
             dsp['v_wind'].values[wind_slice] * 1.944,
             length=5.5, pivot='middle', color='black', transform=latlon_proj)

    period_str = f"{init_times[-1].strftime('%Y%m%d%H')}〜{init_times[0].strftime('%Y%m%d%H')}UTC"
    fig.text(0.5, 0.01,
             f"ECM {n_days}day avg (FT=0h×{len(init_times)}) {period_str} {tagHp}hPa EPT(K), Wind",
             ha='center', va='bottom', size=12)

    os.makedirs(output_dir, exist_ok=True)
    out_fn = f"{output_dir}/{newest_dt_str2}_AVG{n_days}d_ECM_{tagHp}hPa_EPT.png"
    plt.savefig(out_fn, dpi=150, bbox_inches='tight')
    print(f"  出力: {out_fn}")
    plt.close()
    return True


# ---- メイン ----

def main():
    args = parse_args()
    init_str = args.init_time

    if len(init_str) != 10 or not init_str.isdigit():
        print("エラー: init_time は YYYYMMDDHH の10桁で指定してください")
        sys.exit(1)
    if init_str[8:10] not in ("00", "12"):
        print("エラー: 初期時刻の時刻部分は 00 または 12 のみ対応しています")
        sys.exit(1)
    if args.n_days < 1:
        print("エラー: n_days は 1 以上を指定してください")
        sys.exit(1)

    n_days    = args.n_days
    levels    = args.levels
    run_gsm   = not args.ecm_only
    run_ecm   = args.ecm or args.ecm_only

    newest_dt      = datetime.strptime(init_str, "%Y%m%d%H")
    init_times     = build_init_times(newest_dt, n_days)
    newest_dt_str2 = newest_dt.strftime("%Y%m%d%H")
    oldest_dt      = init_times[-1]
    n_steps        = len(init_times)

    script_dir  = Path(__file__).parent.resolve()
    output_dir  = str(script_dir / "output")
    report_dir  = script_dir / "reports" / (init_str + "-ave")
    report_dir.mkdir(parents=True, exist_ok=True)

    period_str  = f"{oldest_dt.strftime('%Y%m%d%H')}〜{newest_dt.strftime('%Y%m%d%H')}UTC"
    level_label = "+".join(f"{l}hPa" for l in levels)
    model_label = "ECMのみ" if args.ecm_only else ("GSM+ECM" if run_ecm else "GSMのみ")

    print(f"{'='*60}")
    print(f" ジェット・前線解析（広域・時間平均） [{model_label}] 上層風:{level_label}")
    print(f" 最新初期時刻: {init_str} UTC  平均: {n_days}日（{n_steps}個 / 12h間隔）")
    print(f" 平均期間: {period_str}")
    print(f" 上層域: {AREA_UPPER}  850hPa域: {AREA_EPT}")
    print(f"{'='*60}\n")
    print("使用する初期時刻一覧:")
    for dt in init_times:
        print(f"  {dt.strftime('%Y%m%d %HUTC')} FT=0h")
    print()

    # ---- Step 0: データファイル確認 ----
    print("--- Step 0: データファイル確認 ---")
    if not check_data_files(init_times, run_gsm, run_ecm):
        sys.exit(1)
    print("  全ファイル確認OK\n")

    collected = {
        "upper_gsm": {lev: None for lev in levels},
        "upper_ecm": {lev: None for lev in levels},
        "ept_gsm":   None,
        "ept_ecm":   None,
    }

    # ---- 上層風 ----
    for lev in levels:
        if run_gsm:
            print(f"--- GSM {lev}hPa 上層風 (時間平均) ---")
            ok = plot_gsm_100hpa_avg(init_times, lev, output_dir, AREA_UPPER, newest_dt_str2, n_days, no_isotac=args.no_isotac)
            if ok:
                src = Path(output_dir) / f"{newest_dt_str2}_AVG{n_days}d_GSM_{lev}hPa_Height_Wind.png"
                collected["upper_gsm"][lev] = copy_png(src, report_dir, f"GSM {lev}hPa 上層風")
            else:
                print(f"警告: GSM {lev}hPa 上層風 の生成に失敗しました")
            print()

        if run_ecm:
            print(f"--- ECM {lev}hPa 上層風 (時間平均) ---")
            ok = plot_ecm_100hpa_avg(init_times, lev, output_dir, AREA_UPPER, newest_dt_str2, n_days, no_isotac=args.no_isotac)
            if ok:
                src = Path(output_dir) / f"{newest_dt_str2}_AVG{n_days}d_ECM_{lev}hPa_Height_Wind.png"
                collected["upper_ecm"][lev] = copy_png(src, report_dir, f"ECM {lev}hPa 上層風")
            else:
                print(f"警告: ECM {lev}hPa 上層風 の生成に失敗しました")
            print()

    # ---- 850hPa EPT ----
    if run_gsm:
        print("--- GSM 850hPa 相当温位 (時間平均) ---")
        ok = plot_gsm_ept850_avg(init_times, output_dir, AREA_EPT, newest_dt_str2, n_days)
        if ok:
            src = Path(output_dir) / f"{newest_dt_str2}_AVG{n_days}d_GSM_850hPa_EPT.png"
            collected["ept_gsm"] = copy_png(src, report_dir, "GSM EPT850")
        else:
            print("警告: GSM 850hPa EPT の生成に失敗しました")
        print()

    if run_ecm:
        print("--- ECM 850hPa 相当温位 (時間平均) ---")
        ok = plot_ecm_ept850_avg(init_times, output_dir, AREA_EPT, newest_dt_str2, n_days)
        if ok:
            src = Path(output_dir) / f"{newest_dt_str2}_AVG{n_days}d_ECM_850hPa_EPT.png"
            collected["ept_ecm"] = copy_png(src, report_dir, "ECM EPT850")
        else:
            print("警告: ECM 850hPa EPT の生成に失敗しました")
        print()

    any_copied = any([
        any(v for v in collected["upper_gsm"].values()),
        any(v for v in collected["upper_ecm"].values()),
        collected["ept_gsm"],
        collected["ept_ecm"],
    ])
    if not any_copied:
        print("エラー: コピーするPNGがありません。処理を中断します。")
        sys.exit(1)

    # ---- Markdown レポート生成 ----
    lines = [
        "# ジェット・前線解析（広域・時間平均）",
        "",
        f"**最新初期時刻**: {newest_dt.strftime('%Y/%m/%d %HUTC')}  "
        f"（{n_days}日間 / {n_steps}個 平均）",
        f"**平均期間**: {oldest_dt.strftime('%Y/%m/%d %HUTC')} 〜 {newest_dt.strftime('%Y/%m/%d %HUTC')}",
        "",
        f"*(描画領域: 上層 lonW={AREA_UPPER[0]} lonE={AREA_UPPER[1]} "
        f"latS={AREA_UPPER[2]} latN={AREA_UPPER[3]}、"
        f"850hPa lonW={AREA_EPT[0]} lonE={AREA_EPT[1]} "
        f"latS={AREA_EPT[2]} latN={AREA_EPT[3]})*",
        "",
        "---",
        "",
    ]

    lines += [f"## 上層風（{level_label}）", ""]
    for lev in levels:
        if collected["upper_gsm"][lev]:
            lines += [f"### GSM {lev}hPa ({n_days}日平均)", "",
                      f"![GSM {lev}hPa {n_days}日平均](./{collected['upper_gsm'][lev]})", ""]
        if collected["upper_ecm"][lev]:
            lines += [f"### ECMWF {lev}hPa ({n_days}日平均)", "",
                      f"![ECM {lev}hPa {n_days}日平均](./{collected['upper_ecm'][lev]})", ""]
    lines += ["---", ""]

    lines += ["## 850hPa 相当温位・風矢羽", ""]
    if collected["ept_gsm"]:
        lines += [f"### GSM ({n_days}日平均)", "",
                  f"![GSM EPT850 {n_days}日平均](./{collected['ept_gsm']})", ""]
    if collected["ept_ecm"]:
        lines += [f"### ECMWF ({n_days}日平均)", "",
                  f"![ECM EPT850 {n_days}日平均](./{collected['ept_ecm']})", ""]
    lines += ["---", ""]

    md_name = f"jet_front_ave_report_{n_days}d.md"
    md_path = report_dir / md_name
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nMDファイル生成: reports/{init_str}-ave/{md_name}")

    # ---- git add → commit → push（--push 指定時のみ）----
    if not args.push:
        print("\nGitHub push はスキップ（--push を付けると実行）")
    else:
        print("\n--- GitHub へアップロード ---")
        rel_path = f"reports/{init_str}-ave"

        rc = run_git(f"add {rel_path}", script_dir)
        if rc != 0:
            print("エラー: git add 失敗")
            sys.exit(1)

        staged = subprocess.run("git diff --staged --quiet", shell=True, cwd=script_dir)
        if staged.returncode == 0:
            print("変更なし: 既にアップロード済みです（コミット・プッシュをスキップ）")
        else:
            commit_msg = (
                f"report: ジェット・前線解析（広域・時間平均）{n_days}日平均 ({init_str})"
            )
            rc = run_git(f'commit -m "{commit_msg}"', script_dir)
            if rc != 0:
                print("エラー: git commit 失敗")
                sys.exit(1)

            run_git("config http.postBuffer 524288000", script_dir)

            rc = run_git("push", script_dir)
            if rc != 0:
                print("push 失敗。30秒待ってリトライします...")
                import time
                time.sleep(30)
                rc = run_git("push", script_dir)
            if rc != 0:
                print("エラー: git push 失敗（手動で 'git push' を実行してください）")
                sys.exit(1)

    print(f"\n{'='*60}")
    print(f" 完了")
    print(f" レポート: reports/{init_str}-ave/{md_name}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
