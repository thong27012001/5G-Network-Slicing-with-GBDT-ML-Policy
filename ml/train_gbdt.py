"""Các hàm hỗ trợ train GBDT baseline ở chế độ offline."""

from __future__ import annotations

from math import ceil
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from ml.feature_builder import build_training_frame
from ml.feature_schema import CATEGORICAL_FEATURE_COLUMNS, infer_model_feature_columns
from ml.model_registry import save_model_artifacts


DEFAULT_EXCLUDED_FEATURE_PREFIXES = ["current_sla_"]
DEFAULT_THRESHOLD_COSTS_BY_SLICE = {
    "URLLC": {"fn": 8.0, "fp": 1.0},
    "eMBB": {"fn": 3.0, "fp": 1.0},
    "mMTC": {"fn": 1.5, "fp": 2.0},
}


def effective_excluded_feature_prefixes(excluded_feature_prefixes: list[str] | None = None) -> list[str]:
    prefix_candidates = [*DEFAULT_EXCLUDED_FEATURE_PREFIXES, *(excluded_feature_prefixes or [])]
    prefixes: list[str] = []
    for prefix in prefix_candidates:
        prefix = str(prefix).strip()
        if prefix and prefix not in prefixes:
            prefixes.append(prefix)
    return prefixes


def build_pipeline(feature_columns: list[str], random_state: int = 42) -> Pipeline:
    categorical_columns = [col for col in CATEGORICAL_FEATURE_COLUMNS if col in feature_columns]
    numeric_columns = [col for col in feature_columns if col not in categorical_columns]

    preprocessor = ColumnTransformer(
        transformers=[
            (
                "cat",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("encoder", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                categorical_columns,
            ),
            (
                "num",
                Pipeline(steps=[("imputer", SimpleImputer(strategy="median"))]),
                numeric_columns,
            ),
        ]
    )

    model = GradientBoostingClassifier(
        random_state=random_state,
        n_estimators=120,
        learning_rate=0.05,
        max_depth=3,
        subsample=0.9,
    )

    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("gbdt", model),
        ]
    )


def filter_feature_columns(
    feature_columns: list[str],
    excluded_feature_prefixes: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    prefixes = effective_excluded_feature_prefixes(excluded_feature_prefixes)
    if not prefixes:
        return feature_columns, []

    kept_columns: list[str] = []
    dropped_columns: list[str] = []
    for column in feature_columns:
        if any(column.startswith(prefix) for prefix in prefixes):
            dropped_columns.append(column)
        else:
            kept_columns.append(column)

    if not kept_columns:
        raise ValueError("All model features were removed by excluded_feature_prefixes.")

    return kept_columns, dropped_columns


def _class_balanced_weights(y: pd.Series) -> pd.Series:
    labels = pd.Series(y)
    counts = labels.value_counts(dropna=False)
    class_count = max(len(counts), 1)
    total = max(len(labels), 1)
    weights_by_class = {label: total / (class_count * count) for label, count in counts.items() if count > 0}
    return labels.map(weights_by_class).fillna(1.0).astype(float)


def _effective_sample_weight(
    y: pd.Series,
    slice_priority_weight: pd.Series,
    mode: str = "class_balanced",
) -> pd.Series:
    mode = mode.lower().strip()
    base_weight = pd.Series(slice_priority_weight, index=y.index).fillna(1.0).astype(float)
    class_weight = _class_balanced_weights(y)

    if mode == "slice_priority":
        weight = base_weight
    elif mode == "class_balanced":
        weight = class_weight
    elif mode == "combined":
        weight = base_weight * class_weight
    else:
        raise ValueError("sample_weight_mode must be 'slice_priority', 'class_balanced', or 'combined'.")

    mean_weight = float(weight.mean())
    if mean_weight > 0:
        weight = weight / mean_weight
    return weight.astype(float)


def _build_transition_mask(
    dataset: pd.DataFrame,
    target_column: str,
    reference_column: str = "current_sla_violation",
) -> pd.Series:
    """Return a boolean Series flagging rows where the target differs from the reference label.

    For binary targets (e.g. `next_sla_violation` or `next_sla_violation_any_h{H}`),
    a transition row is one where `current_sla_violation != target`. These are the
    "anticipation" rows the model has the most signal to learn from; reweighting them
    avoids the GBDT defaulting to persistence (predict the current label).
    """
    if target_column not in dataset.columns:
        return pd.Series(False, index=dataset.index)
    if reference_column not in dataset.columns:
        return pd.Series(False, index=dataset.index)
    target = pd.to_numeric(dataset[target_column], errors="coerce").fillna(-1).astype(int)
    reference = pd.to_numeric(dataset[reference_column], errors="coerce").fillna(-1).astype(int)
    return (target != reference) & (target >= 0) & (reference >= 0)


def _apply_transition_multiplier(
    weights: pd.Series,
    transition_mask: pd.Series,
    multiplier: float,
) -> pd.Series:
    """Multiply weights of transition rows by `multiplier` and renormalize to mean 1.0."""
    if multiplier is None or float(multiplier) == 1.0:
        return weights
    multiplier = float(multiplier)
    if multiplier <= 0:
        raise ValueError("transition_weight_multiplier must be positive.")
    aligned_mask = transition_mask.reindex(weights.index, fill_value=False).astype(bool)
    adjusted = weights.copy().astype(float)
    adjusted.loc[aligned_mask] = adjusted.loc[aligned_mask] * multiplier
    mean_weight = float(adjusted.mean())
    if mean_weight > 0:
        adjusted = adjusted / mean_weight
    return adjusted


def _calibration_cv(y_train: pd.Series, requested_cv: int) -> int | None:
    if requested_cv <= 1:
        return None
    counts = pd.Series(y_train).value_counts()
    if counts.empty or len(counts) < 2:
        return None
    max_cv = int(counts.min())
    if max_cv < 2:
        return None
    return max(2, min(int(requested_cv), max_cv))


def _fit_model(
    pipeline: Pipeline,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    weight_train: pd.Series,
    calibration_method: str = "none",
    calibration_cv: int = 5,
):
    calibration_method = calibration_method.lower().strip()
    if calibration_method in {"none", "off", "false", ""}:
        pipeline.fit(X_train, y_train, gbdt__sample_weight=weight_train)
        return pipeline, {
            "enabled": False,
            "method": "none",
            "cv": None,
            "reason": "disabled",
        }

    if calibration_method not in {"sigmoid", "isotonic"}:
        raise ValueError("calibration_method must be one of: none, sigmoid, isotonic.")

    effective_cv = _calibration_cv(y_train, calibration_cv)
    if effective_cv is None:
        pipeline.fit(X_train, y_train, gbdt__sample_weight=weight_train)
        return pipeline, {
            "enabled": False,
            "method": calibration_method,
            "cv": None,
            "reason": "not_enough_samples_per_class",
        }

    calibrated = CalibratedClassifierCV(
        estimator=pipeline,
        method=calibration_method,
        cv=effective_cv,
    )
    calibrated.fit(X_train, y_train, gbdt__sample_weight=weight_train)
    return calibrated, {
        "enabled": True,
        "method": calibration_method,
        "cv": int(effective_cv),
        "reason": "ok",
    }


def _threshold_predictions(
    probabilities: pd.Series,
    slice_names: pd.Series,
    threshold_by_slice: dict[str, float],
    default_threshold: float = 0.5,
) -> np.ndarray:
    thresholds = slice_names.map(threshold_by_slice).fillna(default_threshold).astype(float)
    return (probabilities >= thresholds).astype(int).to_numpy()


def tune_thresholds_by_slice(
    y_true: pd.Series,
    y_prob: np.ndarray | pd.Series,
    slice_names: pd.Series | None = None,
    threshold_min: float = 0.20,
    threshold_max: float = 0.80,
    threshold_steps: int = 61,
    cost_by_slice: dict[str, dict[str, float]] | None = None,
) -> dict:
    y_true_series = pd.Series(y_true).astype(int).reset_index(drop=True)
    y_prob_series = pd.Series(y_prob, dtype=float).reset_index(drop=True)
    if slice_names is None:
        slice_series = pd.Series(["__global__"] * len(y_true_series))
    else:
        slice_series = pd.Series(slice_names).astype(str).reset_index(drop=True)

    thresholds = np.linspace(float(threshold_min), float(threshold_max), int(threshold_steps))
    costs = cost_by_slice or DEFAULT_THRESHOLD_COSTS_BY_SLICE
    result: dict[str, dict] = {}

    for slice_name in sorted(slice_series.dropna().unique()):
        mask = slice_series == slice_name
        y_slice = y_true_series[mask]
        p_slice = y_prob_series[mask]
        if y_slice.empty:
            continue

        cost_config = costs.get(str(slice_name), {"fn": 3.0, "fp": 1.0})
        fn_cost = float(cost_config.get("fn", 3.0))
        fp_cost = float(cost_config.get("fp", 1.0))
        candidates = []
        for threshold in thresholds:
            y_pred = p_slice >= threshold
            fn = int(((~y_pred) & (y_slice == 1)).sum())
            fp = int((y_pred & (y_slice == 0)).sum())
            tp = int((y_pred & (y_slice == 1)).sum())
            tn = int(((~y_pred) & (y_slice == 0)).sum())
            cost = fn_cost * fn + fp_cost * fp
            candidates.append((cost, abs(threshold - 0.5), threshold, fn, fp, tp, tn))

        cost, _, threshold, fn, fp, tp, tn = min(candidates, key=lambda item: (item[0], item[1]))
        result[str(slice_name)] = {
            "threshold": float(threshold),
            "cost": float(cost),
            "fn_cost": fn_cost,
            "fp_cost": fp_cost,
            "fn": int(fn),
            "fp": int(fp),
            "tp": int(tp),
            "tn": int(tn),
            "support": int(len(y_slice)),
        }

    threshold_by_slice = {
        slice_name: float(info["threshold"])
        for slice_name, info in result.items()
        if slice_name != "__global__"
    }
    return {
        "enabled": True,
        "threshold_min": float(threshold_min),
        "threshold_max": float(threshold_max),
        "threshold_steps": int(threshold_steps),
        "cost_by_slice": costs,
        "slices": result,
        "threshold_by_slice": threshold_by_slice,
        "default_threshold": float(result.get("__global__", {}).get("threshold", 0.5)),
    }


def _build_stratified_time_split(
    dataset: pd.DataFrame,
    target_column: str,
    test_size: float = 0.2,
    time_column: str = "time",
    scenario_column: str = "scenario_name",
    slice_column: str = "slice_name",
    min_positive_count_test: int = 8,
    min_positive_rate_test: float = 0.05,
    max_test_size_fraction: float = 0.40,
) -> tuple[pd.Index, pd.Index, dict]:
    """Per-(scenario, slice) time-aware split with a positive-rate guard.

    For each `(scenario_name, slice_name)` group, we cut the last `w` time windows
    into the test fold, where `w` is the smallest tail size such that:
      - test fold has at least `min_positive_count_test` positive rows AND
      - test positive rate >= `min_positive_rate_test`,
    bounded by `max_test_size_fraction`.

    If a group cannot meet the guard even at `max_test_size_fraction` (e.g. the slice
    has zero positives), we fall back to the requested `test_size` and flag the group
    as `degraded` in the split summary.
    """
    if time_column not in dataset.columns:
        raise ValueError(f"Stratified time split requires a '{time_column}' column.")
    if slice_column not in dataset.columns:
        raise ValueError(f"Stratified time split requires a '{slice_column}' column.")
    if target_column not in dataset.columns:
        raise ValueError(f"Stratified time split requires the target column '{target_column}'.")

    has_scenario = scenario_column in dataset.columns
    if has_scenario:
        group_keys = [scenario_column, slice_column]
    else:
        group_keys = [slice_column]

    train_index_parts: list[pd.Index] = []
    test_index_parts: list[pd.Index] = []
    summaries: list[dict] = []

    for keys, group in dataset.groupby(group_keys, sort=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        scenario_name = str(keys[0]) if has_scenario else "__global__"
        slice_name = str(keys[-1])

        unique_times = sorted(group[time_column].dropna().unique().tolist())
        total_windows = len(unique_times)
        if total_windows < 2:
            raise ValueError(
                f"Stratified split requires at least 2 distinct time values for "
                f"({scenario_name}, {slice_name})."
            )

        baseline_windows = max(1, ceil(total_windows * test_size))
        baseline_windows = min(baseline_windows, total_windows - 1)
        cap_windows = max(baseline_windows, ceil(total_windows * max_test_size_fraction))
        cap_windows = min(cap_windows, total_windows - 1)

        chosen_windows = baseline_windows
        guard_status = "ok_default"
        for tail in range(baseline_windows, cap_windows + 1):
            test_times = set(unique_times[-tail:])
            test_mask = group[time_column].isin(test_times)
            test_pos = int(group.loc[test_mask, target_column].sum())
            test_total = int(test_mask.sum())
            if test_total == 0:
                continue
            test_rate = test_pos / test_total
            if test_pos >= min_positive_count_test and test_rate >= min_positive_rate_test:
                chosen_windows = tail
                guard_status = "ok_stratified"
                break
        else:
            chosen_windows = cap_windows
            guard_status = "degraded_no_positive_in_tail"

        test_times_final = set(unique_times[-chosen_windows:])
        group_test = group[group[time_column].isin(test_times_final)]
        group_train = group[~group[time_column].isin(test_times_final)]

        if group_train.empty or group_test.empty:
            raise ValueError(
                f"Stratified split produced an empty partition for "
                f"({scenario_name}, {slice_name})."
            )

        train_index_parts.append(group_train.index)
        test_index_parts.append(group_test.index)
        summaries.append(
            {
                "scenario_name": scenario_name,
                "slice_name": slice_name,
                "guard_status": guard_status,
                "test_windows": int(chosen_windows),
                "total_windows": int(total_windows),
                "train_rows": int(len(group_train)),
                "test_rows": int(len(group_test)),
                "test_positive_rows": int(group_test[target_column].sum()),
                "test_positive_rate": float(
                    group_test[target_column].sum() / max(len(group_test), 1)
                ),
                "train_time_min": float(group_train[time_column].min()),
                "train_time_max": float(group_train[time_column].max()),
                "test_time_min": float(group_test[time_column].min()),
                "test_time_max": float(group_test[time_column].max()),
            }
        )

    train_index = train_index_parts[0]
    for part in train_index_parts[1:]:
        train_index = train_index.append(part)
    test_index = test_index_parts[0]
    for part in test_index_parts[1:]:
        test_index = test_index.append(part)

    split_info = {
        "split_strategy": "stratified_time",
        "grouping_columns": group_keys,
        "min_positive_count_test": int(min_positive_count_test),
        "min_positive_rate_test": float(min_positive_rate_test),
        "max_test_size_fraction": float(max_test_size_fraction),
        "test_size_baseline": float(test_size),
        "slice_summaries": summaries,
    }
    return train_index, test_index, split_info


def _build_time_based_split(
    dataset: pd.DataFrame,
    test_size: float = 0.2,
    time_column: str = "time",
    scenario_column: str = "scenario_name",
) -> tuple[pd.Index, pd.Index, dict]:
    if time_column not in dataset.columns:
        raise ValueError(f"Time-based split requires a '{time_column}' column.")

    grouping_column = scenario_column if scenario_column in dataset.columns else None
    grouped = dataset.groupby(grouping_column, sort=False) if grouping_column else [("__global__", dataset)]

    train_index_parts: list[pd.Index] = []
    test_index_parts: list[pd.Index] = []
    scenario_summaries: list[dict] = []

    for scenario_name, group in grouped:
        unique_times = sorted(group[time_column].dropna().unique().tolist())
        if len(unique_times) < 2:
            raise ValueError(
                f"Time-based split requires at least 2 distinct time values for group '{scenario_name}'."
            )

        requested_test_windows = max(1, ceil(len(unique_times) * test_size))
        requested_test_windows = min(requested_test_windows, len(unique_times) - 1)
        test_times = set(unique_times[-requested_test_windows:])
        group_test = group[group[time_column].isin(test_times)]
        group_train = group[~group[time_column].isin(test_times)]

        if group_train.empty or group_test.empty:
            raise ValueError(
                f"Time-based split produced an empty partition for group '{scenario_name}'. "
                f"Check the dataset density or reduce test_size."
            )

        train_index_parts.append(group_train.index)
        test_index_parts.append(group_test.index)
        scenario_summaries.append(
            {
                "scenario_name": "__global__" if grouping_column is None else str(scenario_name),
                "train_time_min": float(min(group_train[time_column])),
                "train_time_max": float(max(group_train[time_column])),
                "test_time_min": float(min(group_test[time_column])),
                "test_time_max": float(max(group_test[time_column])),
                "train_rows": int(len(group_train)),
                "test_rows": int(len(group_test)),
                "train_windows": int(group_train[time_column].nunique()),
                "test_windows": int(group_test[time_column].nunique()),
            }
        )

    train_index = train_index_parts[0]
    for part in train_index_parts[1:]:
        train_index = train_index.append(part)

    test_index = test_index_parts[0]
    for part in test_index_parts[1:]:
        test_index = test_index.append(part)

    split_info = {
        "split_strategy": "time",
        "grouping_column": grouping_column or "__global__",
        "scenario_summaries": scenario_summaries,
        "test_size": float(test_size),
    }
    return train_index, test_index, split_info


def print_top_feature_importances(model: Pipeline, top_n: int = 10) -> None:
    try:
        feature_names = model.named_steps["preprocessor"].get_feature_names_out()
        feature_importances = model.named_steps["gbdt"].feature_importances_
        model_name = "gbdt"
    except Exception:
        try:
            base_model = model.calibrated_classifiers_[0].estimator
            feature_names = base_model.named_steps["preprocessor"].get_feature_names_out()
            feature_importances = base_model.named_steps["gbdt"].feature_importances_
            model_name = "calibrated_gbdt_fold0"
        except Exception:
            print("\nFeature importance extraction is not available in this environment.")
            return

    try:
        importance_df = pd.DataFrame(
            {"feature": feature_names, "importance": feature_importances}
        ).sort_values("importance", ascending=False)
        print(f"\nTop feature importances ({model_name}):")
        print(importance_df.head(top_n).to_string(index=False))
    except Exception:
        print("\nFeature importance extraction is not available in this environment.")


def run_training(
    dataset: pd.DataFrame,
    target_column: str = "next_sla_violation",
    split_strategy: str = "time",
    test_size: float = 0.2,
    random_state: int = 42,
    time_column: str = "time",
    scenario_column: str = "scenario_name",
    excluded_feature_prefixes: list[str] | None = None,
    sample_weight_mode: str = "class_balanced",
    calibration_method: str = "none",
    calibration_cv: int = 5,
    tune_thresholds: bool = True,
    threshold_min: float = 0.20,
    threshold_max: float = 0.80,
    threshold_steps: int = 61,
    min_positive_count_test: int = 8,
    min_positive_rate_test: float = 0.05,
    max_test_size_fraction: float = 0.40,
    transition_weight_multiplier: float = 1.0,
    transition_reference_column: str = "current_sla_violation",
) -> dict:
    feature_columns = infer_model_feature_columns(dataset.columns.tolist())
    feature_columns, dropped_feature_columns = filter_feature_columns(
        feature_columns,
        excluded_feature_prefixes=excluded_feature_prefixes,
    )
    pipeline = build_pipeline(feature_columns, random_state=random_state)

    X = dataset[feature_columns]
    y = dataset[target_column]
    slice_priority_weight = dataset["sample_weight"] if "sample_weight" in dataset.columns else pd.Series(1.0, index=dataset.index)

    if split_strategy == "random":
        X_train, X_test, y_train, y_test, base_weight_train, base_weight_test = train_test_split(
            X,
            y,
            slice_priority_weight,
            test_size=test_size,
            random_state=random_state,
            stratify=y,
        )
        split_info = {
            "split_strategy": "random",
            "test_size": float(test_size),
            "random_state": int(random_state),
        }
    elif split_strategy == "time":
        train_index, test_index, split_info = _build_time_based_split(
            dataset,
            test_size=test_size,
            time_column=time_column,
            scenario_column=scenario_column,
        )
        X_train, X_test = X.loc[train_index], X.loc[test_index]
        y_train, y_test = y.loc[train_index], y.loc[test_index]
        base_weight_train, base_weight_test = slice_priority_weight.loc[train_index], slice_priority_weight.loc[test_index]
        split_info["random_state"] = int(random_state)
    elif split_strategy == "stratified_time":
        train_index, test_index, split_info = _build_stratified_time_split(
            dataset,
            target_column=target_column,
            test_size=test_size,
            time_column=time_column,
            scenario_column=scenario_column,
            min_positive_count_test=min_positive_count_test,
            min_positive_rate_test=min_positive_rate_test,
            max_test_size_fraction=max_test_size_fraction,
        )
        X_train, X_test = X.loc[train_index], X.loc[test_index]
        y_train, y_test = y.loc[train_index], y.loc[test_index]
        base_weight_train, base_weight_test = slice_priority_weight.loc[train_index], slice_priority_weight.loc[test_index]
        split_info["random_state"] = int(random_state)
    else:
        raise ValueError("split_strategy must be one of: 'random', 'time', 'stratified_time'")

    weight_train = _effective_sample_weight(y_train, base_weight_train, mode=sample_weight_mode)
    weight_test = _effective_sample_weight(y_test, base_weight_test, mode=sample_weight_mode)

    transition_info: dict = {
        "enabled": float(transition_weight_multiplier) != 1.0,
        "multiplier": float(transition_weight_multiplier),
        "reference_column": transition_reference_column,
        "transition_rows_train": 0,
        "transition_rate_train": 0.0,
    }
    if transition_info["enabled"]:
        transition_mask_full = _build_transition_mask(
            dataset,
            target_column=target_column,
            reference_column=transition_reference_column,
        )
        transition_mask_train = transition_mask_full.reindex(y_train.index, fill_value=False)
        transition_info["transition_rows_train"] = int(transition_mask_train.sum())
        transition_info["transition_rate_train"] = float(
            transition_mask_train.sum() / max(len(transition_mask_train), 1)
        )
        weight_train = _apply_transition_multiplier(
            weight_train,
            transition_mask_train,
            multiplier=transition_weight_multiplier,
        )
    model, calibration_info = _fit_model(
        pipeline,
        X_train,
        y_train,
        weight_train,
        calibration_method=calibration_method,
        calibration_cv=calibration_cv,
    )

    y_prob = model.predict_proba(X_test)[:, 1]
    threshold_info = {
        "enabled": False,
        "threshold_by_slice": {},
        "default_threshold": 0.5,
    }
    if tune_thresholds:
        slice_names = X_test["slice_name"] if "slice_name" in X_test.columns else None
        threshold_info = tune_thresholds_by_slice(
            y_test,
            y_prob,
            slice_names=slice_names,
            threshold_min=threshold_min,
            threshold_max=threshold_max,
            threshold_steps=threshold_steps,
        )
        if slice_names is not None:
            y_pred = _threshold_predictions(
                pd.Series(y_prob, index=X_test.index),
                slice_names,
                threshold_info["threshold_by_slice"],
                default_threshold=threshold_info["default_threshold"],
            )
        else:
            y_pred = (y_prob >= float(threshold_info["default_threshold"])).astype(int)
    else:
        y_pred = model.predict(X_test)
    report_text = classification_report(y_test, y_pred, digits=4, zero_division=0)
    report_dict = classification_report(y_test, y_pred, output_dict=True, zero_division=0)
    roc_auc = float("nan")
    if pd.Series(y_test).nunique() > 1:
        roc_auc = roc_auc_score(y_test, y_prob)

    return {
        "model": model,
        "feature_columns": feature_columns,
        "X_test": X_test,
        "y_test": y_test,
        "y_pred": y_pred,
        "y_prob": y_prob,
        "classification_report": report_text,
        "classification_report_dict": report_dict,
        "accuracy": accuracy_score(y_test, y_pred),
        "roc_auc": roc_auc,
        "test_sample_weight": weight_test,
        "sample_weight_mode": sample_weight_mode,
        "calibration_info": calibration_info,
        "threshold_info": threshold_info,
        "transition_info": transition_info,
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "split_info": split_info,
        "dropped_feature_columns": dropped_feature_columns,
        "excluded_feature_prefixes": effective_excluded_feature_prefixes(excluded_feature_prefixes),
    }


def train_and_save(
    dataset: pd.DataFrame,
    model_dir,
    target_column: str = "next_sla_violation",
    metadata: dict | None = None,
    split_strategy: str = "time",
    test_size: float = 0.2,
    random_state: int = 42,
    time_column: str = "time",
    scenario_column: str = "scenario_name",
    excluded_feature_prefixes: list[str] | None = None,
    sample_weight_mode: str = "class_balanced",
    calibration_method: str = "none",
    calibration_cv: int = 5,
    tune_thresholds: bool = True,
    threshold_min: float = 0.20,
    threshold_max: float = 0.80,
    threshold_steps: int = 61,
    min_positive_count_test: int = 8,
    min_positive_rate_test: float = 0.05,
    max_test_size_fraction: float = 0.40,
    transition_weight_multiplier: float = 1.0,
    transition_reference_column: str = "current_sla_violation",
) -> dict:
    result = run_training(
        dataset,
        target_column=target_column,
        split_strategy=split_strategy,
        test_size=test_size,
        random_state=random_state,
        time_column=time_column,
        scenario_column=scenario_column,
        excluded_feature_prefixes=excluded_feature_prefixes,
        sample_weight_mode=sample_weight_mode,
        calibration_method=calibration_method,
        calibration_cv=calibration_cv,
        tune_thresholds=tune_thresholds,
        threshold_min=threshold_min,
        threshold_max=threshold_max,
        threshold_steps=threshold_steps,
        min_positive_count_test=min_positive_count_test,
        min_positive_rate_test=min_positive_rate_test,
        max_test_size_fraction=max_test_size_fraction,
        transition_weight_multiplier=transition_weight_multiplier,
        transition_reference_column=transition_reference_column,
    )
    artifact_metadata = dict(metadata or {})
    artifact_metadata.setdefault("target_column", target_column)
    artifact_metadata.setdefault("split_strategy", split_strategy)
    artifact_metadata.setdefault("test_size", test_size)
    artifact_metadata.setdefault("random_state", random_state)
    artifact_metadata["excluded_feature_prefixes"] = result["excluded_feature_prefixes"]
    artifact_metadata["dropped_feature_columns"] = result["dropped_feature_columns"]
    artifact_metadata["sample_weight_mode"] = result["sample_weight_mode"]
    artifact_metadata["calibration"] = result["calibration_info"]
    artifact_metadata["threshold_tuning"] = result["threshold_info"]
    artifact_metadata["transition_reweight"] = result["transition_info"]
    artifact_metadata["split_info"] = result["split_info"]
    artifact_metadata["decision_thresholds_by_slice"] = result["threshold_info"].get("threshold_by_slice", {})
    artifact_metadata["decision_threshold_default"] = result["threshold_info"].get("default_threshold", 0.5)
    artifact_metadata["below_threshold_action_scale"] = 0.25

    artifacts = save_model_artifacts(
        result["model"],
        model_dir,
        result["feature_columns"],
        metadata=artifact_metadata,
        label_config={
            "target_column": target_column,
            "split_strategy": split_strategy,
        },
    )
    result["artifacts"] = artifacts
    return result


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    excel_path = repo_root / "final_output" / "legacy_simulation_outputs" / "output.xlsx"
    sla_path = repo_root / "sla_reference_table.csv"

    if not excel_path.exists():
        raise FileNotFoundError(
            f"Missing training source: {excel_path}. Generate output.xlsx before running this example."
        )
    if not sla_path.exists():
        raise FileNotFoundError(
            f"Missing SLA reference: {sla_path}. Create the SLA table before running this example."
        )

    dataset = build_training_frame(excel_path, sla_path, horizon=1)
    print(f"Training rows: {len(dataset)}")
    print("Binary label distribution:")
    print(dataset["next_sla_violation"].value_counts().to_string())
    print("\nThree-level label distribution:")
    print(dataset["next_sla_label"].value_counts().to_string())

    result = run_training(dataset)
    model = result["model"]
    feature_columns = result["feature_columns"]

    print("\nClassification report for next-window SLA violation:")
    print(result["classification_report"])
    print(f"ROC-AUC: {result['roc_auc']:.4f}")
    print_top_feature_importances(model)

    latest_rows = dataset.sort_values("time").tail(5).copy()
    latest_scores = model.predict_proba(latest_rows[feature_columns])[:, 1]
    latest_rows["predicted_violation_risk"] = latest_scores
    display_columns = [
        "time",
        "slice_name",
        "base_station_id",
        "clients_seen",
        "connected_clients_ratio",
        "block_ratio",
        "handover_ratio",
        "avg_slice_load_ratio",
        "avg_latency_ms",
        "p95_latency_ms",
        "latency_violation_ratio",
        "predicted_violation_risk",
    ]
    print("\nLatest prediction examples:")
    print(latest_rows[display_columns].to_string(index=False))


if __name__ == "__main__":
    main()
