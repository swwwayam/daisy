# Convex storage latency

Measured October 14, 2026 against DAISY's Sydney Convex deployment from the
local Python API. Synthetic CSVs contained six numeric/categorical columns.
Upload timings include parsing, input checks, saving the original CSV and
interpreted snapshot, and generating the schema report. Stage-save timings
measure persistence of an EDA result on an existing dataset, not EDA computation.

| Rows | Upload before | Upload after | Stage save before | Stage save after |
| --- | ---: | ---: | ---: | ---: |
| 10,000 | 9.025 s | 2.723 s | 5.622 s | 0.556 s |
| 50,000 | 15.001 s | 4.500 s | 12.241 s | 0.553 s |

Single-run measurements, with network variability; these are not latency guarantees.
Parsing alone took 0.095 s and 0.546 s in the final runs. No model-training or
external AI response times are included.

Changes: persistent HTTP/TLS connections, inline metadata up to 32 KiB,
metadata-only stage writes, concurrent original/snapshot transfers, lossless
gzip snapshot compression, bounded original-byte caching, and moving blocking
CSV/cloud work off the API event loop.

Cloud recovery was checked after removing the in-process dataset, including
row count, the first literal zero, and the last row. Original CSV downloads
and model ZIPs are not compressed or modified by the new snapshot format.
Existing uncompressed snapshots remain readable. Five Convex tests and 47
backend regressions passed, covering metadata-only preservation, ownership,
input interpretation, persistence, and model export.
