#!/usr/bin/env python
# coding: utf-8

# GSM 500hPa天気図（高度・相対渦度・H/Lスタンプ・渦度ピーク表示）描画スクリプト
# 元コード: note3.ipynb（黒良さんNoteをベースに上原が発展）
# 修正: 引数対応・自動DL・複数FT対応 20260409上原政博

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
from scipy.ndimage import maximum_filter, minimum_filter  # 新形式に修正済み

# RISHサーバーのベースURL
BASE_URL = "http://database.rish.kyoto-u.ac.jp/arch/jmadata/data/gpv/original"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; GSM-Downloader/1.0)"}


# ──────────────────────────────────────────
# ユーティリティ関数
# ──────────────────────────────────────────

def transform_lonlat_to_figure(lonlat, ax, proj):
    """
    緯度経度で指定したポイントの図上の座標を取得する。
    図法の座標 → pixel座標 → 図の座標 の3段変換。

    Returns:
        (図の座標, pixel座標, 図法の座標)
    """
    point_proj = proj.transform_point(*lonlat, ccrs.PlateCarree())
    point_pix  = ax.transData.transform(point_proj)
    point_fig  = ax.transAxes.inverted().transform(point_pix)
    return point_fig, point_pix, point_proj


def detect_peaks(image, filter_size=3, dist_cut=5.0, flag=0):
    """
    極大/極小ピーク検出。

    Args:
        image      : 2次元配列
        filter_size: この値×この値の範囲内の最大/最小値をピークとして検出
        dist_cut   : この距離以内のピークは1つにまとめる
        flag       : 0=最大値検出、0以外=最小値検出

    Returns:
        (row_indices, col_indices) のタプル
    """
    if flag == 0:
        local_ext = maximum_filter(image,
                        footprint=np.ones((filter_size, filter_size)), mode='constant')
        detected_peaks = np.ma.array(image, mask=~(image == local_ext))
    else:
        local_ext = minimum_filter(image,
                        footprint=np.ones((filter_size, filter_size)), mode='constant')
        detected_peaks = np.ma.array(image, mask=~(image == local_ext))

    peaks_index = np.where((detected_peaks.mask != True))
    (x, y) = peaks_index
    size = y.size

    # ピーク間の距離行列を計算
    dist = np.full((size, size), -1.0)
    for i in range(size):
        for j in range(size):
            if i == j:
                dist[i][j] = 0.0
            elif i > j:
                d = math.sqrt((y[i]-y[j])**2 + (x[i]-x[j])**2)
                dist[i][j] = d
                dist[j][i] = d

    # 距離がdist_cut以内の近隣ピークをまとめる
    Kinrin = []
    dSum   = []
    for i in range(size):
        tmpA = []
        distSum = 0.0
        for j in range(size):
            if 0.0 < dist[i][j] < dist_cut:
                tmpA.append(j)
                distSum += dist[i][j]
        dSum.append(distSum)
        Kinrin.append(tmpA)

    # 除外するピーク番号を決定（距離和が小さい方を残す）
    cutPoint = []
    for i in range(size):
        val   = dSum[i]
        val_i = image[x[i]][y[i]]
        for k in Kinrin[i]:
            val_k = image[x[k]][y[k]]
            if flag == 0 and val_i < val_k:
                cutPoint.append(i); break
            if flag != 0 and val_i > val_k:
                cutPoint.append(i); break
            if val > dSum[k]:
                cutPoint.append(i); break
            if val == dSum[k] and i > k:
                cutPoint.append(i); break

    newx = [x[i] for i in range(size) if i not in cutPoint]
    newy = [y[i] for i in range(size) if i not in cutPoint]
    return (np.array(newx), np.array(newy))


def ensure_file(gr_path: str, gr_fn: str, year: int, month: int, day: int) -> bool:
    """
    データファイルが存在しない場合、RISHサーバーから自動ダウンロードする。

    Returns:
        成功時 True、失敗時 False
    """
    if os.path.exists(gr_path):
        return True

    print(f"データファイルが見つかりません: {gr_fn}")
    print(f"RISHサーバーからダウンロードを試みます...")

    url  = f"{BASE_URL}/{year}/{month:02d}/{day:02d}/{gr_fn}"
    dest = Path(gr_path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    try:
        with requests.get(url, headers=HEADERS, stream=True, timeout=120) as r:
            r.raise_for_status()
            total      = int(r.headers.get("content-length", 0))
            downloaded = 0
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        pct = downloaded / total * 100
                        print(f"\r  {pct:.1f}% ({downloaded/(1024*1024):.1f}/{total/(1024*1024):.1f} MB)",
                              end="", flush=True)
            print()
        size_mb = dest.stat().st_size / (1024 * 1024)
        print(f"ダウンロード完了: {gr_fn} ({size_mb:.1f} MB)")
        return True
    except requests.HTTPError as e:
        print(f"\nダウンロード失敗（HTTP {e.response.status_code}）: {url}")
        if dest.exists():
            dest.unlink()
        return False
    except requests.RequestException as e:
        print(f"\nダウンロード失敗: {e}")
        if dest.exists():
            dest.unlink()
        return False


def ddhh_to_hours(ddhh: int) -> int:
    """DDHH形式の予報時間を時間数に変換する（例: 0112 → 36h）"""
    return (ddhh // 100) * 24 + (ddhh % 100)


def hours_to_ddhh(hours: int) -> int:
    """時間数をDDHH形式に変換する（例: 36 → 0112）"""
    return (hours // 24) * 100 + (hours % 24)


def build_ft_list(start_ddhh: int, n_steps: int) -> list[int]:
    """開始FT（DDHH形式）からn_steps個のFTリストを6h間隔で生成する。"""
    start_h = ddhh_to_hours(start_ddhh)
    return [hours_to_ddhh(start_h + i * 6) for i in range(n_steps)]


# ──────────────────────────────────────────
# 引数解析
# ──────────────────────────────────────────

def parse_args():
    """コマンドライン引数を解析する"""
    parser = argparse.ArgumentParser(
        description='GSM GPV GRIB2データから500hPa天気図（高度・渦度・H/Lスタンプ）を描画する',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python GSM_tekizu500hPa.py 2021082300 0000 1    # 初期値1枚
  python GSM_tekizu500hPa.py 2021082300 0000 5    # FT0h〜FT24h（6h間隔）5枚
  python GSM_tekizu500hPa.py 2021082300 0100 3    # FT24h〜FT36h（6h間隔）3枚
  python GSM_tekizu500hPa.py 2021082300 0000 4 500 # 500hPa（デフォルト）

引数説明:
  init_time : 初期時刻 YYYYMMDDHH（UTC）例: 2021082300
  start_ft  : 最初の予報時間 DDHH形式 例: 0000=FT0h, 0100=FT24h
  n_steps   : 作成する天気図の枚数（6h間隔）
  level     : 気圧面 hPa（省略可、デフォルト: 500）
        """
    )
    parser.add_argument('init_time', type=str,
                        help='初期時刻 YYYYMMDDHH（UTC）例: 2021082300')
    parser.add_argument('start_ft',  type=str,
                        help='最初の予報時間 DDHH形式 例: 0000, 0018, 0100')
    parser.add_argument('n_steps',   type=int,
                        help='作成する天気図の枚数（6h間隔）')
    parser.add_argument('level',     type=int, nargs='?', default=500,
                        help='気圧面 hPa（デフォルト: 500）')
    return parser.parse_args()


# ──────────────────────────────────────────
# 1FT分の描画
# ──────────────────────────────────────────

def plot_one(i_year: int, i_month: int, i_day: int, i_hourZ: int,
             ft_ddhh: int, tagHp: int, output_dir: str) -> bool:
    """
    1つの予報時間について天気図を描画してPNGに保存・画面表示する。

    Returns:
        成功時 True、失敗時 False
    """
    ft_hours = ddhh_to_hours(ft_ddhh)

    # GRIB2ファイル名を構築
    gsm_fn_t = "Z__C_RJTD_{0:04d}{1:02d}{2:02d}{3:02d}0000_GSM_GPV_Rgl_FD{4:04d}_grib2.bin"
    gr_fn    = gsm_fn_t.format(i_year, i_month, i_day, i_hourZ, ft_ddhh)
    gr_path  = f"./data_gsm/{gr_fn}"

    # ファイルがなければ自動ダウンロード
    if not ensure_file(gr_path, gr_fn, i_year, i_month, i_day):
        print(f"スキップ: FT={ft_hours}h（データ取得失敗）")
        return False

    print(f"[{ft_hours:4d}h] データ読み込み: {gr_fn}")

    # GRIB2読み込み
    grbs  = pygrib.open(gr_path)
    grbHt = grbs(shortName="gh", typeOfLevel='isobaricInhPa', level=tagHp)[0]
    grbWu = grbs(shortName="u",  typeOfLevel='isobaricInhPa', level=tagHp)[0]
    grbWv = grbs(shortName="v",  typeOfLevel='isobaricInhPa', level=tagHp)[0]
    grbs.close()

    # 領域切り出し
    latS, latN, lonW, lonE = -20, 80, 70, 190
    valHt, latHt, lonHt = grbHt.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)
    valWu, latWu, lonWu = grbWu.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)
    valWv, latWv, lonWv = grbWv.data(lat1=latS, lat2=latN, lon1=lonW, lon2=lonE)

    # xarrayデータセット作成
    ds = xr.Dataset(
        {
            "Geopotential_height": (["lat", "lon"], valHt),
            "u_wind":              (["lat", "lon"], valWu),
            "v_wind":              (["lat", "lon"], valWv),
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
    ds['level'].attrs['units']   = 'hPa'
    ds['lat'].attrs['units']     = 'degrees_north'
    ds['lon'].attrs['units']     = 'degrees_east'

    # 相対渦度を計算
    ds['vorticity'] = mpcalc.vorticity(ds['u_wind'], ds['v_wind'])

    # 図法・描画範囲
    proj        = ccrs.Stereographic(central_latitude=60, central_longitude=140)
    latlon_proj = ccrs.PlateCarree()
    areaAry     = [108, 156, 17, 55]  # 極東

    # 等値線の間隔
    levels_ht   = np.arange(4800, 6000,  60)           # 高度 60m間隔（実線）
    levels_ht2  = np.arange(4800, 6000, 300)           # 高度 300m間隔（太線）
    levels_vr   = np.arange(-0.0002, 0.0002, 0.00004)  # 渦度 4e-5毎

    # 渦度ハッチ設定
    levels_h_vr = [0.0, 0.00008, 1.0]  # 0.0以上: 灰色、8e-5以上: 赤
    colors_h_vr = ['0.9', 'red']
    alpha_h_vr  = 0.3

    # タイトル文字列
    dt_i    = grbHt.analDate
    dt_str  = (dt_i.strftime("%H00UTC%d%b%Y")).upper()
    dt_str2 = dt_i.strftime("%Y%m%d%H")

    # ── 描画 ──
    fig = plt.figure(figsize=(10, 8))
    plt.subplots_adjust(left=0, right=1, bottom=0.06, top=0.98)
    ax = fig.add_subplot(1, 1, 1, projection=proj)
    ax.set_extent(areaAry, latlon_proj)

    # 相対渦度ハッチ
    ax.contourf(ds['lon'], ds['lat'], ds['vorticity'],
                levels_h_vr, colors=colors_h_vr,
                alpha=alpha_h_vr, transform=latlon_proj)
    # 相対渦度等値線
    ax.contour(ds['lon'], ds['lat'], ds['vorticity'],
               levels_vr, colors='black', linewidths=1.0, transform=latlon_proj)
    # 等高度線（60m毎、実線）
    cn_hgt = ax.contour(ds['lon'], ds['lat'], ds['Geopotential_height'],
                        colors='black', linewidths=1.2,
                        levels=levels_ht, transform=latlon_proj)
    ax.clabel(cn_hgt, levels_ht, fontsize=15, inline=True,
              inline_spacing=5, fmt='%i', rightside_up=True)
    # 等高度線（300m毎、太線）
    cn_hgt2 = ax.contour(ds['lon'], ds['lat'], ds['Geopotential_height'],
                         colors='black', linewidths=1.5,
                         levels=levels_ht2, transform=latlon_proj)
    ax.clabel(cn_hgt2, fontsize=15, inline=True,
              inline_spacing=0, fmt='%i', rightside_up=True)
    # 5820gpm線（茶色・一点鎖線）
    ax.contour(ds['lon'], ds['lat'], ds['Geopotential_height'],
               colors='brown', linestyles='dashdot',
               linewidths=1.2, levels=[5820], transform=latlon_proj)
    # 5400gpm線（青色・一点鎖線）
    ax.contour(ds['lon'], ds['lat'], ds['Geopotential_height'],
               colors='blue', linestyles='dashdot',
               linewidths=1.2, levels=[5400], transform=latlon_proj)

    # ＋スタンプ（渦度極大）
    maxid = detect_peaks(ds['vorticity'].values, filter_size=3, dist_cut=4.0)
    for i in range(len(maxid[0])):
        wlon  = ds['lon'][maxid[1][i]]
        wlat  = ds['lat'][maxid[0][i]]
        fig_z, _, _ = transform_lonlat_to_figure((wlon, wlat), ax, proj)
        if 0.0 < fig_z[0] < 1.0 and 0.0 < fig_z[1] < 1.0:
            val  = ds['vorticity'].values[maxid[0][i]][maxid[1][i]]
            ival = int(val * 1000000.0)
            if ival > 30:
                ax.plot(wlon, wlat, marker='+', markersize=7,
                        color="red", transform=latlon_proj)
                if ival > 50:
                    ax.text(fig_z[0], fig_z[1]-0.01, str(ival), size=14,
                            color="black", transform=ax.transAxes,
                            verticalalignment="top", horizontalalignment="center")

    # －スタンプ（渦度極小）
    minid = detect_peaks(ds['vorticity'].values, filter_size=3, dist_cut=4.0, flag=1)
    for i in range(len(minid[0])):
        wlon  = ds['lon'][minid[1][i]]
        wlat  = ds['lat'][minid[0][i]]
        fig_z, _, _ = transform_lonlat_to_figure((wlon, wlat), ax, proj)
        if 0.0 < fig_z[0] < 1.0 and 0.0 < fig_z[1] < 1.0:
            val  = ds['vorticity'].values[minid[0][i]][minid[1][i]]
            ival = int(val * -1000000.0)
            if ival > 30:
                ax.plot(wlon, wlat, marker='_', markersize=8,
                        color="blue", transform=latlon_proj)
                if ival > 50:
                    ax.text(fig_z[0], fig_z[1]-0.01, str(ival), size=12,
                            color="blue", transform=ax.transAxes,
                            verticalalignment="top", horizontalalignment="center")

    # H スタンプ（高度極大）
    maxid = detect_peaks(ds['Geopotential_height'].values, filter_size=10, dist_cut=8.0)
    for i in range(len(maxid[0])):
        wlon  = ds['lon'][maxid[1][i]]
        wlat  = ds['lat'][maxid[0][i]]
        fig_z, _, _ = transform_lonlat_to_figure((wlon, wlat), ax, proj)
        if 0.0 < fig_z[0] < 1.0 and 0.0 < fig_z[1] < 1.0:
            ax.text(wlon, wlat, 'H', size=24, color="blue",
                    ha='center', va='center', transform=latlon_proj)

    # L スタンプ（高度極小）
    minid = detect_peaks(ds['Geopotential_height'].values, filter_size=10, dist_cut=8.0, flag=1)
    for i in range(len(minid[0])):
        wlon  = ds['lon'][minid[1][i]]
        wlat  = ds['lat'][minid[0][i]]
        fig_z, _, _ = transform_lonlat_to_figure((wlon, wlat), ax, proj)
        if 0.0 < fig_z[0] < 1.0 and 0.0 < fig_z[1] < 1.0:
            ax.text(wlon, wlat, 'L', size=24, color="red",
                    ha='center', va='center', transform=latlon_proj)

    # 海岸線・グリッド線
    ax.coastlines(resolution='50m')
    xticks = np.arange(0, 360.1, 10)
    yticks = np.arange(-90, 90.1, 10)
    gl = ax.gridlines(crs=ccrs.PlateCarree(), draw_labels=False, linewidth=1, alpha=0.8)
    gl.xlocator = mticker.FixedLocator(xticks)
    gl.ylocator = mticker.FixedLocator(yticks)

    # タイトル
    fig.text(0.5, 0.01,
             f"GSM FT{ft_hours:d}h IT:{dt_str} {tagHp}hPa Height(m),VORT",
             ha='center', va='bottom', size=18)

    # PNG保存 → 画面表示
    os.makedirs(output_dir, exist_ok=True)
    out_fn = f"{output_dir}/{dt_str2}_FT{ft_hours:03d}h_{tagHp}hPa_Height_VORT.png"
    plt.savefig(out_fn, dpi=150, bbox_inches='tight')
    print(f"[{ft_hours:4d}h] 出力: {out_fn}")
    plt.show()
    plt.close()
    return True


# ──────────────────────────────────────────
# メイン
# ──────────────────────────────────────────

def main():
    args = parse_args()

    # 初期時刻を解析
    init_str = args.init_time
    if len(init_str) != 10:
        print("エラー: init_time は YYYYMMDDHH の10桁で指定してください（例: 2021082300）")
        sys.exit(1)

    i_year  = int(init_str[0:4])
    i_month = int(init_str[4:6])
    i_day   = int(init_str[6:8])
    i_hourZ = int(init_str[8:10])
    tagHp   = args.level

    # 描画するFTリストを生成（start_ftからn_steps個、6h間隔）
    start_ddhh = int(args.start_ft)
    ft_list    = build_ft_list(start_ddhh, args.n_steps)

    start_h = ddhh_to_hours(start_ddhh)
    end_h   = ddhh_to_hours(ft_list[-1])
    print(f"初期時刻: {init_str} UTC")
    print(f"予報時間: FT{start_h}h〜FT{end_h}h（{args.n_steps}枚、6h間隔）")
    print(f"気圧面: {tagHp}hPa")
    print()

    # 各FTについて描画
    success = 0
    for ft_ddhh in ft_list:
        if plot_one(i_year, i_month, i_day, i_hourZ, ft_ddhh, tagHp, "./output"):
            success += 1

    print(f"\n完了: {success}/{args.n_steps}枚 出力先: ./output/")


if __name__ == "__main__":
    main()
