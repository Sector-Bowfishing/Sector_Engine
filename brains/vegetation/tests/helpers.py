"""Synthetic scenes for the observer tests (10 m grid; 5x5-pixel cells)."""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from vegetation_brain import observer as O


def lake_mask(h=100, w=100, margin=10):
    m = np.zeros((h, w), bool)
    m[margin:h - margin, margin:w - margin] = True
    return m


def scene_arrays(h=100, w=100, plant=None, cloud=None, haze=None, shadow=None, nir_water=0.005, red_water=0.005, swir_water=0.003):
    scl = np.full((h, w), 6, "uint8")
    red = np.full((h, w), red_water, "float32")
    nir = np.full((h, w), nir_water, "float32")
    swir = np.full((h, w), swir_water, "float32")
    if plant is not None:
        red[plant], nir[plant], swir[plant] = 0.05, 0.25, 0.08          # NDVI 0.67
        scl[plant] = 4                                                  # SCL vegetation class over a plant canopy
    if cloud is not None:
        scl[cloud] = 9
    if shadow is not None:
        scl[shadow] = 3
    if haze is not None:
        swir[haze] = 0.05
        red[haze], nir[haze] = 0.04, 0.045                              # NDVI ~0.06: not a plant spectrum
    return scl, red, nir, swir


def cells_for(plant=None, **kw):
    mask = kw.pop("mask", None)
    mask = lake_mask() if mask is None else mask
    scl, red, nir, swir = scene_arrays(plant=plant, **kw)
    return O.to_cells(O.scene_fields(scl, red, nir, swir, mask))


def patch(rows, cols, h=100, w=100):
    p = np.zeros((h, w), bool)
    p[rows[0]:rows[1], cols[0]:cols[1]] = True
    return p


def scene(sid, d, **kw):
    return O.Scene(sid, d, cells_for(**kw))


REF = date(2025, 7, 20)


def days(n):
    return REF + timedelta(days=n)
