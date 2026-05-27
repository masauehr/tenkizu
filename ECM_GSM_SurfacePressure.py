#!/usr/bin/env python
# coding: utf-8

# GSM + ECMWF 地上気圧天気図 比較表示スクリプト
# 既存の GSM_faxSrfPre.py / ECM_SurfacePressure.py を実行し、
# 生成された PNG を1枚に結合して比較表示する。
# --push 付きで git push まで行う。
#
# 使用例:
#   python ECM_GSM_SurfacePressure.py 2026052712               # GSM+ECM FT=0h（両モデル）
#   python ECM_GSM_SurfacePressure.py 2026052712 0000 3        # GSMみ 3枚（6h間隔）
#   python ECM_GSM_SurfacePressure.py 2026052712 --ecm 0 3     # ECMWFみ 3枚
#   python ECM_GSM_SurfacePressure.py 2026052712 0000 12h      # GSM FT=0,12,...48h
#   python ECM_GSM_SurfacePressure.py 2026052712 --push

import os
import sys
import subprocess
import argparse
from pathlib import Path

OUTPUT_DIR = "./output"


# ---- プリセット ----
PRESETS = {
    "12h": {"interval": 12, "n_steps": 5},     # FT=0,12,24,36,48h
    "24h": {"interval": 24, "n_steps": 6},     # FT=0,24,48,72,96,120h
}


# ---- ユーティリティ ----
def ddhh_to_hours(ddhh):
    """DDHH形式(例: 0000) -> 時間数(例: 0)"""
    return (ddhh // 100) * 24 + (ddhh % 100)


def hours_to_ddhh(h):
    """時間数 -> DDHH形式(例: 0 -> 0000)"""
    return (h // 24) * 100 + (h % 24)


# ---- メイン ----
def parse_args():
    preset_list = ", ".join(
        f"{k}({v['interval']}h*{v['n_steps']})" for k, v in PRESETS.items()
    )
    parser = argparse.ArgumentParser(
        description=(
            "GSM+ECMWF 地上気圧天気図を比較表示（PNG結合版）\n"
            "\n"
            "使用例:\n"
            "  python ECM_GSM_SurfacePressure.py 2026052712\n"
            "    # GSM+ECM FT=0h（両モデル共通、デフォルト）\n"
            "  python ECM_GSM_SurfacePressure.py 2026052712 0000 3\n"
            "    # GSMみ 3枚（6h間隔: FT=0,6,12）\n"
            "  python ECM_GSM_SurfacePressure.py 2026052712 --ecm 0 3\n"
            "    # ECMWFみ 3枚（6h間隔: FT=0,6,12）\n"
            "  python ECM_GSM_SurfacePressure.py 2026052712 0000 12h\n"
            "    # GSM 12hプリセット（FT=0,12,24,36,48）\n"
            "  python ECM_GSM_SurfacePressure.py 2026052712 --push\n"
            "    # 両モデル実行後 GitHub push\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("init_time", type=str, help="初期時刻 YYYYMMDDHH（UTC）")

    # モデル切替フラグ（互いに排他）
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--gsm-only", action="store_true",
        help="GSMのみ実行（デフォルトは両モデル）",
    )
    mode_group.add_argument(
        "--ecm-only", action="store_true",
        help="ECMWFのみ実行（デフォルトは両モデル）",
    )

    # 標準引数（GSM DDHH / ECM 時間数 共用）
    parser.add_argument(
        "start_ft", type=str, nargs="?", default="0000",
        help="開始予報時間 DDHH(GSM)/時間数(ECM)。デフォルト: 0000",
    )
    parser.add_argument(
        "n_steps", type=str, nargs="?", default="1",
        help=f"枚数またはプリセット名 [{preset_list}]",
    )

    # git push
    parser.add_argument(
        "--push", action="store_true",
        help="生成後 GitHub へ git push する",
    )

    if any(a in sys.argv[1:] for a in ("?", "-?", "--?")):
        parser.print_help()
        sys.exit(0)

    return parser.parse_args()


def run_py(script, args_list, script_dir):
    """Python スクリプトを実行する"""
    cmd = f"python {script} {' '.join(args_list)}"
    print(f"    $ {cmd}")
    result = subprocess.run(
        cmd, shell=True, cwd=script_dir, text=True, executable="/bin/bash",
    )
    return result.returncode == 0


def git_run(cmd, cwd):
    """git コマンドを実行する"""
    print(f"    $ git {cmd}")
    result = subprocess.run(
        f"git {cmd}", shell=True, cwd=cwd, capture_output=True, text=True,
    )
    if result.stdout.strip():
        print(f"      {result.stdout.strip()}")
    if result.stderr.strip():
        print(f"      {result.stderr.strip()}")
    return result.returncode


def main():
    args = parse_args()
    init_str = args.init_time

    if len(init_str) != 10:
        print("エラー: init_time は YYYYMMDDHH の10桁で指定してください")
        sys.exit(1)

    # モデル切替判定
    run_gsm = not args.ecm_only        # --ecm-only 以外なら GSM
    run_ecm = not args.gsm_only        # --gsm-only 以外なら ECM

    # 引数解釈
    start_ddhh = int(args.start_ft)
    start_hours = ddhh_to_hours(start_ddhh)

    raw_steps = args.n_steps
    if raw_steps in PRESETS:
        n_steps = PRESETS[raw_steps]["n_steps"]
        interval = PRESETS[raw_steps]["interval"]
    else:
        n_steps = int(raw_steps)
        interval = 6

    # FTリスト生成（GSM/ECM 共に同じ範囲）
    gsm_fts = [hours_to_ddhh(start_hours + i * interval) for i in range(n_steps)]
    ecm_fts = [start_hours + i * interval for i in range(n_steps)]

    gsm_end = start_hours + (n_steps - 1) * interval
    ecm_end = start_hours + (n_steps - 1) * interval

    script_dir = Path(__file__).parent.resolve()
    output_dir = script_dir / OUTPUT_DIR

    print("=" * 60)
    print(f" GSM+ECMWF 地上気圧比較図 [{init_str}]")
    if run_gsm:
        print(f"  GSM   FT{start_hours}-{gsm_end}h ({n_steps}枚, {interval}h間隔)")
    if run_ecm:
        print(f"  ECM   FT{start_hours}-{ecm_end}h ({n_steps}枚, {interval}h間隔)")
    print(f"  出力先: {output_dir}/")
    print("=" * 60)

    # ====== Step 1: 既存スクリプト実行（PNG生成） ======
    print("\n--- Step 1: PNG 生成 ---")
    for ft_ddhh in gsm_fts:
        ft_h = ddhh_to_hours(ft_ddhh)
        run_py(
            "GSM_faxSrfPre.py",
            [init_str, f"{ft_ddhh:04d}", "1"],
            str(script_dir),
        )

    for ft_h in ecm_fts:
        run_py(
            "ECM_SurfacePressure.py",
            [init_str, str(ft_h), "1"],
            str(script_dir),
        )

    # ====== Step 2: PNG 探索 + 結合 ======
    print("\n--- Step 2: PNG 結合 ---")
    files_gsm = sorted(
        (f for f in output_dir.glob(f"{init_str}_*GSM_SurfacePressure.png")),
        key=lambda x: x.name,
    )
    files_ecm = sorted(
        (f for f in output_dir.glob(f"{init_str}_*ECM_SurfacePressure.png")),
        key=lambda x: x.name,
    )

    if not files_gsm and not files_ecm:
        print("エラー: 生成PNGが見つかりません。")
        sys.exit(1)

    # PIL で結合
    from PIL import Image, ImageDraw
    margin = 200                        # パネル間マージン（px）

    pairs = []
    for fg in files_gsm:
        base = fg.name.split("_FT")[0]    # ex: 2026052712_FT000h
        fe = next((f for f in files_ecm if f.name.startswith(base)), None)
        if fe:
            pairs.append((fg, fe))
        else:
            pairs.append((fg, None))      # ECM 未存在
    for fe in files_ecm:
        if not any(
            fe.name.startswith(fg.name.split("_FT")[0]) for fg in files_gsm
        ):
            pairs.append((None, fe))

    out_paths = []
    for fg_png, fe_png in pairs:
        gsm_img = Image.open(fg_png).convert("RGB") if fg_png else None
        ecm_img = Image.open(fe_png).convert("RGB") if fe_png else None

        # サイズ統一
        w = (gsm_img.width if gsm_img else ecm_img.width)
        h = (gsm_img.height if gsm_img else ecm_img.height)
        if gsm_img and (gsm_img.width != w or gsm_img.height != h):
            gsm_img = gsm_img.resize((w, h), Image.LANCZOS)
        if ecm_img and (ecm_img.width != w or ecm_img.height != h):
            ecm_img = ecm_img.resize((w, h), Image.LANCZOS)

        # 横に並べる
        combo_w = (w * 2) + margin
        combo = Image.new("RGB", (combo_w, h), "white")

        if gsm_img:
            combo.paste(gsm_img, (0, 0))
        if ecm_img:
            combo.paste(ecm_img, (w + margin, 0))

        # ラベル描画
        draw = ImageDraw.Draw(combo)
        if gsm_img:
            draw.text((w // 2 - 40, 10), "GSM", fill="darkblue")
        if ecm_img:
            draw.text((w + margin + w // 2 - 40, 10), "ECMWF", fill="darkred")

        out_name = fg_png.name if fg_png else fe_png.name
        out_name = out_name.replace(".png", "_combined.png")
        out_path = output_dir / out_name
        combo.save(out_path, dpi=150)
        print(f"    {out_path}")
        out_paths.append(out_path)

    # ====== Step 3: 結果表示 ======
    print(
        f"\n完了: GSM {len(files_gsm)}枚 + ECM {len(files_ecm)}枚"
    )
    print(f"     結合PNG: {len(out_paths)}枚 出力先: {output_dir}/")

    # ====== --push 処理 ======
    if not args.push:
        print("\nGitHub push はスキップ（--push を付けると実行）")
    else:
        print("\n--- GitHub へアップロード ---")
        rc = git_run(f"add {output_dir}", str(script_dir))
        if rc != 0:
            print("エラー: git add 失敗")
            sys.exit(1)

        staged = subprocess.run(
            "git diff --staged --quiet", shell=True,
            cwd=str(script_dir), capture_output=True,
        )
        if staged.returncode == 0:
            print("変更なし: 既にアップ済み（skip）")
        else:
            commit_msg = f"chart: GSM+ECM 地上気圧比較図 {init_str}"
            rc = git_run(f'commit -m "{commit_msg}"', str(script_dir))
            if rc != 0:
                print("エラー: git commit 失敗")
                sys.exit(1)

            git_run("config http.postBuffer 524288000", str(script_dir))
            rc = git_run("push", str(script_dir))
            if rc != 0:
                print("エラー: git push 失敗")
                sys.exit(1)
            print("  push OK")


if __name__ == "__main__":
    main()
