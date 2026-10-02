"""Minimal osgeo.gdal replacement (ctypes over rasterio's bundled libgdal).

Implements only what ACOLITE's Sentinel-2 L1C path uses: Open, Dataset /
Band reads, MEM driver Create + WriteArray, and Warp. Warp builds the same
option list the official bindings' gdal.WarpOptions() would build for the
supported keywords and hands it to GDAL's own GDALWarp(). Any unsupported
keyword or attribute raises instead of silently diverging.
"""
import atexit, ctypes, os
import numpy as np

from . import _lib as L

__version__ = L.GDALVersionInfo(b'RELEASE_NAME').decode()
_SHIM = True

GA_ReadOnly, GA_Update = 0, 1
GF_Read, GF_Write = 0, 1

GDT_Unknown = 0
GDT_Byte = 1
GDT_UInt16 = 2
GDT_Int16 = 3
GDT_UInt32 = 4
GDT_Int32 = 5
GDT_Float32 = 6
GDT_Float64 = 7
GDT_UInt64 = 12
GDT_Int64 = 13
GDT_Int8 = 14

_NP = {GDT_Byte: np.uint8, GDT_UInt16: np.uint16, GDT_Int16: np.int16, GDT_UInt32: np.uint32,
       GDT_Int32: np.int32, GDT_Float32: np.float32, GDT_Float64: np.float64,
       GDT_UInt64: np.uint64, GDT_Int64: np.int64, GDT_Int8: np.int8}
_FROM_NP = {np.dtype(v): k for k, v in _NP.items()}

_use_exceptions = True
_shutting_down = False


def _at_exit():
    global _shutting_down
    _shutting_down = True  # leak handles at interpreter exit rather than close in random GC order


atexit.register(_at_exit)


def UseExceptions():
    global _use_exceptions
    _use_exceptions = True


def DontUseExceptions():
    global _use_exceptions
    _use_exceptions = False


def GetUseExceptions():
    return int(_use_exceptions)


def SetConfigOption(key, value):
    L.CPLSetConfigOption(str(key).encode(), None if value is None else str(value).encode())


def GetConfigOption(key, default=None):
    r = L.CPLGetConfigOption(str(key).encode(), None if default is None else str(default).encode())
    return None if r is None else r.decode()


def _fail(msg):
    if _use_exceptions:
        raise RuntimeError(msg)
    return None


class Band:
    def __init__(self, ds, h):
        self._ds = ds  # keep dataset alive
        self._h = h

    @property
    def DataType(self):
        return L.GDALGetRasterDataType(self._h)

    @property
    def XSize(self):
        return self._ds.RasterXSize

    @property
    def YSize(self):
        return self._ds.RasterYSize

    def GetNoDataValue(self):
        ok = ctypes.c_int(0)
        v = L.GDALGetRasterNoDataValue(self._h, ctypes.byref(ok))
        return v if ok.value else None

    def SetNoDataValue(self, v):
        return L.GDALSetRasterNoDataValue(self._h, float(v))

    def ReadAsArray(self, xoff=0, yoff=0, win_xsize=None, win_ysize=None,
                    buf_xsize=None, buf_ysize=None, buf_type=None, buf_obj=None, **kw):
        if buf_xsize is not None or buf_ysize is not None or buf_obj is not None or kw:
            raise NotImplementedError('osgeo shim: ReadAsArray buffer resampling options not supported')
        if win_xsize is None: win_xsize = self._ds.RasterXSize - xoff
        if win_ysize is None: win_ysize = self._ds.RasterYSize - yoff
        dt = self.DataType if buf_type is None else buf_type
        if dt not in _NP:
            raise NotImplementedError('osgeo shim: data type {} not supported'.format(dt))
        arr = np.empty((int(win_ysize), int(win_xsize)), dtype=_NP[dt])
        err = L.GDALRasterIO(self._h, GF_Read, int(xoff), int(yoff), int(win_xsize), int(win_ysize),
                             arr.ctypes.data_as(ctypes.c_void_p), int(win_xsize), int(win_ysize), dt, 0, 0)
        if err >= 3:
            return _fail('RasterIO read failed: ' + L.last_error())
        return arr

    def WriteArray(self, array, xoff=0, yoff=0, **kw):
        if kw:
            raise NotImplementedError('osgeo shim: WriteArray options not supported')
        a = np.asarray(array)
        if a.ndim != 2:
            raise ValueError('WriteArray expects a 2D array')
        dt = _FROM_NP.get(a.dtype)
        if dt is None:
            a = a.astype(np.float64); dt = GDT_Float64
        a = np.ascontiguousarray(a)
        ny, nx = a.shape
        err = L.GDALRasterIO(self._h, GF_Write, int(xoff), int(yoff), nx, ny,
                             a.ctypes.data_as(ctypes.c_void_p), nx, ny, dt, 0, 0)
        if err >= 3:
            return _fail('RasterIO write failed: ' + L.last_error())
        return 0

    def FlushCache(self):
        pass


class Dataset:
    def __init__(self, h, keep=None, refs=None):
        self._h = h
        self._keep = keep or []  # warp sources we opened: closed after this one
        self._refs = refs or []  # caller-supplied warp sources: only kept alive

    def _handle(self):
        if not self._h:
            raise RuntimeError('dataset is closed')
        return self._h

    @property
    def RasterXSize(self):
        return L.GDALGetRasterXSize(self._handle())

    @property
    def RasterYSize(self):
        return L.GDALGetRasterYSize(self._handle())

    @property
    def RasterCount(self):
        return L.GDALGetRasterCount(self._handle())

    def GetRasterBand(self, i):
        hb = L.GDALGetRasterBand(self._handle(), int(i))
        if not hb:
            return _fail('band {} not found'.format(i))
        return Band(self, hb)

    def GetGeoTransform(self, can_return_null=None):
        gt = (ctypes.c_double * 6)()
        L.GDALGetGeoTransform(self._handle(), gt)
        return tuple(gt)

    def SetGeoTransform(self, gt):
        arr = (ctypes.c_double * 6)(*[float(v) for v in gt])
        return L.GDALSetGeoTransform(self._handle(), arr)

    def GetProjection(self):
        r = L.GDALGetProjectionRef(self._handle())
        return r.decode() if r else ''

    GetProjectionRef = GetProjection

    def SetProjection(self, wkt):
        return L.GDALSetProjection(self._handle(), (wkt or '').encode())

    def GetMetadata(self, domain=''):
        p = L.GDALGetMetadata(self._handle(), domain.encode() if domain else None)
        out = {}
        if p:
            i = 0
            while p[i] is not None:
                kv = p[i].decode('utf-8', 'replace')
                if '=' in kv:
                    k, v = kv.split('=', 1)
                    out[k] = v
                i += 1
        return out

    GetMetadata_Dict = GetMetadata

    def ReadAsArray(self, xoff=0, yoff=0, xsize=None, ysize=None, **kw):
        if kw:
            raise NotImplementedError('osgeo shim: Dataset.ReadAsArray options not supported')
        n = self.RasterCount
        arrs = [self.GetRasterBand(i + 1).ReadAsArray(xoff, yoff, xsize, ysize) for i in range(n)]
        return arrs[0] if n == 1 else np.stack(arrs)

    def FlushCache(self):
        if self._h:
            L.GDALFlushCache(self._h)

    def Close(self):
        if self._h:
            L.GDALClose(self._h)
            self._h = None
        for k in self._keep:
            k.Close()
        self._keep = []
        self._refs = []

    def __del__(self):
        if _shutting_down:
            return
        try:
            self.Close()
        except Exception:
            pass


class Driver:
    def __init__(self, h, name):
        self._h = h
        self.ShortName = name

    def Create(self, name, xsize, ysize, bands=1, eType=GDT_Byte, options=None):
        if options:
            raise NotImplementedError('osgeo shim: creation options not supported')
        h = L.GDALCreate(self._h, (name or '').encode(), int(xsize), int(ysize), int(bands), int(eType), None)
        if not h:
            return _fail('Create failed: ' + L.last_error())
        return Dataset(h)


def GetDriverByName(name):
    h = L.GDALGetDriverByName(name.encode())
    if not h:
        return None
    return Driver(h, name)


def Open(path, eAccess=GA_ReadOnly):
    L.CPLErrorReset()
    h = L.GDALOpen(os.fspath(path).encode(), int(eAccess))
    if not h:
        return _fail(L.last_error() or '{}: No such file or directory'.format(path))
    return Dataset(h)


def _strHighPrec(x):
    return ('%.18g' % x) if isinstance(x, float) else str(x)


def _addOptions(new_options, arg, options):
    if isinstance(options, str):
        new_options += [arg, options]
    elif isinstance(options, dict):
        for k, v in options.items():
            new_options += [arg, f'{k}={v}']
    else:
        for opt in options:
            new_options += [arg, opt]


_WARP_SUPPORTED = {'format', 'outputBounds', 'outputBoundsSRS', 'xRes', 'yRes', 'targetAlignedPixels',
                   'width', 'height', 'srcSRS', 'dstSRS', 'resampleAlg', 'srcNodata', 'dstNodata',
                   'rpc', 'transformerOptions', 'options'}


def WarpOptions(options=None, format=None, outputBounds=None, outputBoundsSRS=None,
                xRes=None, yRes=None, targetAlignedPixels=False, width=0, height=0,
                srcSRS=None, dstSRS=None, resampleAlg=None, srcNodata=None, dstNodata=None,
                rpc=False, transformerOptions=None):
    """Same argument -> CLI-string translation as osgeo.gdal.WarpOptions (GDAL 3.12)
    for the supported subset of keywords."""
    new_options = list(options) if options else []
    if format is not None:
        new_options += ['-of', format]
    if outputBounds is not None:
        new_options += ['-te'] + [_strHighPrec(outputBounds[i]) for i in range(4)]
    if outputBoundsSRS is not None:
        new_options += ['-te_srs', str(outputBoundsSRS)]
    if xRes is not None and yRes is not None:
        new_options += ['-tr', _strHighPrec(xRes), _strHighPrec(yRes)]
    if width != 0 or height != 0:
        new_options += ['-ts', str(width), str(height)]
    if srcSRS is not None:
        new_options += ['-s_srs', str(srcSRS)]
    if dstSRS is not None:
        new_options += ['-t_srs', str(dstSRS)]
    if targetAlignedPixels:
        new_options += ['-tap']
    if resampleAlg is not None:
        new_options += ['-r', str(resampleAlg)]
    if srcNodata is not None:
        new_options += ['-srcnodata', str(srcNodata)]
    if dstNodata is not None:
        new_options += ['-dstnodata', str(dstNodata)]
    if rpc:
        new_options += ['-rpc']
    if transformerOptions is not None:
        _addOptions(new_options, '-to', transformerOptions)
    return new_options


def Warp(destNameOrDestDS, srcDSOrSrcDSTab, **kwargs):
    bad = set(kwargs) - _WARP_SUPPORTED
    if bad:
        raise NotImplementedError('osgeo shim: Warp keywords not supported: {}'.format(sorted(bad)))
    if not isinstance(destNameOrDestDS, (str, os.PathLike)):
        raise NotImplementedError('osgeo shim: Warp into an existing dataset not supported')
    opts = WarpOptions(**kwargs)

    srcs = srcDSOrSrcDSTab if isinstance(srcDSOrSrcDSTab, list) else [srcDSOrSrcDSTab]
    src_objs = [Open(s) if isinstance(s, (str, os.PathLike)) else s for s in srcs]
    handles = (ctypes.c_void_p * len(src_objs))(*[s._handle() for s in src_objs])

    argv = L.str_list(opts)
    popts = L.GDALWarpAppOptionsNew(argv, None)
    if not popts:
        return _fail('GDALWarpAppOptionsNew failed: ' + L.last_error())
    usage_err = ctypes.c_int(0)
    L.CPLErrorReset()
    h = L.GDALWarp(os.fspath(destNameOrDestDS).encode(), None, len(src_objs), handles, popts,
                   ctypes.byref(usage_err))
    L.GDALWarpAppOptionsFree(popts)
    if not h:
        return _fail('GDALWarp failed: ' + L.last_error())
    # A VRT output references its sources; keep the source objects we opened
    # alive until the result is closed (caller-supplied datasets are theirs).
    keep = [s for s, orig in zip(src_objs, srcs) if isinstance(orig, (str, os.PathLike))]
    refs = [s for s, orig in zip(src_objs, srcs) if not isinstance(orig, (str, os.PathLike))]
    return Dataset(h, keep=keep, refs=refs)


def __getattr__(name):
    raise NotImplementedError('osgeo shim: gdal.{} not implemented'.format(name))
