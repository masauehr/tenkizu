#!/bin/bash
# 全天気図を一括生成するスクリプト
# 引数順は個別Pythonスクリプトと統一: INIT_TIME [START_FT [N_STEPS|PRESET]]
#
# 使用法: bash run_all_charts.sh YYYYMMDDHH [START_FT_DDHH [N_STEPS|12h|24h]] [--ecm] [--interval N]
#
# 引数説明:
#   INIT_TIME    : 初期時刻 YYYYMMDDHH（必須）
#   START_FT     : 開始予報時間 DDHH形式（省略時: 0000 = FT=0h）
#                  例: 0000=FT0h, 0006=FT6h, 0100=FT24h, 0112=FT36h
#   N_STEPS      : 作成する枚数（省略時: 1）または以下のプリセット名:
#                  "12h" → FT=0,12,24,36,48h の5枚（12h間隔、START_FTは無視）
#                  "24h" → FT=0,24,48,72,96,120h の6枚（24h間隔、START_FTは無視）
#   --ecm        : ECMWFも実行する（省略時はGSMのみ）
#   --interval N : プリセット未使用時のFT間隔 時間数（省略時: 6）
#
# 例:
#   bash run_all_charts.sh 2023052312                    # FT=0h GSMのみ1枚
#   bash run_all_charts.sh 2023052312 0000 5             # FT=0,6,12,18,24h GSMのみ5枚（6h間隔）
#   bash run_all_charts.sh 2023052312 0100 3             # FT=24,30,36h GSMのみ3枚
#   bash run_all_charts.sh 2023052312 0000 12h           # FT=0,12,24,36,48h GSMのみ（12hプリセット）
#   bash run_all_charts.sh 2023052312 0000 24h           # FT=0,24,48,72,96,120h GSMのみ（24hプリセット）
#   bash run_all_charts.sh 2023052312 0000 5 --interval 12   # 12h間隔 5枚
#   bash run_all_charts.sh 2023052312 0000 5 --ecm       # FT=0,6,12,18,24h GSM+ECM5枚

set -e

# オプションと位置引数を分離
WITH_ECM=false
INTERVAL=6
POSITIONAL=()

i=0
args_array=("$@")
while [ $i -lt ${#args_array[@]} ]; do
    arg="${args_array[$i]}"
    if [ "$arg" = "--ecm" ]; then
        WITH_ECM=true
    elif [ "$arg" = "--interval" ]; then
        i=$((i + 1))
        INTERVAL="${args_array[$i]}"
    else
        POSITIONAL+=("$arg")
    fi
    i=$((i + 1))
done

INIT_TIME="${POSITIONAL[0]:-}"
START_FT_DDHH="${POSITIONAL[1]:-0000}"   # 開始予報時間（DDHH形式）
N_STEPS="${POSITIONAL[2]:-1}"            # 作成枚数またはプリセット名

if [ -z "$INIT_TIME" ]; then
    echo "エラー: 初期時刻を指定してください"
    echo "使用法: $0 YYYYMMDDHH [START_FT_DDHH [N_STEPS|12h|24h]] [--ecm] [--interval N]"
    exit 1
fi

if [ ${#INIT_TIME} -ne 10 ]; then
    echo "エラー: 初期時刻は YYYYMMDDHH の10桁で指定してください"
    exit 1
fi

# ECM系はhours形式のため、DDHH → 時間数 に変換
DD=$((10#${START_FT_DDHH:0:2}))
HH=$((10#${START_FT_DDHH:2:2}))
START_FT_H=$((DD * 24 + HH))

# プリセット判定と FT リスト生成
PRESET_MODE=false
PRESET_LABEL=""
if [ "$N_STEPS" = "12h" ]; then
    PRESET_MODE=true
    PRESET_LABEL="12h"
    PRESET_FTS_DDHH=(0000 0012 0100 0112 0200)   # FT=0,12,24,36,48h（GSM用DDHH形式）
    PRESET_FTS_H=(0 12 24 36 48)                  # FT=0,12,24,36,48h（ECM用時間数）
elif [ "$N_STEPS" = "24h" ]; then
    PRESET_MODE=true
    PRESET_LABEL="24h"
    PRESET_FTS_DDHH=(0000 0100 0200 0300 0400 0500)  # FT=0,24,48,72,96,120h（GSM用DDHH形式）
    PRESET_FTS_H=(0 24 48 72 96 120)                  # FT=0,24,48,72,96,120h（ECM用時間数）
else
    # 数値枚数モード: --interval に従ってFTリストを生成
    FTS_DDHH=()
    FTS_H=()
    for ((step=0; step<N_STEPS; step++)); do
        ft_h=$((START_FT_H + step * INTERVAL))
        ft_dd=$((ft_h / 24))
        ft_hh=$((ft_h % 24))
        ft_ddhh=$(printf "%02d%02d" $ft_dd $ft_hh)
        FTS_DDHH+=("$ft_ddhh")
        FTS_H+=("$ft_h")
    done
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# conda環境をアクティベート
source "$(conda info --base)/etc/profile.d/conda.sh" 2>/dev/null || true
conda activate met_env_310 2>/dev/null || true

ECM_LABEL=""
if [ "$WITH_ECM" = true ]; then
    ECM_LABEL=" +ECM"
fi

if [ "$PRESET_MODE" = true ]; then
    echo "=============================="
    echo "初期時刻: $INIT_TIME  プリセット: ${PRESET_LABEL}（FT=${PRESET_FTS_H[*]}h）${ECM_LABEL}"
    echo "出力先: $SCRIPT_DIR/output/"
    echo "=============================="
else
    echo "=============================="
    echo "初期時刻: $INIT_TIME  開始FT: $START_FT_DDHH (FT=${START_FT_H}h)  枚数: $N_STEPS  間隔: ${INTERVAL}h${ECM_LABEL}"
    echo "出力先: $SCRIPT_DIR/output/"
    echo "=============================="
fi
echo ""

# GSM系スクリプト実行関数（DDHH形式FT、1枚ずつ）
run_gsm() {
    local name="$1"
    local script="$2"
    local extra_args="${3:-}"
    echo "---------- $name ----------"
    if [ "$PRESET_MODE" = true ]; then
        for ft in "${PRESET_FTS_DDHH[@]}"; do
            python "$script" "$INIT_TIME" "$ft" 1 $extra_args \
                || echo "  ※ FT=$ft でエラーが発生しました（スキップ）"
        done
    else
        for ft in "${FTS_DDHH[@]}"; do
            python "$script" "$INIT_TIME" "$ft" 1 $extra_args \
                || echo "  ※ FT=$ft でエラーが発生しました（スキップ）"
        done
    fi
    echo ""
}

# ECM系スクリプト実行関数（時間数形式FT、1枚ずつ）
run_ecm() {
    local name="$1"
    local script="$2"
    local extra_args="${3:-}"
    if [ "$WITH_ECM" = false ]; then
        return 0
    fi
    echo "---------- $name ----------"
    if [ "$PRESET_MODE" = true ]; then
        for ft in "${PRESET_FTS_H[@]}"; do
            python "$script" "$INIT_TIME" "$ft" 1 $extra_args \
                || echo "  ※ FT=${ft}h でエラーが発生しました（スキップ）"
        done
    else
        for ft in "${FTS_H[@]}"; do
            python "$script" "$INIT_TIME" "$ft" 1 $extra_args \
                || echo "  ※ FT=${ft}h でエラーが発生しました（スキップ）"
        done
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

# ECMWF系（ECMWF Open Dataからデータ取得）: --ecm 指定時のみ実行
run_ecm "ECMWF 500hPa高度・渦度"     ECM_tenkizu500hPa.py
run_ecm "ECMWF 850hPa 相当温位"      ECM_EPT850hPa.py
run_ecm "ECMWF FAX57 500hPa気温"     ECM_Fax57.py
run_ecm "ECMWF FAX78 700hPa収束"     ECM_Fax78.py
run_ecm "ECMWF 地上気圧"             ECM_SurfacePressure.py

# 100hPa 高度・風矢羽（GSM常時、ECMは --ecm 指定時のみ）
run_gsm "GSM 100hPa高度・風矢羽"     GSM_100hPa.py
run_ecm "ECMWF 100hPa高度・風矢羽"   ECM_100hPa.py

echo "=============================="
echo "全処理完了"
echo "出力先: $SCRIPT_DIR/output/"
echo "=============================="
