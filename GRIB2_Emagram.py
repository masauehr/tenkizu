#!/usr/bin/env python
# coding: utf-8
"""
GSM/ECMWF GRIB2 emagram plotter.

The GRIB2 download paths and filename rules follow the existing GSM_*.py and
ECM_*.py scripts in this repository. Plot layout follows JRA55_Emagram.py.
"""

import argparse
import datetime as dt
import os
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parent / ".matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(Path(__file__).resolve().parent / ".cache"))
os.environ.setdefault("PROJ_LIB", "/opt/anaconda3/envs/met_env_310/share/proj")

if "--show" not in sys.argv:
    import matplotlib

    matplotlib.use("Agg")

import matplotlib.pyplot as plt
import metpy.calc as mpcalc
import numpy as np
import pygrib
import requests
from matplotlib.collections import LineCollection
from metpy.plots import Hodograph, SkewT
from metpy.units import units
from mpl_toolkits.axes_grid1.inset_locator import inset_axes

try:
    from pyproj import datadir

    if Path(os.environ["PROJ_LIB"]).exists():
        datadir.set_data_dir(os.environ["PROJ_LIB"])
except Exception:
    pass

plt.rcParams["font.family"] = ["Hiragino Sans", "DejaVu Sans"]

GSM_BASE_URL = "http://database.rish.kyoto-u.ac.jp/arch/jmadata/data/gpv/original"
ECM_BASE_URL = "https://data.ecmwf.int/forecasts"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; GRIB2-Emagram/1.0)"}


def parse_args():
    parser = argparse.ArgumentParser(
        description="GSM/ECMWF GRIB2から任意地点のエマグラム・温位エマグラムを作図する",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""使用例:
  python GRIB2_Emagram.py gsm 2026041200 --ft 12 --lat 25 --lon 125
  python GRIB2_Emagram.py gsm 2026041200 --start-ft 0 --steps 5 --interval 6 --lat 25 --lon 125
  python GRIB2_Emagram.py ecm 2026041200 --ft 24 --lat 25 --lon 125
  python GRIB2_Emagram.py ecm 2026041200 --start-ft 0 --steps 3 --lat 25 --lon 125 --push

実行環境（conda の場合）:
  conda activate met_env_310
  python GRIB2_Emagram.py [引数]

  ※ 環境名（met_env_310）は利用者の構築状況により異なります。
     pygrib / metpy / cartopy 等が入った Python 3.10 環境であれば動作します。
""",
    )
    parser.add_argument("model", choices=("gsm", "ecm"), help="入力モデル")
    parser.add_argument("init_time", help="初期時刻 YYYYMMDDHH（UTC）")
    parser.add_argument("--ft", default="0",
                        help="予想時刻。時間数(例: 12, 24) または DDHH形式(例: 0012, 0100)")
    parser.add_argument("--start-ft",
                        help="複数作図時の開始FT。時間数またはDDHH形式。省略時は--ftを使用")
    parser.add_argument("--steps", "--n-steps", dest="n_steps", type=int, default=1,
                        help="作図するFT数（デフォルト: 1）")
    parser.add_argument("--interval", type=int, default=6,
                        help="FT間隔の時間数（デフォルト: 6）")
    parser.add_argument("--lat", type=float, required=True, help="緯度（北緯を正）")
    parser.add_argument("--lon", type=float, required=True, help="経度（東経、0-360または-180-180）")
    parser.add_argument("--method", choices=("nearest", "exact"), default="nearest",
                        help="地点の扱い。nearestは最近傍格子、exactは格子完全一致のみ")
    parser.add_argument("--top", type=float, default=100.0, help="上端気圧 hPa")
    parser.add_argument("--bottom", type=float, default=1020.0, help="下端気圧 hPa")
    parser.add_argument("--figsize", nargs=2, type=float, default=(8.0, 16.0),
                        metavar=("WIDTH", "HEIGHT"))
    parser.add_argument("--gsm-data-dir", default="./data_gsm")
    parser.add_argument("--ecm-data-dir", default="./data/ecm")
    parser.add_argument("--output-dir",
                        help="PNGとMarkdownの保存先。省略時はreports/{init}_{MODEL}_emagram_{FT範囲}_lat*_lon*")
    parser.add_argument("--push", action="store_true",
                        help="生成したPNG/Markdownをgit commitしてGitHubへpushする")
    parser.add_argument("--show", action="store_true", help="保存後に画面表示する")

    # ? / -? / --? でヘルプ表示
    if any(a in sys.argv[1:] for a in ('?', '-?', '--?')):
        parser.print_help()
        sys.exit(0)

    return parser.parse_args()


def parse_ymdh(value, label):
    if len(value) != 10 or not value.isdigit():
        raise ValueError(f"{label} must be YYYYMMDDHH")
    parsed = dt.datetime.strptime(value, "%Y%m%d%H").replace(tzinfo=dt.timezone.utc)
    if parsed.hour not in (0, 6, 12, 18):
        raise ValueError(f"{label} hour must be one of 00, 06, 12, 18")
    return parsed


def parse_ft_hours(value):
    text = str(value).strip().lower()
    if text.startswith("ft"):
        text = text[2:]
    if text.endswith("h"):
        text = text[:-1]
    if not text.isdigit():
        raise ValueError("ft must be hours or DDHH, for example 12, 24, 0012, 0100")
    if len(text) == 4:
        days = int(text[:2])
        hours = int(text[2:])
        if hours >= 24:
            raise ValueError("DDHH ft must have HH < 24")
        total = days * 24 + hours
    else:
        total = int(text)
    if total < 0 or total % 6 != 0:
        raise ValueError("ft must be a non-negative multiple of 6 hours")
    return total


def hours_to_ddhh(hours):
    return (hours // 24) * 100 + (hours % 24)


def resolve_runs(args):
    init_time = parse_ymdh(args.init_time, "init_time")
    if args.n_steps < 1:
        raise ValueError("--steps must be 1 or greater")
    if args.interval < 1 or args.interval % 6 != 0:
        raise ValueError("--interval must be a positive multiple of 6 hours")
    start_ft = parse_ft_hours(args.start_ft if args.start_ft is not None else args.ft)
    return init_time, [(start_ft + i * args.interval, init_time + dt.timedelta(hours=start_ft + i * args.interval))
                       for i in range(args.n_steps)]


def normalize_lon(lon):
    return lon % 360.0


def default_output_directory(args, init_time, runs):
    if args.output_dir:
        return Path(args.output_dir)
    first_ft = runs[0][0]
    last_ft = runs[-1][0]
    ft_label = f"FT{first_ft:03d}h" if len(runs) == 1 else f"FT{first_ft:03d}-{last_ft:03d}h_{args.interval}h"
    return Path("reports") / (
        f"{init_time:%Y%m%d%H}_{args.model.upper()}_emagram_{ft_label}_"
        f"lat{args.lat:.2f}_lon{normalize_lon(args.lon):.2f}"
    )


def gsm_filename(init_time, ft_hours):
    ft_ddhh = hours_to_ddhh(ft_hours)
    return f"Z__C_RJTD_{init_time:%Y%m%d%H}0000_GSM_GPV_Rgl_FD{ft_ddhh:04d}_grib2.bin"


def ecm_filename(init_time, ft_hours):
    stream = "oper" if init_time.hour in (0, 12) else "scda"
    return f"{init_time:%Y%m%d%H}0000-{ft_hours:d}h-{stream}-fc.grib2"


def download_file(url, path):
    if path.exists() and path.stat().st_size > 0:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".part")
    print(f"Downloading: {url}")
    try:
        with requests.get(url, headers=HEADERS, stream=True, timeout=120) as response:
            response.raise_for_status()
            total = int(response.headers.get("content-length", 0))
            done = 0
            with tmp_path.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    handle.write(chunk)
                    done += len(chunk)
                    if total:
                        print(f"\r  {done / total * 100:5.1f}%", end="", flush=True)
            if total:
                print()
        tmp_path.replace(path)
    except requests.RequestException:
        if tmp_path.exists():
            tmp_path.unlink()
        raise
    return path


def ensure_grib(args, init_time, ft_hours):
    if args.model == "gsm":
        filename = gsm_filename(init_time, ft_hours)
        path = Path(args.gsm_data_dir) / filename
        url = f"{GSM_BASE_URL}/{init_time:%Y}/{init_time:%m}/{init_time:%d}/{filename}"
    else:
        filename = ecm_filename(init_time, ft_hours)
        path = Path(args.ecm_data_dir) / filename
        stream = "oper" if init_time.hour in (0, 12) else "scda"
        url = f"{ECM_BASE_URL}/{init_time:%Y%m%d}/{init_time:%H}z/ifs/0p25/{stream}/{filename}"
    return download_file(url, path)


def nearest_grid_index(lats, lons, lat, lon, method):
    target_lon = normalize_lon(lon)
    lons_norm = np.mod(lons, 360.0)
    dist2 = (lats - lat) ** 2 + (lons_norm - target_lon) ** 2
    iy, ix = np.unravel_index(int(np.nanargmin(dist2)), dist2.shape)
    grid_lat = float(lats[iy, ix])
    grid_lon = float(lons_norm[iy, ix])
    if method == "exact" and (not np.isclose(grid_lat, lat) or not np.isclose(grid_lon, target_lon)):
        raise ValueError(
            f"requested point is not on the {method} grid: requested lat={lat}, lon={target_lon}; "
            f"nearest lat={grid_lat}, lon={grid_lon}"
        )
    return iy, ix, grid_lat, grid_lon


def grib_levels(grbs, short_name, top):
    msgs = grbs(shortName=short_name, typeOfLevel="isobaricInhPa", level=lambda lev: lev >= top)
    by_level = {int(msg["level"]): msg for msg in msgs}
    return by_level


def read_profile(args, init_time, ft_hours):
    path = ensure_grib(args, init_time, ft_hours)
    print(f"Read: {path}")
    grbs = pygrib.open(str(path))
    try:
        fields = {
            "T": grib_levels(grbs, "t", args.top),
            "RH": grib_levels(grbs, "r", args.top),
            "u": grib_levels(grbs, "u", args.top),
            "v": grib_levels(grbs, "v", args.top),
            "h": grib_levels(grbs, "gh", args.top),
        }
        levels = sorted(
            set.intersection(set(fields["T"].keys()), set(fields["u"].keys()), set(fields["v"].keys()), set(fields["h"].keys())),
            reverse=True,
        )
        if not levels:
            raise RuntimeError("no common isobaric levels found for t/u/v/gh")

        sample = fields["T"][levels[0]]
        lats, lons = sample.latlons()
        iy, ix, grid_lat, grid_lon = nearest_grid_index(lats, lons, args.lat, args.lon, args.method)
        anal_time = sample.analDate.replace(tzinfo=dt.timezone.utc)
        valid_time = sample.validDate.replace(tzinfo=dt.timezone.utc)

        t_vals, rh_vals, u_vals, v_vals, h_vals = [], [], [], [], []
        for lev in levels:
            t_vals.append(float(fields["T"][lev].values[iy, ix]))
            if lev in fields["RH"]:
                rh_vals.append(float(fields["RH"][lev].values[iy, ix]))
            else:
                rh_vals.append(np.nan)
            u_vals.append(float(fields["u"][lev].values[iy, ix]))
            v_vals.append(float(fields["v"][lev].values[iy, ix]))
            h_vals.append(float(fields["h"][lev].values[iy, ix]))
    finally:
        grbs.close()

    p = units.Quantity(np.asarray(levels, dtype=float), units.hPa)
    temp = units.Quantity(np.asarray(t_vals, dtype=float), units.K)
    rh = units.Quantity(np.clip(np.asarray(rh_vals, dtype=float), 0.0, 100.0) / 100.0, units.dimensionless)
    dewpoint = mpcalc.dewpoint_from_relative_humidity(temp, rh)
    u = units.Quantity(np.asarray(u_vals, dtype=float), units("m/s")).to("knots")
    v = units.Quantity(np.asarray(v_vals, dtype=float), units("m/s")).to("knots")
    h = units.Quantity(np.asarray(h_vals, dtype=float), units.meter)

    return {
        "p": p,
        "T": temp,
        "Td": dewpoint,
        "u": u,
        "v": v,
        "h": h,
        "grid_lat": grid_lat,
        "grid_lon": grid_lon,
        "anal_time": anal_time,
        "valid_time": valid_time,
        "path": path,
        "humidity_top": min(fields["RH"].keys()) if fields["RH"] else None,
    }


def _plot_mixing_lines_pt(skew, mixing_ratio=None, pressure=None, **kwargs):
    if mixing_ratio is None:
        mixing_ratio = np.array(
            [0.0004, 0.001, 0.002, 0.004, 0.007, 0.01, 0.016, 0.024, 0.032]
        ).reshape(-1, 1)
    if pressure is None:
        pressure = units.Quantity(np.linspace(600, max(skew.ax.get_ylim())), "mbar")
    td = mpcalc.dewpoint(mpcalc.vapor_pressure(pressure, mixing_ratio))
    pt = mpcalc.potential_temperature(pressure, td).to(units.degree_Celsius)
    linedata = [np.vstack((t.m, pressure.m)).T for t in pt]
    kwargs.setdefault("colors", "tab:blue")
    kwargs.setdefault("linestyles", "dotted")
    kwargs.setdefault("alpha", 0.8)
    return skew.ax.add_collection(LineCollection(linedata, **kwargs))


def parcel_diagnostics(profile):
    p, T, Td = profile["p"], profile["T"], profile["Td"]
    finite = np.isfinite(p.magnitude) & np.isfinite(T.magnitude) & np.isfinite(Td.magnitude)
    low = np.where(finite & (p.magnitude >= 850.0))[0]
    if low.size == 0:
        raise RuntimeError("no finite low-level temperature/dewpoint data for parcel diagnostics")
    ept = mpcalc.equivalent_potential_temperature(p[low], T[low], Td[low])
    i_start = int(low[int(np.nanargmax(ept.magnitude))])
    prof = mpcalc.parcel_profile(p[i_start:], T[i_start], Td[i_start]).to("degC")
    lcl_p, lcl_t = mpcalc.lcl(p[i_start], T[i_start], Td[i_start])
    env = finite & (np.arange(len(p)) >= i_start)
    p_env = p[env]
    t_env = T[env]
    td_env = Td[env]
    prof_env = mpcalc.parcel_profile(p_env, T[i_start], Td[i_start]).to("degC")
    el_p, el_t = mpcalc.el(p_env, t_env, td_env, which="most_cape")
    cape, cin = mpcalc.cape_cin(
        p_env, t_env, td_env, prof_env, which_lfc="bottom", which_el="top"
    )
    return i_start, prof, p_env, t_env, prof_env, lcl_p, lcl_t, el_p, el_t, cape, cin


def finite_quantity(value):
    try:
        return np.isfinite(value.magnitude)
    except Exception:
        return False


def output_path(output_dir, model, init_time, ft_hours, kind, req_lat, req_lon):
    return Path(output_dir) / (
        f"{init_time:%Y%m%d%H}_FT{ft_hours:03d}h_{model.upper()}_{kind}_"
        f"lat{req_lat:.2f}_lon{normalize_lon(req_lon):.2f}.png"
    )


def draw_emagram(model, profile, init_time, ft_hours, req_lat, req_lon, output_dir, figsize, bottom, top):
    p, T, Td, u, v, h = profile["p"], profile["T"], profile["Td"], profile["u"], profile["v"], profile["h"]
    valid_time = profile["valid_time"]
    i_start, parcel_prof, p_env, t_env, parcel_prof_env, lcl_p, lcl_t, el_p, el_t, cape, cin = parcel_diagnostics(profile)

    fig = plt.figure(figsize=figsize)
    fig.subplots_adjust(top=0.92, right=0.95)
    skew = SkewT(fig, rotation=0, aspect=120)
    skew.ax.set_xlim(-70, 40)
    skew.ax.set_ylim(bottom, top)
    skew.ax.set_xlabel("Temperature (degC)")
    skew.ax.set_ylabel("Pressure (hPa)")

    skew.plot(p, T, "r", linewidth=1.8, label="気温")
    skew.plot(p, Td, "g", linewidth=1.8, label="露点温度")
    skew.plot_barbs(p, u, v, y_clip_radius=0.03)
    skew.plot(p[i_start:], parcel_prof, "k", linewidth=2, alpha=0.55, label="持ち上げ気塊")
    skew.plot(p[i_start], T[i_start], "ko", markerfacecolor="black")
    skew.plot(lcl_p, lcl_t, "ko", markerfacecolor="blue")
    if finite_quantity(el_p):
        skew.plot(el_p, el_t, "ko", markerfacecolor="red")
    skew.shade_cin(p_env, t_env, parcel_prof_env)
    skew.shade_cape(p_env, t_env, parcel_prof_env)

    skew.plot_dry_adiabats(t0=np.arange(203, 533, 10) * units.K, alpha=0.25, color="orangered")
    skew.plot_moist_adiabats(t0=np.arange(203, 400, 5) * units.K, alpha=0.25, color="tab:green")
    skew.plot_mixing_lines(pressure=np.arange(1000, 99, -20) * units.hPa, linestyle="dotted", color="tab:blue")

    title = f"{model.upper()} Emagram FT{ft_hours:03d}h  Init {init_time:%Y-%m-%d %HUTC}"
    subtitle = (
        f"Valid {valid_time:%Y-%m-%d %HUTC}   "
        f"req {req_lat:.2f}N {normalize_lon(req_lon):.2f}E / "
        f"grid {profile['grid_lat']:.2f}N {profile['grid_lon']:.2f}E"
    )
    skew.ax.set_title(f"{title}\n{subtitle}", loc="center", pad=8, fontsize=11)
    skew.ax.legend(
        loc="center left",
        bbox_to_anchor=(-69, 700),
        bbox_transform=skew.ax.transData,
        fontsize=9,
        framealpha=0.82,
    )

    ax_hod = inset_axes(skew.ax, "40%", "40%", loc=1)
    hod = Hodograph(ax_hod, component_range=80.0)
    hod.add_grid(increment=20)
    hod.plot_colormapped(u, v, h)

    stats = (
        f"Parcel start: {p[i_start].magnitude:.0f} hPa\n"
        f"LCL: {lcl_p.magnitude:.0f} hPa\n"
        f"CAPE: {cape.magnitude:.0f} J/kg\n"
        f"CIN: {cin.magnitude:.0f} J/kg"
    )
    skew.ax.text(
        0.02, 0.02, stats, transform=skew.ax.transAxes, fontsize=9,
        va="bottom", ha="left", bbox={"boxstyle": "round,pad=0.3", "fc": "white", "alpha": 0.75}
    )

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    path = output_path(output_dir, model, init_time, ft_hours, "emagram", req_lat, req_lon)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    print(f"Output: {path}")
    print(f"Grid: lat={profile['grid_lat']:.2f}, lon={profile['grid_lon']:.2f}")
    print(f"CAPE: {cape.magnitude:.1f} {cape.units}")
    print(f"CIN: {cin.magnitude:.1f} {cin.units}")
    return fig, path


def draw_pt_emagram(model, profile, init_time, ft_hours, req_lat, req_lon, output_dir, figsize, bottom, top):
    p, T, Td, u, v = profile["p"], profile["T"], profile["Td"], profile["u"], profile["v"]
    valid_time = profile["valid_time"]
    pt = mpcalc.potential_temperature(p, T)
    spt = mpcalc.potential_temperature(p, Td)
    ept = mpcalc.equivalent_potential_temperature(p, T, Td)
    sept = mpcalc.saturation_equivalent_potential_temperature(p, T)

    all_values = np.concatenate([pt.magnitude, spt.magnitude, ept.magnitude, sept.magnitude])
    valid = all_values[np.isfinite(all_values)]
    x_min = int(np.floor((valid.min() - 5.0) / 10.0) * 10.0)
    x_max = int(np.ceil((valid.max() + 5.0) / 10.0) * 10.0)
    x_ticks = np.arange(x_min, x_max + 1, 10) * units.K

    fig = plt.figure(figsize=figsize)
    fig.subplots_adjust(top=0.92)
    skew = SkewT(fig, rotation=0, aspect=120)
    skew.ax.set_xlim(x_min * units.K, x_max * units.K)
    skew.ax.set_ylim(bottom, top)
    skew.ax.set_xticks(x_ticks)
    skew.ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{273.15 + x:.0f}"))
    skew.ax.set_xlabel("Potential temperature (K)")
    skew.ax.set_ylabel("Pressure (hPa)")

    _plot_mixing_lines_pt(
        skew,
        pressure=np.arange(1000, 99, -20) * units.hPa,
        mixing_ratio=np.array([0.0004, 0.001, 0.002, 0.004, 0.007, 0.01, 0.016, 0.024, 0.032]).reshape(-1, 1),
    )
    skew.plot(p, pt, "black", linewidth=1.6, label="温位 theta")
    skew.plot(p, ept, "g", linewidth=1.6, label="相当温位 theta-e")
    skew.plot(p, sept, "r", linewidth=1.6, label="飽和相当温位 theta-es")
    skew.plot(p, spt, "purple", linewidth=1.6, label="露点温度から求めた温位")
    skew.plot_barbs(p, u, v, y_clip_radius=0.03)

    title = f"{model.upper()} PT-Emagram FT{ft_hours:03d}h  Init {init_time:%Y-%m-%d %HUTC}"
    subtitle = (
        f"Valid {valid_time:%Y-%m-%d %HUTC}   "
        f"req {req_lat:.2f}N {normalize_lon(req_lon):.2f}E / "
        f"grid {profile['grid_lat']:.2f}N {profile['grid_lon']:.2f}E"
    )
    skew.ax.set_title(f"{title}\n{subtitle}", loc="center", pad=8, fontsize=11)
    skew.ax.legend(loc="upper left", bbox_to_anchor=(0.02, 0.98), fontsize=9)

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    path = output_path(output_dir, model, init_time, ft_hours, "pt_emagram", req_lat, req_lon)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    print(f"Output: {path}")
    return fig, path


def make_report(output_dir, model, init_time, runs, req_lat, req_lon, records):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    first_ft = runs[0][0]
    last_ft = runs[-1][0]
    ft_label = f"FT{first_ft:03d}h" if len(runs) == 1 else f"FT{first_ft:03d}-{last_ft:03d}h"
    md_path = output_dir / f"{model.lower()}_emagram_report_{ft_label}.md"
    lines = [
        f"# {model.upper()} エマグラム",
        "",
        f"**初期時刻**: {init_time:%Y/%m/%d %HUTC}",
        f"**地点**: req {req_lat:.2f}N {normalize_lon(req_lon):.2f}E",
        f"**FT**: {ft_label}",
        "",
        "---",
        "",
    ]
    for rec in records:
        ft_h = rec["ft_hours"]
        valid_time = rec["valid_time"]
        lines += [
            f"## FT={ft_h:03d}h",
            "",
            f"**有効時刻**: {valid_time:%Y/%m/%d %HUTC}  ",
            f"**格子点**: {rec['grid_lat']:.2f}N {rec['grid_lon']:.2f}E  ",
            f"**入力ファイル**: `{rec['input_file'].name}`",
            "",
            "### エマグラム",
            "",
            f"![{model.upper()} Emagram FT{ft_h:03d}h](./{rec['emagram'].name})",
            "",
            "### 温位エマグラム",
            "",
            f"![{model.upper()} PT-Emagram FT{ft_h:03d}h](./{rec['pt_emagram'].name})",
            "",
            "---",
            "",
        ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"MD: {md_path}")
    return md_path


def run_git(args, cwd):
    print(f"$ git {' '.join(str(arg) for arg in args)}")
    result = subprocess.run(["git", *[str(arg) for arg in args]], cwd=cwd, capture_output=True, text=True)
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip())
    return result.returncode


def push_report(output_dir, model, init_time, runs):
    repo_dir = Path(__file__).resolve().parent
    out_path = Path(output_dir).resolve()
    try:
        rel_path = out_path.relative_to(repo_dir)
    except ValueError:
        raise ValueError(f"--push requires output_dir inside repository: {repo_dir}")
    if run_git(["add", rel_path], repo_dir) != 0:
        raise RuntimeError("git add failed")
    staged = subprocess.run(
        ["git", "diff", "--staged", "--name-only", "--", str(rel_path)],
        cwd=repo_dir, capture_output=True, text=True,
    )
    if not staged.stdout.strip():
        print("No staged changes in output dir. Commit and push skipped.")
        return
    print(f"Staged:\n{staged.stdout.strip()}")
    first_ft = runs[0][0]
    last_ft = runs[-1][0]
    ft_label = f"FT{first_ft:03d}h" if len(runs) == 1 else f"FT{first_ft:03d}-{last_ft:03d}h"
    commit_msg = f"report: {model.upper()} emagram {ft_label} ({init_time:%Y%m%d%H})"
    if subprocess.run(["git", "commit", "-m", commit_msg], cwd=repo_dir).returncode != 0:
        raise RuntimeError("git commit failed")
    if subprocess.run(["git", "push"], cwd=repo_dir).returncode != 0:
        raise RuntimeError("git push failed")


def main():
    args = parse_args()
    try:
        init_time, runs = resolve_runs(args)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(2)

    output_dir = default_output_directory(args, init_time, runs)
    records = []
    open_figs = []
    print(f"Model: {args.model.upper()}")
    print(f"Init: {init_time:%Y-%m-%d %HUTC}")
    print(f"FTs: {', '.join(f'{ft_h}h' for ft_h, _ in runs)}")
    print(f"Output dir: {output_dir}")

    for ft_hours, expected_valid in runs:
        print(f"=== {args.model.upper()} FT={ft_hours}h  Expected valid={expected_valid:%Y-%m-%d %HUTC} ===")
        profile = read_profile(args, init_time, ft_hours)
        fig, emagram_path = draw_emagram(
            args.model, profile, init_time, ft_hours, args.lat, args.lon, output_dir,
            tuple(args.figsize), args.bottom, args.top
        )
        fig_pt, pt_path = draw_pt_emagram(
            args.model, profile, init_time, ft_hours, args.lat, args.lon, output_dir,
            tuple(args.figsize), args.bottom, args.top
        )
        records.append({
            "ft_hours": ft_hours,
            "valid_time": profile["valid_time"],
            "grid_lat": profile["grid_lat"],
            "grid_lon": profile["grid_lon"],
            "input_file": Path(profile["path"]),
            "emagram": Path(emagram_path),
            "pt_emagram": Path(pt_path),
        })
        if args.show:
            open_figs.extend([fig, fig_pt])
        else:
            plt.close(fig)
            plt.close(fig_pt)

    make_report(output_dir, args.model, init_time, runs, args.lat, args.lon, records)
    if args.push:
        try:
            push_report(output_dir, args.model, init_time, runs)
        except (RuntimeError, ValueError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)
    if args.show:
        plt.show()
        for fig in open_figs:
            plt.close(fig)


if __name__ == "__main__":
    main()
