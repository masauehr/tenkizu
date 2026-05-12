#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
エマグラム・温位エマグラム描画スクリプト
  参考: 黒良 R.  https://note.com/rkurora/
  作成: 上原政博
"""

import sys

# --show 未指定時は非インタラクティブバックエンドを使用
if '--show' not in sys.argv:
    import matplotlib
    matplotlib.use('Agg')

import matplotlib
matplotlib.rcParams['font.family'] = ['Hiragino Sans', 'DejaVu Sans']

import argparse
import os
import subprocess
from datetime import datetime, timezone, timedelta

import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from mpl_toolkits.axes_grid1.inset_locator import inset_axes

import numpy as np
import metpy
import metpy.calc as mpcalc
from metpy.plots import SkewT, Hodograph
from metpy.units import pandas_dataframe_to_unit_arrays, units
from siphon.simplewebservice.wyoming import WyomingUpperAir


# ── 地点辞書（優先度順） ───────────────────────────────────────────────────────
STATIONS = {
    # ── 優先地点（南西諸島） ──
    '石垣島':   {'id': '47918', 'region': '南西諸島'},
    '南大東島': {'id': '47945', 'region': '南西諸島'},
    '名瀬':     {'id': '47909', 'region': '南西諸島'},
    # ── 九州 ──
    '鹿児島':   {'id': '47827', 'region': '九州'},
    '福岡':     {'id': '47807', 'region': '九州'},
    # ── 近畿 ──
    '潮岬':     {'id': '47778', 'region': '近畿'},
    # ── 関東 ──
    '館野':     {'id': '47646', 'region': '関東'},
    '八丈島':   {'id': '47678', 'region': '関東'},
    # ── 北陸 ──
    '輪島':     {'id': '47600', 'region': '北陸'},
    # ── 東北 ──
    '秋田':     {'id': '47582', 'region': '東北'},
    # ── 北海道 ──
    '稚内':     {'id': '47401', 'region': '北海道'},
    # ── 台湾 ── (Wyoming Upper Airにデータがない場合はエラーになる)
    '花蓮':     {'id': '46699', 'region': '台湾'},
    '台北':     {'id': '46692', 'region': '台湾'},
}

DEFAULT_STATION = '石垣島'


# ── 温位エマグラム用: 等飽和混合比曲線（横軸＝温位）を SkewT に追加 ────────────
def _plot_mixing_lines_pt(self, mixing_ratio=None, pressure=None, **kwargs):
    """SkewT に温位エマグラム用の等飽和混合比曲線を追加するメソッド"""
    if self.mixing_lines:
        self.mixing_lines.remove()

    if mixing_ratio is None:
        mixing_ratio = np.array(
            [0.0004, 0.001, 0.002, 0.004, 0.007, 0.01, 0.016, 0.024, 0.032]
        ).reshape(-1, 1)

    if pressure is None:
        pressure = units.Quantity(
            np.linspace(600, max(self.ax.get_ylim())), 'mbar'
        )

    td = mpcalc.dewpoint(mpcalc.vapor_pressure(pressure, mixing_ratio))
    pt = mpcalc.potential_temperature(pressure, td).to(units.degree_Celsius)
    linedata = [np.vstack((t.m, pressure.m)).T for t in pt]

    kwargs.setdefault('colors', 'g')
    kwargs.setdefault('linestyles', 'dashed')
    kwargs.setdefault('alpha', 0.8)
    self.mixing_lines = self.ax.add_collection(LineCollection(linedata, **kwargs))
    return self.mixing_lines


metpy.plots.SkewT.plot_mixing_lines_pt = _plot_mixing_lines_pt


# ── データ取得 ─────────────────────────────────────────────────────────────────
def fetch_data(dt: datetime, station_id: str) -> dict:
    """Wyoming Upper Air サービスから高層ゾンデデータを取得する"""
    print(f"  データ取得中 [{station_id}] {dt.strftime('%Y-%m-%d %HUTC')}")
    df = WyomingUpperAir.request_data(dt, station_id)
    data = pandas_dataframe_to_unit_arrays(df)
    return {
        'p':  data['pressure'],
        'T':  data['temperature'],
        'Td': data['dewpoint'],
        'u':  data['u_wind'],
        'v':  data['v_wind'],
        'h':  data['height'],
    }


# ── エマグラム描画 ──────────────────────────────────────────────────────────────
def draw_emagram(fig: plt.Figure, d: dict, dt: datetime, label: str) -> SkewT:
    """温度・露点・風・CAPE/CIN・ホドグラフを描画するエマグラム"""
    p, T, Td, u, v, h = d['p'], d['T'], d['Td'], d['u'], d['v'], d['h']

    # 850hPa以下で最大相当温位となる高度の気塊を選び持ち上げる
    p_mag = p.magnitude.tolist()
    i_85 = next((i for i, pi in enumerate(p_mag) if pi <= 850.0), 0)
    ept = mpcalc.equivalent_potential_temperature(
        p[:i_85 + 1], T[:i_85 + 1], Td[:i_85 + 1]
    )
    i_eptmax = int(np.argmax(ept.magnitude))
    prof = mpcalc.parcel_profile(
        p[i_eptmax:], T[i_eptmax], Td[i_eptmax]
    ).to('degC')
    lcl_p, lcl_T = mpcalc.lcl(p[i_eptmax], T[i_eptmax], Td[i_eptmax])

    skew = SkewT(fig, rotation=0, aspect=120)
    skew.ax.set_xlim(-70, 40)
    skew.ax.set_ylim(1020, 100)

    # 温度・露点・風
    skew.plot(p, T,  'r')
    skew.plot(p, Td, 'g')
    skew.plot_barbs(p, u, v, y_clip_radius=0.03)

    # パーセルプロファイル・持ち上げ開始点・LCL
    skew.plot(p[i_eptmax:], prof, 'k', linewidth=2, alpha=0.5)
    skew.plot(p[i_eptmax],  T[i_eptmax], 'ko', markerfacecolor='black')
    skew.plot(lcl_p,        lcl_T,        'ko', markerfacecolor='blue')

    # CAPE/CIN シェード（MetPy 1.7: 全引数を同サイズで渡す必要がある）
    skew.shade_cin(p[i_eptmax:],  T[i_eptmax:], prof)
    skew.shade_cape(p[i_eptmax:], T[i_eptmax:], prof)

    # 補助線（乾燥断熱線・湿潤断熱線・等混合比線）
    dry_tmp   = np.arange(203, 533, 10) * units.K
    moist_tmp = np.arange(203, 400,  5) * units.K
    mix_p     = np.arange(1000, 99, -20) * units.hPa
    skew.plot_dry_adiabats(t0=dry_tmp,    alpha=0.25, color='orangered')
    skew.plot_moist_adiabats(t0=moist_tmp, alpha=0.25, color='tab:green')
    skew.plot_mixing_lines(pressure=mix_p, linestyle='dotted', color='tab:blue')

    skew.ax.set_title(f'{label}  Emagram', loc='left')
    skew.ax.set_title(dt.strftime('%Y-%m-%d %HUTC'), loc='right')

    # ホドグラフ（右上インセット）
    ax_hod = inset_axes(skew.ax, '40%', '40%', loc=1)
    hd = Hodograph(ax_hod, component_range=80.)
    hd.add_grid(increment=20)
    hd.plot_colormapped(u, v, h)

    return skew


# ── 温位エマグラム描画 ─────────────────────────────────────────────────────────
def draw_pt_emagram(fig: plt.Figure, d: dict, dt: datetime, label: str) -> SkewT:
    """温位・相当温位・飽和相当温位・飽和温位・風を描画する温位エマグラム"""
    p, T, Td, u, v = d['p'], d['T'], d['Td'], d['u'], d['v']

    pt   = mpcalc.potential_temperature(p, T)
    spt  = mpcalc.potential_temperature(p, Td)
    ept  = mpcalc.equivalent_potential_temperature(p, T, Td)
    sept = mpcalc.saturation_equivalent_potential_temperature(p, T)

    # 全プロファイルの実測値から横軸範囲を自動決定（10K単位・5Kマージン）
    all_vals = np.concatenate([
        pt.magnitude, spt.magnitude, ept.magnitude, sept.magnitude
    ])
    valid = all_vals[np.isfinite(all_vals)]
    ax_min_val = int(np.floor((valid.min() - 5) / 10) * 10)
    ax_max_val = int(np.ceil( (valid.max() + 5) / 10) * 10)

    ax_min  = ax_min_val * units.K
    ax_max  = ax_max_val * units.K
    x_ticks = np.arange(ax_min_val, ax_max_val + 1, 10) * units.K

    skew = SkewT(fig, rotation=0, aspect=120)
    skew.ax.set_xlim(ax_min, ax_max)
    skew.ax.set_ylim(1020, 300)

    # X軸ラベルをケルビン表示に変換
    skew.ax.xaxis.set_major_formatter(
        plt.FuncFormatter(lambda x, _: '%d' % (273.15 + x))
    )
    skew.ax.set_xticks(x_ticks)
    skew.ax.set_xlabel('Kelvin')

    # 等飽和混合比曲線（横軸:温位）
    mr    = np.array([0.0004, 0.001, 0.002, 0.004, 0.007,
                       0.01, 0.016, 0.024, 0.032]).reshape(-1, 1)
    mix_p = np.arange(1000, 99, -20) * units.hPa
    skew.plot_mixing_lines_pt(pressure=mix_p, mixing_ratio=mr,
                               linestyle='dotted', color='tab:blue')

    # 各温位プロファイル
    skew.plot(p, pt,   'black',  label='θ (温位)')
    skew.plot(p, ept,  'g',      label='θe (相当温位)')
    skew.plot(p, sept, 'r',      label='θes (飽和相当温位)')
    skew.plot(p, spt,  'purple', label='θw (飽和温位)')
    skew.ax.legend(loc='upper right', fontsize=8)

    # 風
    skew.plot_barbs(p, u, v, y_clip_radius=0.03)

    skew.ax.set_title(f'{label}  PT-Emagram', loc='left')
    skew.ax.set_title(dt.strftime('%Y-%m-%d %HUTC'), loc='right')

    return skew


# ── git ヘルパー ────────────────────────────────────────────────────────────────
def _run_git(cmd: str, cwd: str) -> int:
    print(f'$ git {cmd}')
    result = subprocess.run(
        f'git {cmd}', shell=True, cwd=cwd, capture_output=True, text=True
    )
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip())
    return result.returncode


# ── Markdownレポート生成 ───────────────────────────────────────────────────────
def make_report(report_dir: str, dt: datetime, label: str,
                figs: list[tuple[plt.Figure, str]]) -> str:
    """PNGをreport_dirに保存し、Markdownレポートを生成して返す"""
    os.makedirs(report_dir, exist_ok=True)

    lines = [
        '# エマグラム レポート',
        '',
        f'**地点**: {label}',
        f'**観測時刻**: {dt.strftime("%Y/%m/%d %HUTC")}',
        '',
        '---',
        '',
    ]

    for fig, fname in figs:
        fig.savefig(os.path.join(report_dir, fname), dpi=150, bbox_inches='tight')
        print(f'[保存] {report_dir}/{fname}')

        if '_pt_emagram' in fname:
            heading = '## 温位エマグラム（PT-Emagram）'
            alt    = f'温位エマグラム {label}'
            desc = 'θ（黒）・θe（緑）・θes（赤）・θw（紫）・等飽和混合比線'
        else:
            heading = '## エマグラム（Emagram）'
            alt    = f'エマグラム {label}'
            desc = '温度（赤）・露点（緑）・CAPE/CIN・ホドグラフ'

        lines += [
            heading,
            '',
            f'_{desc}_',
            '',
            f'![{alt}](./{fname})',
            '',
            '---',
            '',
        ]

    md_path = os.path.join(report_dir, 'emagram_report.md')
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f'[MD生成] {md_path}')
    return md_path


# ── GitHub push ────────────────────────────────────────────────────────────────
def push_report(proj_dir: str, report_rel: str, label: str, dt: datetime) -> None:
    """report_rel を git add → commit → push する"""
    rc = _run_git(f'add {report_rel}', proj_dir)
    if rc != 0:
        print('[エラー] git add 失敗', file=sys.stderr)
        return

    staged = subprocess.run(
        'git diff --staged --quiet', shell=True, cwd=proj_dir
    )
    if staged.returncode == 0:
        print('[情報] 変更なし: 既にコミット済み（push スキップ）')
        return

    dt_str = dt.strftime('%Y%m%d%H')
    commit_msg = f'report: エマグラム {label} ({dt_str})'
    rc = _run_git(f'commit -m "{commit_msg}"', proj_dir)
    if rc != 0:
        print('[エラー] git commit 失敗', file=sys.stderr)
        return

    _run_git('config http.postBuffer 524288000', proj_dir)
    rc = _run_git('push', proj_dir)
    if rc != 0:
        print('[エラー] git push 失敗（リトライ）', file=sys.stderr)
        _run_git('push', proj_dir)


# ── 引数解析 ───────────────────────────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    site_lines = '\n  '.join(
        f"{name}（{v['id']}）  {v['region']}"
        for name, v in STATIONS.items()
    )
    parser = argparse.ArgumentParser(
        description='エマグラム・温位エマグラム描画スクリプト',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
地点一覧:
  {site_lines}

使用例:
  python emagram.py
  python emagram.py --date 2024051200
  python emagram.py --site 南大東島
  python emagram.py --site 台北 --mode pt
  python emagram.py --date 2024051200 --site 名瀬 --mode emagram
  python emagram.py --id 47807 --show
  python emagram.py --site 石垣島 --report
  python emagram.py --site 石垣島 --report --push
""",
    )
    parser.add_argument(
        '--date', metavar='YYYYMMDDHH',
        help='観測日時（UTC）例: 2024051200。省略時は直近の00/12UTC',
    )
    parser.add_argument(
        '--site', metavar='地点名',
        default=DEFAULT_STATION,
        choices=list(STATIONS.keys()),
        help=f'地点名（デフォルト: {DEFAULT_STATION}）',
    )
    parser.add_argument(
        '--id', metavar='STATION_ID', dest='station_id',
        help='WMO地点番号（--site より優先）',
    )
    parser.add_argument(
        '--mode', choices=['both', 'emagram', 'pt'], default='both',
        help='表示モード（デフォルト: both）',
    )
    parser.add_argument(
        '--no-save', action='store_true',
        help='PNG保存をスキップする（--report 指定時は無効）',
    )
    parser.add_argument(
        '--show', action='store_true',
        help='完了後に画面表示する（GUIが必要）',
    )
    parser.add_argument(
        '--report', action='store_true',
        help='reports/{tag}/ にPNG+Markdownレポートを生成する',
    )
    parser.add_argument(
        '--push', action='store_true',
        help='--report と併用: 生成後に git add → commit → push する',
    )
    return parser.parse_args()


# ── メイン ─────────────────────────────────────────────────────────────────────
def main() -> None:
    args = parse_args()

    # 日時の解決
    if args.date:
        dt = datetime.strptime(args.date, '%Y%m%d%H')
    else:
        # 現在UTCから6時間前以前の最新00/12UTCを選ぶ
        threshold = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=6)
        hour = 0 if threshold.hour < 12 else 12
        dt = threshold.replace(hour=hour, minute=0, second=0, microsecond=0)
        print(f'[情報] 直近の観測時刻を使用: {dt.strftime("%Y-%m-%d %HUTC")}')

    # 地点の解決
    if args.station_id:
        station_id = args.station_id
        label = station_id
    else:
        name = args.site
        station_id = STATIONS[name]['id']
        label = f'{name}（{station_id}）'

    # データ取得
    try:
        d = fetch_data(dt, station_id)
    except Exception as e:
        print(f'[エラー] データ取得失敗: {e}', file=sys.stderr)
        print('  ヒント: 観測時刻・地点番号を確認してください。', file=sys.stderr)
        sys.exit(1)

    proj_dir = os.path.dirname(os.path.abspath(__file__))
    tag = f'{dt.strftime("%Y%m%d%H")}_{station_id}'

    # 描画
    figs: list[tuple[plt.Figure, str]] = []

    if args.mode in ('both', 'emagram'):
        fig_e = plt.figure(figsize=(8, 16))
        draw_emagram(fig_e, d, dt, label)
        figs.append((fig_e, f'{tag}_emagram.png'))

    if args.mode in ('both', 'pt'):
        fig_pt = plt.figure(figsize=(8, 16))
        draw_pt_emagram(fig_pt, d, dt, label)
        figs.append((fig_pt, f'{tag}_pt_emagram.png'))

    # ── report モード: reports/{tag}/ にPNG+Markdown を生成 ──
    if args.report:
        report_dir = os.path.join(proj_dir, 'reports', tag)
        make_report(report_dir, dt, label, figs)

        if args.push:
            report_rel = os.path.join('reports', tag)
            push_report(proj_dir, report_rel, label, dt)
        else:
            print('[情報] GitHub push はスキップ（--push を付けると実行）')

    # ── 通常モード: output/emagram/ に PNG を保存 ──
    else:
        out_dir = os.path.join(proj_dir, 'output', 'emagram')
        os.makedirs(out_dir, exist_ok=True)
        for fig, fname in figs:
            if not args.no_save:
                path = os.path.join(out_dir, fname)
                fig.savefig(path, dpi=150, bbox_inches='tight')
                print(f'[保存] {path}')

    if args.show:
        plt.show()
    else:
        plt.close('all')


if __name__ == '__main__':
    main()
