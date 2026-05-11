# 07 Model Report

This report describes the GBDT SLA-risk model used by the closed-loop ML policy.
The model is global to the artifact directory and does not retrain per simulation seed.

## Model Scope

- Model directory: `C:\Users\LENOVO\Downloads\5G-Network-Slicing-main\5G-Network-Slicing-with-GBDT-ML-Policy\models\sla_risk_gbdt`
- Model type: `multi_horizon_gbdt`
- Target mode: `any_in_horizon`
- Dataset version: `v2`
- Training scenarios: light-realistic (4200 rows), heavy-realistic (4200 rows)
- Total training rows recorded in manifest: `8400`
- Current simulation scenario context: `global`

## Overall Horizon Metrics

| horizon | target_column | blend_weight | accuracy | roc_auc | calibration |
| --- | --- | --- | --- | --- | --- |
| 1 | next_sla_violation_any_h1 | 0.1111 | 0.9545 | 0.9906 | isotonic |
| 3 | next_sla_violation_any_h3 | 0.3333 | 0.9798 | 0.9983 | isotonic |
| 5 | next_sla_violation_any_h5 | 0.5556 | 0.9949 | 0.9990 | isotonic |

Visual output: `roc_auc_accuracy_by_horizon.png`.

ROC curve output: `roc_curves_by_horizon.png`. The curve is regenerated from
the saved test split when the training dataset referenced by the model metadata
is available; the raw plotted points are exported to `roc_curve_points.csv`.

## Precision, Recall, F1, and Confusion Matrix

The per-slice metrics below are reconstructed from the threshold-tuning
confusion counts saved in each horizon metadata file.

| horizon | slice_name | threshold | support | precision | recall | f1 | tp | fp | fn | tn |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | URLLC | 0.2300 | 560 | 0.8169 | 0.9206 | 0.8657 | 406 | 91 | 35 | 28 |
| 1 | eMBB | 0.5000 | 1106 | N/A | N/A | N/A | 0 | 0 | 0 | 1106 |
| 1 | mMTC | 0.5000 | 1106 | N/A | N/A | N/A | 0 | 0 | 0 | 1106 |
| 3 | URLLC | 0.2000 | 560 | 0.9367 | 0.9581 | 0.9473 | 503 | 34 | 22 | 1 |
| 3 | eMBB | 0.5000 | 1106 | N/A | N/A | N/A | 0 | 0 | 0 | 1106 |
| 3 | mMTC | 0.5000 | 1106 | N/A | N/A | N/A | 0 | 0 | 0 | 1106 |
| 5 | URLLC | 0.3400 | 560 | 0.9750 | 1.0000 | 0.9873 | 546 | 14 | 0 | 0 |
| 5 | eMBB | 0.5000 | 1106 | N/A | N/A | N/A | 0 | 0 | 0 | 1106 |
| 5 | mMTC | 0.5000 | 1106 | N/A | N/A | N/A | 0 | 0 | 0 | 1106 |

Visual outputs: `precision_recall_f1_by_slice.png` and `confusion_matrices.png`.

## Diagnostic Event-Support Evaluation

The strict holdout split is still the official offline evaluation. However,
eMBB and mMTC positive samples appear only in the early warmup/event window of
the current training scenarios, so the tail holdout has zero positive rows for
those slices. This is why their strict precision/recall/F1 are `N/A`.

The table below is an additional diagnostic pass over the full labelled dataset
to confirm that the saved model can still recognize the available eMBB/mMTC
event rows. It is useful for sanity checking and report explanation, but it
should not be described as an independent holdout score.

| scope | horizon | slice_name | support | positive_rows | positive_rate | positive_time_min | positive_time_max | precision | recall | f1 | roc_auc |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| full_dataset_diagnostic | 1 | URLLC | 2744 | 1540 | 0.5612 | 3.0000 | 198.0000 | 0.7410 | 0.9773 | 0.8429 | 0.9690 |
| full_dataset_diagnostic | 1 | eMBB | 2744 | 98 | 0.0357 | 3.0000 | 15.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| full_dataset_diagnostic | 1 | mMTC | 2744 | 98 | 0.0357 | 3.0000 | 15.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| full_dataset_diagnostic | 3 | URLLC | 2744 | 1953 | 0.7117 | 3.0000 | 198.0000 | 0.8210 | 0.9887 | 0.8971 | 0.9772 |
| full_dataset_diagnostic | 3 | eMBB | 2744 | 98 | 0.0357 | 3.0000 | 15.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| full_dataset_diagnostic | 3 | mMTC | 2744 | 98 | 0.0357 | 3.0000 | 15.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| full_dataset_diagnostic | 5 | URLLC | 2744 | 2135 | 0.7781 | 3.0000 | 198.0000 | 0.8922 | 1.0000 | 0.9430 | 0.9960 |
| full_dataset_diagnostic | 5 | eMBB | 2744 | 98 | 0.0357 | 3.0000 | 15.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| full_dataset_diagnostic | 5 | mMTC | 2744 | 98 | 0.0357 | 3.0000 | 15.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |

Diagnostic visual outputs: `diagnostic_precision_recall_f1_by_slice.png` and
`diagnostic_confusion_matrices.png`.

## Feature Importance

Feature importance is extracted from the horizon-1 GBDT estimator.

| feature | importance |
| --- | --- |
| connected_clients_ratio | 0.2909 |
| clients_seen_lag3 | 0.2097 |
| clients_seen_lag2 | 0.1181 |
| clients_seen | 0.1140 |
| avg_latency_ms_lag3 | 0.0594 |
| clients_seen_lag1 | 0.0545 |
| avg_latency_ms_lag1 | 0.0330 |
| slice_name_URLLC | 0.0313 |
| avg_slice_load_ratio_delta_3 | 0.0238 |
| avg_latency_ms_lag2 | 0.0086 |

## Threshold and Controller Rule

- Threshold tuning is cost-aware per slice. FN/FP costs are stored in each `h*/metadata.json`.
- Decision thresholds are read from model metadata. If a slice does not define a threshold, the default is `0.5`.
- Multi-horizon inference blends submodel risks using the weights in `horizon_models.json`.
- Controller preset: `balanced_ml_v3_gentle`.
- Broker preset: `forecasting_balanced`.
- Runtime action schema: `target_ratio`, `scheduling_weight`, and `admission_guard_factor`.
- Below-threshold action scaling is stored in model metadata as `below_threshold_action_scale` when available.
- Detailed controller and broker parameters are exported to `controller_rule.md`,
  `controller_rule_parameters.csv`, and `broker_rule_parameters.csv`.

## Files

- `model_overall_metrics.csv`: accuracy and ROC-AUC by horizon.
- `roc_auc_accuracy_by_horizon.png`: visual summary of accuracy and ROC-AUC.
- `roc_curves_by_horizon.png`: ROC curve by prediction horizon with AUC in the legend.
- `roc_curve_points.csv`: FPR/TPR/threshold points used to draw the ROC curves.
- `model_evaluation_predictions.csv`: reconstructed test-fold labels and probabilities used for ROC.
- `model_per_slice_metrics.csv`: precision/recall/F1 and confusion counts by horizon and slice.
- `precision_recall_f1_by_slice.png`: visual summary of precision/recall/F1 by slice.
- `model_confusion_matrices.csv`: compact TP/FP/FN/TN table.
- `confusion_matrices.png`: visual confusion matrices by horizon and slice.
- `model_diagnostic_metrics.csv`: full-dataset diagnostic metrics with positive-support timing.
- `model_diagnostic_predictions.csv`: labels and probabilities used for diagnostic metrics.
- `diagnostic_precision_recall_f1_by_slice.png`: diagnostic precision/recall/F1 plot.
- `diagnostic_confusion_matrices.png`: diagnostic confusion matrices.
- `feature_importance_h1.csv`: full horizon-1 feature importance table.
- `feature_importance_top15.png`: top feature-importance plot.
- `controller_rule.md`: closed-loop controller and broker rule explanation.
- `controller_rule_parameters.csv`: exported controller preset parameters.
- `broker_rule_parameters.csv`: exported broker preset parameters.
