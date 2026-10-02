"""ctypes binding to the libgdal that ships inside the rasterio wheel.

No GDAL Python bindings (osgeo) are installable here: PyPI has no binary
GDAL wheels for macOS and there is no system GDAL/conda. rasterio bundles a
full libgdal (3.12.4, with JP2OpenJPEG). This module loads that exact
library (the same instance rasterio uses) and exposes the handful of C API
calls ACOLITE's Sentinel-2 path needs, so warps go through GDAL's own
gdalwarp code (GDALWarp + GDALWarpAppOptionsNew), not a re-implementation.
"""
import ctypes, glob, os

import rasterio  # noqa: F401  (initialises GDAL_DATA / PROJ data paths, registers drivers)

_dylibs = os.path.join(os.path.dirname(rasterio.__file__), '.dylibs')
_cands = sorted(glob.glob(os.path.join(_dylibs, 'libgdal*.dylib')) +
                glob.glob(os.path.join(os.path.dirname(rasterio.__file__), '..', 'rasterio.libs', 'libgdal*.so*')))
if not _cands:
    raise ImportError('could not locate rasterio-bundled libgdal')
LIBPATH = _cands[0]
lib = ctypes.CDLL(LIBPATH)

c_void_p, c_int, c_char_p, c_double = ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_double
c_char_pp = ctypes.POINTER(ctypes.c_char_p)

def _sig(name, restype, argtypes):
    f = getattr(lib, name)
    f.restype = restype
    f.argtypes = argtypes
    return f

GDALAllRegister = _sig('GDALAllRegister', None, [])
GDALOpen = _sig('GDALOpen', c_void_p, [c_char_p, c_int])
GDALClose = _sig('GDALClose', c_int, [c_void_p])
GDALGetRasterXSize = _sig('GDALGetRasterXSize', c_int, [c_void_p])
GDALGetRasterYSize = _sig('GDALGetRasterYSize', c_int, [c_void_p])
GDALGetRasterCount = _sig('GDALGetRasterCount', c_int, [c_void_p])
GDALGetRasterBand = _sig('GDALGetRasterBand', c_void_p, [c_void_p, c_int])
GDALGetGeoTransform = _sig('GDALGetGeoTransform', c_int, [c_void_p, ctypes.POINTER(c_double)])
GDALSetGeoTransform = _sig('GDALSetGeoTransform', c_int, [c_void_p, ctypes.POINTER(c_double)])
GDALGetProjectionRef = _sig('GDALGetProjectionRef', c_char_p, [c_void_p])
GDALSetProjection = _sig('GDALSetProjection', c_int, [c_void_p, c_char_p])
GDALGetMetadata = _sig('GDALGetMetadata', c_char_pp, [c_void_p, c_char_p])
GDALFlushCache = _sig('GDALFlushCache', c_int, [c_void_p])
GDALGetDriverByName = _sig('GDALGetDriverByName', c_void_p, [c_char_p])
GDALCreate = _sig('GDALCreate', c_void_p, [c_void_p, c_char_p, c_int, c_int, c_int, c_int, c_char_pp])
GDALGetRasterDataType = _sig('GDALGetRasterDataType', c_int, [c_void_p])
GDALGetRasterNoDataValue = _sig('GDALGetRasterNoDataValue', c_double, [c_void_p, ctypes.POINTER(c_int)])
GDALSetRasterNoDataValue = _sig('GDALSetRasterNoDataValue', c_int, [c_void_p, c_double])
GDALRasterIO = _sig('GDALRasterIO', c_int, [c_void_p, c_int, c_int, c_int, c_int, c_int,
                                            c_void_p, c_int, c_int, c_int, c_int, c_int])
GDALWarpAppOptionsNew = _sig('GDALWarpAppOptionsNew', c_void_p, [c_char_pp, c_void_p])
GDALWarpAppOptionsFree = _sig('GDALWarpAppOptionsFree', None, [c_void_p])
GDALWarp = _sig('GDALWarp', c_void_p, [c_char_p, c_void_p, c_int, ctypes.POINTER(c_void_p), c_void_p,
                                      ctypes.POINTER(c_int)])
GDALVersionInfo = _sig('GDALVersionInfo', c_char_p, [c_char_p])
CPLGetLastErrorMsg = _sig('CPLGetLastErrorMsg', c_char_p, [])
CPLErrorReset = _sig('CPLErrorReset', None, [])
CPLSetConfigOption = _sig('CPLSetConfigOption', None, [c_char_p, c_char_p])
CPLGetConfigOption = _sig('CPLGetConfigOption', c_char_p, [c_char_p, c_char_p])
VSIFree = _sig('VSIFree', None, [c_void_p])

OSRNewSpatialReference = _sig('OSRNewSpatialReference', c_void_p, [c_char_p])
OSRDestroySpatialReference = _sig('OSRDestroySpatialReference', None, [c_void_p])
OSRImportFromWkt = _sig('OSRImportFromWkt', c_int, [c_void_p, ctypes.POINTER(c_char_p)])
OSRImportFromEPSG = _sig('OSRImportFromEPSG', c_int, [c_void_p, c_int])
OSRImportFromProj4 = _sig('OSRImportFromProj4', c_int, [c_void_p, c_char_p])
OSRExportToWkt = _sig('OSRExportToWkt', c_int, [c_void_p, ctypes.POINTER(c_void_p)])
OSRExportToProj4 = _sig('OSRExportToProj4', c_int, [c_void_p, ctypes.POINTER(c_void_p)])

GDALAllRegister()


def last_error():
    m = CPLGetLastErrorMsg()
    return m.decode('utf-8', 'replace') if m else ''


def str_list(items):
    """NULL-terminated char** from a list of str."""
    arr = (ctypes.c_char_p * (len(items) + 1))()
    for i, s in enumerate(items):
        arr[i] = s.encode('utf-8')
    arr[len(items)] = None
    return arr


def take_string(ptr):
    """Copy and free a GDAL-allocated char*."""
    if not ptr:
        return ''
    s = ctypes.cast(ptr, ctypes.c_char_p).value.decode('utf-8', 'replace')
    VSIFree(ptr)
    return s
