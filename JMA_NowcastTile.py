#!/usr/bin/env python
# coding: utf-8

# 気象庁 高解像度降水ナウキャスト実況タイル 描画スクリプト
# 新規作成 20260810 上原政博
#
# データソース: 気象庁防災情報Webサイトの公開タイルAPI（認証不要・無償）
#   https://www.jma.go.jp/bosai/jmatile/data/nowc/{時刻}/none/{時刻}/surf/hrpns/{z}/{x}/{y}.png
#
# 参考実装: /Users/masahiro/web/webapp/gmsRadarAmedasTileViewer（同APIを使用した既存Webビューア）
#
# 注意: これは「解析雨量」そのものではなく「高解像度降水ナウキャスト実況」（hrpns）。
#   レーダー+アメダス較正という点では解析雨量と同種のデータだが、別プロダクト。
#   タイルはPNG着色画像（8階調に量子化済み）であり、JMA_AnalysisRain.py（GRIB2、
#   連続値・過去任意時刻）とは異なり、直近時刻のみ・粗い階調でしか取得できない。
#   長期アーカイブなし（ナウキャストのローリングウィンドウのみ）。

import os
os.environ['PROJ_LIB'] = '/opt/anaconda3/envs/met_env_310/share/proj'  # ★importの前に設定！

import sys
import io
import math
import argparse
import datetime as dt

import numpy as np
import requests
from PIL import Image
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import cartopy.crs as ccrs

from pyproj import datadir
datadir.set_data_dir(os.environ['PROJ_LIB'])

BASE_URL = "https://www.jma.go.jp/bosai/jmatile/data/nowc"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; JMA-NowcastTile/1.0)"}

# タイル配信の実測レイテンシ（gmsRadarAmedasTileViewer/js/image_util.js の値に準拠）
PUBLISH_LATENCY_MIN = 12.5
DATA_INTERVAL_MIN = 5

JAPAN_AREA = [122.0, 148.0, 24.0, 46.0]  # LON_W, LON_E, LAT_S, LAT_N
TILE_SIZE = 256
MERC_R = 6378137.0
MERC_ORIGIN_SHIFT = math.pi * MERC_R  # 20037508.34...

# 高解像度降水ナウキャスト凡例（legend_jp_normal_hrpns.svg 準拠、実タイル画素で検証済み）
# (R,G,B) -> 階級下限 mm/h
COLOR_TABLE = [
    ((242, 242, 255), 1),
    ((160, 210, 255), 5),
    ((33, 140, 255), 10),
    ((0, 65, 255), 20),
    ((255, 245, 0), 30),
    ((255, 153, 0), 50),
    ((255, 40, 0), 80),
    ((180, 0, 104), 80),  # 80mm/h以上（最上位区分）
]
LEVELS = [1, 5, 10, 20, 30, 50, 80]
COLORS = ['#f2f2ff', '#a0d2ff', '#218cff', '#0041ff', '#fff500', '#ff9900', '#ff2800', '#b40068']


def latest_valid_time():
    now = dt.datetime.now(dt.timezone.utc)
    t = now - dt.timedelta(minutes=PUBLISH_LATENCY_MIN)
    epoch_minutes = int(t.timestamp() // 60)
    rounded = epoch_minutes - (epoch_minutes % DATA_INTERVAL_MIN)
    return dt.datetime.fromtimestamp(rounded * 60, tz=dt.timezone.utc)


def parse_valid_time(value):
    if len(value) == 10:
        value += "00"
    if len(value) != 12 or not value.isdigit():
        raise ValueError("valid_time は YYYYMMDDHHMM（12桁）または YYYYMMDDHH（10桁、分=00）で指定してください")
    valid = dt.datetime.strptime(value, "%Y%m%d%H%M").replace(tzinfo=dt.timezone.utc)
    if valid.minute % DATA_INTERVAL_MIN != 0:
        raise ValueError(f"高解像度降水ナウキャストは{DATA_INTERVAL_MIN}分間隔のデータのみ存在します")
    return valid


def lonlat_to_tile(lon, lat, zoom):
    n = 2 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    lat_rad = math.radians(lat)
    y = int((1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi) / 2.0 * n)
    return x, y


def tile_to_merc(x, y, zoom):
    n = 2 ** zoom
    mx = x / n * (2 * MERC_ORIGIN_SHIFT) - MERC_ORIGIN_SHIFT
    my = MERC_ORIGIN_SHIFT - y / n * (2 * MERC_ORIGIN_SHIFT)
    return mx, my


def fetch_tile(valid, zoom, x, y, session):
    ts = valid.strftime("%Y%m%d%H%M%S")
    url = f"{BASE_URL}/{ts}/none/{ts}/surf/hrpns/{zoom}/{x}/{y}.png"
    try:
        r = session.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None
        return Image.open(io.BytesIO(r.content)).convert("RGBA")
    except requests.RequestException:
        return None


def fetch_and_stitch(valid, zoom, area):
    lon_w, lon_e, lat_s, lat_n = area
    x0, y0 = lonlat_to_tile(lon_w, lat_n, zoom)
    x1, y1 = lonlat_to_tile(lon_e, lat_s, zoom)

    n_x = x1 - x0 + 1
    n_y = y1 - y0 + 1
    print(f"タイル取得範囲: zoom={zoom}  x={x0}-{x1}({n_x}枚)  y={y0}-{y1}({n_y}枚)  計{n_x * n_y}枚")

    canvas = Image.new("RGBA", (n_x * TILE_SIZE, n_y * TILE_SIZE), (255, 255, 255, 0))
    session = requests.Session()
    ok = 0
    for ix, tx in enumerate(range(x0, x1 + 1)):
        for iy, ty in enumerate(range(y0, y1 + 1)):
            img = fetch_tile(valid, zoom, tx, ty, session)
            if img is not None:
                canvas.paste(img, (ix * TILE_SIZE, iy * TILE_SIZE))
                ok += 1
    print(f"取得成功: {ok}/{n_x * n_y}枚")
    if ok == 0:
        return None, None

    left, top = tile_to_merc(x0, y0, zoom)
    right, bottom = tile_to_merc(x1 + 1, y1 + 1, zoom)
    extent = [left, right, bottom, top]
    return canvas, extent


def decode_colors(canvas):
    arr = np.array(canvas)
    rgb = arr[:, :, :3].astype(np.int16)
    alpha = arr[:, :, 3]

    category = np.full(arr.shape[:2], np.nan)
    for (r, g, b), val in COLOR_TABLE:
        match = (rgb[:, :, 0] == r) & (rgb[:, :, 1] == g) & (rgb[:, :, 2] == b) & (alpha > 0)
        category[match] = val

    total = alpha.size
    rain_px = int(np.isfinite(category).sum())
    print(f"降水あり画素: {rain_px}/{total} ({rain_px / total * 100:.2f}%)")
    for (r, g, b), val in COLOR_TABLE:
        cnt = int(((rgb[:, :, 0] == r) & (rgb[:, :, 1] == g) & (rgb[:, :, 2] == b) & (alpha > 0)).sum())
        if cnt > 0:
            print(f"  {val:3d}mm/h台: {cnt}画素")
    return category


def parse_args():
    parser = argparse.ArgumentParser(
        description='気象庁 高解像度降水ナウキャスト実況タイルから現在の降水分布図を描画する',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python JMA_NowcastTile.py                          # 直近時刻・日本域
  python JMA_NowcastTile.py --valid-time 202608100900 # 時刻指定（UTC）
  python JMA_NowcastTile.py --area 128 142 30 40      # 描画範囲指定
  python JMA_NowcastTile.py --zoom 8                  # 高解像度（タイル数増）

注意:
  「解析雨量」そのものではなく「高解像度降水ナウキャスト実況」（別プロダクト）。
  PNGタイルの8階調着色を色から逆引きしているため、連続値ではない。
  ナウキャストのローリングウィンドウ内（直近のみ）でしか取得できない。

実行環境（conda の場合）:
  conda activate met_env_310
  python JMA_NowcastTile.py [引数]
"""
    )
    parser.add_argument('--valid-time', type=str, default=None,
                        help='解析時刻 YYYYMMDDHHMM または YYYYMMDDHH（UTC、5分間隔。省略時は自動推定）')
    parser.add_argument('--area', type=float, nargs=4, default=JAPAN_AREA,
                        metavar=('LON_W', 'LON_E', 'LAT_S', 'LAT_N'),
                        help=f'描画範囲（デフォルト: {JAPAN_AREA}）')
    parser.add_argument('--zoom', type=int, default=7, help='タイルズームレベル（デフォルト: 7）')
    parser.add_argument('--output-dir', default='./output', help='PNG出力先（デフォルト: ./output）')

    if any(a in sys.argv[1:] for a in ('?', '-?', '--?')):
        parser.print_help()
        sys.exit(0)

    return parser.parse_args()


def main():
    args = parse_args()

    if args.valid_time:
        try:
            valid = parse_valid_time(args.valid_time)
        except ValueError as e:
            print(f"エラー: {e}")
            sys.exit(1)
    else:
        valid = latest_valid_time()

    print(f"解析時刻(UTC): {valid:%Y-%m-%d %H:%M}  範囲: {args.area}  zoom={args.zoom}")

    canvas, extent = fetch_and_stitch(valid, args.zoom, args.area)
    if canvas is None:
        print("エラー: タイルを1枚も取得できませんでした（時刻がナウキャストの提供範囲外の可能性）")
        sys.exit(1)

    decode_colors(canvas)

    proj_merc = ccrs.epsg(3857)
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(1, 1, 1, projection=proj_merc)
    ax.set_extent(extent, crs=proj_merc)
    ax.imshow(np.array(canvas), origin='upper', extent=extent, transform=proj_merc, interpolation='nearest')
    ax.coastlines(resolution='50m', linewidth=1.2, color='black')

    cmap = mcolors.ListedColormap(COLORS)
    norm = mcolors.BoundaryNorm(LEVELS + [150], cmap.N)
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    cb = fig.colorbar(sm, ax=ax, orientation='vertical', shrink=0.8, pad=0.02, ticks=LEVELS + [150])
    cb.set_label('mm/h')

    dt_str = valid.strftime("%H%MUTC%d%b%Y").upper()
    fig.text(0.5, 0.01, f"JMA High-Res Precip. Nowcast (obs)  {dt_str}", ha='center', va='bottom', size=15)

    os.makedirs(args.output_dir, exist_ok=True)
    out_fn = f"{args.output_dir}/{valid:%Y%m%d%H%M}_JMA_NowcastTile.png"
    plt.savefig(out_fn, dpi=150, bbox_inches='tight')
    print(f"出力: {out_fn}")
    plt.close()


if __name__ == "__main__":
    main()
