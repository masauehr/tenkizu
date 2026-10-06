"""MSM 地上風（10m）の指定地点時系列を、京大生存圏研究所の日別NetCDF（MSM-S）から取得してCSV化する。

データ源: 京都大学生存圏研究所 気象庁データアーカイブ（研究・教育目的）
  http://database.rish.kyoto-u.ac.jp/arch/jmadata/data/gpv/netcdf/MSM-S/YYYY/MMDD.nc
  - 1ファイル=1日（UTC）分、約140MB。毎日 01:00 GMT 頃に前日分が公開される。
  - 時刻は1時間ごと24点。00,03,...,21UTC は初期値（FH00=解析値）、
    それ以外は直前の初期値からの1〜2時間予報。→ CSV の is_analysis 列で区別する。

出力列: time_utc, time_jst, u, v, wspd(m/s), wdir(度, 風が吹いてくる方位), is_analysis

使い方:
  python msm_wind_fetch.py                       # 直近5日（UTCで昨日まで）
  python msm_wind_fetch.py --days 5 --end 2026-10-02
  python msm_wind_fetch.py --start 2026-09-28 --end 2026-10-02 --lat 26.1708 --lon 127.7418
  python msm_wind_fetch.py --analysis-only       # 3時間ごとの解析値のみ

NetCDF は地点を抜き出した後に削除する（--keep で保存）。data/MMDD.nc が既にあればそれを使う。
サーバー負荷配慮のため、ダウンロード間隔を空ける。
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import xarray as xr

BASE_URL = "http://database.rish.kyoto-u.ac.jp/arch/jmadata/data/gpv/netcdf/MSM-S"
DATA_DIR = Path(__file__).resolve().parent / "data"
HEADERS = {"User-Agent": "tenkizu-msm-wind-fetch (research use)"}
REQUEST_INTERVAL_SEC = 3.0

# 既定の地点: nouken と同じ 沖縄本島南部
DEFAULT_LAT = 26.1708
DEFAULT_LON = 127.7418


def day_url(day: dt.date) -> str:
    return f"{BASE_URL}/{day.year}/{day:%m%d}.nc"


def download_day(day: dt.date, dest: Path) -> bool:
    """1日分のNetCDFをダウンロードする。未公開（404）なら False。"""
    tmp = dest.with_suffix(".part")
    try:
        with requests.get(day_url(day), headers=HEADERS, stream=True, timeout=120) as r:
            if r.status_code == 404:
                return False
            r.raise_for_status()
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
    except requests.RequestException:
        tmp.unlink(missing_ok=True)
        raise
    tmp.rename(dest)
    return True


def extract_point(nc_path: Path, lat: float, lon: float) -> pd.DataFrame:
    """NetCDF から最寄り格子の u, v を取り出し、風速・風向・解析値フラグを付ける。"""
    with xr.open_dataset(nc_path) as ds:
        pt = ds[["u", "v"]].sel(lat=lat, lon=lon, method="nearest").load()
        grid_lat, grid_lon = float(pt.lat), float(pt.lon)
    df = pt.to_dataframe()[["u", "v"]].reset_index()
    df["time_utc"] = df["time"]
    df["time_jst"] = df["time_utc"] + pd.Timedelta(hours=9)
    df["wspd"] = np.hypot(df["u"], df["v"])
    df["wdir"] = np.degrees(np.arctan2(-df["u"], -df["v"])) % 360
    df["is_analysis"] = df["time_utc"].dt.hour % 3 == 0   # FH00=初期値（解析値）
    df.attrs["grid"] = (grid_lat, grid_lon)
    return df[["time_utc", "time_jst", "u", "v", "wspd", "wdir", "is_analysis"]]


def fetch_range(start: dt.date, end: dt.date, lat: float, lon: float,
                keep: bool = False, data_dir: Path = DATA_DIR) -> tuple[pd.DataFrame, tuple[float, float] | None]:
    """start〜end（UTC日付, 両端含む）を取得して縦に連結する。"""
    data_dir.mkdir(parents=True, exist_ok=True)
    frames, grid = [], None
    days = pd.date_range(start, end, freq="D").date
    downloaded_prev = False
    for day in days:
        local = data_dir / f"{day:%m%d}.nc"
        existed = local.exists()
        if not existed:
            if downloaded_prev:
                time.sleep(REQUEST_INTERVAL_SEC)
            print(f"  {day}: ダウンロード中 {day_url(day)}", flush=True)
            if not download_day(day, local):
                print(f"  {day}: 未公開（404）のためスキップ")
                downloaded_prev = False
                continue
            downloaded_prev = True
        else:
            print(f"  {day}: ローカルの {local.name} を使用")
            downloaded_prev = False
        df = extract_point(local, lat, lon)
        grid = df.attrs.get("grid", grid)
        frames.append(df)
        if not existed and not keep:
            local.unlink()
    if not frames:
        return pd.DataFrame(), grid
    out = pd.concat(frames, ignore_index=True).drop_duplicates("time_utc")
    return out.sort_values("time_utc").reset_index(drop=True), grid


def default_end() -> dt.date:
    """UTC で昨日（前日分は 01:00 GMT 頃に公開される）。"""
    return dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--start", type=dt.date.fromisoformat, help="開始日 YYYY-MM-DD（UTC）")
    p.add_argument("--end", type=dt.date.fromisoformat, help="終了日 YYYY-MM-DD（UTC, 既定=昨日）")
    p.add_argument("--days", type=int, default=5, help="--start 省略時の日数（既定5）")
    p.add_argument("--lat", type=float, default=DEFAULT_LAT)
    p.add_argument("--lon", type=float, default=DEFAULT_LON)
    p.add_argument("--analysis-only", action="store_true", help="3時間ごとの解析値のみ出力")
    p.add_argument("--keep", action="store_true", help="ダウンロードしたNetCDFを残す")
    p.add_argument("--out", type=Path, help="出力CSV（既定 data/msm_wind_<期間>.csv）")
    a = p.parse_args()

    end = a.end or default_end()
    start = a.start or (end - dt.timedelta(days=a.days - 1))
    if start > end:
        p.error("--start が --end より後")

    print(f"MSM-S 風 取得: {start}〜{end} (UTC)  地点 N{a.lat:.4f}, E{a.lon:.4f}")
    df, grid = fetch_range(start, end, a.lat, a.lon, keep=a.keep)
    if df.empty:
        print("取得できた日が0件でした。", file=sys.stderr)
        return 1
    if a.analysis_only:
        df = df[df["is_analysis"]].reset_index(drop=True)

    out = a.out or DATA_DIR / f"msm_wind_{start:%Y%m%d}_{end:%Y%m%d}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.round(3).to_csv(out, index=False)
    print(f"最寄り格子: N{grid[0]:.4f}, E{grid[1]:.4f}")
    print(f"-> {out}  ({len(df)}行, {df['time_utc'].min()}〜{df['time_utc'].max()} UTC)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
