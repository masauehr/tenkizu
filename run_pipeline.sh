#!/bin/bash
# GSM天気図作成パイプライン
# ダウンロード → 天気図描画 を一括実行する
# 使用例:
#   bash run_pipeline.sh                          # 最新データを自動検索して描画
#   bash run_pipeline.sh --date 20171210          # 指定日のデータをDLして描画
#   bash run_pipeline.sh --date 20171210 --hour 12 # 時刻指定

# Conda環境を初期化（環境に応じて適切なパスが自動選択される）
CONDA_INIT=""
for conda_path in \
    "/opt/anaconda3/etc/profile.d/conda.sh" \
    "$HOME/anaconda3/etc/profile.d/conda.sh" \
    "$HOME/miniconda3/etc/profile.d/conda.sh"; do
    if [ -f "$conda_path" ]; then
        CONDA_INIT="$conda_path"
        break
    fi
done

if [ -z "$CONDA_INIT" ]; then
    echo "エラー: Conda の初期化スクリプトが見つかりません。"
    exit 1
fi

source "$CONDA_INIT"
conda activate met_env_310

echo "=== GSM天気図作成パイプライン 開始 ==="

# ステップ1: データダウンロード
echo ""
echo "--- ステップ1: GSMデータダウンロード ---"
python download_gsm.py "$@"
if [ $? -ne 0 ]; then
    echo "エラー: ダウンロードに失敗しました。"
    exit 1
fi

# ステップ2: 天気図描画（data_gsmにある全ファイルから描画）
echo ""
echo "--- ステップ2: 天気図描画 ---"

# data_gsmディレクトリ内のGSMファイルを検索して描画
DRAWN=0
for filepath in ./data_gsm/Z__C_RJTD_*_GSM_GPV_Rgl_FD*_grib2.bin; do
    if [ ! -f "$filepath" ]; then
        continue
    fi
    filename=$(basename "$filepath")
    # ファイル名からパラメータを解析
    # 例: Z__C_RJTD_20171210120000_GSM_GPV_Rgl_FD0000_grib2.bin
    #     →  init_time=2017121012, ft=0000
    init_full=$(echo "$filename" | sed 's/Z__C_RJTD_\([0-9]*\)0000_GSM_GPV_Rgl_FD\([0-9]*\)_grib2.bin/\1/')
    ft=$(echo "$filename" | sed 's/Z__C_RJTD_\([0-9]*\)0000_GSM_GPV_Rgl_FD\([0-9]*\)_grib2.bin/\2/')
    init_time="${init_full:0:10}"

    python kurora_tenkizu.py "$init_time" "$ft"
    DRAWN=$((DRAWN + 1))
done

echo ""
echo "=== パイプライン完了: ${DRAWN}枚の天気図を作成 ==="
echo "出力先: $(pwd)/output/"
