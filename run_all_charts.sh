#!/bin/bash
# 全天気図を一括生成するスクリプト
# 引数順は個別Pythonスクリプトと統一: INIT_TIME [START_FT [N_STEPS]]
#
# 使用法: bash run_all_charts.sh YYYYMMDDHH [START_FT_DDHH [N_STEPS]]
#
# 引数説明:
#   INIT_TIME   : 初期時刻 YYYYMMDDHH（必須）
#   START_FT    : 開始予報時間 DDHH形式（省略時: 0000 = FT=0h）
#                 例: 0000=FT0h, 0006=FT6h, 0100=FT24h, 0112=FT36h
#   N_STEPS     : 作成する枚数（省略時: 1）6h間隔
#
# 例:
#   bash run_all_charts.sh 2023052312              # FT=0h 各1枚
#   bash run_all_charts.sh 2023052312 0000 5       # FT=0,6,12,18,24h 各5枚
#   bash run_all_charts.sh 2023052312 0100 3       # FT=24,30,36h 各3枚

set -e

INIT_TIME="$1"
START_FT_DDHH="${2:-0000}"   # 開始予報時間（DDHH形式）
N_STEPS="${3:-1}"            # 作成枚数

if [ -z "$INIT_TIME" ]; then
    echo "エラー: 初期時刻を指定してください"
    echo "使用法: $0 YYYYMMDDHH [START_FT_DDHH [N_STEPS]]"
    exit 1
fi

if [ ${#INIT_TIME} -ne 10 ]; then
    echo "エラー: 初期時刻は YYYYMMDDHH の10桁で指定してください"
    exit 1
fi

# ECM系はhours形式のため、DDHH → 時間数 に変換
# 例: 0100 → DD=01, HH=00 → 1*24+0 = 24h
DD=$((10#${START_FT_DDHH:0:2}))
HH=$((10#${START_FT_DDHH:2:2}))
START_FT_H=$((DD * 24 + HH))

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# conda環境をアクティベート
source "$(conda info --base)/etc/profile.d/conda.sh" 2>/dev/null || true
conda activate met_env_310 2>/dev/null || true

echo "=============================="
echo "初期時刻: $INIT_TIME  開始FT: $START_FT_DDHH (FT=${START_FT_H}h)  枚数: $N_STEPS"
echo "出力先: $SCRIPT_DIR/output/"
echo "=============================="
echo ""

run_script() {
    local name="$1"
    local script="$2"
    shift 2
    echo "---------- $name ----------"
    python "$script" "$@" || echo "  ※ $name でエラーが発生しました（スキップ）"
    echo ""
}

# GSM系（RISHサーバーからデータ取得）: start_ft は DDHH形式
run_script "GSM 500hPa高度・渦度"      GSM_tenkizu500hPa.py    "$INIT_TIME" "$START_FT_DDHH" "$N_STEPS"
run_script "GSM 850hPa Qベクター"       GSM_QVector850hPa.py    "$INIT_TIME" "$START_FT_DDHH" "$N_STEPS"
run_script "GSM 300hPa ジェット"        GSM_Jet300hPa.py        "$INIT_TIME" "$START_FT_DDHH" "$N_STEPS"
run_script "GSM 不安定域分布"           GSM_Instability.py      "$INIT_TIME" "$START_FT_DDHH" "$N_STEPS"
run_script "GSM 鉛直断面図"             GSM_CrossSection.py     "$INIT_TIME" "$START_FT_DDHH" "$N_STEPS"

# ECMWF系（ECMWF Open Dataからデータ取得）: start_ft は時間数（DDHHから変換済み）
run_script "ECMWF 850hPa 相当温位"      ECM_EPT850hPa.py        "$INIT_TIME" "$START_FT_H" "$N_STEPS"
run_script "ECMWF FAX57 500hPa気温"     ECM_Fax57.py            "$INIT_TIME" "$START_FT_H" "$N_STEPS"
run_script "ECMWF FAX78 700hPa収束"     ECM_Fax78.py            "$INIT_TIME" "$START_FT_H" "$N_STEPS"
run_script "ECMWF 地上気圧"             ECM_SurfacePressure.py  "$INIT_TIME" "$START_FT_H" "$N_STEPS"

echo "=============================="
echo "全処理完了"
echo "出力先: $SCRIPT_DIR/output/"
echo "=============================="
