"""Separability / outlier ranking.

V1 (surfaced in the UI): unsupervised outlier-attribute ranking using a
robust modified z-score (median + MAD).

Phase 2 (built and unit-tested, but NO UI path reaches it): labelled
reference-vs-target separability metrics and a threshold suggestion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np

_EPS = 1e-12
_MAD_TO_SIGMA = 0.6745  # 0.75 quantile of the standard normal.


# --------------------------------------------------------------------------- #
# V1 — unsupervised outlier-attribute ranking
# --------------------------------------------------------------------------- #
@dataclass
class AttrOutlierScore:
    """How strongly one attribute makes outlier cells separate."""

    attr: str
    max_abs_z: float
    n_outliers: int
    outlier_indices: List[int] = field(default_factory=list)


def modified_zscores(values: np.ndarray) -> np.ndarray:
    """Robust modified z-scores: 0.6745 * (x - median) / MAD.

    MAD = median(|x - median(x)|). When MAD is ~0 (a near-constant
    attribute) the scores are all 0 — nothing separates.
    """
    x = np.asarray(values, dtype=np.float64)
    if x.size == 0:
        return x
    med = float(np.median(x))
    mad = float(np.median(np.abs(x - med)))
    if mad < _EPS:
        return np.zeros_like(x)
    return _MAD_TO_SIGMA * (x - med) / mad


def rank_outlier_attributes(table: Dict[str, np.ndarray],
                            k_sigma: float = 3.5,
                            skip: set | None = None) -> List[AttrOutlierScore]:
    """Rank attributes by how far the outlier cells separate.

    Parameters
    ----------
    table:
        ``{attr_id: values_per_instance}``.
    k_sigma:
        |z| threshold for counting an instance as an outlier.
    skip:
        Attribute ids to exclude from the ranking (e.g. SIZE_ATTRS).

    Returns the scores sorted by ``max_abs_z`` descending.
    """
    skip = skip or set()
    scores: List[AttrOutlierScore] = []
    for attr, values in table.items():
        if attr in skip:
            continue
        vals = np.asarray(values, dtype=np.float64)
        if vals.size == 0 or not np.all(np.isfinite(vals)):
            vals = np.nan_to_num(vals, nan=0.0, posinf=0.0, neginf=0.0)
        z = modified_zscores(vals)
        abs_z = np.abs(z)
        max_abs_z = float(abs_z.max()) if abs_z.size else 0.0
        idx = [int(i) for i in np.nonzero(abs_z > k_sigma)[0]]
        scores.append(AttrOutlierScore(
            attr=attr,
            max_abs_z=max_abs_z,
            n_outliers=len(idx),
            outlier_indices=idx,
        ))
    scores.sort(key=lambda s: s.max_abs_z, reverse=True)
    return scores


# --------------------------------------------------------------------------- #
# Phase 2 — labelled separability metrics (dormant; not wired to any UI)
# --------------------------------------------------------------------------- #
@dataclass
class ThresholdSuggestion:
    threshold: float
    direction: str          # "greater" or "less" (target side)
    catch_rate: float       # fraction of targets caught
    false_alarm: float      # fraction of references flagged


def cnr(reference: np.ndarray, target: np.ndarray) -> float:
    """Contrast-to-noise ratio."""
    r = np.asarray(reference, dtype=np.float64)
    t = np.asarray(target, dtype=np.float64)
    denom = np.sqrt(0.5 * (t.var() + r.var()))
    return _safe_div(abs(t.mean() - r.mean()), denom)


def fisher(reference: np.ndarray, target: np.ndarray) -> float:
    """Fisher discriminant ratio."""
    r = np.asarray(reference, dtype=np.float64)
    t = np.asarray(target, dtype=np.float64)
    return _safe_div((t.mean() - r.mean()) ** 2, t.var() + r.var())


def cohens_d(reference: np.ndarray, target: np.ndarray) -> float:
    """Cohen's d effect size (pooled standard deviation)."""
    r = np.asarray(reference, dtype=np.float64)
    t = np.asarray(target, dtype=np.float64)
    nr, nt = r.size, t.size
    if nr + nt - 2 <= 0:
        return 0.0
    pooled_var = ((nr - 1) * r.var(ddof=1) + (nt - 1) * t.var(ddof=1)) / (nr + nt - 2)
    return _safe_div(t.mean() - r.mean(), np.sqrt(pooled_var))


def auc(reference: np.ndarray, target: np.ndarray) -> float:
    """Direction-agnostic rank-based AUC = max(a, 1 - a)."""
    r = np.asarray(reference, dtype=np.float64)
    t = np.asarray(target, dtype=np.float64)
    nr, nt = r.size, t.size
    if nr == 0 or nt == 0:
        return 0.5
    combined = np.concatenate([r, t])
    ranks = _rankdata(combined)
    rank_t = ranks[nr:]
    a = (rank_t.sum() - nt * (nt + 1) / 2.0) / (nr * nt)
    return float(max(a, 1.0 - a))


def separation_score(reference: np.ndarray, target: np.ndarray) -> float:
    """Friendly 0..100 score derived from the AUC."""
    a = auc(reference, target)
    return float(np.clip((a - 0.5) * 200.0, 0.0, 100.0))


def suggest_threshold(reference: np.ndarray, target: np.ndarray) -> ThresholdSuggestion:
    """Youden's J optimal threshold over candidate split points."""
    r = np.asarray(reference, dtype=np.float64)
    t = np.asarray(target, dtype=np.float64)
    target_greater = t.mean() >= r.mean()
    direction = "greater" if target_greater else "less"

    candidates = np.unique(np.concatenate([r, t]))
    if candidates.size > 1:
        mids = (candidates[:-1] + candidates[1:]) / 2.0
        thresholds = np.concatenate([[candidates[0] - 1], mids, [candidates[-1] + 1]])
    else:
        thresholds = candidates

    best = ThresholdSuggestion(float(candidates[0]) if candidates.size else 0.0,
                               direction, 0.0, 0.0)
    best_j = -np.inf
    for thr in thresholds:
        if target_greater:
            catch = _safe_div(np.sum(t > thr), t.size)
            fa = _safe_div(np.sum(r > thr), r.size)
        else:
            catch = _safe_div(np.sum(t < thr), t.size)
            fa = _safe_div(np.sum(r < thr), r.size)
        j = catch - fa
        if j > best_j:
            best_j = j
            best = ThresholdSuggestion(float(thr), direction, float(catch), float(fa))
    return best


def _rankdata(a: np.ndarray) -> np.ndarray:
    """Average-rank of each element (ties share the mean rank)."""
    a = np.asarray(a, dtype=np.float64)
    order = np.argsort(a, kind="mergesort")
    ranks = np.empty(a.size, dtype=np.float64)
    sorted_a = a[order]
    i = 0
    while i < a.size:
        j = i
        while j + 1 < a.size and sorted_a[j + 1] == sorted_a[i]:
            j += 1
        avg = (i + j) / 2.0 + 1.0  # ranks are 1-based
        ranks[order[i:j + 1]] = avg
        i = j + 1
    return ranks


def _safe_div(num: float, den: float) -> float:
    if abs(den) < _EPS:
        return 0.0
    return float(num) / float(den)
