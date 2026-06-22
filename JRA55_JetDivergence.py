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

try:
    from pyproj import datadir

    if Path(os.environ["PROJ_LIB"]).exists():
        datadir.set_data_dir(os.environ["PROJ_LIB"])
except Exception:
    pass


BASE_URL = "https://database.rish.kyoto-u.ac.jp/arch/jra55/data/isobaric_1.25d"
VARS = ("HGT", "UGRD", "VGRD", "RELD")
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; JRA55-WeatherMap/1.0)"}


def parse_args():
    parser = argparse.ArgumentParser(
        description="JRA-55 NetCDF filesからジェット気流・上層発散天気図を作成する",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python JRA55_JetDivergence.py 1961071518
  python JRA55_JetDivergence.py 1961071518 --level 300 --data-dir data/Jra55
  JRA55_USER=xxxx JRA55_PASSWORD=yyyy python JRA55_JetDivergence.py 1961071518

実行環境（conda の場合）:
  conda activate met_env
  python JRA55_JetDivergence.py [引数]

  ※ 環境名（met_env）は利用者の構築状況により異なります。
     xarray / metpy / cartopy 等が入った Python 3.10 環境であれば動作します。
""",
    )
    parser.add_argument("valid_time", help="valid time in UTC: YYYYMMDDHH")
    parser.add_argument("--level", type=int, default=300, help="pressure level hPa")
    parser.add_argument("--data-dir", default="./data/Jra55", help="NetCDF storage directory")
    parser.add_argument("--output-dir", default="./output", help="PNG output directory")
    parser.add_argument(
        "--config",
        default="./jra55_config.ini",
        help="JRA-55 credential config file. Not tracked by git by default.",
    )
    parser.add_argument("--user", default=os.environ.get("JRA55_USER"), help="RISH JRA-55 user ID")
    parser.add_argument(
        "--password",
        default=os.environ.get("JRA55_PASSWORD"),
        help="RISH JRA-55 password",
    )
    parser.add_argument("--lon-west", type=float, default=70.0, help="read area west longitude")
    parser.add_argument("--lon-east", type=float, default=190.0, help="read area east longitude")
    parser.add_argument("--lat-north", type=float, default=80.0, help="read area north latitude")
    parser.add_argument("--lat-south", type=float, default=-20.0, help="read area south latitude")
    parser.add_argument("--map-west", type=float, default=115.0, help="plot area west longitude")
    parser.add_argument("--map-east", type=float, default=151.0, help="plot area east longitude")
    parser.add_argument("--map-south", type=float, default=20.0, help="plot area south latitude")
    parser.add_argument("--map-north", type=float, default=50.0, help="plot area north latitude")
    parser.add_argument("--barb-step", type=int, default=3, help="ageostrophic wind barb thinning")

    # ? / -? / --? でヘルプ表示
    if any(a in sys.argv[1:] for a in ('?', '-?', '--?')):
        parser.print_help()
        sys.exit(0)

    return parser.parse_args()


def load_credentials(args):
    user = args.user
    password = args.password
    config_path = Path(args.config)

    if config_path.exists():
        config = configparser.ConfigParser()
        config.read(config_path, encoding="utf-8")
        if config.has_section("jra55"):
            user = user or config.get("jra55", "user", fallback=None)
            password = password or config.get("jra55", "password", fallback=None)

    return user, password


def parse_valid_time(value):
    if len(value) != 10 or not value.isdigit():
        raise ValueError("valid_time must be YYYYMMDDHH")
    valid = dt.datetime.strptime(value, "%Y%m%d%H").replace(tzinfo=dt.timezone.utc)
    if valid.hour not in (0, 6, 12, 18):
        raise ValueError("JRA-55 isobaric_1.25d data is available every 6 hours")
    return valid


def monthly_file(data_dir, var_name, valid_time):
    yyyymm = valid_time.strftime("%Y%m")
    return Path(data_dir) / var_name / valid_time.strftime("%Y") / f"{var_name}_{yyyymm}.nc"


def source_url(var_name, valid_time):
    yyyymm = valid_time.strftime("%Y%m")
    year = valid_time.strftime("%Y")
    return f"{BASE_URL}/{var_name}/{year}/{var_name}_{yyyymm}.nc"


def ensure_file(path, var_name, valid_time, user=None, password=None):
    if path.exists() and path.stat().st_size > 0:
        return path

    url = source_url(var_name, valid_time)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".part")
    auth = (user, password) if user and password else None

    print(f"Downloading {var_name}: {url}")
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
                        pct = downloaded / total * 100.0
                        print(
                            f"\r  {pct:5.1f}% ({downloaded/1048576:.1f}/{total/1048576:.1f} MB)",
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
            raise RuntimeError(
                "JRA-55 authentication failed. Set JRA55_USER/JRA55_PASSWORD "
                "or pass --user/--password."
            ) from exc
        raise
    except requests.RequestException:
        if tmp_path.exists():
            tmp_path.unlink()
        raise

    return path


def open_field(path, var_name, valid_time, level, lat_slice, lon_slice):
    ds = xr.open_dataset(path)
    data = ds.metpy.parse_cf(var_name).squeeze()

    if var_name == "HGT":
        data.attrs["units"] = "meter"
    elif var_name in ("UGRD", "VGRD"):
        data.attrs["units"] = "m/s"
    elif var_name == "RELD":
        data.attrs["units"] = "1 / second"

    time_index = (valid_time.day - 1) * 4 + valid_time.hour // 6
    return data.isel(time=time_index).sel(level=level, lat=lat_slice, lon=lon_slice)


def height_interval(level):
    if level < 400:
        return 120
    if level < 700:
        return 60
    return 30


def plot_chart(fields, valid_time, level, args):
    hgt = fields["HGT"]
    ugrd = fields["UGRD"]
    vgrd = fields["VGRD"]
    reld = fields["RELD"]

    _, _ = mpcalc.geostrophic_wind(hgt)
    uag, vag = mpcalc.ageostrophic_wind(hgt, ugrd, vgrd)
    uag = uag.metpy.convert_units("knots")
    vag = vag.metpy.convert_units("knots")
    wind_speed = mpcalc.wind_speed(ugrd, vgrd).metpy.convert_units("knots")

    levels_reld = [-10, -5, -2, -1, 1, 2, 5, 10]
    levels_ws = np.arange(40, 300, 20)
    dd_hgt = height_interval(level)
    min_hgt = int(hgt.min() / dd_hgt) * dd_hgt
    levels_hgt = np.arange(min_hgt, hgt.max() + dd_hgt, dd_hgt)

    proj = ccrs.Stereographic(central_latitude=60, central_longitude=140)
    latlon_proj = ccrs.PlateCarree()
    fig = plt.figure(figsize=(10, 8))
    plt.rcParams["contour.negative_linestyle"] = "solid"
    plt.subplots_adjust(left=0, right=1, bottom=0.06, top=0.98)

    ax = fig.add_subplot(1, 1, 1, projection=proj)
    ax.set_extent([args.map_west, args.map_east, args.map_south, args.map_north], latlon_proj)
    ax.coastlines(resolution="50m")

    gl = ax.gridlines(crs=latlon_proj, draw_labels=False, linewidth=1, alpha=0.8)
    gl.xlocator = mticker.FixedLocator(np.arange(0, 360.1, 10))
    gl.ylocator = mticker.FixedLocator(np.arange(-90, 90.1, 10))

    cn_reld = ax.contourf(
        reld.lon,
        reld.lat,
        reld.values * 1e5,
        levels_reld,
        cmap="coolwarm",
        extend="both",
        transform=latlon_proj,
    )
    ax_reld = fig.add_axes([0.1, 0.1, 0.8, 0.02])
    cb_reld = fig.colorbar(cn_reld, orientation="horizontal", aspect=40, pad=0.01, cax=ax_reld)
    cb_reld.set_label("Divergence (*10$^{-5}$ s$^{-1}$)")

    cn_ws = ax.contour(
        wind_speed.lon,
        wind_speed.lat,
        wind_speed.values,
        colors="blue",
        linewidths=1.5,
        levels=levels_ws,
        transform=latlon_proj,
    )
    ax.clabel(cn_ws, fontsize=18, inline=True, colors="blue", inline_spacing=5, fmt="%i")

    cn_hgt = ax.contour(
        hgt.lon,
        hgt.lat,
        hgt,
        colors="black",
        linewidths=1.2,
        levels=levels_hgt,
        transform=latlon_proj,
    )
    ax.clabel(cn_hgt, levels_hgt, fontsize=18, inline=True, colors="black", inline_spacing=5, fmt="%i")

    step = max(1, args.barb_step)
    wind_slice0 = slice(None, None, step)
    wind_slice2 = (slice(None, None, step), slice(None, None, step))
    ax.barbs(
        uag.lon[wind_slice0],
        uag.lat[wind_slice0],
        uag.values[wind_slice2],
        vag.values[wind_slice2],
        length=5.5,
        pivot="middle",
        color="black",
        transform=latlon_proj,
    )

    label_time = valid_time.strftime("%HZ%d%b%Y").upper()
    fig.text(
        0.5,
        0.01,
        f"JRA-55 {label_time} {level}hPa Heights, ISOTACH, Divergence, Ageostrophic Wind",
        ha="center",
        va="bottom",
        size=15,
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{valid_time.strftime('%Y%m%d%H')}_JRA55_{level}hPa_Jet_Divergence.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_path


def main():
    args = parse_args()
    try:
        valid_time = parse_valid_time(args.valid_time)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(2)

    lat_slice = slice(args.lat_north, args.lat_south)
    lon_slice = slice(args.lon_west, args.lon_east)

    fields = {}
    user, password = load_credentials(args)
    for var_name in VARS:
        path = monthly_file(args.data_dir, var_name, valid_time)
        path = ensure_file(path, var_name, valid_time, user, password)
        print(f"Reading {var_name}: {path}")
        fields[var_name] = open_field(path, var_name, valid_time, args.level, lat_slice, lon_slice)

    out_path = plot_chart(fields, valid_time, args.level, args)
    print(f"Output: {out_path}")


if __name__ == "__main__":
    main()
