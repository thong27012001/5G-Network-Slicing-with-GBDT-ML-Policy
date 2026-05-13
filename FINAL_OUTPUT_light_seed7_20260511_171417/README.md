# Pipeline Output - light_seed7

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
| Total bandwidth delta | `7.21%` |
| Block ratio delta | `0.0000` |
| Connected clients delta | `-0.0004` |
| p95 latency delta | `16.99%` |
| State SLA share baseline -> ML | `0.0070 -> 0.0060` |
| eMBB completion delta | `0.0035` |
| URLLC completion latency delta | `-0.0047 ms` |

## Nguồn

- Comparison source: `C:\Users\Admin\5G-Network-Slicing-with-GBDT-ML-Policy\logs\raw_runs\raw_light_seed7_20260511_171417`
- Model source: `C:\Users\Admin\5G-Network-Slicing-with-GBDT-ML-Policy\models\sla_risk_gbdt`
