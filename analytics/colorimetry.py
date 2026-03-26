from __future__ import annotations

"""Lightweight colorimetry helpers for spectra -> XYZ/Lab and DeltaE."""

from math import pow, sqrt


def _f(t: float) -> float:
    return pow(t, 1 / 3) if t > 0.008856 else (7.787 * t + 16 / 116)


def xyz_to_lab(xyz: tuple[float, float, float], white: tuple[float, float, float] = (95.047, 100.0, 108.883)) -> tuple[float, float, float]:
    x, y, z = xyz
    xr, yr, zr = x / white[0], y / white[1], z / white[2]
    fx, fy, fz = _f(xr), _f(yr), _f(zr)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def delta_e_76(lab1: tuple[float, float, float], lab2: tuple[float, float, float]) -> float:
    return sqrt(sum((a - b) ** 2 for a, b in zip(lab1, lab2)))


def lab_from_tristimulus(x: float, y: float, z: float, illuminant: str = "D65", observer: int = 2) -> tuple[float, float, float]:
    # placeholder for configurable illuminants/observers; defaults align to D65/2°.
    _ = (illuminant, observer)
    return xyz_to_lab((x, y, z))
