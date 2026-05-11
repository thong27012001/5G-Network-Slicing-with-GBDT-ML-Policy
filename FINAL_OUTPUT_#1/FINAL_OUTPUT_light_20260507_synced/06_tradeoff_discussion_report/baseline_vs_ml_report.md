# Baseline vs ML Policy Report

## Run Summary

- Timestamp: `2026-05-05T10:17:37`
- Config: `slicesim\scenario-light-realistic-longterm.yml`
- Model: `models\gbdt_anyh_135`
- Controller type: `gbdt`
- Controller preset: `balanced_ml_v3_gentle`
- Broker enabled: `True`
- Broker preset: `forecasting_balanced`
- Seed: `42`

## Global KPI Comparison

| metric | baseline | ml_policy | delta_ml_minus_baseline | delta_pct |
|---|---|---|---|---|
| connected_clients_ratio | 0.7282 | 0.7253 | -0.0029 | -0.4006 |
| coverage_ratio | 0.9991 | 0.9994 | 0.0002 | 0.0208 |
| block_ratio | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| handover_ratio | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| avg_slice_load_ratio | 0.6702 | 0.7277 | 0.0575 | 8.5798 |
| total_bandwidth_usage | 315002560.0357 | 342029187.4267 | 27026627.3910 | 8.5798 |
| avg_latency_ms | 1.1228 | 1.1110 | -0.0118 | -1.0491 |
| p95_latency_ms | 9.2652 | 8.9960 | -0.2692 | -2.9059 |
| latency_violation_ratio | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| avg_state_sla_violation_share | 0.0025 | 0.0025 | 0.0000 | 0.0000 |
| bandwidth_jain_fairness | 0.3730 | 0.3696 | -0.0033 | -0.8895 |
| bandwidth_jain_fairness_min | 0.3333 | 0.3333 | 0.0000 | 0.0000 |

## Per-Slice Summary

| slice_name | avg_bandwidth_usage_mbps_baseline | avg_bandwidth_usage_mbps_ml | avg_bandwidth_usage_mbps_delta | avg_served_bandwidth_baseline | avg_served_bandwidth_ml | avg_served_bandwidth_delta | avg_completion_latency_ms_baseline | avg_completion_latency_ms_ml | avg_completion_latency_ms_delta | avg_first_service_latency_ms_baseline | avg_first_service_latency_ms_ml | avg_first_service_latency_ms_delta | avg_recorded_first_service_latency_ms_baseline | avg_recorded_first_service_latency_ms_ml | avg_recorded_first_service_latency_ms_delta | avg_bandwidth_share_baseline | avg_bandwidth_share_ml | avg_bandwidth_share_delta | zero_bandwidth_window_share_baseline | zero_bandwidth_window_share_ml | zero_bandwidth_window_share_delta | completion_ratio_baseline | completion_ratio_ml | completion_ratio_delta | completion_latency_violation_ratio_baseline | completion_latency_violation_ratio_ml | completion_latency_violation_ratio_delta | first_service_latency_violation_ratio_baseline | first_service_latency_violation_ratio_ml | first_service_latency_violation_ratio_delta | request_latency_violation_event_ratio_baseline | request_latency_violation_event_ratio_ml | request_latency_violation_event_ratio_delta | avg_state_sla_violation_share_baseline | avg_state_sla_violation_share_ml | avg_state_sla_violation_share_delta | avg_sla_safety_margin_baseline | avg_sla_safety_margin_ml | avg_sla_safety_margin_delta | avg_sla_safety_margin_improvement_pct |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| URLLC | 7.6016 | 7.6081 | 0.0065 | 140175.9772 | 139796.1922 | -379.7850 | 0.0624 | 0.0583 | -0.0041 | 0.0044 | 0.0030 | -0.0013 | 0.0044 | 0.0030 | -0.0013 | 0.0246 | 0.0227 | -0.0019 | 0.0000 | 0.0000 | 0.0000 | 0.9995 | 0.9995 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0025 | 0.0025 | 0.0000 | 0.2996 | 0.2398 | -0.0597 | -19.9425 |
| eMBB | 297.5251 | 324.5454 | 27.0203 | 159607.1204 | 176012.3592 | 16405.2387 | 10.2653 | 9.2558 | -1.0095 | 0.2366 | 0.2023 | -0.0343 | 0.2367 | 0.2024 | -0.0343 | 0.9441 | 0.9484 | 0.0044 | 0.0005 | 0.0005 | 0.0000 | 0.9494 | 0.9540 | 0.0046 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0025 | 0.0025 | 0.0000 | 0.3067 | 0.2476 | -0.0591 | -19.2737 |
| mMTC | 9.8758 | 9.8756 | -0.0001 | 79918.7901 | 80054.0418 | 135.2517 | 0.2608 | 0.2690 | 0.0081 | 0.1598 | 0.1626 | 0.0028 | 0.1599 | 0.1627 | 0.0028 | 0.0313 | 0.0289 | -0.0025 | 0.0005 | 0.0005 | 0.0000 | 0.9990 | 0.9990 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0025 | 0.0025 | 0.0000 | 0.3137 | 0.2552 | -0.0585 | -18.6477 |

## Per-Base-Station Summary

| base_station_id | avg_bandwidth_usage_mbps_baseline | avg_bandwidth_usage_mbps_ml | avg_bandwidth_usage_mbps_delta | avg_bandwidth_usage_mbps_delta_pct | avg_capacity_mbps_baseline | avg_capacity_mbps_ml | avg_capacity_mbps_delta | avg_capacity_mbps_delta_pct | avg_load_ratio_baseline | avg_load_ratio_ml | avg_load_ratio_delta | avg_load_ratio_delta_pct | avg_remaining_capacity_ratio_baseline | avg_remaining_capacity_ratio_ml | avg_remaining_capacity_ratio_delta | avg_remaining_capacity_ratio_delta_pct | avg_request_count_per_window_baseline | avg_request_count_per_window_ml | avg_request_count_per_window_delta | avg_request_count_per_window_delta_pct | total_request_count_baseline | total_request_count_ml | total_request_count_delta | total_request_count_delta_pct | avg_requested_usage_mbps_per_window_baseline | avg_requested_usage_mbps_per_window_ml | avg_requested_usage_mbps_per_window_delta | avg_requested_usage_mbps_per_window_delta_pct | avg_clients_seen_per_window_baseline | avg_clients_seen_per_window_ml | avg_clients_seen_per_window_delta | avg_clients_seen_per_window_delta_pct | avg_connected_events_per_window_baseline | avg_connected_events_per_window_ml | avg_connected_events_per_window_delta | avg_connected_events_per_window_delta_pct | avg_disconnected_events_per_window_baseline | avg_disconnected_events_per_window_ml | avg_disconnected_events_per_window_delta | avg_disconnected_events_per_window_delta_pct | avg_state_sla_violation_share_baseline | avg_state_sla_violation_share_ml | avg_state_sla_violation_share_delta | avg_state_sla_violation_share_delta_pct | avg_sla_safety_margin_baseline | avg_sla_safety_margin_ml | avg_sla_safety_margin_delta | avg_sla_safety_margin_delta_pct | avg_sla_breach_count_per_window_baseline | avg_sla_breach_count_per_window_ml | avg_sla_breach_count_per_window_delta | avg_sla_breach_count_per_window_delta_pct |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BS_0 | 51.4860 | 57.6427 | 6.1566 | 11.9579 | 80.0000 | 80.0000 | 0.0000 | 0.0000 | 0.6436 | 0.7205 | 0.0770 | 11.9579 | 0.3564 | 0.2795 | -0.0770 | -21.5917 | 25.7240 | 26.0100 | 0.2860 | 1.1118 | 51448.0000 | 52020.0000 | 572.0000 | 1.1118 | 52.8661 | 59.1976 | 6.3315 | 11.9765 | 427.2205 | 428.0345 | 0.8140 | 0.1905 | 25.7255 | 26.0135 | 0.2880 | 1.1195 | 25.5680 | 25.8490 | 0.2810 | 1.0990 | 0.0025 | 0.0025 | 0.0000 | 0.0000 | 0.3067 | 0.2476 | -0.0591 | -19.2780 | 0.0075 | 0.0075 | 0.0000 | 0.0000 |
| BS_1 | 43.9637 | 47.4219 | 3.4582 | 7.8660 | 65.0000 | 65.0000 | 0.0000 | 0.0000 | 0.6764 | 0.7296 | 0.0532 | 7.8660 | 0.3236 | 0.2704 | -0.0532 | -16.4393 | 28.2960 | 28.3790 | 0.0830 | 0.2933 | 56592.0000 | 56758.0000 | 166.0000 | 0.2933 | 45.4088 | 49.0606 | 3.6518 | 8.0421 | 430.0905 | 431.2830 | 1.1925 | 0.2773 | 28.2995 | 28.3815 | 0.0820 | 0.2898 | 28.1395 | 28.2225 | 0.0830 | 0.2950 | 0.0025 | 0.0025 | 0.0000 | 0.0000 | 0.3067 | 0.2476 | -0.0591 | -19.2780 | 0.0075 | 0.0075 | 0.0000 | 0.0000 |
| BS_2 | 44.0170 | 47.5022 | 3.4852 | 7.9180 | 65.0000 | 65.0000 | 0.0000 | 0.0000 | 0.6772 | 0.7308 | 0.0536 | 7.9180 | 0.3228 | 0.2692 | -0.0536 | -16.6098 | 29.5030 | 30.0640 | 0.5610 | 1.9015 | 59006.0000 | 60128.0000 | 1122.0000 | 1.9015 | 45.2910 | 49.0816 | 3.7906 | 8.3695 | 427.1625 | 428.8280 | 1.6655 | 0.3899 | 29.5330 | 30.0810 | 0.5480 | 1.8556 | 29.3810 | 29.9345 | 0.5535 | 1.8839 | 0.0025 | 0.0025 | 0.0000 | 0.0000 | 0.3067 | 0.2476 | -0.0591 | -19.2780 | 0.0075 | 0.0075 | 0.0000 | 0.0000 |
| BS_3 | 43.8012 | 47.3428 | 3.5416 | 8.0856 | 65.0000 | 65.0000 | 0.0000 | 0.0000 | 0.6739 | 0.7284 | 0.0545 | 8.0856 | 0.3261 | 0.2716 | -0.0545 | -16.7067 | 27.9020 | 28.1635 | 0.2615 | 0.9372 | 55804.0000 | 56327.0000 | 523.0000 | 0.9372 | 45.1624 | 48.8824 | 3.7200 | 8.2369 | 428.2905 | 428.1505 | -0.1400 | -0.0327 | 27.9085 | 28.1665 | 0.2580 | 0.9244 | 27.7520 | 28.0095 | 0.2575 | 0.9279 | 0.0025 | 0.0025 | 0.0000 | 0.0000 | 0.3067 | 0.2476 | -0.0591 | -19.2780 | 0.0075 | 0.0075 | 0.0000 | 0.0000 |
| BS_4 | 43.8852 | 47.1493 | 3.2641 | 7.4379 | 65.0000 | 65.0000 | 0.0000 | 0.0000 | 0.6752 | 0.7254 | 0.0502 | 7.4379 | 0.3248 | 0.2746 | -0.0502 | -15.4589 | 29.1350 | 29.3720 | 0.2370 | 0.8135 | 58270.0000 | 58744.0000 | 474.0000 | 0.8135 | 45.2971 | 48.9273 | 3.6302 | 8.0142 | 428.9820 | 428.9535 | -0.0285 | -0.0066 | 29.1355 | 29.3755 | 0.2400 | 0.8237 | 28.9745 | 29.2235 | 0.2490 | 0.8594 | 0.0025 | 0.0025 | 0.0000 | 0.0000 | 0.3067 | 0.2476 | -0.0591 | -19.2780 | 0.0075 | 0.0075 | 0.0000 | 0.0000 |
| BS_5 | 43.9891 | 47.5219 | 3.5327 | 8.0309 | 65.0000 | 65.0000 | 0.0000 | 0.0000 | 0.6768 | 0.7311 | 0.0543 | 8.0309 | 0.3232 | 0.2689 | -0.0543 | -16.8138 | 28.7140 | 28.7900 | 0.0760 | 0.2647 | 57428.0000 | 57580.0000 | 152.0000 | 0.2647 | 45.3213 | 49.1935 | 3.8722 | 8.5438 | 428.2285 | 424.8240 | -3.4045 | -0.7950 | 28.7155 | 28.7950 | 0.0795 | 0.2769 | 28.5635 | 28.6405 | 0.0770 | 0.2696 | 0.0025 | 0.0025 | 0.0000 | 0.0000 | 0.3067 | 0.2476 | -0.0591 | -19.2780 | 0.0075 | 0.0075 | 0.0000 | 0.0000 |
| BS_6 | 43.8603 | 47.4484 | 3.5881 | 8.1807 | 65.0000 | 65.0000 | 0.0000 | 0.0000 | 0.6748 | 0.7300 | 0.0552 | 8.1807 | 0.3252 | 0.2700 | -0.0552 | -16.9732 | 27.2090 | 27.5190 | 0.3100 | 1.1393 | 54418.0000 | 55038.0000 | 620.0000 | 1.1393 | 45.1901 | 48.9692 | 3.7791 | 8.3626 | 427.4735 | 427.9985 | 0.5250 | 0.1228 | 27.2105 | 27.5365 | 0.3260 | 1.1981 | 27.0560 | 27.3790 | 0.3230 | 1.1938 | 0.0025 | 0.0025 | 0.0000 | 0.0000 | 0.3067 | 0.2476 | -0.0591 | -19.2780 | 0.0075 | 0.0075 | 0.0000 | 0.0000 |

## Per-Base-Station Slice SLA Summary

| base_station_id | slice_name | avg_bandwidth_usage_mbps_baseline | avg_bandwidth_usage_mbps_ml | avg_bandwidth_usage_mbps_delta | avg_bandwidth_usage_mbps_delta_pct | avg_slice_capacity_mbps_baseline | avg_slice_capacity_mbps_ml | avg_slice_capacity_mbps_delta | avg_slice_capacity_mbps_delta_pct | avg_slice_load_ratio_baseline | avg_slice_load_ratio_ml | avg_slice_load_ratio_delta | avg_slice_load_ratio_delta_pct | avg_remaining_capacity_ratio_baseline | avg_remaining_capacity_ratio_ml | avg_remaining_capacity_ratio_delta | avg_remaining_capacity_ratio_delta_pct | avg_request_count_per_window_baseline | avg_request_count_per_window_ml | avg_request_count_per_window_delta | avg_request_count_per_window_delta_pct | total_request_count_baseline | total_request_count_ml | total_request_count_delta | total_request_count_delta_pct | avg_requested_usage_mbps_per_window_baseline | avg_requested_usage_mbps_per_window_ml | avg_requested_usage_mbps_per_window_delta | avg_requested_usage_mbps_per_window_delta_pct | avg_clients_seen_per_window_baseline | avg_clients_seen_per_window_ml | avg_clients_seen_per_window_delta | avg_clients_seen_per_window_delta_pct | avg_state_sla_violation_share_baseline | avg_state_sla_violation_share_ml | avg_state_sla_violation_share_delta | avg_state_sla_violation_share_delta_pct | avg_sla_safety_margin_baseline | avg_sla_safety_margin_ml | avg_sla_safety_margin_delta | avg_sla_safety_margin_delta_pct | avg_sla_breach_count_per_window_baseline | avg_sla_breach_count_per_window_ml | avg_sla_breach_count_per_window_delta | avg_sla_breach_count_per_window_delta_pct |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BS_0 | URLLC | 0.8880 | 0.8670 | -0.0209 | -2.3592 | 14.4000 | 15.9968 | 1.5968 | 11.0889 | 0.0617 | 0.0542 | -0.0075 | -12.1061 | 0.9383 | 0.9458 | 0.0075 | 0.7956 | 6.3485 | 6.2055 | -0.1430 | -2.2525 | 12697.0000 | 12411.0000 | -286.0000 | -2.2525 | 0.8880 | 0.8670 | -0.0209 | -2.3592 | 33.0000 | 32.5735 | -0.4265 | -1.2924 | 0.0025 | 0.0025 | 0.0000 | 0.0000 | 0.2996 | 0.2398 | -0.0597 | -19.9425 | 0.0025 | 0.0025 | 0.0000 | 0.0000 |
| BS_0 | eMBB | 49.2935 | 55.4681 | 6.1746 | 12.5262 | 49.6000 | 55.9714 | 6.3714 | 12.8455 | 0.9938 | 0.9910 | -0.0029 | -0.2886 | 0.0062 | 0.0090 | 0.0029 | 46.4227 | 3.1000 | 3.4625 | 0.3625 | 11.6935 | 6200.0000 | 6925.0000 | 725.0000 | 11.6935 | 50.6731 | 57.0226 | 6.3494 | 12.5302 | 294.9500 | 296.1685 | 1.2185 | 0.4131 | 0.0025 | 0.0025 | 0.0000 | 0.0000 | 0.3067 | 0.2476 | -0.0591 | -19.2737 | 0.0025 | 0.0025 | 0.0000 | 0.0000 |
| BS_0 | mMTC | 1.3045 | 1.3075 | 0.0030 | 0.2295 | 16.0000 | 8.0318 | -7.9682 | -49.8011 | 0.0815 | 0.1630 | 0.0814 | 99.8741 | 0.9185 | 0.8370 | -0.0814 | -8.8659 | 16.2755 | 16.3420 | 0.0665 | 0.4086 | 32551.0000 | 32684.0000 | 133.0000 | 0.4086 | 1.3050 | 1.3080 | 0.0030 | 0.2320 | 99.2705 | 99.2925 | 0.0220 | 0.0222 | 0.0025 | 0.0025 | 0.0000 | 0.0000 | 0.3137 | 0.2552 | -0.0585 | -18.6477 | 0.0025 | 0.0025 | 0.0000 | 0.0000 |
| BS_1 | URLLC | 1.2354 | 1.2352 | -0.0002 | -0.0148 | 10.4000 | 12.9948 | 2.5948 | 24.9500 | 0.1188 | 0.0951 | -0.0237 | -19.9667 | 0.8812 | 0.9049 | 0.0237 | 2.6915 | 8.8145 | 8.8070 | -0.0075 | -0.0851 | 17629.0000 | 17614.0000 | -15.0000 | -0.0851 | 1.2354 | 1.2352 | -0.0002 | -0.0148 | 44.0000 | 44.4250 | 0.4250 | 0.9659 | 0.0025 | 0.0025 | 0.0000 | 0.0000 | 0.2996 | 0.2398 | -0.0597 | -19.9425 | 0.0025 | 0.0025 | 0.0000 | 0.0000 |
| BS_1 | eMBB | 41.3774 | 44.8456 | 3.4682 | 8.3818 | 41.6000 | 45.4163 | 3.8163 | 9.1738 | 0.9947 | 0.9874 | -0.0073 | -0.7295 | 0.0053 | 0.0126 | 0.0073 | 135.6201 | 2.6175 | 2.8345 | 0.2170 | 8.2904 | 5235.0000 | 5669.0000 | 434.0000 | 8.2904 | 42.8218 | 46.4834 | 3.6616 | 8.5507 | 285.4730 | 286.1760 | 0.7030 | 0.2463 | 0.0025 | 0.0025 | 0.0000 | 0.0000 | 0.3067 | 0.2476 | -0.0591 | -19.2737 | 0.0025 | 0.0025 | 0.0000 | 0.0000 |
| BS_1 | mMTC | 1.3509 | 1.3411 | -0.0098 | -0.7254 | 13.0000 | 6.5889 | -6.4111 | -49.3161 | 0.1039 | 0.2038 | 0.0998 | 96.0760 | 0.8961 | 0.7962 | -0.0998 | -11.1416 | 16.8640 | 16.7375 | -0.1265 | -0.7501 | 33728.0000 | 33475.0000 | -253.0000 | -0.7501 | 1.3516 | 1.3420 | -0.0096 | -0.7095 | 100.6175 | 100.6820 | 0.0645 | 0.0641 | 0.0025 | 0.0025 | 0.0000 | 0.0000 | 0.3137 | 0.2552 | -0.0585 | -18.6477 | 0.0025 | 0.0025 | 0.0000 | 0.0000 |
| BS_2 | URLLC | 1.1623 | 1.1730 | 0.0107 | 0.9178 | 10.4000 | 12.9948 | 2.5948 | 24.9500 | 0.1118 | 0.0903 | -0.0215 | -19.2205 | 0.8882 | 0.9097 | 0.0215 | 2.4183 | 8.2710 | 8.3755 | 0.1045 | 1.2635 | 16542.0000 | 16751.0000 | 209.0000 | 1.2635 | 1.1623 | 1.1730 | 0.0107 | 0.9178 | 42.0000 | 42.0000 | 0.0000 | 0.0000 | 0.0025 | 0.0025 | 0.0000 | 0.0000 | 0.2996 | 0.2398 | -0.0597 | -19.9425 | 0.0025 | 0.0025 | 0.0000 | 0.0000 |
| BS_2 | eMBB | 41.3687 | 44.8158 | 3.4471 | 8.3326 | 41.6000 | 45.3551 | 3.7551 | 9.0266 | 0.9944 | 0.9881 | -0.0064 | -0.6406 | 0.0056 | 0.0119 | 0.0064 | 114.5933 | 2.6005 | 2.8400 | 0.2395 | 9.2098 | 5201.0000 | 5680.0000 | 479.0000 | 9.2098 | 42.6419 | 46.3944 | 3.7526 | 8.8002 | 269.0315 | 269.8280 | 0.7965 | 0.2961 | 0.0025 | 0.0025 | 0.0000 | 0.0000 | 0.3067 | 0.2476 | -0.0591 | -19.2737 | 0.0025 | 0.0025 | 0.0000 | 0.0000 |
| BS_2 | mMTC | 1.4859 | 1.5134 | 0.0275 | 1.8492 | 13.0000 | 6.6501 | -6.3499 | -48.8452 | 0.1143 | 0.2278 | 0.1135 | 99.3035 | 0.8857 | 0.7722 | -0.1135 | -12.8153 | 18.6315 | 18.8485 | 0.2170 | 1.1647 | 37263.0000 | 37697.0000 | 434.0000 | 1.1647 | 1.4868 | 1.5142 | 0.0274 | 1.8405 | 116.1310 | 117.0000 | 0.8690 | 0.7483 | 0.0025 | 0.0025 | 0.0000 | 0.0000 | 0.3137 | 0.2552 | -0.0585 | -18.6477 | 0.0025 | 0.0025 | 0.0000 | 0.0000 |
| BS_3 | URLLC | 0.9465 | 0.9444 | -0.0022 | -0.2285 | 10.4000 | 12.9948 | 2.5948 | 24.9500 | 0.0910 | 0.0727 | -0.0183 | -20.1477 | 0.9090 | 0.9273 | 0.0183 | 2.0173 | 6.7240 | 6.7700 | 0.0460 | 0.6841 | 13448.0000 | 13540.0000 | 92.0000 | 0.6841 | 0.9465 | 0.9444 | -0.0022 | -0.2285 | 35.0000 | 35.0000 | 0.0000 | 0.0000 | 0.0025 | 0.0025 | 0.0000 | 0.0000 | 0.2996 | 0.2398 | -0.0597 | -19.9425 | 0.0025 | 0.0025 | 0.0000 | 0.0000 |
| BS_3 | eMBB | 41.3714 | 44.9115 | 3.5401 | 8.5568 | 41.6000 | 45.3695 | 3.7695 | 9.0612 | 0.9945 | 0.9899 | -0.0046 | -0.4665 | 0.0055 | 0.0101 | 0.0046 | 84.4220 | 2.5665 | 2.8230 | 0.2565 | 9.9942 | 5133.0000 | 5646.0000 | 513.0000 | 9.9942 | 42.7317 | 46.4503 | 3.7187 | 8.7024 | 279.9825 | 279.1505 | -0.8320 | -0.2972 | 0.0025 | 0.0025 | 0.0000 | 0.0000 | 0.3067 | 0.2476 | -0.0591 | -19.2737 | 0.0025 | 0.0025 | 0.0000 | 0.0000 |
| BS_3 | mMTC | 1.4833 | 1.4870 | 0.0037 | 0.2490 | 13.0000 | 6.6357 | -6.3643 | -48.9558 | 0.1141 | 0.2243 | 0.1102 | 96.6210 | 0.8859 | 0.7757 | -0.1102 | -12.4446 | 18.6115 | 18.5705 | -0.0410 | -0.2203 | 37223.0000 | 37141.0000 | -82.0000 | -0.2203 | 1.4842 | 1.4877 | 0.0035 | 0.2340 | 113.3080 | 114.0000 | 0.6920 | 0.6107 | 0.0025 | 0.0025 | 0.0000 | 0.0000 | 0.3137 | 0.2552 | -0.0585 | -18.6477 | 0.0025 | 0.0025 | 0.0000 | 0.0000 |
| BS_4 | URLLC | 0.9218 | 0.9274 | 0.0056 | 0.6040 | 10.4000 | 12.9948 | 2.5948 | 24.9500 | 0.0886 | 0.0714 | -0.0173 | -19.4837 | 0.9114 | 0.9286 | 0.0173 | 1.8949 | 6.5435 | 6.6525 | 0.1090 | 1.6658 | 13087.0000 | 13305.0000 | 218.0000 | 1.6658 | 0.9218 | 0.9274 | 0.0056 | 0.6040 | 32.9175 | 33.0430 | 0.1255 | 0.3813 | 0.0025 | 0.0025 | 0.0000 | 0.0000 | 0.2996 | 0.2398 | -0.0597 | -19.9425 | 0.0025 | 0.0025 | 0.0000 | 0.0000 |
| BS_4 | eMBB | 41.3657 | 44.6293 | 3.2636 | 7.8897 | 41.6000 | 45.3232 | 3.7232 | 8.9500 | 0.9944 | 0.9847 | -0.0097 | -0.9770 | 0.0056 | 0.0153 | 0.0097 | 172.4932 | 2.5800 | 2.8275 | 0.2475 | 9.5930 | 5160.0000 | 5655.0000 | 495.0000 | 9.5930 | 42.7770 | 46.4068 | 3.6298 | 8.4854 | 274.9155 | 275.0010 | 0.0855 | 0.0311 | 0.0025 | 0.0025 | 0.0000 | 0.0000 | 0.3067 | 0.2476 | -0.0591 | -19.2737 | 0.0025 | 0.0025 | 0.0000 | 0.0000 |
| BS_4 | mMTC | 1.5977 | 1.5926 | -0.0051 | -0.3185 | 13.0000 | 6.6820 | -6.3180 | -48.5999 | 0.1229 | 0.2386 | 0.1157 | 94.1670 | 0.8771 | 0.7614 | -0.1157 | -13.1945 | 20.0115 | 19.8920 | -0.1195 | -0.5972 | 40023.0000 | 39784.0000 | -239.0000 | -0.5972 | 1.5983 | 1.5931 | -0.0052 | -0.3223 | 121.1490 | 120.9095 | -0.2395 | -0.1977 | 0.0025 | 0.0025 | 0.0000 | 0.0000 | 0.3137 | 0.2552 | -0.0585 | -18.6477 | 0.0025 | 0.0025 | 0.0000 | 0.0000 |
| BS_5 | URLLC | 1.2551 | 1.2675 | 0.0124 | 0.9850 | 10.4000 | 12.9948 | 2.5948 | 24.9500 | 0.1207 | 0.0976 | -0.0231 | -19.1660 | 0.8793 | 0.9024 | 0.0231 | 2.6306 | 9.0325 | 9.0740 | 0.0415 | 0.4595 | 18065.0000 | 18148.0000 | 83.0000 | 0.4595 | 1.2551 | 1.2675 | 0.0124 | 0.9850 | 46.0000 | 45.9570 | -0.0430 | -0.0935 | 0.0025 | 0.0025 | 0.0000 | 0.0000 | 0.2996 | 0.2398 | -0.0597 | -19.9425 | 0.0025 | 0.0025 | 0.0000 | 0.0000 |
| BS_5 | eMBB | 41.3661 | 44.9095 | 3.5434 | 8.5660 | 41.6000 | 45.4148 | 3.8148 | 9.1703 | 0.9944 | 0.9888 | -0.0055 | -0.5576 | 0.0056 | 0.0112 | 0.0055 | 98.6020 | 2.5795 | 2.8365 | 0.2570 | 9.9632 | 5159.0000 | 5673.0000 | 514.0000 | 9.9632 | 42.6976 | 46.5804 | 3.8828 | 9.0938 | 275.4600 | 273.2725 | -2.1875 | -0.7941 | 0.0025 | 0.0025 | 0.0000 | 0.0000 | 0.3067 | 0.2476 | -0.0591 | -19.2737 | 0.0025 | 0.0025 | 0.0000 | 0.0000 |
| BS_5 | mMTC | 1.3679 | 1.3449 | -0.0231 | -1.6856 | 13.0000 | 6.5904 | -6.4096 | -49.3048 | 0.1052 | 0.2042 | 0.0990 | 94.0594 | 0.8948 | 0.7958 | -0.0990 | -11.0614 | 17.1020 | 16.8795 | -0.2225 | -1.3010 | 34204.0000 | 33759.0000 | -445.0000 | -1.3010 | 1.3686 | 1.3456 | -0.0230 | -1.6811 | 106.7685 | 105.5945 | -1.1740 | -1.0996 | 0.0025 | 0.0025 | 0.0000 | 0.0000 | 0.3137 | 0.2552 | -0.0585 | -18.6477 | 0.0025 | 0.0025 | 0.0000 | 0.0000 |
| BS_6 | URLLC | 1.1925 | 1.1937 | 0.0012 | 0.0995 | 10.4000 | 12.9948 | 2.5948 | 24.9500 | 0.1147 | 0.0919 | -0.0228 | -19.8862 | 0.8853 | 0.9081 | 0.0228 | 2.5755 | 8.4935 | 8.5390 | 0.0455 | 0.5357 | 16987.0000 | 17078.0000 | 91.0000 | 0.5357 | 1.1925 | 1.1937 | 0.0012 | 0.0995 | 42.6435 | 43.0000 | 0.3565 | 0.8360 | 0.0025 | 0.0025 | 0.0000 | 0.0000 | 0.2996 | 0.2398 | -0.0597 | -19.9425 | 0.0025 | 0.0025 | 0.0000 | 0.0000 |
| BS_6 | eMBB | 41.3823 | 44.9656 | 3.5833 | 8.6589 | 41.6000 | 45.4344 | 3.8344 | 9.2173 | 0.9948 | 0.9896 | -0.0051 | -0.5155 | 0.0052 | 0.0104 | 0.0051 | 97.9862 | 2.5760 | 2.8310 | 0.2550 | 9.8991 | 5152.0000 | 5662.0000 | 510.0000 | 9.8991 | 42.7114 | 46.4859 | 3.7745 | 8.8373 | 285.3505 | 284.9030 | -0.4475 | -0.1568 | 0.0025 | 0.0025 | 0.0000 | 0.0000 | 0.3067 | 0.2476 | -0.0591 | -19.2737 | 0.0025 | 0.0025 | 0.0000 | 0.0000 |
| BS_6 | mMTC | 1.2855 | 1.2892 | 0.0036 | 0.2828 | 13.0000 | 6.5708 | -6.4292 | -49.4552 | 0.0989 | 0.1963 | 0.0974 | 98.5444 | 0.9011 | 0.8037 | -0.0974 | -10.8141 | 16.1395 | 16.1490 | 0.0095 | 0.0589 | 32279.0000 | 32298.0000 | 19.0000 | 0.0589 | 1.2863 | 1.2896 | 0.0034 | 0.2616 | 99.4795 | 100.0955 | 0.6160 | 0.6192 | 0.0025 | 0.0025 | 0.0000 | 0.0000 | 0.3137 | 0.2552 | -0.0585 | -18.6477 | 0.0025 | 0.0025 | 0.0000 | 0.0000 |

## Resource Allocation Summary

| slice_name | baseline_state_ratio | ml_state_ratio | ml_action_target_ratio_mean | ml_action_target_ratio_min | ml_action_target_ratio_max | ml_scheduling_weight_mean | ml_admission_guard_factor_mean | target_ratio_delta_vs_baseline_state |
|---|---|---|---|---|---|---|---|---|
| URLLC | 0.1629 | 0.1999 | 0.2000 | 0.2000 | 0.2000 | 2.7931 | 1.1485 | 0.0371 |
| eMBB | 0.6371 | 0.6984 | 0.6986 | 0.6588 | 0.7000 | 1.3345 | 1.0424 | 0.0614 |
| mMTC | 0.2000 | 0.1016 | 0.1014 | 0.1000 | 0.1412 | 0.9734 | 1.0061 | -0.0986 |

## Visual Comparison

### Global KPI View

![Global KPI comparison](baseline_vs_ml_global_kpis.png)

### Per-Slice View

![Per-slice comparison](baseline_vs_ml_per_slice_bars.png)

### Per-Slice Panel Images

#### Throughput per Slice

![Throughput per Slice](baseline_vs_ml_per_slice_bars_throughput.png)
#### Latency per Slice

![Latency per Slice](baseline_vs_ml_per_slice_bars_latency.png)
#### Completion Ratio

![Completion Ratio](baseline_vs_ml_per_slice_bars_completion_ratio.png)
#### SLA Safety Margin Improvement

![SLA Safety Margin Improvement](baseline_vs_ml_per_slice_bars_sla_margin_improvement.png)
#### Improvement Heatmap

![Improvement Heatmap](baseline_vs_ml_per_slice_bars_improvement_heatmap.png)

### Per-Slice Time-Series View

![Per-slice time-series comparison](baseline_vs_ml_timeseries.png)

### ML Action Distribution

![ML action distribution](ml_action_distribution.png)

## Metric Notes

- `avg_state_sla_violation_share` is the per-slice state-level SLA violation ratio averaged from simulator state frames.
- `avg_sla_safety_margin` is the average distance to the active SLA boundary. Higher is better; negative means violation.
- `avg_sla_safety_margin_improvement_pct` is `(ML margin - baseline margin) / abs(baseline margin) * 100`.
- `request_latency_violation_event_ratio`, `completion_latency_violation_ratio`, and `first_service_latency_violation_ratio` are client-level latency-only metrics.
- A latency value of `0` can mean no recorded latency event for that slice/window. Check `completion_ratio` and request/completion counts before interpreting it as perfect latency.
- `bandwidth_jain_fairness` is Jain's fairness index over per-slice bandwidth usage per time window. Higher is more balanced, with `1.0` meaning equal usage across slices.

## Trade-off Notes

- URLLC completion latency changed by -0.00 ms and SLA safety margin changed by -0.0597 (-19.9%).
- eMBB average bandwidth usage changed by 27.020 Mbps and completion ratio changed by 0.0046.
- mMTC first-service latency changed by 0.00 ms and completion ratio changed by 0.0000.
- URLLC recorded first-service latency changed by -0.00 ms on windows with actual first-service events.
- Classic trade-off snapshot: if URLLC improved by 0.00 ms in latency, eMBB bandwidth moved by 27.020 Mbps.

## Artifacts

- Baseline raw states: `artifacts\comparisons\e2e_light_longterm_2026_05_05\baseline_run\baseline_states.csv`
- ML raw states: `artifacts\comparisons\e2e_light_longterm_2026_05_05\ml_run\online_states_raw.csv`
- ML broker forecasts: `artifacts\comparisons\e2e_light_longterm_2026_05_05\ml_run\online_broker_forecasts.csv`
- ML broker feedback: `artifacts\comparisons\e2e_light_longterm_2026_05_05\ml_run\online_broker_feedback.csv`
- Comparison CSV (global): `artifacts\comparisons\e2e_light_longterm_2026_05_05\global_kpi_comparison.csv`
- Comparison CSV (per-slice): `artifacts\comparisons\e2e_light_longterm_2026_05_05\per_slice_comparison.csv`
- Comparison CSV (per-base-station): `artifacts\comparisons\e2e_light_longterm_2026_05_05\per_base_station_comparison.csv`
- Comparison CSV (per-base-station-slice): `artifacts\comparisons\e2e_light_longterm_2026_05_05\per_base_station_slice_comparison.csv`
- Resource allocation CSV: `artifacts\comparisons\e2e_light_longterm_2026_05_05\resource_allocation_summary.csv`
- ML action time-series CSV: `artifacts\comparisons\e2e_light_longterm_2026_05_05\ml_action_ratio_timeseries.csv`
- Global KPI plot: `artifacts\comparisons\e2e_light_longterm_2026_05_05\baseline_vs_ml_global_kpis.png`
- Per-slice bar plot: `artifacts\comparisons\e2e_light_longterm_2026_05_05\baseline_vs_ml_per_slice_bars.png`
- Per-slice vector plot (SVG): `artifacts\comparisons\e2e_light_longterm_2026_05_05\baseline_vs_ml_per_slice_bars.svg`
- Per-slice panel plot (Throughput per Slice): `artifacts\comparisons\e2e_light_longterm_2026_05_05\baseline_vs_ml_per_slice_bars_throughput.png`
- Per-slice panel plot (Latency per Slice): `artifacts\comparisons\e2e_light_longterm_2026_05_05\baseline_vs_ml_per_slice_bars_latency.png`
- Per-slice panel plot (Completion Ratio): `artifacts\comparisons\e2e_light_longterm_2026_05_05\baseline_vs_ml_per_slice_bars_completion_ratio.png`
- Per-slice panel plot (SLA Safety Margin Improvement): `artifacts\comparisons\e2e_light_longterm_2026_05_05\baseline_vs_ml_per_slice_bars_sla_margin_improvement.png`
- Per-slice panel plot (Improvement Heatmap): `artifacts\comparisons\e2e_light_longterm_2026_05_05\baseline_vs_ml_per_slice_bars_improvement_heatmap.png`
- Per-slice time-series plot: `artifacts\comparisons\e2e_light_longterm_2026_05_05\baseline_vs_ml_timeseries.png`
- ML action distribution plot: `artifacts\comparisons\e2e_light_longterm_2026_05_05\ml_action_distribution.png`
