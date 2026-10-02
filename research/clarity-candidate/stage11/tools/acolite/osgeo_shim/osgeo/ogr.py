"""Placeholder osgeo.ogr: ACOLITE imports it at package load (ogr.DontUseExceptions()).
The Sentinel-2 path used here (JP2 detector footprints, rectangular limit, no polygon)
needs no OGR; anything else raises NotImplementedError."""
wkbPolygon, wkbLinearRing = 3, 101


def UseExceptions():
    pass


def DontUseExceptions():
    pass


def __getattr__(name):
    raise NotImplementedError('osgeo shim: ogr.{} not implemented'.format(name))
