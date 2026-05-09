# Pipeline Output - heavy-realistic-longterm

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
| Total bandwidth delta | `9.08%` |
| Block ratio delta | `0.0000` |
| Connected clients delta | `-0.0025` |
| p95 latency delta | `10.13%` |
| State SLA share baseline -> ML | `0.0085 -> 0.0090` |
| eMBB completion delta | `0.0089` |
| URLLC completion latency delta | `-0.0042 ms` |

## Nguồn

- Comparison source: `C:\Users\LENOVO\Downloads\5G-Network-Slicing-main\5G-Network-Slicing-main\artifacts\comparisons\e2e_heavy_longterm_2026_05_04`
- Model source: `C:\Users\LENOVO\Downloads\5G-Network-Slicing-main\5G-Network-Slicing-main\models\gbdt_anyh_135`
