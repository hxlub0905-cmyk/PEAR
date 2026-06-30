"""Attribute bank.

For an 8-bit grayscale ROI (``patch``) compute a bank of scalar image
attributes. Each attribute reduces the patch to a single number. Optional
inputs add physical-area and cell-to-cell-residual attributes.

Implemented in plain NumPy/OpenCV (no scikit-image, no scipy). Every
division is guarded so degenerate / tiny patches never raise.
"""

from __future__ import annotations

from typing import Dict, Optional

import cv2
import numpy as np

# English display names for every attribute id.
ATTR_LABELS: Dict[str, str] = {
    "glv_mean": "GLV mean",
    "glv_std": "GLV std",
    "glv_min": "GLV min",
    "glv_max": "GLV max",
    "glv_median": "GLV median",
    "glv_p5": "GLV P5",
    "glv_p95": "GLV P95",
    "glv_iqr": "GLV IQR",
    "glv_mad": "GLV MAD",
    "glv_range": "GLV range",
    "glv_skew": "GLV skew",
    "glv_kurtosis": "GLV kurtosis",
    "snr": "SNR",
    "michelson": "Michelson contrast",
    "rms_contrast": "RMS contrast",
    "grad_mean": "Gradient mag.",
    "lap_var": "Laplacian var.",
    "edge_density": "Edge density",
    "entropy": "Entropy",
    "fft_hf_ratio": "FFT HF ratio",
    "glcm_contrast": "GLCM contrast",
    "glcm_homogeneity": "GLCM homogeneity",
    "glcm_energy": "GLCM energy",
    "glcm_correlation": "GLCM correlation",
    "area_px": "Area (px)",
    "area_nm2": "Area (nm²)",
    "c2c_rms": "C2C residual RMS",
    "c2c_mae": "C2C residual MAE",
    "c2c_maxabs": "C2C residual max|Δ|",
}

# Short human-readable definitions (shown as tooltips so the engineer can
# see exactly how each number is computed).
ATTR_FORMULAS: Dict[str, str] = {
    "glv_mean": "mean(gray)",
    "glv_std": "std(gray)",
    "glv_min": "min(gray)",
    "glv_max": "max(gray)",
    "glv_median": "median(gray)",
    "glv_p5": "5th percentile of gray",
    "glv_p95": "95th percentile of gray",
    "glv_iqr": "P75 − P25",
    "glv_mad": "median(|x − median|)",
    "glv_range": "max − min",
    "glv_skew": "m3 / m2^1.5 (central moments)",
    "glv_kurtosis": "m4 / m2² − 3 (excess)",
    "snr": "mean / std",
    "michelson": "(max − min) / (max + min)",
    "rms_contrast": "std / mean",
    "grad_mean": "mean √(Sobelx² + Sobely²)",
    "lap_var": "variance of Laplacian",
    "edge_density": "fraction of px with |grad| > 25",
    "entropy": "Shannon entropy of 256-bin histogram",
    "fft_hf_ratio": "energy beyond 0.25·Nyquist / total energy",
    "glcm_contrast": "Σ P·(i−j)²  (8-level horizontal GLCM)",
    "glcm_homogeneity": "Σ P / (1 + (i−j)²)",
    "glcm_energy": "Σ P²",
    "glcm_correlation": "normalized i,j correlation of P",
    "area_px": "w · h",
    "area_nm2": "w · h · (nm_per_px)²",
    "c2c_rms": "√mean((patch − golden)²)",
    "c2c_mae": "mean(|patch − golden|)",
    "c2c_maxabs": "max(|patch − golden|)",
}

# Attributes that describe the box, not the structure. Shown in the
# per-instance data but excluded from outlier ranking by default.
SIZE_ATTRS = {"area_px", "area_nm2"}

_EPS = 1e-12


def _safe_div(num: float, den: float) -> float:
    """Division that returns 0.0 when the denominator is ~0."""
    if abs(den) < _EPS:
        return 0.0
    return float(num) / float(den)


def _glcm_8level(patch: np.ndarray) -> np.ndarray:
    """Horizontal (offset (0,1)) GLCM quantized to 8 gray levels.

    Returns a normalized 8x8 probability matrix (rows/cols are gray
    levels). Symmetric is not enforced; the offset is one pixel to the
    right within each row.
    """
    if patch.shape[1] < 2:
        return np.zeros((8, 8), dtype=np.float64)
    # Quantize 0..255 -> 0..7.
    q = (patch.astype(np.int32) * 8) // 256
    np.clip(q, 0, 7, out=q)
    left = q[:, :-1].ravel()
    right = q[:, 1:].ravel()
    glcm = np.zeros((8, 8), dtype=np.float64)
    np.add.at(glcm, (left, right), 1.0)
    total = glcm.sum()
    if total < _EPS:
        return glcm
    return glcm / total


def _glcm_features(glcm: np.ndarray) -> Dict[str, float]:
    """Contrast, homogeneity, energy, correlation from a normalized GLCM."""
    levels = glcm.shape[0]
    i = np.arange(levels).reshape(-1, 1).astype(np.float64)
    j = np.arange(levels).reshape(1, -1).astype(np.float64)

    contrast = float(np.sum(glcm * (i - j) ** 2))
    homogeneity = float(np.sum(glcm / (1.0 + (i - j) ** 2)))
    energy = float(np.sum(glcm ** 2))

    mu_i = float(np.sum(i * glcm))
    mu_j = float(np.sum(j * glcm))
    var_i = float(np.sum(((i - mu_i) ** 2) * glcm))
    var_j = float(np.sum(((j - mu_j) ** 2) * glcm))
    cov = float(np.sum((i - mu_i) * (j - mu_j) * glcm))
    correlation = _safe_div(cov, np.sqrt(var_i * var_j))

    return {
        "glcm_contrast": contrast,
        "glcm_homogeneity": homogeneity,
        "glcm_energy": energy,
        "glcm_correlation": correlation,
    }


def _entropy(patch: np.ndarray) -> float:
    """Shannon entropy (bits) of the 256-bin gray-level histogram."""
    hist = np.bincount(patch.ravel(), minlength=256).astype(np.float64)
    total = hist.sum()
    if total < _EPS:
        return 0.0
    p = hist / total
    nz = p[p > 0]
    return float(-np.sum(nz * np.log2(nz)))


def _fft_hf_ratio(patch: np.ndarray) -> float:
    """Spectral energy beyond 0.25*Nyquist radius divided by total energy."""
    f = patch.astype(np.float64)
    f = f - f.mean()
    if f.shape[0] < 2 or f.shape[1] < 2:
        return 0.0
    spec = np.abs(np.fft.fftshift(np.fft.fft2(f))) ** 2
    h, w = spec.shape
    cy, cx = h / 2.0, w / 2.0
    yy, xx = np.ogrid[:h, :w]
    r = np.sqrt(((yy - cy) / (h / 2.0)) ** 2 + ((xx - cx) / (w / 2.0)) ** 2)
    total = float(spec.sum())
    if total < _EPS:
        return 0.0
    hf = float(spec[r > 0.25].sum())
    return _safe_div(hf, total)


def _moments(values: np.ndarray) -> Dict[str, float]:
    """Skew (m3/m2^1.5) and excess kurtosis (m4/m2^2 - 3)."""
    x = values.astype(np.float64)
    mean = float(x.mean())
    d = x - mean
    m2 = float(np.mean(d ** 2))
    m3 = float(np.mean(d ** 3))
    m4 = float(np.mean(d ** 4))
    skew = _safe_div(m3, m2 ** 1.5)
    kurt = _safe_div(m4, m2 ** 2) - 3.0 if m2 > _EPS else 0.0
    return {"glv_skew": skew, "glv_kurtosis": kurt}


def compute_attributes(patch: np.ndarray,
                       golden_sub: Optional[np.ndarray] = None,
                       nm_per_px: Optional[float] = None,
                       edge_thresh: float = 25.0) -> Dict[str, float]:
    """Compute the full attribute bank for one 8-bit grayscale ROI.

    Parameters
    ----------
    patch:
        2-D uint8 (or convertible) grayscale ROI.
    golden_sub:
        Matching Golden-Cell sub-region; enables the C2C residual
        attributes. Must be the same shape as ``patch``.
    nm_per_px:
        Pixel size in nanometres; enables ``area_nm2``.
    edge_thresh:
        Gradient-magnitude threshold for ``edge_density``.
    """
    p = np.asarray(patch)
    if p.dtype != np.uint8:
        p = np.clip(p, 0, 255).astype(np.uint8)
    if p.ndim != 2:
        raise ValueError("patch must be 2-D grayscale")

    h, w = p.shape
    flat = p.ravel()
    f = p.astype(np.float64)

    mean = float(f.mean())
    std = float(f.std())
    vmin = float(flat.min())
    vmax = float(flat.max())
    median = float(np.median(f))
    p5 = float(np.percentile(f, 5))
    p25 = float(np.percentile(f, 25))
    p75 = float(np.percentile(f, 75))
    p95 = float(np.percentile(f, 95))
    mad = float(np.median(np.abs(f - median)))

    attrs: Dict[str, float] = {
        "glv_mean": mean,
        "glv_std": std,
        "glv_min": vmin,
        "glv_max": vmax,
        "glv_median": median,
        "glv_p5": p5,
        "glv_p95": p95,
        "glv_iqr": p75 - p25,
        "glv_mad": mad,
        "glv_range": vmax - vmin,
        "snr": _safe_div(mean, std),
        "michelson": _safe_div(vmax - vmin, vmax + vmin),
        "rms_contrast": _safe_div(std, mean),
    }
    attrs.update(_moments(f))

    # Gradient / edge / texture.
    gx = cv2.Sobel(f, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(f, cv2.CV_64F, 0, 1, ksize=3)
    grad = np.hypot(gx, gy)
    attrs["grad_mean"] = float(grad.mean())
    attrs["lap_var"] = float(cv2.Laplacian(f, cv2.CV_64F).var())
    attrs["edge_density"] = float(np.mean(grad > edge_thresh))
    attrs["entropy"] = _entropy(p)
    attrs["fft_hf_ratio"] = _fft_hf_ratio(p)
    attrs.update(_glcm_features(_glcm_8level(p)))

    # Size attributes (excluded from ranking, kept in per-instance data).
    attrs["area_px"] = float(w * h)
    if nm_per_px is not None and nm_per_px > 0:
        attrs["area_nm2"] = float(w * h) * float(nm_per_px) ** 2

    # Cell-to-cell residual attributes.
    if golden_sub is not None and golden_sub.shape == p.shape:
        diff = f - golden_sub.astype(np.float64)
        attrs["c2c_rms"] = float(np.sqrt(np.mean(diff ** 2)))
        attrs["c2c_mae"] = float(np.mean(np.abs(diff)))
        attrs["c2c_maxabs"] = float(np.max(np.abs(diff)))

    return attrs
