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
#                 "key" を指定すると FT=0,12,24,36,48h の5枚を生成（START_FTは無視）
#
# 例:
#   bash run_all_charts.sh 2023052312              # FT=0h 各1枚
#   bash run_all_charts.sh 2023052312 0000 5       # FT=0,6,12,18,24h 各5枚
#   bash run_all_charts.sh 2023052312 0100 3       # FT=24,30,36h 各3枚
#   bash run_all_charts.sh 2023052312 0000 key     # FT=0,12,24,36,48h 各5枚（keyモード）

set -e

INIT_TIME="$1"
START_FT_DDHH="${2:-0000}"   # 開始予報時間（DDHH形式）
N_STEPS="${3:-1}"            # 作成枚数、または "key"

if [ -z "$INIT_TIME" ]; then
    echo "エラー: 初期時刻を指定してください"
    echo "使用法: $0 YYYYMMDDHH [START_FT_DDHH [N_STEPS|key]]"
    exit 1
fi

if [ ${#INIT_TIME} -ne 10 ]; then
    echo "エラー: 初期時刻は YYYYMMDDHH の10桁で指定してください"
    exit 1
fi

# keyモード判定
KEY_MODE=false
if [ "$N_STEPS" = "key" ]; then
    KEY_MODE=true
fi

# ECM系はhours形式のため、DDHH → 時間数 に変換
# 例: 0100 → DD=01, HH=00 → 1*24+0 = 24h
DD=$((10#${START_FT_DDHH:0:2}))
HH=$((10#${START_FT_DDHH:2:2}))
START_FT_H=$((DD * 24 + HH))

# keyモード時の予報時間リスト
KEY_FTS_DDHH=(0000 0012 0100 0112 0200)   # GSM用（DDHH形式）
KEY_FTS_H=(0 12 24 36 48)                  # ECM用（時間数）

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# conda環境をアクティベート
source "$(conda info --base)/etc/profile.d/conda.sh" 2>/dev/null || true
conda activate met_env_310 2>/dev/null || true

if [ "$KEY_MODE" = true ]; then
    echo "=============================="
    echo "初期時刻: $INIT_TIME  モード: key（FT=0,12,24,36,48h）"
    echo "出力先: $SCRIPT_DIR/output/"
    echo "=============================="
else
    echo "=============================="
    echo "初期時刻: $INIT_TIME  開始FT: $START_FT_DDHH (FT=${START_FT_H}h)  枚数: $N_STEPS"
    echo "出力先: $SCRIPT_DIR/output/"
    echo "=============================="
fi
echo ""

# GSM系スクリプト実行関数（DDHH形式FT）
run_gsm() {
    local name="$1"
    local script="$2"
    echo "---------- $name ----------"
    if [ "$KEY_MODE" = true ]; then
        for ft in "${KEY_FTS_DDHH[@]}"; do
            python "$script" "$INIT_TIME" "$ft" 1 || echo "  ※ FT=$ft でエラーが発生しました（スキップ）"
        done
    else
        python "$script" "$INIT_TIME" "$START_FT_DDHH" "$N_STEPS" \
            || echo "  ※ $name でエラーが発生しました（スキップ）"
    fi
    echo ""
}

# ECM系スクリプト実行関数（時間数形式FT）
run_ecm() {
    local name="$1"
    local script="$2"
    echo "---------- $name ----------"
    if [ "$KEY_MODE" = true ]; then
        for ft in "${KEY_FTS_H[@]}"; do
            python "$script" "$INIT_TIME" "$ft" 1 || echo "  ※ FT=${ft}h でエラーが発生しました（スキップ）"
        done
    else
        python "$script" "$INIT_TIME" "$START_FT_H" "$N_STEPS" \
            || echo "  ※ $name でエラーが発生しました（スキップ）"
    fi
    echo ""
}

# GSM系（RISHサーバーからデータ取得）: start_ft は DDHH形式
run_gsm "GSM 500hPa高度・渦度"      GSM_tenkizu500hPa.py
run_gsm "GSM 850hPa Qベクター"       GSM_QVector850hPa.py
run_gsm "GSM 300hPa ジェット"        GSM_Jet300hPa.py
run_gsm "GSM 不安定域分布"           GSM_Instability.py
run_gsm "GSM 鉛直断面図"             GSM_CrossSection.py
run_gsm "GSM FAX57 500hPa気温"       GSM_fax57.py
run_gsm "GSM FAX78 850hPa気温・風"   GSM_fax78.py
run_gsm "GSM 地上気圧"               GSM_faxSrfPre.py
run_gsm "GSM 850hPa 相当温位"        GSM_EPT850hPa.py

# ECMWF系（ECMWF Open Dataからデータ取得）: start_ft は時間数（DDHHから変換済み）
run_ecm "ECMWF 500hPa高度・渦度"     ECM_tenkizu500hPa.py
run_ecm "ECMWF 850hPa 相当温位"      ECM_EPT850hPa.py
run_ecm "ECMWF FAX57 500hPa気温"     ECM_Fax57.py
run_ecm "ECMWF FAX78 700hPa収束"     ECM_Fax78.py
run_ecm "ECMWF 地上気圧"             ECM_SurfacePressure.py

echo "=============================="
echo "全処理完了"
echo "出力先: $SCRIPT_DIR/output/"
echo "=============================="
