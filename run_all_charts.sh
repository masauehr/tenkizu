#!/bin/bash
# 全10天気図を一括生成するスクリプト
# 使用法: bash run_all_charts.sh YYYYMMDDHH [n_steps]
#
# 例:
#   bash run_all_charts.sh 2023052312       # 各スクリプト1枚（FT=0h）
#   bash run_all_charts.sh 2023052312 5     # 各スクリプト5枚（FT=0,6,12,18,24h）

set -e

INIT_TIME="$1"
N_STEPS="${2:-1}"

if [ -z "$INIT_TIME" ]; then
    echo "エラー: 初期時刻を指定してください"
    echo "使用法: $0 YYYYMMDDHH [n_steps]"
    exit 1
fi

if [ ${#INIT_TIME} -ne 10 ]; then
    echo "エラー: 初期時刻は YYYYMMDDHH の10桁で指定してください"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# conda環境をアクティベート
source "$(conda info --base)/etc/profile.d/conda.sh" 2>/dev/null || true
conda activate met_env_310 2>/dev/null || true

echo "=============================="
echo "初期時刻: $INIT_TIME  枚数: $N_STEPS"
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

# GSM系（RISHサーバーからデータ取得）
run_script "GSM 500hPa高度・渦度"      kurora_tenkizu.py       "$INIT_TIME" 0000 "$N_STEPS"
run_script "GSM 500hPa高度・渦度(詳細)" GSM_tenkizu500hPa.py    "$INIT_TIME" 0000 "$N_STEPS"
run_script "GSM 850hPa Qベクター"       GSM_QVector850hPa.py    "$INIT_TIME" 0000 "$N_STEPS"
run_script "GSM 300hPa ジェット"        GSM_Jet300hPa.py        "$INIT_TIME" 0000 "$N_STEPS"
run_script "GSM 不安定域分布"           GSM_Instability.py      "$INIT_TIME" 0000 "$N_STEPS"
run_script "GSM 鉛直断面図"             GSM_CrossSection.py     "$INIT_TIME" 0000 "$N_STEPS"

# ECMWF系（ECMWF Open Dataからデータ取得）
run_script "ECMWF 850hPa 相当温位"      ECM_EPT850hPa.py        "$INIT_TIME" 0 "$N_STEPS"
run_script "ECMWF FAX57 500hPa気温"     ECM_Fax57.py            "$INIT_TIME" 0 "$N_STEPS"
run_script "ECMWF FAX78 700hPa収束"     ECM_Fax78.py            "$INIT_TIME" 0 "$N_STEPS"
run_script "ECMWF 地上気圧"             ECM_SurfacePressure.py  "$INIT_TIME" 0 "$N_STEPS"

echo "=============================="
echo "全処理完了"
echo "出力先: $SCRIPT_DIR/output/"
echo "=============================="
