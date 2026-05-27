#!/usr/bin/env python
# coding: utf-8

import argparse
import configparser
import datetime as dt
import os
import sys
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parent / ".matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(Path(__file__).resolve().parent / ".cache"))
os.environ.setdefault("PROJ_LIB", "/opt/anaconda3/envs/met_env/share/proj")

import cartopy.crs as ccrs
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import metpy.calc as mpcalc
import numpy as np
import requests
import xarray as xr
from metpy.units import units

try:
    from pyproj import datadir

    if Path(os.environ["PROJ_LIB"]).exists():
        datadir.set_data_dir(os.environ["PROJ_LIB"])
except Exception:
    pass


BASE_URL = "https://database.rish.kyoto-u.ac.jp/arch/jra55/data/isobaric_1.25d"
ALL_CHARTS = ["jet", "fax57", "fax78", "ept", "srf"]
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; JRA55-SynopCharts/1.0)"}


def parse_args():
    parser = argparse.ArgumentParser(
        description="JRA-55から総観天気図セットを作成する",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("valid_time", help="valid time in UTC: YYYYMMDDHH")
    parser.add_argument("--charts", nargs="+", choices=ALL_CHARTS, default=ALL_CHARTS)
    parser.add_argument("--data-dir", default="./data/Jra55")
    parser.add_argument("--output-dir", default="./output")
    parser.add_argument("--config", default="./jra55_config.ini")
    parser.add_argument("--user", default=os.environ.get("JRA55_USER"))
    parser.add_argument("--password", default=os.environ.get("JRA55_PASSWORD"))

    # ? / -? / --? でヘルプ表示
    if any(a in sys.argv[1:] for a in ('?', '-?', '--?')):
        parser.print_help()
        sys.exit(0)

    return parser.parse_args()


def parse_valid_time(value):
    if len(value) != 10 or not value.isdigit():
        raise ValueError("valid_time must be YYYYMMDDHH")
    valid = dt.datetime.strptime(value, "%Y%m%d%H").replace(tzinfo=dt.timezone.utc)
    if valid.hour not in (0, 6, 12, 18):
        raise ValueError("JRA-55 data is available every 6 hours")
    return valid


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
            downloaded = 0
            with tmp_path.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    handle.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        print(
                            f"\r  {downloaded/total*100:5.1f}% ({downloaded/1048576:.1f}/{total/1048576:.1f} MB)",
                            end="",
                            flush=True,
                        )
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


def iso_path(data_dir, var_name, valid_time):
    yyyymm = valid_time.strftime("%Y%m")
    return Path(data_dir) / var_name / valid_time.strftime("%Y") / f"{var_name}_{yyyymm}.nc"


def surf_path(data_dir, var_name, suffix, valid_time):
    year = valid_time.strftime("%Y")
    return Path(data_dir) / "surf" / var_name / f"{var_name}_{suffix}_{year}.nc"


def ensure_iso(data_dir, var_name, valid_time, user, password):
    path = iso_path(data_dir, var_name, valid_time)
    url = f"{BASE_URL}/{var_name}/{valid_time:%Y}/{var_name}_{valid_time:%Y%m}.nc"
    return download_file(url, path, user, password)


def ensure_surf(data_dir, var_name, suffix, valid_time, user, password):
    path = surf_path(data_dir, var_name, suffix, valid_time)
    url = f"{BASE_URL}/surf/{var_name}/{var_name}_{suffix}_{valid_time:%Y}.nc"
    return download_file(url, path, user, password)


def time_index_month(valid_time):
    return (valid_time.day - 1) * 4 + valid_time.hour // 6


def time_index_year(valid_time):
    return (valid_time.timetuple().tm_yday - 1) * 4 + valid_time.hour // 6


def read_iso(data_dir, var_name, valid_time, level, lat_slice, lon_slice, user, password):
    path = ensure_iso(data_dir, var_name, valid_time, user, password)
    data = xr.open_dataset(path).metpy.parse_cf(var_name).squeeze()
    if var_name == "HGT":
        data.attrs["units"] = "meter"
    elif var_name in ("UGRD", "VGRD"):
        data.attrs["units"] = "m/s"
    elif var_name in ("RELD",):
        data.attrs["units"] = "1 / second"
    elif var_name == "TMP":
        data.attrs["units"] = "K"
    elif var_name == "RH":
        data.attrs["units"] = "%"
    return data.isel(time=time_index_month(valid_time)).sel(level=level, lat=lat_slice, lon=lon_slice)


def read_surf(data_dir, var_name, suffix, valid_time, user, password):
    path = ensure_surf(data_dir, var_name, suffix, valid_time, user, password)
    ds = xr.open_dataset(path)
    actual_name = f"{var_name}_{suffix}"
    parse_name = actual_name if actual_name in ds.data_vars else var_name
    data = ds.metpy.parse_cf(parse_name).squeeze()
    if var_name in ("UGRD", "VGRD"):
        data.attrs["units"] = "m/s"
    elif var_name == "TMP":
        data.attrs["units"] = "K"
    elif var_name == "PRMSL":
        data.attrs["units"] = "Pa"
    return data.isel(time=time_index_year(valid_time))


def setup_map(area):
    proj = ccrs.Stereographic(central_latitude=60, central_longitude=140)
    latlon = ccrs.PlateCarree()
    fig = plt.figure(figsize=(10, 8))
    plt.subplots_adjust(left=0, right=1, bottom=0.06, top=0.98)
    ax = fig.add_subplot(1, 1, 1, projection=proj)
    ax.set_extent(area, latlon)
    ax.coastlines(resolution="50m", linewidth=1.4)
    gl = ax.gridlines(crs=latlon, draw_labels=False, linewidth=1, alpha=0.8)
    gl.xlocator = mticker.FixedLocator(np.arange(0, 360.1, 10))
    gl.ylocator = mticker.FixedLocator(np.arange(-90, 90.1, 10))
    return fig, ax, latlon


def celsius(data):
    return data.metpy.convert_units(units.degC)


def rh_fraction(rh):
    values = rh / 100.0 if float(rh.max()) > 1.5 else rh
    values.attrs["units"] = ""
    return values


def save(fig, output_dir, valid_time, name):
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    path = Path(output_dir) / f"{valid_time:%Y%m%d%H}_JRA55_{name}.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Output: {path}")
    return path


def plot_jet(ctx):
    hgt = ctx["iso"]("HGT", 300)
    u = ctx["iso"]("UGRD", 300)
    v = ctx["iso"]("VGRD", 300)
    div = ctx["iso"]("RELD", 300)
    uag, vag = mpcalc.ageostrophic_wind(hgt, u, v)
    ws = mpcalc.wind_speed(u, v).metpy.convert_units("knots")
    uag = uag.metpy.convert_units("knots")
    vag = vag.metpy.convert_units("knots")
    fig, ax, latlon = setup_map([115, 151, 20, 50])
    cn = ax.contourf(div.lon, div.lat, div.values * 1e5, [-10, -5, -2, -1, 1, 2, 5, 10],
                     cmap="coolwarm", extend="both", transform=latlon)
    fig.colorbar(cn, orientation="horizontal", cax=fig.add_axes([0.1, 0.1, 0.8, 0.02]))
    cs = ax.contour(ws.lon, ws.lat, ws.values, colors="blue", linewidths=1.5,
                    levels=np.arange(40, 300, 20), transform=latlon)
    ax.clabel(cs, fontsize=14, colors="blue", fmt="%i")
    levels_h = np.arange(int(hgt.min() / 120) * 120, hgt.max() + 120, 120)
    ch = ax.contour(hgt.lon, hgt.lat, hgt, colors="black", linewidths=1.2,
                    levels=levels_h, transform=latlon)
    ax.clabel(ch, fontsize=14, colors="black", fmt="%i")
    s = (slice(None, None, 3), slice(None, None, 3))
    ax.barbs(uag.lon[s[1]], uag.lat[s[0]], uag.values[s], vag.values[s],
             length=5.5, pivot="middle", color="black", transform=latlon)
    fig.text(0.5, 0.01, f"JRA-55 {ctx['valid']:%HUTC%d%b%Y} 300hPa Heights, ISOTACH, Divergence, Ageostrophic Wind",
             ha="center", size=14)
    return save(fig, ctx["output_dir"], ctx["valid"], "300hPa_Jet_Divergence")


def plot_fax57(ctx):
    t500 = celsius(ctx["iso"]("TMP", 500))
    t700 = ctx["iso"]("TMP", 700)
    rh700 = rh_fraction(ctx["iso"]("RH", 700))
    t700c = celsius(t700)
    ttd = t700c - mpcalc.dewpoint_from_relative_humidity(t700, rh700)
    fig, ax, latlon = setup_map([108, 156, 17, 55])
    cnf = ax.contourf(ttd.lon, ttd.lat, ttd, [0, 3, 6, 18, 100],
                      colors=["green", "0.4", "1.0", "yellow"], alpha=0.25,
                      extend="both", transform=latlon)
    fig.colorbar(cnf, orientation="horizontal", cax=fig.add_axes([0.1, 0.1, 0.8, 0.02]))
    ax.contour(ttd.lon, ttd.lat, ttd, colors="gray", linewidths=1.0,
               levels=np.arange(3, 30, 3), transform=latlon)
    cs = ax.contour(t500.lon, t500.lat, t500, colors="blue", linewidths=1.3,
                    levels=np.arange(-60, 42, 3), transform=latlon)
    ax.clabel(cs, fontsize=12, colors="blue", fmt="%i")
    fig.text(0.5, 0.01, f"JRA-55 {ctx['valid']:%HUTC%d%b%Y} 500hPa Temp, 700hPa T-Td",
             ha="center", size=14)
    return save(fig, ctx["output_dir"], ctx["valid"], "Fax57")


def plot_fax78(ctx):
    t850 = celsius(ctx["iso"]("TMP", 850))
    u850 = ctx["iso"]("UGRD", 850)
    v850 = ctx["iso"]("VGRD", 850)
    div700 = ctx["iso"]("RELD", 700)
    fig, ax, latlon = setup_map([108, 156, 17, 55])
    div = np.clip(div700.values * 1e5, -20, 10)
    cn = ax.contourf(div700.lon, div700.lat, div, [-20, -10, -5, -2, 2, 5, 10],
                     colors=["red", "orange", "gray", "white", "yellow", "skyblue"],
                     alpha=0.5, extend="both", transform=latlon)
    fig.colorbar(cn, orientation="horizontal", cax=fig.add_axes([0.1, 0.1, 0.8, 0.02]))
    cs = ax.contour(t850.lon, t850.lat, t850, colors="blue", linewidths=1.3,
                    levels=np.arange(-60, 42, 3), transform=latlon)
    ax.clabel(cs, fontsize=12, colors="blue", fmt="%i")
    s = (slice(None, None, 5), slice(None, None, 5))
    ax.barbs(u850.lon[s[1]], u850.lat[s[0]], u850.values[s] * 1.944, v850.values[s] * 1.944,
             length=5.5, pivot="middle", color="black", transform=latlon)
    fig.text(0.5, 0.01, f"JRA-55 {ctx['valid']:%HUTC%d%b%Y} 700hPa Divergence, 850hPa Temp/Wind",
             ha="center", size=14)
    return save(fig, ctx["output_dir"], ctx["valid"], "Fax78")


def plot_ept(ctx):
    t850 = ctx["iso"]("TMP", 850)
    rh850 = rh_fraction(ctx["iso"]("RH", 850))
    u850 = ctx["iso"]("UGRD", 850)
    v850 = ctx["iso"]("VGRD", 850)
    td = mpcalc.dewpoint_from_relative_humidity(t850, rh850)
    ept = mpcalc.equivalent_potential_temperature(850 * units.hPa, t850, td)
    fig, ax, latlon = setup_map([115, 151, 20, 50])
    cn = ax.contourf(ept.lon, ept.lat, ept, np.arange(270, 360, 3),
                     cmap="jet", extend="both", transform=latlon)
    fig.colorbar(cn, orientation="horizontal", cax=fig.add_axes([0.1, 0.1, 0.8, 0.02]))
    cs = ax.contour(ept.lon, ept.lat, ept, colors="black", linewidths=0.5,
                    levels=np.arange(270, 390, 3), transform=latlon)
    ax.clabel(cs, fontsize=8, fmt="%i")
    s = (slice(None, None, 5), slice(None, None, 5))
    ax.barbs(u850.lon[s[1]], u850.lat[s[0]], u850.values[s] * 1.944, v850.values[s] * 1.944,
             length=5.5, pivot="middle", color="black", transform=latlon)
    fig.text(0.5, 0.01, f"JRA-55 {ctx['valid']:%HUTC%d%b%Y} 850hPa EPT(K), Wind",
             ha="center", size=14)
    return save(fig, ctx["output_dir"], ctx["valid"], "850hPa_EPT")


def plot_srf(ctx):
    prmsl = ctx["surf"]("PRMSL", "msl")
    u = ctx["surf"]("UGRD", "fhg")
    v = ctx["surf"]("VGRD", "fhg")
    tmp = ctx["surf"]("TMP", "fhg")
    pre = prmsl / 100.0 if float(prmsl.mean()) > 2000 else prmsl
    temp = celsius(tmp)
    fig, ax, latlon = setup_map([108, 156, 17, 55])
    ax.contour(temp.lon, temp.lat, temp, colors="green", alpha=0.5,
               linewidths=1.0, levels=np.arange(-60, 60, 3), transform=latlon)
    ax.contour(pre.lon, pre.lat, pre, colors="black", linewidths=1.0,
               levels=np.arange(860, 1100, 4), transform=latlon)
    cs = ax.contour(pre.lon, pre.lat, pre, colors="black", linewidths=2.4,
                    levels=np.arange(860, 1100, 20), transform=latlon)
    ax.clabel(cs, fontsize=12, colors="black", fmt="%i")
    s = (slice(None, None, 5), slice(None, None, 5))
    ax.barbs(u.lon[s[1]], u.lat[s[0]], u.values[s] * 1.944, v.values[s] * 1.944,
             length=5.5, pivot="middle", color="black", transform=latlon)
    fig.text(0.5, 0.01, f"JRA-55 {ctx['valid']:%HUTC%d%b%Y} Surface Pressure, Wind, 2m Temp",
             ha="center", size=14)
    return save(fig, ctx["output_dir"], ctx["valid"], "SurfacePressure")


def main():
    args = parse_args()
    try:
        valid_time = parse_valid_time(args.valid_time)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(2)
    user, password = load_credentials(args)
    lat_slice = slice(80.0, -20.0)
    lon_slice = slice(70.0, 190.0)
    cache = {}

    def iso(var_name, level):
        key = ("iso", var_name, level)
        if key not in cache:
            cache[key] = read_iso(args.data_dir, var_name, valid_time, level, lat_slice, lon_slice, user, password)
        return cache[key]

    def surf(var_name, suffix):
        key = ("surf", var_name, suffix)
        if key not in cache:
            cache[key] = read_surf(args.data_dir, var_name, suffix, valid_time, user, password)
        return cache[key]

    ctx = {"valid": valid_time, "output_dir": args.output_dir, "iso": iso, "surf": surf}
    plotters = {"jet": plot_jet, "fax57": plot_fax57, "fax78": plot_fax78, "ept": plot_ept, "srf": plot_srf}
    for chart in args.charts:
        print(f"=== {chart} ===")
        plotters[chart](ctx)


if __name__ == "__main__":
    main()
