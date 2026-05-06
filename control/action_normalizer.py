"""Normalize controller actions into safe, bounded ratios and weights."""

from __future__ import annotations

import logging

import pandas as pd

from control.controller_schema import ControllerConstraints

LOGGER = logging.getLogger(__name__)


def _project_to_bounded_simplex(
    preferred: pd.Series,
    lower: pd.Series,
    upper: pd.Series,
    *,
    tolerance: float = 1e-12,
    max_iterations: int = 32,
) -> pd.Series:
    lower = lower.astype(float)
    upper = upper.astype(float)
    upper = pd.concat([lower, upper], axis=1).max(axis=1)

    lower_sum = float(lower.sum())
    upper_sum = float(upper.sum())
    if lower_sum > 1.0 + tolerance:
        LOGGER.warning(
            "Minimum ratio constraints sum to %.4f (> 1.0); scaling floors down to keep ratios feasible.",
            lower_sum,
        )
        return lower / lower_sum
    if upper_sum < 1.0 - tolerance:
        return upper / upper_sum if upper_sum > 0 else pd.Series(1.0 / len(preferred), index=preferred.index)

    target = preferred.astype(float).clip(lower=lower, upper=upper)
    for _ in range(max_iterations):
        diff = 1.0 - float(target.sum())
        if abs(diff) <= tolerance:
            break

        if diff > 0:
            room = (upper - target).clip(lower=0.0)
        else:
            room = (target - lower).clip(lower=0.0)

        room_sum = float(room.sum())
        if room_sum <= tolerance:
            break

        adjustment = abs(diff) * room / room_sum
        if diff > 0:
            target = (target + adjustment).clip(upper=upper)
        else:
            target = (target - adjustment).clip(lower=lower)

    total = float(target.sum())
    if total <= tolerance:
        return lower / lower_sum if lower_sum > tolerance else pd.Series(1.0 / len(preferred), index=preferred.index)
    return target / total


def normalize_ratio_actions(
    action_df: pd.DataFrame,
    constraints: ControllerConstraints | None = None,
) -> pd.DataFrame:
    constraints = constraints or ControllerConstraints()
    if action_df.empty:
        return action_df.copy()

    output_frames = []
    for _, group in action_df.groupby("base_station_id", sort=False):
        group = group.copy()
        if "current_ratio" not in group.columns:
            group["current_ratio"] = 1.0 / max(len(group), 1)

        min_ratio = pd.Series(constraints.min_ratio, index=group.index, dtype=float)
        if constraints.min_ratio_by_slice:
            slice_min_ratio = group["slice_name"].map(constraints.min_ratio_by_slice)
            min_ratio = pd.concat([min_ratio, slice_min_ratio], axis=1).max(axis=1).fillna(constraints.min_ratio)

        max_ratio = pd.Series(constraints.max_ratio, index=group.index, dtype=float)
        if constraints.max_ratio_by_slice:
            slice_max_ratio = group["slice_name"].map(constraints.max_ratio_by_slice)
            max_ratio = pd.concat([max_ratio, slice_max_ratio], axis=1).min(axis=1).fillna(constraints.max_ratio)
        max_ratio = pd.concat([min_ratio, max_ratio], axis=1).max(axis=1)

        target = group["raw_target_ratio"].clip(lower=min_ratio, upper=max_ratio)
        if "max_step_change" in group.columns:
            step_change = group["max_step_change"].fillna(constraints.max_step_change).clip(lower=0.0)
        else:
            step_change = pd.Series(constraints.max_step_change, index=group.index, dtype=float)
        lower_bound = (group["current_ratio"] - step_change).clip(lower=min_ratio)
        upper_bound = (group["current_ratio"] + step_change).clip(upper=max_ratio)
        target = _project_to_bounded_simplex(target, lower_bound, upper_bound)

        group["target_ratio"] = target
        group["scheduling_weight"] = group["scheduling_weight"].clip(
            lower=constraints.scheduling_weight_floor,
            upper=constraints.scheduling_weight_ceiling,
        )
        group["admission_guard_factor"] = group["admission_guard_factor"].clip(
            lower=constraints.admission_guard_floor,
            upper=constraints.admission_guard_ceiling,
        )
        output_frames.append(group)

    return pd.concat(output_frames, ignore_index=True)
