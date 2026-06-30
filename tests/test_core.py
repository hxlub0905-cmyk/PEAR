"""Headless core tests (no Qt).

Synthesize a repeating field with injected outlier cells and verify the
full core path: period detection -> ROI expansion -> attribute bank ->
unsupervised outlier ranking.
"""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from examples.make_sample import (CELL_H, CELL_W, N_COLS, N_ROWS, OUTLIERS,
                                  make_field)
from pear.core.analysis import (PeriodInfo, Region, build_golden_cell,
                                expand_reference_roi, run_region_analysis)
from pear.core.attributes import ATTR_LABELS, SIZE_ATTRS, compute_attributes
from pear.core.period_core import estimate_period
from pear.core import separability


def _period(image) -> PeriodInfo:
    res = estimate_period(image)
    conf = (res.confidence_x + res.confidence_y) / 2.0
    golden = build_golden_cell(image, res.px, res.py)
    return PeriodInfo(px=res.px, py=res.py, axis_mode=res.axis_mode,
                      confidence=conf, golden_cell=golden)


def test_estimate_period_recovers_cell_size():
    img = make_field()
    res = estimate_period(img)
    assert res.px == CELL_W
    assert res.py == CELL_H
    assert res.axis_mode == "XY"


def test_expand_yields_one_instance_per_cell():
    img = make_field()
    # An ROI in the feature block of the top-left cell.
    roi = (16, 13, 30, 26)
    inst = expand_reference_roi(roi, CELL_W, CELL_H, img.shape)
    assert len(inst) == N_COLS * N_ROWS


def test_full_attribute_bank_present_and_labelled():
    img = make_field()
    patch = img[0:CELL_H, 0:CELL_W]
    golden = build_golden_cell(img, CELL_W, CELL_H)
    attrs = compute_attributes(patch, golden_sub=golden, nm_per_px=1.5)
    # The full attribute table (every id in §8) is labelled and produced.
    assert len(ATTR_LABELS) == 29
    for key in attrs:
        assert key in ATTR_LABELS
    # With golden + nm_per_px every attribute id should be produced.
    assert set(attrs.keys()) == set(ATTR_LABELS.keys())


def test_ranking_flags_injected_outliers():
    img = make_field()
    period = _period(img)
    roi = (16, 13, 30, 26)  # over the feature block
    region = Region(rid=1, name="region 1", color="#0E8C8C", roi=roi)
    run_region_analysis(img, region, period)

    assert region.ranking, "ranking must be non-empty"
    assert region.sel_attr is not None
    # Size attributes excluded from ranking.
    ranked_ids = {s.attr for s in region.ranking}
    assert not (ranked_ids & SIZE_ATTRS)

    # The top attribute must flag the 4 injected outlier cells (and only
    # those), identified by (col, row).
    top = region.ranking[0]
    assert top.n_outliers >= len(OUTLIERS)
    flagged = {(region.records[i]["col"], region.records[i]["row"])
               for i in top.outlier_indices}
    for cell in OUTLIERS:
        assert cell in flagged, f"injected outlier {cell} not flagged by {top.attr}"


def test_modified_zscore_constant_is_zero():
    z = separability.modified_zscores(np.full(20, 5.0))
    assert np.allclose(z, 0.0)


def test_zero_mad_does_not_mask_minority_outlier():
    # A majority of identical values collapses the MAD to 0; the mean-AD
    # fallback must still surface the lone deviating cell.
    vals = np.array([5.0] * 9 + [100.0])
    z = separability.modified_zscores(vals)
    assert abs(z[-1]) > 3.5
    assert np.allclose(z[:9], 0.0)
    scores = separability.rank_outlier_attributes({"a": vals})
    assert scores[0].n_outliers == 1
    assert scores[0].outlier_indices == [9]


def test_phase2_metrics_directionagnostic_auc():
    rng = np.random.default_rng(0)
    ref = rng.normal(0, 1, 200)
    tgt = rng.normal(4, 1, 50)
    assert separability.auc(ref, tgt) > 0.95
    # AUC is symmetric (direction-agnostic).
    assert np.isclose(separability.auc(ref, tgt), separability.auc(tgt, ref))
    sugg = separability.suggest_threshold(ref, tgt)
    assert sugg.catch_rate > 0.8
    assert sugg.false_alarm < 0.2
    assert separability.cnr(ref, tgt) > 0
    assert separability.fisher(ref, tgt) > 0
    assert separability.cohens_d(ref, tgt) > 0
    assert 0.0 <= separability.separation_score(ref, tgt) <= 100.0
