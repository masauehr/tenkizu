# tenkizu — TODO

## 現在の状態

主要スクリプトの作成は完了。今後は必要に応じて追加・改修を行う。

---

## 完了済み

- [x] `GSM_tenkizu500hPa.py` — 500hPa 高度・渦度・H/L スタンプ（2026-04-09）
- [x] `GSM_QVector850hPa.py` — 850hPa Q ベクター発散・気温・高度（2026-04-09）
- [x] `GSM_Jet300hPa.py` — 300hPa ジェット・非地衡風・発散（2026-04-09）
- [x] `GSM_Instability.py` — 不安定域分布（SEPT−maxEPT・上層気温）（2026-04-09）
- [x] `GSM_CrossSection.py` — 鉛直断面図（2026-04-09）
- [x] `ECM_EPT850hPa.py` — ECMWF 850hPa 相当温位・風（2026-04-09）
- [x] `ECM_Fax57.py` — ECMWF FAX57 500hPa気温・700hPa湿数（2026-04-09）
- [x] `ECM_Fax78.py` — ECMWF FAX78 700hPa収束・発散・850hPa気温・風（2026-04-09）
- [x] `ECM_SurfacePressure.py` — ECMWF 地上気圧・風・2m気温（2026-04-09）
- [x] `run_all_charts.sh` — 全スクリプト一括実行（2026-04-09）
- [x] 全スクリプトの引数省略対応（start_ft・n_steps デフォルト化）（2026-04-09）
- [x] 一括スクリプトの引数順を個別スクリプトと統一（2026-04-09）
- [x] `GSM_EPT850hPa.py` — GSM 850hPa 相当温位シェード・等値線・風矢羽（2026-04-13）
- [x] `ECM_tenkizu500hPa.py` — ECMWF 500hPa 等高度線・相対渦度・H/L スタンプ（2026-04-13）
- [x] GSM出力ファイル名にプレフィックス付与: `GSM_Fax57.png` / `GSM_Fax78.png` / `GSM_SurfacePressure.png`（衝突回避）（2026-04-13）
- [x] ECM出力ファイル名にプレフィックス付与: `ECM_Fax57.png` / `ECM_Fax78.png` / `ECM_SurfacePressure.png` / `ECM_850hPa_EPT.png`（2026-04-13）
- [x] `run_all_charts.sh` に GSM_EPT850hPa.py・ECM_tenkizu500hPa.py を追加（計14スクリプト）（2026-04-13）
- [x] `run_gsm_auto.py` のスクリプトリストに `GSM_EPT850hPa.py` を追加（2026-04-13）
- [x] `run_ecm_auto.py` のスクリプトリストに `ECM_tenkizu500hPa.py` を追加（2026-04-13）
- [x] `make_pptx.py` — PNG を PowerPoint に自動貼り付け（GSM/ECM、4:3スライド）（2026-04-13）
- [x] `make_pptx2.py` — 残り画像用 PPTX 生成スクリプト（300hPa_Jet/Fax57/Instability/EPT/CrossSection）（2026-04-13）
- [x] `samples/` — 全出力種別のサンプル画像を GitHub にアップロード（2026-04-13）
