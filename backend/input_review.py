"""User-approved interpretation of source data; no learned statistics here."""
import io
import csv

import pandas as pd
from pydantic import BaseModel, Field
from typing import Literal

from daisy_predict import normalize_input
from training_config import TrainingConfig


class InputReview(BaseModel):
    missing_tokens: list[str] = Field(default_factory=list, max_length=50)
    column_tokens: dict[str, list[str]] = Field(default_factory=dict)
    column_types: dict[str, Literal["auto", "numeric", "text", "datetime"]] = Field(default_factory=dict)
    blank_is_missing: bool = True
    training_config: TrainingConfig | None = None

    def policy(self):
        return {"type": "normalize", **self.model_dump(exclude={"training_config"})}


def read_source(content, review=None):
    """Read strings first so review can preserve leading zeros and literal NA values."""
    policy = (review or InputReview()).policy()
    header = next(csv.reader(io.StringIO(content.decode("utf-8-sig"))), [])
    if len(header) != len(set(header)):
        raise ValueError("CSV contains duplicate column names")
    frame = pd.read_csv(io.BytesIO(content), keep_default_na=False, dtype=str)
    if len(frame.columns) != len(set(frame.columns)):
        raise ValueError("CSV contains duplicate column names")
    known = set(frame.columns)
    if (set(policy["column_tokens"]) | set(policy["column_types"])) - known:
        raise ValueError("Review refers to unknown columns")
    tokens = [*policy["missing_tokens"], *(token for group in policy["column_tokens"].values() for token in group)]
    if len(tokens) > 1000 or any(not isinstance(token, str) or len(token) > 256 for token in tokens):
        raise ValueError("Use at most 1,000 missing tokens of at most 256 characters")
    return normalize_input(frame, policy), policy
