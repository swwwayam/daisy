"""Fixed study design, agreed before automated feature/cleaning decisions."""
from typing import Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, model_validator
from sklearn.model_selection import GroupShuffleSplit, train_test_split


class TrainingConfig(BaseModel):
    target_column: str = Field(min_length=1, max_length=256)
    problem_type: Literal["auto", "classification", "regression"] = "auto"
    split_strategy: Literal["random", "stratified", "group", "time"] = "random"
    group_column: str | None = None
    time_column: str | None = None
    primary_metric: Literal["auto", "f1_weighted", "f1_macro", "accuracy", "balanced_accuracy", "rmse", "mae", "r2"] = "auto"
    duplicate_policy: Literal["keep", "drop"] = "keep"

    @model_validator(mode="after")
    def compatible(self):
        if self.split_strategy == "group" and not self.group_column:
            raise ValueError("Group splitting requires a group column")
        if self.split_strategy == "time" and not self.time_column:
            raise ValueError("Time splitting requires a date/time column")
        if self.target_column in {self.group_column, self.time_column}:
            raise ValueError("Split columns cannot be the prediction target")
        if self.problem_type == "regression" and self.split_strategy == "stratified":
            raise ValueError("Stratified label splitting requires classification")
        class_metrics = {"f1_weighted", "f1_macro", "accuracy", "balanced_accuracy"}
        regression_metrics = {"rmse", "mae", "r2"}
        if (self.problem_type == "regression" and self.primary_metric in class_metrics) or (self.problem_type == "classification" and self.primary_metric in regression_metrics):
            raise ValueError("Metric does not match the task type")
        return self


def configured_partitions(source, configuration, random_state=42):
    config = TrainingConfig(**configuration)
    needed = {config.target_column}
    if config.split_strategy == "group": needed.add(config.group_column)
    if config.split_strategy == "time": needed.add(config.time_column)
    if needed - set(source.columns):
        raise ValueError(f"Study columns are missing: {sorted(needed - set(source.columns))}")
    source = source.dropna(subset=[config.target_column])
    if config.duplicate_policy == "drop": source = source.drop_duplicates()
    if not source.index.is_unique or len(source) < 15:
        raise ValueError("Study needs at least 15 uniquely indexed labeled rows")
    if config.split_strategy == "time":
        dates = pd.to_datetime(source[config.time_column], errors="coerce", utc=True)
        if dates.isna().any(): raise ValueError("All labeled rows need valid timestamps for time splitting")
        unique = dates.sort_values().unique()
        if len(unique) < 5: raise ValueError("Time splitting needs at least five distinct timestamps")
        validation_start, test_start = unique[int(len(unique) * .6)], unique[int(len(unique) * .8)]
        train = source.index[dates < validation_start]
        validation = source.index[(dates >= validation_start) & (dates < test_start)]
        test = source.index[dates >= test_start]
    elif config.split_strategy == "group":
        groups = source[config.group_column]
        if groups.isna().any() or groups.nunique() < 5:
            raise ValueError("Group splitting needs at least five nonmissing groups")
        development_pos, test_pos = next(GroupShuffleSplit(n_splits=1, test_size=.2, random_state=random_state).split(source, groups=groups))
        development = source.iloc[development_pos]
        train_pos, validation_pos = next(GroupShuffleSplit(n_splits=1, test_size=.25, random_state=random_state).split(development, groups=development[config.group_column]))
        train, validation, test = development.index[train_pos], development.index[validation_pos], source.index[test_pos]
    else:
        stratify = source[config.target_column] if config.split_strategy == "stratified" else None
        development, test = train_test_split(source.index, test_size=.2, random_state=random_state, stratify=stratify)
        train, validation = train_test_split(development, test_size=.25, random_state=random_state,
                                           stratify=source.loc[development, config.target_column] if stratify is not None else None)
    if len(train) < 10 or min(len(validation), len(test)) < 2:
        raise ValueError("Study split needs at least ten training and two validation/test rows; add more labeled data")
    return source, train, validation, test
