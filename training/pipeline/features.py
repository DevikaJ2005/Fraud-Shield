from __future__ import annotations

import pandas as pd

from training.pipeline.schema import LABEL_COLUMN, ORDERED_FEATURES, TIMESTAMP_COLUMN, validate_feature_order


def prepare_features(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    missing = [column for column in [TIMESTAMP_COLUMN, LABEL_COLUMN, *ORDERED_FEATURES] if column not in frame]
    if missing:
        raise ValueError(f"Dataset is missing required columns: {', '.join(missing)}")
    validate_feature_order(ORDERED_FEATURES)
    features = frame[ORDERED_FEATURES].copy()
    labels = frame[LABEL_COLUMN].astype(int)
    return features, labels


def temporal_split(frame: pd.DataFrame, train_ratio: float = 0.70, validation_ratio: float = 0.15) -> dict[str, pd.DataFrame]:
    if train_ratio <= 0 or validation_ratio <= 0 or train_ratio + validation_ratio >= 1:
        raise ValueError("Temporal split ratios must leave a non-empty test split")
    ordered = frame.sort_values(TIMESTAMP_COLUMN).reset_index(drop=True)
    train_end = int(len(ordered) * train_ratio)
    validation_end = int(len(ordered) * (train_ratio + validation_ratio))
    if train_end <= 0 or validation_end <= train_end or validation_end >= len(ordered):
        raise ValueError("Dataset is too small for temporal train/validation/test split")
    return {
        "train": ordered.iloc[:train_end].copy(),
        "validation": ordered.iloc[train_end:validation_end].copy(),
        "test": ordered.iloc[validation_end:].copy(),
    }


def split_summary(splits: dict[str, pd.DataFrame]) -> dict:
    return {
        "type": "temporal",
        "train_rows": int(len(splits["train"])),
        "validation_rows": int(len(splits["validation"])),
        "test_rows": int(len(splits["test"])),
        "train_start": str(splits["train"][TIMESTAMP_COLUMN].min()),
        "train_end": str(splits["train"][TIMESTAMP_COLUMN].max()),
        "validation_start": str(splits["validation"][TIMESTAMP_COLUMN].min()),
        "validation_end": str(splits["validation"][TIMESTAMP_COLUMN].max()),
        "test_start": str(splits["test"][TIMESTAMP_COLUMN].min()),
        "test_end": str(splits["test"][TIMESTAMP_COLUMN].max()),
    }
