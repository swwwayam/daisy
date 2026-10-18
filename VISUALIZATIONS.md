# Visualization Studio

Open **Visualizations** in the workspace navigation. The studio is a prominent
section above the active pipeline stage, available as soon as a dataset is uploaded.

1. Choose the current pipeline dataset, original dataset, or saved model validation.
2. Pick X and optionally Y. Leaving Y empty requests a distribution/count.
3. Choose a graph or keep Auto, then Generate visualization.
4. Download the SVG or expand View plotted values for the underlying chart data.

Auto selects histogram for one numeric column, scatter for two numeric columns,
category heatmap for two categorical columns, and bar otherwise. Invalid axis/type
combinations return an actionable error. Bar plots support mean, sum and count.
Histograms ignore Y. Line plots connect numeric pairs sorted by X; they are not
automatically time-series forecasts.

## Model diagnostics

After training, Saved model validation defaults to actual vs predicted. Regression
produces a scatter plot; classification produces a count confusion heatmap. A
residual preset uses predicted X and actual-minus-predicted Y. Encoded features
from the saved estimator can also be selected. Candidate metric comparisons are
shown below the studio when training results are present. SHAP/permutation plots
remain in the model explanation panel.

Model plots reuse frozen preprocessing, estimator and validation indices, checking
the stored dataset fingerprint. They never refit, finalize an experiment or score
the final-test fold. They use the existing deterministic validation sample (at most
200 rows), shared inference concurrency and scored-row quota. Confusion plots here
are validation diagnostics; final-test confusion results remain in Results.

## Bounds and privacy

- Dataset histograms/bar aggregates process the selected columns across valid rows.
- Histograms use 20 bins; bars display the top 20 groups by plotted value.
- Heatmaps use counts for the top 15 categories per axis, bounded before cross-tabulation.
- Dataset scatter/line plots use at most 1,000 deterministic sampled pairs.
- Missing and non-finite selected values are excluded; zero is preserved.
- Count bars use X only, so missing Y values do not reduce their counts.
- Category labels remain unique when long names are truncated or values stringify alike.
- Bar and heatmap reports state how many valid rows fall outside displayed groups.
- Every chart states rows used, source rows, exclusions, sampling and plot scope.
- Both endpoints require authentication and enforce dataset/experiment ownership.
- Plotting calls no AI provider. Selected plot data goes only to the authenticated
  browser; SVG downloads happen locally. Model plotting still consumes inference quota.

Backend tests cover real regression/classification artifact plots, ownership,
frozen models, split isolation, aggregation correctness and high-cardinality bounds.
The studio UI was inspected using a temporary synthetic fixture, not a real login.
