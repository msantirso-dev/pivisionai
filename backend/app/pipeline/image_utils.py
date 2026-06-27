"""Cheap image similarity helpers (pHash, SSIM proxy, histogram)."""

from __future__ import annotations

import cv2
import numpy as np


def _gray_small(frame: np.ndarray, size: int = 32) -> np.ndarray:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
    return cv2.resize(gray, (size, size), interpolation=cv2.INTER_AREA)


def compute_phash(frame: np.ndarray) -> int:
    """Average hash as 64-bit int."""
    small = _gray_small(frame, 8)
    avg = small.mean()
    bits = (small > avg).flatten()
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    return value


def phash_distance(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def compute_ssim_proxy(a: np.ndarray, b: np.ndarray) -> float:
    """Fast SSIM proxy using normalized MSE on grayscale 64x64."""
    ga = _gray_small(a, 64).astype(np.float32)
    gb = _gray_small(b, 64).astype(np.float32)
    if np.array_equal(ga, gb):
        return 1.0
    mse = float(np.mean((ga - gb) ** 2))
    return max(0.0, 1.0 - mse / (255.0 ** 2))


def histogram_similarity(a: np.ndarray, b: np.ndarray) -> float:
    ha = cv2.calcHist([a], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
    hb = cv2.calcHist([b], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
    cv2.normalize(ha, ha)
    cv2.normalize(hb, hb)
    return float(cv2.compareHist(ha, hb, cv2.HISTCMP_CORREL))
