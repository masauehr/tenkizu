#!/usr/bin/env python
# coding: utf-8

# ECMWF 100hPa 等高度線・風矢羽 天気図描画スクリプト
# GSM_100hPa.py の ECMWF Open Data 版
# 作成: 20260428 上原政博

import os
os.environ['PROJ_LIB'] = '/opt/anaconda3/envs/met_env_310/share/proj'

from pyproj import datadir, CRS
datadir.set_data_dir(os.environ['PROJ_LIB'])

import pygrib
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import cartopy.crs as ccrs
import sys
import argparse
from pathlib import Path
import requests
from scipy.ndimage import uniform_filter

ECM_BASE_URL  = "https://data.ecmwf.int/forecasts"
HEADERS       = {"User-Agent": "Mozilla/5.0 (compatible; ECM-Downloader/1.0)"}
# 絶対パスで指定: 呼び出し元のcwdに依存しない
DATA_DIR      = str(Path(__file__).parent / "data" / "ecm")
# 正常なECM全球ファイルは100MB超。50MB未満は不完全ダウンロードと判定
MIN_FILE_SIZE = 50 * 1024 * 1024


def ensure_file_ecm(ecm_path, ecm_fn, year, month, day, hour):
    if os.path.exists(ecm_path):
        size = os.path.getsize(ecm_path)
        if size >= MIN_FILE_SIZE:
            return True
        print(f"警告: ファイルが不完全です ({size/1024/1024:.1f}MB < 50MB)。削除して再ダウンロードします: {ecm_fn}")
        os.remove(ecm_path)
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
            print("  過去データはCDS API (https://cds.climate.copernicus.eu) を利用してください。")
        if dest.exists(): dest.unlink()
        return False
    except requests.RequestException as e:
        print(f"\nダウンロード失敗: {e}")
        if dest.exists(): dest.unlink()
        return False


def build_ft_list(start_ft, n_steps, step=6):
    return [start_ft + i * step for i in range(n_steps)]


def parse_args():
    parser = argparse.ArgumentParser(
        description='ECMWF GRIB2から100hPa等高度線・風矢羽天気図を描画する',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python ECM_100hPa.py 2026041200 0 1               # FT=0h 1枚
  python ECM_100hPa.py 2026041200 0 5               # FT=0,6,12,18,24h 5枚
  python ECM_100hPa.py 2026041200 24 3              # FT=24,30,36h 3枚
  python ECM_100hPa.py 2026041200 0 1 --smooth-size 5  # スムージング5×5
  python ECM_100hPa.py 2026041200 0 1 --wind-step 8    # 風矢羽8格子おき

デフォルト描画設定:
  --area        84 156 17 55   東経84〜156°、北緯17〜55°
  --smooth-size 3              3×3格子平均スムージング（ECM 0.25°→約0.75°相当）
  --wind-step   12             風矢羽を12格子おき（約3度間隔）
        """
    )
    parser.add_argument('init_time', type=str, help='初期時刻 YYYYMMDDHH（UTC）')
    parser.add_argument('start_ft',  type=int, nargs='?', default=0,   help='開始予報時間（時間数、デフォルト: 0）')
    parser.add_argument('n_steps',   type=int, nargs='?', default=1,   help='作成する枚数（6h間隔、デフォルト: 1）')
    parser.add_argument('level',     type=int, nargs='?', default=100, help='気圧面 hPa（デフォルト: 100）')
    parser.add_argument('--area',    type=float, nargs=4, default=None,
                        metavar=('LON_W', 'LON_E', 'LAT_S', 'LAT_N'),
                        help='描画範囲 lonW lonE latS latN（デフォルト: 84 156 17 55）')
    parser.add_argument('--avg_steps', type=int, default=1,
                        help='平均するFT個数（1=平均なし、n指定時は6h間隔でn個を平均して1枚、デフォルト: 1）')
    parser.add_argument('--smooth-size', type=int, default=3,
                        help='uniform_filterのサイズ（デフォルト: 3）')
    parser.add_argument('--wind-step', type=int, default=12,
                        help='風矢羽の間引き格子数（デフォルト: 12）')

    # ? / -? / --? でヘルプ表示
    if any(a in sys.argv[1:] for a in ('?', '-?', '--?')):
        parser.print_help()
        sys.exit(0)

    return parser.parse_args()


def plot_one(i_year, i_month, i_day, i_hourZ, ft_hours, tagHp, output_dir, area=None, smooth_size=3, wind_step=12):
    if i_hourZ in (0, 12):
        ecm_fn = f"{i_year:04d}{i_month:02d}{i_day:02d}{i_hourZ:02d}0000-{ft_hours:d}h-oper-fc.grib2"
    else:
        ecm_fn = f"{i_year:04d}{i_month:02d}{i_day:02d}{i_hourZ:02d}0000-{ft_hours:d}h-scda-fc.grib2"
    ecm_path = f"{DATA_DIR}/{ecm_fn}"

    if not ensure_file_ecm(ecm_path, ecm_fn, i_year, i_month, i_day, i_hourZ):
        print(f"スキップ: FT={ft_hours}h（データ取得失敗）")
        return False

    print(f"[{ft_hours:4d}h] データ読み込み: {ecm_fn}")

    grbs  = pygrib.open(ecm_path)
    grbHt = grbs(shortName="gh", typeOfLevel='isobaricInhPa', level=tagHp)[0]
    grbWu = grbs(shortName="u",  typeOfLevel='isobaricInhPa', level=tagHp)[0]
    grbWv = grbs(shortName="v",  typeOfLevel='isobaricInhPa', level=tagHp)[0]
    grbs.close()

    latS, latN, lonW, lonE = -20, 80, 70, 190
    valHt, latHt, lonHt = grbHt.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)
    valWu, latWu, lonWu = grbWu.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)
    valWv, latWv, lonWv = grbWv.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)

    # ECM(0.25°)を平滑化
    valHt = uniform_filter(valHt, size=smooth_size)
    valWu = uniform_filter(valWu, size=smooth_size)
    valWv = uniform_filter(valWv, size=smooth_size)

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

    # 横長フィグ: 底部にタイトル行・カラーバー行を独立配置
    fig = plt.figure(figsize=(13, 9))
    plt.subplots_adjust(left=0, right=1, bottom=0.18, top=0.98)
    ax = fig.add_subplot(1, 1, 1, projection=proj)
    ax.set_extent(areaAry, latlon_proj)

    # ISOTAC カラー塗り
    cn_ws = ax.contourf(lon, lat, ws_kt,
                        levels_ws, cmap='YlOrRd', extend='max',
                        alpha=0.65, transform=latlon_proj)

    # ISOTAC 等風速線
    cn_ws_line = ax.contour(lon, lat, ws_kt,
                             levels_ws, colors='blue', linewidths=1.5,
                             transform=latlon_proj)
    ax.clabel(cn_ws_line, fontsize=14, inline=True, colors='blue',
              inline_spacing=5, fmt='%i', rightside_up=True)

    # 等高度線（黒線、上に重ねる）
    cn_hgt = ax.contour(lon, lat, valHt,
                        colors='black', linewidths=1.2, levels=levels_ht,
                        transform=latlon_proj)
    ax.clabel(cn_hgt, levels_ht[::2], fontsize=14, inline=True,
              inline_spacing=5, fmt='%i', rightside_up=True)

    # 風矢羽
    lat_sl = slice(None, None, wind_step)
    lon_sl = slice(None, None, wind_step)
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

    # タイトル: 地図直下
    fig.text(0.5, 0.13,
             f"ECM FT{ft_hours:d}h IT:{dt_str} {tagHp}hPa Height(m), ISOTAC(kt), Wind(kt)",
             ha='center', va='bottom', size=15)

    # カラーバー: タイトルの下
    cb_ax = fig.add_axes([0.1, 0.04, 0.8, 0.025])
    fig.colorbar(cn_ws, cax=cb_ax, orientation='horizontal',
                 label='Wind Speed (kt)')

    os.makedirs(output_dir, exist_ok=True)
    out_fn = f"{output_dir}/{dt_str2}_FT{ft_hours:03d}h_ECM_{tagHp}hPa_Height_Wind.png"
    plt.savefig(out_fn, dpi=150, bbox_inches='tight')
    print(f"[{ft_hours:4d}h] 出力: {out_fn}")
    plt.close()
    return True


def plot_avg(i_year, i_month, i_day, i_hourZ, batch_start_h, avg_steps, tagHp, output_dir, area=None, smooth_size=3, wind_step=12):
    """avg_steps個のFT（6h間隔）データを平均して1枚の天気図を生成する"""
    ft_list = [batch_start_h + i * 6 for i in range(avg_steps)]
    batch_end_h = ft_list[-1]

    valHt_all, valWu_all, valWv_all = [], [], []
    lat = lon = None
    dt_str = dt_str2 = None

    for ft_h in ft_list:
        if i_hourZ in (0, 12):
            ecm_fn = f"{i_year:04d}{i_month:02d}{i_day:02d}{i_hourZ:02d}0000-{ft_h:d}h-oper-fc.grib2"
        else:
            ecm_fn = f"{i_year:04d}{i_month:02d}{i_day:02d}{i_hourZ:02d}0000-{ft_h:d}h-scda-fc.grib2"
        ecm_path = f"{DATA_DIR}/{ecm_fn}"

        if not ensure_file_ecm(ecm_path, ecm_fn, i_year, i_month, i_day, i_hourZ):
            print(f"  スキップ: FT={ft_h}h（データ取得失敗）")
            return False

        print(f"  [{ft_h:4d}h] データ読み込み: {ecm_fn}")
        grbs  = pygrib.open(ecm_path)
        grbHt = grbs(shortName="gh", typeOfLevel='isobaricInhPa', level=tagHp)[0]
        grbWu = grbs(shortName="u",  typeOfLevel='isobaricInhPa', level=tagHp)[0]
        grbWv = grbs(shortName="v",  typeOfLevel='isobaricInhPa', level=tagHp)[0]
        grbs.close()

        latS, latN, lonW, lonE = -20, 80, 70, 190
        _valHt, latHt, lonHt = grbHt.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)
        _valWu, _, _          = grbWu.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)
        _valWv, _, _          = grbWv.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)

        _valHt = uniform_filter(_valHt, size=smooth_size)
        _valWu = uniform_filter(_valWu, size=smooth_size)
        _valWv = uniform_filter(_valWv, size=smooth_size)

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

    fig = plt.figure(figsize=(13, 9))
    plt.subplots_adjust(left=0, right=1, bottom=0.18, top=0.98)
    ax = fig.add_subplot(1, 1, 1, projection=proj)
    ax.set_extent(areaAry, latlon_proj)

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

    lat_sl = slice(None, None, wind_step)
    lon_sl = slice(None, None, wind_step)
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
    fig.text(0.5, 0.13,
             f"ECM {avg_label} IT:{dt_str} {tagHp}hPa Height(m), ISOTAC(kt), Wind(kt)",
             ha='center', va='bottom', size=15)

    cb_ax = fig.add_axes([0.1, 0.04, 0.8, 0.025])
    fig.colorbar(cn_ws, cax=cb_ax, orientation='horizontal', label='Wind Speed (kt)')

    os.makedirs(output_dir, exist_ok=True)
    out_fn = f"{output_dir}/{dt_str2}_{avg_label}_ECM_{tagHp}hPa_Height_Wind.png"
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

    ft_list = build_ft_list(args.start_ft, args.n_steps)

    print(f"初期時刻: {init_str} UTC  気圧面: {args.level}hPa")
    print(f"予報時間: FT{ft_list[0]}h〜FT{ft_list[-1]}h（{args.n_steps}枚）")
    print()

    if args.avg_steps > 1:
        print(f"平均モード: start_ft={args.start_ft}h, avg_steps={args.avg_steps}, n_steps={args.n_steps}")
        print()
        success = 0
        for step_i in range(args.n_steps):
            batch_start_h = args.start_ft + step_i * (6 * args.avg_steps)
            if plot_avg(i_year, i_month, i_day, i_hourZ, batch_start_h, args.avg_steps, args.level, "./output",
                        area=args.area, smooth_size=args.smooth_size, wind_step=args.wind_step):
                success += 1
        print(f"\n完了: {success}/{args.n_steps}枚 出力先: ./output/")
    else:
        success = 0
        for ft_h in ft_list:
            if plot_one(i_year, i_month, i_day, i_hourZ, ft_h, args.level, "./output",
                        area=args.area, smooth_size=args.smooth_size, wind_step=args.wind_step):
                success += 1
        print(f"\n完了: {success}/{args.n_steps}枚 出力先: ./output/")


if __name__ == "__main__":
    main()
