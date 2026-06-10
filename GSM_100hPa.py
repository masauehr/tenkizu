#!/usr/bin/env python
# coding: utf-8

# GSM 100hPa 等高度線・風矢羽 天気図描画スクリプト
# 作成: 20260428 上原政博

import os
os.environ['PROJ_LIB'] = '/opt/anaconda3/envs/met_env_310/share/proj'

from pyproj import datadir, CRS
datadir.set_data_dir(os.environ['PROJ_LIB'])

import pygrib
import matplotlib.pyplot as plt
from pathlib import Path
import matplotlib.ticker as mticker
import numpy as np
import cartopy.crs as ccrs
import sys
import argparse
from pathlib import Path
import requests

BASE_URL = "http://database.rish.kyoto-u.ac.jp/arch/jmadata/data/gpv/original"
HEADERS  = {"User-Agent": "Mozilla/5.0 (compatible; GSM-Downloader/1.0)"}
# 絶対パスで指定: 呼び出し元のcwdに依存しない
_SCRIPT_DIR = Path(__file__).parent


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
        description='GSM GRIB2から100hPa等高度線・風矢羽天気図を描画する',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python GSM_100hPa.py 2021100100 0000 1   # FT=0h 1枚
  python GSM_100hPa.py 2021100100 0000 5   # FT0h〜FT24h 5枚
  python GSM_100hPa.py 2021100100 0100 3   # FT24h〜FT36h 3枚

実行環境（conda の場合）:
  conda activate met_env_310
  python GSM_100hPa.py [引数]

  ※ 環境名（met_env_310）は利用者の構築状況により異なります。
     pygrib / metpy / cartopy 等が入った Python 3.10 環境であれば動作します。
"""
    )
    parser.add_argument('init_time', type=str, help='初期時刻 YYYYMMDDHH（UTC）')
    parser.add_argument('start_ft',  type=str, nargs='?', default='0000', help='開始予報時間 DDHH形式（デフォルト: 0000）')
    parser.add_argument('n_steps',   type=int, nargs='?', default=1,      help='作成する枚数（6h間隔、デフォルト: 1）')
    parser.add_argument('level',     type=int, nargs='?', default=100,    help='気圧面 hPa（デフォルト: 100）')
    parser.add_argument('--area',    type=float, nargs=4, default=None,
                        metavar=('LON_W', 'LON_E', 'LAT_S', 'LAT_N'),
                        help='描画範囲 lonW lonE latS latN（デフォルト: 84 156 17 55）')
    parser.add_argument('--avg_steps', type=int, default=1,
                        help='平均するFT個数（1=平均なし、n指定時は6h間隔でn個を平均して1枚、デフォルト: 1）')
    parser.add_argument('--no-isotac', action='store_true',
                        help='ISOTACシェード・等風速線を非表示にし等高度線＋矢羽のみにする')

    # ? / -? / --? でヘルプ表示
    if any(a in sys.argv[1:] for a in ('?', '-?', '--?')):
        parser.print_help()
        sys.exit(0)

    return parser.parse_args()


def plot_one(i_year, i_month, i_day, i_hourZ, ft_ddhh, tagHp, output_dir, area=None, no_isotac=False):
    ft_hours = ddhh_to_hours(ft_ddhh)

    gsm_fn_t = "Z__C_RJTD_{0:04d}{1:02d}{2:02d}{3:02d}0000_GSM_GPV_Rgl_FD{4:04d}_grib2.bin"
    gr_fn    = gsm_fn_t.format(i_year, i_month, i_day, i_hourZ, ft_ddhh)
    gr_path  = str(_SCRIPT_DIR / "data_gsm" / gr_fn)

    if not ensure_file(gr_path, gr_fn, i_year, i_month, i_day):
        print(f"スキップ: FT={ft_hours}h（データ取得失敗）")
        return False

    print(f"[{ft_hours:4d}h] データ読み込み: {gr_fn}")

    grbs  = pygrib.open(gr_path)
    grbHt = grbs(shortName="gh", typeOfLevel='isobaricInhPa', level=tagHp)[0]
    grbWu = grbs(shortName="u",  typeOfLevel='isobaricInhPa', level=tagHp)[0]
    grbWv = grbs(shortName="v",  typeOfLevel='isobaricInhPa', level=tagHp)[0]
    grbs.close()

    latS, latN, lonW, lonE = -20, 80, 70, 190
    valHt, latHt, lonHt = grbHt.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)
    valWu, latWu, lonWu = grbWu.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)
    valWv, latWv, lonWv = grbWv.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)

    lat = latHt[:, 0]
    lon = lonHt[0, :]

    # m/s → ノット変換・風速計算
    u_kt  = valWu * 1.94384
    v_kt  = valWv * 1.94384
    ws_kt = np.sqrt(u_kt**2 + v_kt**2)

    dt_i    = grbHt.analDate
    dt_str  = (dt_i.strftime("%H00UTC%d%b%Y")).upper()
    dt_str2 = dt_i.strftime("%Y%m%d%H")

    # 等高度線レベル（120m間隔）
    min_hgt   = int(valHt.min() / 120) * 120
    max_hgt   = int(valHt.max() / 120 + 1) * 120
    levels_ht = np.arange(min_hgt, max_hgt + 120, 120)

    # 等風速線レベル（20kt間隔）
    levels_ws = np.arange(20, 130, 20)

    areaAry     = area if area is not None else [84, 156, 17, 55]
    proj        = ccrs.Stereographic(central_latitude=60, central_longitude=140)
    latlon_proj = ccrs.PlateCarree()

    bottom = 0.08 if no_isotac else 0.18
    fig = plt.figure(figsize=(13, 9))
    plt.subplots_adjust(left=0, right=1, bottom=bottom, top=0.98)
    ax = fig.add_subplot(1, 1, 1, projection=proj)
    ax.set_extent(areaAry, latlon_proj)

    if not no_isotac:
        cn_ws = ax.contourf(lon, lat, ws_kt,
                            levels_ws, cmap='YlOrRd', extend='max',
                            alpha=0.65, transform=latlon_proj)
        cn_ws_line = ax.contour(lon, lat, ws_kt,
                                levels_ws, colors='blue', linewidths=1.5,
                                transform=latlon_proj)
        ax.clabel(cn_ws_line, fontsize=14, inline=True, colors='blue',
                  inline_spacing=5, fmt='%i', rightside_up=True)

    cn_hgt = ax.contour(lon, lat, valHt,
                        colors='black', linewidths=1.2, levels=levels_ht,
                        transform=latlon_proj)
    ax.clabel(cn_hgt, levels_ht[::2], fontsize=14, inline=True,
              inline_spacing=5, fmt='%i', rightside_up=True)

    # 風矢羽（GSM 0.5°格子: 8格子おき = 4度間隔）
    lat_sl = slice(None, None, 8)
    lon_sl = slice(None, None, 8)
    ax.barbs(lon[lon_sl], lat[lat_sl],
             u_kt[lat_sl, :][:, lon_sl],
             v_kt[lat_sl, :][:, lon_sl],
             length=6, pivot='middle', color='black', transform=latlon_proj,
             sizes=dict(emptybarb=0.05))

    ax.coastlines(resolution='50m')
    xticks = np.arange(0, 360.1, 10)
    yticks = np.arange(-90, 90.1, 10)
    gl = ax.gridlines(crs=ccrs.PlateCarree(), draw_labels=False, linewidth=1, alpha=0.8)
    gl.xlocator = mticker.FixedLocator(xticks)
    gl.ylocator = mticker.FixedLocator(yticks)

    title_elems = f"{tagHp}hPa Height(m), Wind(kt)" if no_isotac else f"{tagHp}hPa Height(m), ISOTAC(kt), Wind(kt)"
    title_y = 0.02 if no_isotac else 0.13
    fig.text(0.5, title_y,
             f"GSM FT{ft_hours:d}h IT:{dt_str} {title_elems}",
             ha='center', va='bottom', size=15)

    if not no_isotac:
        cb_ax = fig.add_axes([0.1, 0.04, 0.8, 0.025])
        fig.colorbar(cn_ws, cax=cb_ax, orientation='horizontal',
                     label='Wind Speed (kt)')

    os.makedirs(output_dir, exist_ok=True)
    out_fn = f"{output_dir}/{dt_str2}_FT{ft_hours:03d}h_GSM_{tagHp}hPa_Height_Wind.png"
    plt.savefig(out_fn, dpi=150, bbox_inches='tight')
    print(f"[{ft_hours:4d}h] 出力: {out_fn}")
    plt.close()
    return True


def plot_avg(i_year, i_month, i_day, i_hourZ, batch_start_h, avg_steps, tagHp, output_dir, area=None, no_isotac=False):
    """avg_steps個のFT（6h間隔）データを平均して1枚の天気図を生成する"""
    ft_list = [batch_start_h + i * 6 for i in range(avg_steps)]
    batch_end_h = ft_list[-1]

    valHt_all, valWu_all, valWv_all = [], [], []
    lat = lon = None
    dt_str = dt_str2 = None

    for ft_h in ft_list:
        ft_ddhh = hours_to_ddhh(ft_h)
        gr_fn   = f"Z__C_RJTD_{i_year:04d}{i_month:02d}{i_day:02d}{i_hourZ:02d}0000_GSM_GPV_Rgl_FD{ft_ddhh:04d}_grib2.bin"
        gr_path = str(_SCRIPT_DIR / "data_gsm" / gr_fn)

        if not ensure_file(gr_path, gr_fn, i_year, i_month, i_day):
            print(f"  スキップ: FT={ft_h}h（データ取得失敗）")
            return False

        print(f"  [{ft_h:4d}h] データ読み込み: {gr_fn}")
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
            lat    = latHt[:, 0]
            lon    = lonHt[0, :]
            dt_i   = grbHt.analDate
            dt_str  = (dt_i.strftime("%H00UTC%d%b%Y")).upper()
            dt_str2 = dt_i.strftime("%Y%m%d%H")

    if not valHt_all:
        print("エラー: 平均するデータがありません")
        return False

    valHt = np.mean(valHt_all, axis=0)
    valWu = np.mean(valWu_all, axis=0)
    valWv = np.mean(valWv_all, axis=0)

    u_kt  = valWu * 1.94384
    v_kt  = valWv * 1.94384
    ws_kt = np.sqrt(u_kt**2 + v_kt**2)

    min_hgt   = int(valHt.min() / 120) * 120
    max_hgt   = int(valHt.max() / 120 + 1) * 120
    levels_ht = np.arange(min_hgt, max_hgt + 120, 120)
    levels_ws = np.arange(20, 130, 20)

    areaAry     = area if area is not None else [84, 156, 17, 55]
    proj        = ccrs.Stereographic(central_latitude=60, central_longitude=140)
    latlon_proj = ccrs.PlateCarree()

    bottom = 0.08 if no_isotac else 0.18
    fig = plt.figure(figsize=(13, 9))
    plt.subplots_adjust(left=0, right=1, bottom=bottom, top=0.98)
    ax = fig.add_subplot(1, 1, 1, projection=proj)
    ax.set_extent(areaAry, latlon_proj)

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
    xticks = np.arange(0, 360.1, 10)
    yticks = np.arange(-90, 90.1, 10)
    gl = ax.gridlines(crs=ccrs.PlateCarree(), draw_labels=False, linewidth=1, alpha=0.8)
    gl.xlocator = mticker.FixedLocator(xticks)
    gl.ylocator = mticker.FixedLocator(yticks)

    avg_label = f"FT{batch_start_h:03d}-{batch_end_h:03d}h_avg{avg_steps}"
    title_elems = f"{tagHp}hPa Height(m), Wind(kt)" if no_isotac else f"{tagHp}hPa Height(m), ISOTAC(kt), Wind(kt)"
    title_y = 0.02 if no_isotac else 0.13
    fig.text(0.5, title_y,
             f"GSM {avg_label} IT:{dt_str} {title_elems}",
             ha='center', va='bottom', size=15)

    if not no_isotac:
        cb_ax = fig.add_axes([0.1, 0.04, 0.8, 0.025])
        fig.colorbar(cn_ws, cax=cb_ax, orientation='horizontal', label='Wind Speed (kt)')

    os.makedirs(output_dir, exist_ok=True)
    out_fn = f"{output_dir}/{dt_str2}_{avg_label}_GSM_{tagHp}hPa_Height_Wind.png"
    plt.savefig(out_fn, dpi=150, bbox_inches='tight')
    print(f"  平均出力: {out_fn}")
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

    if args.avg_steps > 1:
        start_ft_h = ddhh_to_hours(start_ddhh)
        print(f"平均モード: start_ft={start_ft_h}h, avg_steps={args.avg_steps}, n_steps={args.n_steps}")
        print()
        success = 0
        for step_i in range(args.n_steps):
            batch_start_h = start_ft_h + step_i * (6 * args.avg_steps)
            if plot_avg(i_year, i_month, i_day, i_hourZ, batch_start_h, args.avg_steps, tagHp, "./output", area=args.area, no_isotac=args.no_isotac):
                success += 1
        print(f"\n完了: {success}/{args.n_steps}枚 出力先: ./output/")
    else:
        success = 0
        for ft_ddhh in ft_list:
            if plot_one(i_year, i_month, i_day, i_hourZ, ft_ddhh, tagHp, "./output", area=args.area, no_isotac=args.no_isotac):
                success += 1
        print(f"\n完了: {success}/{args.n_steps}枚 出力先: ./output/")


if __name__ == "__main__":
    main()
