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
_MAD_TO_SIGMA = 0.6745       # 0.75 quantile of the standard normal.
_MEANAD_TO_SIGMA = 1.253314  # sqrt(pi/2): mean-AD -> sigma for a normal.


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

    MAD = median(|x - median(x)|). When a majority of cells share the same
    value the MAD collapses to 0 even though a minority of cells differ —
    which would mask exactly the outliers we are looking for. In that case
    we fall back to the mean absolute deviation (the Iglewicz-Hoaglin
    mean-AD variant), which stays finite as long as *any* value differs
    from the median. Only a truly constant attribute yields all zeros.
    """
    x = np.asarray(values, dtype=np.float64)
    if x.size == 0:
        return x
    med = float(np.median(x))
    abs_dev = np.abs(x - med)
    mad = float(np.median(abs_dev))
    if mad >= _EPS:
        return _MAD_TO_SIGMA * (x - med) / mad
    mean_ad = float(abs_dev.mean())
    if mean_ad >= _EPS:
        return (x - med) / (_MEANAD_TO_SIGMA * mean_ad)
    return np.zeros_like(x)


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
# Labelled compare — rank attributes by how well they separate target cells
# from reference cells (uses the metrics below).
# --------------------------------------------------------------------------- #
@dataclass
class AttrSeparabilityScore:
    """How well one attribute separates tagged target cells from reference."""

    attr: str
    separation_score: float     # friendly 0..100 (from AUC)
    auc: float
    cnr: float
    cohens_d: float
    threshold: float
    direction: str              # "greater" / "less" (target side of threshold)
    catch_rate: float           # fraction of targets caught
    false_alarm: float          # fraction of references flagged
    n_target: int
    n_reference: int


def rank_separability_attributes(table: Dict[str, np.ndarray],
                                 target_mask: np.ndarray,
                                 skip: set | None = None
                                 ) -> List[AttrSeparabilityScore]:
    """Rank attributes by target-vs-reference separation (descending).

    ``target_mask`` is a boolean array over the instances; True = target,
    False = reference. Attributes in ``skip`` are excluded. Returns an
    empty list if either group is empty.
    """
    skip = skip or set()
    mask = np.asarray(target_mask, dtype=bool)
    if mask.sum() == 0 or (~mask).sum() == 0:
        return []
    scores: List[AttrSeparabilityScore] = []
    for attr, values in table.items():
        if attr in skip:
            continue
        vals = np.nan_to_num(np.asarray(values, dtype=np.float64),
                             nan=0.0, posinf=0.0, neginf=0.0)
        t = vals[mask]
        r = vals[~mask]
        sugg = suggest_threshold(r, t)
        scores.append(AttrSeparabilityScore(
            attr=attr,
            separation_score=separation_score(r, t),
            auc=auc(r, t),
            cnr=cnr(r, t),
            cohens_d=cohens_d(r, t),
            threshold=sugg.threshold,
            direction=sugg.direction,
            catch_rate=sugg.catch_rate,
            false_alarm=sugg.false_alarm,
            n_target=int(t.size),
            n_reference=int(r.size),
        ))
    scores.sort(key=lambda s: (s.separation_score, s.auc), reverse=True)
    return scores


# --------------------------------------------------------------------------- #
# Phase 2 — labelled separability metrics
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
    vr = r.var(ddof=1) if nr > 1 else 0.0
    vt = t.var(ddof=1) if nt > 1 else 0.0
    pooled_var = ((nr - 1) * vr + (nt - 1) * vt) / (nr + nt - 2)
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
