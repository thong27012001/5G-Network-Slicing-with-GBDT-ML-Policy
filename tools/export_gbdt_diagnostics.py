"""Export per-slice GBDT diagnostics for production model gbdt_anyh_135.

Generates:
    - per_slice_metrics.csv      -- ROC-AUC, P, R, F1, support per slice × horizon
    - per_slice_confusion.json   -- Confusion matrix per slice × horizon
    - feature_importance_top15.png -- Bar chart top-15 features (h1 model)
    - per_slice_metrics.md       -- Markdown summary table

Usage:
    python tools/export_gbdt_diagnostics.py
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import (
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "models" / "gbdt_anyh_135"
OUTPUT_DIR = ROOT / "artifacts" / "gbdt_diagnostics" / "anyh_135_per_slice"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SLICE_ORDER = ("URLLC", "eMBB", "mMTC")
HORIZONS = (1, 3, 5)


def _load_h_artifacts(horizon: int) -> dict:
    h_dir = MODEL_DIR / f"h{horizon}"
    model = joblib.load(h_dir / "model.joblib")
    with (h_dir / "feature_columns.json").open() as fh:
        feat_cols = json.load(fh)
    with (h_dir / "metadata.json").open() as fh:
        meta = json.load(fh)
    with (h_dir / "label_config.json").open() as fh:
        label_cfg = json.load(fh)

    dataset_path = Path(meta["dataset"])
    if not dataset_path.exists():
        # Try relative path under repo
        rel = dataset_path.name
        candidate = ROOT / "artifacts" / "multihorizon_training" / "datasets_anyh_135" / rel
        if candidate.exists():
            dataset_path = candidate
        else:
            raise SystemExit(f"Dataset not found: {dataset_path}")

    df = pd.read_csv(dataset_path)
    return {
        "model": model,
        "features": feat_cols,
        "meta": meta,
        "label_cfg": label_cfg,
        "df": df,
        "target_col": meta["target_column"],
    }


def _build_test_split(df: pd.DataFrame, meta: dict) -> tuple[pd.DataFrame, pd.Series]:
    """Reconstruct test split using the metadata's split strategy."""
    split_strategy = meta.get("split_strategy", "stratified_time")
    test_size = float(meta.get("test_size", 0.2))
    target_col = meta["target_column"]

    # Stratified-time split: per (scenario, slice) take last fraction tail.
    # Simpler reconstruction: take last test_size fraction per (scenario_name, slice_name).
    df = df.sort_values(["scenario_name", "slice_name", "base_station_id", "time"]).reset_index(drop=True)

    test_idx = []
    for (scen, slc), grp in df.groupby(["scenario_name", "slice_name"], sort=False):
        n = len(grp)
        n_test = max(int(np.ceil(n * test_size)), 1)
        test_idx.extend(grp.iloc[-n_test:].index.tolist())

    test_mask = df.index.isin(test_idx)
    test = df[test_mask].copy()
    return test, test[target_col]


def _per_slice_metrics(
    model, X: pd.DataFrame, y: pd.Series, slice_col: pd.Series, thresholds: dict[str, float]
) -> pd.DataFrame:
    proba = model.predict_proba(X)[:, 1]

    rows = []
    for slice_name in SLICE_ORDER:
        mask = slice_col == slice_name
        n = int(mask.sum())
        if n == 0:
            rows.append({"slice": slice_name, "support": 0, "n_pos": 0, "auc": np.nan,
                         "threshold": thresholds.get(slice_name, np.nan),
                         "precision": np.nan, "recall": np.nan, "f1": np.nan,
                         "tp": 0, "fp": 0, "fn": 0, "tn": 0})
            continue

        y_slice = y[mask].astype(int).to_numpy()
        p_slice = proba[mask]
        n_pos = int(y_slice.sum())

        threshold = thresholds.get(slice_name, 0.5)
        pred = (p_slice >= threshold).astype(int)

        try:
            auc = roc_auc_score(y_slice, p_slice) if n_pos > 0 and n_pos < n else float("nan")
        except ValueError:
            auc = float("nan")

        if n_pos > 0:
            prec = precision_score(y_slice, pred, zero_division=0)
            rec = recall_score(y_slice, pred, zero_division=0)
            f1 = f1_score(y_slice, pred, zero_division=0)
        else:
            prec = rec = f1 = float("nan")

        cm = confusion_matrix(y_slice, pred, labels=[0, 1])
        tn, fp, fn, tp = cm.ravel()

        rows.append({
            "slice": slice_name,
            "support": n,
            "n_pos": n_pos,
            "pos_rate": n_pos / n,
            "threshold": threshold,
            "auc": auc,
            "precision": prec,
            "recall": rec,
            "f1": f1,
            "tp": int(tp),
            "fp": int(fp),
            "fn": int(fn),
            "tn": int(tn),
        })
    return pd.DataFrame(rows)


def _extract_feature_importance(model, feat_cols: list[str]) -> pd.DataFrame:
    """Pull feature_importances_ + post-OHE feature names from model pipeline."""
    raw = _try_get_importances(model)
    if raw is None:
        raise SystemExit("Could not extract feature_importances_ from model.")

    # Get post-OHE feature names via ColumnTransformer in the pipeline.
    names = _get_transformed_feature_names(model, feat_cols)
    if names is None or len(names) != len(raw):
        # Fallback to raw indices
        names = [f"f{i}" for i in range(len(raw))]

    return pd.DataFrame({"feature": names, "importance": raw}).sort_values(
        "importance", ascending=False
    )


def _get_transformed_feature_names(model, feat_cols: list[str]) -> list[str] | None:
    """Find ColumnTransformer in pipeline and return post-OHE feature names."""
    pipeline = None
    if hasattr(model, "named_steps"):
        pipeline = model
    elif hasattr(model, "calibrated_classifiers_"):
        inner = model.calibrated_classifiers_[0]
        base = getattr(inner, "estimator", inner)
        if hasattr(base, "named_steps"):
            pipeline = base
    if pipeline is None:
        return None

    for step_name, step in pipeline.named_steps.items():
        if hasattr(step, "transformers_"):
            try:
                names = step.get_feature_names_out(feat_cols)
                # Strip transformer prefix like 'cat__' or 'num__'
                return [n.split("__", 1)[-1] for n in names]
            except Exception:
                continue
    return None


def _try_get_importances(obj):
    """Walk Pipeline/CalibratedClassifierCV/etc to find feature_importances_."""
    if hasattr(obj, "feature_importances_"):
        return obj.feature_importances_
    if hasattr(obj, "named_steps"):
        for step in reversed(list(obj.named_steps.values())):
            if hasattr(step, "feature_importances_"):
                return step.feature_importances_
            if hasattr(step, "calibrated_classifiers_"):
                inner = step.calibrated_classifiers_[0]
                base = getattr(inner, "estimator", inner)
                if hasattr(base, "feature_importances_"):
                    return base.feature_importances_
    if hasattr(obj, "calibrated_classifiers_"):
        inner = obj.calibrated_classifiers_[0]
        base = getattr(inner, "estimator", inner)
        return _try_get_importances(base)
    return None


def _plot_feature_importance(fi_df: pd.DataFrame, output_path: Path, top_n: int = 15) -> None:
    top = fi_df.head(top_n).iloc[::-1]
    fig, ax = plt.subplots(figsize=(8, 5.5))
    ax.barh(top["feature"], top["importance"], color="#1f77b4", alpha=0.9)
    ax.set_xlabel("Built-in feature importance")
    ax.set_title(f"Top-{top_n} features — gbdt_anyh_135 (h=1)")
    ax.grid(axis="x", linestyle="--", alpha=0.4)
    fig.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    all_metrics = []
    all_confusion = {}

    fi_df_h1 = None
    feat_cols_h1 = None

    for h in HORIZONS:
        print(f"\n=== Horizon h={h} ===")
        art = _load_h_artifacts(h)
        thresholds = {
            s: art["meta"]["threshold_tuning"]["slices"][s]["threshold"]
            for s in SLICE_ORDER
        }
        print(f"Tuned thresholds: {thresholds}")

        test_df, y_test = _build_test_split(art["df"], art["meta"])
        slice_col = test_df["slice_name"]
        feat_cols = art["features"]
        X_test = test_df[feat_cols]

        metrics_df = _per_slice_metrics(art["model"], X_test, y_test, slice_col, thresholds)
        metrics_df.insert(0, "horizon", h)
        all_metrics.append(metrics_df)

        for _, row in metrics_df.iterrows():
            key = f"h{h}_{row['slice']}"
            all_confusion[key] = {
                "tp": row["tp"], "fp": row["fp"], "fn": row["fn"], "tn": row["tn"],
                "support": row["support"], "n_pos": row["n_pos"], "threshold": row["threshold"],
            }

        print(metrics_df[["slice", "support", "n_pos", "threshold", "auc",
                          "precision", "recall", "f1"]].to_string(index=False))

        if h == 1:
            fi_df_h1 = _extract_feature_importance(art["model"], feat_cols)
            feat_cols_h1 = feat_cols

    combined = pd.concat(all_metrics, ignore_index=True)
    combined.to_csv(OUTPUT_DIR / "per_slice_metrics.csv", index=False)
    print(f"\nWrote: {OUTPUT_DIR / 'per_slice_metrics.csv'}")

    with (OUTPUT_DIR / "per_slice_confusion.json").open("w") as fh:
        json.dump(all_confusion, fh, indent=2)
    print(f"Wrote: {OUTPUT_DIR / 'per_slice_confusion.json'}")

    if fi_df_h1 is not None:
        fi_df_h1.to_csv(OUTPUT_DIR / "feature_importance_h1.csv", index=False)
        _plot_feature_importance(fi_df_h1, OUTPUT_DIR / "feature_importance_top15.png")
        print(f"Wrote: {OUTPUT_DIR / 'feature_importance_top15.png'}")
        print(f"\nTop 5 features (h1):")
        print(fi_df_h1.head(5).to_string(index=False))


if __name__ == "__main__":
    main()
