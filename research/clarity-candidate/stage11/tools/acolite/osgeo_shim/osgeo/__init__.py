"""Minimal ctypes-based stand-in for the GDAL Python bindings (osgeo).

Backed by the libgdal bundled in the rasterio wheel. Only the subset of the
API that ACOLITE's Sentinel-2 L1C -> L2R/L2W path uses is implemented; anything
else raises NotImplementedError. See gdal.py.
"""
from . import _lib
__version__ = _lib.GDALVersionInfo(b'RELEASE_NAME').decode()
