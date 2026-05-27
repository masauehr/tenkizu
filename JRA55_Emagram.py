#!/usr/bin/env python
# coding: utf-8
"""
JRA-55 isobaric data emagram plotter.

Data download and cache layout follow JRA55_SynopCharts.py.
"""

import argparse
import configparser
import datetime as dt
import os
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parent / ".matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(Path(__file__).resolve().parent / ".cache"))

if "--show" not in sys.argv:
    import matplotlib

    matplotlib.use("Agg")

import matplotlib.pyplot as plt
import metpy.calc as mpcalc
import numpy as np
import requests
import xarray as xr
from matplotlib.collections import LineCollection
from metpy.plots import Hodograph, SkewT
from metpy.units import units
from mpl_toolkits.axes_grid1.inset_locator import inset_axes

plt.rcParams["font.family"] = ["Hiragino Sans", "DejaVu Sans"]

BASE_URL = "https://database.rish.kyoto-u.ac.jp/arch/jra55/data/isobaric_1.25d"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; JRA55-Emagram/1.0)"}
REQUIRED_VARS = ("TMP", "RH", "UGRD", "VGRD", "HGT")


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


def parse_args():
    parser = argparse.ArgumentParser(
        description="JRA-55から任意地点のエマグラムを作図する",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""使用例:
  python JRA55_Emagram.py 1959091500 --ft 12 --lat 25 --lon 125
  python JRA55_Emagram.py 1959091500 --start-ft 0 --steps 5 --interval 6 --lat 25 --lon 125
  python JRA55_Emagram.py 1959091500 --start-ft 0 --steps 5 --interval 6 --lat 25 --lon 125 --push
  python JRA55_Emagram.py 1959091500 --ft 0100 --lat 25 --lon 125
  python JRA55_Emagram.py --valid-time 1959091512 --lat 25 --lon 125
""",
    )
    parser.add_argument("init_time", nargs="?", help="initial time in UTC: YYYYMMDDHH")
    parser.add_argument("--ft", default="0",
                        help="予想時刻。時間数(例: 12, 24) または DDHH形式(例: 0012, 0100)")
    parser.add_argument("--start-ft",
                        help="複数作図時の開始FT。時間数またはDDHH形式。省略時は--ftを使用")
    parser.add_argument("--steps", "--n-steps", dest="n_steps", type=int, default=1,
                        help="作図するFT数（デフォルト: 1）")
    parser.add_argument("--interval", type=int, default=6,
                        help="FT間隔の時間数（デフォルト: 6）")
    parser.add_argument("--valid-time",
                        help="有効時刻を直接指定する旧形式: YYYYMMDDHH。指定時はinit_time/--ftより優先")
    parser.add_argument("--lat", type=float, required=True, help="緯度（北緯を正）")
    parser.add_argument("--lon", type=float, required=True, help="経度（東経、0-360または-180-180）")
    parser.add_argument("--method", choices=("nearest", "exact"), default="nearest",
                        help="指定地点の扱い。nearestは最近傍格子、exactは格子完全一致のみ")
    parser.add_argument("--data-dir", default="./data/Jra55")
    parser.add_argument("--output-dir",
                        help="PNGとMarkdownの保存先。省略時はreports/{init}_JRA55_emagram_{FT範囲}_lat*_lon*")
    parser.add_argument("--config", default="./jra55_config.ini")
    parser.add_argument("--user", default=os.environ.get("JRA55_USER"))
    parser.add_argument("--password", default=os.environ.get("JRA55_PASSWORD"))
    parser.add_argument("--top", type=float, default=100.0, help="上端気圧 hPa")
    parser.add_argument("--bottom", type=float, default=1020.0, help="下端気圧 hPa")
    parser.add_argument("--figsize", nargs=2, type=float, default=(8.0, 16.0),
                        metavar=("WIDTH", "HEIGHT"))
    parser.add_argument("--push", action="store_true",
                        help="生成したPNG/Markdownをgit commitしてGitHubへpushする")
    parser.add_argument("--show", action="store_true", help="保存後に画面表示する")

    # ? / -? / --? でヘルプ表示
    if any(a in sys.argv[1:] for a in ('?', '-?', '--?')):
        parser.print_help()
        sys.exit(0)

    return parser.parse_args()


def parse_valid_time(value):
    parsed = parse_ymdh(value, "valid_time")
    if parsed.hour not in (0, 6, 12, 18):
        raise ValueError("JRA-55 data is available every 6 hours")
    return parsed


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


def resolve_runs(args):
    if args.valid_time:
        valid_time = parse_valid_time(args.valid_time)
        return valid_time, [(0, valid_time)]
    if not args.init_time:
        raise ValueError("init_time is required unless --valid-time is specified")
    init_time = parse_ymdh(args.init_time, "init_time")
    if args.n_steps < 1:
        raise ValueError("--steps must be 1 or greater")
    if args.interval < 1 or args.interval % 6 != 0:
        raise ValueError("--interval must be a positive multiple of 6 hours")

    start_ft = parse_ft_hours(args.start_ft if args.start_ft is not None else args.ft)
    runs = []
    for i in range(args.n_steps):
        ft_hours = start_ft + i * args.interval
        valid_time = init_time + dt.timedelta(hours=ft_hours)
        if valid_time.hour not in (0, 6, 12, 18):
            raise ValueError("valid time must be on a 6-hour boundary")
        runs.append((ft_hours, valid_time))
    return init_time, runs


def load_credentials(args):
    user, password = args.user, args.password
    config_path = Path(args.config)
    if config_path.exists():
        config = configparser.ConfigParser()
        config.read(config_path, encoding="utf-8")
        if config.has_section("jra55"):
            user = user or config.get("jra55", "user", fallback=None)
            password = password or config.get("jra55", "password", fallback=None)
    return user, password


def iso_path(data_dir, var_name, valid_time):
    return Path(data_dir) / var_name / valid_time.strftime("%Y") / f"{var_name}_{valid_time:%Y%m}.nc"


def download_file(url, path, user=None, password=None):
    if path.exists() and path.stat().st_size > 0:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".part")
    auth = (user, password) if user and password else None
    print(f"Downloading: {url}")
    try:
        with requests.get(url, headers=HEADERS, auth=auth, stream=True, timeout=120) as response:
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
    except requests.HTTPError as exc:
        if tmp_path.exists():
            tmp_path.unlink()
        if exc.response is not None and exc.response.status_code in (401, 403):
            raise RuntimeError("JRA-55 authentication failed. Check jra55_config.ini.") from exc
        raise
    except requests.RequestException:
        if tmp_path.exists():
            tmp_path.unlink()
        raise
    return path


def ensure_iso(data_dir, var_name, valid_time, user, password):
    path = iso_path(data_dir, var_name, valid_time)
    url = f"{BASE_URL}/{var_name}/{valid_time:%Y}/{var_name}_{valid_time:%Y%m}.nc"
    return download_file(url, path, user, password)


def time_index_month(valid_time):
    return (valid_time.day - 1) * 4 + valid_time.hour // 6


def normalize_lon(lon):
    return lon % 360.0


def nearest_index(values, target):
    return int(np.abs(values - target).argmin())


def grid_indices(sample, lat, lon, method):
    lats = np.asarray(sample["lat"].values, dtype=float)
    lons = np.asarray(sample["lon"].values, dtype=float)
    lon = normalize_lon(lon)
    i_lat = nearest_index(lats, lat)
    i_lon = nearest_index(lons, lon)
    grid_lat = float(lats[i_lat])
    grid_lon = float(lons[i_lon])
    if method == "exact" and (not np.isclose(grid_lat, lat) or not np.isclose(grid_lon, lon)):
        raise ValueError(
            f"requested point is not on a JRA-55 grid: requested lat={lat}, lon={lon}; "
            f"nearest lat={grid_lat}, lon={grid_lon}"
        )
    return i_lat, i_lon, grid_lat, grid_lon


def open_var(data_dir, var_name, valid_time, user, password):
    path = ensure_iso(data_dir, var_name, valid_time, user, password)
    data = xr.open_dataset(path).metpy.parse_cf(var_name).squeeze()
    if var_name == "HGT":
        data.attrs["units"] = "meter"
    elif var_name in ("UGRD", "VGRD"):
        data.attrs["units"] = "m/s"
    elif var_name == "TMP":
        data.attrs["units"] = "K"
    elif var_name == "RH":
        data.attrs["units"] = "%"
    return data


def read_profile(data_dir, valid_time, lat, lon, method, user, password, top):
    arrays = {name: open_var(data_dir, name, valid_time, user, password) for name in REQUIRED_VARS}
    i_lat, i_lon, grid_lat, grid_lon = grid_indices(arrays["TMP"], lat, lon, method)
    t_index = time_index_month(valid_time)

    selected = {}
    for name, data in arrays.items():
        prof = data.isel(time=t_index, lat=i_lat, lon=i_lon)
        prof = prof.sel(level=slice(top, None))
        selected[name] = prof

    p = units.Quantity(np.flip(np.asarray(selected["TMP"]["level"], dtype=float)), units.hPa)
    temp = units.Quantity(np.flip(np.asarray(selected["TMP"], dtype=float)), units.K)
    rh_values = np.flip(np.asarray(selected["RH"], dtype=float))
    rh_values = np.clip(rh_values, 0.0, 100.0)
    rh = units.Quantity(rh_values / 100.0, units.dimensionless)
    dewpoint = mpcalc.dewpoint_from_relative_humidity(temp, rh)
    u = units.Quantity(np.flip(np.asarray(selected["UGRD"], dtype=float)), units("m/s")).to("knots")
    v = units.Quantity(np.flip(np.asarray(selected["VGRD"], dtype=float)), units("m/s")).to("knots")
    h = units.Quantity(np.flip(np.asarray(selected["HGT"], dtype=float)), units.meter)

    finite = np.isfinite(temp.magnitude) & np.isfinite(dewpoint.magnitude)
    return {
        "p": p[finite],
        "T": temp[finite],
        "Td": dewpoint[finite],
        "u": u[finite],
        "v": v[finite],
        "h": h[finite],
        "grid_lat": grid_lat,
        "grid_lon": grid_lon,
    }


def parcel_diagnostics(profile):
    p, T, Td = profile["p"], profile["T"], profile["Td"]
    low = np.where(p.magnitude >= 850.0)[0]
    if low.size == 0:
        low = np.arange(min(3, len(p)))
    ept = mpcalc.equivalent_potential_temperature(p[low], T[low], Td[low])
    i_start = int(low[int(np.nanargmax(ept.magnitude))])
    prof = mpcalc.parcel_profile(p[i_start:], T[i_start], Td[i_start]).to("degC")
    lcl_p, lcl_t = mpcalc.lcl(p[i_start], T[i_start], Td[i_start])
    el_p, el_t = mpcalc.el(p[i_start:], T[i_start:], Td[i_start:], which="most_cape")
    cape, cin = mpcalc.cape_cin(
        p[i_start:], T[i_start:], Td[i_start:], prof, which_lfc="bottom", which_el="top"
    )
    return i_start, prof, lcl_p, lcl_t, el_p, el_t, cape, cin


def finite_quantity(value):
    try:
        return np.isfinite(value.magnitude)
    except Exception:
        return False


def output_path(output_dir, init_time, ft_hours, kind, req_lat, req_lon):
    return Path(output_dir) / (
        f"{init_time:%Y%m%d%H}_FT{ft_hours:03d}h_JRA55_{kind}_"
        f"lat{req_lat:.2f}_lon{normalize_lon(req_lon):.2f}.png"
    )


def default_output_directory(args, init_time, runs):
    if args.output_dir:
        return Path(args.output_dir)
    first_ft = runs[0][0]
    last_ft = runs[-1][0]
    if len(runs) == 1:
        ft_label = f"FT{first_ft:03d}h"
    else:
        ft_label = f"FT{first_ft:03d}-{last_ft:03d}h_{args.interval}h"
    return Path("reports") / (
        f"{init_time:%Y%m%d%H}_JRA55_emagram_{ft_label}_"
        f"lat{args.lat:.2f}_lon{normalize_lon(args.lon):.2f}"
    )


def make_report(report_dir, init_time, runs, req_lat, req_lon, records):
    report_dir.mkdir(parents=True, exist_ok=True)
    first_ft = runs[0][0]
    last_ft = runs[-1][0]
    ft_label = f"FT{first_ft:03d}h" if len(runs) == 1 else f"FT{first_ft:03d}-{last_ft:03d}h"
    md_name = f"jra55_emagram_report_{ft_label}.md"
    md_path = report_dir / md_name

    lines = [
        "# JRA-55 エマグラム",
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
        grid_lat = rec["grid_lat"]
        grid_lon = rec["grid_lon"]
        emagram = rec["emagram"].name
        pt_emagram = rec["pt_emagram"].name
        lines += [
            f"## FT={ft_h:03d}h",
            "",
            f"**有効時刻**: {valid_time:%Y/%m/%d %HUTC}  ",
            f"**格子点**: {grid_lat:.2f}N {grid_lon:.2f}E",
            "",
            "### エマグラム",
            "",
            f"![JRA-55 Emagram FT{ft_h:03d}h](./{emagram})",
            "",
            "### 温位エマグラム",
            "",
            f"![JRA-55 PT-Emagram FT{ft_h:03d}h](./{pt_emagram})",
            "",
            "---",
            "",
        ]

    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"MD: {md_path}")
    return md_path


def run_git(args, cwd):
    print(f"$ git {' '.join(str(arg) for arg in args)}")
    result = subprocess.run(
        ["git", *[str(arg) for arg in args]],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip())
    return result.returncode


def push_report(output_dir, init_time, runs):
    repo_dir = Path(__file__).resolve().parent
    out_path = Path(output_dir).resolve()
    try:
        rel_path = out_path.relative_to(repo_dir)
    except ValueError:
        raise ValueError(f"--push requires output_dir inside repository: {repo_dir}")

    rc = run_git(["add", rel_path], repo_dir)
    if rc != 0:
        raise RuntimeError("git add failed")

    staged = subprocess.run(["git", "diff", "--staged", "--quiet"], cwd=repo_dir)
    if staged.returncode == 0:
        print("No staged changes. Commit and push skipped.")
        return

    first_ft = runs[0][0]
    last_ft = runs[-1][0]
    ft_label = f"FT{first_ft:03d}h" if len(runs) == 1 else f"FT{first_ft:03d}-{last_ft:03d}h"
    commit_msg = f"report: JRA-55 emagram {ft_label} ({init_time:%Y%m%d%H})"
    rc = subprocess.run(["git", "commit", "-m", commit_msg], cwd=repo_dir).returncode
    if rc != 0:
        raise RuntimeError("git commit failed")

    rc = subprocess.run(["git", "push"], cwd=repo_dir).returncode
    if rc != 0:
        raise RuntimeError("git push failed")


def draw_emagram(profile, init_time, ft_hours, valid_time, req_lat, req_lon, output_dir, figsize, bottom, top):
    p, T, Td, u, v, h = profile["p"], profile["T"], profile["Td"], profile["u"], profile["v"], profile["h"]
    i_start, parcel_prof, lcl_p, lcl_t, el_p, el_t, cape, cin = parcel_diagnostics(profile)

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
    skew.shade_cin(p[i_start:], T[i_start:], parcel_prof)
    skew.shade_cape(p[i_start:], T[i_start:], parcel_prof)

    dry_tmp = np.arange(203, 533, 10) * units.K
    moist_tmp = np.arange(203, 400, 5) * units.K
    mix_p = np.arange(1000, 99, -20) * units.hPa
    skew.plot_dry_adiabats(t0=dry_tmp, alpha=0.25, color="orangered")
    skew.plot_moist_adiabats(t0=moist_tmp, alpha=0.25, color="tab:green")
    skew.plot_mixing_lines(pressure=mix_p, linestyle="dotted", color="tab:blue")

    title = f"JRA-55 Emagram FT{ft_hours:03d}h  Init {init_time:%Y-%m-%d %HUTC}"
    subtitle = (
        f"Valid {valid_time:%Y-%m-%d %HUTC}   "
        f"req {req_lat:.2f}N {normalize_lon(req_lon):.2f}E / grid {profile['grid_lat']:.2f}N {profile['grid_lon']:.2f}E"
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
    path = output_path(output_dir, init_time, ft_hours, "emagram", req_lat, req_lon)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    print(f"Output: {path}")
    print(f"Init: {init_time:%Y-%m-%d %HUTC}")
    print(f"FT: {ft_hours} h")
    print(f"Valid: {valid_time:%Y-%m-%d %HUTC}")
    print(f"Grid: lat={profile['grid_lat']:.2f}, lon={profile['grid_lon']:.2f}")
    print(f"Parcel start: {p[i_start].magnitude:.1f} hPa")
    print(f"LCL: {lcl_p.magnitude:.1f} hPa")
    if finite_quantity(el_p):
        print(f"EL: {el_p.magnitude:.1f} hPa")
    print(f"CAPE: {cape.magnitude:.1f} {cape.units}")
    print(f"CIN: {cin.magnitude:.1f} {cin.units}")
    return fig, path


def draw_pt_emagram(profile, init_time, ft_hours, valid_time, req_lat, req_lon, output_dir, figsize, bottom, top):
    p, T, Td, u, v = profile["p"], profile["T"], profile["Td"], profile["u"], profile["v"]

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

    mix_p = np.arange(1000, 99, -20) * units.hPa
    mr = np.array([0.0004, 0.001, 0.002, 0.004, 0.007, 0.01, 0.016, 0.024, 0.032]).reshape(-1, 1)
    _plot_mixing_lines_pt(skew, pressure=mix_p, mixing_ratio=mr)

    skew.plot(p, pt, "black", linewidth=1.6, label="温位 theta")
    skew.plot(p, ept, "g", linewidth=1.6, label="相当温位 theta-e")
    skew.plot(p, sept, "r", linewidth=1.6, label="飽和相当温位 theta-es")
    skew.plot(p, spt, "purple", linewidth=1.6, label="露点温度から求めた温位")
    skew.plot_barbs(p, u, v, y_clip_radius=0.03)

    title = f"JRA-55 PT-Emagram FT{ft_hours:03d}h  Init {init_time:%Y-%m-%d %HUTC}"
    subtitle = (
        f"Valid {valid_time:%Y-%m-%d %HUTC}   "
        f"req {req_lat:.2f}N {normalize_lon(req_lon):.2f}E / grid {profile['grid_lat']:.2f}N {profile['grid_lon']:.2f}E"
    )
    skew.ax.set_title(f"{title}\n{subtitle}", loc="center", pad=8, fontsize=11)
    skew.ax.legend(loc="upper left", bbox_to_anchor=(0.02, 0.98), fontsize=9)

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    path = output_path(output_dir, init_time, ft_hours, "pt_emagram", req_lat, req_lon)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    print(f"Output: {path}")
    return fig, path


def main():
    args = parse_args()
    try:
        init_time, runs = resolve_runs(args)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(2)

    user, password = load_credentials(args)
    output_dir = default_output_directory(args, init_time, runs)
    records = []
    open_figs = []

    print(f"Init: {init_time:%Y-%m-%d %HUTC}")
    print(f"FTs: {', '.join(f'{ft_h}h' for ft_h, _ in runs)}")
    print(f"Output dir: {output_dir}")

    for ft_hours, valid_time in runs:
        print(f"=== FT={ft_hours}h  Valid={valid_time:%Y-%m-%d %HUTC} ===")
        profile = read_profile(
            args.data_dir, valid_time, args.lat, args.lon, args.method, user, password, args.top
        )
        fig, emagram_path = draw_emagram(
            profile, init_time, ft_hours, valid_time, args.lat, args.lon, output_dir,
            tuple(args.figsize), args.bottom, args.top
        )
        fig_pt, pt_path = draw_pt_emagram(
            profile, init_time, ft_hours, valid_time, args.lat, args.lon, output_dir,
            tuple(args.figsize), args.bottom, args.top
        )
        records.append({
            "ft_hours": ft_hours,
            "valid_time": valid_time,
            "grid_lat": profile["grid_lat"],
            "grid_lon": profile["grid_lon"],
            "emagram": Path(emagram_path),
            "pt_emagram": Path(pt_path),
        })
        if args.show:
            open_figs.extend([fig, fig_pt])
        else:
            plt.close(fig)
            plt.close(fig_pt)

    make_report(output_dir, init_time, runs, args.lat, args.lon, records)

    if args.push:
        try:
            push_report(output_dir, init_time, runs)
        except (RuntimeError, ValueError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)

    if args.show:
        plt.show()
        for fig in open_figs:
            plt.close(fig)


if __name__ == "__main__":
    main()
