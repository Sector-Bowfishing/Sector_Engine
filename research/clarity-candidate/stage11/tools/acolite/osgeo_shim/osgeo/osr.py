"""Minimal osgeo.osr (ctypes over rasterio's libgdal): WKT/EPSG/PROJ round-trips only."""
import ctypes
from . import _lib as L

OAMS_TRADITIONAL_GIS_ORDER, OAMS_AUTHORITY_COMPLIANT = 0, 1


def UseExceptions():
    pass


def DontUseExceptions():
    pass


class SpatialReference:
    def __init__(self, wkt=''):
        self._h = L.OSRNewSpatialReference(wkt.encode() if wkt else None)

    def ImportFromWkt(self, wkt):
        p = ctypes.c_char_p(wkt.encode())
        err = L.OSRImportFromWkt(self._h, ctypes.byref(p))
        if err:
            raise RuntimeError('OSRImportFromWkt failed: ' + L.last_error())
        return 0

    def ImportFromEPSG(self, code):
        err = L.OSRImportFromEPSG(self._h, int(code))
        if err:
            raise RuntimeError('OSRImportFromEPSG failed: ' + L.last_error())
        return 0

    def ImportFromProj4(self, s):
        err = L.OSRImportFromProj4(self._h, s.encode())
        if err:
            raise RuntimeError('OSRImportFromProj4 failed: ' + L.last_error())
        return 0

    def ExportToWkt(self, options=None):
        if options:
            raise NotImplementedError('osgeo shim: ExportToWkt options')
        out = ctypes.c_void_p()
        L.OSRExportToWkt(self._h, ctypes.byref(out))
        return L.take_string(out.value)

    def ExportToProj4(self):
        out = ctypes.c_void_p()
        L.OSRExportToProj4(self._h, ctypes.byref(out))
        return L.take_string(out.value)

    def __del__(self):
        from . import gdal as _g
        if _g._shutting_down:
            return
        try:
            if self._h:
                L.OSRDestroySpatialReference(self._h)
                self._h = None
        except Exception:
            pass


def __getattr__(name):
    raise NotImplementedError('osgeo shim: osr.{} not implemented'.format(name))
