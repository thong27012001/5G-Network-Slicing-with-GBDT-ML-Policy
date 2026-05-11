# Pipeline Output - heavy_seed7

Thư mục này gom artifact của một lần chạy end-to-end theo đúng luồng: mô phỏng, mô hình, KPI baseline, KPI ML, so sánh KPI và thảo luận trade-off.

## Cấu trúc

- `01_output_simulation`: dữ liệu thô từ baseline và ML run.
- `02_model_training_report_plot`: artifact mô hình, metadata và tóm tắt huấn luyện.
- `03_KPI_plot_output_with_baseline`: KPI của baseline.
- `04_KPI_plot_output_with_ML_Policy`: KPI/action/prediction của ML policy.
- `05_KPI_plot_output_comparison`: bảng và hình so sánh baseline vs ML.
- `06_tradeoff_discussion_report`: báo cáo nhận xét trade-off và guardrail.

## Tóm tắt nhanh

| KPI | Kết quả |
|---|---:|
| Total bandwidth delta | `6.22%` |
| Block ratio delta | `0.0000` |
| Connected clients delta | `-0.0007` |
| p95 latency delta | `2.12%` |
| State SLA share baseline -> ML | `0.0010 -> 0.0010` |
| eMBB completion delta | `0.0077` |
| URLLC completion latency delta | `-0.0057 ms` |

## Nguồn

- Comparison source: `C:\Users\LENOVO\Downloads\5G-Network-Slicing-main\5G-Network-Slicing-with-GBDT-ML-Policy\FINAL_OUTPUT_#1\FINAL_OUTPUT_heavy_seed7_20260508_015220`
- Model source: `C:\Users\LENOVO\Downloads\5G-Network-Slicing-main\5G-Network-Slicing-with-GBDT-ML-Policy\models\sla_risk_gbdt`
