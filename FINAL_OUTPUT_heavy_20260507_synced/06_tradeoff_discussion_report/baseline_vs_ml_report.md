# Baseline vs ML Policy Report

## Run Summary

- Timestamp: `2026-05-04T20:41:41`
- Config: `slicesim\scenario-heavy-realistic-longterm.yml`
- Model: `models\gbdt_anyh_135`
- Controller type: `gbdt`
- Controller preset: `balanced_ml_v3_gentle`
- Broker enabled: `True`
- Broker preset: `forecasting_balanced`
- Seed: `42`

## Global KPI Comparison

| metric | baseline | ml_policy | delta_ml_minus_baseline | delta_pct |
|---|---|---|---|---|
| connected_clients_ratio | 0.6198 | 0.6173 | -0.0025 | -0.4099 |
| coverage_ratio | 0.9997 | 0.9996 | -0.0001 | -0.0060 |
| block_ratio | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| handover_ratio | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| avg_slice_load_ratio | 0.6647 | 0.7251 | 0.0603 | 9.0750 |
| total_bandwidth_usage | 1675114727.2285 | 1827132086.2246 | 152017358.9961 | 9.0750 |
| avg_latency_ms | 1.4698 | 1.4656 | -0.0041 | -0.2821 |
| p95_latency_ms | 10.3583 | 11.4078 | 1.0495 | 10.1322 |
| latency_violation_ratio | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| avg_state_sla_violation_share | 0.0085 | 0.0090 | 0.0005 | 5.8824 |
| bandwidth_jain_fairness | 0.3651 | 0.3623 | -0.0028 | -0.7716 |
| bandwidth_jain_fairness_min | 0.3333 | 0.3333 | 0.0000 | 0.0000 |

## Per-Slice Summary

| slice_name | avg_bandwidth_usage_mbps_baseline | avg_bandwidth_usage_mbps_ml | avg_bandwidth_usage_mbps_delta | avg_served_bandwidth_baseline | avg_served_bandwidth_ml | avg_served_bandwidth_delta | avg_completion_latency_ms_baseline | avg_completion_latency_ms_ml | avg_completion_latency_ms_delta | avg_first_service_latency_ms_baseline | avg_first_service_latency_ms_ml | avg_first_service_latency_ms_delta | avg_recorded_first_service_latency_ms_baseline | avg_recorded_first_service_latency_ms_ml | avg_recorded_first_service_latency_ms_delta | avg_bandwidth_share_baseline | avg_bandwidth_share_ml | avg_bandwidth_share_delta | zero_bandwidth_window_share_baseline | zero_bandwidth_window_share_ml | zero_bandwidth_window_share_delta | completion_ratio_baseline | completion_ratio_ml | completion_ratio_delta | completion_latency_violation_ratio_baseline | completion_latency_violation_ratio_ml | completion_latency_violation_ratio_delta | first_service_latency_violation_ratio_baseline | first_service_latency_violation_ratio_ml | first_service_latency_violation_ratio_delta | request_latency_violation_event_ratio_baseline | request_latency_violation_event_ratio_ml | request_latency_violation_event_ratio_delta | avg_state_sla_violation_share_baseline | avg_state_sla_violation_share_ml | avg_state_sla_violation_share_delta | avg_sla_safety_margin_baseline | avg_sla_safety_margin_ml | avg_sla_safety_margin_delta | avg_sla_safety_margin_improvement_pct |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| URLLC | 29.3719 | 29.3140 | -0.0579 | 340240.9409 | 340281.7232 | 40.7823 | 0.0628 | 0.0586 | -0.0042 | 0.0049 | 0.0034 | -0.0015 | 0.0049 | 0.0034 | -0.0015 | 0.0180 | 0.0165 | -0.0015 | 0.0000 | 0.0000 | 0.0000 | 0.9995 | 0.9994 | -0.0001 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0085 | 0.0090 | 0.0005 | 0.1551 | 0.1495 | -0.0056 | -3.6392 |
| eMBB | 1599.6226 | 1751.7383 | 152.1157 | 387260.6397 | 427426.7876 | 40166.1479 | 20.3948 | 18.5501 | -1.8447 | 0.3928 | 0.3180 | -0.0748 | 0.3930 | 0.3182 | -0.0748 | 0.9545 | 0.9583 | 0.0038 | 0.0005 | 0.0005 | 0.0000 | 0.8988 | 0.9077 | 0.0089 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0085 | 0.0090 | 0.0005 | 0.1551 | 0.1495 | -0.0056 | -3.6392 |
| mMTC | 46.1202 | 46.0798 | -0.0404 | 224780.4222 | 225059.1691 | 278.7470 | 0.2850 | 0.2925 | 0.0075 | 0.1842 | 0.1873 | 0.0032 | 0.1843 | 0.1874 | 0.0032 | 0.0275 | 0.0252 | -0.0023 | 0.0005 | 0.0005 | 0.0000 | 0.9990 | 0.9990 | -0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0085 | 0.0090 | 0.0005 | 0.1551 | 0.1495 | -0.0056 | -3.6392 |

## Per-Base-Station Summary

| base_station_id | avg_bandwidth_usage_mbps_baseline | avg_bandwidth_usage_mbps_ml | avg_bandwidth_usage_mbps_delta | avg_bandwidth_usage_mbps_delta_pct | avg_capacity_mbps_baseline | avg_capacity_mbps_ml | avg_capacity_mbps_delta | avg_capacity_mbps_delta_pct | avg_load_ratio_baseline | avg_load_ratio_ml | avg_load_ratio_delta | avg_load_ratio_delta_pct | avg_remaining_capacity_ratio_baseline | avg_remaining_capacity_ratio_ml | avg_remaining_capacity_ratio_delta | avg_remaining_capacity_ratio_delta_pct | avg_request_count_per_window_baseline | avg_request_count_per_window_ml | avg_request_count_per_window_delta | avg_request_count_per_window_delta_pct | total_request_count_baseline | total_request_count_ml | total_request_count_delta | total_request_count_delta_pct | avg_requested_usage_mbps_per_window_baseline | avg_requested_usage_mbps_per_window_ml | avg_requested_usage_mbps_per_window_delta | avg_requested_usage_mbps_per_window_delta_pct | avg_clients_seen_per_window_baseline | avg_clients_seen_per_window_ml | avg_clients_seen_per_window_delta | avg_clients_seen_per_window_delta_pct | avg_connected_events_per_window_baseline | avg_connected_events_per_window_ml | avg_connected_events_per_window_delta | avg_connected_events_per_window_delta_pct | avg_disconnected_events_per_window_baseline | avg_disconnected_events_per_window_ml | avg_disconnected_events_per_window_delta | avg_disconnected_events_per_window_delta_pct | avg_state_sla_violation_share_baseline | avg_state_sla_violation_share_ml | avg_state_sla_violation_share_delta | avg_state_sla_violation_share_delta_pct | avg_sla_safety_margin_baseline | avg_sla_safety_margin_ml | avg_sla_safety_margin_delta | avg_sla_safety_margin_delta_pct | avg_sla_breach_count_per_window_baseline | avg_sla_breach_count_per_window_ml | avg_sla_breach_count_per_window_delta | avg_sla_breach_count_per_window_delta_pct |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BS_0 | 270.1668 | 302.9579 | 32.7911 | 12.1373 | 420.0000 | 420.0000 | 0.0000 | 0.0000 | 0.6433 | 0.7213 | 0.0781 | 12.1373 | 0.3567 | 0.2787 | -0.0781 | -21.8851 | 44.5055 | 44.7955 | 0.2900 | 0.6516 | 89011.0000 | 89591.0000 | 580.0000 | 0.6516 | 285.2832 | 319.3043 | 34.0212 | 11.9254 | 1071.1280 | 1069.5160 | -1.6120 | -0.1505 | 44.5085 | 44.7980 | 0.2895 | 0.6504 | 44.1765 | 44.4615 | 0.2850 | 0.6451 | 0.0085 | 0.0090 | 0.0005 | 5.8824 | 0.1551 | 0.1495 | -0.0056 | -3.6392 | 0.0255 | 0.0270 | 0.0015 | 5.8824 |
| BS_1 | 233.5160 | 253.4169 | 19.9009 | 8.5223 | 350.0000 | 350.0000 | 0.0000 | 0.0000 | 0.6672 | 0.7240 | 0.0569 | 8.5223 | 0.3328 | 0.2760 | -0.0569 | -17.0846 | 41.5750 | 41.6465 | 0.0715 | 0.1720 | 83150.0000 | 83293.0000 | 143.0000 | 0.1720 | 250.4637 | 270.0410 | 19.5772 | 7.8164 | 1071.3665 | 1071.2755 | -0.0910 | -0.0085 | 41.5930 | 41.6660 | 0.0730 | 0.1755 | 41.2405 | 41.3255 | 0.0850 | 0.2061 | 0.0085 | 0.0090 | 0.0005 | 5.8824 | 0.1551 | 0.1495 | -0.0056 | -3.6392 | 0.0255 | 0.0270 | 0.0015 | 5.8824 |
| BS_2 | 234.4877 | 254.2118 | 19.7241 | 8.4116 | 350.0000 | 350.0000 | 0.0000 | 0.0000 | 0.6700 | 0.7263 | 0.0564 | 8.4116 | 0.3300 | 0.2737 | -0.0564 | -17.0753 | 46.1070 | 46.5625 | 0.4555 | 0.9879 | 92214.0000 | 93125.0000 | 911.0000 | 0.9879 | 249.9311 | 270.2867 | 20.3556 | 8.1445 | 1070.4315 | 1071.1725 | 0.7410 | 0.0692 | 46.1220 | 46.5815 | 0.4595 | 0.9963 | 45.7960 | 46.2590 | 0.4630 | 1.0110 | 0.0085 | 0.0090 | 0.0005 | 5.8824 | 0.1551 | 0.1495 | -0.0056 | -3.6392 | 0.0255 | 0.0270 | 0.0015 | 5.8824 |
| BS_3 | 234.0230 | 253.8453 | 19.8222 | 8.4702 | 350.0000 | 350.0000 | 0.0000 | 0.0000 | 0.6686 | 0.7253 | 0.0566 | 8.4702 | 0.3314 | 0.2747 | -0.0566 | -17.0915 | 44.4370 | 44.6025 | 0.1655 | 0.3724 | 88874.0000 | 89205.0000 | 331.0000 | 0.3724 | 248.8804 | 269.5510 | 20.6706 | 8.3055 | 1070.9705 | 1070.8235 | -0.1470 | -0.0137 | 44.4415 | 44.6195 | 0.1780 | 0.4005 | 44.1045 | 44.2905 | 0.1860 | 0.4217 | 0.0085 | 0.0090 | 0.0005 | 5.8824 | 0.1551 | 0.1495 | -0.0056 | -3.6392 | 0.0255 | 0.0270 | 0.0015 | 5.8824 |
| BS_4 | 233.7215 | 253.7604 | 20.0389 | 8.5739 | 350.0000 | 350.0000 | 0.0000 | 0.0000 | 0.6678 | 0.7250 | 0.0573 | 8.5739 | 0.3322 | 0.2750 | -0.0573 | -17.2336 | 43.1875 | 43.0400 | -0.1475 | -0.3415 | 86375.0000 | 86080.0000 | -295.0000 | -0.3415 | 248.7481 | 270.3740 | 21.6258 | 8.6939 | 1071.4105 | 1072.5785 | 1.1680 | 0.1090 | 43.1955 | 43.0580 | -0.1375 | -0.3183 | 42.8540 | 42.7120 | -0.1420 | -0.3314 | 0.0085 | 0.0090 | 0.0005 | 5.8824 | 0.1551 | 0.1495 | -0.0056 | -3.6392 | 0.0255 | 0.0270 | 0.0015 | 5.8824 |
| BS_5 | 234.5033 | 254.3827 | 19.8794 | 8.4772 | 350.0000 | 350.0000 | 0.0000 | 0.0000 | 0.6700 | 0.7268 | 0.0568 | 8.4772 | 0.3300 | 0.2732 | -0.0568 | -17.2121 | 46.1990 | 46.2360 | 0.0370 | 0.0801 | 92398.0000 | 92472.0000 | 74.0000 | 0.0801 | 249.6627 | 269.1840 | 19.5213 | 7.8191 | 1070.9500 | 1070.0775 | -0.8725 | -0.0815 | 46.2060 | 46.2480 | 0.0420 | 0.0909 | 45.8835 | 45.9200 | 0.0365 | 0.0795 | 0.0085 | 0.0090 | 0.0005 | 5.8824 | 0.1551 | 0.1495 | -0.0056 | -3.6392 | 0.0255 | 0.0270 | 0.0015 | 5.8824 |
| BS_6 | 234.6964 | 254.5571 | 19.8607 | 8.4623 | 350.0000 | 350.0000 | 0.0000 | 0.0000 | 0.6706 | 0.7273 | 0.0567 | 8.4623 | 0.3294 | 0.2727 | -0.0567 | -17.2247 | 46.2925 | 46.6850 | 0.3925 | 0.8479 | 92585.0000 | 93370.0000 | 785.0000 | 0.8479 | 249.1826 | 271.0780 | 21.8954 | 8.7869 | 1071.1230 | 1071.4845 | 0.3615 | 0.0337 | 46.3140 | 46.6955 | 0.3815 | 0.8237 | 45.9925 | 46.3675 | 0.3750 | 0.8154 | 0.0085 | 0.0090 | 0.0005 | 5.8824 | 0.1551 | 0.1495 | -0.0056 | -3.6392 | 0.0255 | 0.0270 | 0.0015 | 5.8824 |

## Per-Base-Station Slice SLA Summary

| base_station_id | slice_name | avg_bandwidth_usage_mbps_baseline | avg_bandwidth_usage_mbps_ml | avg_bandwidth_usage_mbps_delta | avg_bandwidth_usage_mbps_delta_pct | avg_slice_capacity_mbps_baseline | avg_slice_capacity_mbps_ml | avg_slice_capacity_mbps_delta | avg_slice_capacity_mbps_delta_pct | avg_slice_load_ratio_baseline | avg_slice_load_ratio_ml | avg_slice_load_ratio_delta | avg_slice_load_ratio_delta_pct | avg_remaining_capacity_ratio_baseline | avg_remaining_capacity_ratio_ml | avg_remaining_capacity_ratio_delta | avg_remaining_capacity_ratio_delta_pct | avg_request_count_per_window_baseline | avg_request_count_per_window_ml | avg_request_count_per_window_delta | avg_request_count_per_window_delta_pct | total_request_count_baseline | total_request_count_ml | total_request_count_delta | total_request_count_delta_pct | avg_requested_usage_mbps_per_window_baseline | avg_requested_usage_mbps_per_window_ml | avg_requested_usage_mbps_per_window_delta | avg_requested_usage_mbps_per_window_delta_pct | avg_clients_seen_per_window_baseline | avg_clients_seen_per_window_ml | avg_clients_seen_per_window_delta | avg_clients_seen_per_window_delta_pct | avg_state_sla_violation_share_baseline | avg_state_sla_violation_share_ml | avg_state_sla_violation_share_delta | avg_state_sla_violation_share_delta_pct | avg_sla_safety_margin_baseline | avg_sla_safety_margin_ml | avg_sla_safety_margin_delta | avg_sla_safety_margin_delta_pct | avg_sla_breach_count_per_window_baseline | avg_sla_breach_count_per_window_ml | avg_sla_breach_count_per_window_delta | avg_sla_breach_count_per_window_delta_pct |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BS_0 | URLLC | 3.9647 | 3.9136 | -0.0512 | -1.2911 | 84.0000 | 84.0000 | 0.0000 | 0.0000 | 0.0472 | 0.0466 | -0.0006 | -1.2911 | 0.9528 | 0.9534 | 0.0006 | 0.0640 | 11.6130 | 11.4425 | -0.1705 | -1.4682 | 23226.0000 | 22885.0000 | -341.0000 | -1.4682 | 3.9647 | 3.9136 | -0.0512 | -1.2911 | 115.1885 | 113.9890 | -1.1995 | -1.0413 | 0.0085 | 0.0090 | 0.0005 | 5.8824 | 0.1551 | 0.1495 | -0.0056 | -3.6392 | 0.0085 | 0.0090 | 0.0005 | 5.8824 |
| BS_0 | eMBB | 259.5582 | 292.3792 | 32.8210 | 12.6449 | 260.4000 | 293.9017 | 33.5017 | 12.8655 | 0.9968 | 0.9948 | -0.0020 | -0.2011 | 0.0032 | 0.0052 | 0.0020 | 61.9994 | 3.3025 | 3.7290 | 0.4265 | 12.9145 | 6605.0000 | 7458.0000 | 853.0000 | 12.9145 | 274.6729 | 308.7220 | 34.0491 | 12.3962 | 625.3360 | 624.5195 | -0.8165 | -0.1306 | 0.0085 | 0.0090 | 0.0005 | 5.8824 | 0.1551 | 0.1495 | -0.0056 | -3.6392 | 0.0085 | 0.0090 | 0.0005 | 5.8824 |
| BS_0 | mMTC | 6.6438 | 6.6652 | 0.0213 | 0.3208 | 75.6000 | 42.0983 | -33.5017 | -44.3144 | 0.0879 | 0.1585 | 0.0706 | 80.3348 | 0.9121 | 0.8415 | -0.0706 | -7.7402 | 29.5900 | 29.6240 | 0.0340 | 0.1149 | 59180.0000 | 59248.0000 | 68.0000 | 0.1149 | 6.6455 | 6.6688 | 0.0233 | 0.3504 | 330.6035 | 331.0075 | 0.4040 | 0.1222 | 0.0085 | 0.0090 | 0.0005 | 5.8824 | 0.1551 | 0.1495 | -0.0056 | -3.6392 | 0.0085 | 0.0090 | 0.0005 | 5.8824 |
| BS_1 | URLLC | 4.2726 | 4.2782 | 0.0056 | 0.1300 | 63.0000 | 69.9860 | 6.9860 | 11.0889 | 0.0678 | 0.0611 | -0.0067 | -9.8636 | 0.9322 | 0.9389 | 0.0067 | 0.7176 | 12.5535 | 12.5630 | 0.0095 | 0.0757 | 25107.0000 | 25126.0000 | 19.0000 | 0.0757 | 4.2726 | 4.2782 | 0.0056 | 0.1300 | 128.2190 | 128.4830 | 0.2640 | 0.2059 | 0.0085 | 0.0090 | 0.0005 | 5.8824 | 0.1551 | 0.1495 | -0.0056 | -3.6392 | 0.0085 | 0.0090 | 0.0005 | 5.8824 |
| BS_1 | eMBB | 223.3819 | 243.2946 | 19.9127 | 8.9142 | 224.0000 | 244.9001 | 20.9001 | 9.3304 | 0.9972 | 0.9934 | -0.0038 | -0.3849 | 0.0028 | 0.0066 | 0.0038 | 139.0880 | 2.9160 | 3.1585 | 0.2425 | 8.3162 | 5832.0000 | 6317.0000 | 485.0000 | 8.3162 | 240.3267 | 259.9161 | 19.5894 | 8.1512 | 654.9865 | 653.9570 | -1.0295 | -0.1572 | 0.0085 | 0.0090 | 0.0005 | 5.8824 | 0.1551 | 0.1495 | -0.0056 | -3.6392 | 0.0085 | 0.0090 | 0.0005 | 5.8824 |
| BS_1 | mMTC | 5.8615 | 5.8441 | -0.0174 | -0.2963 | 63.0000 | 35.1139 | -27.8861 | -44.2637 | 0.0930 | 0.1666 | 0.0735 | 79.0415 | 0.9070 | 0.8334 | -0.0735 | -8.1083 | 26.1055 | 25.9250 | -0.1805 | -0.6914 | 52211.0000 | 51850.0000 | -361.0000 | -0.6914 | 5.8644 | 5.8467 | -0.0177 | -0.3025 | 288.1610 | 288.8355 | 0.6745 | 0.2341 | 0.0085 | 0.0090 | 0.0005 | 5.8824 | 0.1551 | 0.1495 | -0.0056 | -3.6392 | 0.0085 | 0.0090 | 0.0005 | 5.8824 |
| BS_2 | URLLC | 4.2656 | 4.2335 | -0.0321 | -0.7521 | 63.0000 | 69.9860 | 6.9860 | 11.0889 | 0.0677 | 0.0605 | -0.0072 | -10.6575 | 0.9323 | 0.9395 | 0.0072 | 0.7740 | 12.5170 | 12.4540 | -0.0630 | -0.5033 | 25034.0000 | 24908.0000 | -126.0000 | -0.5033 | 4.2656 | 4.2335 | -0.0321 | -0.7521 | 124.8845 | 124.9615 | 0.0770 | 0.0617 | 0.0085 | 0.0090 | 0.0005 | 5.8824 | 0.1551 | 0.1495 | -0.0056 | -3.6392 | 0.0085 | 0.0090 | 0.0005 | 5.8824 |
| BS_2 | eMBB | 223.3217 | 243.0166 | 19.6950 | 8.8191 | 224.0000 | 244.7200 | 20.7200 | 9.2500 | 0.9970 | 0.9930 | -0.0040 | -0.3986 | 0.0030 | 0.0070 | 0.0040 | 131.2403 | 2.8735 | 3.0790 | 0.2055 | 7.1516 | 5747.0000 | 6158.0000 | 411.0000 | 7.1516 | 238.7612 | 259.0881 | 20.3269 | 8.5135 | 599.4580 | 599.6250 | 0.1670 | 0.0279 | 0.0085 | 0.0090 | 0.0005 | 5.8824 | 0.1551 | 0.1495 | -0.0056 | -3.6392 | 0.0085 | 0.0090 | 0.0005 | 5.8824 |
| BS_2 | mMTC | 6.9004 | 6.9617 | 0.0612 | 0.8875 | 63.0000 | 35.2940 | -27.7060 | -43.9778 | 0.1095 | 0.1974 | 0.0879 | 80.2394 | 0.8905 | 0.8026 | -0.0879 | -9.8697 | 30.7165 | 31.0295 | 0.3130 | 1.0190 | 61433.0000 | 62059.0000 | 626.0000 | 1.0190 | 6.9043 | 6.9651 | 0.0608 | 0.8802 | 346.0890 | 346.5860 | 0.4970 | 0.1436 | 0.0085 | 0.0090 | 0.0005 | 5.8824 | 0.1551 | 0.1495 | -0.0056 | -3.6392 | 0.0085 | 0.0090 | 0.0005 | 5.8824 |
| BS_3 | URLLC | 3.9252 | 3.9301 | 0.0049 | 0.1249 | 63.0000 | 69.9860 | 6.9860 | 11.0889 | 0.0623 | 0.0562 | -0.0061 | -9.8636 | 0.9377 | 0.9438 | 0.0061 | 0.6554 | 11.5860 | 11.5435 | -0.0425 | -0.3668 | 23172.0000 | 23087.0000 | -85.0000 | -0.3668 | 3.9252 | 3.9301 | 0.0049 | 0.1249 | 117.0250 | 117.4215 | 0.3965 | 0.3388 | 0.0085 | 0.0090 | 0.0005 | 5.8824 | 0.1551 | 0.1495 | -0.0056 | -3.6392 | 0.0085 | 0.0090 | 0.0005 | 5.8824 |
| BS_3 | eMBB | 223.3606 | 243.1833 | 19.8227 | 8.8748 | 224.0000 | 244.7912 | 20.7912 | 9.2818 | 0.9971 | 0.9934 | -0.0038 | -0.3767 | 0.0029 | 0.0066 | 0.0038 | 131.5989 | 2.8960 | 3.1655 | 0.2695 | 9.3059 | 5792.0000 | 6331.0000 | 539.0000 | 9.3059 | 238.2154 | 258.8863 | 20.6709 | 8.6774 | 623.0915 | 622.9845 | -0.1070 | -0.0172 | 0.0085 | 0.0090 | 0.0005 | 5.8824 | 0.1551 | 0.1495 | -0.0056 | -3.6392 | 0.0085 | 0.0090 | 0.0005 | 5.8824 |
| BS_3 | mMTC | 6.7373 | 6.7319 | -0.0054 | -0.0799 | 63.0000 | 35.2228 | -27.7772 | -44.0908 | 0.1069 | 0.1913 | 0.0843 | 78.8443 | 0.8931 | 0.8087 | -0.0843 | -9.4413 | 29.9550 | 29.8935 | -0.0615 | -0.2053 | 59910.0000 | 59787.0000 | -123.0000 | -0.2053 | 6.7398 | 6.7347 | -0.0052 | -0.0766 | 330.8540 | 330.4175 | -0.4365 | -0.1319 | 0.0085 | 0.0090 | 0.0005 | 5.8824 | 0.1551 | 0.1495 | -0.0056 | -3.6392 | 0.0085 | 0.0090 | 0.0005 | 5.8824 |
| BS_4 | URLLC | 3.9608 | 3.9777 | 0.0169 | 0.4269 | 63.0000 | 69.9860 | 6.9860 | 11.0889 | 0.0629 | 0.0568 | -0.0060 | -9.5919 | 0.9371 | 0.9432 | 0.0060 | 0.6435 | 11.7220 | 11.7530 | 0.0310 | 0.2645 | 23444.0000 | 23506.0000 | 62.0000 | 0.2645 | 3.9608 | 3.9777 | 0.0169 | 0.4269 | 115.7125 | 116.0000 | 0.2875 | 0.2485 | 0.0085 | 0.0090 | 0.0005 | 5.8824 | 0.1551 | 0.1495 | -0.0056 | -3.6392 | 0.0085 | 0.0090 | 0.0005 | 5.8824 |
| BS_4 | eMBB | 223.3514 | 243.4728 | 20.1214 | 9.0089 | 224.0000 | 244.8607 | 20.8607 | 9.3128 | 0.9971 | 0.9943 | -0.0028 | -0.2822 | 0.0029 | 0.0057 | 0.0028 | 97.1860 | 2.9000 | 3.1875 | 0.2875 | 9.9138 | 5800.0000 | 6375.0000 | 575.0000 | 9.9138 | 238.3753 | 260.0830 | 21.7077 | 9.1065 | 638.4210 | 638.6950 | 0.2740 | 0.0429 | 0.0085 | 0.0090 | 0.0005 | 5.8824 | 0.1551 | 0.1495 | -0.0056 | -3.6392 | 0.0085 | 0.0090 | 0.0005 | 5.8824 |
| BS_4 | mMTC | 6.4093 | 6.3099 | -0.0994 | -1.5506 | 63.0000 | 35.1533 | -27.8467 | -44.2011 | 0.1017 | 0.1797 | 0.0779 | 76.5868 | 0.8983 | 0.8203 | -0.0779 | -8.6740 | 28.5655 | 28.0995 | -0.4660 | -1.6313 | 57131.0000 | 56199.0000 | -932.0000 | -1.6313 | 6.4120 | 6.3132 | -0.0988 | -1.5403 | 317.2770 | 317.8835 | 0.6065 | 0.1912 | 0.0085 | 0.0090 | 0.0005 | 5.8824 | 0.1551 | 0.1495 | -0.0056 | -3.6392 | 0.0085 | 0.0090 | 0.0005 | 5.8824 |
| BS_5 | URLLC | 4.3005 | 4.2939 | -0.0066 | -0.1525 | 63.0000 | 69.9860 | 6.9860 | 11.0889 | 0.0683 | 0.0614 | -0.0069 | -10.1190 | 0.9317 | 0.9386 | 0.0069 | 0.7413 | 12.6365 | 12.6025 | -0.0340 | -0.2691 | 25273.0000 | 25205.0000 | -68.0000 | -0.2691 | 4.3005 | 4.2939 | -0.0066 | -0.1525 | 124.6475 | 124.5035 | -0.1440 | -0.1155 | 0.0085 | 0.0090 | 0.0005 | 5.8824 | 0.1551 | 0.1495 | -0.0056 | -3.6392 | 0.0085 | 0.0090 | 0.0005 | 5.8824 |
| BS_5 | eMBB | 223.3104 | 243.2330 | 19.9227 | 8.9215 | 224.0000 | 244.7460 | 20.7460 | 9.2616 | 0.9969 | 0.9938 | -0.0031 | -0.3155 | 0.0031 | 0.0062 | 0.0031 | 102.1787 | 2.8900 | 3.1330 | 0.2430 | 8.4083 | 5780.0000 | 6266.0000 | 486.0000 | 8.4083 | 238.4673 | 258.0315 | 19.5641 | 8.2041 | 607.4575 | 608.4155 | 0.9580 | 0.1577 | 0.0085 | 0.0090 | 0.0005 | 5.8824 | 0.1551 | 0.1495 | -0.0056 | -3.6392 | 0.0085 | 0.0090 | 0.0005 | 5.8824 |
| BS_5 | mMTC | 6.8925 | 6.8557 | -0.0367 | -0.5332 | 63.0000 | 35.2680 | -27.7320 | -44.0190 | 0.1094 | 0.1945 | 0.0851 | 77.8107 | 0.8906 | 0.8055 | -0.0851 | -9.5586 | 30.6725 | 30.5005 | -0.1720 | -0.5608 | 61345.0000 | 61001.0000 | -344.0000 | -0.5608 | 6.8948 | 6.8586 | -0.0362 | -0.5257 | 338.8450 | 337.1585 | -1.6865 | -0.4977 | 0.0085 | 0.0090 | 0.0005 | 5.8824 | 0.1551 | 0.1495 | -0.0056 | -3.6392 | 0.0085 | 0.0090 | 0.0005 | 5.8824 |
| BS_6 | URLLC | 4.6824 | 4.6870 | 0.0045 | 0.0971 | 63.0000 | 69.9860 | 6.9860 | 11.0889 | 0.0743 | 0.0670 | -0.0073 | -9.8876 | 0.9257 | 0.9330 | 0.0073 | 0.7939 | 13.7025 | 13.7880 | 0.0855 | 0.6240 | 27405.0000 | 27576.0000 | 171.0000 | 0.6240 | 4.6824 | 4.6870 | 0.0045 | 0.0971 | 134.0560 | 134.0775 | 0.0215 | 0.0160 | 0.0085 | 0.0090 | 0.0005 | 5.8824 | 0.1551 | 0.1495 | -0.0056 | -3.6392 | 0.0085 | 0.0090 | 0.0005 | 5.8824 |
| BS_6 | eMBB | 223.3386 | 243.1588 | 19.8203 | 8.8745 | 224.0000 | 244.7966 | 20.7966 | 9.2842 | 0.9970 | 0.9933 | -0.0038 | -0.3790 | 0.0030 | 0.0067 | 0.0038 | 127.9669 | 2.9250 | 3.1325 | 0.2075 | 7.0940 | 5850.0000 | 6265.0000 | 415.0000 | 7.0940 | 237.8203 | 259.6774 | 21.8571 | 9.1906 | 607.8605 | 608.0235 | 0.1630 | 0.0268 | 0.0085 | 0.0090 | 0.0005 | 5.8824 | 0.1551 | 0.1495 | -0.0056 | -3.6392 | 0.0085 | 0.0090 | 0.0005 | 5.8824 |
| BS_6 | mMTC | 6.6754 | 6.7113 | 0.0359 | 0.5379 | 63.0000 | 35.2174 | -27.7826 | -44.0993 | 0.1060 | 0.1907 | 0.0847 | 79.9621 | 0.8940 | 0.8093 | -0.0847 | -9.4768 | 29.6650 | 29.7645 | 0.0995 | 0.3354 | 59330.0000 | 59529.0000 | 199.0000 | 0.3354 | 6.6798 | 6.7136 | 0.0338 | 0.5060 | 329.2065 | 329.3835 | 0.1770 | 0.0538 | 0.0085 | 0.0090 | 0.0005 | 5.8824 | 0.1551 | 0.1495 | -0.0056 | -3.6392 | 0.0085 | 0.0090 | 0.0005 | 5.8824 |

## Resource Allocation Summary

| slice_name | baseline_state_ratio | ml_state_ratio | ml_action_target_ratio_mean | ml_action_target_ratio_min | ml_action_target_ratio_max | ml_scheduling_weight_mean | ml_admission_guard_factor_mean | target_ratio_delta_vs_baseline_state |
|---|---|---|---|---|---|---|---|---|
| URLLC | 0.1829 | 0.2000 | 0.2000 | 0.2000 | 0.2000 | 2.3999 | 1.0483 | 0.0171 |
| eMBB | 0.6371 | 0.6995 | 0.6996 | 0.6690 | 0.7000 | 1.3432 | 1.0425 | 0.0625 |
| mMTC | 0.1800 | 0.1006 | 0.1004 | 0.1000 | 0.1310 | 0.9783 | 1.0064 | -0.0796 |

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

- URLLC completion latency changed by -0.00 ms and SLA safety margin changed by -0.0056 (-3.6%).
- eMBB average bandwidth usage changed by 152.116 Mbps and completion ratio changed by 0.0089.
- mMTC first-service latency changed by 0.00 ms and completion ratio changed by -0.0000.
- URLLC recorded first-service latency changed by -0.00 ms on windows with actual first-service events.
- Classic trade-off snapshot: if URLLC improved by 0.00 ms in latency, eMBB bandwidth moved by 152.116 Mbps.

## Artifacts

- Baseline raw states: `artifacts\comparisons\e2e_heavy_longterm_2026_05_04\baseline_run\baseline_states.csv`
- ML raw states: `artifacts\comparisons\e2e_heavy_longterm_2026_05_04\ml_run\online_states_raw.csv`
- ML broker forecasts: `artifacts\comparisons\e2e_heavy_longterm_2026_05_04\ml_run\online_broker_forecasts.csv`
- ML broker feedback: `artifacts\comparisons\e2e_heavy_longterm_2026_05_04\ml_run\online_broker_feedback.csv`
- Comparison CSV (global): `artifacts\comparisons\e2e_heavy_longterm_2026_05_04\global_kpi_comparison.csv`
- Comparison CSV (per-slice): `artifacts\comparisons\e2e_heavy_longterm_2026_05_04\per_slice_comparison.csv`
- Comparison CSV (per-base-station): `artifacts\comparisons\e2e_heavy_longterm_2026_05_04\per_base_station_comparison.csv`
- Comparison CSV (per-base-station-slice): `artifacts\comparisons\e2e_heavy_longterm_2026_05_04\per_base_station_slice_comparison.csv`
- Resource allocation CSV: `artifacts\comparisons\e2e_heavy_longterm_2026_05_04\resource_allocation_summary.csv`
- ML action time-series CSV: `artifacts\comparisons\e2e_heavy_longterm_2026_05_04\ml_action_ratio_timeseries.csv`
- Global KPI plot: `artifacts\comparisons\e2e_heavy_longterm_2026_05_04\baseline_vs_ml_global_kpis.png`
- Per-slice bar plot: `artifacts\comparisons\e2e_heavy_longterm_2026_05_04\baseline_vs_ml_per_slice_bars.png`
- Per-slice vector plot (SVG): `artifacts\comparisons\e2e_heavy_longterm_2026_05_04\baseline_vs_ml_per_slice_bars.svg`
- Per-slice panel plot (Throughput per Slice): `artifacts\comparisons\e2e_heavy_longterm_2026_05_04\baseline_vs_ml_per_slice_bars_throughput.png`
- Per-slice panel plot (Latency per Slice): `artifacts\comparisons\e2e_heavy_longterm_2026_05_04\baseline_vs_ml_per_slice_bars_latency.png`
- Per-slice panel plot (Completion Ratio): `artifacts\comparisons\e2e_heavy_longterm_2026_05_04\baseline_vs_ml_per_slice_bars_completion_ratio.png`
- Per-slice panel plot (SLA Safety Margin Improvement): `artifacts\comparisons\e2e_heavy_longterm_2026_05_04\baseline_vs_ml_per_slice_bars_sla_margin_improvement.png`
- Per-slice panel plot (Improvement Heatmap): `artifacts\comparisons\e2e_heavy_longterm_2026_05_04\baseline_vs_ml_per_slice_bars_improvement_heatmap.png`
- Per-slice time-series plot: `artifacts\comparisons\e2e_heavy_longterm_2026_05_04\baseline_vs_ml_timeseries.png`
- ML action distribution plot: `artifacts\comparisons\e2e_heavy_longterm_2026_05_04\ml_action_distribution.png`
