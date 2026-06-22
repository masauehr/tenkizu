#!/usr/bin/env python
# coding: utf-8
# tenkizuプロジェクト 実行環境確認スクリプト
# 使い方:
#   python python_env.py              # 全スクリプトの環境一覧
#   python python_env.py jet          # 名前にjetを含むスクリプトを検索
#   python python_env.py ?            # ヘルプ表示

import sys
import os
from pathlib import Path

# =====================================================================
# スクリプト → 仮想環境 マッピング
# =====================================================================
SCRIPT_ENV = {
    # --- GSM系（met_env_310） ---
    "GSM_tenkizu500hPa.py":  "met_env_310",
    "GSM_tekizu500hPa.py":   "met_env_310",
    "GSM_QVector850hPa.py":  "met_env_310",
    "GSM_Jet300hPa.py":      "met_env_310",
    "GSM_Instability.py":    "met_env_310",
    "GSM_CrossSection.py":   "met_env_310",
    "GSM_fax57.py":          "met_env_310",
    "GSM_fax78.py":          "met_env_310",
    "GSM_faxSrfPre.py":      "met_env_310",
    "GSM_EPT850hPa.py":      "met_env_310",
    "GSM_100hPa.py":         "met_env_310",
    "GSM_PolarView.py":      "met_env_310",
    # --- ECM系（met_env_310） ---
    "ECM_tenkizu500hPa.py":  "met_env_310",
    "ECM_EPT850hPa.py":      "met_env_310",
    "ECM_Fax57.py":          "met_env_310",
    "ECM_Fax78.py":          "met_env_310",
    "ECM_SurfacePressure.py":"met_env_310",
    "ECM_100hPa.py":         "met_env_310",
    # --- AIFS系（met_env_310） ---
    "AIFS_SurfacePressure.py":     "met_env_310",
    "AIFS_ENS_SurfacePressure.py": "met_env_310",
    # --- GFS系（met_env_310） ---
    "GFS_SurfacePressure.py":      "met_env_310",
    # --- GRIB2エマグラム（met_env_310） ---
    "GRIB2_Emagram.py":      "met_env_310",
    # --- レポート（GSM/ECM混在 → met_env_310） ---
    "jet_front_report.py":      "met_env_310",
    "jet_front_wide_report.py": "met_env_310",
    "jet_front_ave_report.py":  "met_env_310",
    "jet_front_compare_report.py": "met_env_310",
    "synop_report.py":          "met_env_310",
    "typhoon-multi.py":         "met_env_310",
    "upper_wind_report.py":     "met_env_310",
    # --- ユーティリティ（met_env_310） ---
    "download_gsm.py":       "met_env_310",
    "run_gsm_auto.py":       "met_env_310",
    "run_gsm_ept_auto.py":   "met_env_310",
    "run_ecm_auto.py":       "met_env_310",
    "run_ecm_500hpa_auto.py":"met_env_310",
    "make_pptx.py":          "met_env_310",
    "make_pptx2.py":         "met_env_310",
    "kurora_tenkizu.py":     "met_env_310",
    "make_ncep_climo.py":    "met_env_310",
    # --- Wyoming ゾンデ（met_env_310 or met_env） ---
    "emagram.py":            "met_env_310",
    # --- JRA-55系（met_env） ---
    "JRA55_SynopCharts.py":  "met_env",
    "JRA55_JetDivergence.py":"met_env",
    "JRA55_Emagram.py":      "met_env",
    "jra55_synop_report.py": "met_env",
    "jra55_jet_report.py":   "met_env",
}

ENV_DESCRIPTION = {
    "met_env_310": "GSM/ECM/AIFS/GFS系（pygrib使用）",
    "met_env":     "JRA-55系（xarray/NetCDF使用）",
}

ENV_ACTIVATE = {
    "met_env_310": "conda activate met_env_310",
    "met_env":     "conda activate met_env",
}

# =====================================================================
# 表示ヘルパー
# =====================================================================
def color(text, code):
    return f"\033[{code}m{text}\033[0m" if sys.stdout.isatty() else text

def bold(t):    return color(t, "1")
def green(t):   return color(t, "32")
def yellow(t):  return color(t, "33")
def cyan(t):    return color(t, "36")
def dim(t):     return color(t, "2")


def show_help():
    print(bold("python_env.py") + "  —  tenkizu スクリプト実行環境確認ツール")
    print()
    print("使い方:")
    print("  python python_env.py              全スクリプトの環境一覧を表示")
    print("  python python_env.py <キーワード>  名前に一致するスクリプトを絞り込み")
    print("  python python_env.py ?            このヘルプを表示")
    print()
    print("例:")
    print("  python python_env.py jet          jet_front_*.py を一覧")
    print("  python python_env.py jra55        JRA-55系を一覧")
    print("  python python_env.py ECM          ECM系を一覧")
    print()
    print("仮想環境の切り替え:")
    for env, cmd in ENV_ACTIVATE.items():
        print(f"  {green(env):30s}  {cmd}")


def show_env_summary():
    """環境ごとのグループ表示"""
    groups = {}
    for script, env in SCRIPT_ENV.items():
        groups.setdefault(env, []).append(script)

    for env in ["met_env_310", "met_env"]:
        scripts = groups.get(env, [])
        desc = ENV_DESCRIPTION.get(env, "")
        cmd  = ENV_ACTIVATE.get(env, "")
        print(bold(f"[ {env} ]") + f"  {dim(desc)}")
        print(f"  {cyan('activate:')} {cmd}")
        print()
        for s in sorted(scripts):
            exists = Path(s).exists()
            mark = green("✓") if exists else dim("○")
            print(f"  {mark}  {s}")
        print()


def show_filtered(keyword):
    """キーワードでフィルタリング"""
    matched = {k: v for k, v in SCRIPT_ENV.items()
               if keyword.lower() in k.lower()}

    if not matched:
        # スクリプト名で見つからなければ環境名でも検索
        matched = {k: v for k, v in SCRIPT_ENV.items()
                   if keyword.lower() in v.lower()}

    if not matched:
        print(f"「{keyword}」に一致するスクリプトが見つかりません。")
        print(dim("ヒント: python python_env.py ? でヘルプ確認"))
        return

    # 環境ごとにグループ表示
    groups = {}
    for script, env in matched.items():
        groups.setdefault(env, []).append(script)

    print(bold(f"「{keyword}」に一致するスクリプト ({len(matched)}件)"))
    print()
    for env, scripts in sorted(groups.items()):
        desc = ENV_DESCRIPTION.get(env, "")
        cmd  = ENV_ACTIVATE.get(env, "")
        print(bold(f"[ {env} ]") + f"  {dim(desc)}")
        print(f"  {cyan('activate:')} {cmd}")
        print()
        for s in sorted(scripts):
            exists = Path(s).exists()
            mark = green("✓") if exists else dim("○")
            print(f"  {mark}  {s}")
        print()


def show_current_env():
    """現在アクティブな仮想環境を表示"""
    env_name = os.environ.get("CONDA_DEFAULT_ENV") or os.environ.get("VIRTUAL_ENV", "")
    if env_name:
        if "/" in env_name:
            env_name = Path(env_name).name
        print(dim(f"現在の環境: {env_name}"))
    else:
        print(dim("現在の環境: (base または未アクティベート)"))
    print()


# =====================================================================
# メイン
# =====================================================================
def main():
    args = sys.argv[1:]

    if args and args[0] in ("?", "-?", "--?", "-h", "--help"):
        show_help()
        return

    os.chdir(Path(__file__).parent)
    show_current_env()

    if args:
        show_filtered(args[0])
    else:
        show_env_summary()


if __name__ == "__main__":
    main()
