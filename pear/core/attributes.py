"""Metric bank — GLV statistics and e-beam SNR.

Deliberately small: the tool measures **grey-level-value (GLV) statistics**
of a region plus a **signal-to-noise ratio (SNR)**. Everything is plain
NumPy and every reduction is guarded so degenerate / tiny patches never
raise.

GLV statistics operate on a single ROI patch. Their ids are stable
strings; custom quantiles use the id form ``glv_q<NN>`` (e.g. ``glv_q90``).

SNR follows the e-beam definition ``(mean_target - mean_reference) /
std_reference`` and therefore needs a *target* ROI and a *reference* ROI.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np

# Fixed GLV statistics: id -> display label. Q25/Q75 are quantiles too, but
# are shown by default, so they live in the fixed set.
GLV_STATS: Dict[str, str] = {
    "glv_mean": "GLV mean",
    "glv_median": "GLV median",
    "glv_q25": "GLV Q25",
    "glv_q75": "GLV Q75",
    "glv_std": "GLV std",
    "glv_min": "GLV min",
    "glv_max": "GLV max",
}

# Short formulas, shown as tooltips.
GLV_FORMULAS: Dict[str, str] = {
    "glv_mean": "mean(gray)",
    "glv_median": "median(gray)",
    "glv_q25": "25th percentile",
    "glv_q75": "75th percentile",
    "glv_std": "std(gray)",
    "glv_min": "min(gray)",
    "glv_max": "max(gray)",
}

SNR_ID = "snr"
SNR_LABEL = "SNR"
SNR_FORMULA = "(mean_T − mean_R) / std_R"

_EPS = 1e-9


def quantile_of(mid: str) -> Optional[int]:
    """Percentile for a quantile metric id (``glv_q90`` -> 90), else None."""
    if mid.startswith("glv_q") and mid[5:].isdigit():
        return int(mid[5:])
    return None


def metric_label(mid: str) -> str:
    """Human label for any metric id (fixed, custom quantile, or SNR)."""
    if mid in GLV_STATS:
        return GLV_STATS[mid]
    if mid == SNR_ID:
        return SNR_LABEL
    q = quantile_of(mid)
    if q is not None:
        return f"GLV Q{q}"
    return mid


def metric_formula(mid: str) -> str:
    if mid in GLV_FORMULAS:
        return GLV_FORMULAS[mid]
    if mid == SNR_ID:
        return SNR_FORMULA
    q = quantile_of(mid)
    if q is not None:
        return f"{q}th percentile"
    return "—"


def glv_value(patch: np.ndarray, mid: str) -> float:
    """One GLV statistic of a patch. Custom quantiles (``glv_q<NN>``) work too."""
    f = np.asarray(patch, dtype=np.float64).ravel()
    if f.size == 0:
        return 0.0
    if mid == "glv_mean":
        return float(f.mean())
    if mid == "glv_std":
        return float(f.std())
    if mid == "glv_min":
        return float(f.min())
    if mid == "glv_max":
        return float(f.max())
    if mid == "glv_median":
        return float(np.median(f))
    q = quantile_of(mid)
    if q is not None:
        return float(np.percentile(f, q))
    return 0.0


def glv_stats(patch: np.ndarray) -> Dict[str, float]:
    """The full fixed GLV statistic set for a patch."""
    return {mid: glv_value(patch, mid) for mid in GLV_STATS}


def snr(target: np.ndarray, reference: np.ndarray) -> float:
    """E-beam SNR: ``(mean_target - mean_reference) / std_reference``."""
    t = np.asarray(target, dtype=np.float64).ravel()
    r = np.asarray(reference, dtype=np.float64).ravel()
    if t.size == 0 or r.size == 0:
        return 0.0
    sd = float(r.std())
    if sd < _EPS:
        return 0.0
    return (float(t.mean()) - float(r.mean())) / sd


def default_metrics() -> List[str]:
    """Metrics selected on first run."""
    return ["glv_mean", "glv_median"]
