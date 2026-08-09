#!/usr/bin/env python
# coding: utf-8

# 気象庁 解析雨量（1kmメッシュ）描画スクリプト
# 新規作成 20260810 上原政博
#
# データソース: 気象庁 解析雨量GRIB2（Z__C_RJTD_..._Prr60lv_ANAL_grib2.bin）
#
# 注意: 解析雨量GRIB2は気象庁ローカルの productDefinitionTemplate（第4節50008）と
#       独自のランレングス圧縮（第7節）を使用しており、pygrib（eccodes）では
#       "Unable to find template productDefinition" エラーとなり読み込めない。
#       そのため本スクリプトでは GRIB2 の第5節・第7節を自前でパースする
#       （手法参考: https://qiita.com/vpcf/items/b680f504cfe8b6a64222 ）。
#
# データ入手: 気象業務支援センター（有償）が正規の配信元。無償の自動ダウンロード元は
#       未確認のため、本スクリプトは自動DLに対応していない。
#       data/jmara/ に該当ファイルを手動配置して実行すること。
#       動作確認用サンプルは気象庁公式サンプルページから入手可能：
#       https://www.data.jma.go.jp/developer/gpv_sample/kotan_kaiseki.zip

import os
import sys
import argparse
import struct
import datetime as dt
from itertools import repeat
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import cartopy.crs as ccrs

# 解析雨量1kmメッシュの格子仕様（全国合成: 3360行 x 2560列、20-48N/118-150E）
GRID_SHAPE = (3360, 2560)
GRID_LON_RANGE = (118.0, 150.0)
GRID_LAT_RANGE = (48.0, 20.0)  # 北→南


def set_table(section5):
    max_level = struct.unpack_from('>H', section5, 15)[0]
    table = (
        -10,
        *struct.unpack_from('>' + str(max_level) + 'H', section5, 18)
    )
    return np.array(table, dtype=np.int16)


def decode_runlength(code, hi_level):
    level = 0
    for raw in code:
        if raw <= hi_level:
            level = raw
            pwr = 0
            yield level
        else:
            length = (0xFF - hi_level) ** pwr * (raw - (hi_level + 1))
            pwr += 1
            yield from repeat(level, length)


def load_jmara_grib2(path):
    with open(path, 'rb') as f:
        binary = f.read()

    len_ = {'sec0': 16, 'sec1': 21, 'sec3': 72, 'sec4': 82, 'sec6': 6}

    end4 = len_['sec0'] + len_['sec1'] + len_['sec3'] + len_['sec4'] - 1
    len_['sec5'] = struct.unpack_from('>I', binary, end4 + 1)[0]
    section5 = binary[end4:(end4 + len_['sec5'] + 1)]

    end6 = end4 + len_['sec5'] + len_['sec6']
    len_['sec7'] = struct.unpack_from('>I', binary, end6 + 1)[0]
    section7 = binary[end6:(end6 + len_['sec7'] + 1)]

    highest_level = struct.unpack_from('>H', section5, 13)[0]
    level_table = set_table(section5)
    decoded = np.fromiter(
        decode_runlength(section7[6:], highest_level), dtype=np.int16
    ).reshape(GRID_SHAPE)

    return level_table[decoded]


def jmara_grid():
    ny, nx = GRID_SHAPE
    lon = np.linspace(*GRID_LON_RANGE, nx, endpoint=False) + 1 / 80 / 2
    lat = np.linspace(*GRID_LAT_RANGE, ny, endpoint=False) - 1 / 80 / 1.5 / 2
    return lon, lat


def jmara_filename(valid):
    return f"Z__C_RJTD_{valid:%Y%m%d%H%M}00_SRF_GPV_Ggis1km_Prr60lv_ANAL_grib2.bin"


def parse_valid_time(value):
    if len(value) == 10:
        value += "00"
    if len(value) != 12 or not value.isdigit():
        raise ValueError("valid_time は YYYYMMDDHHMM（12桁）または YYYYMMDDHH（10桁、分=00）で指定してください")
    valid = dt.datetime.strptime(value, "%Y%m%d%H%M").replace(tzinfo=dt.timezone.utc)
    if valid.minute not in (0, 30):
        raise ValueError("解析雨量は毎時00分・30分のデータのみ存在します")
    return valid


def build_valid_time_list(start, steps, interval_min):
    return [start + dt.timedelta(minutes=interval_min * i) for i in range(steps)]


def parse_args():
    parser = argparse.ArgumentParser(
        description='気象庁 解析雨量（1kmメッシュ）GRIB2から降水強度分布図を描画する',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python JMA_AnalysisRain.py 202108170900              # 1枚
  python JMA_AnalysisRain.py 202108170900 3            # 30分間隔で3枚
  python JMA_AnalysisRain.py 202108170900 3 --interval-min 60

事前準備:
  data/jmara/ に Z__C_RJTD_YYYYMMDDHHMM00_SRF_GPV_Ggis1km_Prr60lv_ANAL_grib2.bin
  形式のファイルを手動配置しておくこと（自動ダウンロード未対応）。

実行環境（conda の場合）:
  conda activate met_env_310
  python JMA_AnalysisRain.py [引数]
"""
    )
    parser.add_argument('valid_time', type=str, help='解析時刻 YYYYMMDDHHMM または YYYYMMDDHH（UTC）')
    parser.add_argument('steps', type=int, nargs='?', default=1, help='作成する枚数（デフォルト: 1）')
    parser.add_argument('--interval-min', type=int, default=30, help='時刻間隔（分、デフォルト: 30）')
    parser.add_argument('--data-dir', default='./data/jmara', help='GRIB2ファイル配置先（デフォルト: ./data/jmara）')
    parser.add_argument('--output-dir', default='./output', help='PNG出力先（デフォルト: ./output）')
    parser.add_argument('--area', type=float, nargs=4, default=None,
                        metavar=('LON_W', 'LON_E', 'LAT_S', 'LAT_N'),
                        help='描画範囲（デフォルト: データ全域 118 150 20 48）')
    parser.add_argument('--vmax', type=float, default=80.0, help='カラースケール上限 mm/h（デフォルト: 80）')

    if any(a in sys.argv[1:] for a in ('?', '-?', '--?')):
        parser.print_help()
        sys.exit(0)

    return parser.parse_args()


def plot_one(valid, data_dir, output_dir, area=None, vmax=80.0):
    fn = jmara_filename(valid)
    path = Path(data_dir) / fn

    if not path.exists():
        print(f"[{valid:%Y-%m-%d %H:%M}Z] スキップ: ファイルが見つかりません: {path}")
        print("  data/jmara/ に手動配置してください（自動ダウンロード未対応）")
        return False

    print(f"[{valid:%Y-%m-%d %H:%M}Z] データ読み込み: {fn}")
    rain = load_jmara_grib2(path) / 10.0
    rain = np.where(rain < 0, np.nan, rain)  # 欠測（レベル0未満）を除外

    lon, lat = jmara_grid()

    levels = [0.1, 1, 5, 10, 20, 30, 50, vmax]
    colors = ['lightskyblue', 'deepskyblue', 'blue', 'lime', 'yellow', 'orange', 'red']
    cmap = mcolors.ListedColormap(colors)
    cmap.set_under('white')
    cmap.set_over('magenta')
    norm = mcolors.BoundaryNorm(levels, cmap.N)

    i_area = area if area is not None else [*GRID_LON_RANGE, GRID_LAT_RANGE[1], GRID_LAT_RANGE[0]]

    proj = ccrs.PlateCarree()
    fig = plt.figure(figsize=(10, 8))
    plt.subplots_adjust(left=0, right=1, bottom=0.06, top=0.95)
    ax = fig.add_subplot(1, 1, 1, projection=proj)
    ax.set_extent(i_area, proj)

    mesh = ax.pcolormesh(lon, lat, rain, cmap=cmap, norm=norm, transform=proj, shading='auto')
    ax.coastlines(resolution='50m', linewidth=1.2)
    cb = fig.colorbar(mesh, ax=ax, orientation='vertical', extend='both', shrink=0.8, pad=0.02)
    cb.set_label('mm/h')

    dt_str = valid.strftime("%H%MUTC%d%b%Y").upper()
    fig.text(0.5, 0.01, f"JMA Analysis of Precipitation  {dt_str}", ha='center', va='bottom', size=15)

    os.makedirs(output_dir, exist_ok=True)
    out_fn = f"{output_dir}/{valid:%Y%m%d%H%M}_JMA_AnalysisRain.png"
    plt.savefig(out_fn, dpi=150, bbox_inches='tight')
    print(f"[{valid:%Y-%m-%d %H:%M}Z] 出力: {out_fn}")
    plt.close()
    return True


def main():
    args = parse_args()
    try:
        start = parse_valid_time(args.valid_time)
    except ValueError as e:
        print(f"エラー: {e}")
        sys.exit(1)

    valid_list = build_valid_time_list(start, args.steps, args.interval_min)

    print(f"解析時刻: {start:%Y-%m-%d %H:%M} UTC〜  {args.steps}枚（{args.interval_min}分間隔）")
    print()

    success = 0
    for valid in valid_list:
        if plot_one(valid, args.data_dir, args.output_dir, area=args.area, vmax=args.vmax):
            success += 1
    print(f"\n完了: {success}/{len(valid_list)}枚 出力先: {args.output_dir}/")


if __name__ == "__main__":
    main()
