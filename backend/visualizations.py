"""Bounded, deterministic plot data. No provider calls or model fitting."""
import numpy as np
import pandas as pd


def build_plot(frame, x, y=None, kind="auto", aggregation="mean", total_rows=None):
    if x not in frame or (y and y not in frame):
        raise ValueError("Choose columns available in this data source.")
    numeric = lambda name: pd.api.types.is_numeric_dtype(frame[name]) and not pd.api.types.is_bool_dtype(frame[name])
    if kind == "auto":
        kind = "histogram" if not y and numeric(x) else "scatter" if y and numeric(x) and numeric(y) else "heatmap" if y and not numeric(x) and not numeric(y) else "bar"
    if kind == "heatmap" and (not y or numeric(x) or numeric(y)):
        raise ValueError("Category heatmaps require two categorical columns. Use scatter for numeric axes.")
    if kind in {"scatter", "line"} and (not y or not numeric(x) or not numeric(y)):
        raise ValueError("Scatter and line charts require numeric X and Y columns.")
    if kind == "histogram" and not numeric(x):
        raise ValueError("Histograms require a numeric X column. Use a bar chart for categories.")
    if kind == "bar" and y and aggregation != "count" and not numeric(y):
        raise ValueError("Mean and sum require a numeric Y column; choose Count for categories.")
    columns = list(dict.fromkeys([x] + ([y] if y and kind != "histogram" else [])))
    data = frame[columns].replace([np.inf, -np.inf], np.nan).dropna()
    valid_rows = len(data)
    if not valid_rows:
        raise ValueError("No finite, non-missing rows are available for these axes.")
    sampled = kind in {"scatter", "line"} and valid_rows > 1000
    if sampled:
        data = data.sample(1000, random_state=42)
    cells = None
    if kind == "heatmap":
        x_values = data[x].value_counts().head(15).index.tolist()
        y_values = data[y].value_counts().head(15).index.tolist()
        bounded = data[data[x].isin(x_values) & data[y].isin(y_values)]
        counts = pd.crosstab(bounded[x], bounded[y])
        cells = [{"x": str(a)[:160], "y": str(b)[:160], "value": int(counts.loc[a, b]) if a in counts.index and b in counts.columns else 0} for a in x_values for b in y_values]
        points, y_label = [], y
    elif kind == "histogram":
        # Normalize first so extreme finite values cannot overflow numpy bins.
        values = data[x].to_numpy(dtype=float)
        scale = max(float(np.max(np.abs(values))), 1.)
        counts, edges = np.histogram(values / scale, bins=20)
        points = [{"x": f"{edges[i] * scale:.5g} to {edges[i+1] * scale:.5g}", "y": int(count)} for i, count in enumerate(counts)]
        y_label = "Row count"
    elif kind == "bar":
        # Bound category count, while aggregating all valid rows, not a preview.
        groups = data.groupby(x, observed=True, sort=False)
        result = groups.size() if not y or aggregation == "count" else groups[y].agg(aggregation)
        result = result.replace([np.inf, -np.inf], np.nan).dropna().sort_values(ascending=False).head(20)
        points = [{"x": str(key)[:160], "y": float(value)} for key, value in result.items()]
        y_label = "Row count" if not y or aggregation == "count" else f"{aggregation.title()} of {y}"
    else:
        if kind == "line":
            data = data.sort_values(x, kind="stable")
        points = [{"x": float(a), "y": float(b)} for a, b in zip(data[x], data[y])]
        y_label = y
    return {"kind": kind, "x_label": x, "y_label": y_label, "points": points, "cells": cells,
            "source_rows": len(frame) if total_rows is None else total_rows, "valid_rows": valid_rows,
            "rows_used": len(data), "sampled": sampled, "excluded_rows": len(frame) - valid_rows,
            "scope": "Counts for the 15 most frequent categories on each axis; remaining categories omitted." if kind == "heatmap" else "Top 20 groups by plotted value." if kind == "bar" else "20 numeric bins." if kind == "histogram" else "Numeric pairs; line charts are sorted by X and do not establish time order or causality."}
